// Guarda la app en el celular para que abra aunque la computadora esté apagada.
// Abre lo guardado al instante y, si la compu contesta, se actualiza para la próxima vez.
const CAJA = "tienda-celular-v3";
const APP = ["/celular", "/static/celular.js", "/static/celular.css", "/static/celular-icono.png",
  "/static/vendor/hanken-grotesk.woff2", "/static/logica.js", "/static/lector.js",
  "/static/vendor/zxing-0.21.3.min.js"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CAJA).then((c) => c.addAll(APP)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CAJA).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  const clave = url.pathname === "/celular" ? "/celular" : e.request;
  // Si llega con la llave (el QR o el ícono), primero la PC: así la página trae el manifiesto
  // con la llave y el ícono que se agregue a inicio sí queda conectado. Sin PC, lo guardado.
  if (url.pathname === "/celular" && url.searchParams.has("llave")) {
    e.respondWith(
      fetch(e.request)
        .then((r) => { if (r.ok) { const copia = r.clone(); e.waitUntil(caches.open(CAJA).then((c) => c.put(clave, copia))); } return r; })
        .catch(() => caches.match(clave).then((g) => g || new Response("Sin conexión", { status: 503 })))
    );
    return;
  }
  e.respondWith(
    caches.open(CAJA).then(async (c) => {
      const guardada = await c.match(clave, { ignoreSearch: true });
      const red = fetch(e.request)
        .then((r) => { if (r.ok) c.put(clave, r.clone()); return r; })
        .catch(() => null);
      if (guardada) { e.waitUntil(red); return guardada; }
      return (await red) || new Response("Sin conexión", { status: 503 });
    })
  );
});
