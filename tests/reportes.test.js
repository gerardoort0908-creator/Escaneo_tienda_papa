// Cuentas de Reportes (app/static/reportes-logica.js). Correr: node --test tests/*.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const R = require("../app/static/reportes-logica.js");

const sabado = new Date(2026, 10, 21); // sáb 21 nov 2026

test("periodos", () => {
  assert.deepEqual(R.periodo("hoy", sabado), { desde: "2026-11-21", hasta: "2026-11-21" });
  assert.deepEqual(R.periodo("ayer", sabado), { desde: "2026-11-20", hasta: "2026-11-20" });
  assert.deepEqual(R.periodo("semana", sabado), { desde: "2026-11-16", hasta: "2026-11-21" });
  assert.deepEqual(R.periodo("semana", new Date(2026, 10, 22)), { desde: "2026-11-16", hasta: "2026-11-22" }); // domingo
  assert.deepEqual(R.periodo("mes", sabado), { desde: "2026-11-01", hasta: "2026-11-21" });
  assert.deepEqual(R.periodo("mespasado", sabado), { desde: "2026-10-01", hasta: "2026-10-31" });
  assert.deepEqual(R.periodo("mespasado", new Date(2027, 0, 5)), { desde: "2026-12-01", hasta: "2026-12-31" });
  assert.deepEqual(R.periodo("ayer", new Date(2027, 2, 1)), { desde: "2027-02-28", hasta: "2027-02-28" });
});

test("comparar con el periodo anterior", () => {
  assert.equal(R.cambio(500, 0), null);
  assert.deepEqual(R.cambio(1120, 1000), { clase: "sube", texto: "+12% que el periodo anterior" });
  assert.equal(R.cambio(800, 1000).texto, "−20% que el periodo anterior");
  assert.equal(R.cambio(1000, 1000).clase, "igual");
});

test("margen y textos", () => {
  assert.equal(R.margen(2500, 10000), 25);
  assert.equal(R.margen(0, 0), 0);
  assert.equal(R.periodoTexto("2026-11-21", "2026-11-21"), "sáb 21 nov");
  assert.equal(R.periodoTexto("2026-11-01", "2026-11-21"), "1 nov al 21 nov");
  assert.equal(R.horaTexto(0), "12 am");
  assert.equal(R.horaTexto(13), "1 pm");
});

test("horas de la gráfica", () => {
  const puntos = Array.from({ length: 24 }, (_, h) => ({ hora: h, ventas: h === 6 || h === 22 ? 1 : 0 }));
  const horas = R.horasConVentas(puntos).map((p) => p.hora);
  assert.equal(horas[0], 6);
  assert.equal(horas[horas.length - 1], 22);
  assert.equal(R.horasConVentas(puntos.map((p) => ({ ...p, ventas: 0 }))).length, 14);
});

test("cuando sube muchísimo no da un porcentaje enorme", () => {
  assert.equal(R.cambio(4000, 260).texto, "Más del doble que el periodo anterior");
  assert.equal(R.cambio(1990, 1000).texto, "+99% que el periodo anterior");
});
