"""La pantalla de Vender: rutas del servidor de punta a punta, con una base en memoria."""

import pytest
from fastapi.testclient import TestClient

from app import ejemplo
from app.main import Configuracion, crear_app
from app.vender import Celular
from tienda import productos as P
from tienda import ventas

LLAVE = "llave-de-prueba-1234567890"


@pytest.fixture
def tienda_app(bd, surtido):
    P.editar(bd, surtido["coca"], codigo="7501055300075")
    return crear_app(Configuracion(ip="192.168.1.50", llave=LLAVE, certificados=None), bd)


@pytest.fixture
def compu(tienda_app):
    return TestClient(tienda_app, client=("127.0.0.1", 50000))


@pytest.fixture
def celular(tienda_app):
    return TestClient(tienda_app, client=("192.168.1.77", 50000))


def cobro(renglones, recibido, total, operacion="operacion-0001"):
    return {"operacion": operacion, "renglones": renglones, "recibido": recibido, "total_visto": total}


# ---------------------------------------------------------------- páginas y permisos

def test_la_compu_abre_vender(compu):
    assert compu.get("/", follow_redirects=False).headers["location"] == "/vender"
    r = compu.get("/vender")
    assert r.status_code == 200 and "Escanea un producto" in r.text


def test_el_celular_no_puede_vender_ni_ver_productos(celular, surtido):
    assert celular.get("/vender").status_code == 403
    assert celular.get("/api/productos").status_code == 403
    assert celular.post("/api/ventas/cobrar", json=cobro([{"producto_id": surtido["coca"], "cantidad": 1}], 2200, 2200)).status_code == 403
    assert celular.post("/api/ventas/1/cancelar", json={"motivo": "x"}).status_code == 403


def test_sin_base_de_datos_queda_solo_la_prueba_del_escaner():
    app = crear_app(Configuracion(ip="192.168.1.50", llave=LLAVE, certificados=None))
    compu = TestClient(app, client=("127.0.0.1", 50000))
    assert compu.get("/", follow_redirects=False).headers["location"] == "/pantalla"
    assert compu.get("/vender").status_code == 404


# ---------------------------------------------------------------- buscar

def test_buscar_por_nombre(compu):
    r = compu.get("/api/productos", params={"q": "coca"}).json()
    assert [p["nombre"] for p in r] == ["Coca-Cola 600 ml"]
    assert r[0] == {"id": r[0]["id"], "codigo": "7501055300075", "nombre": "Coca-Cola 600 ml",
                    "unidad": "pieza", "precio": 2200, "existencia": 24,
                    "costo": 1550, "minimo": 6, "activo": True}


def test_buscar_por_codigo(compu):
    assert compu.get("/api/productos/codigo/7501055300075").json()["nombre"] == "Coca-Cola 600 ml"
    r = compu.get("/api/productos/codigo/7500000000008")
    assert r.status_code == 404 and r.json()["detail"] == "Ese código no está registrado"


# ---------------------------------------------------------------- cobrar

def test_cobrar_guarda_la_venta_y_da_el_cambio(compu, bd, surtido):
    renglones = [{"producto_id": surtido["coca"], "cantidad": 2}, {"producto_id": surtido["huevo"], "cantidad": 500}]
    # 2 × $22 + ½ kg de huevo a $45 ($22.50 → $23) = $67
    r = compu.post("/api/ventas/cobrar", json=cobro(renglones, 10000, 6700))
    assert r.status_code == 200
    recibo = r.json()
    assert recibo["total"] == 6700 and recibo["cambio"] == 3300
    assert P.obtener(bd, surtido["coca"]).existencia == 22
    assert P.obtener(bd, surtido["huevo"]).existencia == 22_000
    assert ventas.obtener(bd, recibo["venta_id"])["estado"] == "hecha"


def test_un_reintento_no_cobra_dos_veces(compu, bd, surtido):
    datos = cobro([{"producto_id": surtido["coca"], "cantidad": 1}], 2200, 2200, "doble-enter-123")
    primero = compu.post("/api/ventas/cobrar", json=datos).json()
    segundo = compu.post("/api/ventas/cobrar", json=datos).json()
    assert primero == segundo
    assert P.obtener(bd, surtido["coca"]).existencia == 23


def test_si_el_precio_cambio_no_cobra(compu, bd, surtido):
    P.editar(bd, surtido["coca"], precio_venta=2400)
    r = compu.post("/api/ventas/cobrar", json=cobro([{"producto_id": surtido["coca"], "cantidad": 1}], 5000, 2200))
    assert r.status_code == 422 and "$24" in r.json()["detail"]
    assert P.obtener(bd, surtido["coca"]).existencia == 24


