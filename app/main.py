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

from .certificados import RutasCertificados, sello_en_der
from .codigos import CodigoInvalido, normalizar
from .escaneos import Escaneo, Pantallas, RegistroEscaneos, ahora_ms, mensaje_de, registro

ESTATICOS = Path(__file__).parent / "static"
LOCALES = {"127.0.0.1", "::1"}


@dataclass
class Configuracion:
    ip: str
    llave: str
    certificados: RutasCertificados | None
    puerto_http: int = 8000
    puerto_https: int = 8443

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


def crear_app(config: Configuracion) -> FastAPI:
    app = FastAPI(title="Prueba del escáner", docs_url=None, redoc_url=None, openapi_url=None)
    estado = Estado(config)
    app.state.estado = estado

    @app.middleware("http")
    async def sin_cache(request: Request, call_next):
        respuesta = await call_next(request)
        respuesta.headers["Cache-Control"] = "no-store"
        return respuesta

    app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")

    @app.get("/", include_in_schema=False)
    async def inicio(request: Request):
        destino = "/pantalla" if _es_local(request.client.host if request.client else None) else "/celular"
        return RedirectResponse(destino)

    @app.get("/pantalla", include_in_schema=False)
    async def pantalla(request: Request):
        _exigir_local(request)
        return FileResponse(ESTATICOS / "pantalla.html")

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
    async def hora():
        """El celular la pide varias veces para saber cuánto se desfasa su reloj."""
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
            await estado.pantallas.avisar(mensaje_de(escaneo))
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

    return app
