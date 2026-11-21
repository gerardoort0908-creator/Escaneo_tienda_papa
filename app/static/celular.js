(function () {
  "use strict";
  const L = window.Logica;
  const $ = (id) => document.getElementById(id);
  const FORMATOS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128", "code_39", "itf", "qr_code"];

  let llave = L.llaveDeHash(location.hash);
  try {
    if (llave) localStorage.setItem("llave", llave);
    else llave = localStorage.getItem("llave");
  } catch (_) { /* sin almacenamiento: usamos la del enlace */ }
  if (location.hash) history.replaceState(null, "", location.pathname);

  let desfase = 0; // ms que se suman al reloj del celular para tener la hora de la compu
  let audio = null;
  const aceptar = L.crearFiltroRepetidos(1500);
  const confirmar = L.crearConfirmador(2, 600); // dos lecturas iguales en menos de 0.6 s

  // ---------- Avisos en pantalla ----------
  function conexion(texto, tipo) {
    $("conexion").textContent = texto;
    $("punto").className = "punto " + (tipo || "");
  }
  function problema(texto) {
    const p = $("problema");
    p.textContent = texto;
    p.classList.remove("oculto");
    $("inicio").classList.remove("oculto");
  }
  function destello(bien) {
    const d = $("destello");
    d.classList.toggle("mal", !bien);
    d.classList.add("si");
    requestAnimationFrame(() => requestAnimationFrame(() => d.classList.remove("si")));
  }
  function pitido(bien) {
    if (navigator.vibrate) navigator.vibrate(bien ? 40 : [60, 60, 60]);
    if (!audio) return;
    const o = audio.createOscillator();
    const g = audio.createGain();
    o.frequency.value = bien ? 1760 : 330;
    g.gain.setValueAtTime(0.18, audio.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.12);
    o.connect(g).connect(audio.destination);
    o.start();
    o.stop(audio.currentTime + 0.13);
  }

  // ---------- Reloj y conexión ----------
  // Cada 2 s preguntamos la hora a la computadora. Sirve para dos cosas:
  // 1) mantener abierta la conexión segura y despierto el WiFi del celular, así el
  //    escaneo no espera a reconectarse (eso puede costar más de 100 ms);
  // 2) afinar el desfase de relojes con las mediciones más recientes.
  const mediciones = [];
  async function medirHora() {
    const t0 = Date.now();
    try {
      const r = await fetch("/api/hora", { cache: "no-store" });
      const { ts } = await r.json();
      mediciones.push({ t0, ts, t1: Date.now() });
      if (mediciones.length > 15) mediciones.shift();
      desfase = L.calcularDesfase(mediciones).desfase;
      conexion("Conectado", "ok");
    } catch (_) {
      conexion("Sin conexión con la computadora", "mal");
    }
  }
  async function latido() {
    if (document.visibilityState === "visible") await medirHora();
    setTimeout(latido, 2000);
  }

  // ---------- Envío ----------
  async function enviar(escaneo, intento) {
    let r;
    try {
      r = await fetch("/api/escaneo", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Llave": llave || "" },
        body: JSON.stringify(escaneo),
        keepalive: true,
      });
    } catch (_) {
      conexion("Reintentando…", "mal");
      setTimeout(() => enviar(escaneo, intento + 1), L.esperaReintento(intento));
      return;
    }
    if (r.ok) {
      const datos = await r.json();
      conexion("Conectado", "ok");
      $("estado").textContent = datos.pantallas
        ? "✓ Llegó a la computadora"
        : "✓ Llegó, pero la pantalla de la computadora está cerrada";
      return;
    }
    if (r.status === 401) {
      pitido(false);
      problema("Este celular no está autorizado. Escanea otra vez el QR que aparece en la computadora.");
      return;
    }
    if (r.status === 422) {
      pitido(false);
      destello(false);
      $("estado").textContent = "Se leyó mal. Vuelve a escanearlo.";
      return;
    }
    setTimeout(() => enviar(escaneo, intento + 1), L.esperaReintento(intento));
  }

  function alDetectar(codigo, formato) {
    const ahora = Date.now();
    if (!aceptar(codigo, ahora)) return;
    // Primero se envía y después se avisa en el celular, para no retrasar el envío.
    enviar({ id: L.nuevoId(crypto), codigo, formato, t_detectado: ahora + desfase }, 0);
    pitido(true);
    destello(true);
    $("codigo").textContent = codigo;
    $("estado").textContent = "Enviando…";
  }

  // ---------- Lectores ----------
  async function lectorNativo() {
    if (!("BarcodeDetector" in window)) return null;
    try {
      const soportados = await BarcodeDetector.getSupportedFormats();
      if (!soportados.includes("ean_13")) return null;
      const detector = new BarcodeDetector({ formats: FORMATOS.filter((f) => soportados.includes(f)) });
      return async (video) => {
        const r = await detector.detect(video);
        return r.length ? { codigo: r[0].rawValue, formato: r[0].format } : null;
      };
    } catch (_) {
      return null;
    }
  }

  /** Traduce el recuadro dorado de la pantalla a pixeles del video (que se ve recortado). */
  function zonaDelRecuadro(video) {
    const vw = video.videoWidth, vh = video.videoHeight;
    if (!vw || !vh) return null;
    const caja = video.getBoundingClientRect();
    const marco = document.querySelector(".franja").getBoundingClientRect();
    const s = Math.max(caja.width / vw, caja.height / vh); // object-fit: cover
    const ox = (vw * s - caja.width) / 2, oy = (vh * s - caja.height) / 2;
    const sx = Math.max(0, (marco.left - caja.left + ox) / s);
    const sy = Math.max(0, (marco.top - caja.top + oy) / s);
    const sw = Math.min(vw - sx, marco.width / s);
    const sh = Math.min(vh - sy, marco.height / s);
    return sw > 10 && sh > 10 ? { sx, sy, sw, sh } : null;
  }

  function lectorZxing() {
    const Z = window.ZXing;
    const hints = new Map();
    hints.set(Z.DecodeHintType.POSSIBLE_FORMATS, [
      Z.BarcodeFormat.EAN_13, Z.BarcodeFormat.EAN_8, Z.BarcodeFormat.UPC_A, Z.BarcodeFormat.UPC_E,
      Z.BarcodeFormat.CODE_128, Z.BarcodeFormat.CODE_39, Z.BarcodeFormat.ITF, Z.BarcodeFormat.QR_CODE,
    ]);
    const lector = new Z.MultiFormatReader();
    lector.setHints(hints);
    const lienzo = document.createElement("canvas");
    const ctx = lienzo.getContext("2d", { willReadFrequently: true });
    return async (video) => {
      // Solo lo que está dentro del recuadro dorado, reducido: menos pixeles = lectura más rápida.
      const zona = zonaDelRecuadro(video);
      if (!zona) return null;
      const { sx, sy, sw, sh } = zona;
      const escala = Math.min(1, 800 / sw);
      lienzo.width = Math.round(sw * escala);
      lienzo.height = Math.round(sh * escala);
      ctx.drawImage(video, sx, sy, sw, sh, 0, 0, lienzo.width, lienzo.height);
      try {
        const fuente = new Z.HTMLCanvasElementLuminanceSource(lienzo);
        const r = lector.decodeWithState(new Z.BinaryBitmap(new Z.HybridBinarizer(fuente)));
        return { codigo: r.getText(), formato: Z.BarcodeFormat[r.getBarcodeFormat()].toLowerCase() };
      } catch (_) {
        return null; // no hay código en este cuadro
      } finally {
        lector.reset();
      }
    };
  }

  async function empezar() {
    $("problema").classList.add("oculto");
    if (!window.isSecureContext || !navigator.mediaDevices) {
      problema("La cámara está bloqueada porque la página no es segura. Abre el enlace del QR (empieza con https).");
      return;
    }
    if (!llave) {
      problema("Falta la llave. Escanea el QR que aparece en la pantalla de la computadora.");
      return;
    }
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      await audio.resume();
    } catch (_) { audio = null; }

    const video = $("video");
    try {
      video.srcObject = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      await video.play();
    } catch (e) {
      problema(
        e && e.name === "NotAllowedError"
          ? "No diste permiso para la cámara. Toca el candado o \"aA\" junto a la dirección y permite la cámara."
          : "No se pudo abrir la cámara: " + (e && e.message ? e.message : e)
      );
      return;
    }
    $("inicio").classList.add("oculto");

    const leer = (await lectorNativo()) || lectorZxing();
    let ocupado = false;
    const vuelta = async () => {
      if (!ocupado && video.readyState >= 2) {
        ocupado = true;
        try {
          const r = await leer(video);
          if (r && confirmar(r.codigo, Date.now())) alDetectar(r.codigo, r.formato);
        } catch (_) { /* cuadro dañado, seguimos */ }
        ocupado = false;
      }
      requestAnimationFrame(vuelta);
    };
    requestAnimationFrame(vuelta);
  }

  $("empezar").addEventListener("click", empezar);
  (async () => {
    for (let i = 0; i < 5; i++) await medirHora();
    setTimeout(latido, 2000);
  })();
})();
