/* Lógica sin pantalla de Fiado y Corte de caja (se prueba con node --test). */
(function () {
  "use strict";

  /** Lo que se cuenta al hacer el corte: billetes y monedas, de mayor a menor (en centavos). */
  const DENOMINACIONES = [100000, 50000, 20000, 10000, 5000, 2000, 1000, 500, 200, 100, 50];
  const PRIMERA_MONEDA = 1000; // de $10 para abajo ya son monedas ($20 puede ser billete o moneda: se cuentan juntos)

  /** conteo = { 50000: 3, 100: 7, ... } → total en centavos. */
  function sumar(conteo) {
    let total = 0;
    for (const d of DENOMINACIONES) {
      const n = Number(conteo[d] || 0);
      if (Number.isInteger(n) && n > 0) total += d * n;
    }
    return total;
  }

  /** Cómo salió el corte: cuadra, sobra o falta (diferencia = contado − esperado). */
  function resultado(diferencia) {
    if (diferencia === 0) return { clase: "cuadra", texto: "Cuadra exacto" };
    if (diferencia > 0) return { clase: "sobra", texto: "Sobran" };
    return { clase: "falta", texto: "Faltan" };
  }

  /** Botones rápidos para abonar: solo los que no pasan de la deuda. */
  function abonosRapidos(saldo) {
    return [2000, 5000, 10000, 20000, 50000].filter((v) => v < saldo);
  }

  /** "2026-11-21 18:05:00" → Date (hora local). */
  function fecha(texto) {
    const [d, h = "00:00:00"] = String(texto || "").split(" ");
    const [a, m, dia] = d.split("-").map(Number);
    const [hh, mm, ss] = h.split(":").map(Number);
    return new Date(a, (m || 1) - 1, dia || 1, hh || 0, mm || 0, ss || 0);
  }

  const api = { DENOMINACIONES, PRIMERA_MONEDA, sumar, resultado, abonosRapidos, fecha };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else window.Cuentas = api;
})();
