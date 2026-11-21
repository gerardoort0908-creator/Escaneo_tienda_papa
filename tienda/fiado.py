"""Módulo de Fiado: clientes que se llevan y pagan después.

Dueño de: clientes, fiado_movimientos.

Sin límite de crédito. El saldo es la suma de los movimientos: cada venta fiada
suma, cada abono resta. Un abono se escribe a mano o con "Pagó todo".
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .nucleo import dinero, registro, reloj
from .nucleo.base_datos import BaseDatos
from .nucleo.errores import DatoInvalido, NoEncontrado, NoPermitido, Repetido

_log = registro.obtener("fiado")
LARGO_NOMBRE = 60


@dataclass(frozen=True)
class Cliente:
    id: int
    nombre: str
    telefono: str | None
    nota: str | None
    activo: bool
    saldo: int


_SELECT = """
SELECT c.*, COALESCE((SELECT SUM(monto) FROM fiado_movimientos f WHERE f.cliente_id = c.id), 0) AS saldo
FROM clientes c
"""


def _a_cliente(f: sqlite3.Row) -> Cliente:
    return Cliente(f["id"], f["nombre"], f["telefono"], f["nota"], bool(f["activo"]), f["saldo"])


def crear_cliente(bd: BaseDatos, nombre: str, telefono: str | None = None, nota: str | None = None) -> int:
    nombre = _validar_nombre(nombre)
    with bd.transaccion() as con:
        _nombre_libre(con, nombre, None)
        cliente_id = con.execute(
            "INSERT INTO clientes (nombre, telefono, nota, creado) VALUES (?, ?, ?, ?)",
            (nombre, _texto_opcional(telefono), _texto_opcional(nota), reloj.texto()),
        ).lastrowid
    _log.info("Cliente nuevo %d «%s»", cliente_id, nombre)
    return cliente_id


def editar_cliente(bd: BaseDatos, cliente_id: int, *, nombre: str | None = None,
                   telefono: str | None = None, nota: str | None = None) -> Cliente:
    with bd.transaccion() as con:
        actual = _fila(con, cliente_id)
        nuevo = _validar_nombre(nombre) if nombre is not None else actual["nombre"]
        if nuevo.casefold() != actual["nombre"].casefold():
            _nombre_libre(con, nuevo, cliente_id)
        con.execute(
            "UPDATE clientes SET nombre = ?, telefono = ?, nota = ? WHERE id = ?",
            (nuevo,
             _texto_opcional(telefono) if telefono is not None else actual["telefono"],
             _texto_opcional(nota) if nota is not None else actual["nota"],
             cliente_id),
        )
    return obtener(bd, cliente_id)


def desactivar_cliente(bd: BaseDatos, cliente_id: int) -> None:
    """Solo si ya no debe nada, para que ninguna deuda se pierda de vista."""
    with bd.transaccion() as con:
        _fila(con, cliente_id)
        saldo = _saldo(con, cliente_id)
        if saldo:
            raise NoPermitido(f"Todavía debe {dinero.formatear(saldo)}")
        con.execute("UPDATE clientes SET activo = 0 WHERE id = ?", (cliente_id,))


def obtener(bd: BaseDatos, cliente_id: int) -> Cliente:
    with bd.lectura() as con:
        fila = con.execute(_SELECT + "WHERE c.id = ?", (cliente_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("Ese cliente no existe")
    return _a_cliente(fila)


def buscar(bd: BaseDatos, texto: str = "") -> list[Cliente]:
    condiciones, valores = ["c.activo = 1"], []
    for palabra in texto.split():
        condiciones.append("c.nombre LIKE ?")
        valores.append(f"%{palabra}%")
    with bd.lectura() as con:
        filas = con.execute(
            _SELECT + "WHERE " + " AND ".join(condiciones) + " ORDER BY c.nombre COLLATE NOCASE", valores
        ).fetchall()
    return [_a_cliente(f) for f in filas]


def deudores(bd: BaseDatos) -> list[Cliente]:
    """Quién debe, de mayor a menor deuda."""
    with bd.lectura() as con:
        filas = con.execute("SELECT * FROM (" + _SELECT + ") WHERE saldo > 0 ORDER BY saldo DESC").fetchall()
    return [_a_cliente(f) for f in filas]


def historial(bd: BaseDatos, cliente_id: int) -> list[dict]:
    with bd.lectura() as con:
        filas = con.execute(
            "SELECT tipo, monto, venta_id, nota, cuando FROM fiado_movimientos WHERE cliente_id = ? ORDER BY id",
            (cliente_id,),
        ).fetchall()
    return [dict(f) for f in filas]


def abonar(bd: BaseDatos, cliente_id: int, monto: int, nota: str | None = None) -> int:
    """Registra un pago en efectivo. Devuelve lo que sigue debiendo."""
    dinero.validar_centavos(monto)
    with bd.transaccion() as con:
        cliente = _fila(con, cliente_id)
        saldo = _saldo(con, cliente_id)
        if saldo <= 0:
            raise NoPermitido(f"{cliente['nombre']} no debe nada")
        if monto > saldo:
            raise DatoInvalido(f"Solo debe {dinero.formatear(saldo)}; el abono es mayor")
        _mover(con, cliente_id, "abono", -monto, None, nota)
    _log.info("Abono %s de %d «%s»; resta %s", dinero.formatear(monto), cliente_id, cliente["nombre"],
              dinero.formatear(saldo - monto))
    return saldo - monto


def pago_todo(bd: BaseDatos, cliente_id: int) -> int:
    """Botón "Pagó todo". Devuelve cuánto pagó."""
    with bd.transaccion():
        saldo = obtener(bd, cliente_id).saldo
        abonar(bd, cliente_id, saldo, "Pagó todo")
    return saldo


def abonos_entre(bd: BaseDatos, desde: str, hasta: str | None) -> int:
    """Efectivo que entró por abonos en ese rango de horas (lo usa el corte de caja)."""
    with bd.lectura() as con:
        return con.execute(
            "SELECT COALESCE(-SUM(monto), 0) FROM fiado_movimientos"
            " WHERE tipo = 'abono' AND cuando >= ? AND (? IS NULL OR cuando < ?)",
            (desde, hasta, hasta),
        ).fetchone()[0]


# ---------------------------------------------------------------- para Ventas

def cargar_venta(bd: BaseDatos, cliente_id: int, venta_id: int, monto: int) -> None:
    with bd.transaccion() as con:
        cliente = _fila(con, cliente_id)
        if not cliente["activo"]:
            raise NoPermitido("Ese cliente está desactivado")
        _mover(con, cliente_id, "cargo", monto, venta_id, None)


def cancelar_cargo(bd: BaseDatos, venta_id: int) -> None:
    """Al cancelar una venta fiada se quita lo que se le había cargado."""
    with bd.transaccion() as con:
        cargo = con.execute(
            "SELECT cliente_id, monto FROM fiado_movimientos WHERE venta_id = ? AND tipo = 'cargo'", (venta_id,)
        ).fetchone()
        if cargo is None:
            raise NoEncontrado("Esa venta no está en el fiado")
        if con.execute("SELECT 1 FROM fiado_movimientos WHERE venta_id = ? AND tipo = 'cancelacion'",
                       (venta_id,)).fetchone():
            raise NoPermitido("Ese cargo ya estaba cancelado")
        _mover(con, cargo["cliente_id"], "cancelacion", -cargo["monto"], venta_id, "Venta cancelada")


# ---------------------------------------------------------------- internos

def _mover(con: sqlite3.Connection, cliente_id: int, tipo: str, monto: int, venta_id: int | None, nota: str | None) -> None:
    con.execute(
        "INSERT INTO fiado_movimientos (cliente_id, tipo, monto, venta_id, nota, cuando) VALUES (?, ?, ?, ?, ?, ?)",
        (cliente_id, tipo, monto, venta_id, _texto_opcional(nota), reloj.texto()),
    )


def _fila(con: sqlite3.Connection, cliente_id: int) -> sqlite3.Row:
    fila = con.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("Ese cliente no existe")
    return fila


def _saldo(con: sqlite3.Connection, cliente_id: int) -> int:
    return con.execute(
        "SELECT COALESCE(SUM(monto), 0) FROM fiado_movimientos WHERE cliente_id = ?", (cliente_id,)
    ).fetchone()[0]


def _nombre_libre(con: sqlite3.Connection, nombre: str, propio: int | None) -> None:
    for fila in con.execute("SELECT id, nombre FROM clientes WHERE activo = 1 AND id IS NOT ?", (propio,)):
        if fila["nombre"].casefold() == nombre.casefold():
            raise Repetido("Ya hay un cliente con ese nombre; agrega un apellido o apodo")


def _validar_nombre(nombre: str) -> str:
    limpio = " ".join((nombre or "").split())
    if not limpio:
        raise DatoInvalido("Escribe el nombre del cliente")
    if len(limpio) > LARGO_NOMBRE:
        raise DatoInvalido(f"El nombre es muy largo (máximo {LARGO_NOMBRE} letras)")
    return limpio


def _texto_opcional(texto: str | None) -> str | None:
    limpio = " ".join((texto or "").split())
    return limpio or None
