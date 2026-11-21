// La app del celular: vende aunque la PC esté apagada; las ventas se pasan solas cuando la PC contesta.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const pesos = (c) => "$" + (c / 100).toLocaleString("es-MX", { minimumFractionDigits: c % 100 ? 2 : 0, maximumFractionDigits: 2 });
  const enApp = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

  // ---------- Memoria del celular (IndexedDB: sobrevive aunque se cierre la app) ----------
  let bdPromesa = null;
  function bd() {
    if (!bdPromesa) {
      bdPromesa = new Promise((ok, mal) => {
        const r = indexedDB.open("tienda-prueba", 1); // nombre de cuando era prueba: cambiarlo borraría lo guardado
        r.onupgradeneeded = () => {
          r.result.createObjectStore("ventas", { keyPath: "id" });
          r.result.createObjectStore("datos");
        };
        r.onsuccess = () => ok(r.result);
        r.onerror = () => mal(r.error);
      });
    }
    return bdPromesa;
  }
  async function op(almacen, modo, fn) {
    const b = await bd();
    return new Promise((ok, mal) => {
      const t = b.transaction(almacen, modo);
      const res = fn(t.objectStore(almacen));
      t.oncomplete = () => ok(res && "result" in res ? res.result : undefined);
      t.onerror = () => mal(t.error);
    });
  }
  const leerDato = (k) => op("datos", "readonly", (s) => s.get(k));
  const guardarDato = (k, v) => op("datos", "readwrite", (s) => s.put(v, k));
  const todasLasVentas = () => op("ventas", "readonly", (s) => s.getAll());
  const guardarVenta = (v) => op("ventas", "readwrite", (s) => s.put(v));

  // ---------- Llave del QR y nombre de este celular ----------
  async function prepararLlave() {
    const m = /[?#&]llave=([A-Za-z0-9_-]+)/.exec(location.search + location.hash);
    let llave = m ? m[1] : null;
    if (llave) await guardarDato("llave", llave);
    else llave = await leerDato("llave");
    if (llave) $("manifiesto").href = "/celular.webmanifest?k=" + encodeURIComponent(llave);
    return llave;
  }
  async function nombreCelular() {
    let n = await leerDato("celular");
    if (!n) {
      const ua = navigator.userAgent;
      const tipo = /iPhone/.test(ua) ? "iPhone" : /Huawei|HUAWEI/.test(ua) ? "Huawei" : /Android/.test(ua) ? "Android" : "Celular";
      n = tipo + "-" + Math.random().toString(36).slice(2, 6);
      await guardarDato("celular", n);
    }
    return n;
  }
  const idNuevo = () => (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2)).replace(/[^A-Za-z0-9_-]/g, "");

  // ---------- Pantalla ----------
  let productos = [];
  const cuenta = new Map(); // id → cantidad (piezas, o gramos si es por kilo)
  const subtotal = (p, cant) => (p.unidad === "kg" ? Math.round((p.precio * cant) / 1000) : p.precio * cant);
  const cantTexto = (p, cant) => (p.unidad === "kg" ? (cant / 1000).toString().replace(".5", "½").replace(/^0½/, "½") + " kg" : String(cant));

  function toast(texto) {
    const t = $("toast");
    t.textContent = texto;
    t.classList.add("si");
    clearTimeout(toast.t);
    toast.t = setTimeout(() => t.classList.remove("si"), 1800);
  }

  /** Suma una pieza (o medio kilo) a la cuenta y devuelve cuánto lleva de ese producto. */
  function sumar(p) {
    const cant = (cuenta.get(p.id) || 0) + (p.unidad === "kg" ? 500 : 1);
    cuenta.set(p.id, cant);
    return cant;
  }

  // Mismos tonos que los círculos de la PC (comun.js), para que cada producto se reconozca igual.
  const TONOS = [
    ["#FF7A62", "#B9141B"], ["#FFE07A", "#E08B0B", 1], ["#A6DAFF", "#2A78C9"], ["#F0B67E", "#8E501C"],
    ["#8BD177", "#357A27"], ["#FFB3D1", "#C9457F"], ["#B79BE8", "#5B3F9A"], ["#FFF6E2", "#D8AC6C", 1],
    ["#7FE0D0", "#17806F"], ["#F6D58E", "#C9963C", 1],
  ];
  function pintarTile(t, nombre) {
    let h = 0;
    for (const c of nombre) h = (h * 31 + c.codePointAt(0)) >>> 0;
    const [c1, c2, claro] = TONOS[h % TONOS.length];
    t.className = "tile" + (claro ? " claro" : "");
    t.textContent = (nombre.trim()[0] || "?").toUpperCase();
    t.style.setProperty("--c1", c1);
    t.style.setProperty("--c2", c2);
  }
  const icono = (id) => '<svg class="ic"><use href="#i-' + id + '"/></svg>';
  function quitar(p) {
    const cant = (cuenta.get(p.id) || 0) - (p.unidad === "kg" ? 500 : 1);
    if (cant > 0) cuenta.set(p.id, cant); else cuenta.delete(p.id);
  }

  const sinAcentos = (t) => t.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");

  function pintarProductos() {
    const lista = $("lista");
    lista.textContent = "";
    if (!productos.length) {
      lista.innerHTML = '<div class="vacio">Sin productos todavía. Abre la app una vez con la PC prendida.</div>';
      return;
    }
    const q = sinAcentos($("buscar").value.trim());
    const vistos = q ? productos.filter((p) => sinAcentos(p.nombre).includes(q) || p.codigo === q) : productos;
    if (!vistos.length) lista.innerHTML = '<div class="vacio">No hay productos con ese nombre.</div>';
    for (const p of vistos) {
      const cant = cuenta.get(p.id) || 0;
      const b = document.createElement("div");
      b.className = "fila" + (cant ? " puesta" : "");
      b.setAttribute("role", "button");
      b.innerHTML = '<span class="tile"></span><span class="n"><b></b><small></small></span>';
      pintarTile(b.querySelector(".tile"), p.nombre);
      b.querySelector("b").textContent = p.nombre;
      b.querySelector("small").textContent = pesos(p.precio) + (p.unidad === "kg" ? " el kilo" : "");
      if (cant) {
        const paso = document.createElement("span");
        paso.className = "paso";
        paso.innerHTML = '<button aria-label="Quitar uno">' + icono("menos") + "</button><span></span>" +
          '<button aria-label="Agregar uno">' + icono("mas") + "</button>";
        paso.querySelector("span").textContent = cantTexto(p, cant);
        paso.firstChild.onclick = (e) => { e.stopPropagation(); quitar(p); pintarProductos(); };
        paso.lastChild.onclick = (e) => { e.stopPropagation(); sumar(p); pintarProductos(); };
        b.appendChild(paso);
      } else {
        b.insertAdjacentHTML("beforeend", '<span class="mas">' + icono("mas") + "</span>");
      }
      b.onclick = () => { sumar(p); pintarProductos(); };
      lista.appendChild(b);
    }
    let total = 0, piezas = 0;
    for (const [id, cant] of cuenta) {
      const p = productos.find((x) => x.id === id);
      if (p) { total += subtotal(p, cant); piezas += p.unidad === "kg" ? 1 : cant; }
    }
    $("total").textContent = pesos(total);
    $("articulos").textContent = piezas ? (piezas === 1 ? "1 artículo" : piezas + " artículos") : "Agrega productos";
    $("camara-listo").textContent = total ? "Listo · " + pesos(total) : "Listo";
    $("cobrar").textContent = total ? "Cobrar " + pesos(total) : "Cobrar";
    $("cobrar").disabled = total === 0;
    $("limpiar").classList.toggle("oculto", total === 0);
  }

  async function pintarHistorial() {
    const L = window.Logica;
    const unidad = (r) => r.unidad || (productos.find((p) => p.id === r.producto_id) || {}).unidad;
    const ventas = (await todasLasVentas()).map((v) => ({ ...v, renglones: v.renglones.map((r) => ({ ...r, unidad: unidad(r) })) }));
    const h = $("hist");
    h.textContent = "";
    $("hist-cuenta").textContent = ventas.length ? "· " + ventas.length : "";
    if (!ventas.length) { h.innerHTML = '<div class="lista"><div class="vacio">Aún no hay ventas.</div></div>'; return; }
    const ahora = new Date();
    const hoy = ahora.getFullYear() + "-" + String(ahora.getMonth() + 1).padStart(2, "0") + "-" + String(ahora.getDate()).padStart(2, "0");
    for (const d of L.ventasPorDia(ventas)) {
      const cab = document.createElement("div");
      cab.className = "dia";
      cab.innerHTML = "<b></b><span></span>";
      cab.firstChild.textContent = L.diaTexto(d.dia, hoy);
      cab.lastChild.textContent = (d.cuantas === 1 ? "1 venta" : d.cuantas + " ventas") + " · " + pesos(d.total);
      const caja = document.createElement("div");
      caja.className = "lista";
      for (const v of d.ventas) {
        const f = document.createElement("div");
        f.className = "venta";
        f.innerHTML = '<span class="cab"><span></span><small></small></span><span class="total"></span>' +
          '<span class="que"></span><span class="marca-estado"></span>';
        f.querySelector(".cab span").textContent = "Venta " + v.numero;
        f.querySelector(".cab small").textContent = L.hora12(v.cuando);
        f.querySelector(".total").textContent = pesos(v.total);
        f.querySelector(".que").textContent = L.renglonesTexto(v.renglones) + (v.problema ? " — " + v.problema : "");
        const marca = f.querySelector(".marca-estado");
        marca.textContent = v.pasada ? "En la PC" : v.problema ? "No pasó" : "Por pasar";
        marca.classList.add(v.pasada ? "ok" : v.problema ? "mal" : "espera");
        caja.appendChild(f);
      }
      h.append(cab, caja);
    }
  }

  function verSeccion(ventas) {
    document.body.classList.toggle("en-ventas", ventas);
    $("sec-vender").classList.toggle("oculto", ventas);
    $("sec-ventas").classList.toggle("oculto", !ventas);
    $("p-vender").setAttribute("aria-selected", String(!ventas));
    $("p-ventas").setAttribute("aria-selected", String(ventas));
    scrollTo(0, 0);
  }

  function estado(texto, tipo, sub) {
    $("estado").className = "estado " + (tipo || "");
    $("estado-tx").textContent = texto;
    $("estado-sub").textContent = sub || "";
  }

  function avisarPasaron(n, total) {
    $("pasaron-tx").textContent = (n === 1 ? "1 venta ya está en la PC" : n + " ventas ya están en la PC") + " (" + pesos(total) + ")";
    $("pasaron").classList.remove("oculto");
    if (navigator.vibrate) navigator.vibrate(60);
    clearTimeout(avisarPasaron.t);
    avisarPasaron.t = setTimeout(() => $("pasaron").classList.add("oculto"), 3500);
  }

  // ---------- Hablar con la PC ----------
  let llave = null;
  async function pedir(url, opciones) {
    const control = new AbortController();
    const t = setTimeout(() => control.abort(), 3500); // si la PC está apagada no esperamos de más
    try {
      const r = await fetch(url, { ...opciones, signal: control.signal, cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Llave": llave, ...(opciones && opciones.headers) } });
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.json();
    } finally { clearTimeout(t); }
  }

  // Cada 2 s: la PC sabe que hay un celular ("Celular listo") y aquí sabemos si la PC está prendida.
  let pcViva = false;
  async function latido() {
    if (llave && !document.hidden) {
      let viva = false;
      try { await pedir("/api/hora"); viva = true; } catch (_) { /* apagada o fuera del WiFi */ }
      if (viva && !pcViva) sincronizar();
      pcViva = viva;
      $("modo").classList.toggle("oculto", !viva);
      if (!viva && modoPc) ponerModo(false);
    }
    setTimeout(latido, 2000);
  }

  let enviando = false;
  async function sincronizar() {
    if (enviando) return;
    const pendientes = (await todasLasVentas()).filter((v) => !v.pasada);
    if (!llave) { estado("Sin conectar", "espera"); return; }
    enviando = true;
    try {
      const datos = await pedir("/api/celular/productos");
      productos = datos.productos;
      await guardarDato("productos", productos);
      if (!document.querySelector("#hoja:not(.oculto)")) pintarProductos();
      if (pendientes.length) {
        estado("Pasando a la PC…", "espera");
        const envio = pendientes.map(({ pasada, problema, ...v }) => v);
        const r = await pedir("/api/celular/ventas", { method: "POST", body: JSON.stringify({ ventas: envio }) });
        const ok = new Set(r.guardadas);
        let n = 0, total = 0;
        for (const v of pendientes) {
          if (ok.has(v.id)) { await guardarVenta({ ...v, pasada: true, problema: null }); n++; total += v.total; }
          else if (r.problemas && r.problemas[v.id]) await guardarVenta({ ...v, problema: r.problemas[v.id] });
        }
        if (n) avisarPasaron(n, total);
        await pintarHistorial();
      }
      const quedan = (await todasLasVentas()).filter((v) => !v.pasada).length;
      if (quedan) estado("PC conectada", "ok", (quedan === 1 ? "1 venta no pudo pasar" : quedan + " ventas no pudieron pasar") + ": revisa abajo qué pasó.");
      else estado("PC conectada", "ok");
    } catch (_) {
      const n = pendientes.length;
      if (n) estado("Sin PC · " + n + " por pasar", "espera",
        (n === 1 ? "La venta está guardada aquí y pasa sola" : "Las ventas están guardadas aquí y pasan solas") + " cuando prendas la PC.");
      else estado("Sin PC", "espera", "Puedes seguir vendiendo: todo se guarda aquí y pasa solo a la PC.");
    } finally {
      enviando = false;
    }
  }

  // ---------- Cobrar: con cuánto paga y el cambio ----------
  const BILLETES = [2000, 5000, 10000, 20000, 50000];
  let cobro = null;
  function cuentaActual() {
    const renglones = [];
    let total = 0;
    for (const [id, cant] of cuenta) {
      const p = productos.find((x) => x.id === id);
      if (!p) continue;
      renglones.push({ producto_id: p.id, nombre: p.nombre, unidad: p.unidad, cantidad: cant, precio: p.precio });
      total += subtotal(p, cant);
    }
    return { renglones, total };
  }
  function pintarCobro() {
    const { total, recibido } = cobro;
    $("h-total").textContent = pesos(total);
    $("h-recibido").textContent = recibido ? "Te dio " + pesos(recibido) : "Toca los billetes y monedas";
    $("h-borrar").classList.toggle("oculto", !recibido);
    const alcanza = recibido >= total;
    $("h-cambio").classList.toggle("listo", recibido > 0 && alcanza);
    $("h-cambio-lbl").textContent = !recibido ? "" : alcanza ? "Su cambio" : "Faltan";
    $("h-cambio-n").textContent = recibido ? pesos(Math.abs(recibido - total)) : "";
    $("h-listo").disabled = !alcanza;
  }
  function abrirCobro() {
    const c = cuentaActual();
    if (!c.renglones.length) return;
    cobro = { ...c, recibido: 0 };
    const caja = $("billetes");
    caja.textContent = "";
    for (const b of BILLETES) {
      const boton = document.createElement("button");
      boton.textContent = pesos(b);
      boton.onclick = () => { cobro.recibido += b; pintarCobro(); };
      caja.appendChild(boton);
    }
    const exacto = document.createElement("button");
    exacto.textContent = "Exacto";
    exacto.className = "exacto";
    exacto.onclick = () => { cobro.recibido = cobro.total; pintarCobro(); };
    caja.appendChild(exacto);
    pintarCobro();
    $("hoja").classList.remove("oculto");
  }

  async function guardarCobro() {
    if (!cobro || cobro.recibido < cobro.total) return;
    const d = new Date();
    const cuando = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 19).replace("T", " ");
    await guardarVenta({ id: idNuevo(), cuando, celular: await nombreCelular(), renglones: cobro.renglones,
      total: cobro.total, recibido: cobro.recibido, pasada: false });
    const cambio = cobro.recibido - cobro.total;
    cobro = null;
    $("hoja").classList.add("oculto");
    cuenta.clear();
    pintarProductos();
    await pintarHistorial();
    toast(cambio ? "Guardada. Cambio: " + pesos(cambio) : "Venta guardada");
    sincronizar();
  }

  // ---------- Escanear con la cámara (no necesita la PC: busca en la lista guardada) ----------
  const L = window.Logica;
  let escaneando = false;
  function porCodigo(codigo) {
    // En la PC un UPC-A se guarda como EAN-13 (con 0), pero uno escrito a mano puede venir de 12.
    return productos.find((p) => p.codigo && (p.codigo === codigo || "0" + p.codigo === codigo));
  }
  function leido(texto, sub, bien, p) {
    const t = $("leido-tile");
    if (p) pintarTile(t, p.nombre);
    else { t.className = "tile vacia"; t.style.cssText = ""; t.innerHTML = icono(bien ? "escanear" : "x"); }
    $("leido-tx").textContent = texto;
    $("leido-sub").textContent = sub || "";
    $("leido").classList.toggle("mal", !bien);
    const d = $("destello");
    d.classList.toggle("mal", !bien);
    d.classList.add("si");
    requestAnimationFrame(() => requestAnimationFrame(() => d.classList.remove("si")));
    if (navigator.vibrate) navigator.vibrate(bien ? 40 : [60, 60, 60]);
  }
  // Con la PC prendida se puede mandar lo escaneado a la pantalla de Vender de la PC, como antes.
  let modoPc = false;
  function ponerModo(pc) {
    modoPc = pc;
    $("modo-aqui").setAttribute("aria-pressed", String(!pc));
    $("modo-pc").setAttribute("aria-pressed", String(pc));
    const t = $("leido-tile");
    t.className = "tile vacia"; t.style.cssText = ""; t.innerHTML = icono("escanear");
    $("leido-tx").textContent = pc ? "Lo que escanees sale en la pantalla de la PC" : "Pon el código dentro del recuadro";
    $("leido-sub").textContent = "";
    $("leido").classList.remove("mal");
  }
  async function mandarALaPc(crudo, formato, codigo) {
    const p = porCodigo(codigo);
    try {
      const r = await pedir("/api/escaneo", { method: "POST",
        body: JSON.stringify({ id: idNuevo(), codigo: crudo, formato, t_detectado: Date.now() }) });
      if (r.pantallas) leido(p ? p.nombre : codigo, "Ya está en la pantalla de la PC", true, p);
      else leido("Llegó, pero en la PC no está abierta la pantalla de Vender", "Ábrela o toca “Cobrar aquí”", false);
    } catch (_) {
      leido("La PC no contesta", "Toca “Cobrar aquí” para seguir vendiendo en el celular", false);
    }
  }

  function alLeer(crudo, formato) {
    const codigo = L.normalizarCodigo(crudo, formato);
    if (!codigo) return; // lectura borrosa: que siga intentando
    if (modoPc) { mandarALaPc(crudo, formato, codigo); return; }
    const p = porCodigo(codigo);
    if (!p) { leido("Este código no está en la lista", codigo + " · agrégalo en Productos con la PC prendida", false); return; }
    const cant = sumar(p);
    pintarProductos();
    leido(p.nombre, "Llevas " + cantTexto(p, cant) + " · " + pesos(subtotal(p, cant)), true, p);
  }
  async function abrirCamara() {
    const video = $("video");
    if (!window.isSecureContext || !navigator.mediaDevices) {
      toast("La cámara necesita abrir la app desde el QR (https)");
      return;
    }
    $("camara").classList.remove("oculto");
    ponerModo(modoPc && pcViva);
    try {
      await window.Lector.abrirCamara(video);
    } catch (e) {
      cerrarCamara();
      toast(e && e.name === "NotAllowedError" ? "Falta dar permiso a la cámara" : "No se pudo abrir la cámara");
      return;
    }
    const leer = await window.Lector.crear($("franja"));
    const aceptar = L.crearFiltroRepetidos(1500);
    const confirmar = L.crearConfirmador(2, 600); // dos lecturas iguales: evita lecturas equivocadas
    escaneando = true;
    let ocupado = false;
    const vuelta = async () => {
      if (!escaneando) return;
      if (!ocupado && video.readyState >= 2) {
        ocupado = true;
        try {
          const r = await leer(video);
          const ahora = Date.now();
          if (r && confirmar(r.codigo, ahora) && aceptar(r.codigo, ahora)) alLeer(r.codigo, r.formato);
        } catch (_) { /* cuadro dañado, seguimos */ }
        ocupado = false;
      }
      requestAnimationFrame(vuelta);
    };
    requestAnimationFrame(vuelta);
  }
  function cerrarCamara() {
    escaneando = false;
    window.Lector.cerrarCamara($("video"));
    $("camara").classList.add("oculto");
  }

  // ---------- Arranque ----------
  async function iniciar() {
    $("cobrar").onclick = () => { cerrarCamara(); abrirCobro(); };
    $("escanear").onclick = abrirCamara;
    $("p-vender").onclick = () => verSeccion(false);
    $("p-ventas").onclick = () => verSeccion(true);
    $("camara-listo").onclick = cerrarCamara;
    $("camara-cerrar").onclick = cerrarCamara;
    $("instalar-cerrar").onclick = () => {
      $("instalar").classList.add("oculto");
      try { localStorage.setItem("sin-aviso-instalar", "1"); } catch (_) { /* sin memoria: solo por ahora */ }
    };
    $("modo-aqui").onclick = () => ponerModo(false);
    $("modo-pc").onclick = () => ponerModo(true);
    $("buscar").oninput = pintarProductos;
    $("h-listo").onclick = guardarCobro;
    $("h-cancelar").onclick = () => { cobro = null; $("hoja").classList.add("oculto"); };
    $("h-borrar").onclick = () => { if (cobro) { cobro.recibido = 0; pintarCobro(); } };
    $("pasaron").onclick = () => $("pasaron").classList.add("oculto");
    $("limpiar").onclick = () => { cuenta.clear(); pintarProductos(); };
    $("liga-sello").href = "http://" + location.hostname + ":8000/sello";
    llave = await prepararLlave();
    $("sin-llave").classList.toggle("oculto", !!llave);
    productos = (await leerDato("productos")) || [];
    pintarProductos();
    await pintarHistorial();

    if ("serviceWorker" in navigator) {
      try {
        await navigator.serviceWorker.register("/celular-sw.js", { scope: "/" });
      } catch (_) {
        $("sin-guardar").classList.remove("oculto"); // casi siempre: el celular aún no confía en el sello
      }
    } else {
      $("sin-guardar").classList.remove("oculto");
    }
    let yaLoCerro = false;
    try { yaLoCerro = localStorage.getItem("sin-aviso-instalar") === "1"; } catch (_) { /* sin memoria */ }
    if (!enApp && !yaLoCerro) {
      $("instalar").classList.remove("oculto");
      $("instalar-tx").textContent = /iPhone|iPad/.test(navigator.userAgent)
        ? "toca Compartir y luego “Agregar a inicio”."
        : "abre el menú ⋮ y toca “Instalar app”.";
    }
    if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
    sincronizar();
    setInterval(sincronizar, 5000);
    latido();
    addEventListener("online", sincronizar);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) sincronizar(); });
  }
  iniciar();
})();
