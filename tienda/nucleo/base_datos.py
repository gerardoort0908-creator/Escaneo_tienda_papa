"""La base de datos (un solo archivo SQLite) y las transacciones todo-o-nada.

    with bd.transaccion() as con:
        ...  # si algo falla aquí adentro, no se guarda NADA de lo de adentro

Las transacciones se pueden anidar: Ventas abre una y adentro Productos abre la
suya; si falla cualquier parte, se deshace todo.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from . import registro
from .esquema import MIGRACIONES

_log = registro.obtener("base_datos")


class BaseDatos:
    def __init__(self, ruta: Path | str) -> None:
        self.ruta = str(ruta)
        self._con = sqlite3.connect(
            self.ruta, isolation_level=None, check_same_thread=False, timeout=10
        )
        self._con.row_factory = sqlite3.Row
        self._candado = threading.RLock()
        self._nivel = 0
        self._con.execute("PRAGMA foreign_keys = ON")
        if self.ruta != ":memory:":
            self._con.execute("PRAGMA journal_mode = WAL")
        # FULL: si se va la luz, lo último que se cobró ya quedó en el disco.
        self._con.execute("PRAGMA synchronous = FULL")

    @contextmanager
    def transaccion(self) -> Iterator[sqlite3.Connection]:
        with self._candado:
            externa = self._nivel == 0
            punto = f"paso_{self._nivel}"
            self._con.execute("BEGIN IMMEDIATE" if externa else f"SAVEPOINT {punto}")
            self._nivel += 1
            try:
                yield self._con
            except BaseException:
                if externa:
                    self._con.execute("ROLLBACK")
                else:
                    self._con.execute(f"ROLLBACK TO {punto}")
                    self._con.execute(f"RELEASE {punto}")
                raise
            else:
                self._con.execute("COMMIT" if externa else f"RELEASE {punto}")
            finally:
                self._nivel -= 1

    @contextmanager
    def lectura(self) -> Iterator[sqlite3.Connection]:
        """Para consultar sin cambiar nada."""
        with self._candado:
            yield self._con

    @property
    def version(self) -> int:
        with self.lectura() as con:
            return con.execute("PRAGMA user_version").fetchone()[0]

    def migrar(self) -> None:
        """Deja la base de datos en la versión más nueva. Cada paso es todo-o-nada."""
        actual = self.version
        for numero, sql in enumerate(MIGRACIONES[actual:], start=actual + 1):
            with self.transaccion() as con:
                for sentencia in _sentencias(sql):
                    con.execute(sentencia)
                con.execute(f"PRAGMA user_version = {numero}")
            _log.info("Base de datos actualizada a la versión %d", numero)

    def respaldar_en(self, destino: Path) -> None:
        """Copia consistente aunque el programa esté en uso."""
        with self._candado:
            copia = sqlite3.connect(str(destino))
            try:
                self._con.backup(copia)
                copia.execute("PRAGMA journal_mode = DELETE")  # un solo archivo, sin -wal ni -shm
            finally:
                copia.close()

    def cerrar(self) -> None:
        with self._candado:
            self._con.close()


def _sentencias(sql: str) -> list[str]:
    """Separa el texto en sentencias completas (los triggers llevan ';' adentro)."""
    resultado, actual = [], ""
    for renglon in sql.splitlines(keepends=True):
        if renglon.strip().startswith("--"):
            continue
        actual += renglon
        if sqlite3.complete_statement(actual):
            if actual.strip():
                resultado.append(actual.strip())
            actual = ""
    if actual.strip():
        raise ValueError("Sentencia SQL incompleta en la migración")
    return resultado
