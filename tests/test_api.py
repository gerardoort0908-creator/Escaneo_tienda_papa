import time
import uuid

from conftest import LLAVE


def _escaneo(**cambios):
    datos = {"id": uuid.uuid4().hex, "codigo": "7501055363056", "formato": "ean_13", "t_detectado": time.time() * 1000}
    datos.update(cambios)
    return datos


def _enviar(cliente, datos, llave=LLAVE):
    return cliente.post("/api/escaneo", json=datos, headers={"X-Llave": llave})


def test_pantalla_solo_desde_la_computadora(compu, celular):
    assert compu.get("/pantalla").status_code == 200
    assert celular.get("/pantalla").status_code == 403
    assert celular.get("/api/info").status_code == 403
    assert celular.get("/api/qr.svg").status_code == 403


def test_inicio_lleva_a_cada_quien_a_su_pagina(compu, celular):
    assert compu.get("/", follow_redirects=False).headers["location"] == "/pantalla"
    assert celular.get("/", follow_redirects=False).headers["location"] == "/celular"


def test_info_y_qr(compu):
    info = compu.get("/api/info").json()
    assert info["url_celular"] == f"https://192.168.1.50:8443/celular#llave={LLAVE}"
    assert info["en_wifi"]
    qr = compu.get("/api/qr.svg")
    assert qr.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in qr.text


def test_hora_del_servidor(celular):
    antes = time.time() * 1000
    ts = celular.get("/api/hora").json()["ts"]
    assert antes - 5 <= ts <= time.time() * 1000 + 5


def test_sin_llave_no_entra(celular):
    assert _enviar(celular, _escaneo(), llave="otra").status_code == 401
    assert _enviar(celular, _escaneo(), llave="").status_code == 401


def test_escaneo_llega_a_la_pantalla_una_sola_vez(compu, celular):
    datos = _escaneo(codigo="036000291452", formato="upc_a")
    with compu.websocket_connect("/ws/pantalla") as ws:
        r = _enviar(celular, datos)
        assert r.status_code == 200
        assert r.json() == {"id": datos["id"], "codigo": "0036000291452", "duplicado": False, "pantallas": 1}
        mensaje = ws.receive_json()
        assert mensaje["tipo"] == "escaneo" and mensaje["codigo"] == "0036000291452"
        assert mensaje["t_recibido"] >= mensaje["t_detectado"] - 1000

        repetido = _enviar(celular, datos)  # el celular reintenta el mismo envío
        assert repetido.json()["duplicado"] is True
        _enviar(celular, _escaneo(id="otro-id-000001"))
        assert ws.receive_json()["id"] == "otro-id-000001"  # el repetido nunca se mandó


def test_lectura_mala_se_rechaza(celular):
    r = _enviar(celular, _escaneo(codigo="7501055363057"))
    assert r.status_code == 422
    assert "verificador" in r.json()["detail"]


def test_datos_mal_formados(celular):
    assert _enviar(celular, _escaneo(id="corto")).status_code == 422
    assert _enviar(celular, _escaneo(id="tiene espacios 123")).status_code == 422


def test_pantalla_remota_rechazada(celular):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with celular.websocket_connect("/ws/pantalla") as ws:
            ws.receive_json()


def test_sin_cache(celular):
    assert celular.get("/celular").headers["cache-control"] == "no-store"
