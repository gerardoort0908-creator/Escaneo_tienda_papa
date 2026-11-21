"""El servidor: páginas para el celular y la computadora, y la ruta que recibe escaneos."""

from __future__ import annotations

import io
import secrets
from dataclasses import dataclass, field
from pathlib import Path

import segno
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from tienda import productos
from tienda.nucleo.base_datos import BaseDatos
from tienda.nucleo.errores import ErrorTienda

from .certificados import RutasCertificados, sello_en_der
from .codigos import CodigoInvalido, normalizar
from .escaneos import Escaneo, Pantallas, RegistroEscaneos, ahora_ms, mensaje_de, registro
from . import fiado_caja, inventario, reportes_rutas
from .vender import Celular, crear_rutas, error_de_tienda, producto_json

ESTATICOS = Path(__file__).parent / "static"
LOCALES = {"127.0.0.1", "::1"}


@dataclass
class Configuracion:
    ip: str
    llave: str
    certificados: RutasCertificados | None
    puerto_http: int = 8000
    puerto_https: int = 8443
    ejemplo: bool = False  # datos de práctica, guardados aparte

    @property
    def url_celular(self) -> str:
        return f"https://{self.ip}:{self.puerto_https}/celular#llave={self.llave}"

    @property
    def url_sello(self) -> str:
        return f"http://{self.ip}:{self.puerto_http}/sello"


@dataclass
class Estado:
    config: Configuracion
    escaneos: RegistroEscaneos = field(default_factory=RegistroEscaneos)
    pantallas: Pantallas = field(default_factory=Pantallas)
    celular: Celular = field(default_factory=Celular)
    bd: BaseDatos | None = None


class EscaneoEntrante(BaseModel):
    id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    codigo: str = Field(min_length=1, max_length=64)
    formato: str = Field(min_length=1, max_length=20)
    t_detectado: float = Field(description="ms, ya corregido al reloj de la computadora")


def _es_local(host: str | None) -> bool:
    return host in LOCALES


def _exigir_local(request: Request) -> None:
    if not _es_local(request.client.host if request.client else None):
        raise HTTPException(status_code=403, detail="Solo desde la computadora de la tienda")


def _exigir_llave(request: Request, estado: Estado) -> None:
    dada = request.headers.get("x-llave", "")
    if not secrets.compare_digest(dada.encode(), estado.config.llave.encode()):
        raise HTTPException(status_code=401, detail="Llave incorrecta: vuelve a escanear el QR")


