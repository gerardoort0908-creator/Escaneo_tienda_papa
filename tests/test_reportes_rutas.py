"""Pantalla de Reportes: cuentas del periodo y archivo de Excel."""

import io
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import Configuracion, crear_app
from tienda import fiado, ventas
from tienda import productos as P

LLAVE = "llave-de-prueba-1234567890"
HOY = date.today().isoformat()


@pytest.fixture
def compu(bd, surtido):
    app = crear_app(Configuracion(ip="192.168.1.50", llave=LLAVE, certificados=None), bd)
    return TestClient(app, client=("127.0.0.1", 50000))


@pytest.fixture
def dia_con_ventas(bd, surtido):
    """3 Cocas en efectivo, 1 kg de huevo prestado a Lupe que abona $20, y una venta cancelada."""
    ventas.cobrar_efectivo(bd, [ventas.Pedido(surtido["coca"], 3)], 10000)
    lupe = fiado.crear_cliente(bd, "Lupe")
    ventas.vender_fiado(bd, [ventas.Pedido(surtido["huevo"], 1000)], lupe)
    fiado.abonar(bd, lupe, 2000)
    cancelada = ventas.cobrar_efectivo(bd, [ventas.Pedido(surtido["coca"], 1)], 2200).venta_id
    ventas.cancelar(bd, cancelada, "prueba")
    return lupe


def test_pagina_solo_en_la_compu(compu, bd):
    assert "Reportes" in compu.get("/reportes").text
    celular = TestClient(crear_app(Configuracion(ip="192.168.1.50", llave=LLAVE, certificados=None), bd),
                         client=("192.168.1.77", 50000))
    assert celular.get("/reportes").status_code == 403
    assert celular.get("/api/reportes", params={"desde": HOY, "hasta": HOY}).status_code == 403


def test_reporte_de_hoy(compu, dia_con_ventas, surtido):
    d = compu.get("/api/reportes", params={"desde": HOY, "hasta": HOY}).json()
    r = d["resumen"]
    assert (r["vendido"], r["ventas"], r["efectivo"], r["prestado"]) == (6600 + 4500, 2, 6600, 4500)
    assert r["costo"] == 3 * 1550 + 3820 and r["ganancia"] == r["vendido"] - r["costo"]
    assert (r["pagos_de_prestamos"], r["canceladas"]) == (2000, 1)
    assert d["grafica"]["por"] == "hora" and len(d["grafica"]["puntos"]) == 24
    assert sum(p["vendido"] for p in d["grafica"]["puntos"]) == 11100
    assert [x["nombre"] for x in d["mas_vendidos"]] == ["Coca-Cola 600 ml", "Huevo blanco"]
    assert d["prestamos"] == {"deben": 2500, "personas": 1, "deudores": [{"nombre": "Lupe", "saldo": 2500}]}


def test_cada_venta_con_lo_que_se_llevo(compu, dia_con_ventas, bd, surtido):
    origen = [ventas.DelCelular(surtido["coca"], 2, 2200)]
    ventas.de_celular(bd, "venta-celular-777", "iPhone-ab12", f"{HOY} 00:00:01", origen, 5000)
    lista = compu.get("/api/reportes", params={"desde": HOY, "hasta": HOY}).json()["lista_ventas"]
    assert [v["celular"] for v in lista] == ["iPhone-ab12", None, None, None]
    assert [(v["forma_pago"], v["estado"], v["cliente"]) for v in lista[1:]] == [
        ("efectivo", "hecha", None), ("fiado", "hecha", "Lupe"), ("efectivo", "cancelada", None)]
    assert lista[3]["motivo"] == "prueba"
    assert lista[1]["renglones"] == [{"nombre": "Coca-Cola 600 ml", "unidad": "pieza", "cantidad": 3, "subtotal": 6600}]
    assert lista[2]["renglones"][0]["unidad"] == "kg" and lista[2]["renglones"][0]["cantidad"] == 1000


def test_varios_dias_trae_cada_dia_aunque_no_haya_ventas(compu, dia_con_ventas):
    desde = (date.today() - timedelta(days=6)).isoformat()
    d = compu.get("/api/reportes", params={"desde": desde, "hasta": HOY}).json()
    puntos = d["grafica"]["puntos"]
    assert d["grafica"]["por"] == "dia" and len(puntos) == 7
    assert puntos[-1]["vendido"] == 11100 and puntos[0]["vendido"] == 0
    assert d["anterior"]["vendido"] == 0


def test_faltantes_y_sin_moverse(compu, bd, surtido):
    P.ajustar_conteo(bd, surtido["coca"], 0, "conteo")
    d = compu.get("/api/reportes", params={"desde": HOY, "hasta": HOY}).json()
    assert [(x["nombre"], x["nivel"]) for x in d["faltantes"]] == [("Coca-Cola 600 ml", "acabado")]
    # el huevo no se vendió hoy: 22.5 kg a $38.20 = $859.50 parados
    assert d["sin_moverse"] == [{"id": surtido["huevo"], "nombre": "Huevo blanco", "unidad": "kg",
                                 "existencia": 22_500, "parado": 85950}]


def test_fechas_malas(compu):
    assert compu.get("/api/reportes", params={"desde": "ayer", "hasta": HOY}).status_code == 422
    r = compu.get("/api/reportes", params={"desde": "2020-01-01", "hasta": HOY})
    assert r.status_code == 422 and "año" in r.json()["detail"]
    # al revés también sirve: se acomodan solas
    hace3 = (date.today() - timedelta(days=3)).isoformat()
    d = compu.get("/api/reportes", params={"desde": HOY, "hasta": hace3}).json()
    assert (d["desde"], d["hasta"]) == (hace3, HOY)


def test_excel(compu, dia_con_ventas):
    from openpyxl import load_workbook

    r = compu.get("/api/reportes/excel", params={"desde": HOY, "hasta": HOY})
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    libro = load_workbook(io.BytesIO(r.content))
    assert libro.sheetnames == ["Resumen", "Por hora", "Más vendidos", "Ventas", "Por acabarse", "Préstamos"]
    resumen = {f[0]: f[1] for f in libro["Resumen"].iter_rows(min_row=4, values_only=True)}
    assert resumen["Vendiste"] == 111 and resumen["Se prestó"] == 45 and resumen["Te deben hoy (todos)"] == 25
    filas = list(libro["Ventas"].iter_rows(min_row=2, values_only=True))
    assert [(f[2], f[3], f[4], f[5]) for f in filas] == [("Efectivo", None, "Coca-Cola 600 ml", 3),
                                                       ("Préstamo", "Lupe", "Huevo blanco", 1)]
