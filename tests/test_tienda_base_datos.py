import sqlite3

import pytest

from tienda.nucleo.base_datos import BaseDatos, _sentencias
from tienda.nucleo.esquema import MIGRACIONES


def _cuantos(bd):
    with bd.lectura() as con:
        return con.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]


def _cliente(con, nombre):
    con.execute("INSERT INTO clientes (nombre, creado) VALUES (?, '2026-11-21 10:00:00')", (nombre,))


def test_version_al_dia(bd):
    assert bd.version == len(MIGRACIONES)
    bd.migrar()  # repetir no hace nada
    assert bd.version == len(MIGRACIONES)


def test_todo_o_nada(bd):
    with pytest.raises(RuntimeError):
        with bd.transaccion() as con:
            _cliente(con, "Ana")
            raise RuntimeError("se fue la luz")
    assert _cuantos(bd) == 0


def test_transaccion_anidada_falla_y_se_deshace_todo(bd):
    with pytest.raises(RuntimeError):
        with bd.transaccion() as con:
            _cliente(con, "Ana")
            with bd.transaccion() as con2:
                _cliente(con2, "Beto")
            raise RuntimeError
    assert _cuantos(bd) == 0


def test_anidada_que_falla_se_puede_atrapar(bd):
    with bd.transaccion() as con:
        _cliente(con, "Ana")
        with pytest.raises(RuntimeError):
            with bd.transaccion() as con2:
                _cliente(con2, "Beto")
                raise RuntimeError
    assert _cuantos(bd) == 1


def test_lo_guardado_sobrevive_a_cerrar(tmp_path):
    ruta = tmp_path / "t.sqlite"
    bd = BaseDatos(ruta)
    bd.migrar()
    with bd.transaccion() as con:
        _cliente(con, "Ana")
    bd.cerrar()
    otra = BaseDatos(ruta)
    assert _cuantos(otra) == 1
    otra.cerrar()


@pytest.mark.parametrize("sql", [
    "DELETE FROM ventas",
    "DELETE FROM productos",
    "DELETE FROM clientes",
    "DELETE FROM movimientos_inventario",
    "UPDATE movimientos_inventario SET cantidad = 99",
    "DELETE FROM fiado_movimientos",
    "UPDATE fiado_movimientos SET monto = 1",
    "UPDATE venta_lineas SET subtotal = 1",
    "DELETE FROM cortes",
])
def test_la_base_no_deja_borrar_ni_alterar_historia(bd, surtido, sql):
    from tienda import fiado, ventas, caja
    cliente = fiado.crear_cliente(bd, "Ana")
    ventas.vender_fiado(bd, [ventas.Pedido(surtido["coca"], 1)], cliente)
    caja.abrir(bd, 0)
    caja.cerrar(bd, 0)
    with pytest.raises(sqlite3.IntegrityError):
        with bd.transaccion() as con:
            con.execute(sql)


def test_venta_no_se_puede_maquillar(bd, surtido):
    from tienda import ventas
    recibo = ventas.cobrar_efectivo(bd, [ventas.Pedido(surtido["coca"], 1)], 5000)
    with pytest.raises(sqlite3.IntegrityError):
        with bd.transaccion() as con:
            con.execute("UPDATE ventas SET total = 100 WHERE id = ?", (recibo.venta_id,))


def test_base_rechaza_precio_con_centavos_aunque_se_salten_las_reglas(bd):
    with pytest.raises(sqlite3.IntegrityError):
        with bd.transaccion() as con:
            con.execute("INSERT INTO productos (nombre, unidad, precio_venta, creado, actualizado)"
                        " VALUES ('x', 'pieza', 2250, 'a', 'a')")


def test_separa_sentencias_con_triggers():
    partes = _sentencias("CREATE TABLE a (x);\nCREATE TRIGGER t BEFORE DELETE ON a BEGIN SELECT 1; END;\n")
    assert len(partes) == 2
