"""Módulo de Caja: abrir con un fondo, sacar dinero (retiros) y hacer el corte.

Dueño de: cortes, caja_retiros.

Al cerrar: lo que debería haber = fondo + ventas en efectivo + abonos de fiado
− retiros. Se compara con lo que se contó y se guarda la diferencia.
Las ventas no dependen de la caja: si se olvida abrirla, se puede vender igual.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from . import fiado, ventas
from .nucleo import dinero, registro, reloj
from .nucleo.base_datos import BaseDatos
from .nucleo.errores import DatoInvalido, NoPermitido

_log = registro.obtener("caja")


@dataclass(frozen=True)
class Resumen:
    corte_id: int
    abierto: str
    fondo: int
    ventas_efectivo: int
    abonos: int
    retiros: int

    @property
    def esperado(self) -> int:
        return self.fondo + self.ventas_efectivo + self.abonos - self.retiros


@dataclass(frozen=True)
class Corte:
    resumen: Resumen
    contado: int

    @property
    def diferencia(self) -> int:
        """Positiva: sobra dinero. Negativa: falta."""
        return self.contado - self.resumen.esperado


def abrir(bd: BaseDatos, fondo: int) -> int:
    dinero.validar_centavos(fondo, permitir_cero=True)
    with bd.transaccion() as con:
        if _abierto(con):
            raise NoPermitido("La caja ya está abierta; primero haz el corte")
        corte_id = con.execute("INSERT INTO cortes (abierto, fondo) VALUES (?, ?)",
                               (reloj.texto(), fondo)).lastrowid
    _log.info("Caja abierta (corte %d) con fondo %s", corte_id, dinero.formatear(fondo))
    return corte_id


def retirar(bd: BaseDatos, monto: int, nota: str) -> None:
    """Dinero que se saca de la caja (pagar a un proveedor, llevarlo al banco...)."""
    dinero.validar_centavos(monto)
    nota = " ".join((nota or "").split())
    if not nota:
        raise DatoInvalido("Escribe para qué se sacó el dinero")
    with bd.transaccion() as con:
        corte = _exigir_abierto(con)
        con.execute("INSERT INTO caja_retiros (corte_id, monto, nota, cuando) VALUES (?, ?, ?, ?)",
                    (corte["id"], monto, nota, reloj.texto()))
    _log.info("Retiro %s: %s", dinero.formatear(monto), nota)


def resumen(bd: BaseDatos, hasta: str | None = None) -> Resumen:
    """Cómo va la caja abierta en este momento."""
    with bd.lectura() as con:
        corte = _exigir_abierto(con)
        retiros = con.execute("SELECT COALESCE(SUM(monto), 0) FROM caja_retiros WHERE corte_id = ?",
                              (corte["id"],)).fetchone()[0]
    return Resumen(
        corte["id"], corte["abierto"], corte["fondo"],
        ventas.efectivo_entre(bd, corte["abierto"], hasta),
        fiado.abonos_entre(bd, corte["abierto"], hasta),
        retiros,
    )


def cerrar(bd: BaseDatos, contado: int, nota: str | None = None) -> Corte:
    dinero.validar_centavos(contado, permitir_cero=True)
    with bd.transaccion() as con:
        ahora = reloj.texto()
        r = resumen(bd)
        corte = Corte(r, contado)
        con.execute(
            "UPDATE cortes SET cerrado = ?, esperado = ?, contado = ?, diferencia = ?, nota = ? WHERE id = ?",
            (ahora, r.esperado, contado, corte.diferencia, nota, r.corte_id),
        )
    _log.info("Corte %d: esperado %s, contado %s, diferencia %s", r.corte_id, dinero.formatear(r.esperado),
              dinero.formatear(contado), dinero.formatear(corte.diferencia))
    return corte


def esta_abierta(bd: BaseDatos) -> bool:
    with bd.lectura() as con:
        return _abierto(con) is not None


def cortes_anteriores(bd: BaseDatos, limite: int = 30) -> list[dict]:
    with bd.lectura() as con:
        filas = con.execute("SELECT * FROM cortes WHERE cerrado IS NOT NULL ORDER BY id DESC LIMIT ?",
                            (limite,)).fetchall()
    return [dict(f) for f in filas]


def _abierto(con: sqlite3.Connection) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM cortes WHERE cerrado IS NULL").fetchone()


def _exigir_abierto(con: sqlite3.Connection) -> sqlite3.Row:
    corte = _abierto(con)
    if corte is None:
        raise NoPermitido("La caja no está abierta")
    return corte
