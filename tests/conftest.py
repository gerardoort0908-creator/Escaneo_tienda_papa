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
