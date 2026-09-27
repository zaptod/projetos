"use strict";
const TOKEN = "painel.token";
const ULTIMO = "painel.ultimo_estado";
const CONTATO = "painel.ultimo_contato";
const TITULOS = {vila: "Vila", diario: "Diário", videos: "Vídeos",
                 comandos: "Comandos", relatorios: "Relatórios"};
const RELATORIOS = ["metas", "funcionamento", "confiabilidade", "auditoria"];
const $ = (id) => document.getElementById(id);

let tela = "vila";
let diarioDesde = "";
let diarioFabrica = null;
let timer = null;

function el(tag, attrs = {}, ...filhos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v; else n.setAttribute(k, v);
  }
  for (const f of filhos) if (f != null) n.append(f);
  return n;
}

function hora(iso) {
  const d = new Date(iso);
  return isNaN(d) ? String(iso).slice(11, 16)
    : d.toLocaleTimeString("pt-BR", {hour: "2-digit", minute: "2-digit"});
}

function ha(segundos) {
  if (segundos == null) return "";
  const m = Math.round(segundos / 60);
  if (m < 1) return "agora";
  if (m < 60) return `há ${m} min`;
  const h = Math.floor(m / 60);
  return h < 24 ? `há ${h} h` : `há ${Math.floor(h / 24)} d`;
}

class ErroApi extends Error {
  constructor(mensagem, status) { super(mensagem); this.status = status; }
}

async function api(caminho, opcoes = {}) {
  const token = localStorage.getItem(TOKEN);
  let resp;
  try {
    resp = await fetch(caminho, {
      ...opcoes,
      headers: {...(opcoes.headers || {}),
                ...(token ? {Authorization: `Bearer ${token}`} : {})},
    });
  } catch (err) {
    // fetch so falha assim quando nao chegou a falar com ninguem: sem
    // rede, ou o Tailscale do celular desligado.
    throw new ErroApi("sem rede", 0);
  }
  if (resp.status === 401) {
    localStorage.removeItem(TOKEN); mostrar();
    throw new ErroApi("não pareado", 401);
  }
  let dados = {};
  try { dados = await resp.json(); } catch (err) { /* 502 do serve vem em texto */ }
  if (!resp.ok) throw new ErroApi(dados.erro || `erro ${resp.status}`, resp.status);
  return dados;
}

function quandoCurto(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return "";
  const hoje = new Date().toDateString() === d.toDateString();
  return hoje ? hora(iso)
    : d.toLocaleDateString("pt-BR", {day: "2-digit", month: "2-digit"}) + " " + hora(iso);
}

// O "desde quando" e o ultimo contato que deu certo, de QUALQUER tela.
// E a mensagem diz de que lado esta o problema: sem rede (quase sempre o
// Tailscale do celular, que o Android desliga) nao e o mesmo que o PC
// respondendo com erro (502 = servidor parado atras do `tailscale serve`).
function conexao(ok, err) {
  const alvo = $("conexao");
  if (ok) {
    localStorage.setItem(CONTATO, new Date().toISOString());
    alvo.className = "";
    alvo.textContent = "ao vivo · " + hora(new Date().toISOString());
    $("aviso").classList.add("oculto");
    return;
  }
  const status = err && err.status;
  if (status === 401) return;
  const contato = localStorage.getItem(CONTATO);
  const desde = contato ? ` desde ${quandoCurto(contato)}` : "";
  alvo.className = "off";
  let texto;
  if (!status) {
    alvo.textContent = "sem conexão" + desde;
    texto = navigator.onLine === false
      ? "O celular está sem internet."
      : "Não consegui falar com o PC. Confira se o Tailscale está ligado neste celular.";
  } else if (status === 502 || status === 503 || status === 504) {
    alvo.textContent = "PC sem o servidor" + desde;
    texto = "O PC atendeu, mas o servidor do app está parado.";
  } else {
    alvo.textContent = "erro do PC" + desde;
    texto = `O PC respondeu com erro: ${err.message}`;
  }
  $("aviso-texto").textContent = texto;
  $("aviso").classList.remove("oculto");
}

