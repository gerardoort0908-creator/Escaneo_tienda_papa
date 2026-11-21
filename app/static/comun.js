/* Lo que comparten todas las pantallas: barra de arriba, menú de abajo, buscar, conectar el
   celular, producto nuevo, avisos y la llegada de escaneos. Cada pantalla llama Tienda.montar(). */
(function () {
  "use strict";
  const V = window.Venta;
  const L = window.Logica;
  const $ = (id) => document.getElementById(id);

  const TONOS = [
    ["#FF7A62", "#B9141B"], ["#FFE07A", "#E08B0B", 1], ["#A6DAFF", "#2A78C9"], ["#F0B67E", "#8E501C"],
    ["#8BD177", "#357A27"], ["#FFB3D1", "#C9457F"], ["#B79BE8", "#5B3F9A"], ["#FFF6E2", "#D8AC6C", 1],
    ["#7FE0D0", "#17806F"], ["#F6D58E", "#C9963C", 1],
  ];

  const SECCIONES = [
    ["vender", "/vender", "Vender", '<path d="M3 5h2l2.2 10.2a2 2 0 0 0 2 1.6h7.6a2 2 0 0 0 2-1.5L20.5 8H6.2"/><circle cx="10" cy="20" r="1.2"/><circle cx="17" cy="20" r="1.2"/>'],
    ["mercancia", "/mercancia", "Llegó mercancía", '<path d="M3 8.5 12 4l9 4.5v7L12 20l-9-4.5z"/><path d="M3 8.5 12 13l9-4.5M12 13v7"/>'],
    ["productos", "/productos", "Productos", '<path d="M4 7V5a1 1 0 0 1 1-1h2M17 4h2a1 1 0 0 1 1 1v2M20 17v2a1 1 0 0 1-1 1h-2M7 20H5a1 1 0 0 1-1-1v-2"/><path d="M8 8v8M11 8v8M14 8v8M16.5 8v8"/>'],
    ["fiado", "/fiado", "Préstamos", '<path d="M5 4h11l3 3v13H5z"/><path d="M9 10h6M9 14h6"/>'],
    ["caja", "/caja", "Corte de caja", '<rect x="3" y="9" width="18" height="11" rx="1.5"/><path d="M7 9V5h10v4M3 14h18"/><path d="M10 6.8h4"/>'],
    ["reportes", "/reportes", "Reportes", '<path d="M4 20V10M10 20V4M16 20v-7"/>'],
  ];

  const LUPA = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg>';

  const MARCO = `
  <div class="amb" aria-hidden="true"><i></i><i></i></div>
  <header class="top">
    <span class="brand">
      <svg viewBox="0 0 32 32" aria-hidden="true"><defs><linearGradient id="marca" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F4DDA6"/><stop offset="1" stop-color="#B8924A"/></linearGradient></defs><rect width="32" height="32" rx="9" fill="url(#marca)"/><path d="M7 13h18l-2-5H9z" fill="#2A1E08"/><path d="M7 13c0 1.7 1.3 3 3 3s3-1.3 3-3c0 1.7 1.3 3 3 3s3-1.3 3-3c0 1.7 1.3 3 3 3s3-1.3 3-3" fill="none" stroke="#2A1E08" stroke-width="1.4" opacity=".85"/><path d="M9 17v7h14v-7M14 24v-4h4v4" fill="none" stroke="#2A1E08" stroke-width="1.6" stroke-linejoin="round" opacity=".85"/></svg>
      Tu tienda
    </span>
    <span class="aviso-ejemplo" id="aviso-ejemplo" hidden>Modo de práctica: nada de esto es real</span>
    <span class="r">
      <button class="cel" id="cel" data-on="false" title="Conectar el celular">
        <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="2.5" width="12" height="19" rx="3"/><path class="ck" d="m9 12 2.2 2.2L15.5 10"/><path class="qr" d="M9.5 9.5h2v2h-2zM12.5 12.5h2v2h-2z"/></svg>
        <span id="cel-txt">Conectar celular</span>
      </button>
      <span id="reloj" class="reloj"></span>
    </span>
  </header>`;

  const CAPAS = `
  <nav class="dock glass" id="dock" aria-label="Secciones"></nav>

  <div class="capa" id="busqueda" hidden>
    <div class="panel glass" role="dialog" aria-label="Buscar producto">
      <label class="searchin">${LUPA}
        <input id="q" autocomplete="off" spellcheck="false" placeholder="Nombre o código del producto" aria-label="Buscar producto">
        <kbd>Esc</kbd>
      </label>
      <div class="rows" id="resultados" role="listbox"></div>
    </div>
  </div>

  <div class="capa" id="alta" hidden>
    <form class="panel glass" id="alta-form" role="dialog" aria-label="Producto nuevo">
      <h3>Este código no está registrado</h3>
      <p class="sub" id="alta-sub"></p>
      <div class="codigo-nuevo" id="alta-codigo"></div>
      <label class="campo"><span>Nombre</span><input id="alta-nombre" maxlength="80" autocomplete="off" required></label>
      <div class="dos">
        <label class="campo"><span>Lo vendes en</span><span class="pre">$<input id="alta-precio" inputmode="numeric" autocomplete="off" required></span></label>
        <div class="campo"><span>Se vende por</span>
          <div class="segin" id="alta-unidad"><button type="button" data-u="pieza" class="on">Pieza</button><button type="button" data-u="kg">Kilo</button></div>
        </div>
      </div>
      <label class="campo" id="alta-costo-campo" hidden><span>Te cuesta</span><span class="pre">$<input id="alta-costo" inputmode="decimal" autocomplete="off"></span></label>
      <p class="error" id="alta-error" aria-live="polite"></p>
      <div class="acts2">
        <button type="button" class="act soft" id="alta-no">Ahora no</button>
        <button type="submit" class="act" id="alta-si">Guardar</button>
      </div>
    </form>
  </div>

  <div class="capa" id="conectar" hidden>
    <div class="panel glass conectar" role="dialog" aria-label="Conectar el celular">
      <img id="qr" alt="Código QR para conectar el celular" width="220" height="220">
      <div>
        <h3>Conecta el celular</h3>
        <ol class="sub">
          <li>El celular debe estar en el mismo WiFi que esta computadora.</li>
          <li>Abre la cámara del celular y apunta a este código.</li>
          <li>Agrégala a la <b>pantalla de inicio</b> del celular (ahí te dice cómo). Así funciona aunque esta computadora esté apagada.</li>
        </ol>
        <p class="sub" id="sin-wifi" hidden>Esta computadora no parece estar en un WiFi.</p>
        <button class="act soft" id="conectar-cerrar">Listo</button>
      </div>
    </div>
  </div>

  <div class="capa" id="clientes" hidden>
    <div class="panel glass" role="dialog" aria-labelledby="cl-titulo">
      <div class="cl-cab"><h3 id="cl-titulo"></h3><span class="sub" id="cl-sub"></span></div>
      <label class="searchin">${LUPA}
        <input id="cq" autocomplete="off" spellcheck="false" placeholder="Escribe el nombre del cliente" aria-label="Nombre del cliente">
        <kbd>Esc</kbd>
      </label>
      <div class="rows" id="cl-lista" role="listbox"></div>
    </div>
  </div>

  <div class="toast glass" id="toast" role="status" aria-live="polite"><i></i><span></span></div>`;

  // ------------------------------------------------------------ utilidades

  function el(etiqueta, clase, texto) {
    const e = document.createElement(etiqueta);
    if (clase) e.className = clase;
    if (texto !== undefined) e.textContent = texto;
    return e;
  }

  /** Cifra grande: $ chiquito, pesos grandes y centavos chiquitos (solo si hay). */
  function numHTML(contenedor, centavos) {
    const p = V.partes(centavos);
    contenedor.replaceChildren(el("span", "cur", "$"), document.createTextNode(p.entero));
    if (p.centavos) contenedor.appendChild(el("span", "cts", "." + p.centavos));
  }

  /** Miniatura de color: cada producto toma siempre el mismo color, según su nombre. */
  function tile(nombre) {
    let h = 0;
    for (const c of nombre) h = (h * 31 + c.codePointAt(0)) >>> 0;
    const [c1, c2, claro] = TONOS[h % TONOS.length];
    const t = el("span", "tile" + (claro ? " claro" : ""), (nombre.trim()[0] || "?").toUpperCase());
    t.style.setProperty("--c1", c1);
    t.style.setProperty("--c2", c2);
    return t;
  }

  function precioTexto(p) {
    return V.pesos(p.precio) + (p.unidad === "kg" ? " el kilo" : " c/u");
  }

  /** Existencia en palabras: "24 piezas", "1 pieza", "22½ kg". */
  function existenciaTexto(cantidad, unidad) {
    if (unidad === "kg") return V.cantidadTexto(cantidad, "kg");
    return cantidad + (Math.abs(cantidad) === 1 ? " pieza" : " piezas");
  }

  let temporizadorToast = null;
  function aviso(texto, malo) {
    const t = $("toast");
    t.querySelector("span").textContent = texto;
    t.classList.toggle("mal", !!malo);
    t.classList.add("show");
    clearTimeout(temporizadorToast);
    temporizadorToast = setTimeout(() => t.classList.remove("show"), malo ? 4200 : 2600);
  }

  // Un "bip" suave al agregar; uno grave si algo salió mal. Así no hace falta voltear a ver.
  let audio = null;
  function bip(malo) {
    try {
      audio = audio || new AudioContext();
      const o = audio.createOscillator();
      const g = audio.createGain();
      o.type = "sine";
      o.frequency.value = malo ? 220 : 1320;
      g.gain.setValueAtTime(0.0001, audio.currentTime);
      g.gain.exponentialRampToValueAtTime(0.12, audio.currentTime + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, audio.currentTime + (malo ? 0.35 : 0.12));
      o.connect(g).connect(audio.destination);
      o.start();
      o.stop(audio.currentTime + 0.4);
    } catch (_) { /* sin sonido no pasa nada */ }
  }

  async function api(ruta, datos) {
    const opciones = datos === undefined ? {} : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos),
    };
    const r = await fetch(ruta, opciones);
    const cuerpo = await r.json().catch(() => ({}));
    if (!r.ok) {
      const detalle = typeof cuerpo.detail === "string" ? cuerpo.detail : "Revisa los datos e intenta otra vez.";
      const error = new Error(detalle);
      error.estado = r.status;
      throw error;
    }
    return cuerpo;
  }

  function nuevoId() { return L.nuevoId(crypto).replace(/[^A-Za-z0-9_-]/g, ""); }

  // ------------------------------------------------------------ capas

  const CAPAS_IDS = ["busqueda", "alta", "conectar", "clientes"];
  function capaAbierta() { return CAPAS_IDS.find((id) => !$(id).hidden) || null; }
  function cerrarCapa(id) {
    $(id).hidden = true;
    if (document.activeElement) document.activeElement.blur();
  }

  // ------------------------------------------------------------ buscar

  let config = {};
  let resultados = [];
  let elegido = 0;
  let consulta = 0;
  let espera = null;

  function abrirBusqueda(inicial) {
    if (config.antesDeBuscar) config.antesDeBuscar();
    $("busqueda").hidden = false;
    $("q").value = inicial || "";
    $("q").focus();
    buscar();
  }

  async function buscar() {
    const n = ++consulta;
    const texto = $("q").value.trim();
    let lista = [];
    try { lista = await api("/api/productos?q=" + encodeURIComponent(texto)); } catch (_) { lista = []; }
    if (n !== consulta) return; // ya llegó otra búsqueda más nueva
    resultados = lista;
    elegido = 0;
    pintarResultados(texto);
  }

  function pintarResultados(texto) {
    const caja = $("resultados");
    caja.replaceChildren();
    if (!resultados.length) {
      caja.appendChild(el("p", "vacio", texto
        ? (/^\d{6,}$/.test(texto) ? "Ese código no está registrado. Presiona Enter para darlo de alta." : "No hay productos con ese nombre.")
        : "Todavía no hay productos registrados."));
      return;
    }
    resultados.forEach((p, i) => {
      const fila = el("button", "rw" + (i === elegido ? " sel" : ""));
      fila.setAttribute("role", "option");
      const n = el("span", "n");
      n.append(el("b", "", p.nombre), el("small", "", (p.codigo ? p.codigo + " · " : "") + "hay " + existenciaTexto(p.existencia, p.unidad)));
      fila.append(tile(p.nombre), n, el("span", "p", precioTexto(p)));
      fila.onclick = () => elegir(i);
      caja.appendChild(fila);
    });
  }

  function elegir(i) {
    const p = resultados[i];
    if (!p) return;
    cerrarCapa("busqueda");
    config.alElegir(p);
  }

  /** Un código tecleado o escaneado: el producto, o la ventanita de alta si no existe. */
  async function porCodigo(codigo) {
    try {
      config.alElegir(await api("/api/productos/codigo/" + encodeURIComponent(codigo)));
    } catch (error) {
      if (error.estado === 404) config.codigoNuevo(codigo);
      else aviso(error.message, true);
    }
  }

  // ------------------------------------------------------------ producto nuevo (ventanita)

  let unidadAlta = "pieza";
  let codigoAlta = null;
  let altaLista = null;
  let altaConCosto = false;

  /** Abre la ventanita. `alGuardar(producto, costoCentavos)` recibe lo que se dio de alta. */
  function abrirAlta(codigo, { conCosto = false, sub = "", boton = "Guardar", alGuardar }) {
    bip(true);
    codigoAlta = codigo;
    altaLista = alGuardar;
    altaConCosto = conCosto;
    $("alta-codigo").textContent = codigo ? "Código " + codigo : "";
    $("alta-sub").textContent = sub;
    $("alta-si").textContent = boton;
    $("alta-costo-campo").hidden = !conCosto;
    for (const id of ["alta-nombre", "alta-precio", "alta-costo"]) $(id).value = "";
    $("alta-error").textContent = "";
    unidadDeAlta("pieza");
    $("alta").hidden = false;
    $("alta-nombre").focus();
  }

  function unidadDeAlta(u) {
    unidadAlta = u;
    $("alta-unidad").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.u === u));
    $("alta-precio").placeholder = u === "kg" ? "precio del kilo" : "";
    $("alta-costo").placeholder = u === "kg" ? "costo del kilo" : "";
  }

  async function guardarAlta(e) {
    e.preventDefault();
    const precio = $("alta-precio").value.replace(/[$,\s]/g, "");
    if (!/^\d+$/.test(precio)) {
      $("alta-error").textContent = "El precio va en pesos cerrados, sin centavos (por ejemplo 22).";
      return;
    }
    let costo = 0;
    if (altaConCosto && $("alta-costo").value.trim()) {
      costo = V.leerMonto($("alta-costo").value);
      if (costo === null) { $("alta-error").textContent = "Escribe el costo como 15 o 15.50."; return; }
    }
    try {
      const p = await api("/api/inventario", {
        nombre: $("alta-nombre").value, precio, costo: (costo / 100).toFixed(2), unidad: unidadAlta, codigo: codigoAlta,
      });
      cerrarCapa("alta");
      aviso("«" + p.nombre + "» quedó registrado");
      altaLista(p, costo);
    } catch (error) {
      $("alta-error").textContent = error.message;
    }
  }

  // ------------------------------------------------------------ elegir cliente (para fiar)

  let clientes = [];
  let clElegido = 0;
  let clConsulta = 0;
  let clListo = null;

  /** Abre la lista de clientes. `alElegir(cliente)` recibe al elegido (o al recién dado de alta). */
  function abrirClientes({ titulo, sub = "", alElegir }) {
    clListo = alElegir;
    $("cl-titulo").textContent = titulo;
    $("cl-sub").textContent = sub;
    $("cq").value = "";
    $("clientes").hidden = false;
    $("cq").focus();
    buscarClientes();
  }

  async function buscarClientes() {
    const n = ++clConsulta;
    const texto = $("cq").value.trim();
    let lista = [];
    try { lista = (await api("/api/clientes?q=" + encodeURIComponent(texto))).clientes; } catch (_) { lista = []; }
    if (n !== clConsulta) return;
    clientes = lista;
    const exacto = clientes.some((c) => c.nombre.toLocaleLowerCase() === texto.toLocaleLowerCase());
    if (texto && !exacto) clientes = [...clientes, { nuevo: texto }];
    clElegido = 0;
    pintarClientes(texto);
  }

  function pintarClientes(texto) {
    const caja = $("cl-lista");
    caja.replaceChildren();
    if (!clientes.length) {
      caja.appendChild(el("p", "vacio", "Todavía no hay clientes. Escribe el nombre para darlo de alta."));
      return;
    }
    clientes.forEach((c, i) => {
      const fila = el("button", "rw" + (i === clElegido ? " sel" : "") + (c.nuevo ? " cl-nuevo" : ""));
      fila.setAttribute("role", "option");
      const n = el("span", "n");
      if (c.nuevo) {
        const mas = el("span", "tile mas", "+");
        n.append(el("b", "", "Cliente nuevo: " + c.nuevo), el("small", "", "Se da de alta y se le presta"));
        fila.append(mas, n, el("span", "p", ""));
      } else {
        n.append(el("b", "", c.nombre), el("small", "", c.telefono || (c.saldo > 0 ? "Tiene cuenta abierta" : "No debe nada")));
        fila.append(tile(c.nombre), n, el("span", "p" + (c.saldo > 0 ? " debe" : ""), c.saldo > 0 ? "debe " + V.pesos(c.saldo) : "—"));
      }
      fila.onclick = () => elegirCliente(i);
      caja.appendChild(fila);
    });
  }

  async function elegirCliente(i) {
    let c = clientes[i];
    if (!c) return;
    if (c.nuevo) {
      try { c = await api("/api/clientes", { nombre: c.nuevo }); } catch (error) { aviso(error.message, true); return; }
    }
    cerrarCapa("clientes");
    clListo(c);
  }

  // ------------------------------------------------------------ celular y estado

  let conectadoAntes = null;
  async function revisarEstado() {
    try {
      const d = await api("/api/vender/estado");
      $("aviso-ejemplo").hidden = !d.ejemplo;
      $("cel").dataset.on = d.celular;
      $("cel-txt").textContent = d.celular ? "Celular listo" : "Conectar celular";
      if (d.celular && conectadoAntes === false && !$("conectar").hidden) {
        cerrarCapa("conectar");
        aviso("Celular conectado");
      }
      conectadoAntes = d.celular;
    } catch (_) { /* el servidor está reiniciando */ }
  }

  // Los escaneos llegan por aquí al instante, ya con el producto buscado.
  let ws = null;
  function escuchar(intento) {
    ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/pantalla");
    ws.onopen = () => { intento = 0; };
    ws.onmessage = (m) => {
      const d = JSON.parse(m.data);
      if (d.tipo === "ventas-celular") {
        aviso((d.nuevas === 1 ? "Llegó 1 venta del celular" : "Llegaron " + d.nuevas + " ventas del celular") + " (" + V.pesos(d.total) + ")");
        if (config.alLlegarVentas) config.alLlegarVentas();
        return;
      }
      if (d.tipo !== "escaneo") return;
      if (capaAbierta() === "alta") return; // está llenando un producto nuevo; no lo interrumpimos
      if (capaAbierta()) cerrarCapa(capaAbierta());
      if (d.producto) config.alElegir(d.producto);
      else config.codigoNuevo(d.codigo);
      requestAnimationFrame(() => requestAnimationFrame(() => {
        if (ws.readyState === 1) ws.send(JSON.stringify({ tipo: "mostrado", id: d.id, latencia_ms: Math.max(0, Date.now() - d.t_detectado) }));
      }));
    };
    ws.onclose = () => setTimeout(() => escuchar(intento + 1), L.esperaReintento(intento));
  }

  function reloj() {
    const d = new Date();
    let h = d.getHours();
    const m = String(d.getMinutes()).padStart(2, "0");
    const ap = h >= 12 ? "p. m." : "a. m.";
    h = h % 12 || 12;
    $("reloj").textContent = h + ":" + m + " " + ap;
  }

  function pintarDock(actual) {
    const dock = $("dock");
    for (const [clave, ruta, nombre, icono] of SECCIONES) {
      const a = el(ruta ? "a" : "span", clave === actual ? "on" : "");
      a.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${icono}</svg>`;
      a.appendChild(document.createTextNode(nombre));
      if (!ruta) {
        a.dataset.pronto = "";
        a.title = "Muy pronto";
        a.onclick = () => aviso(nombre + " llega en uno de los siguientes pasos");
      } else if (clave !== actual) {
        a.href = ruta;
        a.onclick = (e) => {
          const motivo = config.antesDeSalir && config.antesDeSalir();
          if (motivo) { e.preventDefault(); aviso(motivo, true); }
        };
      } else {
        a.setAttribute("aria-current", "page");
      }
      dock.appendChild(a);
    }
  }

  // ------------------------------------------------------------ teclado

  function teclado(e) {
    if (e.repeat && e.key === "Enter") { e.preventDefault(); return; }
    const capa = capaAbierta();
    if (e.key === "Escape") {
      if (capa) { cerrarCapa(capa); e.stopImmediatePropagation(); }
      return;
    }
    if (e.key === "F2") { e.preventDefault(); e.stopImmediatePropagation(); if (capa !== "alta") abrirBusqueda(); return; }
    if (capa) return; // la capa abierta maneja sus propias teclas (las pantallas revisan capaAbierta())
    const escribiendo = e.target.matches && e.target.matches("input, textarea");
    // Empezar a escribir un nombre abre la búsqueda con esa letra.
    if (config.escribirBusca && config.escribirBusca() && !escribiendo && e.key.length === 1 && /[\p{L}\d]/u.test(e.key)
        && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      e.stopImmediatePropagation();
      abrirBusqueda(e.key);
    }
  }

  // ------------------------------------------------------------ montar

  /**
   * Arma la pantalla. Opciones:
   *   seccion        — "vender", "mercancia", "productos", "fiado" o "caja" (se marca en el menú)
   *   alElegir(p)    — se escaneó, buscó o tecleó un producto que sí existe
   *   codigoNuevo(c) — se escaneó o tecleó un código que no existe
   *   escribirBusca()— true si teclear una letra debe abrir la búsqueda
   *   antesDeBuscar(), antesDeSalir() → texto si no se puede salir todavía
   */
  function montar(opciones) {
    config = opciones;
    const app = $("app");
    app.insertAdjacentHTML("afterbegin", MARCO);
    app.insertAdjacentHTML("beforeend", CAPAS);
    pintarDock(opciones.seccion);

    $("q").addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(buscar, 90); });
    $("q").addEventListener("keydown", async (e) => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (!resultados.length) return;
        elegido = (elegido + (e.key === "ArrowDown" ? 1 : -1) + resultados.length) % resultados.length;
        pintarResultados($("q").value.trim());
        const sel = $("resultados").querySelector(".sel");
        if (sel) sel.scrollIntoView({ block: "nearest" });
      } else if (e.key === "Enter") {
        e.preventDefault();
        const texto = $("q").value.trim();
        clearTimeout(espera);
        if (/^\d{6,}$/.test(texto)) { cerrarCapa("busqueda"); await porCodigo(texto); return; } // código tecleado o de lector USB
        await buscar();
        elegir(elegido);
      }
    });
    $("busqueda").addEventListener("mousedown", (e) => { if (e.target === $("busqueda")) cerrarCapa("busqueda"); });
    document.querySelectorAll("[data-abrir-busqueda]").forEach((b) => { b.onclick = () => abrirBusqueda(); });

    $("cq").addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(buscarClientes, 90); });
    $("cq").addEventListener("keydown", async (e) => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (!clientes.length) return;
        clElegido = (clElegido + (e.key === "ArrowDown" ? 1 : -1) + clientes.length) % clientes.length;
        pintarClientes();
        const sel = $("cl-lista").querySelector(".sel");
        if (sel) sel.scrollIntoView({ block: "nearest" });
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (e.repeat) return;
        clearTimeout(espera);
        await buscarClientes();
        elegirCliente(clElegido);
      }
    });
    $("clientes").addEventListener("mousedown", (e) => { if (e.target === $("clientes")) cerrarCapa("clientes"); });

    $("alta-unidad").addEventListener("click", (e) => { const b = e.target.closest("[data-u]"); if (b) unidadDeAlta(b.dataset.u); });
    $("alta-no").onclick = () => cerrarCapa("alta");
    $("alta-form").onsubmit = guardarAlta;

    $("cel").onclick = () => {
      fetch("/api/info").then((r) => r.json()).then((d) => { $("sin-wifi").hidden = d.en_wifi; }).catch(() => {});
      $("qr").src = "/api/qr.svg?que=celular";
      $("conectar").hidden = false;
      $("conectar-cerrar").focus();
    };
    $("conectar-cerrar").onclick = () => cerrarCapa("conectar");

    document.addEventListener("keydown", teclado, true);

    const ligero = /[?&]ligero=1/.test(location.search) || (navigator.hardwareConcurrency || 4) <= 2;
    document.documentElement.classList.toggle("ligero", ligero);
    reloj();
    setInterval(reloj, 10000);
    revisarEstado();
    setInterval(revisarEstado, 2000);
    escuchar(0);
  }

  window.Tienda = {
    montar, el, numHTML, tile, precioTexto, existenciaTexto, aviso, bip, api, nuevoId,
    abrirBusqueda, porCodigo, abrirAlta, abrirClientes, capaAbierta, cerrarCapa,
  };
})();
