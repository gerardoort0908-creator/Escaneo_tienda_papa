import pytest

from tienda import productos as P
from tienda.nucleo.errores import DatoInvalido, NoEncontrado, Repetido


def test_alta_y_busqueda(bd, surtido):
    coca = P.por_codigo(bd, "7501055300075")
    assert coca.nombre == "Coca-Cola 600 ml" and coca.existencia == 24
    assert [p.nombre for p in P.buscar(bd, "coca")] == ["Coca-Cola 600 ml"]
    assert [p.nombre for p in P.buscar(bd, "huevo BLANCO")] == ["Huevo blanco"]
    assert P.buscar(bd, "100%") == []  # los comodines se buscan como letras
    assert P.por_codigo(bd, "000") is None


def test_codigo_repetido(bd, surtido):
    with pytest.raises(Repetido, match="Coca-Cola"):
        P.crear(bd, nombre="Otra", precio_venta=1000, codigo="7501055300075")


def test_codigo_de_producto_desactivado_sigue_apartado(bd, surtido):
    P.desactivar(bd, surtido["coca"])
    assert P.por_codigo(bd, "7501055300075") is None
    with pytest.raises(Repetido):
        P.crear(bd, nombre="Otra", precio_venta=1000, codigo="7501055300075")
    P.reactivar(bd, surtido["coca"])
    assert P.por_codigo(bd, "7501055300075") is not None


@pytest.mark.parametrize("datos", [
    {"nombre": "", "precio_venta": 1000},
    {"nombre": "x" * 81, "precio_venta": 1000},
    {"nombre": "Pan", "precio_venta": 1050},
    {"nombre": "Pan", "precio_venta": 0},
    {"nombre": "Pan", "precio_venta": 1000, "unidad": "litro"},
    {"nombre": "Pan", "precio_venta": 1000, "costo": -1},
])
def test_alta_invalida(bd, datos):
    with pytest.raises(DatoInvalido):
        P.crear(bd, **datos)


def test_costo_si_lleva_centavos(bd):
    pid = P.crear(bd, nombre="Chicle", precio_venta=100, costo=37)
    assert P.obtener(bd, pid).costo_promedio == 37


def test_editar_precio_guarda_historial(bd, surtido):
    P.editar(bd, surtido["coca"], precio_venta=2300)
    historia = P.historial_precios(bd, surtido["coca"])
    assert [h["precio_venta"] for h in historia] == [2200, 2300]
    assert historia[-1]["motivo"] == "cambio de precio"


def test_editar_sin_cambiar_precio_no_ensucia_historial(bd, surtido):
    P.editar(bd, surtido["coca"], nombre="  Coca   600  ")
    assert P.obtener(bd, surtido["coca"]).nombre == "Coca 600"
    assert len(P.historial_precios(bd, surtido["coca"])) == 1


def test_quitar_codigo(bd, surtido):
    P.editar(bd, surtido["coca"], quitar_codigo=True)
    assert P.obtener(bd, surtido["coca"]).codigo is None


def test_costo_promedio_ponderado(bd):
    pid = P.crear(bd, nombre="Sabritas", precio_venta=2000, costo=1000)
    P.registrar_llegada(bd, [P.Llegada(pid, 10, 1000)])
    P.registrar_llegada(bd, [P.Llegada(pid, 10, 1200)])
    producto = P.obtener(bd, pid)
    assert producto.existencia == 20 and producto.costo_promedio == 1100


def test_costo_promedio_sin_existencia_toma_el_nuevo():
    assert P.costo_promedio(0, 999, 5, 1234) == 1234
    assert P.costo_promedio(-3, 999, 5, 1234) == 1234
    assert P.costo_promedio(3, 1000, 1, 1001) == 1000  # 1000.25 → 1000


def test_llegada_todo_o_nada(bd, surtido):
    with pytest.raises(NoEncontrado):
        P.registrar_llegada(bd, [P.Llegada(surtido["coca"], 5, 1500), P.Llegada(9999, 1, 100)])
    assert P.obtener(bd, surtido["coca"]).existencia == 24


def test_ajuste_por_conteo(bd, surtido):
    assert P.ajustar_conteo(bd, surtido["coca"], 20, "conteo") == -4
    assert P.obtener(bd, surtido["coca"]).existencia == 20
    assert P.ajustar_conteo(bd, surtido["coca"], 20, "conteo") == 0
    with pytest.raises(DatoInvalido):
        P.ajustar_conteo(bd, surtido["coca"], 20, "  ")


def test_faltantes(bd, surtido):
    assert P.faltantes(bd) == []
    P.ajustar_conteo(bd, surtido["coca"], 6, "conteo")
    assert [p.nombre for p in P.faltantes(bd)] == ["Coca-Cola 600 ml"]


def test_huevo_solo_de_medio_kilo(bd, surtido):
    P.validar_cantidad_venta("kg", 1500)
    with pytest.raises(DatoInvalido, match="medio kilo"):
        P.validar_cantidad_venta("kg", 750)


def test_corregir_costo_queda_en_el_historial(bd, surtido):
    from tienda import productos as P

    p = P.corregir_costo(bd, surtido["coca"], 1600)
    assert p.costo_promedio == 1600
    ultimo = P.historial_precios(bd, surtido["coca"])[-1]
    assert ultimo["costo"] == 1600 and ultimo["motivo"] == "costo corregido"
    assert P.corregir_costo(bd, surtido["coca"], 1600).costo_promedio == 1600  # sin cambio, sin renglón nuevo
    assert [h["motivo"] for h in P.historial_precios(bd, surtido["coca"])] == ["alta", "costo corregido"]
