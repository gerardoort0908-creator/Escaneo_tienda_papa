"""Pantallas de Fiado y Corte de caja: rutas del servidor de punta a punta."""

import pytest
from fastapi.testclient import TestClient

from app.main import Configuracion, crear_app
from tienda import productos as P

LLAVE = "llave-de-prueba-1234567890"


@pytest.fixture
def compu(bd, surtido):
    app = crear_app(Configuracion(ip="192.168.1.50", llave=LLAVE, certificados=None), bd)
    return TestClient(app, client=("127.0.0.1", 50000))


@pytest.fixture
def celular(bd):
    app = crear_app(Configuracion(ip="192.168.1.50", llave=LLAVE, certificados=None), bd)
    return TestClient(app, client=("192.168.1.77", 50000))


def _fiar(compu, cliente_id, renglones, total, operacion="fiar-00000001"):
    return compu.post("/api/ventas/fiar", json={"operacion": operacion, "renglones": renglones,
                                                "total_visto": total, "cliente_id": cliente_id})


def _cliente(compu, nombre="Doña Lupe"):
    return compu.post("/api/clientes", json={"nombre": nombre, "telefono": "55 1234 5678"}).json()["id"]


def test_paginas_solo_en_la_compu(compu, celular):
    assert "Préstamos" in compu.get("/fiado").text
    assert "Corte de caja" in compu.get("/caja").text
    for ruta in ("/fiado", "/caja", "/api/clientes", "/api/caja"):
        assert celular.get(ruta).status_code == 403
    assert celular.post("/api/ventas/fiar", json={}).status_code == 403


def test_vender_fiado_y_ver_lo_que_se_llevo(compu, bd, surtido):
    lupe = _cliente(compu)
    r = _fiar(compu, lupe, [{"producto_id": surtido["coca"], "cantidad": 2},
                            {"producto_id": surtido["huevo"], "cantidad": 1500}], 2 * 2200 + 6800)
    assert r.status_code == 200
    assert r.json()["cliente"]["saldo"] == 11200
    assert P.obtener(bd, surtido["coca"]).existencia == 22
    d = compu.get(f"/api/clientes/{lupe}").json()
    assert d["saldo"] == 11200
    assert d["movimientos"][0]["detalle"] == "2 Coca-Cola 600 ml, 1½ kg Huevo blanco"


def test_fiar_dos_veces_la_misma_operacion_no_cobra_doble(compu, surtido):
    lupe = _cliente(compu)
    renglones = [{"producto_id": surtido["coca"], "cantidad": 1}]
    _fiar(compu, lupe, renglones, 2200)
    _fiar(compu, lupe, renglones, 2200)
    assert compu.get(f"/api/clientes/{lupe}").json()["saldo"] == 2200


def test_fiar_rechaza_si_el_precio_cambio(compu, bd, surtido):
    lupe = _cliente(compu)
    P.editar(bd, surtido["coca"], precio_venta=2400)
    r = _fiar(compu, lupe, [{"producto_id": surtido["coca"], "cantidad": 1}], 2200)
    assert r.status_code == 422 and "$24" in r.json()["detail"]
    assert compu.get(f"/api/clientes/{lupe}").json()["saldo"] == 0
    assert P.obtener(bd, surtido["coca"]).existencia == 24


def test_abonar_y_pago_todo(compu, surtido):
    lupe = _cliente(compu)
    _fiar(compu, lupe, [{"producto_id": surtido["coca"], "cantidad": 5}], 11000)
    r = compu.post(f"/api/clientes/{lupe}/abonar", json={"operacion": "abono-0000001", "monto": "50"})
    assert r.json()["saldo"] == 6000 and r.json()["pago"] == 5000
    # el mismo abono reenviado no cuenta doble
    compu.post(f"/api/clientes/{lupe}/abonar", json={"operacion": "abono-0000001", "monto": "50"})
    assert compu.get(f"/api/clientes/{lupe}").json()["saldo"] == 6000
    r = compu.post(f"/api/clientes/{lupe}/abonar", json={"operacion": "abono-0000002", "monto": "100"})
    assert r.status_code == 422 and "Solo debe $60" in r.json()["detail"]
    r = compu.post(f"/api/clientes/{lupe}/abonar", json={"operacion": "abono-0000003", "todo": True})
    assert r.json()["saldo"] == 0 and r.json()["pago"] == 6000
    assert r.json()["movimientos"][0]["nota"] == "Pagó todo"


