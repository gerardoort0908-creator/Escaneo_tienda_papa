"""Todo el dinero se maneja en centavos enteros: $22 se guarda como 2200.

Con números enteros las sumas nunca pierden un centavo (con decimales, 0.1 + 0.2
no da exactamente 0.3 en la computadora).
"""

from __future__ import annotations

import re

from .errores import DatoInvalido

_FORMA = re.compile(r"^\d+(\.\d{1,2})?$")
TOPE = 100_000_000  # $1,000,000.00: nada en la tienda debería pasar de aquí


def a_centavos(texto: str | int, *, permitir_cero: bool = False) -> int:
    """Convierte lo que se escribe ("22", "18.50", "$1,250.5") a centavos.

    Un número entero de Python se toma como pesos. No acepta negativos ni más de
    dos decimales.
    """
    if isinstance(texto, bool):
        raise DatoInvalido("Cantidad de dinero no válida")
    if isinstance(texto, int):
        centavos = texto * 100
    else:
        limpio = str(texto).strip().replace("$", "").replace(",", "").replace(" ", "")
        if not _FORMA.match(limpio):
            raise DatoInvalido(f"«{texto}» no es una cantidad de dinero válida")
        pesos, _, decimales = limpio.partition(".")
        centavos = int(pesos) * 100 + int((decimales + "00")[:2])
    validar_centavos(centavos, permitir_cero=permitir_cero)
    return centavos


def validar_centavos(centavos: int, *, permitir_cero: bool = False) -> int:
    if isinstance(centavos, bool) or not isinstance(centavos, int):
        raise DatoInvalido("Cantidad de dinero no válida")
    if centavos < 0 or (centavos == 0 and not permitir_cero):
        raise DatoInvalido("La cantidad debe ser mayor que cero")
    if centavos > TOPE:
        raise DatoInvalido("La cantidad es demasiado grande")
    return centavos


def validar_precio_venta(centavos: int) -> int:
    """El precio de venta va en pesos cerrados (22, 88): sin centavos."""
    validar_centavos(centavos)
    if centavos % 100:
        raise DatoInvalido("El precio de venta va en pesos cerrados, sin centavos")
    return centavos


def dividir_redondeando(numerador: int, divisor: int) -> int:
    """División entera redondeando a la mitad hacia arriba (2.5 → 3), sin decimales de por medio."""
    if divisor <= 0:
        raise ValueError("divisor debe ser positivo")
    signo = -1 if numerador < 0 else 1
    return signo * ((2 * abs(numerador) + divisor) // (2 * divisor))


def redondear_a_peso(centavos: int) -> int:
    """$22.50 → $23; $22.49 → $22."""
    return dividir_redondeando(centavos, 100) * 100


def formatear(centavos: int) -> str:
    """2200 → "$22"; 1850 → "$18.50"; 125000 → "$1,250"."""
    signo = "-" if centavos < 0 else ""
    pesos, resto = divmod(abs(centavos), 100)
    texto = f"{pesos:,}"
    if resto:
        texto += f".{resto:02d}"
    return f"{signo}${texto}"
