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

test("normalizarCodigo: igual que en la PC", () => {
  assert.equal(L.normalizarCodigo("7501055300075", "ean_13"), "7501055300075");
  assert.equal(L.normalizarCodigo("012345678905", "upc_a"), "0012345678905");
  assert.equal(L.normalizarCodigo("2548000664222", "ean_13"), null); // dígito no cuadra
  assert.equal(L.normalizarCodigo("750105530007", "ean_13"), null); // largo equivocado
  assert.equal(L.normalizarCodigo(" ABC-123 ", "code_128"), "ABC-123");
  assert.equal(L.normalizarCodigo("", "code_128"), null);
});

test("lista de ventas: número por día, de la más nueva a la más vieja", () => {
  const v = (cuando, total, estado) => ({ cuando, total, estado, renglones: [] });
  const dias = L.ventasPorDia([
    v("2026-11-21 09:00:00", 500), v("2026-11-20 18:00:00", 900), v("2026-11-21 08:30:00", 300),
    v("2026-11-21 10:00:00", 700, "cancelada"),
  ]);
  assert.deepEqual(dias.map((d) => [d.dia, d.cuantas, d.total]), [["2026-11-21", 2, 800], ["2026-11-20", 1, 900]]);
  assert.deepEqual(dias[0].ventas.map((x) => [x.numero, x.cuando.slice(11, 16)]), [[3, "10:00"], [2, "09:00"], [1, "08:30"]]);
});

test("lista de ventas: textos", () => {
  assert.equal(L.renglonesTexto([{ nombre: "Agua", cantidad: 2 }, { nombre: "Huevo", cantidad: 1500, unidad: "kg" },
    { nombre: "Frijol", cantidad: 500, unidad: "kg" }]), "2 × Agua · 1½ kg Huevo · ½ kg Frijol");
  assert.equal(L.hora12("2026-11-21 00:05:00"), "12:05 a.m.");
  assert.equal(L.hora12("2026-11-21 13:40:00"), "1:40 p.m.");
  assert.equal(L.diaTexto("2026-11-21", "2026-11-21"), "Hoy");
  assert.equal(L.diaTexto("2026-11-20", "2026-11-21"), "Ayer");
  assert.equal(L.diaTexto("2026-11-19", "2026-11-21"), "Jueves 19 de noviembre");
});
