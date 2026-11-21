"""Rutas de las pantallas de Fiado y Corte de caja, y de vender fiado desde Vender."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from tienda import caja, fiado, ventas
from tienda.nucleo import dinero, reloj
from tienda.nucleo.base_datos import BaseDatos
from tienda.nucleo.errores import DatoInvalido

from .vender import Recibos, Renglon


def cliente_json(c: fiado.Cliente) -> dict:
    return {"id": c.id, "nombre": c.nombre, "telefono": c.telefono, "nota": c.nota, "activo": c.activo,
            "saldo": c.saldo}


class ClienteNuevo(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    telefono: str | None = Field(default=None, max_length=30)
    nota: str | None = Field(default=None, max_length=120)


class ClienteCambios(BaseModel):
    nombre: str | None = Field(default=None, max_length=60)
    telefono: str | None = Field(default=None, max_length=30)
    nota: str | None = Field(default=None, max_length=120)


class Abono(BaseModel):
    operacion: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    monto: str | None = Field(default=None, max_length=20, description="pesos como se escriben")
    todo: bool = Field(default=False, description="botón Pagó todo")


class Fiar(BaseModel):
    operacion: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    renglones: list[Renglon] = Field(min_length=1, max_length=500)
    total_visto: int
    cliente_id: int = Field(gt=0)


class Dinero(BaseModel):
    monto: str = Field(min_length=1, max_length=20)
    nota: str | None = Field(default=None, max_length=120)


def _que_se_llevo(bd: BaseDatos, venta_id: int) -> str:
    """"2 Coca-Cola 600 ml, ½ kg Huevo blanco" para el historial del cliente."""
    partes = []
    for r in ventas.obtener(bd, venta_id)["renglones"]:
        if r["unidad"] == "kg":
            kilos = r["cantidad"] / 1000
            cuanto = ("½" if kilos == 0.5 else f"{kilos:g}".replace(".5", "½")) + " kg"
        else:
            cuanto = str(r["cantidad"])
        partes.append(f"{cuanto} {r['nombre']}")
    return ", ".join(partes)


def detalle_cliente(bd: BaseDatos, cliente_id: int) -> dict:
    c = fiado.obtener(bd, cliente_id)
    movimientos = []
    for m in reversed(fiado.historial(bd, cliente_id)[-60:]):
        if m["tipo"] == "cargo" and m["venta_id"]:
            m["detalle"] = _que_se_llevo(bd, m["venta_id"])
        movimientos.append(m)
    return {**cliente_json(c), "movimientos": movimientos}


def estado_caja(bd: BaseDatos) -> dict:
    anteriores = caja.cortes_anteriores(bd, limite=8)
    if not caja.esta_abierta(bd):
        return {"abierta": False, "anteriores": anteriores}
    r = caja.resumen(bd)
    with bd.lectura() as con:
        retiros = [dict(f) for f in con.execute(
            "SELECT monto, nota, cuando FROM caja_retiros WHERE corte_id = ? ORDER BY id DESC", (r.corte_id,))]
    return {
        "abierta": True, "anteriores": anteriores, "abierto": r.abierto, "fondo": r.fondo,
        "ventas_efectivo": r.ventas_efectivo, "abonos": r.abonos, "retiros": r.retiros, "esperado": r.esperado,
        "lista_retiros": retiros, "ventas": ventas.resumen_entre(bd, r.abierto, None), "ahora": reloj.texto(),
    }


def crear_rutas(bd: BaseDatos, exigir_local: Callable[[Request], None]) -> APIRouter:
    rutas = APIRouter(dependencies=[Depends(exigir_local)])
    hechos = Recibos()

    # ------------------------------------------------------------ clientes

    @rutas.get("/api/clientes")
    def lista(q: str = ""):
        todos = fiado.buscar(bd, q[:60])
        todos.sort(key=lambda c: (c.saldo <= 0, -c.saldo, c.nombre.casefold()))
        return {"clientes": [cliente_json(c) for c in todos],
                "deben": sum(1 for c in todos if c.saldo > 0) if not q else None,
                "total": sum(c.saldo for c in todos if c.saldo > 0) if not q else None}

    @rutas.get("/api/clientes/{cliente_id}")
    def uno(cliente_id: int):
        return detalle_cliente(bd, cliente_id)

    @rutas.post("/api/clientes")
    def nuevo(c: ClienteNuevo):
        return detalle_cliente(bd, fiado.crear_cliente(bd, c.nombre, c.telefono, c.nota))

    @rutas.post("/api/clientes/{cliente_id}")
    def cambiar(cliente_id: int, c: ClienteCambios):
        fiado.editar_cliente(bd, cliente_id, nombre=c.nombre, telefono=c.telefono, nota=c.nota)
        return detalle_cliente(bd, cliente_id)

    @rutas.post("/api/clientes/{cliente_id}/quitar")
    def quitar(cliente_id: int):
        fiado.desactivar_cliente(bd, cliente_id)
        return {"id": cliente_id, "activo": False}

    @rutas.post("/api/clientes/{cliente_id}/abonar")
    def abonar(cliente_id: int, a: Abono):
        previo = hechos.ya(a.operacion)
        if previo is not None:
            return previo
        if a.todo:
            pago = fiado.pago_todo(bd, cliente_id)
        else:
            if not a.monto:
                raise DatoInvalido("Escribe cuánto pagó")
            pago = dinero.a_centavos(a.monto)
            fiado.abonar(bd, cliente_id, pago)
        hecho = {**detalle_cliente(bd, cliente_id), "pago": pago}
        hechos.guardar(a.operacion, hecho)
        return hecho

    @rutas.post("/api/ventas/fiar")
    def fiar(f: Fiar):
        previo = hechos.ya(f.operacion)
        if previo is not None:
            return previo
        pedidos = [ventas.Pedido(r.producto_id, r.cantidad) for r in f.renglones]
        with bd.transaccion():
            cuenta = ventas.cotizar(bd, pedidos)
            if cuenta.total != f.total_visto:
                raise DatoInvalido(
                    f"El total cambió a {dinero.formatear(cuenta.total)} (algún precio se modificó). Revisa la cuenta."
                )
            venta_id = ventas.vender_fiado(bd, pedidos, f.cliente_id)
        c = fiado.obtener(bd, f.cliente_id)
        hecho = {"venta_id": venta_id, "total": cuenta.total, "cliente": cliente_json(c)}
        hechos.guardar(f.operacion, hecho)
        return hecho

    # ------------------------------------------------------------ caja

    @rutas.get("/api/caja")
    def ver_caja():
        return estado_caja(bd)

    @rutas.post("/api/caja/abrir")
    def abrir(d: Dinero):
        caja.abrir(bd, dinero.a_centavos(d.monto, permitir_cero=True))
        return estado_caja(bd)

    @rutas.post("/api/caja/retiro")
    def retiro(d: Dinero):
        caja.retirar(bd, dinero.a_centavos(d.monto), d.nota or "")
        return estado_caja(bd)

    @rutas.post("/api/caja/cerrar")
    def cerrar(d: Dinero):
        ventas_del_turno = estado_caja(bd).get("ventas")
        nota = " ".join((d.nota or "").split()) or None
        corte = caja.cerrar(bd, dinero.a_centavos(d.monto, permitir_cero=True), nota)
        r = corte.resumen
        return {
            "corte_id": r.corte_id, "abierto": r.abierto, "fondo": r.fondo, "ventas_efectivo": r.ventas_efectivo,
            "abonos": r.abonos, "retiros": r.retiros, "esperado": r.esperado, "contado": corte.contado,
            "diferencia": corte.diferencia, "ventas": ventas_del_turno, "caja": estado_caja(bd),
        }

    return rutas