// ------------------------------------------------------------- agora
function desenharEstado(e) {
  $("proxima").textContent = e.proxima ? e.proxima.horario : "—";
  const pausa = e.pausa || {};
  $("pausa").textContent = pausa.situacao && pausa.situacao !== "rodando"
    ? "⏸ " + pausa.resumo : "▶ " + (pausa.resumo || "");
  $("pausa").className = pausa.situacao && pausa.situacao !== "rodando"
    ? "erro" : "fraco";

  const prev = $("previsao");
  prev.replaceChildren();
  const p = e.previsao;
  if (p && p.calculando) prev.append(el("div", {class: "fraco"}, "calculando o que sai…"));
  else if (p && !p.falhou) {
    const item = (rotulo, v) => v && prev.append(el("div", {class: "linha"},
      el("span", {class: "emoji"}, rotulo),
      el("span", {class: "corpo"}, v.titulo +
        (v.partes > 1 ? ` · parte ${v.parte}/${v.partes}` : ""))));
    item("📖", p.historias);
    item("⚔", p.builds);
    const gordura = Object.entries(p.gordura || {})
      .map(([k, v]) => `${k}: ${v}`).join(" · ");
    if (gordura) prev.append(el("div", {class: "fraco"}, "estoque (dias) — " + gordura));
  }

  const fab = $("fabricas");
  fab.replaceChildren();
  for (const f of e.fabricas || []) {
    fab.append(el("div", {class: "linha"},
      el("span", {class: "emoji"}, f.emoji),
      el("span", {class: "corpo"}, f.rotulo,
        f.detalhe ? el("div", {class: "fraco"}, f.detalhe) : null),
      el("span", {class: "selo " + f.status},
        f.status === "trabalhando" ? "trabalhando"
          : f.status === "erro" ? "erro" : ha(f.ha_s) || "ocioso")));
  }
}

function desenharEventos(alvo, eventos, vazio) {
  if (!eventos.length && vazio) {
    alvo.replaceChildren(el("div", {class: "ok"}, vazio));
    return;
  }
  for (const ev of eventos) {
    alvo.prepend(el("div", {class: "linha"},
      el("span", {class: "emoji"}, ev.emoji || "•"),
      el("span", {class: "corpo"},
        el("span", {class: "fraco"}, hora(ev.ts) + " "),
        ev.detalhe || ev.etapa || ev.fabrica),
      el("span", {class: "selo " + (ev.status === "erro" ? "erro"
        : ev.status === "inicio" ? "trabalhando" : "ocioso")}, ev.status)));
  }
}

async function carregarAgora() {
  try {
    const e = await api("/api/estado");
    localStorage.setItem(ULTIMO, JSON.stringify({quando: new Date().toISOString(), e}));
    desenharEstado(e);
    const erros = await api("/api/erros?n=6");
    $("erros").replaceChildren();
    desenharEventos($("erros"), erros.reverse(), "✓ nenhum erro registrado");
    conexao(true);
  } catch (err) {
    const ultimo = JSON.parse(localStorage.getItem(ULTIMO) || "null");
    if (ultimo) desenharEstado(ultimo.e);
    conexao(false, err);
  }
}

// ------------------------------------------------------------ diario
async function carregarDiario() {
  try {
    const filtro = diarioFabrica ? `&fabrica=${encodeURIComponent(diarioFabrica)}` : "";
    $("diario-filtro").classList.toggle("oculto", !diarioFabrica);
    $("diario-filtro-nome").textContent = diarioFabrica
      ? `só ${diarioFabrica}` : "";
    const eventos = await api(
      `/api/diario?n=80&desde=${encodeURIComponent(diarioDesde)}${filtro}`);
    if (eventos.length) diarioDesde = eventos[eventos.length - 1].ts;
    desenharEventos($("diario"), eventos);
    conexao(true);
  } catch (err) { conexao(false, err); }
}

// ------------------------------------------------------------ videos
async function carregarVideos() {
  try {
    const lista = await api("/api/videos?n=60");
    const alvo = $("videos");
    alvo.replaceChildren();
    for (const v of lista) {
      const botao = el("button", {class: "acao"}, "▶");
      botao.addEventListener("click", () => tocar(v));
      let publicar = null;
      if (publicarLigado && v.canal === "builds" && v.perfil === "celular"
          && !v.pendencias.length) {
        publicar = el("button", {class: "acao"}, "Publicar");
        publicar.addEventListener("click", () => pedirPublicacao(v));
      }
      const detalhe = [v.canal, v.perfil,
        v.variante && v.variante !== "A" ? `gancho ${v.variante}` : "",
        v.partes > 1 ? `parte ${v.parte}/${v.partes}` : "",
        (v.bytes / 1048576).toFixed(1) + " MB",
        new Date(v.quando * 1000).toLocaleDateString("pt-BR")]
        .filter(Boolean).join(" · ");
      alvo.append(el("div", {class: "linha"},
        el("span", {class: "corpo"}, v.titulo || v.id,
          el("div", {class: "fraco"}, detalhe),
          v.pendencias.length
            ? el("div", {class: "erro"}, "pendente: " + v.pendencias.join(", "))
            : null),
        publicar, botao));
    }
    if (!lista.length) alvo.append(el("div", {class: "fraco"}, "nenhum vídeo pronto."));
    conexao(true);
  } catch (err) { conexao(false, err); }
}

