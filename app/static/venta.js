/* Cuentas de la pantalla de vender, sin pantalla ni red, para poder probarlas aparte.
   Todo el dinero va en centavos enteros, igual que en la base de datos. */
(function (raiz) {
  "use strict";

  const PASO_GRANEL = 500; // gramos: el huevo se vende de medio kilo en medio kilo
  const BILLETES = [100000, 50000, 20000, 10000, 5000, 2000];
  const MONEDAS = [2000, 1000, 500, 200, 100, 50];
  const TOPE = 100000000; // $1,000,000

  /** División entera redondeando la mitad hacia arriba (igual que tienda/nucleo/dinero.py). */
  function dividirRedondeando(numerador, divisor) {
    return Math.floor((2 * numerador + divisor) / (2 * divisor));
  }

  /** Lo que cuesta un renglón. Granel: precio por kilo × kilos, redondeado al peso
      (medio kilo de huevo a $45 = $22.50 → $23). Igual que ventas.subtotal(). */
  function subtotal(precio, cantidad, unidad) {
    if (unidad === "kg") return dividirRedondeando(precio * cantidad, 1000 * 100) * 100;
    return precio * cantidad;
  }

  function paso(unidad) { return unidad === "kg" ? PASO_GRANEL : 1; }

  /** 2200 → "$22"; 1850 → "$18.50"; 125000 → "$1,250". */
  function pesos(centavos) {
    const signo = centavos < 0 ? "-" : "";
    const c = Math.abs(centavos);
    const entero = Math.floor(c / 100).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    const resto = c % 100;
    return signo + "$" + entero + (resto ? "." + String(resto).padStart(2, "0") : "");
  }

  /** Para las cifras grandes: {entero: "1,250", centavos: "50" | ""}. */
  function partes(centavos) {
    const texto = pesos(centavos).replace("-", "").slice(1);
    const [entero, cts] = texto.split(".");
    return { entero, centavos: cts || "" };
  }

  /** 500 → "½ kg"; 1000 → "1 kg"; 1500 → "1½ kg". Pieza: "3". */
  function cantidadTexto(cantidad, unidad) {
    if (unidad !== "kg") return String(cantidad);
    const medios = Math.round(cantidad / PASO_GRANEL);
    const kilos = Math.floor(medios / 2);
    return (kilos ? String(kilos) : "") + (medios % 2 ? "½" : "") + " kg";
  }

  /** Lo que se escribe en "Otra cantidad" ("120", "120.5", "$1,000") → centavos, o null. */
  function leerMonto(texto) {
    const limpio = String(texto || "").replace(/[$,\s]/g, "");
    if (!/^\d+(\.\d{0,2})?$/.test(limpio)) return null;
    const [entero, dec = ""] = limpio.split(".");
    const centavos = Number(entero) * 100 + Number((dec + "00").slice(0, 2));
    return centavos > 0 && centavos <= TOPE ? centavos : null;
  }

  /** La cuenta del cliente. Lo último escaneado queda arriba. */
  function crearCuenta() {
    let renglones = [];

    function agregar(producto) {
      const i = renglones.findIndex((r) => r.producto.id === producto.id);
      if (i >= 0) {
        const [r] = renglones.splice(i, 1);
        r.cantidad += paso(r.producto.unidad);
        r.producto = producto; // por si cambió el precio o la existencia
        renglones.unshift(r);
        return r;
      }
      const r = { producto, cantidad: paso(producto.unidad) };
      renglones.unshift(r);
      return r;
    }

    /** −/+ en un renglón. Si llega a cero, el renglón se quita. */
    function cambiar(productoId, pasos) {
      const r = renglones.find((x) => x.producto.id === productoId);
      if (!r) return null;
      r.cantidad += pasos * paso(r.producto.unidad);
      if (r.cantidad <= 0) { quitar(productoId); return null; }
      return r;
    }

    function quitar(productoId) {
      renglones = renglones.filter((x) => x.producto.id !== productoId);
    }

    return {
      agregar, cambiar, quitar,
      vaciar() { renglones = []; },
      get renglones() { return renglones.slice(); },
      get vacia() { return renglones.length === 0; },
      get total() { return renglones.reduce((s, r) => s + subtotal(r.producto.precio, r.cantidad, r.producto.unidad), 0); },
      /** Piezas: cada una cuenta. Granel: cada producto cuenta como uno. */
      get articulos() { return renglones.reduce((s, r) => s + (r.producto.unidad === "kg" ? 1 : r.cantidad), 0); },
      /** Lo que se manda a cobrar. */
      get pedido() { return renglones.map((r) => ({ producto_id: r.producto.id, cantidad: r.cantidad })); },
    };
  }

  /** El dinero que entrega el cliente, pieza por pieza (billetes, monedas u otra cantidad). */
  function crearPago(total) {
    let piezas = [];
    return {
      total,
      poner(valor) { if (valor > 0) piezas.push(valor); },
      /** Quita una pieza de ese valor (la última que se puso). */
      quitar(valor) { const i = piezas.lastIndexOf(valor); if (i >= 0) piezas.splice(i, 1); },
      exacto() { piezas = [total]; },
      limpiar() { piezas = []; },
      get piezas() { return piezas.slice(); },
      get recibido() { return piezas.reduce((s, v) => s + v, 0); },
      get falta() { return Math.max(0, total - this.recibido); },
      get cambio() { return Math.max(0, this.recibido - total); },
      get alcanza() { return this.recibido >= total; },
    };
  }

  /** Agrupa piezas iguales: [50000, 2000, 2000] → [{valor: 50000, n: 1}, {valor: 2000, n: 2}], de mayor a menor. */
  function agrupar(valores) {
    const cuenta = new Map();
    for (const v of valores) cuenta.set(v, (cuenta.get(v) || 0) + 1);
    return [...cuenta.entries()].sort((a, b) => b[0] - a[0]).map(([valor, n]) => ({ valor, n }));
  }

  /**
   * Cómo dar el cambio con la menor cantidad de billetes y monedas.
   * Los billetes de $20 se prefieren sobre la moneda de $20 (es la que más se usa).
   * `resto` son los centavos que no se pueden dar con monedas de 50¢ (casi nunca pasa,
   * porque los precios son en pesos cerrados).
   */
  function desglose(cambio) {
    let falta = cambio;
    const piezas = [];
    for (const v of BILLETES) while (falta >= v) { piezas.push({ tipo: "billete", valor: v }); falta -= v; }
    for (const v of MONEDAS) {
      if (v === 2000) continue; // el billete de $20 ya lo cubrió
      while (falta >= v) { piezas.push({ tipo: "moneda", valor: v }); falta -= v; }
    }
    const grupos = [];
    for (const p of piezas) {
      const ultimo = grupos[grupos.length - 1];
      if (ultimo && ultimo.tipo === p.tipo && ultimo.valor === p.valor) ultimo.n += 1;
      else grupos.push({ ...p, n: 1 });
    }
    return { grupos, resto: falta };
  }

  const api = {
    PASO_GRANEL, BILLETES, MONEDAS, subtotal, paso, pesos, partes, cantidadTexto, leerMonto,
    crearCuenta, crearPago, agrupar, desglose, dividirRedondeando,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.Venta = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
