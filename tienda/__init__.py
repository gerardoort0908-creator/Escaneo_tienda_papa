"""La tienda: cimientos del punto de venta.

Módulos (cada uno escribe solo en sus tablas):
    productos  — productos, precios e inventario
    ventas     — cobrar, vender fiado, cancelar
    fiado      — clientes, cargos y abonos
    caja       — fondo, retiros y corte de caja
    reportes   — cuentas de solo lectura
El escáner del celular vive aparte, en la carpeta app/.
"""

from __future__ import annotations

from pathlib import Path

from .nucleo import registro, respaldos
from .nucleo.base_datos import BaseDatos

ARCHIVO = "tienda.sqlite"


def abrir(carpeta_datos: Path) -> BaseDatos:
    """Arranque: registros, base de datos al día y respaldos (del día y del mes) si faltan."""
    carpeta_datos.mkdir(parents=True, exist_ok=True)
    registro.configurar(carpeta_datos / "registros")
    bd = BaseDatos(carpeta_datos / ARCHIVO)
    bd.migrar()
    try:
        respaldos.respaldos_al_dia(bd, carpeta_datos / "respaldos")
    except Exception:  # un respaldo fallido no debe impedir vender; queda en respaldos.log
        pass
    return bd
