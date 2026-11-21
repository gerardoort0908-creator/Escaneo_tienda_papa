"""Arranca la prueba del escáner.

Abre dos puertas en esta computadora:
- http://localhost:8000/pantalla  → la pantalla que ve el papá (solo desde esta compu).
- https://<ip>:8443/celular       → el escáner del celular (https para que abra la cámara).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import secrets
import sys
import threading
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from app.certificados import preparar_certificados
from app.main import Configuracion, crear_app
from app.red import ip_en_la_red

CARPETA = Path(__file__).resolve().parent
DATOS = CARPETA / "datos"


def leer_o_crear_llave(ruta: Path) -> str:
    """La llave que autoriza a los celulares; se guarda para que el QR siga sirviendo."""
    if ruta.exists():
        llave = ruta.read_text(encoding="utf-8").strip()
        if len(llave) >= 16:
            return llave
    llave = secrets.token_urlsafe(18)
    ruta.write_text(llave, encoding="utf-8")
    return llave


def configurar_registro() -> None:
    DATOS.mkdir(exist_ok=True)
    archivo = RotatingFileHandler(DATOS / "escaner.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    archivo.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    registro = logging.getLogger("escaner")
    registro.setLevel(logging.INFO)
    registro.addHandler(archivo)


async def servir(config: Configuracion) -> None:
    app = crear_app(config)
    assert config.certificados is not None
    http = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=config.puerto_http, log_level="warning",
                                       timeout_keep_alive=120))
    https = uvicorn.Server(
        uvicorn.Config(
            app, host="0.0.0.0", port=config.puerto_https, log_level="warning",
            timeout_keep_alive=120,  # el celular reusa la conexión segura: no repite el saludo TLS
            ssl_certfile=str(config.certificados.servidor),
            ssl_keyfile=str(config.certificados.servidor_llave),
        )
    )
    await asyncio.gather(http.serve(), https.serve())


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba del escáner con celular")
    parser.add_argument("--ip", help="Usar esta IP en lugar de detectarla")
    parser.add_argument("--sin-navegador", action="store_true", help="No abrir la pantalla al arrancar")
    args = parser.parse_args()

    configurar_registro()
    ip = args.ip or ip_en_la_red()
    config = Configuracion(
        ip=ip,
        llave=leer_o_crear_llave(DATOS / "llave.txt"),
        certificados=preparar_certificados(DATOS / "certificados", ip),
    )
    print()
    print("  Prueba del escáner funcionando.")
    print(f"  Pantalla de la computadora: http://localhost:{config.puerto_http}/pantalla")
    print(f"  Dirección para el celular:  https://{ip}:{config.puerto_https}/celular")
    if ip == "127.0.0.1":
        print("  OJO: esta computadora no parece estar en un WiFi; el celular no la va a encontrar.")
    print("  Para apagarlo cierra esta ventana o presiona Ctrl+C.")
    print()
    if not args.sin_navegador:
        threading.Timer(1.5, webbrowser.open, args=(f"http://localhost:{config.puerto_http}/pantalla",)).start()
    try:
        asyncio.run(servir(config))
    except KeyboardInterrupt:
        pass
    except OSError as error:
        print(f"\n  No se pudo arrancar: {error}\n  ¿Ya hay otra ventana del programa abierta?")
        sys.exit(1)


if __name__ == "__main__":
    main()
