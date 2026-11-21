"""Arranque: si una copia vieja del programa ocupa las puertas, se cierra sola; si es otro programa, no se toca."""

import socket
import subprocess
import sys

from app import puertos


def _puerto_ocupado():
    s = socket.socket()
    s.bind(("0.0.0.0", 0))
    s.listen()
    return s, s.getsockname()[1]


def test_puerto_libre_no_hace_nada():
    s = socket.socket()
    s.bind(("0.0.0.0", 0))
    puerto = s.getsockname()[1]
    s.close()
    assert puertos.liberar([puerto]) is None


def test_otro_programa_no_se_toca(monkeypatch):
    s, puerto = _puerto_ocupado()
    try:
        apagados = []
        monkeypatch.setattr(puertos, "quien_usa", lambda p: [999999])
        monkeypatch.setattr(puertos, "linea_de_comando", lambda pid: "/usr/bin/otro-programa")
        monkeypatch.setattr(puertos, "_apagar", apagados.append)
        mensaje = puertos.liberar([puerto], espera_s=0.2)
        assert "Otro programa" in mensaje and apagados == []
    finally:
        s.close()


def test_copia_vieja_del_programa_se_cierra():
    codigo = "import socket,time; s=socket.socket(); s.bind(('0.0.0.0',0)); s.listen(); print(s.getsockname()[1],flush=True); time.sleep(60)"
    viejo = subprocess.Popen([sys.executable, "-c", codigo, "iniciar.py"], stdout=subprocess.PIPE, text=True)
    try:
        puerto = int(viejo.stdout.readline())
        if not puertos.quien_usa(puerto):  # sin lsof/netstat en esta máquina
            return
        assert puertos.liberar([puerto]) is None
        assert viejo.wait(timeout=5) is not None
    finally:
        viejo.kill()
