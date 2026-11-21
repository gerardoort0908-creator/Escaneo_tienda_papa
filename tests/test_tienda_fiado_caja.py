import pytest

from tienda import caja, fiado, ventas as V
from tienda.nucleo.errores import DatoInvalido, NoPermitido, Repetido


@pytest.fixture
def ana(bd, surtido):
    cliente = fiado.crear_cliente(bd, "Doña Ana", telefono=" 33 1234 5678 ")
    V.vender_fiado(bd, [V.Pedido(surtido["coca"], 5)], cliente)  # debe $110
    return cliente


def test_abono_y_pago_todo(bd, ana):
    assert fiado.abonar(bd, ana, 5000) == 6000
    assert fiado.pago_todo(bd, ana) == 6000
    assert fiado.obtener(bd, ana).saldo == 0
    assert [m["tipo"] for m in fiado.historial(bd, ana)] == ["cargo", "abono", "abono"]


def test_no_se_abona_de_mas(bd, ana):
    with pytest.raises(DatoInvalido, match=r"\$110"):
        fiado.abonar(bd, ana, 20000)
    fiado.pago_todo(bd, ana)
    with pytest.raises(NoPermitido):
        fiado.abonar(bd, ana, 100)


def test_nombre_repetido_sin_importar_mayusculas(bd, ana):
    with pytest.raises(Repetido):
        fiado.crear_cliente(bd, "doña  ANA")


def test_no_se_desactiva_quien_debe(bd, ana):
    with pytest.raises(NoPermitido, match="debe"):
        fiado.desactivar_cliente(bd, ana)
    fiado.pago_todo(bd, ana)
    fiado.desactivar_cliente(bd, ana)
    assert fiado.buscar(bd) == []


def test_deudores(bd, ana):
    beto = fiado.crear_cliente(bd, "Beto")
    assert [c.nombre for c in fiado.deudores(bd)] == ["Doña Ana"]
    assert fiado.obtener(bd, beto).saldo == 0


def test_corte_de_caja(bd, surtido, ana):
    caja.abrir(bd, 50000)
    V.cobrar_efectivo(bd, [V.Pedido(surtido["coca"], 2)], 50000)      # +$44
    cancelada = V.cobrar_efectivo(bd, [V.Pedido(surtido["coca"], 1)], 2200)
    V.cancelar(bd, cancelada.venta_id, "error")                        # no cuenta
    V.vender_fiado(bd, [V.Pedido(surtido["coca"], 1)], ana)           # fiado: no es efectivo
    fiado.abonar(bd, ana, 3000)                                        # +$30
    caja.retirar(bd, 10000, "pago al de la Coca")                      # −$100
    r = caja.resumen(bd)
    assert (r.ventas_efectivo, r.abonos, r.retiros, r.esperado) == (4400, 3000, 10000, 47400)
    corte = caja.cerrar(bd, 47000)
    assert corte.diferencia == -400
    assert not caja.esta_abierta(bd)
    assert caja.cortes_anteriores(bd)[0]["diferencia"] == -400


def test_caja_una_a_la_vez(bd):
    caja.abrir(bd, 0)
    with pytest.raises(NoPermitido):
        caja.abrir(bd, 0)


def test_retiro_con_caja_cerrada_o_sin_nota(bd):
    with pytest.raises(NoPermitido):
        caja.retirar(bd, 100, "x")
    caja.abrir(bd, 0)
    with pytest.raises(DatoInvalido):
        caja.retirar(bd, 100, "")
