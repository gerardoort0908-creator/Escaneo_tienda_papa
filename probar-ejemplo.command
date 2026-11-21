#!/bin/bash
# Doble clic: abre la tienda con productos de EJEMPLO (se guardan aparte, en datos/ejemplo).
cd "$(dirname "$0")" || exit 1
exec ./iniciar.command --ejemplo
