/* Pantalla de Vender y cobrar: escanear → ver el total → cobrar con billetes y monedas → cambio. */
(function () {
  "use strict";
  const V = window.Venta;
  const T = window.Tienda;
  const { el, numHTML, aviso, bip, api } = T;
  const $ = (id) => document.getElementById(id);
  const app = $("app");

  const COLOR_BILLETE = {
    2000: ["#5CC3D3", "#1C6F80"], 5000: ["#EE6FA4", "#93235B"], 10000: ["#F38A5A", "#AA3416"],
    20000: ["#8BD177", "#357A27"], 50000: ["#7C9EE6", "#2A4A94"], 100000: ["#B79BE8", "#5B3F9A"],
  };
  const ESPERA_REGRESO_MS = 25000; // la pantalla del cambio vuelve sola a "Escanea"

  const cuenta = V.crearCuenta();
  let pago = null;
  let ultimaVenta = null;
  let ocupado = false; // mientras se guarda un cobro
  let regreso = null;

  // ------------------------------------------------------------ estados

  function estado(nuevo) {
    app.dataset.state = nuevo;
    clearTimeout(regreso);
    if (nuevo === "done") regreso = setTimeout(nuevaVenta, ESPERA_REGRESO_MS);
  }

  // ------------------------------------------------------------ la cuenta

  let mostrado = 0;
  let animacion = null;
  function pintarTotal() {
    const destino = cuenta.total;
    const desde = mostrado;
    const t0 = performance.now();
    cancelAnimationFrame(animacion);
    const paso = (t) => {
      const k = Math.min(1, (t - t0) / 380);
      const e = 1 - Math.pow(1 - k, 3);
      numHTML($("total"), Math.round((desde + (destino - desde) * e) / 100) * 100);
      if (k < 1) animacion = requestAnimationFrame(paso);
      else { mostrado = destino; numHTML($("total"), destino); }
    };
    animacion = requestAnimationFrame(paso);
    const n = cuenta.articulos;
    $("articulos").textContent = n + (n === 1 ? " artículo" : " artículos");
  }

  function pintarLista(resaltar) {
    const lista = $("lista");
    lista.replaceChildren();
    for (const r of cuenta.renglones) {
      const p = r.producto;
      const fila = el("div", "it" + (p.id === resaltar ? " fresh" : ""));
      fila.setAttribute("role", "listitem");
      const n = el("span", "n");
      n.append(el("b", "", p.nombre), el("small", "", T.precioTexto(p)));
      const paso = el("span", "step");
      const menos = el("button", "", "−");
      menos.setAttribute("aria-label", "Uno menos de " + p.nombre);
      menos.onclick = () => cambiar(p.id, -1);
      const mas = el("button", "", "+");
      mas.setAttribute("aria-label", "Uno más de " + p.nombre);
      mas.onclick = () => cambiar(p.id, 1);
      paso.append(menos, el("span", "", V.cantidadTexto(r.cantidad, p.unidad)), mas);
      fila.append(T.tile(p.nombre), n, paso, el("span", "p", V.pesos(V.subtotal(p.precio, r.cantidad, p.unidad))));
      lista.appendChild(fila);
    }
    pintarTotal();
    if (resaltar) setTimeout(() => { const f = lista.querySelector(".fresh"); if (f) f.classList.remove("fresh"); }, 900);
  }

  function agregar(producto) {
    cuenta.agregar(producto);
    if (app.dataset.state === "done" || app.dataset.state === "idle") estado("sale");
    pintarLista(producto.id);
    if (app.dataset.state === "pay") recalcularPago();
    bip(false);
  }

  function cambiar(id, pasos) {
    cuenta.cambiar(id, pasos);
    vaciarSeguro(false);
    if (cuenta.vacia) { nuevaVenta(); return; }
    pintarLista(null);
  }

  function vaciarSeguro(armado) {
    const b = $("vaciar");
    b.classList.toggle("seguro", armado);
    b.textContent = armado ? "¿Seguro? Toca otra vez para cancelar" : "Cancelar venta";
  }

  let armadoVaciar = null;
  $("vaciar").onclick = () => {
    if (armadoVaciar) {
      clearTimeout(armadoVaciar);
      armadoVaciar = null;
      nuevaVenta();
      aviso("Venta cancelada. No se guardó nada.");
      return;
    }
    vaciarSeguro(true);
    armadoVaciar = setTimeout(() => { armadoVaciar = null; vaciarSeguro(false); }, 3500);
  };

  function nuevaVenta() {
    cuenta.vaciar();
    pago = null;
    clearTimeout(armadoVaciar);
    armadoVaciar = null;
    vaciarSeguro(false);
    mostrado = 0;
    pintarLista(null);
    $("motivos").hidden = true;
    $("deshacer").hidden = false;
    estado("idle");
  }

  // ------------------------------------------------------------ cobrar

  function botonBillete(valor) {
    const b = el("button", "bill");
    b.dataset.valor = valor;
    const [c1, c2] = COLOR_BILLETE[valor];
    b.style.setProperty("--b1", c1);
    b.style.setProperty("--b2", c2);
    b.append(el("small", "", "Billete"), el("b", "", V.pesos(valor)));
    b.setAttribute("aria-label", "Billete de " + V.pesos(valor));
    return b;
  }

  function botonMoneda(valor) {
    const b = el("button", "coin" + (valor < 100 ? " plata" : ""), valor < 100 ? valor + "¢" : V.pesos(valor));
    b.dataset.valor = valor;
    b.setAttribute("aria-label", "Moneda de " + (valor < 100 ? valor + " centavos" : V.pesos(valor)));
    return b;
  }

  $("billetes").append(...[...V.BILLETES].reverse().map(botonBillete));
  $("monedas").append(...V.MONEDAS.map(botonMoneda));

  function irACobrar() {
    if (cuenta.vacia || app.dataset.state !== "sale") return;
    pago = V.crearPago(cuenta.total);
    $("monto").value = "";
    estado("pay");
    pintarPago();
  }

  function recalcularPago() {
    const piezas = pago ? pago.piezas : [];
    pago = V.crearPago(cuenta.total);
    piezas.forEach((v) => pago.poner(v));
    pintarPago();
  }

  function pintarPago() {
    $("p-total").textContent = V.pesos(pago.total);
    $("p-recibido").textContent = V.pesos(pago.recibido);
    const piezas = $("piezas");
    piezas.replaceChildren();
    for (const g of V.agrupar(pago.piezas)) {
      const chip = el("button", "pc", (g.n > 1 ? g.n + " × " : "") + V.pesos(g.valor));
      chip.appendChild(el("i", "", "×"));
      chip.title = "Quitar uno";
      chip.onclick = () => { pago.quitar(g.valor); pintarPago(); };
      piezas.appendChild(chip);
    }
    const st = $("p-estado");
    st.replaceChildren();
    const fin = $("terminar");
    if (!pago.alcanza) {
      st.className = "pstat falta";
      st.append(el("span", "", pago.recibido ? "Todavía falta" : "Falta"), el("b", "", V.pesos(pago.falta)));
      fin.className = "cta off";
      fin.textContent = "Cobrar";
    } else {
      st.className = "pstat ok";
      st.append(el("span", "", "Cambio"), el("b", "", V.pesos(pago.cambio)));
      fin.className = "cta";
      fin.replaceChildren(document.createTextNode(pago.cambio ? "Cobrar y dar cambio " : "Cobrar "), el("kbd", "", "Enter"));
    }
  }

  document.querySelector(".pleft").addEventListener("click", (e) => {
    const b = e.target.closest("[data-valor]");
    if (!b || !pago) return;
    pago.poner(Number(b.dataset.valor));
    pintarPago();
  });

  $("otra").onsubmit = (e) => {
    e.preventDefault();
    if (!$("monto").value.trim() && pago.alcanza) { terminar(); return; }
    const v = V.leerMonto($("monto").value);
    if (v === null) { aviso("Escribe una cantidad, por ejemplo 150 o 87.50", true); return; }
    pago.poner(v);
    $("monto").value = "";
    pintarPago();
  };

  $("exacto").onclick = () => { pago.exacto(); pintarPago(); terminar(); };
  $("volver").onclick = () => estado("sale");
  $("cobrar").onclick = irACobrar;
  $("terminar").onclick = terminar;

  async function terminar() {
    if (!pago || !pago.alcanza || ocupado) return;
    ocupado = true;
    const datos = { operacion: T.nuevoId(), renglones: cuenta.pedido, recibido: pago.recibido, total_visto: pago.total };
    try {
      const recibo = await api("/api/ventas/cobrar", datos);
      ultimaVenta = recibo.venta_id;
      mostrarCambio(recibo);
    } catch (error) {
      aviso(error.message, true);
      bip(true);
    } finally {
      ocupado = false;
    }
  }

  function mostrarCambio(recibo) {
    numHTML($("d-cambio"), recibo.cambio);
    $("d-lbl").textContent = recibo.cambio ? "Pagó " + V.pesos(recibo.recibido) + " · su cambio es" : "Venta cobrada";
    const dale = $("d-dale");
    dale.replaceChildren();
    if (!recibo.cambio) {
      dale.appendChild(el("span", "lead", "Sin cambio. Pagó exacto."));
    } else {
      const d = V.desglose(recibo.cambio);
      dale.appendChild(el("span", "lead", "Dale"));
      for (const g of d.grupos) {
        if (g.tipo === "billete") {
          const b = el("span", "mb", V.pesos(g.valor));
          b.style.setProperty("--b1", COLOR_BILLETE[g.valor][0]);
          b.style.setProperty("--b2", COLOR_BILLETE[g.valor][1]);
          dale.appendChild(b);
        } else {
          dale.appendChild(el("span", "coin" + (g.valor < 100 ? " plata" : ""), g.valor < 100 ? g.valor + "¢" : V.pesos(g.valor)));
        }
        if (g.n > 1) dale.appendChild(el("span", "x", "×" + g.n));
      }
      if (d.resto) dale.appendChild(el("span", "lead", "+ " + d.resto + "¢"));
    }
    terminarVenta();
  }

  function terminarVenta() {
    cuenta.vaciar();
    pago = null;
    mostrado = 0;
    pintarLista(null);
    $("motivos").hidden = true;
    $("deshacer").hidden = false;
    estado("done");
  }

  // ------------------------------------------------------------ fiado

  $("fiar").onclick = () => {
    if (!pago || ocupado) return;
    T.abrirClientes({ titulo: "¿A quién se le presta?", sub: "Total " + V.pesos(pago.total), alElegir: fiarA });
  };

  async function fiarA(cliente) {
    if (!pago || ocupado) return;
    ocupado = true;
    const datos = { operacion: T.nuevoId(), renglones: cuenta.pedido, total_visto: pago.total, cliente_id: cliente.id };
    try {
      const r = await api("/api/ventas/fiar", datos);
      ultimaVenta = r.venta_id;
      numHTML($("d-cambio"), r.total);
      $("d-lbl").textContent = "Se le prestó a " + r.cliente.nombre;
      const dale = $("d-dale");
      dale.replaceChildren(el("span", "lead", "Ahora debe"), el("b", "debe-total", V.pesos(r.cliente.saldo)), el("span", "lead", "en total"));
      terminarVenta();
    } catch (error) {
      aviso(error.message, true);
      bip(true);
    } finally {
      ocupado = false;
    }
  }

  $("nueva").onclick = nuevaVenta;

  // Cancelar la venta que se acaba de cobrar (se regresa la mercancía; la venta queda como cancelada).
  $("deshacer").onclick = () => {
    clearTimeout(regreso);
    $("deshacer").hidden = true;
    $("motivos").hidden = false;
    $("motivo-otro").value = "";
  };

  async function cancelarUltima(motivo) {
    if (!ultimaVenta) return;
    try {
      await api("/api/ventas/" + ultimaVenta + "/cancelar", { motivo });
      ultimaVenta = null;
      nuevaVenta();
      aviso("Venta cancelada. La mercancía regresó al inventario.");
    } catch (error) {
      aviso(error.message, true);
    }
  }

  $("motivos").addEventListener("click", (e) => {
    const b = e.target.closest("[data-motivo]");
    if (b) cancelarUltima(b.dataset.motivo);
  });
  $("motivos").onsubmit = (e) => {
    e.preventDefault();
    const motivo = $("motivo-otro").value.trim();
    if (!motivo) { $("motivo-otro").focus(); aviso("Escribe por qué se cancela o toca un motivo", true); return; }
    cancelarUltima(motivo);
  };

  // ------------------------------------------------------------ arranque

  T.montar({
    seccion: "vender",
    alElegir: agregar,
    codigoNuevo: (codigo) => T.abrirAlta(codigo, {
      sub: "Dalo de alta y se agrega a la venta. El costo y el mínimo se llenan después en Productos.",
      boton: "Guardar y agregar",
      alGuardar: (p) => agregar(p),
    }),
    escribirBusca: () => app.dataset.state === "idle" || app.dataset.state === "sale",
    antesDeBuscar: () => {
      if (app.dataset.state === "pay" || app.dataset.state === "done") estado(cuenta.vacia ? "idle" : "sale");
    },
    antesDeSalir: () => (cuenta.vacia ? null : "Primero cobra o cancela la venta que está abierta"),
  });

  // Enter siempre hace el paso principal (aunque se haya quedado marcado un billete o un botón); Esc regresa.
  document.addEventListener("keydown", (e) => {
    if (T.capaAbierta()) return;
    const escribiendo = e.target.matches && e.target.matches("input");
    if (e.key === "Escape") {
      if (app.dataset.state === "pay") estado("sale");
      else if (app.dataset.state === "done") nuevaVenta();
    } else if (e.key === "Enter" && !escribiendo) {
      e.preventDefault();
      if (app.dataset.state === "sale") irACobrar();
      else if (app.dataset.state === "pay") terminar();
      else if (app.dataset.state === "done") nuevaVenta();
    }
  }, true);

  pintarLista(null);
  window.__vender = { cuenta, agregar };
})();
