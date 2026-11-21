"""Módulo de Productos e Inventario.

Dueño de: productos, historial_precios, movimientos_inventario.

Cantidades enteras: las piezas se cuentan en piezas y lo de granel (huevo) en
gramos. El huevo se vende solo de medio kilo en medio kilo (500 g, 1000 g, ...).
La existencia nunca se escribe a mano: es la suma de todo lo que entró y salió.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .nucleo import dinero, registro, reloj
from .nucleo.base_datos import BaseDatos
from .nucleo.errores import DatoInvalido, NoEncontrado, NoPermitido, Repetido

_log = registro.obtener("productos")

UNIDADES = ("pieza", "kg")
PASO_GRANEL = 500  # gramos: medio kilo
LARGO_NOMBRE = 80
_TOPE_CANTIDAD = 10_000_000


@dataclass(frozen=True)
class Producto:
    id: int
    codigo: str | None
    nombre: str
    unidad: str
    precio_venta: int
    costo_promedio: int
    minimo: int
    activo: bool
    existencia: int

    @property
    def ganancia_por_unidad(self) -> int:
        return self.precio_venta - self.costo_promedio


@dataclass(frozen=True)
class Llegada:
    """Un renglón de "Llegó mercancía": cuánto llegó y cuánto costó cada unidad."""

    producto_id: int
    cantidad: int
    costo_unitario: int  # centavos por pieza o por kilo


# ---------------------------------------------------------------- consultas

_SELECT = """
SELECT p.*, COALESCE((SELECT SUM(cantidad) FROM movimientos_inventario m
                      WHERE m.producto_id = p.id), 0) AS existencia
