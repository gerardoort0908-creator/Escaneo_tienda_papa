"""Módulo de Ventas: cobrar en efectivo, vender fiado y cancelar.

Dueño de: ventas, venta_lineas.

Cada venta es todo-o-nada: se guarda la venta, sus renglones, la salida de
inventario y (si es fiada) el cargo al cliente, o no se guarda nada.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from . import fiado, productos
from .nucleo import dinero, registro, reloj
from .nucleo.base_datos import BaseDatos
from .nucleo.errores import DatoInvalido, NoEncontrado, NoPermitido, PagoInsuficiente

_log = registro.obtener("ventas")


@dataclass(frozen=True)
class Pedido:
    """Lo que el cliente se lleva: un producto y cuánto (piezas o gramos)."""

    producto_id: int
    cantidad: int


@dataclass(frozen=True)
class Renglon:
    producto_id: int
    nombre: str
    unidad: str
    cantidad: int
    precio_unitario: int
    subtotal: int
    costo: int


@dataclass(frozen=True)
class Cuenta:
    renglones: tuple[Renglon, ...]
    total: int
    costo_total: int

    @property
    def ganancia(self) -> int:
        return self.total - self.costo_total


@dataclass(frozen=True)
class Recibo:
    venta_id: int
    total: int
    recibido: int
    cambio: int


def subtotal(precio: int, cantidad: int, unidad: str) -> int:
    """Pieza: precio × piezas. Granel: precio por kilo × kilos, redondeado al peso
    (medio kilo de un huevo de $45 el kilo = $22.50 → $23)."""
    if unidad == "kg":
        return dinero.dividir_redondeando(precio * cantidad, 1000 * 100) * 100
    return precio * cantidad


def costo_de(costo_unitario: int, cantidad: int, unidad: str) -> int:
    if unidad == "kg":
        return dinero.dividir_redondeando(costo_unitario * cantidad, 1000)
    return costo_unitario * cantidad


def cotizar(bd: BaseDatos, pedidos: list[Pedido]) -> Cuenta:
    """El total que se muestra en pantalla antes de cobrar. No guarda nada."""
    juntos: dict[int, int] = {}
    for p in pedidos:  # el mismo producto escaneado dos veces va en un solo renglón
        juntos[p.producto_id] = juntos.get(p.producto_id, 0) + p.cantidad
    if not juntos:
        raise DatoInvalido("La cuenta está vacía")
    renglones = []
    for producto_id, cantidad in juntos.items():
        producto = productos.obtener(bd, producto_id)
        if not producto.activo:
            raise NoPermitido(f"«{producto.nombre}» está desactivado")
        productos.validar_cantidad_venta(producto.unidad, cantidad)
        renglones.append(Renglon(
            producto.id, producto.nombre, producto.unidad, cantidad, producto.precio_venta,
            subtotal(producto.precio_venta, cantidad, producto.unidad),
            costo_de(producto.costo_promedio, cantidad, producto.unidad),
        ))
    total = sum(r.subtotal for r in renglones)
    dinero.validar_centavos(total)
    return Cuenta(tuple(renglones), total, sum(r.costo for r in renglones))


def cobrar_efectivo(bd: BaseDatos, pedidos: list[Pedido], recibido: int) -> Recibo:
    """Guarda la venta y dice cuánto cambio dar."""
    dinero.validar_centavos(recibido)
    with bd.transaccion() as con:
        cuenta = cotizar(bd, pedidos)
        if recibido < cuenta.total:
            faltan = dinero.formatear(cuenta.total - recibido)
            raise PagoInsuficiente(f"Faltan {faltan}")
        cambio = recibido - cuenta.total
        venta_id = _guardar(bd, con, cuenta, "efectivo", recibido=recibido, cambio=cambio)
    _log.info("Venta %d efectivo %s, recibió %s, cambio %s", venta_id, dinero.formatear(cuenta.total),
              dinero.formatear(recibido), dinero.formatear(cambio))
    return Recibo(venta_id, cuenta.total, recibido, cambio)


def vender_fiado(bd: BaseDatos, pedidos: list[Pedido], cliente_id: int) -> int:
    with bd.transaccion() as con:
        cuenta = cotizar(bd, pedidos)
        venta_id = _guardar(bd, con, cuenta, "fiado", cliente_id=cliente_id)
        fiado.cargar_venta(bd, cliente_id, venta_id, cuenta.total)
    _log.info("Venta %d fiada a cliente %d por %s", venta_id, cliente_id, dinero.formatear(cuenta.total))
    return venta_id


def cancelar(bd: BaseDatos, venta_id: int, motivo: str) -> None:
    """Regresa la mercancía al inventario y, si fue fiada, quita el cargo. La venta
    queda guardada como cancelada (no se borra)."""
    motivo = " ".join((motivo or "").split())
    if not motivo:
        raise DatoInvalido("Escribe por qué se cancela")
    with bd.transaccion() as con:
        venta = _fila(con, venta_id)
        if venta["estado"] == "cancelada":
            raise NoPermitido("Esa venta ya estaba cancelada")
        con.execute("UPDATE ventas SET estado = 'cancelada', cancelada = ?, motivo_cancel = ? WHERE id = ?",
                    (reloj.texto(), motivo, venta_id))
        productos.regreso_por_cancelacion(bd, venta_id)
        if venta["forma_pago"] == "fiado":
            fiado.cancelar_cargo(bd, venta_id)
    _log.info("Venta %d cancelada: %s", venta_id, motivo)


def obtener(bd: BaseDatos, venta_id: int) -> dict:
    with bd.lectura() as con:
        venta = _fila(con, venta_id)
        lineas = con.execute(
            "SELECT producto_id, nombre, unidad, cantidad, precio_unitario, subtotal, costo"
            " FROM venta_lineas WHERE venta_id = ? ORDER BY id", (venta_id,),
        ).fetchall()
    return {**dict(venta), "renglones": [dict(l) for l in lineas]}


def efectivo_entre(bd: BaseDatos, desde: str, hasta: str | None) -> int:
    """Efectivo cobrado (sin cambio) en ese rango de horas; lo usa el corte de caja."""
    with bd.lectura() as con:
        return con.execute(
            "SELECT COALESCE(SUM(total), 0) FROM ventas WHERE forma_pago = 'efectivo' AND estado = 'hecha'"
            " AND cuando >= ? AND (? IS NULL OR cuando < ?)", (desde, hasta, hasta),
        ).fetchone()[0]


def _guardar(bd: BaseDatos, con: sqlite3.Connection, cuenta: Cuenta, forma_pago: str, *,
             recibido: int | None = None, cambio: int | None = None, cliente_id: int | None = None) -> int:
    venta_id = con.execute(
        "INSERT INTO ventas (cuando, forma_pago, total, costo_total, recibido, cambio, cliente_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (reloj.texto(), forma_pago, cuenta.total, cuenta.costo_total, recibido, cambio, cliente_id),
    ).lastrowid
    for r in cuenta.renglones:
        con.execute(
            "INSERT INTO venta_lineas (venta_id, producto_id, nombre, unidad, cantidad, precio_unitario, subtotal, costo)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (venta_id, r.producto_id, r.nombre, r.unidad, r.cantidad, r.precio_unitario, r.subtotal, r.costo),
        )
        productos.salida_por_venta(bd, venta_id, r.producto_id, r.cantidad)
    return venta_id


def _fila(con: sqlite3.Connection, venta_id: int) -> sqlite3.Row:
    fila = con.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("Esa venta no existe")
    return fila


def resumen_entre(bd: BaseDatos, desde: str, hasta: str | None) -> dict:
    """Cuántas ventas hubo en ese rango de horas, cuánto se vendió y cuánto se ganó (lo usa el corte)."""
    with bd.lectura() as con:
        fila = con.execute(
            "SELECT COUNT(*) AS ventas,"
            " COALESCE(SUM(total), 0) AS vendido,"
            " COALESCE(SUM(CASE WHEN forma_pago = 'efectivo' THEN total END), 0) AS efectivo,"
            " COALESCE(SUM(CASE WHEN forma_pago = 'fiado' THEN total END), 0) AS fiado,"
            " COALESCE(SUM(total - costo_total), 0) AS ganancia"
            " FROM ventas WHERE estado = 'hecha' AND cuando >= ? AND (? IS NULL OR cuando < ?)",
            (desde, hasta, hasta),
        ).fetchone()
        canceladas = con.execute(
            "SELECT COUNT(*) FROM ventas WHERE estado = 'cancelada' AND cuando >= ? AND (? IS NULL OR cuando < ?)",
            (desde, hasta, hasta),
        ).fetchone()[0]
    return {**dict(fila), "canceladas": canceladas}
