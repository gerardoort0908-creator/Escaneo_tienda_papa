/* Lee códigos de barras de la cámara: el lector del propio celular si lo tiene, si no ZXing.
   Lo usa la app del celular (celular.js). */
(function (raiz) {
  "use strict";
  const FORMATOS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128", "code_39", "itf", "qr_code"];

  async function nativo() {
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

  /** Traduce el recuadro de la pantalla a pixeles del video (que se ve recortado). */
  function zonaDelRecuadro(video, marcoEl) {
    const vw = video.videoWidth, vh = video.videoHeight;
    if (!vw || !vh) return null;
    const caja = video.getBoundingClientRect();
    const marco = marcoEl.getBoundingClientRect();
    const s = Math.max(caja.width / vw, caja.height / vh); // object-fit: cover
    const ox = (vw * s - caja.width) / 2, oy = (vh * s - caja.height) / 2;
    const sx = Math.max(0, (marco.left - caja.left + ox) / s);
    const sy = Math.max(0, (marco.top - caja.top + oy) / s);
    const sw = Math.min(vw - sx, marco.width / s);
    const sh = Math.min(vh - sy, marco.height / s);
    return sw > 10 && sh > 10 ? { sx, sy, sw, sh } : null;
  }

  function zxing(marcoEl) {
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
      // Solo lo que está dentro del recuadro, reducido: menos pixeles = lectura más rápida.
      const zona = zonaDelRecuadro(video, marcoEl);
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

  /** Devuelve una función que lee un cuadro del video: {codigo, formato} o null. */
  async function crear(marcoEl) {
    return (await nativo()) || zxing(marcoEl);
  }

  /** Prende la cámara trasera en el <video>. Lanza el error del navegador si no se puede. */
  async function abrirCamara(video) {
    video.srcObject = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
    });
    await video.play();
  }

  function cerrarCamara(video) {
    const s = video.srcObject;
    if (s) s.getTracks().forEach((t) => t.stop());
    video.srcObject = null;
  }

  raiz.Lector = { crear, abrirCamara, cerrarCamara };
})(window);
