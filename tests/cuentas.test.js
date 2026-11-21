// Cuentas de Fiado y Corte de caja (app/static/cuentas-logica.js). Correr: node --test tests/*.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../app/static/cuentas-logica.js");

test("sumar el dinero contado", () => {
  assert.equal(C.sumar({}), 0);
  assert.equal(C.sumar({ 50000: 2, 2000: 3, 50: 3 }), 100000 + 6000 + 150);
  assert.equal(C.sumar({ 100: "4", 500: -2, 1000: 1.5 }), 400); // ni negativos ni fracciones
  assert.equal(C.sumar({ 300: 5 }), 0); // no existe la moneda de $3
});

test("resultado del corte", () => {
  assert.equal(C.resultado(0).clase, "cuadra");
  assert.equal(C.resultado(500).clase, "sobra");
  assert.equal(C.resultado(-50).texto, "Faltan");
});

test("abonos rápidos no pasan de la deuda", () => {
  assert.deepEqual(C.abonosRapidos(6000), [2000, 5000]);
  assert.deepEqual(C.abonosRapidos(2000), []);
  assert.deepEqual(C.abonosRapidos(100000), [2000, 5000, 10000, 20000, 50000]);
});

test("fecha del servidor en hora local", () => {
  const f = C.fecha("2026-11-21 18:05:09");
  assert.deepEqual([f.getFullYear(), f.getMonth(), f.getDate(), f.getHours(), f.getMinutes()], [2026, 10, 21, 18, 5]);
});
