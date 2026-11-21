/* Pantalla de Corte de caja: abrir con un fondo, sacar dinero y, al final, contar y cerrar. */
(function () {
  "use strict";
  const V = window.Venta;
  const C = window.Cuentas;
  const T = window.Tienda;
  const { el, aviso, api } = T;
  const $ = (id) => document.getElementById(id);

  let caja = null; // lo que dice el servidor
  let conteo = {}; // { denominación: cuántos }
  let ocupado = false;

  async function cargar() {
    try { caja = await api("/api/caja"); } catch (e) { aviso(e.message, true); return; }
    pintar();
  }

  function pintar(cierre) {
    if (caja.abierta) { pintarComoVa(); pintarCorte(); } else { pintarAbrir(); pintarAnteriores(cierre); }
  }

  const hora = (t) => C.fecha(t).toLocaleTimeString("es-MX", { hour: "numeric", minute: "2-digit" });
  const dia = (t) => C.fecha(t).toLocaleDateString("es-MX", { weekday: "short", day: "numeric", month: "short" });

  function numero(clase, centavos) {
    const n = el("div", "num " + clase);
    T.numHTML(n, centavos);
    return n;
  }

  function encabezado(titulo, sub) {
    const e = el("div", "encabezado");
    e.append(el("h2", "", titulo), el("span", "sub", sub || ""));
    return e;
  }

  // ------------------------------------------------------------ caja cerrada: abrirla

  function pintarAbrir() {
    const p = $("izq");
    p.replaceChildren(encabezado("Abrir la caja", "La caja está cerrada"));
    const f = el("form", "abrir");
    f.appendChild(el("p", "sub", "¿Con cuánto dinero empiezas? Es el cambio que dejas en la caja para empezar el día."));
    const fila = el("div", "fila");
    const monto = el("label", "monto grande");
    const input = el("input");
    input.id = "fondo";
    input.inputMode = "decimal";
    input.autocomplete = "off";
    input.placeholder = "0";
    input.setAttribute("aria-label", "Dinero para empezar");
    monto.append(el("em", "", "$"), input);
    fila.appendChild(monto);
    for (const v of [20000, 50000, 100000]) {
      const b = el("button", "chip", V.pesos(v));
      b.type = "button";
      b.onclick = () => { input.value = String(v / 100); input.focus(); };
      fila.appendChild(b);
    }
    f.appendChild(fila);
    const ok = el("button", "cta", "Abrir la caja");
    ok.type = "submit";
    f.appendChild(ok);
    f.appendChild(el("p", "sub nota", "Se puede vender aunque la caja esté cerrada, pero esas ventas no entran a ningún corte."));
    f.onsubmit = async (e) => {
      e.preventDefault();
      const v = input.value.trim() === "" ? 0 : V.leerMonto(input.value);
      if (v === null) { aviso("Escribe la cantidad, por ejemplo 500", true); input.focus(); return; }
      try {
        caja = await api("/api/caja/abrir", { monto: (v / 100).toFixed(2) });
        conteo = {};
        aviso("Caja abierta con " + V.pesos(v));
        pintar();
      } catch (err) { aviso(err.message, true); }
    };
    p.appendChild(f);
    input.focus();
  }

  function pintarAnteriores(cierre) {
    const p = $("der");
    p.replaceChildren();
    if (cierre) p.appendChild(resultadoCorte(cierre));
    p.appendChild(el("h4", "tit", "Cortes anteriores"));
    if (!caja.anteriores.length) {
      p.appendChild(el("p", "vacio", "Todavía no hay cortes. Abre la caja y al final del día haz el corte."));
      return;
    }
    const lista = el("div", "movs");
    for (const k of caja.anteriores) {
      const r = C.resultado(k.diferencia);
      const fila = el("div", "mov corte");
      const izq = el("div");
      izq.append(el("b", "", dia(k.cerrado)), el("small", "", hora(k.abierto) + " a " + hora(k.cerrado) + " · contaste " + V.pesos(k.contado)));
      fila.append(izq, el("span", "tag " + r.clase, r.clase === "cuadra" ? r.texto : r.texto.toLowerCase() + " " + V.pesos(Math.abs(k.diferencia))));
      lista.appendChild(fila);
    }
    p.appendChild(lista);
  }

  function resultadoCorte(k) {
    const r = C.resultado(k.diferencia);
    const caja2 = el("div", "resultado " + r.clase);
    caja2.appendChild(el("span", "lbl", "Corte terminado · " + r.texto));
    if (r.clase !== "cuadra") caja2.appendChild(numero("", Math.abs(k.diferencia)));
    const kv = el("div", "kv");
    kv.append(el("span", "", "Debía haber"), el("b", "", V.pesos(k.esperado)), el("span", "", "Contaste"), el("b", "", V.pesos(k.contado)));
    if (k.ventas) kv.append(el("span", "", "Se vendió en total"), el("b", "", V.pesos(k.ventas.vendido)), el("span", "", "Ganancia"), el("b", "", V.pesos(k.ventas.ganancia)));
    caja2.appendChild(kv);
    return caja2;
  }

  // ------------------------------------------------------------ caja abierta: cómo va

  function pintarComoVa() {
    const p = $("izq");
    const v = caja.ventas;
    p.replaceChildren(encabezado("Cómo va la caja", "Abierta desde las " + hora(caja.abierto)));
    const grande = el("div", "esperado");
    grande.append(el("span", "lbl", "Debe haber en la caja"), numero("", caja.esperado));
    p.appendChild(grande);

    const kv = el("div", "kv suma");
    const linea = (texto, centavos, signo) => {
      kv.append(el("span", "", texto), el("b", signo === "−" ? "resta" : "", (signo || "") + V.pesos(centavos)));
    };
    linea("Fondo con que empezaste", caja.fondo);
    linea("Ventas en efectivo", caja.ventas_efectivo, "+ ");
    linea("Pagos de préstamos", caja.abonos, "+ ");
    linea("Dinero que sacaste", caja.retiros, "−");
    p.appendChild(kv);

    const otros = el("div", "chips-info");
    otros.append(
      el("span", "", v.ventas + (v.ventas === 1 ? " venta" : " ventas")),
      el("span", "", "Se prestó " + V.pesos(v.fiado)),
      el("span", "", "Ganancia " + V.pesos(v.ganancia)),
    );
    if (v.canceladas) otros.appendChild(el("span", "", v.canceladas + (v.canceladas === 1 ? " cancelada" : " canceladas")));
    p.appendChild(otros);

    // Sacar dinero
    const f = el("form", "retiro mt");
    f.appendChild(el("span", "lbl", "Sacar dinero de la caja"));
    const fila = el("div", "fila");
    const monto = el("label", "monto");
    const input = el("input");
    input.inputMode = "decimal";
    input.autocomplete = "off";
    input.placeholder = "Cuánto";
    input.setAttribute("aria-label", "Cuánto sacaste");
    monto.append(el("em", "", "$"), input);
    const para = el("input", "para");
    para.maxLength = 120;
    para.placeholder = "¿Para qué? (pagar al proveedor, gasto...)";
    para.setAttribute("aria-label", "Para qué");
    const ok = el("button", "boton", "Sacar");
    ok.type = "submit";
    fila.append(monto, para, ok);
    f.appendChild(fila);
    if (caja.lista_retiros.length) {
      const lista = el("div", "historia");
      for (const r of caja.lista_retiros.slice(0, 4)) {
        const l = el("div");
        l.append(el("span", "", hora(r.cuando) + " · " + r.nota), el("b", "", "−" + V.pesos(r.monto)));
        lista.appendChild(l);
      }
      f.appendChild(lista);
    }
    f.onsubmit = async (e) => {
      e.preventDefault();
      const c = V.leerMonto(input.value);
      if (!c) { aviso("Escribe cuánto sacaste", true); input.focus(); return; }
      if (!para.value.trim()) { aviso("Escribe para qué se sacó el dinero", true); para.focus(); return; }
      try {
        caja = await api("/api/caja/retiro", { monto: (c / 100).toFixed(2), nota: para.value });
        aviso("Anotado: salieron " + V.pesos(c));
        pintarComoVa();
        revisarCorte();
      } catch (err) { aviso(err.message, true); }
    };
    p.appendChild(f);
  }

  // ------------------------------------------------------------ caja abierta: el corte

  let revisarCorte = () => {};

  function pintarCorte() {
    const p = $("der");
    p.replaceChildren(encabezado("Hacer el corte", "Cuenta lo que hay en la caja"));
    const rejilla = el("div", "conteo");
    const total = el("div", "contado");
    for (const d of C.DENOMINACIONES) {
      const fila = el("div", "den " + (d >= C.PRIMERA_MONEDA * 2 ? "billete" : "moneda"));
      fila.appendChild(el("span", "v", d < 100 ? "50¢" : V.pesos(d)));
      const paso = el("span", "step");
      const menos = el("button", "", "−");
      const mas = el("button", "", "+");
      const n = el("input");
      n.inputMode = "numeric";
      n.value = conteo[d] ? String(conteo[d]) : "";
      n.placeholder = "0";
      n.setAttribute("aria-label", "Cuántos de " + (d < 100 ? "50 centavos" : V.pesos(d)));
      menos.type = mas.type = "button";
      menos.tabIndex = mas.tabIndex = -1;
      menos.setAttribute("aria-label", "Uno menos");
      mas.setAttribute("aria-label", "Uno más");
      const poner = (x) => { conteo[d] = Math.max(0, x); n.value = conteo[d] ? String(conteo[d]) : ""; revisarCorte(); };
      menos.onclick = () => poner((conteo[d] || 0) - 1);
      mas.onclick = () => poner((conteo[d] || 0) + 1);
      n.addEventListener("input", () => {
        n.value = n.value.replace(/\D/g, "").slice(0, 5);
        conteo[d] = Number(n.value || 0);
        revisarCorte();
      });
      paso.append(menos, n, mas);
      fila.append(paso, el("span", "sub-den", ""));
      rejilla.appendChild(fila);
    }
    p.appendChild(rejilla);
    p.appendChild(total);

    const nota = el("input", "para");
    nota.maxLength = 120;
    nota.placeholder = "Nota (opcional): por qué sobró o faltó";
    nota.setAttribute("aria-label", "Nota del corte");
    const cerrar = el("button", "cta", "Cerrar la caja");
    const pie = el("div", "mt pie");
    pie.append(nota, cerrar);
    p.appendChild(pie);

    revisarCorte = () => {
      const contado = C.sumar(conteo);
      rejilla.querySelectorAll(".den").forEach((f, i) => {
        const d = C.DENOMINACIONES[i];
        f.querySelector(".sub-den").textContent = conteo[d] ? V.pesos(d * conteo[d]) : "";
        f.classList.toggle("lleno", !!conteo[d]);
      });
      const r = C.resultado(contado - caja.esperado);
      total.className = "contado " + (contado ? r.clase : "");
      total.replaceChildren();
      const a = el("div");
      a.append(el("span", "lbl", "Contaste"), numero("", contado));
      const b = el("div", "dif");
      if (!contado) b.append(el("span", "lbl", "Debe haber"), el("b", "", V.pesos(caja.esperado)));
      else b.append(el("span", "lbl", r.texto), el("b", "", r.clase === "cuadra" ? "✓" : V.pesos(Math.abs(contado - caja.esperado))));
      total.append(a, b);
      desarmar();
    };

    let armado = null;
    const desarmar = () => { clearTimeout(armado); armado = null; cerrar.classList.remove("seguro"); cerrar.textContent = "Cerrar la caja"; };
    cerrar.onclick = async () => {
      if (ocupado) return;
      const contado = C.sumar(conteo);
      if (!armado) {
        armado = setTimeout(desarmar, 4000);
        cerrar.classList.add("seguro");
        cerrar.textContent = "Toca otra vez para cerrar con " + V.pesos(contado);
        return;
      }
      ocupado = true;
      try {
        const r = await api("/api/caja/cerrar", { monto: (contado / 100).toFixed(2), nota: nota.value });
        caja = r.caja;
        conteo = {};
        pintar(r);
        aviso("Corte guardado");
      } catch (err) {
        aviso(err.message, true);
        desarmar();
      } finally {
        ocupado = false;
      }
    };
    revisarCorte();
  }

  T.montar({
    seccion: "caja",
    alElegir: () => aviso("Para vender ese producto, abre Vender (abajo a la izquierda)."),
    codigoNuevo: () => aviso("Ese código no está registrado. Dalo de alta en Vender o en Productos."),
    escribirBusca: () => false,
    antesDeSalir: () => null,
  });

  // Las ventas siguen entrando mientras la pantalla está abierta: se actualiza sola.
  setInterval(async () => {
    if (!caja || !caja.abierta || document.activeElement && document.activeElement.matches("input")) return;
    try {
      const nuevo = await api("/api/caja");
      if (nuevo.abierta && nuevo.esperado !== caja.esperado) { caja = nuevo; pintarComoVa(); revisarCorte(); }
    } catch (_) { /* el servidor está reiniciando */ }
  }, 15000);

  cargar();
})();