def crear_app(config: Configuracion, bd: BaseDatos | None = None) -> FastAPI:
    """Sin base de datos solo funciona la prueba del escáner; con ella, también Vender."""
    app = FastAPI(title="Tienda", docs_url=None, redoc_url=None, openapi_url=None)
    estado = Estado(config, bd=bd)
    app.state.estado = estado

    @app.middleware("http")
    async def sin_cache(request: Request, call_next):
        respuesta = await call_next(request)
        respuesta.headers["Cache-Control"] = "no-store"
        return respuesta

    app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")

    @app.get("/", include_in_schema=False)
    async def inicio(request: Request):
        principal = "/vender" if bd is not None else "/pantalla"
        destino = principal if _es_local(request.client.host if request.client else None) else "/celular"
        return RedirectResponse(destino)

    @app.get("/pantalla", include_in_schema=False)
    async def pantalla(request: Request):
        _exigir_local(request)
        return FileResponse(ESTATICOS / "pantalla.html")

    @app.get("/vender", include_in_schema=False)
    async def vender(request: Request):
        _exigir_local(request)
        if bd is None:
            raise HTTPException(status_code=404)
        return FileResponse(ESTATICOS / "vender.html")

    @app.get("/productos", include_in_schema=False)
    async def pagina_productos(request: Request):
        _exigir_local(request)
        if bd is None:
            raise HTTPException(status_code=404)
        return FileResponse(ESTATICOS / "productos.html")

    @app.get("/mercancia", include_in_schema=False)
    async def pagina_mercancia(request: Request):
        _exigir_local(request)
        if bd is None:
            raise HTTPException(status_code=404)
        return FileResponse(ESTATICOS / "mercancia.html")

    @app.get("/fiado", include_in_schema=False)
    async def pagina_fiado(request: Request):
        _exigir_local(request)
        if bd is None:
            raise HTTPException(status_code=404)
        return FileResponse(ESTATICOS / "fiado.html")

    @app.get("/caja", include_in_schema=False)
    async def pagina_caja(request: Request):
        _exigir_local(request)
        if bd is None:
            raise HTTPException(status_code=404)
        return FileResponse(ESTATICOS / "caja.html")

    @app.get("/reportes", include_in_schema=False)
    async def pagina_reportes(request: Request):
        _exigir_local(request)
        if bd is None:
            raise HTTPException(status_code=404)
        return FileResponse(ESTATICOS / "reportes.html")

    @app.get("/celular", include_in_schema=False)
    async def celular():
        return FileResponse(ESTATICOS / "celular.html")

    @app.get("/sello", include_in_schema=False)
    async def guia_sello():
        return FileResponse(ESTATICOS / "sello.html")

    @app.get("/sello-tienda.crt", include_in_schema=False)
    async def descargar_sello():
        if config.certificados is None:
            raise HTTPException(status_code=404)
        return Response(
            sello_en_der(config.certificados),
            media_type="application/x-x509-ca-cert",
            headers={"Content-Disposition": 'attachment; filename="sello-tienda.crt"'},
        )

    @app.get("/api/info")
    async def info(request: Request):
        _exigir_local(request)
        return {
            "ip": config.ip,
            "url_celular": config.url_celular,
            "url_sello": config.url_sello,
            "en_wifi": config.ip != "127.0.0.1",
        }

    @app.get("/api/qr.svg")
    async def qr(request: Request, que: str = "celular"):
        _exigir_local(request)
        url = config.url_sello if que == "sello" else config.url_celular
        salida = io.BytesIO()
        segno.make(url, error="m").save(salida, kind="svg", scale=8, border=2, dark="#151412", light="#f4efe4")
        return Response(salida.getvalue(), media_type="image/svg+xml")

    @app.get("/api/hora")
    async def hora(request: Request):
        """El celular la pide cada 2 s: así sabe cuánto se desfasa su reloj y la compu sabe que está conectado."""
        if not _es_local(request.client.host if request.client else None):
            estado.celular.saludo()
        return {"ts": ahora_ms()}

    @app.post("/api/escaneo")
    async def recibir(entrada: EscaneoEntrante, request: Request):
        _exigir_llave(request, estado)
        t_recibido = ahora_ms()
        try:
            codigo, formato = normalizar(entrada.codigo, entrada.formato)
        except CodigoInvalido as error:
            registro.info("Rechazado %s (%s): %s", entrada.codigo, entrada.formato, error)
            raise HTTPException(status_code=422, detail=str(error)) from error
        escaneo = Escaneo(entrada.id, codigo, formato, entrada.t_detectado, t_recibido)
        nuevo = estado.escaneos.agregar(escaneo)
        if nuevo:
            registro.info("Escaneo %s %s (%s)", escaneo.id, codigo, formato)
            mensaje = mensaje_de(escaneo)
            if bd is not None:
                producto = productos.por_codigo(bd, codigo)
                mensaje["producto"] = producto_json(producto) if producto else None
            await estado.pantallas.avisar(mensaje)
        return {"id": entrada.id, "codigo": codigo, "duplicado": not nuevo, "pantallas": estado.pantallas.cuantas}

    @app.websocket("/ws/pantalla")
    async def ws_pantalla(ws: WebSocket):
        if not _es_local(ws.client.host if ws.client else None):
            await ws.close(code=1008)
            return
        await ws.accept()
        estado.pantallas.conectar(ws)
        try:
            while True:
                mensaje = await ws.receive_json()
                if mensaje.get("tipo") == "mostrado":
                    registro.info(
                        "Mostrado %s en %.0f ms", mensaje.get("id"), float(mensaje.get("latencia_ms", 0))
                    )
        except (WebSocketDisconnect, ValueError):
            pass
        finally:
            estado.pantallas.desconectar(ws)

    if bd is not None:
        app.add_exception_handler(ErrorTienda, error_de_tienda)
        app.include_router(crear_rutas(bd, _exigir_local, estado.celular, ejemplo=config.ejemplo))
        app.include_router(inventario.crear_rutas(bd, _exigir_local))
        app.include_router(fiado_caja.crear_rutas(bd, _exigir_local))
        app.include_router(reportes_rutas.crear_rutas(bd, _exigir_local))

    return app
