/* Pantalla de Reportes: cuánto se vendió y se ganó, qué se vende más, qué hay que comprar y quién debe. */
(function () {
  "use strict";
  const V = window.Venta;
  const R = window.Reportes;
  const T = window.Tienda;
  const { el, aviso, api } = T;
  const $ = (id) => document.getElementById(id);

  const ORO = "#E9C987";
  const VERDE = "#46D98C";
  let rango = R.periodo("hoy", new Date());
  let clave = "hoy";
  let datos = null;
  let orden = "vendido";
  let g1 = null;
  let g2 = null;
  let consulta = 0;

  // ------------------------------------------------------------ cargar

  async function cargar() {
    const n = ++consulta;
    let d;
    try { d = await api("/api/reportes?desde=" + rango.desde + "&hasta=" + rango.hasta); } catch (e) { aviso(e.message, true); return; }
    if (n !== consulta) return;
    datos = d;
    const texto = R.periodoTexto(d.desde, d.hasta);
    const nombre = { hoy: "Hoy", ayer: "Ayer", semana: "Esta semana", mes: "Este mes", mespasado: "Mes pasado" }[clave];
    $("periodo-txt").textContent = nombre ? nombre + " · " + texto : texto;
    $("papel-titulo").textContent = "Reporte de la tienda · " + texto;
    pintarKpis();
    pintarG1();
    pintarG2();
    pintarListas();
  }

  // ------------------------------------------------------------ números de arriba

  function kpi(clase, etiqueta, centavos, ...extra) {
    const k = el("div", "kpi glass " + clase);
    const n = el("div", "num");
    T.numHTML(n, centavos);
    k.append(el("span", "lbl", etiqueta), n, ...extra.filter(Boolean));
    return k;
  }

  function pintarKpis() {
    const r = datos.resumen;
    const a = datos.anterior;
    // Solo se compara un periodo ya terminado: hoy a medio día contra ayer completo engaña.
    const terminado = datos.hasta < R.iso(new Date());
    const comparar = (actual, antes) => {
      const c = terminado ? R.cambio(actual, antes) : null;
      return c ? el("small", c.clase, c.texto) : null;
    };
    const ventas = el("small", "", r.ventas + (r.ventas === 1 ? " venta" : " ventas") + (r.canceladas ? " · " + r.canceladas + " cancelada" + (r.canceladas === 1 ? "" : "s") : ""));
    const margen = el("small", "", r.vendido ? "De cada $100 que vendes te quedan $" + R.margen(r.ganancia, r.vendido) : "Sin ventas");

    // Efectivo contra préstamo
    const barra = el("div", "barra2");
    const ef = el("i", "ef");
    const pr = el("i", "pr");
    const total = r.efectivo + r.prestado;
    ef.style.width = (total ? (r.efectivo / total) * 100 : 0) + "%";
    pr.style.width = (total ? (r.prestado / total) * 100 : 0) + "%";
    barra.append(ef, pr);
    const partes = el("div", "partes");
    const parte = (t, v) => { const s = el("span", "", t + " "); s.appendChild(el("b", "", V.pesos(v))); return s; };
    partes.append(parte("Prestado", r.prestado), parte("Te pagaron", r.pagos_de_prestamos));

    const p = datos.prestamos;
    $("kpis").replaceChildren(
      kpi("", "Vendiste", r.vendido, ventas, comparar(r.vendido, a.vendido)),
      kpi("gana", "Ganaste", r.ganancia, margen, comparar(r.ganancia, a.ganancia)),
      kpi("", "Cobraste en efectivo", r.efectivo, barra, partes),
      kpi("debe", "Te deben (hoy, todos)", p.deben, el("small", "", p.personas ? p.personas + (p.personas === 1 ? " persona" : " personas") : "Nadie te debe")),
    );
  }

  // ------------------------------------------------------------ gráficas

  Chart.defaults.font.family = '"Hanken Grotesk", system-ui, sans-serif';
  Chart.defaults.font.size = 12;

  function colores(papel) {
    return { texto: papel ? "#444" : "rgba(244,242,238,.55)", fuerte: papel ? "#222" : "rgba(244,242,238,.85)",
      rejilla: papel ? "#e6e1d8" : "rgba(255,255,255,.06)" };
  }

  const dinero = (v) => "$" + Math.round(v / 100).toLocaleString("es-MX");
  const tooltip = {
    backgroundColor: "rgba(24,24,25,.96)", borderColor: "rgba(255,255,255,.1)", borderWidth: 1, padding: 10, cornerRadius: 10,
    titleFont: { weight: "600" }, displayColors: true, boxPadding: 4,
    callbacks: { label: (c) => " " + c.dataset.label + ": " + V.pesos(c.raw) },
  };

  function pintarG1() {
    const g = datos.grafica;
    const puntos = g.por === "hora" ? R.horasConVentas(g.puntos) : g.puntos;
    const etiquetas = puntos.map((p) => g.por === "hora" ? R.horaTexto(p.hora) : R.diaTexto(p.dia, puntos.length <= 7));
    $("g1-titulo").textContent = g.por === "hora" ? "A qué hora se vendió" : "Cómo se vendió cada día";
    const c = colores(false);
    const config = {
      type: "bar",
      data: {
        labels: etiquetas,
        datasets: [
          { label: "Vendiste", data: puntos.map((p) => p.vendido), backgroundColor: ORO, borderRadius: 6, maxBarThickness: 34, categoryPercentage: .7, barPercentage: .9 },
          { label: "Ganaste", data: puntos.map((p) => p.ganancia), backgroundColor: VERDE, borderRadius: 6, maxBarThickness: 34, categoryPercentage: .7, barPercentage: .9 },
        ],
      },
      options: {
        maintainAspectRatio: false, animation: { duration: 500 },
        plugins: { legend: { display: false }, tooltip },
        scales: {
          x: { grid: { display: false }, ticks: { color: c.texto, maxRotation: 0, autoSkipPadding: 10 }, border: { display: false } },
          y: { beginAtZero: true, grid: { color: c.rejilla }, border: { display: false }, ticks: { color: c.texto, callback: dinero, maxTicksLimit: 6 } },
        },
      },
    };
    if (g1) g1.destroy();
    g1 = new Chart($("g1"), config);
  }

  function pintarG2() {
    const lista = orden === "vendido" ? datos.mas_vendidos : datos.mas_ganancia;
    $("g2-vacio").hidden = lista.length > 0;
    $("g2").parentElement.hidden = !lista.length;
    if (g2) { g2.destroy(); g2 = null; }
    if (!lista.length) return;
    const c = colores(false);
    const color = orden === "vendido" ? ORO : VERDE;
    g2 = new Chart($("g2"), {
      type: "bar",
      data: {
        labels: lista.map((x) => x.nombre.length > 24 ? x.nombre.slice(0, 23) + "…" : x.nombre),
        datasets: [{ label: orden === "vendido" ? "Vendiste" : "Ganaste", data: lista.map((x) => x[orden]), backgroundColor: color, borderRadius: 6, maxBarThickness: 18 }],
      },
      options: {
        indexAxis: "y", maintainAspectRatio: false, animation: { duration: 500 },
        plugins: {
          legend: { display: false },
          tooltip: { ...tooltip, callbacks: { label: (ctx) => {
            const x = lista[ctx.dataIndex];
            return " " + V.pesos(ctx.raw) + " · " + T.existenciaTexto(x.cantidad, x.unidad).replace("piezas", "vendidas").replace("pieza", "vendida");
          } } },
        },
        scales: {
          x: { beginAtZero: true, grid: { color: c.rejilla }, border: { display: false }, ticks: { color: c.texto, callback: dinero, maxTicksLimit: 5 } },
          y: { grid: { display: false }, border: { display: false }, ticks: { color: c.fuerte, font: { size: 13 } } },
        },
      },
    });
  }

  // Para imprimir, las letras de las gráficas se vuelven oscuras; al terminar regresan.
  function tema(papel) {
    const c = colores(papel);
    for (const g of [g1, g2]) {
      if (!g) continue;
      for (const [nombre, eje] of Object.entries(g.options.scales)) {
        eje.ticks.color = g === g2 && nombre === "y" ? c.fuerte : c.texto;
        if (eje.grid) eje.grid.color = c.rejilla;
      }
      g.options.animation = papel ? false : { duration: 500 };
      g.update("none");
      // En papel la gráfica es más chica que en la pantalla: se dibuja a la medida de media hoja.
      if (papel) g.resize(g === g1 ? 380 : 330, 230); else g.resize();
    }
  }
  window.addEventListener("beforeprint", () => tema(true));
  window.addEventListener("afterprint", () => tema(false));

  // ------------------------------------------------------------ listas

  function item(clase, nombre, detalle, valor) {
    const f = el("div", "it " + clase);
    const n = el("div");
    n.append(el("b", "", nombre), el("small", "", detalle));
    f.append(n, el("span", "v", valor));
    return f;
  }

  function llenar(id, filas, vacio, max) {
    const caja = $(id);
    caja.replaceChildren();
    if (!filas.length) { caja.appendChild(el("p", "vacio", vacio)); return; }
    filas.slice(0, max).forEach((f) => caja.appendChild(f));
    if (filas.length > max) caja.appendChild(el("span", "mas-items", "y " + (filas.length - max) + " más"));
  }

  function pintarListas() {
    llenar("faltan", datos.faltantes.map((x) => item(x.nivel, x.nombre,
      "Mínimo " + T.existenciaTexto(x.minimo, x.unidad),
      x.nivel === "acabado" ? "Se acabó" : "Quedan " + T.existenciaTexto(x.existencia, x.unidad))),
      "Todo está bien surtido.", 6);
    llenar("parado", datos.sin_moverse.map((x) => item("", x.nombre, "Hay " + T.existenciaTexto(x.existencia, x.unidad), V.pesos(x.parado))),
      "Todo lo que tienes se vendió al menos una vez.", 6);
    llenar("deben", datos.prestamos.deudores.map((x) => item("debe", x.nombre, "", V.pesos(x.saldo))),
      "Nadie te debe.", 6);
  }

  // ------------------------------------------------------------ eventos

  $("periodos").addEventListener("click", (e) => {
    const b = e.target.closest("[data-p]");
    if (!b) return;
    $("periodos").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    const fechas = b.dataset.p === "fechas";
    $("fechas").hidden = !fechas;
    if (fechas) {
      clave = "fechas";
      $("f-desde").value = rango.desde;
      $("f-hasta").value = rango.hasta;
      $("f-desde").focus();
      return;
    }
    clave = b.dataset.p;
    rango = R.periodo(clave, new Date());
    cargar();
  });
  const porFechas = () => {
    if (!$("f-desde").value || !$("f-hasta").value) return;
    rango = { desde: $("f-desde").value, hasta: $("f-hasta").value };
    cargar();
  };
  $("f-desde").addEventListener("change", porFechas);
  $("f-hasta").addEventListener("change", porFechas);

  $("orden").addEventListener("click", (e) => {
    const b = e.target.closest("[data-o]");
    if (!b || !datos) return;
    orden = b.dataset.o;
    $("orden").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    pintarG2();
  });

  $("imprimir").onclick = () => window.print();
  $("excel").onclick = () => {
    location.href = "/api/reportes/excel?desde=" + rango.desde + "&hasta=" + rango.hasta;
    aviso("Se está descargando el Excel");
  };

  T.montar({
    seccion: "reportes",
    alElegir: () => aviso("Para vender ese producto, abre Vender (abajo a la izquierda)."),
    codigoNuevo: () => aviso("Ese código no está registrado. Dalo de alta en Vender o en Productos."),
    escribirBusca: () => false,
    antesDeSalir: () => null,
  });

  cargar();
})();
