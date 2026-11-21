"""Averigua la dirección de esta computadora dentro del WiFi de la tienda."""

from __future__ import annotations

import ipaddress
import socket


def es_ip_local(ip: str) -> bool:
    """True si la IP es de una red casera/privada (192.168.x.x, 10.x.x.x, 172.16-31.x.x)."""
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return (
        direccion.version == 4
        and direccion.is_private
        and not direccion.is_loopback
        and not direccion.is_link_local
    )


def ip_en_la_red() -> str:
    """Devuelve la IP de la computadora en el WiFi, o 127.0.0.1 si no está conectada.

    Abrir un socket UDP hacia una dirección externa no envía nada; solo le pide al
    sistema que elija la tarjeta de red que usaría, y de ahí sale nuestra IP.
    """
    candidatas: list[str] = []
    for destino in ("192.168.255.255", "10.255.255.255", "8.8.8.8"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((destino, 1))
                candidatas.append(s.getsockname()[0])
        except OSError:
            continue
    try:
        candidatas.extend(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    for ip in candidatas:
        if es_ip_local(ip):
            return ip
    return "127.0.0.1"