FROM productos p
"""


def _a_producto(fila: sqlite3.Row) -> Producto:
    return Producto(
        id=fila["id"], codigo=fila["codigo"], nombre=fila["nombre"], unidad=fila["unidad"],
        precio_venta=fila["precio_venta"], costo_promedio=fila["costo_promedio"],
        minimo=fila["minimo"], activo=bool(fila["activo"]), existencia=fila["existencia"],
    )


def obtener(bd: BaseDatos, producto_id: int) -> Producto:
    with bd.lectura() as con:
        fila = con.execute(_SELECT + "WHERE p.id = ?", (producto_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("Ese producto no existe")
    return _a_producto(fila)


def por_codigo(bd: BaseDatos, codigo: str) -> Producto | None:
    """El producto activo con ese código, o None si no está dado de alta."""
    with bd.lectura() as con:
        fila = con.execute(_SELECT + "WHERE p.codigo = ? AND p.activo = 1", (codigo.strip(),)).fetchone()
    return _a_producto(fila) if fila else None


def buscar(bd: BaseDatos, texto: str = "", *, incluir_inactivos: bool = False, limite: int = 50) -> list[Producto]:
    """Por pedazo de nombre o código. Sin texto, devuelve todos en orden alfabético."""
    condiciones, valores = [], []
    if not incluir_inactivos:
        condiciones.append("p.activo = 1")
    for palabra in texto.split():
        condiciones.append("(p.nombre LIKE ? ESCAPE '\\' OR p.codigo = ?)")
        valores += [f"%{_escapar_like(palabra)}%", palabra]
    donde = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    with bd.lectura() as con:
        filas = con.execute(
            _SELECT + donde + " ORDER BY p.nombre COLLATE NOCASE LIMIT ?", (*valores, limite)
        ).fetchall()
    return [_a_producto(f) for f in filas]


def faltantes(bd: BaseDatos) -> list[Producto]:
    """Productos activos con existencia igual o menor a su mínimo (los que hay que pedir)."""
    with bd.lectura() as con:
        filas = con.execute(
            "SELECT * FROM (" + _SELECT + "WHERE p.activo = 1) "
            "WHERE existencia <= minimo ORDER BY existencia - minimo, nombre COLLATE NOCASE"
        ).fetchall()
    return [_a_producto(f) for f in filas]


# ---------------------------------------------------------------- altas y cambios

def crear(
    bd: BaseDatos, *, nombre: str, precio_venta: int, unidad: str = "pieza",
    codigo: str | None = None, costo: int = 0, minimo: int = 0,
) -> int:
    nombre = _validar_nombre(nombre)
    dinero.validar_precio_venta(precio_venta)
    dinero.validar_centavos(costo, permitir_cero=True)
    if unidad not in UNIDADES:
        raise DatoInvalido("La unidad debe ser pieza o kg")
    _validar_minimo(minimo, unidad)
    codigo = _limpiar_codigo(codigo)
    ahora = reloj.texto()
    with bd.transaccion() as con:
        _codigo_libre(con, codigo, None)
        cursor = con.execute(
            "INSERT INTO productos (codigo, nombre, unidad, precio_venta, costo_promedio, minimo, creado, actualizado)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (codigo, nombre, unidad, precio_venta, costo, minimo, ahora, ahora),
        )
        producto_id = cursor.lastrowid
        _anotar_precio(con, producto_id, precio_venta, costo, "alta", ahora)
    _log.info("Alta %d «%s» %s %s", producto_id, nombre, codigo or "sin código", dinero.formatear(precio_venta))
    return producto_id


def editar(
    bd: BaseDatos, producto_id: int, *, nombre: str | None = None, precio_venta: int | None = None,
    codigo: str | None = None, quitar_codigo: bool = False, minimo: int | None = None,
) -> Producto:
    """Cambia lo que se indique. Las ventas pasadas no cambian: guardan su propio precio."""
    ahora = reloj.texto()
    with bd.transaccion() as con:
        actual = _fila(con, producto_id)
        nuevo_nombre = _validar_nombre(nombre) if nombre is not None else actual["nombre"]
        nuevo_precio = dinero.validar_precio_venta(precio_venta) if precio_venta is not None else actual["precio_venta"]
        nuevo_minimo = _validar_minimo(minimo, actual["unidad"]) if minimo is not None else actual["minimo"]
        nuevo_codigo = None if quitar_codigo else (_limpiar_codigo(codigo) if codigo is not None else actual["codigo"])
        if nuevo_codigo != actual["codigo"]:
            _codigo_libre(con, nuevo_codigo, producto_id)
        con.execute(
            "UPDATE productos SET nombre = ?, precio_venta = ?, codigo = ?, minimo = ?, actualizado = ? WHERE id = ?",
            (nuevo_nombre, nuevo_precio, nuevo_codigo, nuevo_minimo, ahora, producto_id),
        )
        if nuevo_precio != actual["precio_venta"]:
            _anotar_precio(con, producto_id, nuevo_precio, actual["costo_promedio"], "cambio de precio", ahora)
            _log.info("Precio %d: %s → %s", producto_id, dinero.formatear(actual["precio_venta"]),
                      dinero.formatear(nuevo_precio))
    return obtener(bd, producto_id)


def desactivar(bd: BaseDatos, producto_id: int) -> None:
    """Ya no aparece para vender, pero su historia se queda."""
    _cambiar_activo(bd, producto_id, False)


def reactivar(bd: BaseDatos, producto_id: int) -> None:
    _cambiar_activo(bd, producto_id, True)


def historial_precios(bd: BaseDatos, producto_id: int) -> list[dict]:
    with bd.lectura() as con:
        filas = con.execute(
            "SELECT precio_venta, costo, motivo, cuando FROM historial_precios WHERE producto_id = ? ORDER BY id",
            (producto_id,),
        ).fetchall()
    return [dict(f) for f in filas]


# ---------------------------------------------------------------- inventario

def registrar_llegada(bd: BaseDatos, renglones: list[Llegada], nota: str | None = None) -> None:
    """Pantalla "Llegó mercancía". Suma existencias y recalcula el costo promedio.

    Costo promedio: si había 10 a $10 y llegan 10 a $12, cada uno cuesta ahora $11.
    """
    if not renglones:
        raise DatoInvalido("No hay nada que registrar")
    ahora = reloj.texto()
    with bd.transaccion() as con:
        for r in renglones:
            fila = _fila(con, r.producto_id)
            _validar_cantidad(r.cantidad, fila["unidad"], exigir_paso=False)
            dinero.validar_centavos(r.costo_unitario, permitir_cero=True)
            existencia = _existencia(con, r.producto_id)
            nuevo_costo = costo_promedio(existencia, fila["costo_promedio"], r.cantidad, r.costo_unitario)
            con.execute(
                "INSERT INTO movimientos_inventario (producto_id, cantidad, tipo, costo_unitario, nota, cuando)"
                " VALUES (?, ?, 'llegada', ?, ?, ?)",
                (r.producto_id, r.cantidad, r.costo_unitario, nota, ahora),
            )
            if nuevo_costo != fila["costo_promedio"]:
                con.execute("UPDATE productos SET costo_promedio = ?, actualizado = ? WHERE id = ?",
                            (nuevo_costo, ahora, r.producto_id))
                _anotar_precio(con, r.producto_id, fila["precio_venta"], nuevo_costo, "llegó mercancía", ahora)
    _log.info("Llegó mercancía: %d renglones", len(renglones))


def costo_promedio(existencia: int, costo_actual: int, llegan: int, costo_nuevo: int) -> int:
    """Promedio ponderado. Si no había nada (o había de menos), manda el costo nuevo."""
    if existencia <= 0:
        return costo_nuevo
    return dinero.dividir_redondeando(existencia * costo_actual + llegan * costo_nuevo, existencia + llegan)


def ajustar_conteo(bd: BaseDatos, producto_id: int, contado: int, motivo: str) -> int:
    """Cuando se cuenta lo que hay en el anaquel y no coincide. Devuelve la diferencia."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise DatoInvalido("Escribe por qué se ajusta (por ejemplo: conteo, merma, caducado)")
    with bd.transaccion() as con:
        fila = _fila(con, producto_id)
        if isinstance(contado, bool) or not isinstance(contado, int) or not 0 <= contado <= _TOPE_CANTIDAD:
            raise DatoInvalido("La cantidad contada no es válida")
        diferencia = contado - _existencia(con, producto_id)
        if diferencia:
            con.execute(
                "INSERT INTO movimientos_inventario (producto_id, cantidad, tipo, nota, cuando)"
                " VALUES (?, ?, 'ajuste', ?, ?)",
                (producto_id, diferencia, motivo, reloj.texto()),
            )
            _log.info("Ajuste %d «%s»: %+d (%s)", producto_id, fila["nombre"], diferencia, motivo)
    return diferencia


