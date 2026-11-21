/* Pantalla de Llegó mercancía: escanear lo que llegó, cuántos son y cuánto costó; se suma al inventario. */
(function () {
  "use strict";
  const V = window.Venta;
  const I = window.Inventario;
  const T = window.Tienda;
  const { el, aviso, api } = T;
  const $ = (id) => document.getElementById(id);

  const llegada = I.crearLlegada();
  let ocupado = false;

  function cantidadVisible(r) {
    return r.producto.unidad === "kg" ? I.kilosTexto(r.cantidad) : String(r.cantidad);
  }

  function pintar(resaltar) {
    const lista = $("lista");
    lista.replaceChildren();
    $("vacio").hidden = !llegada.vacia;
    lista.hidden = llegada.vacia;
    for (const r of llegada.renglones) {
      const p = r.producto;
      const kg = p.unidad === "kg";
      const fila = el("div", "rw lleg" + (p.id === resaltar ? " sel" : ""));
      fila.setAttribute("role", "listitem");

      const n = el("span", "n");
      const detalle = el("small", "", "Ahora hay " + T.existenciaTexto(p.existencia, p.unidad));
      if (p.costo && r.costo !== p.costo) {
        const cambio = el("span", "cambio-costo" + (r.costo < p.costo ? " baja" : ""),
          " · antes costaba " + V.pesos(p.costo) + (r.costo < p.costo ? " ↓" : " ↑"));
        detalle.appendChild(cambio);
      }
      n.append(el("b", "", p.nombre), detalle);

      const paso = el("span", "step");
      const menos = el("button", "", "−");
      menos.setAttribute("aria-label", "Uno menos");
      menos.onclick = () => { llegada.cambiar(p.id, -1); pintar(); };
      const mas = el("button", "", "+");
      mas.setAttribute("aria-label", "Uno más");
      mas.onclick = () => { llegada.cambiar(p.id, 1); pintar(); };
      const cant = el("input", "cant");
      cant.value = cantidadVisible(r);
      cant.inputMode = "decimal";
      cant.setAttribute("aria-label", kg ? "Kilos que llegaron" : "Piezas que llegaron");
      cant.title = kg ? "Kilos (puedes escribir 12.5)" : "Piezas";
      cant.onchange = () => {
        const v = kg ? I.leerKilos(cant.value) : (/^\d+$/.test(cant.value.trim()) ? Number(cant.value.trim()) : null);
        if (!v) { aviso(kg ? "Escribe los kilos, por ejemplo 12.5" : "Escribe cuántas piezas son", true); cant.value = cantidadVisible(r); return; }
        llegada.poner(p.id, v);
        pintar();
      };
      cant.onkeydown = (e) => { if (e.key === "Enter") cant.blur(); };
      paso.append(menos, cant, mas);
      if (kg) paso.appendChild(el("small", "", "kg"));

      const costo = el("label", "costo-in");
      const ci = el("input");
      ci.value = r.costo ? V.pesos(r.costo).slice(1) : "";
      ci.placeholder = "0";
      ci.inputMode = "decimal";
      ci.setAttribute("aria-label", kg ? "Costo del kilo" : "Costo de cada uno");
      ci.onchange = () => {
        const t = ci.value.trim();
        const v = t === "" || t === "0" ? 0 : V.leerMonto(t);
        if (v === null) { aviso("Escribe el costo como 15 o 15.50", true); ci.value = r.costo ? V.pesos(r.costo).slice(1) : ""; return; }
        llegada.costo(p.id, v);
        pintar();
      };
      ci.onkeydown = (e) => { if (e.key === "Enter") ci.blur(); };
      costo.append("$", ci, el("small", "", kg ? "/kg" : "c/u"));

      const quitar = el("button", "x", "×");
      quitar.setAttribute("aria-label", "Quitar " + p.nombre);
      quitar.onclick = () => { llegada.quitar(p.id); pintar(); };

      fila.append(T.tile(p.nombre), n, paso, costo, el("span", "p", V.pesos(I.costoRenglon(r.costo, r.cantidad, p.unidad))), quitar);
      lista.appendChild(fila);
    }
    if (resaltar) setTimeout(() => { const f = lista.querySelector(".sel"); if (f) f.classList.remove("sel"); }, 1200);
    pintarResumen();
  }

  function pintarResumen() {
    const piezas = llegada.piezas;
    const big = $("n-piezas");
    big.replaceChildren(document.createTextNode(String(piezas)), el("small", "", piezas === 1 ? "pieza" : "piezas"));
    $("n-kilos").textContent = llegada.gramos ? "y " + I.kilosTexto(llegada.gramos) + " kg a granel" : "";
    $("n-productos").textContent = String(llegada.renglones.length);
    $("costo-total").textContent = V.pesos(llegada.costoTotal);
    const sinCosto = llegada.renglones.filter((r) => !r.costo).length;
    $("guardar").classList.toggle("off", llegada.vacia);
    $("guardar").textContent = sinCosto && !llegada.vacia
      ? "Guardar (" + sinCosto + (sinCosto === 1 ? " sin costo)" : " sin costo)") : "Guardar en inventario";
    $("vaciar").hidden = llegada.vacia;
  }

  function agregar(producto) {
    llegada.agregar(producto);
    pintar(producto.id);
    T.bip(false);
  }

  async function guardar() {
    if (llegada.vacia || ocupado) return;
    ocupado = true;
    try {
      const n = llegada.renglones.length;
      await api("/api/mercancia", { operacion: T.nuevoId(), renglones: llegada.pedido, nota: $("nota").value.trim() || null });
      const piezas = llegada.piezas;
      llegada.vaciar();
      $("nota").value = "";
      pintar();
      aviso("Listo: " + (piezas ? piezas + (piezas === 1 ? " pieza" : " piezas") + " de " : "") + n + (n === 1 ? " producto" : " productos") + " sumados al inventario");
    } catch (e) {
      aviso(e.message, true);
      T.bip(true);
    } finally {
      ocupado = false;
    }
  }

  $("guardar").onclick = guardar;

  let armado = null;
  $("vaciar").onclick = () => {
    const b = $("vaciar");
    if (armado) { clearTimeout(armado); armado = null; llegada.vaciar(); b.classList.remove("seguro"); b.textContent = "Borrar la lista"; pintar(); return; }
    b.classList.add("seguro");
    b.textContent = "¿Seguro? Toca otra vez para borrar";
    armado = setTimeout(() => { armado = null; b.classList.remove("seguro"); b.textContent = "Borrar la lista"; }, 3500);
  };

  T.montar({
    seccion: "mercancia",
    alElegir: agregar,
    codigoNuevo: (codigo) => T.abrirAlta(codigo, {
      conCosto: true,
      sub: "Dalo de alta y se agrega a lo que llegó.",
      boton: "Guardar y agregar",
      alGuardar: (p, costo) => agregar({ ...p, costo }),
    }),
    escribirBusca: () => true,
    antesDeSalir: () => (llegada.vacia ? null : "Primero guarda lo que llegó (o bórralo)"),
  });

  document.addEventListener("keydown", (e) => {
    if (T.capaAbierta()) return;
    const escribiendo = e.target.matches && e.target.matches("input");
    if (e.key === "Enter" && !escribiendo && !e.target.closest("button") && !llegada.vacia) { e.preventDefault(); guardar(); }
  });

  pintar();
})();
