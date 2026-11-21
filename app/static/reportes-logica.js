/* Cuentas de la pantalla de Reportes, sin pantalla ni red (se prueban con node --test). */
(function () {
  "use strict";

  const iso = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  const dia = (a, m, d) => new Date(a, m, d);

  /** Fechas de cada botón de periodo, en hora local. La semana empieza en lunes. */
  function periodo(clave, hoy) {
    const a = hoy.getFullYear(), m = hoy.getMonth(), d = hoy.getDate();
    switch (clave) {
      case "hoy": return { desde: iso(hoy), hasta: iso(hoy) };
      case "ayer": { const y = dia(a, m, d - 1); return { desde: iso(y), hasta: iso(y) }; }
      case "semana": { const atras = (hoy.getDay() + 6) % 7; return { desde: iso(dia(a, m, d - atras)), hasta: iso(hoy) }; }
      case "mes": return { desde: iso(dia(a, m, 1)), hasta: iso(hoy) };
      case "mespasado": return { desde: iso(dia(a, m - 1, 1)), hasta: iso(dia(a, m, 0)) };
      default: throw new Error("periodo desconocido: " + clave);
    }
  }

  /** "+12% que el periodo anterior", o null si antes no hubo nada con qué comparar. */
  function cambio(actual, anterior) {
    if (!anterior) return null;
    const p = Math.round(((actual - anterior) / anterior) * 100);
    if (p === 0) return { clase: "igual", texto: "Igual que el periodo anterior" };
    if (p >= 100) return { clase: "sube", texto: "Más del doble que el periodo anterior" };
    return { clase: p > 0 ? "sube" : "baja", texto: (p > 0 ? "+" : "−") + Math.abs(p) + "% que el periodo anterior" };
  }

  /** Cuánto de cada peso vendido es ganancia (margen), en porcentaje entero. */
  function margen(ganancia, vendido) {
    return vendido > 0 ? Math.round((ganancia / vendido) * 100) : 0;
  }

  const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const DIAS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];

  /** "2026-11-21" → "sáb 21 nov". */
  function diaTexto(texto, conSemana) {
    const [a, m, d] = texto.split("-").map(Number);
    const f = dia(a, m - 1, d);
    return (conSemana ? DIAS[f.getDay()] + " " : "") + d + " " + MESES[m - 1];
  }

  /** Título del periodo: "Hoy, sáb 21 nov" o "1 nov al 21 nov". */
  function periodoTexto(desde, hasta) {
    return desde === hasta ? diaTexto(desde, true) : diaTexto(desde) + " al " + diaTexto(hasta);
  }

  /** Etiqueta de la hora para la gráfica: 7 → "7 am", 13 → "1 pm". */
  function horaTexto(h) {
    return (h % 12 || 12) + (h < 12 ? " am" : " pm");
  }

  /** En la gráfica por horas, recorta las horas de antes y después en que no hubo ventas. */
  function horasConVentas(puntos) {
    const con = puntos.filter((p) => p.ventas > 0).map((p) => p.hora);
    if (!con.length) return puntos.filter((p) => p.hora >= 8 && p.hora <= 21);
    const desde = Math.min(Math.min(...con), 8), hasta = Math.max(Math.max(...con), 21);
    return puntos.filter((p) => p.hora >= desde && p.hora <= hasta);
  }

  const api = { periodo, cambio, margen, diaTexto, periodoTexto, horaTexto, horasConVentas, iso };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else window.Reportes = api;
})();
