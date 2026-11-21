/* Lógica pura del escáner, sin cámara ni red, para poder probarla aparte. */
(function (raiz) {
  "use strict";

  /** Evita contar varias veces el mismo código mientras sigue frente a la cámara. */
  function crearFiltroRepetidos(esperaMs) {
    let ultimo = null;
    let hasta = 0;
    return function aceptar(codigo, ahora) {
      if (codigo === ultimo && ahora < hasta) {
        hasta = ahora + esperaMs; // sigue a la vista: alargamos la espera
        return false;
      }
      ultimo = codigo;
      hasta = ahora + esperaMs;
      return true;
    };
  }

  /**
   * Solo acepta un código cuando sale igual en varias lecturas seguidas.
   * El dígito verificador no basta: a veces una lectura borrosa cambia varios
   * números y aun así "cuadra" (pasó con 7501000664221 → 2548000664221).
   */
  function crearConfirmador(veces, ventanaMs) {
    let candidato = null;
    let cuenta = 0;
    let ultimaVez = -Infinity;
    return function confirmar(codigo, ahora) {
      if (codigo === candidato && ahora - ultimaVez <= ventanaMs) cuenta += 1;
      else { candidato = codigo; cuenta = 1; }
      ultimaVez = ahora;
      return cuenta === veces;
    };
  }

  /**
   * Con varias mediciones {t0, ts, t1} (envío, hora del servidor, respuesta),
   * calcula cuánto hay que sumarle al reloj del celular para tener la hora de la
   * computadora. Usa la medición más rápida, que es la más precisa.
   */
  function calcularDesfase(mediciones) {
    if (!mediciones.length) return null;
    let mejor = mediciones[0];
    for (const m of mediciones) if (m.t1 - m.t0 < mejor.t1 - mejor.t0) mejor = m;
    return { desfase: mejor.ts - (mejor.t0 + mejor.t1) / 2, rtt: mejor.t1 - mejor.t0 };
  }

  /** Espera antes de reintentar un envío: 300, 600, 1200... hasta 5 s. */
  function esperaReintento(intento) {
    return Math.min(5000, 300 * 2 ** Math.max(0, intento));
  }

  /** Id único por escaneo; el servidor lo usa para no contar dos veces un reintento. */
  function nuevoId(cripto) {
    if (cripto && typeof cripto.randomUUID === "function") return cripto.randomUUID();
    const bytes = new Uint8Array(16);
    cripto.getRandomValues(bytes);
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  }

  /** Mediana y percentil 95 de una lista de latencias. */
  function resumen(valores) {
    if (!valores.length) return null;
    const orden = [...valores].sort((a, b) => a - b);
    const p = (q) => orden[Math.min(orden.length - 1, Math.ceil(q * orden.length) - 1)];
    return { cuantos: orden.length, mediana: p(0.5), p95: p(0.95), maximo: orden[orden.length - 1] };
  }

  /** Lee la llave que viene en el QR (…/celular#llave=XXXX). */
  function llaveDeHash(hash) {
    const m = /(?:^#|&)llave=([A-Za-z0-9_-]+)/.exec(hash || "");
    return m ? m[1] : null;
  }

  const api = { crearFiltroRepetidos, crearConfirmador, calcularDesfase, esperaReintento, nuevoId, resumen, llaveDeHash };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.Logica = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
