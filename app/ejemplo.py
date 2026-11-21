"""Productos y clientes de ejemplo para probar sin tocar los datos reales.

Se usan solo con `iniciar --ejemplo`, que guarda todo en datos/ejemplo/.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from tienda import fiado, ventas
from tienda.nucleo import reloj
from tienda import productos as P
from tienda.nucleo.base_datos import BaseDatos

# nombre, precio de venta (pesos), costo (centavos), unidad, existencia, mínimo
PRODUCTOS = [
    ("Coca-Cola 600 ml", 22, 1550, "pieza", 24, 6),
    ("Sabritas Original 45 g", 19, 1330, "pieza", 5, 6),
    ("Leche Lala entera 1 L", 29, 2235, "pieza", 18, 6),
    ("Pan Bimbo grande", 52, 4100, "pieza", 3, 4),
    ("Jabón Zote rosa 400 g", 26, 1900, "pieza", 9, 3),
    ("Galletas Marías 170 g", 18, 1250, "pieza", 14, 4),
    ("Agua Ciel 1 L", 14, 820, "pieza", 30, 8),
    ("Atún Dolores en agua", 28, 2090, "pieza", 12, 4),
    ("Frijol negro 1 kg", 38, 2950, "pieza", 8, 3),
    ("Papel higiénico 4 rollos", 36, 2700, "pieza", 10, 3),
    ("Huevo blanco", 45, 3820, "kg", 22_500, 5_000),
    ("Tortilla de maíz", 24, 1700, "kg", 15_000, 3_000),
]


# cliente, teléfono, lo que se llevó fiado [(producto, cantidad)], abono en pesos
CLIENTES = [
    ("Doña Lupe", "55 1234 5678", [("Leche Lala entera 1 L", 2), ("Pan Bimbo grande", 1), ("Huevo blanco", 1000)], 50),
    ("Don Beto (el de la esquina)", None, [("Coca-Cola 600 ml", 3), ("Sabritas Original 45 g", 2)], 0),
    ("Mari", None, [("Frijol negro 1 kg", 1)], 0),
]


def cargar(bd: BaseDatos) -> int:
    """Da de alta los ejemplos si la base está vacía. Devuelve cuántos productos agregó."""
    agregados = _productos(bd)
    _clientes(bd)
    _dias_anteriores(bd)
    return agregados


def _dias_anteriores(bd: BaseDatos, dias: int = 21) -> None:
    """Ventas inventadas de las últimas semanas, para que Reportes tenga qué mostrar."""
    hoy = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    with bd.lectura() as con:
        if con.execute("SELECT 1 FROM ventas WHERE cuando < ?", (reloj.texto(hoy),)).fetchone():
            return
    productos = [p for p in P.buscar(bd, limite=1000)]
    if not productos:
        return
    azar = random.Random(7)
    original = reloj.ahora
    try:
        reloj.ahora = lambda: hoy - timedelta(days=dias + 1, hours=-8)
        P.registrar_llegada(bd, [P.Llegada(p.id, 60_000 if p.unidad == "kg" else 120, p.costo_promedio) for p in productos],
                            nota="Ejemplos: surtido del mes")
        for d in range(dias, 0, -1):
            dia = hoy - timedelta(days=d)
            for _ in range(azar.randint(9, 22) + (8 if dia.weekday() >= 5 else 0)):
                momento = dia + timedelta(hours=azar.choice([8, 9, 10, 11, 12, 13, 13, 14, 17, 18, 18, 19, 19, 20, 21]),
                                          minutes=azar.randint(0, 59))
                reloj.ahora = lambda m=momento: m
                elegidos = azar.sample(productos[:9] + productos, k=azar.randint(1, 3))
                pedidos = {p.id: (500 * azar.randint(1, 3) if p.unidad == "kg" else azar.randint(1, 3)) for p in elegidos}
                pedido = [ventas.Pedido(i, c) for i, c in pedidos.items()]
                total = ventas.cotizar(bd, pedido).total
                ventas.cobrar_efectivo(bd, pedido, -(-total // 10000) * 10000)
    finally:
        reloj.ahora = original
    # Se deja la existencia como en la lista de ejemplos, para que algunos se vean "por acabarse".
    como_debe = {nombre: existencia for nombre, _, _, _, existencia, _ in PRODUCTOS}
    for p in P.buscar(bd, limite=1000):
        if p.nombre in como_debe:
            P.ajustar_conteo(bd, p.id, como_debe[p.nombre], "Ejemplos")


def _clientes(bd: BaseDatos) -> None:
    if fiado.buscar(bd):
        return
    por_nombre = {p.nombre: p.id for p in P.buscar(bd, limite=1000)}
    for nombre, telefono, llevo, abono in CLIENTES:
        cliente = fiado.crear_cliente(bd, nombre, telefono)
        pedidos = [ventas.Pedido(por_nombre[n], c) for n, c in llevo if n in por_nombre]
        if pedidos:
            ventas.vender_fiado(bd, pedidos, cliente)
        if abono:
            fiado.abonar(bd, cliente, abono * 100)
    fiado.crear_cliente(bd, "Sra. Carmen", None)


def _productos(bd: BaseDatos) -> int:
    if P.buscar(bd, limite=1):
        return 0
    llegadas = []
    for nombre, precio, costo, unidad, existencia, minimo in PRODUCTOS:
        nuevo = P.crear(bd, nombre=nombre, precio_venta=precio * 100, unidad=unidad, costo=costo, minimo=minimo)
        llegadas.append(P.Llegada(nuevo, existencia, costo))
    P.registrar_llegada(bd, llegadas, nota="Ejemplos")
    return len(PRODUCTOS)
