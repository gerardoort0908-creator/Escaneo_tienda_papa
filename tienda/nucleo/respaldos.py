"""Respaldos de la base de datos.

Cada día se guarda una copia en datos/respaldos/diarios (se conservan las
últimas 30). Además, cada mes se guarda una copia completa (tienda-2026-11.sqlite) en datos/respaldos.
Se hace sola al abrir el programa si la del mes todavía no existe. Las copias no
se borran: el SAT pide conservar los registros 5 años.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path

from . import registro
from .base_datos import BaseDatos
from .errores import ErrorTienda

_log = registro.obtener("respaldos")


class RespaldoDanado(ErrorTienda):
    """La copia salió mal; se borra y se avisa."""


def respaldar(bd: BaseDatos, carpeta: Path, nombre: str) -> Path:
    """Copia la base de datos, revisa que la copia esté sana y solo entonces la deja."""
    carpeta.mkdir(parents=True, exist_ok=True)
    final = carpeta / f"{nombre}.sqlite"
    temporal = carpeta / f".{nombre}.sqlite.tmp"
    temporal.unlink(missing_ok=True)
    try:
        bd.respaldar_en(temporal)
        if not copia_sana(temporal):
            raise RespaldoDanado("El respaldo salió dañado; se intentará de nuevo")
        os.replace(temporal, final)
    except Exception:
        temporal.unlink(missing_ok=True)
        _log.exception("Falló el respaldo %s", nombre)
        raise
    _log.info("Respaldo guardado: %s (%d KB)", final.name, final.stat().st_size // 1024)
    return final


def copia_sana(ruta: Path) -> bool:
    try:
        con = sqlite3.connect(ruta.resolve().as_uri() + "?mode=ro", uri=True)  # as_uri: rutas con espacios en Windows
        try:
            return con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            con.close()
    except sqlite3.Error:
        return False


def respaldo_mensual(bd: BaseDatos, carpeta: Path, hoy: date | None = None) -> Path | None:
    """Hace el respaldo del mes si falta. Devuelve la ruta nueva, o None si ya existía."""
    hoy = hoy or date.today()
    nombre = f"tienda-{hoy:%Y-%m}"
    if (carpeta / f"{nombre}.sqlite").exists():
        return None
    return respaldar(bd, carpeta, nombre)


DIARIOS_A_GUARDAR = 30


def respaldo_diario(bd: BaseDatos, carpeta: Path, hoy: date | None = None) -> Path | None:
    """Copia del día si falta; después borra las diarias más viejas que las últimas 30.
    Las mensuales nunca se borran."""
    hoy = hoy or date.today()
    diarios = carpeta / "diarios"
    nombre = f"tienda-{hoy:%Y-%m-%d}"
    nueva = None if (diarios / f"{nombre}.sqlite").exists() else respaldar(bd, diarios, nombre)
    for vieja in listar(diarios)[:-DIARIOS_A_GUARDAR]:
        vieja.unlink()
        _log.info("Respaldo diario viejo quitado: %s", vieja.name)
    return nueva


def respaldos_al_dia(bd: BaseDatos, carpeta: Path, hoy: date | None = None) -> None:
    """Hace los que falten (diario y mensual). Se llama al abrir y una vez al día."""
    respaldo_diario(bd, carpeta, hoy)
    respaldo_mensual(bd, carpeta, hoy)


def listar(carpeta: Path) -> list[Path]:
    if not carpeta.exists():
        return []
    return sorted(carpeta.glob("tienda-*.sqlite"))