def validar_cantidad_venta(unidad: str, cantidad: int) -> None:
    _validar_cantidad(cantidad, unidad, exigir_paso=True)


def salida_por_venta(bd: BaseDatos, venta_id: int, producto_id: int, cantidad: int) -> None:
    """Lo usa Ventas. Se permite quedar en negativo: no se le niega una venta al cliente
    porque el inventario no esté al día; el reporte de faltantes lo señalará."""
    with bd.transaccion() as con:
        fila = _fila(con, producto_id)
        _validar_cantidad(cantidad, fila["unidad"], exigir_paso=True)
        con.execute(
            "INSERT INTO movimientos_inventario (producto_id, cantidad, tipo, costo_unitario, venta_id, cuando)"
            " VALUES (?, ?, 'venta', ?, ?, ?)",
            (producto_id, -cantidad, fila["costo_promedio"], venta_id, reloj.texto()),
        )


def regreso_por_cancelacion(bd: BaseDatos, venta_id: int) -> None:
    """Lo usa Ventas al cancelar: regresa al anaquel exactamente lo que salió."""
    with bd.transaccion() as con:
        salidas = con.execute(
            "SELECT producto_id, cantidad, costo_unitario FROM movimientos_inventario"
            " WHERE venta_id = ? AND tipo = 'venta'", (venta_id,),
        ).fetchall()
        ya = con.execute(
            "SELECT 1 FROM movimientos_inventario WHERE venta_id = ? AND tipo = 'cancelacion'", (venta_id,)
        ).fetchone()
        if ya:
            raise NoPermitido("Esa venta ya se había regresado al inventario")
        ahora = reloj.texto()
        for s in salidas:
            con.execute(
                "INSERT INTO movimientos_inventario (producto_id, cantidad, tipo, costo_unitario, venta_id, cuando)"
                " VALUES (?, ?, 'cancelacion', ?, ?, ?)",
                (s["producto_id"], -s["cantidad"], s["costo_unitario"], venta_id, ahora),
            )


