"""Un archivo de registro por módulo (datos/registros/ventas.log, fiado.log, ...).

Si algo falla en Ventas, se busca solo en ventas.log.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

MODULOS = ("base_datos", "productos", "ventas", "fiado", "caja", "reportes", "respaldos")
_RAIZ = "tienda"


def obtener(modulo: str) -> logging.Logger:
    if modulo not in MODULOS:
        raise ValueError(f"Módulo desconocido: {modulo}")
    return logging.getLogger(f"{_RAIZ}.{modulo}")


def configurar(carpeta: Path) -> None:
    """Prepara los archivos. Se puede llamar más de una vez sin duplicar renglones."""
    carpeta.mkdir(parents=True, exist_ok=True)
    formato = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s")
    for modulo in MODULOS:
        registro = obtener(modulo)
        registro.setLevel(logging.INFO)
        registro.propagate = False
        for manejador in list(registro.handlers):
            registro.removeHandler(manejador)
            manejador.close()
        archivo = RotatingFileHandler(
            carpeta / f"{modulo}.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
        )
        archivo.setFormatter(formato)
        registro.addHandler(archivo)
