"""Revisar y limpiar los códigos que manda el celular."""

from __future__ import annotations

import re

# Formatos en que vienen los productos de tienda (y QR por si acaso).
FORMATOS_CON_DIGITO = {"ean_13", "ean_8", "upc_a", "upc_e"}
FORMATOS_ACEPTADOS = FORMATOS_CON_DIGITO | {"code_128", "code_39", "itf", "qr_code"}
LARGO_MAXIMO = 64
# Largos válidos por formato; el UPC-E no se revisa porque viene comprimido.
_LARGOS = {"ean_13": (13,), "ean_8": (8,), "upc_a": (12,)}
_IMPRIMIBLE = re.compile(r"^[\x20-\x7E]+$")


class CodigoInvalido(ValueError):
    """El código no se puede aceptar; el mensaje explica por qué."""


def digito_verificador_correcto(digitos: str) -> bool:
    """Revisa el último dígito de un EAN-13, EAN-8 o UPC-A (regla GS1).

    De derecha a izquierda (sin contar el último), los dígitos se multiplican por
    3, 1, 3, 1... La suma más el dígito verificador debe terminar en 0.
    """
    if not digitos.isdigit() or len(digitos) not in (8, 12, 13):
        return False
    cuerpo, verificador = digitos[:-1], int(digitos[-1])
    suma = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(cuerpo)))
    return (suma + verificador) % 10 == 0


def normalizar(codigo: str, formato: str) -> tuple[str, str]:
    """Deja el código en una sola forma para que el mismo producto siempre coincida.

    Un UPC-A de 12 dígitos es el mismo producto que su EAN-13 con un 0 al
    inicio; algunos celulares reportan uno y otros el otro, así que guardamos
    siempre el de 13.
    """
    codigo = codigo.strip()
    formato = formato.strip().lower().replace("-", "_")
    if formato not in FORMATOS_ACEPTADOS:
        raise CodigoInvalido(f"Formato no aceptado: {formato or 'vacío'}")
    if not codigo or len(codigo) > LARGO_MAXIMO or not _IMPRIMIBLE.match(codigo):
        raise CodigoInvalido("El código está vacío, es muy largo o trae caracteres raros")
    largos = _LARGOS.get(formato)
    if largos is not None:
        if len(codigo) not in largos or not digito_verificador_correcto(codigo):
            raise CodigoInvalido("El dígito verificador no cuadra: lectura equivocada")
        if len(codigo) == 12:
            return "0" + codigo, "ean_13"
    return codigo, formato
