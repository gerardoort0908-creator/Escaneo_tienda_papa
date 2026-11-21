/* Cuentas de Productos y Llegó mercancía, sin pantalla ni red, para poder probarlas aparte.
   Dinero en centavos; el granel en gramos. */
(function (raiz) {
  "use strict";

  /** bien / acabando / acabado, igual que el servidor (app/inventario.py). */
  function nivel(existencia, minimo) {
    if (existencia <= 0) return "acabado";
    if (existencia <= minimo) return "acabando";
    return "bien";
  }

  const NIVELES = {
    bien: { texto: "Bien", color: "#5BE39B" },
    acabando: { texto: "Se está acabando", color: "#F2B45C" },
    acabado: { texto: "Se acabó", color: "#E8806E" },
  };

  /** Qué tan llena se ve la barra: el mínimo queda a un tercio. */
  function llenado(existencia, minimo) {
    if (existencia <= 0) return 0;
    const tope = Math.max(minimo * 3, 1);
    return Math.min(1, existencia / tope);
  }

  /** Cuánto se gana por pieza (o por kilo) y qué porcentaje del precio es. */
  function ganancia(precio, costo) {
    const porUnidad = precio - costo;
    const porcentaje = precio > 0 ? Math.round((porUnidad * 100) / precio) : 0;
    return { porUnidad, porcentaje, pierde: porUnidad < 0 };
  }

  /** "22.5" o "22½" kilos → gramos (22500), o null. Hasta gramos exactos. */
  function leerKilos(texto) {
    const limpio = String(texto || "").trim().replace("½", ".5").replace(",", ".").replace(/\s*kg$/i, "");
    if (!/^\d*(\.\d{1,3})?$/.test(limpio) || limpio === "" || limpio === ".") return null;
    const gramos = Math.round(Number(limpio) * 1000);
    return gramos > 0 && gramos <= 10000000 ? gramos : null;
  }

  /** Gramos → "22.5" (para mostrar en un campo de kilos). */
  function kilosTexto(gramos) {
    return String(Math.round(gramos) / 1000);
  }

  /** Lo que cuesta un renglón que llegó (el costo del granel es por kilo). */
  function costoRenglon(costo, cantidad, unidad) {
    if (unidad === "kg") return Math.floor((2 * costo * cantidad + 1000) / 2000);
    return costo * cantidad;
  }

  /** La lista de "Llegó mercancía". Lo último escaneado queda arriba. */
  function crearLlegada() {
    let renglones = [];
    const pasoDe = (u) => (u === "kg" ? 1000 : 1); // al escanear o con + se suma 1 pieza o 1 kilo

    function agregar(producto) {
      const i = renglones.findIndex((r) => r.producto.id === producto.id);
      if (i >= 0) {
        const [r] = renglones.splice(i, 1);
        r.cantidad += pasoDe(r.producto.unidad);
        renglones.unshift(r);
        return r;
      }
      const r = { producto, cantidad: pasoDe(producto.unidad), costo: producto.costo || 0 };
      renglones.unshift(r);
      return r;
    }

    function buscar(id) { return renglones.find((r) => r.producto.id === id); }

    return {
      agregar,
      /** −/+ : de 1 en 1 (o de kilo en kilo). En cero se quita. */
      cambiar(id, pasos) {
        const r = buscar(id);
        if (!r) return;
        r.cantidad += pasos * pasoDe(r.producto.unidad);
        if (r.cantidad <= 0) renglones = renglones.filter((x) => x !== r);
      },
      poner(id, cantidad) { const r = buscar(id); if (r && cantidad > 0) r.cantidad = cantidad; },
      costo(id, centavos) { const r = buscar(id); if (r && centavos >= 0) r.costo = centavos; },
      quitar(id) { renglones = renglones.filter((r) => r.producto.id !== id); },
      vaciar() { renglones = []; },
      get renglones() { return renglones.slice(); },
      get vacia() { return renglones.length === 0; },
      get piezas() { return renglones.filter((r) => r.producto.unidad !== "kg").reduce((s, r) => s + r.cantidad, 0); },
      get gramos() { return renglones.filter((r) => r.producto.unidad === "kg").reduce((s, r) => s + r.cantidad, 0); },
      get costoTotal() { return renglones.reduce((s, r) => s + costoRenglon(r.costo, r.cantidad, r.producto.unidad), 0); },
      get pedido() { return renglones.map((r) => ({ producto_id: r.producto.id, cantidad: r.cantidad, costo: r.costo })); },
    };
  }

  const api = { nivel, NIVELES, llenado, ganancia, leerKilos, kilosTexto, costoRenglon, crearLlegada };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.Inventario = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
