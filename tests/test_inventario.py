"""Pantallas de Productos y Llegó mercancía: rutas del servidor de punta a punta."""

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


def test_paginas(compu, celular):
    assert "Productos" in compu.get("/productos").text
    assert "Llegó mercancía" in compu.get("/mercancia").text
    assert celular.get("/productos").status_code == 403
    assert celular.get("/api/inventario").status_code == 403
    assert celular.post("/api/mercancia", json={}).status_code == 403


def test_lista_con_niveles(compu, bd, surtido):
    P.ajustar_conteo(bd, surtido["coca"], 4, "conteo")  # mínimo 6 → se está acabando
    d = compu.get("/api/inventario").json()
    niveles = {p["nombre"]: p["nivel"] for p in d["productos"]}
    assert niveles == {"Coca-Cola 600 ml": "acabando", "Huevo blanco": "bien"}
    assert d["acabando"] == 1 and d["acabados"] == 0
    assert [p["nombre"] for p in compu.get("/api/inventario", params={"filtro": "acabando"}).json()["productos"]] == ["Coca-Cola 600 ml"]
    assert compu.get("/api/inventario", params={"filtro": "otro"}).status_code == 422


def test_alta_completa(compu):
    r = compu.post("/api/inventario", json={"nombre": "Gansito", "precio": "18", "costo": "12.50", "unidad": "pieza",
                                             "codigo": "7501000111206", "minimo": 5})
    assert r.status_code == 200
    p = r.json()
    assert (p["precio"], p["costo"], p["minimo"], p["existencia"], p["nivel"]) == (1800, 1250, 5, 0, "acabado")
    assert p["historial"][0]["motivo"] == "alta"
    assert compu.get("/api/productos/codigo/7501000111206").json()["nombre"] == "Gansito"


def test_alta_explica_los_errores(compu):
    r = compu.post("/api/inventario", json={"nombre": "Gansito", "precio": "18.50", "unidad": "pieza"})
    assert r.status_code == 422 and "pesos cerrados" in r.json()["detail"]
    r = compu.post("/api/inventario", json={"nombre": "Repetida", "precio": "22", "unidad": "pieza", "codigo": "7501055300075"})
    assert r.status_code == 422  # ese código ya es de la Coca


def test_cambiar_precio_costo_minimo_y_codigo(compu, surtido):
    r = compu.post(f"/api/inventario/{surtido['coca']}", json={
        "nombre": "Coca-Cola 600", "precio": "24", "costo": "16", "codigo": "7501055300075", "minimo": 10})
    assert r.status_code == 200
    p = r.json()
    assert (p["nombre"], p["precio"], p["costo"], p["minimo"], p["codigo"]) == ("Coca-Cola 600", 2400, 1600, 10, "7501055300075")
    assert [h["motivo"] for h in p["historial"][:2]] == ["costo corregido", "cambio de precio"]
    quitar = compu.post(f"/api/inventario/{surtido['coca']}", json={"codigo": ""}).json()
    assert quitar["codigo"] is None


def test_cambio_con_error_no_guarda_nada(compu, bd, surtido):
    r = compu.post(f"/api/inventario/{surtido['coca']}", json={"nombre": "Nombre nuevo", "precio": "24.50"})
    assert r.status_code == 422
    assert P.obtener(bd, surtido["coca"]).nombre == "Coca-Cola 600 ml"


def test_contar(compu, bd, surtido):
    r = compu.post(f"/api/inventario/{surtido['coca']}/contar", json={"contado": 20, "motivo": "Merma"})
    assert r.json()["diferencia"] == -4 and r.json()["existencia"] == 20
    assert P.movimientos(bd, surtido["coca"])[0]["nota"] == "Merma"


def test_desactivar_y_reactivar(compu, surtido):
    assert compu.post(f"/api/inventario/{surtido['coca']}/desactivar").json()["activo"] is False
    assert compu.get("/api/productos", params={"q": "coca"}).json() == []  # ya no sale para vender
    assert [p["nombre"] for p in compu.get("/api/inventario", params={"filtro": "desactivados"}).json()["productos"]] == ["Coca-Cola 600 ml"]
    assert compu.post(f"/api/inventario/{surtido['coca']}/reactivar").json()["activo"] is True


def test_llego_mercancia_suma_y_promedia_el_costo(compu, bd, surtido):
    datos = {"operacion": "llegada-0001", "nota": "  Distribuidora  del centro ",
             "renglones": [{"producto_id": surtido["coca"], "cantidad": 24, "costo": 1600},
                           {"producto_id": surtido["huevo"], "cantidad": 22_500, "costo": 4000}]}
    r = compu.post("/api/mercancia", json=datos)
    assert r.status_code == 200
    coca = P.obtener(bd, surtido["coca"])
    assert coca.existencia == 48 and coca.costo_promedio == 1575  # (24 × 15.50 + 24 × 16) / 48
    assert P.obtener(bd, surtido["huevo"]).existencia == 45_000
    assert P.movimientos(bd, surtido["coca"])[0]["nota"] == "Distribuidora del centro"
    # un doble clic no suma dos veces
    assert compu.post("/api/mercancia", json=datos).json() == r.json()
    assert P.obtener(bd, surtido["coca"]).existencia == 48


def test_llegada_con_error_no_suma_nada(compu, bd, surtido):
    r = compu.post("/api/mercancia", json={"operacion": "llegada-0002", "renglones": [
        {"producto_id": surtido["coca"], "cantidad": 10, "costo": 1600},
        {"producto_id": 999, "cantidad": 1, "costo": 100}]})
    assert r.status_code == 404
    assert P.obtener(bd, surtido["coca"]).existencia == 24
