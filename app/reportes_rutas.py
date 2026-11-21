"""Rutas de la pantalla de Reportes: cuentas del periodo, gráficas y el archivo de Excel."""

from __future__ import annotations

import io
from collections.abc import Callable
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from tienda import fiado, reportes
from tienda import productos as P
from tienda.nucleo.base_datos import BaseDatos
from tienda.nucleo.errores import DatoInvalido

from .inventario import nivel

MAX_DIAS = 400  # poco más de un año por reporte


def _fechas(desde: str, hasta: str) -> tuple[date, date]:
    try:
        d, h = date.fromisoformat(desde), date.fromisoformat(hasta)
    except ValueError:
        raise DatoInvalido("Fecha no válida") from None
    if h < d:
        d, h = h, d
    if (h - d).days > MAX_DIAS:
        raise DatoInvalido("El periodo es muy largo; elige un año o menos")
    return d, h


def _faltantes(bd: BaseDatos) -> list[dict]:
    lista = []
    for p in P.buscar(bd, limite=100_000):
        n = nivel(p)
        if n != "bien":
            lista.append({"id": p.id, "nombre": p.nombre, "unidad": p.unidad, "existencia": p.existencia,
                          "minimo": p.minimo, "nivel": n, "costo": p.costo_promedio})
    lista.sort(key=lambda x: (x["nivel"] != "acabado", x["existencia"] - x["minimo"]))
    return lista


def _sin_moverse(bd: BaseDatos, vendidos: set[int]) -> list[dict]:
    """Lo que hay en existencia y no se vendió nada en el periodo, empezando por lo que más dinero tiene parado."""
    lista = []
    for p in P.buscar(bd, limite=100_000):
        if p.id in vendidos or p.existencia <= 0:
            continue
        parado = p.costo_promedio * p.existencia // (1000 if p.unidad == "kg" else 1)
        lista.append({"id": p.id, "nombre": p.nombre, "unidad": p.unidad, "existencia": p.existencia, "parado": parado})
    lista.sort(key=lambda x: -x["parado"])
    return lista[:8]


def armar(bd: BaseDatos, d: date, h: date) -> dict:
    g = reportes.ganancia(bd, d, h)
    todos = reportes.mas_vendidos(bd, d, h, cuantos=100_000)
    deudores = fiado.deudores(bd)
    un_dia = d == h
    # Para comparar: el periodo anterior del mismo largo
    largo = (h - d).days + 1
    antes = reportes.ganancia(bd, d - timedelta(days=largo), d - timedelta(days=1))
    return {
        "desde": d.isoformat(), "hasta": h.isoformat(),
        "resumen": {"vendido": g.ventas, "costo": g.costo, "ganancia": g.ganancia, "ventas": g.numero_ventas,
                    **reportes.formas_de_pago(bd, d, h)},
        "anterior": {"vendido": antes.ventas, "ganancia": antes.ganancia, "ventas": antes.numero_ventas},
        "grafica": {"por": "hora", "puntos": reportes.por_hora(bd, d)} if un_dia
                   else {"por": "dia", "puntos": reportes.por_dia(bd, d, h)},
        "mas_vendidos": todos[:10],
        "mas_ganancia": sorted(todos, key=lambda x: -x["ganancia"])[:10],
        "faltantes": _faltantes(bd),
        "sin_moverse": _sin_moverse(bd, {x["producto_id"] for x in todos}),
        "prestamos": {"deben": sum(c.saldo for c in deudores), "personas": len(deudores),
                      "deudores": [{"nombre": c.nombre, "saldo": c.saldo} for c in deudores[:6]]},
        "cortes": reportes.cortes_entre(bd, d, h),
    }


