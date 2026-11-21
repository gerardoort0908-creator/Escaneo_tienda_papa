// Pruebas de la lógica del celular. Correr con: node --test tests/
const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../app/static/logica.js");

test("no repite el mismo código mientras sigue a la vista", () => {
  const aceptar = L.crearFiltroRepetidos(1500);
  assert.equal(aceptar("A", 0), true);
  assert.equal(aceptar("A", 1000), false);
  assert.equal(aceptar("A", 2000), false); // seguía a la vista: la espera se alargó
  assert.equal(aceptar("A", 4000), true);
  assert.equal(aceptar("B", 4001), true);
  assert.equal(aceptar("A", 4002), true); // otro producto en medio: sí cuenta
});

test("desfase con la medición más rápida", () => {
  const r = L.calcularDesfase([
    { t0: 1000, ts: 5200, t1: 1300 },
    { t0: 2000, ts: 6010, t1: 2020 }, // la más rápida: desfase = 6010 - 2010
  ]);
  assert.deepEqual(r, { desfase: 4000, rtt: 20 });
  assert.equal(L.calcularDesfase([]), null);
});

test("espera de reintentos crece y tiene tope", () => {
  assert.deepEqual([0, 1, 2, 3, 10].map(L.esperaReintento), [300, 600, 1200, 2400, 5000]);
});

test("ids únicos aun sin randomUUID", () => {
  const cripto = { getRandomValues: (a) => require("node:crypto").getRandomValues(a) };
  const a = L.nuevoId(cripto), b = L.nuevoId(cripto);
  assert.match(a, /^[0-9a-f]{32}$/);
  assert.notEqual(a, b);
});

test("resumen de latencias", () => {
  const valores = Array.from({ length: 100 }, (_, i) => i + 1);
  assert.deepEqual(L.resumen(valores), { cuantos: 100, mediana: 50, p95: 95, maximo: 100 });
  assert.equal(L.resumen([]), null);
});

test("lee la llave del QR", () => {
  assert.equal(L.llaveDeHash("#llave=abc_-123"), "abc_-123");
  assert.equal(L.llaveDeHash("#x=1&llave=zz"), "zz");
  assert.equal(L.llaveDeHash(""), null);
  assert.equal(L.llaveDeHash("#llave=<script>"), null);
});

test("solo acepta cuando dos lecturas seguidas coinciden", () => {
  const confirmar = L.crearConfirmador(2, 600);
  assert.equal(confirmar("7501000664221", 0), false);
  assert.equal(confirmar("2548000664221", 50), false); // lectura mala: reinicia
  assert.equal(confirmar("7501000664221", 100), false);
  assert.equal(confirmar("7501000664221", 150), true);
  assert.equal(confirmar("7501000664221", 200), false); // ya se aceptó; no se repite
});

test("dos lecturas muy separadas no cuentan como confirmación", () => {
  const confirmar = L.crearConfirmador(2, 600);
  assert.equal(confirmar("7501000664221", 0), false);
  assert.equal(confirmar("7501000664221", 2000), false);
  assert.equal(confirmar("7501000664221", 2100), true);
});
