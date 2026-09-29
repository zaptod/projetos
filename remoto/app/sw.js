// Guarda so a CASCA do app (html, icone, manifest) para abrir sem rede.
// Dados e videos nunca entram no cache: eles vem sempre do PC.
const CASCA = "painel-casca-v12";
const ARQUIVOS = ["./", "index.html", "app.js", "vila.js", "comandos.js",
                  "decisoes.js", "orquestrador.js", "app.css", "manifest.webmanifest", "icone.svg"];

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
  // So resposta 200 da propria origem entra no cache: um 404 ou 429
  // guardado viraria a casca quebrada ate a proxima atualizacao.
  e.respondWith(fetch(e.request).then((resp) => {
    if (resp.status === 200 && resp.type === "basic") {
      const copia = resp.clone();
      caches.open(CASCA).then((c) => c.put(e.request, copia));
    }
    return resp;
  }).catch(() => caches.match(e.request)));
});