def excel(bd: BaseDatos, d: date, h: date) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    datos = armar(bd, d, h)
    libro = Workbook()
    pesos = '"$"#,##0.00'
    titulo = Font(bold=True, size=14)
    negrita = Font(bold=True, color="FFFFFF")
    fondo = PatternFill("solid", fgColor="3A3530")

    def hoja(nombre: str, encabezados: list[str], filas: list[list], dinero: set[int] = frozenset(),
             primera: bool = False):
        ws = libro.active if primera else libro.create_sheet()
        ws.title = nombre
        ws.append(encabezados)
        for c in ws[1]:
            c.font, c.fill, c.alignment = negrita, fondo, Alignment(horizontal="center")
        for f in filas:
            ws.append(f)
        for col in dinero:
            for celda in ws.iter_rows(min_row=2, min_col=col, max_col=col):
                celda[0].number_format = pesos
        for i, enc in enumerate(encabezados, 1):
            largo = max([len(str(enc))] + [len(str(f[i - 1])) for f in filas if i - 1 < len(f) and f[i - 1] is not None])
            ws.column_dimensions[get_column_letter(i)].width = min(48, largo + 3)
        ws.freeze_panes = "A2"
        return ws

    def cant(cantidad: int, unidad: str):
        return cantidad / 1000 if unidad == "kg" else cantidad

    r = datos["resumen"]
    ws = hoja("Resumen", ["Concepto", "Cantidad"], [
        ["Vendiste", r["vendido"] / 100], ["Te costó esa mercancía", r["costo"] / 100],
        ["Ganaste", r["ganancia"] / 100], ["Número de ventas", r["ventas"]],
        ["Cobrado en efectivo", r["efectivo"] / 100], ["Se prestó", r["prestado"] / 100],
        ["Te pagaron de préstamos", r["pagos_de_prestamos"] / 100], ["Ventas canceladas", r["canceladas"]],
        ["Te deben hoy (todos)", datos["prestamos"]["deben"] / 100],
    ], primera=True)
    for fila in (2, 3, 4, 6, 7, 8, 10):
        ws.cell(row=fila, column=2).number_format = pesos
    ws.insert_rows(1, 2)
    ws["A1"] = f"Reporte de la tienda · {d:%d/%m/%Y}" + ("" if d == h else f" al {h:%d/%m/%Y}")
    ws["A1"].font = titulo

    g = datos["grafica"]
    if g["por"] == "hora":
        hoja("Por hora", ["Hora", "Ventas", "Vendiste", "Ganaste"],
             [[f"{p['hora']}:00", p["ventas"], p["vendido"] / 100, p["ganancia"] / 100] for p in g["puntos"] if p["ventas"]],
             {3, 4})
    else:
        hoja("Por día", ["Día", "Ventas", "Vendiste", "Ganaste"],
             [[date.fromisoformat(p["dia"]).strftime("%d/%m/%Y"), p["ventas"], p["vendido"] / 100, p["ganancia"] / 100]
              for p in g["puntos"]], {3, 4})
    hoja("Más vendidos", ["Producto", "Cantidad", "Unidad", "Vendiste", "Ganaste"],
         [[x["nombre"], cant(x["cantidad"], x["unidad"]), "kg" if x["unidad"] == "kg" else "pzas",
           x["vendido"] / 100, x["ganancia"] / 100] for x in reportes.mas_vendidos(bd, d, h, cuantos=100_000)], {4, 5})
    hoja("Ventas", ["Venta", "Fecha y hora", "Forma de pago", "Cliente", "Producto", "Cantidad", "Unidad",
                    "Precio", "Subtotal", "Costo"],
         [[v["venta"], v["cuando"], "Préstamo" if v["forma_pago"] == "fiado" else "Efectivo", v["cliente"] or "",
           v["producto"], cant(v["cantidad"], v["unidad"]), "kg" if v["unidad"] == "kg" else "pza",
           v["precio_unitario"] / 100, v["subtotal"] / 100, v["costo"] / 100]
          for v in reportes.ventas_detalle(bd, d, h)], {8, 9, 10})
    hoja("Por acabarse", ["Producto", "Hay", "Mínimo", "Unidad", "Cómo va"],
         [[x["nombre"], cant(x["existencia"], x["unidad"]), cant(x["minimo"], x["unidad"]),
           "kg" if x["unidad"] == "kg" else "pzas", "Se acabó" if x["nivel"] == "acabado" else "Se está acabando"]
          for x in datos["faltantes"]])
    hoja("Préstamos", ["Cliente", "Debe"], [[c.nombre, c.saldo / 100] for c in fiado.deudores(bd)], {2})
    if datos["cortes"]:
        hoja("Cortes de caja", ["Abrió", "Cerró", "Fondo", "Debía haber", "Contó", "Diferencia", "Nota"],
             [[k["abierto"], k["cerrado"], k["fondo"] / 100, k["esperado"] / 100, k["contado"] / 100,
               k["diferencia"] / 100, k["nota"] or ""] for k in datos["cortes"]], {3, 4, 5, 6})
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def crear_rutas(bd: BaseDatos, exigir_local: Callable[[Request], None]) -> APIRouter:
    rutas = APIRouter(dependencies=[Depends(exigir_local)])

    @rutas.get("/api/reportes")
    def ver(desde: str, hasta: str):
        return armar(bd, *_fechas(desde, hasta))

    @rutas.get("/api/reportes/excel")
    def bajar(desde: str, hasta: str):
        d, h = _fechas(desde, hasta)
        nombre = f"reporte-tienda-{d:%Y-%m-%d}" + ("" if d == h else f"-al-{h:%Y-%m-%d}") + ".xlsx"
        return Response(excel(bd, d, h), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})

    return rutas