// ------------------------------------------------------------- acoes
// O servidor decide tudo: o que pode, o texto da confirmacao, as recusas.
// A tela so mostra e pede o "sim".
let acoesLigadas = false;
let publicarLigado = false;

function avisar(texto, ruim = false) {
  const t = $("toast");
  t.textContent = texto;
  t.className = "toast" + (ruim ? " ruim" : "");
  clearTimeout(avisar.timer);
  avisar.timer = setTimeout(() => t.classList.add("oculto"), ruim ? 8000 : 5000);
}

async function carregarAcoes() {
  try {
    const info = await api("/api/acoes");
    acoesLigadas = !!info.ligadas;
    publicarLigado = acoesLigadas && !!info.publicar;
    $("controle").classList.toggle("oculto", !acoesLigadas);
    $("gerar-cartao").classList.toggle("oculto", !acoesLigadas);
    if (!acoesLigadas) return;
    const alvo = $("alvo-pausa");
    const atual = alvo.value;
    alvo.replaceChildren(...info.alvos.map((a) => el("option", {value: a}, a)));
    if (info.alvos.includes(atual)) alvo.value = atual;
    $("restantes").textContent = info.restantes == null
      ? "não consegui ler o limite desta hora"
      : `${info.restantes} de ${info.limite_por_hora} gerações/publicações nesta hora`;
  } catch (err) { /* a leitura principal ja mostra a conexao */ }
}

// Abre o dialogo e resolve com o botao escolhido ("cancelar" ao fechar).
function perguntar(texto, {destinos = false, validade = 0} = {}) {
  const d = $("dialogo");
  $("dialogo-texto").textContent = texto;
  $("dialogo-destinos").classList.toggle("oculto", !destinos);
  $("dialogo-sim").classList.toggle("oculto", destinos);
  $("dialogo-sim").disabled = false;
  const prazo = $("dialogo-prazo");
  prazo.textContent = "";
  let relogio = null;
  if (validade) {
    const fim = Date.now() + validade * 1000;
    const tique = () => {
      const falta = Math.max(0, Math.round((fim - Date.now()) / 1000));
      prazo.textContent = falta ? `vale por ${falta} s` : "venceu — peça de novo";
      if (!falta) { $("dialogo-sim").disabled = true; clearInterval(relogio); }
    };
    tique();
    relogio = setInterval(tique, 1000);
  }
  return new Promise((resolve) => {
    d.returnValue = "cancelar";
    d.addEventListener("close", () => {
      clearInterval(relogio);
      resolve(d.returnValue || "cancelar");
    }, {once: true});
    d.showModal();
  });
}

async function agir(acao, args = {}) {
  // as ações do catálogo mandam os campos que a ficha pediu; as antigas
  // (pausar, gerar, publicar) continuam mandando os seus
  try {
    const r = await api("/api/acao", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({acao, args}),
    });
    if (r.confirmar) {
      const escolha = await perguntar(r.texto, {validade: r.vale_s});
      if (escolha !== "confirmar") { avisar("cancelado"); return; }
      const feito = await api("/api/acao/confirmar", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({codigo: r.confirmar}),
      });
      avisar(feito.texto);
    } else {
      avisar(r.texto);
    }
  } catch (err) {
    avisar(err.message, true);
  }
  carregarAcoes();
  if (tela === "agora") carregarAgora();
}

async function pedirPublicacao(v) {
  const gancho = v.variante && v.variante !== "A" ? ` (gancho ${v.variante})` : "";
  const onde = await perguntar(`Publicar «${v.titulo || v.id}»${gancho} onde?`,
                               {destinos: true});
  if (["youtube", "tiktok", "ambos"].includes(onde))
    agir("publicar", {id: v.id, onde});
}

$("btn-pausar").addEventListener("click", () => agir("pausar", {
  alvo: $("alvo-pausa").value,
  minutos: $("prazo-pausa").value ? Number($("prazo-pausa").value) : null,
}));
$("btn-retomar").addEventListener("click", () => {
  const alvo = $("alvo-pausa").value;
  agir("retomar", alvo === "tudo" ? {} : {alvo});
});
$("btn-parar").addEventListener("click", () => agir("parar"));
$("btn-gerar").addEventListener("click", () => agir("gerar"));

let tocando = null;
let renovacoes = 0;

