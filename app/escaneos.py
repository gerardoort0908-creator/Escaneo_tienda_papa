"""Recibir escaneos sin repetirlos y avisar a la pantalla de la computadora."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from typing import Protocol

registro = logging.getLogger("escaner")


@dataclass(frozen=True)
class Escaneo:
    id: str
    codigo: str
    formato: str
    t_detectado: float  # ms, ya pasado al reloj de la computadora
    t_recibido: float  # ms, reloj de la computadora


class Receptor(Protocol):
    async def send_text(self, data: str) -> None: ...


class RegistroEscaneos:
    """Recuerda los últimos ids para que un reintento no cuente dos veces el mismo producto."""

    def __init__(self, capacidad: int = 5000) -> None:
        self._vistos: OrderedDict[str, Escaneo] = OrderedDict()
        self._capacidad = capacidad
        self.duplicados_evitados = 0

    def agregar(self, escaneo: Escaneo) -> bool:
        """True si es nuevo; False si ya había llegado (reintento del celular)."""
        if escaneo.id in self._vistos:
            self.duplicados_evitados += 1
            return False
        self._vistos[escaneo.id] = escaneo
        if len(self._vistos) > self._capacidad:
            self._vistos.popitem(last=False)
        return True

    def __len__(self) -> int:
        return len(self._vistos)


class Pantallas:
    """Las ventanas abiertas en la computadora que muestran los escaneos."""

    def __init__(self) -> None:
        self._conectadas: set[Receptor] = set()

    def conectar(self, pantalla: Receptor) -> None:
        self._conectadas.add(pantalla)

    def desconectar(self, pantalla: Receptor) -> None:
        self._conectadas.discard(pantalla)

    @property
    def cuantas(self) -> int:
        return len(self._conectadas)

    async def avisar(self, mensaje: dict) -> None:
        texto = json.dumps(mensaje)
        destinos = list(self._conectadas)
        resultados = await asyncio.gather(
            *(p.send_text(texto) for p in destinos), return_exceptions=True
        )
        for pantalla, resultado in zip(destinos, resultados):
            if isinstance(resultado, Exception):
                self.desconectar(pantalla)


def ahora_ms() -> float:
    return time.time() * 1000


def mensaje_de(escaneo: Escaneo) -> dict:
    return {"tipo": "escaneo", **asdict(escaneo)}
