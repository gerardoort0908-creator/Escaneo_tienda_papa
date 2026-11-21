"""La app del celular: se abre con el QR de "Conectar celular" y se instala en la pantalla de inicio.

Escanea o elige productos, cobra con cambio y guarda la venta en el celular, aunque la compu
esté apagada. Al prender la compu las ventas entran solas al programa (ventas, inventario,
reportes y corte de caja), cada una una sola vez aunque llegue repetida.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from tienda import productos, ventas
from tienda.nucleo.base_datos import BaseDatos
from tienda.nucleo.errores import ErrorTienda

ESTATICOS = Path(__file__).parent / "static"


class RenglonCelular(BaseModel):
    producto_id: int = Field(gt=0)
    nombre: str = Field(min_length=1, max_length=80)
    cantidad: int = Field(gt=0, le=100_000)
    precio: int = Field(gt=0, le=100_000_000)


class VentaCelular(BaseModel):
    id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    cuando: str = Field(min_length=19, max_length=19, description="AAAA-MM-DD HH:MM:SS, hora del celular")
    celular: str = Field(min_length=1, max_length=40)
    renglones: list[RenglonCelular] = Field(min_length=1, max_length=200)
    total: int = Field(gt=0)
    recibido: int = Field(gt=0)


class Paquete(BaseModel):
    ventas: list[VentaCelular] = Field(max_length=500)


def crear_rutas(bd: BaseDatos | None, llave: str, exigir_llave: Callable[[Request], None],
                avisar: Callable[[dict], Awaitable[None]]) -> APIRouter:
    rutas = APIRouter()

    # ---- lo que abre el celular (se guarda en el celular para funcionar sin la compu)
    def _es_la_llave(k: str) -> bool:
        return bool(k) and secrets.compare_digest(k.encode(), llave.encode())

    @rutas.get("/celular", include_in_schema=False)
    def pagina(llave_dada: str = Query("", alias="llave", max_length=200)):
        # El iPhone lee el manifiesto en cuanto abre la página: ya debe traer la llave para
        # que el icono de inicio la guarde (la app instalada no comparte memoria con Safari).
        html = (ESTATICOS / "celular.html").read_text(encoding="utf-8")
        if _es_la_llave(llave_dada):
            html = html.replace('href="/celular.webmanifest"', f'href="/celular.webmanifest?k={llave}"')
        return HTMLResponse(html)

    @rutas.get("/prueba", include_in_schema=False)
    def antes(request: Request):
        # Iconos que se agregaron a inicio cuando la app se llamaba "prueba".
        consulta = request.url.query
        return RedirectResponse("/celular" + (f"?{consulta}" if consulta else ""))

    @rutas.get("/celular-sw.js", include_in_schema=False)
    def trabajador():
        # Desde la raíz para que pueda atender /celular aunque la compu esté apagada.
        return FileResponse(ESTATICOS / "celular-sw.js", media_type="text/javascript",
                            headers={"Service-Worker-Allowed": "/"})

    @rutas.get("/celular.webmanifest", include_in_schema=False)
    def manifiesto(k: str = ""):
        # La app instalada en el iPhone no comparte memoria con Safari: le pasamos la llave al abrir.
        inicio = "/celular" + (f"?llave={llave}" if _es_la_llave(k) else "")
        datos = {
            "name": "Tienda", "short_name": "Tienda", "lang": "es", "display": "standalone",
            "start_url": inicio, "scope": "/", "background_color": "#0A0A0B", "theme_color": "#0A0A0B",
            "icons": [{"src": "/static/celular-icono.png", "sizes": "512x512", "type": "image/png"}],
        }
        return Response(json.dumps(datos), media_type="application/manifest+json")

    if bd is None:
        return rutas

    # ---- datos (con la llave del QR)
    @rutas.get("/api/celular/productos")
    def lista(request: Request):
        exigir_llave(request)
        return {"productos": [{"id": p.id, "nombre": p.nombre, "unidad": p.unidad, "precio": p.precio_venta,
                               "codigo": p.codigo}
                              for p in productos.buscar(bd, limite=100_000)]}

    @rutas.post("/api/celular/ventas")
    async def recibir(paquete: Paquete, request: Request):
        exigir_llave(request)
        guardadas, problemas, nuevas, total = [], {}, 0, 0
        for v in paquete.ventas:
            renglones = [ventas.DelCelular(r.producto_id, r.cantidad, r.precio) for r in v.renglones]
            try:
                venta_id, es_nueva = ventas.de_celular(bd, v.id, v.celular, v.cuando, renglones, v.recibido)
            except ErrorTienda as error:  # p. ej. un producto que ya no existe: esa venta se queda en el celular
                problemas[v.id] = str(error)
                continue
            guardadas.append(v.id)
            if es_nueva:
                nuevas += 1
                total += ventas.obtener(bd, venta_id)["total"]
        if nuevas:
            await avisar({"tipo": "ventas-celular", "nuevas": nuevas, "total": total})
        return {"guardadas": guardadas, "nuevas": nuevas, "problemas": problemas}

    return rutas