async function tocar(v, desde = 0) {
  try {
    const {url} = await api(`/api/video/${v.canal}/${encodeURIComponent(v.id)}`);
    const player = $("player");
    if (tocando !== v) renovacoes = 0;
    tocando = v;
    $("player-cartao").classList.remove("oculto");
    $("player-titulo").textContent = v.titulo;
    player.src = url;
    if (desde) player.currentTime = desde;
    player.play().catch(() => {});
    if (!desde) window.scrollTo({top: 0, behavior: "smooth"});
  } catch (err) { alert("Não consegui abrir o vídeo: " + err.message); }
}

// O bilhete do video vale 10 minutos. Pausou e voltou depois: o servidor
// responde 410 e o player da erro; pede um bilhete novo e segue de onde parou.
$("player").addEventListener("error", () => {
  if (!tocando || renovacoes >= 3) return;
  renovacoes += 1;
  tocar(tocando, $("player").currentTime || 0);
});

// -------------------------------------------------------- relatorios
function montarAbas() {
  const abas = $("abas-relatorio");
  for (const nome of RELATORIOS) {
    const b = el("button", {class: "acao", "aria-pressed": "false"}, nome);
    b.addEventListener("click", async () => {
      for (const o of abas.children) o.setAttribute("aria-pressed", String(o === b));
      $("relatorio").textContent = "carregando…";
      try {
        const {texto} = await api(`/api/relatorio/${nome}`);
        $("relatorio").textContent = texto.replace(/[*_`]/g, "");
        conexao(true);
      } catch (err) {
        $("relatorio").textContent = "falhou: " + err.message;
        conexao(false, err);
      }
    });
    abas.append(b);
  }
}

// ---------------------------------------------------------- pareamento
$("btn-parear").addEventListener("click", async () => {
  const msg = $("parear-msg");
  msg.textContent = "…";
  try {
    const resp = await fetch("/api/parear", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({codigo: $("codigo").value,
                            nome: navigator.userAgentData?.platform || "celular"}),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || resp.status);
    localStorage.setItem(TOKEN, dados.token);
    $("codigo").value = "";
    msg.textContent = "";
    mostrar();
  } catch (err) { msg.textContent = err.message; }
});

// --------------------------------------------------------------- telas
const CARGAS = {vila: [carregarAgora, 15000], diario: [carregarDiario, 5000],
                videos: [null, 0], comandos: [null, 0], relatorios: [null, 0]};

function mostrar(nova) {
  if (nova && nova !== tela && nova === "diario") {
    diarioDesde = "";                     // filtro novo, lista do zero
    $("diario").replaceChildren();
  }
  if (nova) tela = nova;
  const pareado = !!localStorage.getItem(TOKEN);
  const atual = pareado ? tela : "parear";
  for (const s of document.querySelectorAll("main > section"))
    s.classList.toggle("oculto", s.id !== "tela-" + atual);
  $("nav").classList.toggle("oculto", !pareado);
  $("titulo").textContent = pareado ? TITULOS[tela] : "Parear";
  for (const b of document.querySelectorAll("nav button")) {
    if (b.dataset.tela === tela) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
  clearInterval(timer);
  if (typeof vilaParar === "function") vilaParar();
  if (typeof comandosParar === "function") comandosParar();
  if (!pareado) return;
  if (tela === "vila" && typeof vilaMostrar === "function") vilaMostrar();
  if (tela === "comandos" && typeof comandosMostrar === "function") {
    comandosMostrar();
  }
  carregarAcoes().then(() => { if (tela === "videos") carregarVideos(); });
  const [carga, intervalo] = CARGAS[tela];
  if (carga) {
    carga();
    if (intervalo) timer = setInterval(() => {
      if (document.visibilityState === "visible") carga();
    }, intervalo);
  }
}

for (const b of document.querySelectorAll("nav button"))
  b.addEventListener("click", () => mostrar(b.dataset.tela));
$("btn-tentar").addEventListener("click", () => mostrar());
$("btn-todas").addEventListener("click", () => {
  diarioFabrica = null; diarioDesde = ""; $("diario").replaceChildren();
  carregarDiario();
});
$("vila-mais").addEventListener("click", () => vilaZoom(Vila.zoom * 1.5));
$("vila-menos").addEventListener("click", () => vilaZoom(Vila.zoom / 1.5));
window.addEventListener("online", () => mostrar());
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") mostrar();
});
montarAbas();
mostrar();

// Service worker so existe em contexto seguro (HTTPS do `tailscale serve`).
if ("serviceWorker" in navigator && window.isSecureContext)
  navigator.serviceWorker.register("sw.js").catch(() => {});
