import pytest

from app.codigos import CodigoInvalido, digito_verificador_correcto, normalizar


@pytest.mark.parametrize("codigo", ["7501055363056", "7501000111206", "96385074", "036000291452"])
def test_digito_verificador_correcto(codigo):
    assert digito_verificador_correcto(codigo)


@pytest.mark.parametrize("codigo", ["7501055363057", "96385075", "abc", "", "123"])
def test_digito_verificador_incorrecto(codigo):
    assert not digito_verificador_correcto(codigo)


def test_upc_a_se_guarda_como_ean_13():
    assert normalizar("036000291452", "upc_a") == ("0036000291452", "ean_13")


def test_ean_13_queda_igual_y_limpia_espacios():
    assert normalizar(" 7501055363056 ", "EAN-13") == ("7501055363056", "ean_13")


def test_lectura_equivocada_se_rechaza():
    with pytest.raises(CodigoInvalido):
        normalizar("7501055363057", "ean_13")


def test_largo_equivocado_para_el_formato():
    with pytest.raises(CodigoInvalido):
        normalizar("96385074", "ean_13")


@pytest.mark.parametrize("codigo,formato", [("ABC-123", "code_128"), ("https://x.mx/1", "qr_code")])
def test_otros_formatos_pasan_sin_digito(codigo, formato):
    assert normalizar(codigo, formato) == (codigo, formato)


@pytest.mark.parametrize("codigo,formato", [("123", "pdf417"), ("", "code_128"), ("a\nb", "code_128"), ("x" * 65, "code_128")])
def test_rechaza_basura(codigo, formato):
    with pytest.raises(CodigoInvalido):
        normalizar(codigo, formato)
