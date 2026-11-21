"""Rutas de las pantallas de Productos y Llegó mercancía (solo desde la computadora)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from tienda import productos as P
from tienda.nucleo import dinero
from tienda.nucleo.base_datos import BaseDatos
from tienda.nucleo.errores import DatoInvalido

from .vender import Recibos, producto_json

FILTROS = ("todos", "acabando", "acabados", "desactivados")


def nivel(p: P.Producto) -> str:
    """bien / acabando / acabado, según la existencia contra el mínimo."""
    if p.existencia <= 0:
        return "acabado"
    if p.existencia <= p.minimo:
        return "acabando"
    return "bien"


def _dinero(texto: str | None, *, permitir_cero: bool = False) -> int | None:
    if texto is None:
        return None
    return dinero.a_centavos(texto, permitir_cero=permitir_cero)


class Alta(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    precio: str = Field(min_length=1, max_length=20, description="pesos cerrados, como se escribe")
    costo: str = Field(default="0", max_length=20, description="con centavos si hace falta")
    unidad: str = Field(pattern=r"^(pieza|kg)$")
    codigo: str | None = Field(default=None, max_length=64)
    minimo: int = Field(default=0, ge=0, le=10_000_000)


class Cambios(BaseModel):
    nombre: str | None = Field(default=None, max_length=80)
    precio: str | None = Field(default=None, max_length=20)
    costo: str | None = Field(default=None, max_length=20)
    codigo: str | None = Field(default=None, max_length=64, description="vacío = quitar el código")
    minimo: int | None = Field(default=None, ge=0, le=10_000_000)


class Conteo(BaseModel):
    contado: int = Field(ge=0, le=10_000_000)
    motivo: str = Field(min_length=1, max_length=200)


class RenglonLlegada(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=10_000_000)
    costo: int = Field(ge=0, description="centavos por pieza o por kilo")


class Llegada(BaseModel):
    operacion: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    renglones: list[RenglonLlegada] = Field(min_length=1, max_length=500)
    nota: str | None = Field(default=None, max_length=120)


def detalle(bd: BaseDatos, p: P.Producto) -> dict:
    return {**producto_json(p), "nivel": nivel(p), "historial": P.historial_precios(bd, p.id)[-6:][::-1]}


def crear_rutas(bd: BaseDatos, exigir_local: Callable[[Request], None]) -> APIRouter:
    rutas = APIRouter(dependencies=[Depends(exigir_local)])
    llegadas = Recibos()

    @rutas.get("/api/inventario")
    def lista(q: str = "", filtro: str = "todos"):
        if filtro not in FILTROS:
            raise DatoInvalido("Filtro desconocido")
        todos = P.buscar(bd, q[:80], incluir_inactivos=filtro == "desactivados", limite=1000)
        if filtro == "desactivados":
            todos = [p for p in todos if not p.activo]
        elif filtro in ("acabando", "acabados"):
            buscado = "acabando" if filtro == "acabando" else "acabado"
            todos = [p for p in todos if nivel(p) == buscado]
        cuenta = {"acabando": 0, "acabado": 0}
        for p in P.buscar(bd, limite=100_000):
            if nivel(p) in cuenta:
                cuenta[nivel(p)] += 1
        return {
            "productos": [{**producto_json(p), "nivel": nivel(p)} for p in todos],
            "acabando": cuenta["acabando"], "acabados": cuenta["acabado"],
        }

    @rutas.get("/api/inventario/{producto_id}")
    def uno(producto_id: int):
        return detalle(bd, P.obtener(bd, producto_id))

    @rutas.post("/api/inventario")
    def alta(a: Alta):
        nuevo = P.crear(bd, nombre=a.nombre, precio_venta=dinero.a_centavos(a.precio), unidad=a.unidad,
                        codigo=a.codigo or None, costo=dinero.a_centavos(a.costo, permitir_cero=True),
                        minimo=a.minimo)
        return detalle(bd, P.obtener(bd, nuevo))

    @rutas.post("/api/inventario/{producto_id}")
    def cambiar(producto_id: int, c: Cambios):
        with bd.transaccion():  # todo o nada: si el precio está mal, tampoco se cambia el nombre
            P.editar(bd, producto_id, nombre=c.nombre, precio_venta=_dinero(c.precio),
                     codigo=c.codigo or None if c.codigo is not None else None,
                     quitar_codigo=c.codigo is not None and not c.codigo.strip(), minimo=c.minimo)
            costo = _dinero(c.costo, permitir_cero=True)
            if costo is not None:
                P.corregir_costo(bd, producto_id, costo)
        return detalle(bd, P.obtener(bd, producto_id))

    @rutas.post("/api/inventario/{producto_id}/contar")
    def contar(producto_id: int, c: Conteo):
        diferencia = P.ajustar_conteo(bd, producto_id, c.contado, c.motivo)
        return {**detalle(bd, P.obtener(bd, producto_id)), "diferencia": diferencia}

    @rutas.post("/api/inventario/{producto_id}/desactivar")
    def desactivar(producto_id: int):
        P.desactivar(bd, producto_id)
        return detalle(bd, P.obtener(bd, producto_id))

    @rutas.post("/api/inventario/{producto_id}/reactivar")
    def reactivar(producto_id: int):
        P.reactivar(bd, producto_id)
        return detalle(bd, P.obtener(bd, producto_id))

    @rutas.post("/api/mercancia")
    def llego(l: Llegada):
        previo = llegadas.ya(l.operacion)
        if previo is not None:
            return previo
        nota = " ".join((l.nota or "").split()) or None
        P.registrar_llegada(bd, [P.Llegada(r.producto_id, r.cantidad, r.costo) for r in l.renglones], nota)
        hecho = {"renglones": len(l.renglones),
                 "productos": [producto_json(P.obtener(bd, r.producto_id)) for r in l.renglones]}
        llegadas.guardar(l.operacion, hecho)
        return hecho

    return rutas
