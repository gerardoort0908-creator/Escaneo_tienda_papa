/* Pantalla de Préstamos (en el código se llama fiado): quién debe, cuánto, qué se llevó, y registrar lo que va pagando. */
(function () {
  "use strict";
  const V = window.Venta;
  const C = window.Cuentas;
  const T = window.Tienda;
  const { el, aviso, api } = T;
  const $ = (id) => document.getElementById(id);

  let clientes = [];
  let filtro = "deben";
  let elegido = null; // el cliente a la derecha, con sus movimientos
  let nuevo = false;
  let consulta = 0;
  let ocupado = false;

  // ------------------------------------------------------------ lista

  async function cargar(mantener) {
    const n = ++consulta;
    const q = $("filtro-texto").value.trim();
    let d;
    try { d = await api("/api/clientes?q=" + encodeURIComponent(q)); } catch (e) { aviso(e.message, true); return; }
    if (n !== consulta) return;
    if (d.deben !== null) {
      $("resumen").textContent = d.deben ? d.deben + (d.deben === 1 ? " cliente debe" : " clientes deben") : "Nadie debe nada";
      $("te-deben").hidden = !d.total;
      T.numHTML($("total-deben"), d.total || 0);
    }
    clientes = filtro === "deben" && !q ? d.clientes.filter((c) => c.saldo > 0) : d.clientes;
    pintarLista();
    if (!mantener && !elegido && !nuevo && clientes.length) elegir(clientes[0].id);
    if (!clientes.length && !elegido && !nuevo) pintarVacio();
  }

  function pintarLista() {
    const lista = $("lista");
    lista.replaceChildren();
    if (!clientes.length) {
      lista.appendChild(el("p", "vacio", $("filtro-texto").value.trim() ? "No hay clientes con ese nombre."
        : filtro === "deben" ? "Nadie debe nada. Cuando prestes desde Vender, aquí aparece." : "Todavía no hay clientes."));
      return;
    }
    for (const c of clientes) {
      const fila = el("button", "rw" + (elegido && elegido.id === c.id ? " sel" : ""));
      fila.setAttribute("role", "option");
      const n = el("span", "n");
      n.append(el("b", "", c.nombre), el("small", "", c.telefono || (c.saldo > 0 ? "Tiene cuenta abierta" : "Al corriente")));
      const tag = el("span", "tag " + (c.saldo > 0 ? "debe" : "ok"), c.saldo > 0 ? "debe " + V.pesos(c.saldo) : "no debe");
      fila.append(T.tile(c.nombre), n, tag);
      fila.onclick = () => elegir(c.id);
      lista.appendChild(fila);
    }
  }

  async function elegir(id) {
    try { elegido = await api("/api/clientes/" + id); } catch (e) { aviso(e.message, true); return; }
    nuevo = false;
    pintarLista();
    pintarDetalle();
    const sel = $("lista").querySelector(".sel");
    if (sel) sel.scrollIntoView({ block: "nearest" });
  }

  // ------------------------------------------------------------ detalle

  function pintarVacio() {
    const d = $("detalle");
    d.replaceChildren();
    const v = el("div", "vacio-grande");
    v.append(el("span", "", "Elige un cliente para ver cuánto debe y registrar lo que paga. Para prestar, cobra desde Vender y toca «No pagó: es préstamo»."));
    d.appendChild(v);
  }

  function pintarDetalle() {
    const c = nuevo ? { id: null, nombre: "", telefono: "", nota: "", saldo: 0, movimientos: [] } : elegido;
    const d = $("detalle");
    d.replaceChildren();

    // Nombre y teléfono
    const ficha = el("div", "ficha");
    const nombre = el("input", "nombre-in");
    nombre.id = "d-nombre";
    nombre.value = c.nombre;
    nombre.maxLength = 60;
    nombre.placeholder = "Nombre del cliente";
    nombre.setAttribute("aria-label", "Nombre");
    const tel = el("input", "codigo-in");
    tel.id = "d-tel";
    tel.value = c.telefono || "";
    tel.maxLength = 30;
    tel.inputMode = "tel";
    tel.placeholder = "Teléfono (opcional)";
    tel.setAttribute("aria-label", "Teléfono");
    const nc = el("div");
    nc.append(nombre, tel);
    ficha.append(T.tile(c.nombre || "?"), nc);
    nombre.addEventListener("input", () => { ficha.firstChild.replaceWith(T.tile(nombre.value || "?")); revisar(); });
    tel.addEventListener("input", revisar);
    d.appendChild(ficha);

    const guardar = el("button", "act off", nuevo ? "Dar de alta" : "Guardar nombre y teléfono");
    function revisar() {
      const cambio = nuevo ? nombre.value.trim() : (nombre.value.trim() !== c.nombre || tel.value.trim() !== (c.telefono || ""));
      guardar.classList.toggle("off", !cambio);
      guardar.hidden = !nuevo && !cambio;
    }
    guardar.onclick = async () => {
      try {
        const r = nuevo
          ? await api("/api/clientes", { nombre: nombre.value, telefono: tel.value || null })
          : await api("/api/clientes/" + c.id, { nombre: nombre.value, telefono: tel.value });
        aviso(nuevo ? "«" + r.nombre + "» quedó dado de alta" : "Guardado");
        elegido = r;
        nuevo = false;
        if (filtro === "deben" && r.saldo <= 0) cambiarFiltro("todos");
        await cargar(true);
        pintarDetalle();
      } catch (e) {
        aviso(e.message, true);
      }
    };

    if (nuevo) {
      d.appendChild(el("p", "sub", "Solo hace falta el nombre. Si hay dos con el mismo nombre, agrega un apellido o apodo."));
      const acciones = el("div", "acciones");
      const cancelar = el("button", "boton", "Cancelar");
      cancelar.onclick = salirDeNuevo;
      acciones.appendChild(cancelar);
      const pie = el("div", "mt pie");
      pie.append(guardar, acciones);
      d.appendChild(pie);
      revisar();
      nombre.focus();
      return;
    }
    guardar.hidden = true;
    d.appendChild(guardar);

    // Cuánto debe
    const debe = el("div", "debe " + (c.saldo > 0 ? "si" : "no"));
    const izq = el("div");
    izq.appendChild(el("div", "lbl", c.saldo > 0 ? "Debe" : "No debe nada"));
    const num = el("div", "num");
    T.numHTML(num, c.saldo);
    izq.appendChild(num);
    debe.appendChild(izq);
    const ultimo = c.movimientos.find((m) => m.tipo === "abono");
    if (ultimo) debe.appendChild(el("span", "ultimo", "Último pago: " + V.pesos(-ultimo.monto) + " · " + cuando(ultimo.cuando)));
    d.appendChild(debe);

    // Abonar
    if (c.saldo > 0) d.appendChild(cajaAbono(c));

    // Historial
    if (c.movimientos.length) {
      d.appendChild(el("h4", "tit", "Lo que se ha llevado y lo que ha pagado"));
      const lista = el("div", "movs");
      for (const m of c.movimientos) {
        const fila = el("div", "mov " + m.tipo);
        const izq2 = el("div");
        const que = m.tipo === "cargo" ? "Se llevó" : m.tipo === "abono" ? (m.nota === "Pagó todo" ? "Pagó todo" : "Abonó") : "Venta cancelada";
        izq2.append(el("b", "", que), el("small", "", cuando(m.cuando) + (m.detalle ? " · " + m.detalle : "")));
        fila.append(izq2, el("span", "m", (m.monto > 0 ? "+" : "−") + V.pesos(Math.abs(m.monto))));
        lista.appendChild(fila);
      }
      d.appendChild(lista);
    }

    // Quitar de la lista (solo si ya no debe)
    if (c.saldo === 0) {
      const acciones = el("div", "acciones mt");
      const quitar = el("button", "boton peligro", "Quitar de la lista");
      quitar.onclick = () => quitarCliente(quitar, c);
      acciones.appendChild(quitar);
      d.appendChild(acciones);
    }
  }

  function cajaAbono(c) {
    const caja = el("form", "abono");
    caja.appendChild(el("span", "lbl", "¿Cuánto pagó?"));
    const fila = el("div", "fila");
    for (const v of C.abonosRapidos(c.saldo)) {
      const b = el("button", "chip", V.pesos(v));
      b.type = "button";
      b.onclick = () => abonar(c, v);
      fila.appendChild(b);
    }
    const monto = el("label", "monto");
    const input = el("input");
    input.id = "d-abono";
    input.inputMode = "decimal";
    input.autocomplete = "off";
    input.placeholder = "Otra cantidad";
    input.setAttribute("aria-label", "Cuánto pagó");
    monto.append(el("em", "", "$"), input);
    const ok = el("button", "boton", "Abonar");
    ok.type = "submit";
    const fila2 = el("div", "fila");
    fila2.append(monto, ok);
    if (fila.childNodes.length) caja.appendChild(fila);
    caja.appendChild(fila2);
    const todo = el("button", "act", "Pagó todo · " + V.pesos(c.saldo));
    todo.type = "button";
    todo.onclick = () => abonar(c, null);
    caja.appendChild(todo);
    caja.onsubmit = (e) => {
      e.preventDefault();
      const v = V.leerMonto(input.value);
      if (!v) { aviso("Escribe cuánto pagó, por ejemplo 50 o 75.50", true); input.focus(); return; }
      abonar(c, v);
    };
    return caja;
  }

  async function abonar(c, monto) {
    if (ocupado) return;
    ocupado = true;
    const datos = { operacion: T.nuevoId(), ...(monto === null ? { todo: true } : { monto: (monto / 100).toFixed(2) }) };
    try {
      const r = await api("/api/clientes/" + c.id + "/abonar", datos);
      aviso(r.saldo ? "Abonó " + V.pesos(r.pago) + ". Le quedan " + V.pesos(r.saldo) + "." : "Pagó " + V.pesos(r.pago) + ". Ya no debe nada.");
      T.bip(false);
      elegido = r;
      await cargar(true);
      pintarDetalle();
    } catch (e) {
      aviso(e.message, true);
    } finally {
      ocupado = false;
    }
  }

  let armado = null;
  async function quitarCliente(boton, c) {
    if (!armado) {
      boton.classList.add("seguro");
      boton.textContent = "¿Seguro? Ya no saldrá para prestarle";
      armado = setTimeout(() => { armado = null; boton.classList.remove("seguro"); boton.textContent = "Quitar de la lista"; }, 3500);
      return;
    }
    clearTimeout(armado);
    armado = null;
    try {
      await api("/api/clientes/" + c.id + "/quitar", {});
      aviso("«" + c.nombre + "» ya no está en la lista. Su historia se queda guardada.");
      elegido = null;
      pintarVacio();
      await cargar(false);
    } catch (e) {
      aviso(e.message, true);
    }
  }

  function cuando(texto) {
    const f = C.fecha(texto);
    const hoy = new Date();
    const ayer = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - 1);
    const hora = f.toLocaleTimeString("es-MX", { hour: "numeric", minute: "2-digit" });
    if (f.toDateString() === hoy.toDateString()) return "hoy " + hora;
    if (f.toDateString() === ayer.toDateString()) return "ayer " + hora;
    return f.toLocaleDateString("es-MX", { day: "numeric", month: "short" });
  }

  function salirDeNuevo() {
    nuevo = false;
    if (elegido) pintarDetalle(); else pintarVacio();
  }

  function cambiarFiltro(f) {
    filtro = f;
    $("filtros").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x.dataset.f === f));
  }

  // ------------------------------------------------------------ eventos

  $("filtros").addEventListener("click", (e) => {
    const b = e.target.closest("[data-f]");
    if (!b) return;
    cambiarFiltro(b.dataset.f);
    cargar(true);
  });
  let espera = null;
  $("filtro-texto").addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(() => cargar(true), 120); });
  $("nuevo").onclick = () => { nuevo = true; pintarDetalle(); };

  T.montar({
    seccion: "fiado",
    alElegir: () => aviso("Para vender ese producto, abre Vender (abajo a la izquierda)."),
    codigoNuevo: () => aviso("Ese código no está registrado. Dalo de alta en Vender o en Productos."),
    escribirBusca: () => false,
    antesDeSalir: () => null,
  });

  document.addEventListener("keydown", (e) => {
    if (T.capaAbierta()) return;
    if (e.key === "Escape" && nuevo) salirDeNuevo();
    if (e.key === "/" && !(e.target.matches && e.target.matches("input"))) { e.preventDefault(); $("filtro-texto").focus(); }
  });

  cargar(false);
})();
