"""Rutas de la pantalla de Vender y cobrar.

Solo las usa la computadora de la tienda (el celular nada más manda escaneos).
Toda la lógica de dinero e inventario vive en tienda/; aquí solo se traduce
entre la pantalla y esos módulos.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from tienda import productos, ventas
from tienda.nucleo import dinero
from tienda.nucleo.base_datos import BaseDatos
from tienda.nucleo.errores import DatoInvalido, ErrorTienda, NoEncontrado

CELULAR_VIGENTE_S = 6  # el celular saluda cada 2 s; si calla 6 s, lo damos por desconectado


def producto_json(p: productos.Producto) -> dict:
    return {
        "id": p.id, "codigo": p.codigo, "nombre": p.nombre, "unidad": p.unidad,
        "precio": p.precio_venta, "existencia": p.existencia,
        "costo": p.costo_promedio, "minimo": p.minimo, "activo": p.activo,
    }


class Renglon(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=10_000_000)


class Cobro(BaseModel):
    operacion: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    renglones: list[Renglon] = Field(min_length=1, max_length=500)
    recibido: int = Field(description="centavos")
    total_visto: int = Field(description="el total que mostraba la pantalla, en centavos")


class Cancelacion(BaseModel):
    motivo: str = Field(min_length=1, max_length=200)


class Recibos:
    """Recuerda los últimos cobros por su número de operación: si la pantalla
    reintenta (doble Enter, red lenta), no se cobra dos veces."""

    def __init__(self, capacidad: int = 200) -> None:
        self._hechos: OrderedDict[str, dict] = OrderedDict()
        self._capacidad = capacidad

    def ya(self, operacion: str) -> dict | None:
        return self._hechos.get(operacion)

    def guardar(self, operacion: str, recibo: dict) -> None:
        self._hechos[operacion] = recibo
        while len(self._hechos) > self._capacidad:
            self._hechos.popitem(last=False)


class Celular:
    """Saber si hay un celular conectado: cada saludo suyo deja la hora."""

    def __init__(self, reloj: Callable[[], float] = time.monotonic) -> None:
        self._reloj = reloj
        self._ultimo: float | None = None

    def saludo(self) -> None:
        self._ultimo = self._reloj()

    @property
    def conectado(self) -> bool:
        return self._ultimo is not None and self._reloj() - self._ultimo < CELULAR_VIGENTE_S


def crear_rutas(bd: BaseDatos, exigir_local: Callable[[Request], None], celular: Celular, *,
                ejemplo: bool = False) -> APIRouter:
    rutas = APIRouter(dependencies=[Depends(exigir_local)])
    recibos = Recibos()

    @rutas.get("/api/vender/estado")
    def estado():
        return {"celular": celular.conectado, "ejemplo": ejemplo}

    @rutas.get("/api/productos")
    def buscar(q: str = ""):
        return [producto_json(p) for p in productos.buscar(bd, q[:80], limite=8)]

    @rutas.get("/api/productos/codigo/{codigo}")
    def por_codigo(codigo: str):
        p = productos.por_codigo(bd, codigo[:64])
        if p is None:
            raise HTTPException(status_code=404, detail="Ese código no está registrado")
        return producto_json(p)

    @rutas.post("/api/ventas/cobrar")
    def cobrar(cobro: Cobro):
        previo = recibos.ya(cobro.operacion)
        if previo is not None:
            return previo
        pedidos = [ventas.Pedido(r.producto_id, r.cantidad) for r in cobro.renglones]
        cuenta = ventas.cotizar(bd, pedidos)
        if cuenta.total != cobro.total_visto:
            raise DatoInvalido(
                f"El total cambió a {dinero.formatear(cuenta.total)} (algún precio se modificó). Revisa la cuenta."
            )
        r = ventas.cobrar_efectivo(bd, pedidos, cobro.recibido)
        recibo = {"venta_id": r.venta_id, "total": r.total, "recibido": r.recibido, "cambio": r.cambio}
        recibos.guardar(cobro.operacion, recibo)
        return recibo

    @rutas.post("/api/ventas/{venta_id}/cancelar")
    def cancelar(venta_id: int, c: Cancelacion):
        ventas.cancelar(bd, venta_id, c.motivo)
        return {"venta_id": venta_id, "estado": "cancelada"}

    return rutas


async def error_de_tienda(_: Request, error: ErrorTienda) -> JSONResponse:
    """Los errores de la tienda ya vienen en palabras sencillas: se muestran tal cual."""
    estado = 404 if isinstance(error, NoEncontrado) else 422
    return JSONResponse({"detail": error.mensaje}, status_code=estado)
