// Guarda so a CASCA do app (html, icone, manifest) para abrir sem rede.
// Dados e videos nunca entram no cache: eles vem sempre do PC.
const CASCA = "painel-casca-v1";
const ARQUIVOS = ["./", "index.html", "manifest.webmanifest", "icone.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CASCA).then((c) => c.addAll(ARQUIVOS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((chaves) => Promise.all(
    chaves.filter((k) => k !== CASCA).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")
      || url.pathname.startsWith("/v/")) return;
  // rede primeiro (a casca nova chega logo), cache quando o PC nao responde
  e.respondWith(fetch(e.request).then((resp) => {
    const copia = resp.clone();
    caches.open(CASCA).then((c) => c.put(e.request, copia));
    return resp;
  }).catch(() => caches.match(e.request)));
});