def movimientos(bd: BaseDatos, producto_id: int, limite: int = 100) -> list[dict]:
    with bd.lectura() as con:
        filas = con.execute(
            "SELECT cantidad, tipo, costo_unitario, venta_id, nota, cuando FROM movimientos_inventario"
            " WHERE producto_id = ? ORDER BY id DESC LIMIT ?", (producto_id, limite),
        ).fetchall()
    return [dict(f) for f in filas]


# ---------------------------------------------------------------- internos

def _fila(con: sqlite3.Connection, producto_id: int) -> sqlite3.Row:
    fila = con.execute("SELECT * FROM productos WHERE id = ?", (producto_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("Ese producto no existe")
    return fila


def _existencia(con: sqlite3.Connection, producto_id: int) -> int:
    return con.execute(
        "SELECT COALESCE(SUM(cantidad), 0) FROM movimientos_inventario WHERE producto_id = ?", (producto_id,)
    ).fetchone()[0]


def _anotar_precio(con: sqlite3.Connection, producto_id: int, precio: int, costo: int, motivo: str, cuando: str) -> None:
    con.execute(
        "INSERT INTO historial_precios (producto_id, precio_venta, costo, motivo, cuando) VALUES (?, ?, ?, ?, ?)",
        (producto_id, precio, costo, motivo, cuando),
    )


def _cambiar_activo(bd: BaseDatos, producto_id: int, activo: bool) -> None:
    with bd.transaccion() as con:
        fila = _fila(con, producto_id)
        if activo and fila["codigo"]:
            _codigo_libre(con, fila["codigo"], producto_id)
        con.execute("UPDATE productos SET activo = ?, actualizado = ? WHERE id = ?",
                    (int(activo), reloj.texto(), producto_id))
    _log.info("%s %d «%s»", "Reactivado" if activo else "Desactivado", producto_id, fila["nombre"])


def _codigo_libre(con: sqlite3.Connection, codigo: str | None, propio: int | None) -> None:
    if codigo is None:
        return
    otro = con.execute("SELECT id, nombre FROM productos WHERE codigo = ? AND id IS NOT ?", (codigo, propio)).fetchone()
    if otro:
        raise Repetido(f"Ese código ya es de «{otro['nombre']}»")


def _validar_nombre(nombre: str) -> str:
    limpio = " ".join((nombre or "").split())
    if not limpio:
        raise DatoInvalido("Escribe el nombre del producto")
    if len(limpio) > LARGO_NOMBRE:
        raise DatoInvalido(f"El nombre es muy largo (máximo {LARGO_NOMBRE} letras)")
    return limpio


def _limpiar_codigo(codigo: str | None) -> str | None:
    if codigo is None:
        return None
    limpio = codigo.strip()
    if not limpio:
        return None
    if len(limpio) > 64 or not limpio.isprintable():
        raise DatoInvalido("Ese código no es válido")
    return limpio


def _validar_cantidad(cantidad: int, unidad: str, *, exigir_paso: bool) -> None:
    if isinstance(cantidad, bool) or not isinstance(cantidad, int) or not 0 < cantidad <= _TOPE_CANTIDAD:
        raise DatoInvalido("La cantidad debe ser mayor que cero")
    if unidad == "kg" and exigir_paso and cantidad % PASO_GRANEL:
        raise DatoInvalido("El huevo y lo de granel se venden de medio kilo en medio kilo")


def _validar_minimo(minimo: int, unidad: str) -> int:
    if isinstance(minimo, bool) or not isinstance(minimo, int) or not 0 <= minimo <= _TOPE_CANTIDAD:
        raise DatoInvalido("El mínimo no es válido")
    return minimo


def _escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
