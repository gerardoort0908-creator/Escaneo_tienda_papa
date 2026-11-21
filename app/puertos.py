"""Antes de arrancar: revisar que las puertas (8000 y 8443) estén libres.

Si las ocupa una copia anterior de este mismo programa (por ejemplo, una que
quedó abierta escondida), se apaga sola. Si las ocupa otro programa, no se toca:
solo se explica qué pasa.
"""

from __future__ import annotations

import os
import re
import signal
import socket
import subprocess
import sys
import time

NUESTRO = "iniciar.py"


def libre(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # igual que el servidor
        try:
            s.bind(("0.0.0.0", puerto))
        except OSError:
            return False
    return True


def _salida(comando: list[str]) -> str:
    try:
        return subprocess.run(comando, capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def quien_usa(puerto: int) -> list[int]:
    """Los programas (pid) que escuchan en ese puerto."""
    if sys.platform == "win32":
        pids = set()
        for linea in _salida(["netstat", "-ano", "-p", "tcp"]).splitlines():
            partes = linea.split()
            if len(partes) >= 5 and partes[3].upper() in ("LISTENING", "ESCUCHANDO") \
                    and re.search(rf"[:.]{puerto}$", partes[1]):
                pids.add(int(partes[4]))
        return sorted(pids)
    return sorted({int(p) for p in _salida(["lsof", "-nP", f"-iTCP:{puerto}", "-sTCP:LISTEN", "-t"]).split() if p.isdigit()})


def linea_de_comando(pid: int) -> str:
    if sys.platform == "win32":
        return _salida(["powershell", "-NoProfile", "-Command",
                        f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"])
    return _salida(["ps", "-o", "command=", "-p", str(pid)])


def _apagar(pid: int) -> None:
    if sys.platform == "win32":
        _salida(["taskkill", "/PID", str(pid), "/F"])
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def liberar(puertos: list[int], *, espera_s: float = 5.0) -> str | None:
    """Deja libres los puertos. Devuelve None si quedaron libres, o la explicación si no."""
    ocupados = [p for p in puertos if not libre(p)]
    if not ocupados:
        return None
    ajenos, vistos = [], {os.getpid()}
    for puerto in ocupados:
        for pid in quien_usa(puerto):
            if pid in vistos:
                continue
            vistos.add(pid)
            if NUESTRO in linea_de_comando(pid):
                print(f"  Había otra copia del programa abierta (proceso {pid}). La cierro...")
                _apagar(pid)
            else:
                ajenos.append(pid)
    limite = time.monotonic() + espera_s
    while time.monotonic() < limite and not all(libre(p) for p in ocupados):
        time.sleep(0.2)
    if all(libre(p) for p in ocupados):
        return None
    lista = ", ".join(str(p) for p in ocupados)
    if ajenos:
        return (f"Otro programa está usando la puerta {lista} de esta computadora. "
                "Ciérralo o reinicia la computadora y vuelve a intentar.")
    return f"La puerta {lista} sigue ocupada. Reinicia la computadora y vuelve a intentar."
