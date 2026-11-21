#!/bin/bash
# Doble clic para arrancar el programa de la tienda en una Mac.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Falta Python. Instálalo desde https://www.python.org/downloads/ y vuelve a abrir este archivo."
  read -r -p "Presiona Enter para cerrar..."; exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "Preparando por primera vez (tarda un minuto)..."
  python3 -m venv .venv && .venv/bin/python -m pip install -q --upgrade pip && .venv/bin/python -m pip install -q -r requirements.txt || {
    echo "No se pudo preparar. Revisa tu internet y vuelve a intentar."; rm -rf .venv
    read -r -p "Presiona Enter para cerrar..."; exit 1; }
fi
.venv/bin/python iniciar.py "$@"
