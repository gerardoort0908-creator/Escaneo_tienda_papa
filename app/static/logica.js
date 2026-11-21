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

  /** Último dígito de un EAN-13, EAN-8 o UPC-A (regla GS1): pesos 3,1,3,1… desde la derecha. */
  function digitoCorrecto(digitos) {
    if (!/^\d+$/.test(digitos)) return false;
    let suma = 0;
    const cuerpo = digitos.slice(0, -1);
    for (let i = 0; i < cuerpo.length; i++) suma += Number(cuerpo[cuerpo.length - 1 - i]) * (i % 2 === 0 ? 3 : 1);
    return (suma + Number(digitos.slice(-1))) % 10 === 0;
  }

  /**
   * Igual que app/codigos.py: deja el código en una sola forma (UPC-A de 12 → EAN-13 con 0)
   * y descarta lecturas cuyo dígito verificador no cuadra. Devuelve null si no sirve.
   */
  const LARGOS = { ean_13: 13, ean_8: 8, upc_a: 12 };
  function normalizarCodigo(codigo, formato) {
    codigo = String(codigo || "").trim();
    formato = String(formato || "").trim().toLowerCase().replace("-", "_");
    if (!codigo || codigo.length > 64 || !/^[\x20-\x7E]+$/.test(codigo)) return null;
    const largo = LARGOS[formato];
    if (largo) {
      if (codigo.length !== largo || !digitoCorrecto(codigo)) return null;
      if (largo === 12) return "0" + codigo;
    }
    return codigo;
  }

  // ---------- Lista de ventas (la usan el celular y Reportes de la PC) ----------

  /** "10:15 a.m." a partir de "AAAA-MM-DD HH:MM:SS". */
  function hora12(cuando) {
    const [hh, mm] = cuando.slice(11, 16).split(":").map(Number);
    return ((hh + 11) % 12 + 1) + ":" + String(mm).padStart(2, "0") + (hh < 12 ? " a.m." : " p.m.");
  }

  /** "2 × Agua · ½ kg Huevo": lo que se llevó, en una línea. Por kilo la cantidad viene en gramos. */
  function renglonesTexto(renglones) {
    return renglones.map((r) => {
      if (r.unidad !== "kg") return r.cantidad + " × " + r.nombre;
      const medios = Math.round(r.cantidad / 500);
      return (Math.floor(medios / 2) || "") + (medios % 2 ? "½" : "") + " kg " + r.nombre;
    }).join(" · ");
  }

  const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
  const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
    "octubre", "noviembre", "diciembre"];
  /** "Hoy", "Ayer" o "Jueves 19 de noviembre"; `hoy` es "AAAA-MM-DD". */
  function diaTexto(dia, hoy) {
    const f = new Date(dia + "T12:00:00");
    const h = new Date(hoy + "T12:00:00");
    const atras = Math.round((h - f) / 864e5);
    if (atras === 0) return "Hoy";
    if (atras === 1) return "Ayer";
    const t = DIAS[f.getDay()] + " " + f.getDate() + " de " + MESES[f.getMonth()];
    return t[0].toUpperCase() + t.slice(1);
  }

  /**
   * Agrupa las ventas por día y les pone número: la primera del día es la Venta 1.
   * Devuelve los días y las ventas de la más nueva a la más vieja; las canceladas
   * llevan número pero no suman al total del día.
   */
  function ventasPorDia(ventas) {
    const orden = ventas.map((v, i) => [v, i])
      .sort((a, b) => a[0].cuando.localeCompare(b[0].cuando) || a[1] - b[1]).map((x) => x[0]);
    const dias = [];
    for (const v of orden) {
      const dia = v.cuando.slice(0, 10);
      let d = dias[dias.length - 1];
      if (!d || d.dia !== dia) dias.push((d = { dia, ventas: [], total: 0, cuantas: 0 }));
      const cancelada = v.estado === "cancelada";
      d.ventas.push({ ...v, numero: d.ventas.length + 1 });
      if (!cancelada) { d.total += v.total; d.cuantas += 1; }
    }
    for (const d of dias) d.ventas.reverse();
    return dias.reverse();
  }

  const api = { crearFiltroRepetidos, crearConfirmador, esperaReintento, nuevoId, resumen, normalizarCodigo,
    hora12, renglonesTexto, diaTexto, ventasPorDia };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.Logica = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
