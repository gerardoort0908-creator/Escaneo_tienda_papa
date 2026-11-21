"""Errores con mensajes en palabras sencillas, listos para mostrarse en pantalla."""

from __future__ import annotations


class ErrorTienda(Exception):
    """Algo que el programa no puede hacer; el mensaje se le puede enseñar a quien lo usa."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class DatoInvalido(ErrorTienda):
    """Un número, nombre o código que no tiene sentido."""


class NoEncontrado(ErrorTienda):
    """El producto, cliente o venta no existe."""


class Repetido(ErrorTienda):
    """Ya existe algo con ese código o nombre."""


class PagoInsuficiente(ErrorTienda):
    """El dinero recibido no alcanza para el total."""


class NoPermitido(ErrorTienda):
    """La operación no se puede hacer en el estado actual (por ejemplo, cancelar dos veces)."""
