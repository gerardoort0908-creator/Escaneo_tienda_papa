"""Módulo de Reportes: solo lee, nunca cambia nada.

Aquí están las cuentas básicas; las gráficas, PDF y Excel llegan en la fase de reportes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .nucleo.base_datos import BaseDatos


@dataclass(frozen=True)
class Ganancia:
    ventas: int       # lo que se cobró (efectivo + fiado)
    costo: int        # lo que costó esa mercancía
    numero_ventas: int

    @property
    def ganancia(self) -> int:
        return self.ventas - self.costo


def _rango(desde: date, hasta: date) -> tuple[str, str]:
    """Del inicio de `desde` al final de `hasta` (los dos días cuentan)."""
    return f"{desde:%Y-%m-%d} 00:00:00", f"{hasta + timedelta(days=1):%Y-%m-%d} 00:00:00"


def ganancia(bd: BaseDatos, desde: date, hasta: date) -> Ganancia:
    inicio, fin = _rango(desde, hasta)
    with bd.lectura() as con:
        fila = con.execute(
            "SELECT COALESCE(SUM(total), 0), COALESCE(SUM(costo_total), 0), COUNT(*) FROM ventas"
            " WHERE estado = 'hecha' AND cuando >= ? AND cuando < ?", (inicio, fin),
        ).fetchone()
    return Ganancia(fila[0], fila[1], fila[2])


def mas_vendidos(bd: BaseDatos, desde: date, hasta: date, cuantos: int = 10) -> list[dict]:
    """Ordenados por dinero vendido; también trae cantidad y ganancia."""
    inicio, fin = _rango(desde, hasta)
    with bd.lectura() as con:
        filas = con.execute(
            "SELECT l.producto_id, p.nombre, p.unidad, SUM(l.cantidad) AS cantidad,"
            " SUM(l.subtotal) AS vendido, SUM(l.subtotal - l.costo) AS ganancia"
            " FROM venta_lineas l JOIN ventas v ON v.id = l.venta_id JOIN productos p ON p.id = l.producto_id"
            " WHERE v.estado = 'hecha' AND v.cuando >= ? AND v.cuando < ?"
            " GROUP BY l.producto_id ORDER BY vendido DESC, cantidad DESC LIMIT ?",
            (inicio, fin, cuantos),
        ).fetchall()
    return [dict(f) for f in filas]
