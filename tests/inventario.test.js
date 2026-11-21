// Cuentas de Productos y Llegó mercancía (app/static/inventario-logica.js). Correr: node --test tests/*.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const I = require("../app/static/inventario-logica.js");

const coca = { id: 1, nombre: "Coca-Cola 600 ml", unidad: "pieza", precio: 2200, costo: 1550, existencia: 24 };
const huevo = { id: 2, nombre: "Huevo blanco", unidad: "kg", precio: 4500, costo: 3820, existencia: 22500 };

test("nivel igual que el servidor", () => {
  assert.equal(I.nivel(0, 6), "acabado");
  assert.equal(I.nivel(-3, 6), "acabado");
  assert.equal(I.nivel(6, 6), "acabando");
  assert.equal(I.nivel(7, 6), "bien");
  assert.equal(I.nivel(1, 0), "bien");
});

test("la barra: el mínimo queda a un tercio y nunca pasa de lleno", () => {
  assert.equal(I.llenado(6, 6), 1 / 3);
  assert.equal(I.llenado(100, 6), 1);
  assert.equal(I.llenado(0, 6), 0);
});

test("ganancia por pieza y porcentaje", () => {
  assert.deepEqual(I.ganancia(2000, 1330), { porUnidad: 670, porcentaje: 34, pierde: false });
  assert.equal(I.ganancia(1500, 1600).pierde, true);
});

test("leer kilos", () => {
  assert.equal(I.leerKilos("22.5"), 22500);
  assert.equal(I.leerKilos("22½"), 22500);
  assert.equal(I.leerKilos("0,75"), 750);
  assert.equal(I.leerKilos("3 kg"), 3000);
  for (const malo of ["", ".", "abc", "-1", "0", "1.2345"]) assert.equal(I.leerKilos(malo), null, malo);
  assert.equal(I.kilosTexto(22500), "22.5");
});

test("costo de lo que llegó: granel por kilo, redondeado al centavo", () => {
  assert.equal(I.costoRenglon(1600, 24, "pieza"), 38400);
  assert.equal(I.costoRenglon(3820, 22500, "kg"), 85950);
  assert.equal(I.costoRenglon(3333, 500, "kg"), 1667);
});

test("la lista de lo que llegó", () => {
  const l = I.crearLlegada();
  l.agregar(coca);
  l.agregar(huevo);
  l.agregar(coca); // escanear otra vez suma uno y lo sube
  assert.deepEqual(l.renglones.map((r) => [r.producto.id, r.cantidad, r.costo]), [[1, 2, 1550], [2, 1000, 3820]]);
  l.poner(1, 24);
  l.costo(1, 1600);
  l.cambiar(2, 1);
  assert.equal(l.gramos, 2000);
  assert.equal(l.piezas, 24);
  assert.equal(l.costoTotal, 24 * 1600 + 7640);
  assert.deepEqual(l.pedido, [{ producto_id: 1, cantidad: 24, costo: 1600 }, { producto_id: 2, cantidad: 2000, costo: 3820 }]);
  l.cambiar(2, -2);
  assert.equal(l.renglones.length, 1);
  l.quitar(1);
  assert.ok(l.vacia);
});
