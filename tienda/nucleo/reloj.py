"""La hora de la tienda. Se guarda como texto local "2026-11-21 14:05:09" para que
los reportes por día coincidan con el día de la tienda."""

from __future__ import annotations

from datetime import datetime

FORMATO = "%Y-%m-%d %H:%M:%S"


def ahora() -> datetime:
    return datetime.now().replace(microsecond=0)


def texto(momento: datetime | None = None) -> str:
    return (momento or ahora()).strftime(FORMATO)
