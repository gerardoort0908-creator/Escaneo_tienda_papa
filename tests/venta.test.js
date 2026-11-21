// Cuentas de la pantalla de vender (app/static/venta.js). Correr: node --test tests/
const test = require("node:test");
const assert = require("node:assert/strict");
const V = require("../app/static/venta.js");

const coca = { id: 1, nombre: "Coca-Cola 600 ml", unidad: "pieza", precio: 2200 };
const huevo = { id: 2, nombre: "Huevo blanco", unidad: "kg", precio: 4500 };

test("los pesos se escriben sin .00 y con comas", () => {
  assert.equal(V.pesos(2200), "$22");
  assert.equal(V.pesos(1850), "$18.50");
  assert.equal(V.pesos(125000), "$1,250");
  assert.equal(V.pesos(100000000), "$1,000,000");
  assert.equal(V.pesos(5), "$0.05");
  assert.deepEqual(V.partes(125050), { entero: "1,250", centavos: "50" });
});

test("el granel cobra igual que el servidor: medio kilo de $45 = $23", () => {
  assert.equal(V.subtotal(4500, 500, "kg"), 2300);
  assert.equal(V.subtotal(4500, 1000, "kg"), 4500);
  assert.equal(V.subtotal(4500, 1500, "kg"), 6800); // $67.50 → $68
  assert.equal(V.subtotal(4400, 500, "kg"), 2200);
  assert.equal(V.subtotal(2200, 3, "pieza"), 6600);
});

test("cantidades de huevo en medios kilos", () => {
  assert.equal(V.cantidadTexto(500, "kg"), "½ kg");
  assert.equal(V.cantidadTexto(1000, "kg"), "1 kg");
  assert.equal(V.cantidadTexto(2500, "kg"), "2½ kg");
  assert.equal(V.cantidadTexto(3, "pieza"), "3");
});

test("leer lo que se escribe en Otra cantidad", () => {
  assert.equal(V.leerMonto("120"), 12000);
  assert.equal(V.leerMonto("87.5"), 8750);
  assert.equal(V.leerMonto("$1,000"), 100000);
  assert.equal(V.leerMonto(" 20. "), 2000);
  for (const malo of ["", "abc", "-5", "0", "1.234", "1e3", "9999999"]) assert.equal(V.leerMonto(malo), null, malo);
});

test("escanear dos veces el mismo producto suma en el mismo renglón y lo sube", () => {
  const c = V.crearCuenta();
  c.agregar(coca);
  c.agregar(huevo);
  c.agregar(coca);
  assert.deepEqual(c.renglones.map((r) => [r.producto.id, r.cantidad]), [[1, 2], [2, 500]]);
  assert.equal(c.total, 4400 + 2300);
  assert.equal(c.articulos, 3); // 2 cocas + el huevo cuenta como uno
  assert.deepEqual(c.pedido, [{ producto_id: 1, cantidad: 2 }, { producto_id: 2, cantidad: 500 }]);
});

test("− y + cambian de uno en uno (huevo de medio en medio) y en cero se quita", () => {
  const c = V.crearCuenta();
  c.agregar(huevo);
  c.cambiar(2, 1);
  assert.equal(c.renglones[0].cantidad, 1000);
  c.cambiar(2, -1);
  c.cambiar(2, -1);
  assert.ok(c.vacia);
  assert.equal(c.total, 0);
});

test("el pago dice cuánto falta y cuánto cambio dar", () => {
  const p = V.crearPago(13700);
  assert.equal(p.falta, 13700);
  p.poner(10000);
  assert.equal(p.falta, 3700);
  assert.ok(!p.alcanza);
  p.poner(10000);
  p.poner(500);
  assert.equal(p.recibido, 20500);
  assert.equal(p.cambio, 6800);
  p.quitar(10000);
  assert.equal(p.recibido, 10500);
  p.exacto();
  assert.equal(p.cambio, 0);
  assert.ok(p.alcanza);
});

test("piezas iguales se agrupan", () => {
  assert.deepEqual(V.agrupar([2000, 50000, 2000]), [{ valor: 50000, n: 1 }, { valor: 2000, n: 2 }]);
});

test("el cambio se da con la menor cantidad de billetes y monedas", () => {
  const forma = (c) => V.desglose(c).grupos.map((g) => `${g.tipo[0]}${g.valor / 100}x${g.n}`).join(" ");
  assert.equal(forma(6800), "b50x1 m10x1 m5x1 m2x1 m1x1");
  assert.equal(forma(36300), "b200x1 b100x1 b50x1 m10x1 m2x1 m1x1");
  assert.equal(forma(4000), "b20x2");
  assert.equal(forma(150), "m1x1 m0.5x1");
  assert.equal(V.desglose(0).grupos.length, 0);
  assert.equal(V.desglose(130).resto, 30); // 30¢ no se pueden dar con monedas de 50¢
});

test("el desglose siempre suma exactamente el cambio", () => {
  for (let c = 0; c <= 200000; c += 50) {
    const d = V.desglose(c);
    const suma = d.grupos.reduce((s, g) => s + g.valor * g.n, 0) + d.resto;
    assert.equal(suma, c);
  }
});