def test_lista_de_clientes_primero_los_que_deben(compu, surtido):
    lupe, beto, ana = _cliente(compu, "Lupe"), _cliente(compu, "Beto"), _cliente(compu, "Ana")
    _fiar(compu, lupe, [{"producto_id": surtido["coca"], "cantidad": 1}], 2200, "op-lupe-001")
    _fiar(compu, beto, [{"producto_id": surtido["coca"], "cantidad": 3}], 6600, "op-beto-001")
    d = compu.get("/api/clientes").json()
    assert [c["nombre"] for c in d["clientes"]] == ["Beto", "Lupe", "Ana"]
    assert (d["deben"], d["total"]) == (2, 8800)
    assert [c["nombre"] for c in compu.get("/api/clientes", params={"q": "lu"}).json()["clientes"]] == ["Lupe"]


def test_cliente_repetido_y_quitar(compu, surtido):
    lupe = _cliente(compu)
    r = compu.post("/api/clientes", json={"nombre": "doña lupe"})
    assert r.status_code == 422 and "apellido" in r.json()["detail"]
    _fiar(compu, lupe, [{"producto_id": surtido["coca"], "cantidad": 1}], 2200)
    r = compu.post(f"/api/clientes/{lupe}/quitar")
    assert r.status_code == 422 and "debe $22" in r.json()["detail"]
    compu.post(f"/api/clientes/{lupe}/abonar", json={"operacion": "abono-todo-01", "todo": True})
    assert compu.post(f"/api/clientes/{lupe}/quitar").status_code == 200
    assert compu.get("/api/clientes").json()["clientes"] == []


def test_editar_cliente(compu):
    lupe = _cliente(compu)
    r = compu.post(f"/api/clientes/{lupe}", json={"nombre": "Lupe Martínez", "telefono": ""})
    assert (r.json()["nombre"], r.json()["telefono"]) == ("Lupe Martínez", None)


def test_cancelar_venta_fiada_quita_la_deuda(compu, surtido):
    lupe = _cliente(compu)
    venta = _fiar(compu, lupe, [{"producto_id": surtido["coca"], "cantidad": 2}], 4400).json()["venta_id"]
    compu.post(f"/api/ventas/{venta}/cancelar", json={"motivo": "Me equivoqué"})
    assert compu.get(f"/api/clientes/{lupe}").json()["saldo"] == 0


def test_caja_de_punta_a_punta(compu, surtido):
    assert compu.get("/api/caja").json()["abierta"] is False
    assert compu.post("/api/caja/abrir", json={"monto": "500"}).json()["fondo"] == 50000
    assert compu.post("/api/caja/abrir", json={"monto": "500"}).status_code == 422
    # una venta en efectivo, una fiada y un abono
    compu.post("/api/ventas/cobrar", json={"operacion": "cobro-0000001", "renglones": [
        {"producto_id": surtido["coca"], "cantidad": 3}], "recibido": 10000, "total_visto": 6600})
    lupe = _cliente(compu)
    _fiar(compu, lupe, [{"producto_id": surtido["coca"], "cantidad": 2}], 4400)
    compu.post(f"/api/clientes/{lupe}/abonar", json={"operacion": "abono-caja-01", "monto": "20"})
    r = compu.post("/api/caja/retiro", json={"monto": "100", "nota": "Pagué al de las Cocas"})
    c = r.json()
    assert (c["ventas_efectivo"], c["abonos"], c["retiros"]) == (6600, 2000, 10000)
    assert c["esperado"] == 50000 + 6600 + 2000 - 10000
    assert c["lista_retiros"][0]["nota"] == "Pagué al de las Cocas"
    assert c["ventas"]["ventas"] == 2 and c["ventas"]["fiado"] == 4400
    assert c["ventas"]["ganancia"] == 5 * (2200 - 1550)
    # contaron 5 pesos menos
    r = compu.post("/api/caja/cerrar", json={"monto": "481", "nota": "  "}).json()
    assert (r["esperado"], r["contado"], r["diferencia"]) == (48600, 48100, -500)
    assert r["caja"]["abierta"] is False and r["caja"]["anteriores"][0]["diferencia"] == -500
    assert compu.post("/api/caja/cerrar", json={"monto": "1"}).status_code == 422


def test_retiro_necesita_motivo(compu):
    compu.post("/api/caja/abrir", json={"monto": "0"})
    r = compu.post("/api/caja/retiro", json={"monto": "50"})
    assert r.status_code == 422 and "para qué" in r.json()["detail"]
