"""La app del celular: vende sin la PC y sus ventas entran al programa cuando la PC contesta."""

import pytest
from fastapi.testclient import TestClient

from app.main import Configuracion, crear_app
from tienda import productos as P
from tienda import ventas

LLAVE = "llave-de-prueba-1234567890"
H = {"X-Llave": LLAVE}


def _app(bd, ip_cliente):
    config = Configuracion(ip="192.168.1.50", llave=LLAVE, certificados=None)
    return TestClient(crear_app(config, bd), client=(ip_cliente, 50000))


@pytest.fixture
def celular(bd, surtido):
    return _app(bd, "192.168.1.77")


@pytest.fixture
def compu(bd, surtido):
    return _app(bd, "127.0.0.1")


def _venta(surtido, id_="venta-celular-001", cocas=2, recibido=5000):
    return {"id": id_, "cuando": "2026-11-20 10:15:00", "celular": "iPhone-ab12", "total": 2200 * cocas,
            "recibido": recibido,
            "renglones": [{"producto_id": surtido["coca"], "nombre": "Coca-Cola 600 ml", "unidad": "pieza", "cantidad": cocas, "precio": 2200}]}


def test_el_celular_abre_la_app_sin_llave_pero_los_datos_piden_llave(celular):
    assert "Tu tienda" in celular.get("/celular").text
    assert celular.get("/celular-sw.js").headers["service-worker-allowed"] == "/"
    assert celular.get("/api/celular/productos").status_code == 401
    assert celular.post("/api/celular/ventas", json={"ventas": []}).status_code == 401


def test_productos_para_guardar_en_el_celular(celular):
    nombres = {p["nombre"]: p for p in celular.get("/api/celular/productos", headers=H).json()["productos"]}
    assert nombres["Coca-Cola 600 ml"]["precio"] == 2200
    assert nombres["Huevo blanco"]["unidad"] == "kg"
    assert nombres["Coca-Cola 600 ml"]["codigo"] == "7501055300075"  # para escanear sin la PC


def test_las_ventas_del_celular_entran_al_programa_una_sola_vez(celular, bd, surtido):
    r = celular.post("/api/celular/ventas", json={"ventas": [_venta(surtido)]}, headers=H).json()
    assert r == {"guardadas": ["venta-celular-001"], "nuevas": 1, "problemas": {}}
    assert P.obtener(bd, surtido["coca"]).existencia == 22
    # se cortó el WiFi antes de que el celular viera la respuesta: la manda otra vez, con otra nueva
    r = celular.post("/api/celular/ventas", json={"ventas": [_venta(surtido), _venta(surtido, "venta-celular-002", 1, 2200)]},
                     headers=H).json()
    assert r["nuevas"] == 1 and r["guardadas"] == ["venta-celular-001", "venta-celular-002"]
    assert P.obtener(bd, surtido["coca"]).existencia == 21
    recibidas = ventas.del_celular_recientes(bd)
    assert [v["origen"] for v in recibidas] == ["venta-celular-002", "venta-celular-001"]
    hecha = ventas.obtener(bd, recibidas[1]["venta_id"])
    assert (hecha["cuando"], hecha["total"], hecha["cambio"]) == ("2026-11-20 10:15:00", 4400, 600)


def test_una_venta_con_producto_que_no_existe_se_queda_en_el_celular(celular, surtido):
    mala = _venta(surtido, "venta-celular-009")
    mala["renglones"][0]["producto_id"] = 99999
    r = celular.post("/api/celular/ventas", json={"ventas": [mala, _venta(surtido, "venta-celular-010")]}, headers=H).json()
    assert r["guardadas"] == ["venta-celular-010"] and "venta-celular-009" in r["problemas"]


def test_conectar_celular_abre_la_app(compu):
    assert compu.get("/api/info").json()["url_celular"] == f"https://192.168.1.50:8443/celular?llave={LLAVE}"


def test_el_icono_viejo_de_la_prueba_lleva_a_la_app(celular):
    r = celular.get("/prueba", params={"llave": LLAVE}, follow_redirects=False)
    assert r.headers["location"] == f"/celular?llave={LLAVE}"


def test_la_app_instalada_recibe_la_llave_al_abrir(celular):
    # la página que abre el QR ya trae el manifiesto con la llave (el iPhone lo lee al cargar)
    assert f'href="/celular.webmanifest?k={LLAVE}"' in celular.get("/celular", params={"llave": LLAVE}).text
    assert 'href="/celular.webmanifest"' in celular.get("/celular", params={"llave": "otra"}).text
    assert celular.get("/celular.webmanifest", params={"k": LLAVE}).json()["start_url"] == f"/celular?llave={LLAVE}"
    assert celular.get("/celular.webmanifest", params={"k": "otra"}).json()["start_url"] == "/celular"
