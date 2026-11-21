import datetime as dt

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec

from app.certificados import VIGENCIA_SERVIDOR, preparar_certificados, sello_en_der


def _cargar(ruta):
    return x509.load_pem_x509_certificate(ruta.read_bytes())


def test_el_sello_firma_al_servidor_y_cubre_la_ip(tmp_path):
    rutas = preparar_certificados(tmp_path, "192.168.1.50")
    sello, servidor = _cargar(rutas.sello), _cargar(rutas.servidor)

    servidor.verify_directly_issued_by(sello)
    san = servidor.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert "192.168.1.50" in {str(i) for i in san.get_values_for_type(x509.IPAddress)}
    assert sello.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    assert not servidor.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    # Apple no acepta certificados de servidor de más de 825 días.
    assert servidor.not_valid_after_utc - servidor.not_valid_before_utc <= dt.timedelta(days=825)
    assert VIGENCIA_SERVIDOR <= dt.timedelta(days=825)
    assert isinstance(servidor.public_key(), ec.EllipticCurvePublicKey)


def test_misma_ip_no_rehace_nada(tmp_path):
    rutas = preparar_certificados(tmp_path, "192.168.1.50")
    antes = (rutas.sello.read_bytes(), rutas.servidor.read_bytes())
    preparar_certificados(tmp_path, "192.168.1.50")
    assert (rutas.sello.read_bytes(), rutas.servidor.read_bytes()) == antes


def test_si_cambia_la_ip_se_rehace_el_servidor_pero_no_el_sello(tmp_path):
    rutas = preparar_certificados(tmp_path, "192.168.1.50")
    sello_antes, servidor_antes = rutas.sello.read_bytes(), rutas.servidor.read_bytes()
    preparar_certificados(tmp_path, "192.168.1.80")
    assert rutas.sello.read_bytes() == sello_antes
    assert rutas.servidor.read_bytes() != servidor_antes
    _cargar(rutas.servidor).verify_directly_issued_by(_cargar(rutas.sello))


def test_sello_en_der_es_el_mismo_certificado(tmp_path):
    rutas = preparar_certificados(tmp_path, "10.0.0.5")
    assert x509.load_der_x509_certificate(sello_en_der(rutas)) == _cargar(rutas.sello)
