(function () {
  "use strict";
  const L = window.Logica;
  const $ = (id) => document.getElementById(id);
  const META_MS = 250;
  const latencias = [];
  let info = null;

  function ms(valor) { return Math.round(valor) + " ms"; }

  function mostrarQr(que) {
    $("qr").src = "/api/qr.svg?que=" + que;
    $("p-escaner").setAttribute("aria-pressed", que === "celular");
    $("p-sello").setAttribute("aria-pressed", que === "sello");
    $("pasos-escaner").hidden = que !== "celular";
    $("pasos-sello").hidden = que !== "sello";
    if (info) $("url").textContent = que === "sello" ? info.url_sello : info.url_celular.split("#")[0];
  }

  function pintarMetricas() {
    const r = L.resumen(latencias);
    if (!r) return;
    $("m-cuantos").textContent = r.cuantos;
    for (const k of ["mediana", "p95", "maximo"]) {
      const el = $("m-" + k);
      el.textContent = ms(r[k]);
      el.className = "cifra " + (r[k] <= META_MS ? "bien" : "mal");
    }
  }

  function alLlegar(e) {
    $("titulo").textContent = "Último producto escaneado";
    $("codigo").textContent = e.codigo;
    const g = $("grande");
    g.classList.remove("nuevo");
    void g.offsetWidth;
    g.classList.add("nuevo");

    // Esperamos a que el navegador de verdad dibuje el código antes de medir.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const latencia = Math.max(0, Date.now() - e.t_detectado);
      latencias.push(latencia);
      const lat = $("latencia");
      lat.textContent = "Llegó en " + ms(latencia);
      lat.className = "lat cifra " + (latencia <= META_MS ? "bien" : "mal");

      const fila = document.createElement("tr");
      const hora = new Date(e.t_recibido).toLocaleTimeString("es-MX");
      // Viaje WiFi: del celular a la compu. Dibujar: de que llega a que se ve.
      const viaje = Math.max(0, e.t_recibido - e.t_detectado);
      const columnas = [
        [hora], [e.codigo, "cifra"], [e.formato.replace("_", "-").toUpperCase()],
        [ms(viaje), "n cifra suave"], [ms(Math.max(0, latencia - viaje)), "n cifra suave"], [ms(latencia), "n cifra"],
      ];
      for (const [texto, clase] of columnas) {
        const td = document.createElement("td");
        td.textContent = texto;
        if (clase) td.className = clase;
        fila.appendChild(td);
      }
      $("lista").prepend(fila);
      while ($("lista").children.length > 15) $("lista").lastChild.remove();
      pintarMetricas();
      if (ws && ws.readyState === 1) ws.send(JSON.stringify({ tipo: "mostrado", id: e.id, latencia_ms: latencia }));
    }));
  }

  let ws = null;
  function conectar(intento) {
    ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/pantalla");
    ws.onopen = () => { $("estado-ws").textContent = "lista"; intento = 0; };
    ws.onmessage = (m) => {
      const datos = JSON.parse(m.data);
      if (datos.tipo === "escaneo") alLlegar(datos);
    };
    ws.onclose = () => {
      $("estado-ws").textContent = "reconectando…";
      setTimeout(() => conectar(intento + 1), L.esperaReintento(intento));
    };
  }

  fetch("/api/info").then((r) => r.json()).then((d) => {
    info = d;
    $("sin-wifi").hidden = d.en_wifi;
    mostrarQr("celular");
  });
  $("p-escaner").onclick = () => mostrarQr("celular");
  $("p-sello").onclick = () => mostrarQr("sello");
  conectar(0);
})();
