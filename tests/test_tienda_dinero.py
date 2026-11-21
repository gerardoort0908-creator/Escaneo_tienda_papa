import pytest

from tienda.nucleo import dinero
from tienda.nucleo.errores import DatoInvalido


@pytest.mark.parametrize("texto, centavos", [
    ("22", 2200), ("18.5", 1850), ("18.50", 1850), ("$1,250.05", 125005), (" 0.50 ", 50), (7, 700),
])
def test_lee_lo_que_se_escribe(texto, centavos):
    assert dinero.a_centavos(texto) == centavos


@pytest.mark.parametrize("texto", ["", "abc", "-5", "1.234", "1e3", "12.", ".5", True, "0"])
def test_rechaza_lo_que_no_es_dinero(texto):
    with pytest.raises(DatoInvalido):
        dinero.a_centavos(texto)


def test_cero_solo_si_se_permite():
    assert dinero.a_centavos("0", permitir_cero=True) == 0


def test_precio_de_venta_en_pesos_cerrados():
    assert dinero.validar_precio_venta(2200) == 2200
    with pytest.raises(DatoInvalido):
        dinero.validar_precio_venta(2250)


@pytest.mark.parametrize("centavos, esperado", [(2250, 2300), (2249, 2200), (2200, 2200), (50, 100), (49, 0)])
def test_redondeo_al_peso(centavos, esperado):
    assert dinero.redondear_a_peso(centavos) == esperado


def test_division_redondeada_con_negativos():
    assert dinero.dividir_redondeando(-5, 2) == -3
    assert dinero.dividir_redondeando(5, 2) == 3


@pytest.mark.parametrize("centavos, texto", [(2200, "$22"), (1850, "$18.50"), (125000, "$1,250"), (5, "$0.05"), (-300, "-$3")])
def test_formato(centavos, texto):
    assert dinero.formatear(centavos) == texto


def test_sumas_sin_perder_centavos():
    assert sum([10] * 1000) == 10_00 * 10  # 1000 × $0.10 = $100 exactos
