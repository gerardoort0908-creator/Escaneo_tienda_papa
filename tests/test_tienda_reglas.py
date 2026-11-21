"""Revisa reglas de toda la tienda: módulos independientes, registros y respaldos."""

import logging
import re
from datetime import date
from pathlib import Path

import tienda
from tienda.nucleo import registro, respaldos
from tienda.nucleo.esquema import DUENOS

CARPETA = Path(tienda.__file__).parent
_ESCRITURA = re.compile(r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(\w+)", re.IGNORECASE)


def test_cada_modulo_escribe_solo_en_sus_tablas():
    for modulo, propias in DUENOS.items():
        codigo = (CARPETA / f"{modulo}.py").read_text(encoding="utf-8")
        tocadas = set(_ESCRITURA.findall(codigo))
        assert tocadas <= propias, f"{modulo} escribe en tablas ajenas: {tocadas - propias}"


def test_toda_tabla_tiene_dueno(bd):
    with bd.lectura() as con:
        tablas = {f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    con_dueno = set().union(*DUENOS.values())
    assert tablas == con_dueno


def test_abrir_prepara_todo(tmp_path):
    bd = tienda.abrir(tmp_path)
    assert bd.version >= 1
    assert respaldos.listar(tmp_path / "respaldos")
    registro.obtener("ventas").info("hola")
    assert "hola" in (tmp_path / "registros" / "ventas.log").read_text(encoding="utf-8")
    assert not (tmp_path / "registros" / "fiado.log").read_text(encoding="utf-8")
    bd.cerrar()


def test_respaldo_mensual_una_vez_por_mes(tmp_path, bd, surtido):
    carpeta = tmp_path / "respaldos"
    primero = respaldos.respaldo_mensual(bd, carpeta, date(2026, 11, 3))
    assert primero.name == "tienda-2026-11.sqlite" and respaldos.copia_sana(primero)
    assert respaldos.respaldo_mensual(bd, carpeta, date(2026, 11, 30)) is None
    assert respaldos.respaldo_mensual(bd, carpeta, date(2026, 12, 1)).name == "tienda-2026-12.sqlite"
    assert len(respaldos.listar(carpeta)) == 2
    assert not list(carpeta.glob(".*"))  # no quedan temporales


def test_respaldo_trae_los_datos(tmp_path, bd, surtido):
    from tienda.nucleo.base_datos import BaseDatos
    from tienda import productos
    copia = BaseDatos(respaldos.respaldar(bd, tmp_path, "prueba"))
    assert productos.obtener(copia, surtido["coca"]).existencia == 24
    copia.cerrar()


def test_copia_danada_se_detecta(tmp_path):
    mala = tmp_path / "mala.sqlite"
    mala.write_bytes(b"esto no es una base de datos" * 100)
    assert not respaldos.copia_sana(mala)


def test_registros_no_se_duplican(tmp_path):
    registro.configurar(tmp_path)
    registro.configurar(tmp_path)
    assert len(logging.getLogger("tienda.ventas").handlers) == 1


def test_respaldo_diario_guarda_los_ultimos_30(tmp_path, bd, surtido):
    from datetime import timedelta
    carpeta = tmp_path / "respaldos"
    inicio = date(2026, 11, 1)
    for dia in range(35):
        respaldos.respaldos_al_dia(bd, carpeta, inicio + timedelta(days=dia))
    diarios = respaldos.listar(carpeta / "diarios")
    assert len(diarios) == 30
    assert diarios[0].name == "tienda-2026-11-06.sqlite" and diarios[-1].name == "tienda-2026-12-05.sqlite"
    assert [m.name for m in respaldos.listar(carpeta)] == ["tienda-2026-11.sqlite", "tienda-2026-12.sqlite"]
    assert respaldos.respaldo_diario(bd, carpeta, date(2026, 12, 5)) is None


def test_abrir_hace_respaldo_diario(tmp_path):
    bd = tienda.abrir(tmp_path)
    assert len(respaldos.listar(tmp_path / "respaldos" / "diarios")) == 1
    bd.cerrar()
