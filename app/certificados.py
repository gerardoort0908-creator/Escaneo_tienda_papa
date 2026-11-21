"""Certificados para que el celular pueda abrir la cámara.

Los navegadores solo prestan la cámara a páginas seguras (https). Como todo pasa
dentro del WiFi de la tienda, creamos nuestro propio "sello" (autoridad
certificadora, AC) una sola vez, y con él firmamos el certificado del servidor.

- Si el celular instala el sello, nunca vuelve a ver avisos.
- Si no lo instala, el navegador muestra un aviso una vez y se puede continuar.

El certificado del servidor se rehace solo si cambia la IP de la computadora o
si está por vencer. El sello dura 10 años y no cambia, así el celular no tiene
que instalar nada otra vez.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

NOMBRE_SELLO = "Sello de la tienda (solo red local)"
VIGENCIA_SELLO = dt.timedelta(days=3650)
# Apple rechaza certificados de servidor de más de 825 días; usamos menos.
VIGENCIA_SERVIDOR = dt.timedelta(days=397)
RENOVAR_ANTES = dt.timedelta(days=30)


@dataclass(frozen=True)
class RutasCertificados:
    carpeta: Path

    @property
    def sello(self) -> Path:
        return self.carpeta / "sello-tienda.crt"

    @property
    def sello_llave(self) -> Path:
        return self.carpeta / "sello-tienda.key"

    @property
    def servidor(self) -> Path:
        return self.carpeta / "servidor.crt"

    @property
    def servidor_llave(self) -> Path:
        return self.carpeta / "servidor.key"


def _ahora() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _guardar_llave(llave: ec.EllipticCurvePrivateKey, ruta: Path) -> None:
    ruta.write_bytes(
        llave.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )


def _cargar_llave(ruta: Path) -> ec.EllipticCurvePrivateKey:
    llave = serialization.load_pem_private_key(ruta.read_bytes(), password=None)
    if not isinstance(llave, ec.EllipticCurvePrivateKey):
        raise ValueError(f"Llave inesperada en {ruta}")
    return llave


def _crear_sello(rutas: RutasCertificados) -> None:
    llave = ec.generate_private_key(ec.SECP256R1())
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, NOMBRE_SELLO)])
    inicio = _ahora() - dt.timedelta(days=1)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(nombre)
        .issuer_name(nombre)
        .public_key(llave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(inicio)
        .not_valid_after(inicio + VIGENCIA_SELLO)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_cert_sign=True, crl_sign=True,
                content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(llave.public_key()), critical=False)
        .sign(llave, hashes.SHA256())
    )
    _guardar_llave(llave, rutas.sello_llave)
    rutas.sello.write_bytes(certificado.public_bytes(serialization.Encoding.PEM))


def _servidor_sirve(rutas: RutasCertificados, ip: str, sello: x509.Certificate) -> bool:
    """True si el certificado actual es para esta IP, lo firmó este sello y no está por vencer."""
    if not (rutas.servidor.exists() and rutas.servidor_llave.exists()):
        return False
    try:
        cert = x509.load_pem_x509_certificate(rutas.servidor.read_bytes())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except (ValueError, x509.ExtensionNotFound):
        return False
    ips = {str(d) for d in san.get_values_for_type(x509.IPAddress)}
    return (
        ip in ips
        and cert.issuer == sello.subject
        and cert.not_valid_after_utc - _ahora() > RENOVAR_ANTES
    )


def _crear_servidor(rutas: RutasCertificados, ip: str) -> None:
    sello = x509.load_pem_x509_certificate(rutas.sello.read_bytes())
    sello_llave = _cargar_llave(rutas.sello_llave)
    llave = ec.generate_private_key(ec.SECP256R1())
    inicio = _ahora() - dt.timedelta(days=1)
    nombres: list[x509.GeneralName] = [
        x509.IPAddress(ipaddress.ip_address(ip)),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.DNSName("localhost"),
    ]
    certificado = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ip)]))
        .issuer_name(sello.subject)
        .public_key(llave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(inicio)
        .not_valid_after(inicio + VIGENCIA_SERVIDOR)
        .add_extension(x509.SubjectAlternativeName(nombres), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(sello_llave.public_key()),
            critical=False,
        )
        .sign(sello_llave, hashes.SHA256())
    )
    _guardar_llave(llave, rutas.servidor_llave)
    rutas.servidor.write_bytes(certificado.public_bytes(serialization.Encoding.PEM))


def preparar_certificados(carpeta: Path, ip: str) -> RutasCertificados:
    """Deja listos el sello y el certificado del servidor para la IP dada."""
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = RutasCertificados(carpeta)
    if not (rutas.sello.exists() and rutas.sello_llave.exists()):
        _crear_sello(rutas)
    sello = x509.load_pem_x509_certificate(rutas.sello.read_bytes())
    if not _servidor_sirve(rutas, ip, sello):
        _crear_servidor(rutas, ip)
    return rutas


def sello_en_der(rutas: RutasCertificados) -> bytes:
    """El sello en formato DER: el que Android e iPhone instalan sin quejarse."""
    cert = x509.load_pem_x509_certificate(rutas.sello.read_bytes())
    return cert.public_bytes(serialization.Encoding.DER)