def test_si_no_alcanza_dice_cuanto_falta(compu, surtido):
    r = compu.post("/api/ventas/cobrar", json=cobro([{"producto_id": surtido["coca"], "cantidad": 2}], 4000, 4400))
    assert r.status_code == 422 and r.json()["detail"] == "Faltan $4"


def test_huevo_solo_de_medio_kilo_en_medio_kilo(compu, surtido):
    r = compu.post("/api/ventas/cobrar", json=cobro([{"producto_id": surtido["huevo"], "cantidad": 700}], 5000, 3200))
    assert r.status_code == 422


def test_cancelar_la_venta_regresa_la_mercancia(compu, bd, surtido):
    recibo = compu.post("/api/ventas/cobrar", json=cobro([{"producto_id": surtido["coca"], "cantidad": 3}], 10000, 6600)).json()
    r = compu.post(f"/api/ventas/{recibo['venta_id']}/cancelar", json={"motivo": "Me equivoqué al cobrar"})
    assert r.status_code == 200
    assert P.obtener(bd, surtido["coca"]).existencia == 24
    assert ventas.obtener(bd, recibo["venta_id"])["estado"] == "cancelada"
    otra = compu.post(f"/api/ventas/{recibo['venta_id']}/cancelar", json={"motivo": "otra vez"})
    assert otra.status_code == 422 and "ya estaba cancelada" in otra.json()["detail"]
    assert compu.post("/api/ventas/999/cancelar", json={"motivo": "x"}).status_code == 404


# ---------------------------------------------------------------- escáner → pantalla

def test_el_escaneo_llega_a_la_pantalla_con_el_producto(compu, celular):
    with compu.websocket_connect("/ws/pantalla") as ws:
        r = celular.post("/api/escaneo", headers={"x-llave": LLAVE},
                         json={"id": "esc-00000001", "codigo": "7501055300075", "formato": "ean_13", "t_detectado": 0})
        assert r.status_code == 200
        mensaje = ws.receive_json()
        assert mensaje["producto"]["nombre"] == "Coca-Cola 600 ml"
        assert mensaje["producto"]["precio"] == 2200

        r = celular.post("/api/escaneo", headers={"x-llave": LLAVE},
                         json={"id": "esc-00000002", "codigo": "7500000000008", "formato": "ean_13", "t_detectado": 0})
        assert r.status_code == 200
        mensaje = ws.receive_json()
        assert mensaje["codigo"] == "7500000000008" and mensaje["producto"] is None


def test_la_pantalla_sabe_si_el_celular_esta_conectado(compu, celular):
    assert compu.get("/api/vender/estado").json() == {"celular": False, "ejemplo": False}
    celular.get("/api/hora")
    assert compu.get("/api/vender/estado").json()["celular"] is True


def test_el_celular_se_da_por_desconectado_si_calla():
    ahora = [100.0]
    cel = Celular(reloj=lambda: ahora[0])
    assert not cel.conectado
    cel.saludo()
    ahora[0] += 5
    assert cel.conectado
    ahora[0] += 2
    assert not cel.conectado


# ---------------------------------------------------------------- modo de práctica

def test_los_ejemplos_se_cargan_una_sola_vez(bd):
    assert ejemplo.cargar(bd) == len(ejemplo.PRODUCTOS)
    assert ejemplo.cargar(bd) == 0
    huevo = P.buscar(bd, "huevo")[0]
    assert huevo.unidad == "kg" and huevo.existencia == 22_500


def test_los_ejemplos_traen_semanas_de_ventas_una_sola_vez(bd):
    from datetime import date, timedelta

    from tienda import reportes

    ejemplo.cargar(bd)
    dias = reportes.por_dia(bd, date.today() - timedelta(days=21), date.today() - timedelta(days=1))
    assert len(dias) == 21 and all(d["ventas"] > 0 for d in dias)
    contar = lambda: sum(d["ventas"] for d in reportes.por_dia(bd, date.today() - timedelta(days=21), date.today()))
    antes = contar()
    ejemplo.cargar(bd)
    assert contar() == antes


def test_los_ejemplos_traen_clientes_con_fiado(bd):
    from tienda import fiado

    ejemplo.cargar(bd)
    ejemplo.cargar(bd)
    assert len(fiado.buscar(bd)) == 4
    deben = {c.nombre: c.saldo for c in fiado.deudores(bd)}
    assert deben == {"Doña Lupe": 2 * 2900 + 5200 + 4500 - 5000, "Don Beto (el de la esquina)": 3 * 2200 + 2 * 1900,
                     "Mari": 3800}
