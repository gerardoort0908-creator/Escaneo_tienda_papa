/* Pantalla de Productos: buscar, ver existencias, cambiar precio y costo, contar y dar de alta. */
(function () {
  "use strict";
  const V = window.Venta;
  const I = window.Inventario;
  const T = window.Tienda;
  const { el, aviso, api } = T;
  const $ = (id) => document.getElementById(id);

  let productos = [];
  let filtro = "todos";
  let elegido = null; // el producto que se ve a la derecha (con historial)
  let modoNuevo = null; // { codigo } mientras se da de alta uno nuevo
  let consulta = 0;

  // ------------------------------------------------------------ lista

  async function cargar(mantener) {
    const n = ++consulta;
    const q = $("filtro-texto").value.trim();
    let d;
    try { d = await api("/api/inventario?filtro=" + filtro + "&q=" + encodeURIComponent(q)); } catch (e) { aviso(e.message, true); return; }
    if (n !== consulta) return;
    productos = d.productos;
    $("n-acabando").textContent = d.acabando;
    $("n-acabados").textContent = d.acabados;
    $("cuantos").textContent = productos.length + (productos.length === 1 ? " producto" : " productos");
    pintarLista();
    if (!mantener && !elegido && !modoNuevo && productos.length) elegir(productos[0].id);
    if (!productos.length && !elegido && !modoNuevo) pintarVacio();
  }

  function pintarLista() {
    const lista = $("lista");
    lista.replaceChildren();
    if (!productos.length) {
      lista.appendChild(el("p", "vacio", $("filtro-texto").value.trim() ? "No hay productos con ese nombre."
        : filtro === "todos" ? "Todavía no hay productos. Toca «Nuevo producto» o escanea uno." : "Ninguno por aquí."));
      return;
    }
    for (const p of productos) {
      const nivel = I.NIVELES[p.nivel];
      const fila = el("button", "rw" + (elegido && elegido.id === p.id ? " sel" : "") + (p.activo ? "" : " inactivo"));
      fila.setAttribute("role", "option");
      fila.style.setProperty("--m", nivel.color);
      const n = el("span", "n");
      const barra = el("span", "meter");
      const relleno = el("i");
      relleno.style.width = Math.max(3, I.llenado(p.existencia, p.minimo) * 100) + "%";
      barra.appendChild(relleno);
      n.append(el("b", "", p.nombre), barra);
      const tag = el("span", "tag" + (p.nivel === "bien" ? "" : " aviso"), T.existenciaTexto(p.existencia, p.unidad) + " · ");
      tag.appendChild(el("span", "estado", nivel.texto));
      fila.append(T.tile(p.nombre), n, tag);
      fila.onclick = () => elegir(p.id);
      lista.appendChild(fila);
    }
  }

  async function elegir(id) {
    if (hayCambios() && !(await confirmarDescarte())) return;
    try { elegido = await api("/api/inventario/" + id); } catch (e) { aviso(e.message, true); return; }
    modoNuevo = null;
    pintarLista();
    pintarDetalle();
    const sel = $("lista").querySelector(".sel");
    if (sel) sel.scrollIntoView({ block: "nearest" });
  }

  // Si hay cambios sin guardar, el primer intento de irse solo avisa; el segundo sí se va.
  let avisadoDescarte = false;
  async function confirmarDescarte() {
    if (avisadoDescarte) { avisadoDescarte = false; return true; }
    avisadoDescarte = true;
    setTimeout(() => { avisadoDescarte = false; }, 4000);
    aviso("Tienes cambios sin guardar. Guárdalos, o toca otra vez para dejarlos.", true);
    return false;
  }

  // ------------------------------------------------------------ detalle

  function pintarVacio() {
    const d = $("detalle");
    d.replaceChildren();
    const v = el("div", "vacio-grande");
    v.append(el("span", "", "Escanea un producto con el celular o elige uno de la lista para ver sus datos."));
    d.appendChild(v);
  }

  /** Arma el detalle; sirve igual para un producto existente o para uno nuevo. */
  function pintarDetalle() {
    const p = modoNuevo
      ? { id: null, nombre: "", codigo: modoNuevo.codigo || "", unidad: modoNuevo.unidad || "pieza", precio: 0, costo: 0, existencia: 0, minimo: 0, activo: true, historial: [] }
      : elegido;
    const kg = p.unidad === "kg";
    const d = $("detalle");
    d.replaceChildren();

    // Nombre y código
    const ficha = el("div", "ficha");
    const nombre = el("input", "nombre-in");
    nombre.id = "d-nombre";
    nombre.value = p.nombre;
    nombre.maxLength = 80;
    nombre.placeholder = "Nombre del producto";
    nombre.setAttribute("aria-label", "Nombre");
    const codigo = el("input", "codigo-in");
    codigo.id = "d-codigo";
    codigo.value = p.codigo || "";
    codigo.maxLength = 64;
    codigo.placeholder = "Sin código (escanéalo para ponérselo)";
    codigo.setAttribute("aria-label", "Código de barras");
    const nc = el("div");
    nc.append(nombre, codigo);
    ficha.append(T.tile(p.nombre || "?"), nc);
    nombre.addEventListener("input", () => { ficha.firstChild.replaceWith(T.tile(nombre.value || "?")); });
    d.appendChild(ficha);

    if (modoNuevo) {
      const u = el("div", "segin");
      for (const [valor, texto] of [["pieza", "Por pieza"], ["kg", "Por kilo (granel)"]]) {
        const b = el("button", valor === p.unidad ? "on" : "", texto);
        b.type = "button";
        b.onclick = () => { modoNuevo.unidad = valor; guardarBorrador(); pintarDetalle(); };
        u.appendChild(b);
      }
      d.appendChild(u);
    }

    // Te cuesta / Lo vendes en
    const precios = el("div", "price2");
    const campo = (clase, etiqueta, id, valor, ayuda) => {
      const f = el("label", "pf " + clase);
      const caja = el("div");
      const input = el("input");
      input.id = id;
      input.inputMode = "decimal";
      input.autocomplete = "off";
      input.value = valor;
      caja.append(el("em", "", "$"), input);
      f.append(el("span", "", etiqueta), caja, el("small", "", ayuda));
      precios.appendChild(f);
      return input;
    };
    const costo = campo("", "Te cuesta", "d-costo", p.costo ? V.pesos(p.costo).slice(1) : "", kg ? "el kilo" : "cada uno");
    const precio = campo("vende", "Lo vendes en", "d-precio", p.precio ? V.pesos(p.precio).slice(1) : "", kg ? "el kilo · sin centavos" : "cada uno · sin centavos");
    d.appendChild(precios);

    const gana = el("div", "gain");
    gana.id = "d-gana";
    d.appendChild(gana);

    // Existencia y mínimo
    const nivel = I.NIVELES[I.nivel(p.existencia, p.minimo)];
    const ex = el("div", "existe");
    ex.style.setProperty("--m", modoNuevo ? "var(--tx2)" : p.existencia > p.minimo ? "var(--tx)" : nivel.color);
    const izq = el("div");
    const cuanto = el("div", "cuanto", modoNuevo ? "0" : (kg ? V.cantidadTexto(p.existencia, "kg").replace(" kg", "") : String(p.existencia)));
    cuanto.appendChild(el("small", "", kg ? "kg" : (p.existencia === 1 ? "pieza" : "piezas")));
    izq.append(el("div", "lbl", modoNuevo ? "Hay ahora (se suma en Llegó mercancía)" : "Hay ahora · " + nivel.texto), cuanto);
    if (!modoNuevo) {
      const llegaron = el("button", "sumar", kg ? "+ Llegaron kilos" : "+ Llegaron piezas");
      llegaron.id = "d-llegaron";
      llegaron.onclick = () => abrirLlegada(d, p);
      izq.appendChild(llegaron);
    }
    const min = el("div", "min");
    let minimo = p.minimo;
    const paso = el("span", "step");
    const menos = el("button", "", "−");
    const mas = el("button", "", "+");
    const valorMin = el("span", "", "");
    const pintarMin = () => { valorMin.textContent = kg ? V.cantidadTexto(minimo, "kg") : String(minimo); revisar(); };
    menos.onclick = () => { minimo = Math.max(0, minimo - (kg ? 500 : 1)); pintarMin(); };
    mas.onclick = () => { minimo += kg ? 500 : 1; pintarMin(); };
    menos.setAttribute("aria-label", "Bajar el mínimo");
    mas.setAttribute("aria-label", "Subir el mínimo");
    paso.append(menos, valorMin, mas);
    min.append(el("span", "", "Avísame cuando queden"), paso, el("span", "nota-min", "Esto no suma piezas"));
    ex.append(izq, min);
    d.appendChild(ex);

    // Guardar
    const guardar = el("button", "act", modoNuevo ? "Dar de alta" : "Guardar cambios");
    guardar.id = "d-guardar";
    const acciones = el("div", "acciones");
    if (!modoNuevo) {
      const contar = el("button", "boton", "Contar lo que hay");
      contar.onclick = () => abrirConteo(d, p);
      const des = el("button", "boton" + (p.activo ? " peligro" : ""), p.activo ? "Ya no lo vendo" : "Volver a venderlo");
      des.onclick = () => activar(des, p);
      acciones.append(contar, des);
    } else {
      const cancelar = el("button", "boton", "Cancelar");
      cancelar.onclick = () => { modoNuevo = null; borrador = null; if (elegido) pintarDetalle(); else pintarVacio(); };
      acciones.appendChild(cancelar);
    }

    const pie = el("div", "mt");
    pie.style.display = "grid";
    pie.style.gap = "1rem";
    pie.append(guardar, acciones);
    if (!modoNuevo && p.historial && p.historial.length) pie.prepend(historia(p));
    d.appendChild(pie);

    // ¿Cambió algo? Así el botón se enciende solo cuando hay algo que guardar.
    function leer() {
      return {
        nombre: nombre.value.trim(), codigo: codigo.value.trim(),
        precio: precio.value.replace(/[$,\s]/g, ""), costo: costo.value.replace(/[$,\s]/g, ""), minimo,
      };
    }
    function revisar() {
      const v = leer();
      const precioC = /^\d+$/.test(v.precio) ? Number(v.precio) * 100 : null;
      const costoC = v.costo === "" ? 0 : V.leerMonto(v.costo);
      if (precioC && costoC !== null) {
        const g = I.ganancia(precioC, costoC);
        gana.className = "gain" + (g.pierde ? " mal" : "");
        gana.replaceChildren();
        const texto = el("span");
        if (g.pierde) texto.append("Pierdes ", el("b", "", V.pesos(-g.porUnidad)), kg ? " por kilo. Revisa el precio." : " por pieza. Revisa el precio.");
        else if (!costoC) texto.append("Falta el costo para saber cuánto ganas.");
        else texto.append("Ganas ", el("b", "", V.pesos(g.porUnidad)), (kg ? " por kilo" : " por pieza") + " (" + g.porcentaje + "% del precio)");
        const barra = el("div", "gbar");
        const i = el("i");
        i.style.width = (costoC ? Math.max(3, Math.min(100, Math.abs(g.porcentaje) * 2)) : 0) + "%";
        barra.appendChild(i);
        gana.append(texto, barra);
      } else {
        gana.className = "gain";
        gana.replaceChildren(el("span", "", "Escribe el precio en pesos cerrados (22, 88) y el costo con centavos si hace falta (15.50)."));
      }
      const cambios = modoNuevo ? v.nombre && precioC : (
        v.nombre !== p.nombre || v.codigo !== (p.codigo || "") || precioC !== p.precio || costoC !== p.costo || minimo !== p.minimo);
      guardar.classList.toggle("off", !cambios);
      return v;
    }
    hayCambios = () => !guardar.classList.contains("off") && !modoNuevo;
    for (const i of [nombre, codigo, precio, costo]) i.addEventListener("input", () => { revisar(); guardarBorrador(); });
    for (const i of [nombre, codigo, precio, costo]) i.addEventListener("keydown", (e) => { if (e.key === "Enter") guardar.click(); });
    guardarBorrador = () => {
      if (modoNuevo) borrador = { nombre: nombre.value, precio: precio.value, costo: costo.value };
    };
    if (modoNuevo && borrador) { nombre.value = borrador.nombre; precio.value = borrador.precio; costo.value = borrador.costo; }

    guardar.onclick = async () => {
      const v = revisar();
      if (guardar.classList.contains("off")) return;
      if (!/^\d+$/.test(v.precio)) { aviso("El precio de venta va en pesos cerrados, sin centavos (por ejemplo 22)", true); precio.focus(); return; }
      if (v.costo !== "" && V.leerMonto(v.costo) === null && v.costo !== "0") { aviso("Escribe el costo como 15 o 15.50", true); costo.focus(); return; }
      const costoTexto = v.costo === "" ? "0" : v.costo;
      try {
        if (modoNuevo) {
          elegido = await api("/api/inventario", {
            nombre: v.nombre, precio: v.precio, costo: costoTexto, unidad: p.unidad, codigo: v.codigo || null, minimo,
          });
          modoNuevo = null;
          borrador = null;
          aviso("«" + elegido.nombre + "» quedó registrado. Súmale piezas en Llegó mercancía.");
        } else {
          elegido = await api("/api/inventario/" + p.id, {
            nombre: v.nombre, precio: v.precio, costo: costoTexto, codigo: v.codigo, minimo,
          });
          aviso(elegido.precio !== p.precio ? "Guardado. Las ventas pasadas no cambian." : "Guardado");
        }
        await cargar(true);
        pintarDetalle();
      } catch (e) {
        aviso(e.message, true);
      }
    };

    pintarMin();
    if (modoNuevo) nombre.focus();
  }

  let hayCambios = () => false;
  let borrador = null;
  let guardarBorrador = () => {};

  function historia(p) {
    const caja = el("div", "historia");
    for (const h of p.historial.slice(0, 3)) {
      const fila = el("div");
      const fecha = new Date(h.cuando.replace(" ", "T"));
      const cuando = isNaN(fecha) ? "" : fecha.toLocaleDateString("es-MX", { day: "numeric", month: "short" });
      fila.append(el("span", "", cuando + " · " + h.motivo), el("b", "", "vende " + V.pesos(h.precio_venta) + " · cuesta " + V.pesos(h.costo)));
      caja.appendChild(fila);
    }
    return caja;
  }

  function abrirConteo(d, p) {
    if (d.querySelector(".contar")) return;
    const kg = p.unidad === "kg";
    const caja = el("form", "contar");
    const fila = el("div", "fila");
    const input = el("input");
    input.inputMode = "decimal";
    input.placeholder = kg ? "kilos" : "piezas";
    input.setAttribute("aria-label", "Cuántos hay");
    fila.append(el("span", "", "Conté y hay"), input, el("span", "", kg ? "kg" : "piezas"));
    const motivos = el("div", "fila");
    let motivo = "Conteo";
    motivos.appendChild(el("span", "", "Por:"));
    for (const m of ["Conteo", "Merma", "Caducado", "Se rompió"]) {
      const b = el("button", "chip" + (m === motivo ? " on" : ""), m);
      b.type = "button";
      b.onclick = () => { motivo = m; motivos.querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", c === b)); };
      motivos.appendChild(b);
    }
    const ok = el("button", "boton", "Guardar conteo");
    ok.type = "submit";
    const no = el("button", "chip", "Cancelar");
    no.type = "button";
    no.onclick = () => caja.remove();
    const botones = el("div", "fila");
    botones.append(ok, no);
    caja.append(fila, motivos, botones);
    caja.onsubmit = async (e) => {
      e.preventDefault();
      const texto = input.value.trim();
      const contado = kg ? (texto === "0" ? 0 : I.leerKilos(texto)) : (/^\d+$/.test(texto) ? Number(texto) : null);
      if (contado === null) { aviso(kg ? "Escribe los kilos, por ejemplo 12.5" : "Escribe cuántas piezas hay", true); input.focus(); return; }
      try {
        const r = await api("/api/inventario/" + p.id + "/contar", { contado, motivo });
        elegido = r;
        const dif = r.diferencia;
        aviso(dif === 0 ? "Coincide con lo que decía el sistema" : (dif > 0 ? "Había " : "Faltaban ") + T.existenciaTexto(Math.abs(dif), p.unidad) + ". Ya quedó corregido.");
        await cargar(true);
        pintarDetalle();
      } catch (err) {
        aviso(err.message, true);
      }
    };
    d.querySelector(".mt").prepend(caja);
    input.focus();
  }

  /** Sumar lo que llegó sin salir de Productos: una ventanita con cuántas llegaron y cuánto costaron. */
  function abrirLlegada(d, p) {
    const kg = p.unidad === "kg";
    const capa = el("div", "capa");
    const panel = el("form", "panel glass llegada");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Llegaron piezas");
    const titulo = el("h3", "", p.nombre);
    const sub = el("p", "sub", "Hay " + T.existenciaTexto(p.existencia, p.unidad) + ". Escribe lo que llegó y se suma.");
    const cant = el("input");
    cant.inputMode = "decimal";
    cant.autocomplete = "off";
    const costo = el("input");
    costo.inputMode = "decimal";
    costo.autocomplete = "off";
    costo.value = p.costo ? (p.costo / 100).toFixed(p.costo % 100 ? 2 : 0) : "";
    const campoCant = el("label", "campo");
    campoCant.append(el("span", "", kg ? "¿Cuántos kilos llegaron?" : "¿Cuántas piezas llegaron?"), cant);
    const campoCosto = el("label", "campo");
    const pre = el("span", "pre", "$");
    pre.appendChild(costo);
    campoCosto.append(el("span", "", kg ? "¿Cuánto te costó cada kilo?" : "¿Cuánto te costó cada una?"), pre);
    const dos = el("div", "dos");
    dos.append(campoCant, campoCosto);
    const total = el("p", "total-llegada", "");
    const error = el("p", "error", "");
    error.setAttribute("aria-live", "polite");
    const no = el("button", "act soft", "Cancelar");
    no.type = "button";
    const si = el("button", "act", "Sumar");
    si.type = "submit";
    const acts = el("div", "acts2");
    acts.append(no, si);
    panel.append(titulo, sub, dos, total, error, acts);
    capa.appendChild(panel);
    (document.getElementById("alta") || document.body).parentNode.appendChild(capa);

    const leer = () => {
      const t = cant.value.trim();
      const cantidad = kg ? I.leerKilos(t) : (/^\d+$/.test(t) && Number(t) > 0 ? Number(t) : null);
      const c = costo.value.trim();
      const centavos = c === "" || c === "0" ? 0 : V.leerMonto(c);
      return { cantidad, centavos };
    };
    const pintarTotal = () => {
      const { cantidad, centavos } = leer();
      total.textContent = cantidad && centavos
        ? "Pagaste " + V.pesos(Math.round((cantidad * centavos) / (kg ? 1000 : 1))) + " en total"
        : "";
    };
    cant.addEventListener("input", pintarTotal);
    costo.addEventListener("input", pintarTotal);
    const cerrar = () => { capa.remove(); document.removeEventListener("keydown", tecla, true); };
    const tecla = (e) => { if (e.key === "Escape") { e.stopImmediatePropagation(); cerrar(); } };
    document.addEventListener("keydown", tecla, true);
    no.onclick = cerrar;
    capa.addEventListener("mousedown", (e) => { if (e.target === capa) cerrar(); });

    panel.onsubmit = async (e) => {
      e.preventDefault();
      const { cantidad, centavos } = leer();
      if (!cantidad) { error.textContent = kg ? "Escribe los kilos que llegaron, por ejemplo 12.5" : "Escribe cuántas piezas llegaron"; cant.focus(); return; }
      if (centavos === null) { error.textContent = "Escribe el costo como 15 o 15.50"; costo.focus(); return; }
      si.classList.add("off");
      try {
        await api("/api/mercancia", { operacion: T.nuevoId(), renglones: [{ producto_id: p.id, cantidad, costo: centavos }], nota: null });
        cerrar();
        aviso("Listo: se sumaron " + T.existenciaTexto(cantidad, p.unidad) + " de «" + p.nombre + "».");
        elegido = await api("/api/inventario/" + p.id);
        await cargar(true);
        pintarDetalle();
      } catch (err) {
        si.classList.remove("off");
        error.textContent = err.message;
      }
    };
    cant.focus();
  }

  let armado = null;
  async function activar(boton, p) {
    if (p.activo && !armado) {
      boton.classList.add("seguro");
      boton.textContent = "¿Seguro? Ya no saldrá para vender";
      armado = setTimeout(() => { armado = null; boton.classList.remove("seguro"); boton.textContent = "Ya no lo vendo"; }, 3500);
      return;
    }
    clearTimeout(armado);
    armado = null;
    try {
      elegido = await api("/api/inventario/" + p.id + (p.activo ? "/desactivar" : "/reactivar"), {});
      aviso(p.activo ? "Ya no saldrá para vender. Su historia se queda guardada." : "Otra vez a la venta");
      await cargar(true);
      pintarDetalle();
    } catch (e) {
      aviso(e.message, true);
    }
  }

  function nuevo(codigo) {
    modoNuevo = { codigo: codigo || "", unidad: "pieza" };
    borrador = null;
    pintarLista();
    pintarDetalle();
  }

  // ------------------------------------------------------------ eventos

  $("filtros").addEventListener("click", (e) => {
    const b = e.target.closest("[data-f]");
    if (!b) return;
    filtro = b.dataset.f;
    $("filtros").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    cargar(true);
  });
  let espera = null;
  $("filtro-texto").addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(() => cargar(true), 120); });
  $("nuevo").onclick = () => nuevo("");

  T.montar({
    seccion: "productos",
    alElegir: (p) => {
      // Si está dando de alta uno nuevo y escanea, el código es para ese producto.
      if (modoNuevo && !p) return;
      elegir(p.id);
    },
    codigoNuevo: (codigo) => {
      if (modoNuevo) { $("d-codigo").value = codigo; $("d-codigo").dispatchEvent(new Event("input")); T.bip(false); return; }
      if (elegido && !elegido.codigo) {
        // El producto que está a la vista no tiene código: se lo ponemos.
        $("d-codigo").value = codigo;
        $("d-codigo").dispatchEvent(new Event("input"));
        aviso("Código puesto. Toca «Guardar cambios» para que se quede.");
        T.bip(false);
        return;
      }
      T.bip(true);
      nuevo(codigo);
      aviso("Ese código no está registrado. Llena los datos para darlo de alta.");
    },
    escribirBusca: () => false,
    antesDeSalir: () => (hayCambios() || modoNuevo ? "Primero guarda o cancela los cambios del producto" : null),
  });

  document.addEventListener("keydown", (e) => {
    if (T.capaAbierta()) return;
    if (e.key === "Escape" && modoNuevo) { modoNuevo = null; borrador = null; if (elegido) pintarDetalle(); else pintarVacio(); }
    if (e.key === "/" && !(e.target.matches && e.target.matches("input"))) { e.preventDefault(); $("filtro-texto").focus(); }
  });

  const deLaUrl = new URLSearchParams(location.search).get("filtro");
  if (deLaUrl && document.querySelector(`[data-f="${deLaUrl}"]`)) document.querySelector(`[data-f="${deLaUrl}"]`).click();
  else cargar(false);
})();
