// Guarda so a CASCA do app (html, icone, manifest) para abrir sem rede.
// Dados e videos nunca entram no cache: eles vem sempre do PC.
const CASCA = "painel-casca-v70";
const ARQUIVOS = ["./", "index.html", "app.js", "vila.js", "comandos.js",
                  "decisoes.js", "assembleia.js", "orquestrador.js", "coordenador.js", "conversa.js", "oficina.js", "equipe.js", "biblioteca.js", "atelie_novo.js", "app.css", "bolinha_hoje.png",
                  "manifest.webmanifest", "icones/icone-192.png",
                  "icones/icone-512.png", "icones/icone-maskable-512.png",
                  "icones/apple-touch-icon.png", "icones/favicon-32.png",
                  "icones/favicon-16.png", "favicon.ico"];

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
  // So a CASCA passa por aqui. O resto (fundos e atlas da Vila com `?v=`,
  // /arte-vila/, as paginas /p/ da Biblioteca) e rede pura: antes toda
  // resposta 200 entrava no cache e cada versao da Vila ficava para sempre
  // (~3,2 MB por arte salva no Ateliê; auditoria 11/10, item 2). O
  // Cache-Control do servidor ja cuida das imagens.
  const caminho = url.pathname === "/" ? "./" : url.pathname.slice(1);
  if (e.request.method !== "GET" || !ARQUIVOS.includes(caminho)) return;
  // rede primeiro (a casca nova chega logo), cache quando o PC nao responde
  // So resposta 200 da propria origem entra no cache: um 404 ou 429
  // guardado viraria a casca quebrada ate a proxima atualizacao.
  // Resposta que nao e 200 (o 502 do `tailscale serve` quando o PC nao
  // atende a tempo) tambem cai na copia guardada: antes o 502 ia direto
  // para a pagina, e o script que ele substituia sumia (30/09: o
  // conversa.js, e com ele o "Conversar" e o "Criar").
  e.respondWith(fetch(e.request).then((resp) => {
    if (resp.status === 200 && resp.type === "basic") {
      const copia = resp.clone();
      caches.open(CASCA).then((c) => c.put(e.request, copia));
      return resp;
    }
    return caches.match(e.request).then((guardada) => guardada || resp);
  }).catch(() => caches.match(e.request)));
});
