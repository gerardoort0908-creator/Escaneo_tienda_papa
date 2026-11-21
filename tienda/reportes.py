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


def por_dia(bd: BaseDatos, desde: date, hasta: date) -> list[dict]:
    """Cada día del rango (también los días sin ventas, en cero)."""
    inicio, fin = _rango(desde, hasta)
    with bd.lectura() as con:
        filas = {f["dia"]: dict(f) for f in con.execute(
            "SELECT substr(cuando, 1, 10) AS dia, COUNT(*) AS ventas, SUM(total) AS vendido,"
            " SUM(total - costo_total) AS ganancia FROM ventas"
            " WHERE estado = 'hecha' AND cuando >= ? AND cuando < ? GROUP BY dia", (inicio, fin),
        )}
    dias, d = [], desde
    while d <= hasta:
        clave = f"{d:%Y-%m-%d}"
        dias.append(filas.get(clave, {"dia": clave, "ventas": 0, "vendido": 0, "ganancia": 0}))
        d += timedelta(days=1)
    return dias


def por_hora(bd: BaseDatos, dia: date) -> list[dict]:
    """Las 24 horas de un día: a qué hora se vende más."""
    inicio, fin = _rango(dia, dia)
    with bd.lectura() as con:
        filas = {int(f["hora"]): dict(f) for f in con.execute(
            "SELECT substr(cuando, 12, 2) AS hora, COUNT(*) AS ventas, SUM(total) AS vendido,"
            " SUM(total - costo_total) AS ganancia FROM ventas"
            " WHERE estado = 'hecha' AND cuando >= ? AND cuando < ? GROUP BY hora", (inicio, fin),
        )}
    return [{**filas.get(h, {"ventas": 0, "vendido": 0, "ganancia": 0}), "hora": h} for h in range(24)]


def formas_de_pago(bd: BaseDatos, desde: date, hasta: date) -> dict:
    """Cuánto se cobró en efectivo, cuánto se prestó y cuánto se canceló."""
    inicio, fin = _rango(desde, hasta)
    with bd.lectura() as con:
        fila = con.execute(
            "SELECT COALESCE(SUM(CASE WHEN estado = 'hecha' AND forma_pago = 'efectivo' THEN total END), 0),"
            " COALESCE(SUM(CASE WHEN estado = 'hecha' AND forma_pago = 'fiado' THEN total END), 0),"
            " COUNT(CASE WHEN estado = 'cancelada' THEN 1 END)"
            " FROM ventas WHERE cuando >= ? AND cuando < ?", (inicio, fin),
        ).fetchone()
        pagos = con.execute(
            "SELECT COALESCE(-SUM(monto), 0) FROM fiado_movimientos WHERE tipo = 'abono' AND cuando >= ? AND cuando < ?",
            (inicio, fin),
        ).fetchone()[0]
    return {"efectivo": fila[0], "prestado": fila[1], "canceladas": fila[2], "pagos_de_prestamos": pagos}


def ventas_detalle(bd: BaseDatos, desde: date, hasta: date) -> list[dict]:
    """Cada renglón vendido, para el Excel."""
    inicio, fin = _rango(desde, hasta)
    with bd.lectura() as con:
        filas = con.execute(
            "SELECT v.id AS venta, v.cuando, v.forma_pago, c.nombre AS cliente, l.nombre AS producto, l.unidad,"
            " l.cantidad, l.precio_unitario, l.subtotal, l.costo"
            " FROM venta_lineas l JOIN ventas v ON v.id = l.venta_id LEFT JOIN clientes c ON c.id = v.cliente_id"
            " WHERE v.estado = 'hecha' AND v.cuando >= ? AND v.cuando < ? ORDER BY v.id, l.id", (inicio, fin),
        ).fetchall()
    return [dict(f) for f in filas]


def cortes_entre(bd: BaseDatos, desde: date, hasta: date) -> list[dict]:
    inicio, fin = _rango(desde, hasta)
    with bd.lectura() as con:
        filas = con.execute(
            "SELECT abierto, cerrado, fondo, esperado, contado, diferencia, nota FROM cortes"
            " WHERE cerrado IS NOT NULL AND cerrado >= ? AND cerrado < ? ORDER BY id", (inicio, fin),
        ).fetchall()
    return [dict(f) for f in filas]
