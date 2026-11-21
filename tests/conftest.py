import pytest
from fastapi.testclient import TestClient

from app.main import Configuracion, crear_app

LLAVE = "llave-de-prueba-1234567890"


@pytest.fixture
def app():
    return crear_app(Configuracion(ip="192.168.1.50", llave=LLAVE, certificados=None))


@pytest.fixture
def compu(app):
    """Cliente que se conecta desde la misma computadora."""
    return TestClient(app, client=("127.0.0.1", 50000))


@pytest.fixture
def celular(app):
    """Cliente que se conecta desde otro aparato del WiFi."""
    return TestClient(app, client=("192.168.1.77", 50000))


# ---------------------------------------------------------------- la tienda

@pytest.fixture
def bd():
    """Base de datos de la tienda en memoria, recién creada."""
    from tienda.nucleo.base_datos import BaseDatos

    base = BaseDatos(":memory:")
    base.migrar()
    yield base
    base.cerrar()


@pytest.fixture
def surtido(bd):
    """Unos productos con existencia: Coca 600 ($22, costo $15.50) y Huevo ($45/kg, costo $38.20/kg)."""
    from tienda import productos as P

    coca = P.crear(bd, nombre="Coca-Cola 600 ml", precio_venta=2200, codigo="7501055300075", costo=1550, minimo=6)
    huevo = P.crear(bd, nombre="Huevo blanco", precio_venta=4500, unidad="kg", costo=3820, minimo=5000)
    P.registrar_llegada(bd, [P.Llegada(coca, 24, 1550), P.Llegada(huevo, 22_500, 3820)])
    return {"coca": coca, "huevo": huevo}
