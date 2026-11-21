from datetime import date

import pytest

from tienda import fiado, productos as P, reportes, ventas as V
from tienda.nucleo.errores import DatoInvalido, NoPermitido, PagoInsuficiente


def test_cobro_con_cambio(bd, surtido):
    recibo = V.cobrar_efectivo(bd, [V.Pedido(surtido["coca"], 2)], 5000)
    assert (recibo.total, recibo.cambio) == (4400, 600)
    assert P.obtener(bd, surtido["coca"]).existencia == 22


def test_pago_con_monedas_de_50_centavos(bd, surtido):
    recibo = V.cobrar_efectivo(bd, [V.Pedido(surtido["coca"], 1)], 2250)
    assert recibo.cambio == 50


def test_no_alcanza_y_no_se_guarda_nada(bd, surtido):
    with pytest.raises(PagoInsuficiente, match=r"Faltan \$2"):
        V.cobrar_efectivo(bd, [V.Pedido(surtido["coca"], 1)], 2000)
    assert P.obtener(bd, surtido["coca"]).existencia == 24
    assert reportes.ganancia(bd, date.today(), date.today()).numero_ventas == 0


def test_mismo_producto_dos_veces_va_en_un_renglon(bd, surtido):
    cuenta = V.cotizar(bd, [V.Pedido(surtido["coca"], 1), V.Pedido(surtido["coca"], 2)])
    assert len(cuenta.renglones) == 1 and cuenta.total == 6600


@pytest.mark.parametrize("gramos, total", [(500, 2300), (1000, 4500), (1500, 6800)])
def test_huevo_redondeado_al_peso(bd, surtido, gramos, total):
    assert V.cotizar(bd, [V.Pedido(surtido["huevo"], gramos)]).total == total


def test_huevo_fuera_de_medio_kilo(bd, surtido):
    with pytest.raises(DatoInvalido):
        V.cotizar(bd, [V.Pedido(surtido["huevo"], 700)])


def test_ganancia_de_la_venta(bd, surtido):
    cuenta = V.cotizar(bd, [V.Pedido(surtido["coca"], 2), V.Pedido(surtido["huevo"], 1000)])
    assert cuenta.costo_total == 2 * 1550 + 3820
    assert cuenta.ganancia == 4400 + 4500 - 6920


def test_cambiar_precio_no_cambia_ventas_pasadas(bd, surtido):
    recibo = V.cobrar_efectivo(bd, [V.Pedido(surtido["coca"], 1)], 2200)
    P.editar(bd, surtido["coca"], precio_venta=2500, nombre="Coca 600")
    venta = V.obtener(bd, recibo.venta_id)
    assert venta["total"] == 2200
    assert venta["renglones"][0]["nombre"] == "Coca-Cola 600 ml"


def test_producto_desactivado_no_se_vende(bd, surtido):
    P.desactivar(bd, surtido["coca"])
    with pytest.raises(NoPermitido):
        V.cotizar(bd, [V.Pedido(surtido["coca"], 1)])


def test_se_puede_vender_aunque_el_inventario_diga_cero(bd, surtido):
    P.ajustar_conteo(bd, surtido["coca"], 0, "conteo")
    V.cobrar_efectivo(bd, [V.Pedido(surtido["coca"], 1)], 2200)
    assert P.obtener(bd, surtido["coca"]).existencia == -1


def test_cancelar_regresa_inventario(bd, surtido):
    recibo = V.cobrar_efectivo(bd, [V.Pedido(surtido["coca"], 3)], 10000)
    V.cancelar(bd, recibo.venta_id, "se equivocó de refresco")
    assert P.obtener(bd, surtido["coca"]).existencia == 24
    assert V.obtener(bd, recibo.venta_id)["estado"] == "cancelada"
    assert reportes.ganancia(bd, date.today(), date.today()).numero_ventas == 0
    with pytest.raises(NoPermitido):
        V.cancelar(bd, recibo.venta_id, "otra vez")


def test_cancelar_pide_motivo(bd, surtido):
    recibo = V.cobrar_efectivo(bd, [V.Pedido(surtido["coca"], 1)], 2200)
    with pytest.raises(DatoInvalido):
        V.cancelar(bd, recibo.venta_id, " ")


def test_venta_fiada_y_su_cancelacion(bd, surtido):
    ana = fiado.crear_cliente(bd, "Doña Ana")
    venta = V.vender_fiado(bd, [V.Pedido(surtido["coca"], 2)], ana)
    assert fiado.obtener(bd, ana).saldo == 4400
    V.cancelar(bd, venta, "no se lo llevó")
    assert fiado.obtener(bd, ana).saldo == 0
    assert P.obtener(bd, surtido["coca"]).existencia == 24


def test_venta_fiada_a_cliente_inexistente_no_deja_rastro(bd, surtido):
    with pytest.raises(Exception):
        V.vender_fiado(bd, [V.Pedido(surtido["coca"], 1)], 999)
    assert P.obtener(bd, surtido["coca"]).existencia == 24


def test_reportes_mas_vendidos(bd, surtido):
    V.cobrar_efectivo(bd, [V.Pedido(surtido["coca"], 3)], 10000)
    V.cobrar_efectivo(bd, [V.Pedido(surtido["huevo"], 500)], 2300)
    hoy = date.today()
    top = reportes.mas_vendidos(bd, hoy, hoy)
    assert [t["nombre"] for t in top] == ["Coca-Cola 600 ml", "Huevo blanco"]
    assert top[0]["cantidad"] == 3 and top[0]["ganancia"] == 3 * (2200 - 1550)
    g = reportes.ganancia(bd, hoy, hoy)
    assert (g.ventas, g.numero_ventas) == (8900, 2)


# ---------------------------------------------------------------- ventas hechas en el celular

def test_venta_del_celular_entra_con_su_hora_y_su_precio(bd, surtido):
    from tienda.nucleo import reloj

    hace_rato = reloj.texto(reloj.ahora().replace(microsecond=0) - __import__("datetime").timedelta(hours=2))
    renglones = [V.DelCelular(surtido["coca"], 2, 2000), V.DelCelular(surtido["huevo"], 500, 4500)]
    venta_id, nueva = V.de_celular(bd, "cel-0001-abcd", "iPhone-ab12", hace_rato, renglones, 10000)
    assert nueva
    v = V.obtener(bd, venta_id)
    assert v["cuando"] == hace_rato and v["total"] == 4000 + 2300 and v["cambio"] == 10000 - 6300
    assert P.obtener(bd, surtido["coca"]).existencia == 22  # sí se descontó
    # llega otra vez (se cortó el WiFi): no se duplica
    assert V.de_celular(bd, "cel-0001-abcd", "iPhone-ab12", hace_rato, renglones, 10000) == (venta_id, False)
    assert P.obtener(bd, surtido["coca"]).existencia == 22
    assert V.del_celular_recientes(bd)[0]["venta_id"] == venta_id


def test_venta_del_celular_con_reloj_adelantado_queda_en_ahora(bd, surtido):
    venta_id, _ = V.de_celular(bd, "cel-0002-abcd", "Huawei-x", "2099-01-01 10:00:00",
                                    [V.DelCelular(surtido["coca"], 1, 2200)], 2200)
    assert V.obtener(bd, venta_id)["cuando"] < "2099"
