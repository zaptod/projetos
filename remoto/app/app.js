"use strict";
const TOKEN = "painel.token";
const ULTIMO = "painel.ultimo_estado";
const CONTATO = "painel.ultimo_contato";
// A Vila é a tela; as outras áreas são objetos dela, com nome de objeto.
const TITULOS = {vila: "Vila", agora: "Agora", oficina: "Agora · Codex",
                 coordenador: "Agora · Coordenador", decisoes: "Decidir", sprites: "Decidir · Sprites", assembleias: "Decidir · Assembleia",
                 comandos: "Mandar", conversa: "Mandar · IAs",
                 videos: "Ver · Cinema", biblioteca: "Ver · Biblioteca",
                 relatorios: "Ver · Pergaminhos", diario: "Ver · Diário", arena: "Arena",
                 atelie: "Arena · Ateliê"};
// Os QUATRO objetos da prateleira, um por pergunta (decisão do Adrian,
// app-e-bot/app-reorganizar, 02/10/2026: "Voce realmente acha que o app está
// bem organizado?"). Antes eram 7 objetos e mais 4 telas que só abriam por
// dentro de outras. Cada objeto tem as suas telas como ABAS; a primeira é a
// que abre da primeira vez, e depois volta a última que ele usou.
//   Agora   — o que está rodando e o que vem a seguir;
//   Decidir — o Grimório;
//   Mandar  — todos os botões de comando (e a conversa com as IAs);
//   Ver     — Cinema, Biblioteca, Pergaminhos e Diário.
// (o ️ pede o desenho colorido: sem ele 🛰 e 🎞 saem como glifo de texto)
const OBJETOS = {
  agora: [["agora", "⏳", "Agora"], ["oficina", "🔧", "Codex"],
          ["coordenador", "🛰️", "Coordenador"]],
  decidir: [["decisoes", "📖", "Grimório"], ["sprites", "🎨", "Sprites"], ["assembleias", "🏛️", "Assembleia"]],
  mandar: [["comandos", "🛠️", "Comandos"], ["conversa", "💬", "IAs"]],
  ver: [["videos", "🎞️", "Cinema"], ["biblioteca", "📚", "Biblioteca"],
        ["relatorios", "📜", "Pergaminhos"], ["diario", "📓", "Diário"]],
  arena: [["arena", "⚔️", "Arena"], ["atelie", "🖌️", "Ateliê"]],
};
const ABA_DO_OBJETO = {};             // a última aba usada de cada objeto

function objetoDe(nome) {
  for (const [objeto, abas] of Object.entries(OBJETOS))
    if (abas.some(([t]) => t === nome)) return objeto;
  return null;
}
const RELATORIOS = ["metas", "funcionamento", "confiabilidade", "auditoria"];
const $ = (id) => document.getElementById(id);

let tela = "vila";
let diarioDesde = "";
let diarioFabrica = null;
let timer = null;

// A casca que ESTE aparelho tem aberta (o servidor escreve no index.html) e
// o relógio do PC. O PWA volta do fundo com o mesmo JavaScript de horas
// atrás; cada resposta diz a casca do disco (X-Casca), e diferente = recarregar.
// As horas da API vêm sem fuso, na hora do PC: com o Date e o X-Fuso-Min das
// respostas, "há X min" sai certo mesmo com o relógio do celular adiantado.
const CASCA_MINHA = (document.querySelector('meta[name="casca"]') || {}).content || "";
const Relogio = {desvio: 0, fuso: null};
const Casca = {nova: null};

function agoraPC() { return Date.now() + Relogio.desvio; }

// Uma hora da API ("2026-09-29T00:58:45", sem fuso) como instante: é a hora
// do PC, então usa o fuso DELE (o celular pode estar em outro).
function dataPC(iso) {
  const s = String(iso == null ? "" : iso);
  const m = s.match(/^(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d)(?::(\d\d))?(?:\.\d+)?$/);
  if (!m || Relogio.fuso == null) return new Date(s);
  return new Date(Date.UTC(+m[1], m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0))
    - Relogio.fuso * 60000);
}

function lerRelogio(resp) {
  const data = Date.parse(resp.headers.get("Date") || "");
  // o Date tem 1 s de resolução: só corrige quando o desvio muda de verdade
  if (!isNaN(data) && Math.abs(data - Date.now() - Relogio.desvio) > 1500)
    Relogio.desvio = data - Date.now();
  const fuso = Number(resp.headers.get("X-Fuso-Min"));
  if (resp.headers.get("X-Fuso-Min") !== null && !isNaN(fuso)) Relogio.fuso = fuso;
  const casca = resp.headers.get("X-Casca");
  if (casca && casca !== CASCA_MINHA) cascaNova(casca);
}

// Recarregar só quando não perde nada: na Vila, sem diálogo aberto. Senão, a
// faixa pede o toque. Uma vez por versão (o sessionStorage segura o laço).
function cascaSegura() {
  return tela === "vila" && !document.querySelector("dialog[open]");
}

function cascaNova(versao) {
  Casca.nova = versao;
  if (CASCA_MINHA && cascaSegura()
      && sessionStorage.getItem("painel.recarreguei") !== versao) {
    sessionStorage.setItem("painel.recarreguei", versao);
    location.reload();
    return;
  }
  $("casca-nova").classList.remove("oculto");
}

function el(tag, attrs = {}, ...filhos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v; else n.setAttribute(k, v);
  }
  for (const f of filhos) if (f != null) n.append(f);
  return n;
}

function hora(iso) {
  const d = dataPC(iso);
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
  // `codigo` é o que o servidor manda quando a tela precisa distinguir o
  // motivo (ex.: "fila_mudou" no 409 da reordenação); `dados` é o corpo.
  constructor(mensagem, status, dados = {}) {
    super(mensagem); this.status = status; this.codigo = dados.codigo || ""; this.dados = dados;
  }
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
  lerRelogio(resp);
  if (resp.status === 401) {
    localStorage.removeItem(TOKEN); mostrar();
    throw new ErroApi("não pareado", 401);
  }
  let dados = {};
  try { dados = await resp.json(); } catch (err) { /* 502 do serve vem em texto */ }
  if (!resp.ok) throw new ErroApi(dados.erro || `erro ${resp.status}`, resp.status, dados);
  return dados;
}

function quandoCurto(iso) {
  const d = dataPC(iso);
  if (isNaN(d)) return "";
  const hoje = new Date(agoraPC()).toDateString() === d.toDateString();
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
    // O lote da semana (30/09): o texto e a regra vêm prontos do PC
    // (remoto.lote.resumo, o mesmo do /lote do bot); aqui só a cor.
    // Sem o resumo, diz que não contou: linha que some parece estoque bom.
    const lote = p.lote || {};
    const canais = lote.canais || {};
    if (!Object.keys(canais).length) {
      prev.append(el("div", {class: "erro"}, "lote da semana — não deu para contar o estoque"));
    } else {
      prev.append(el("div", {class: "fraco"},
        "lote da semana" + (lote.cobertura ? " — " + lote.cobertura : "")));
      for (const [canal, emoji] of [["historias", "📖"], ["builds", "⚔"]]) {
        const f = canais[canal] || {};
        const ruim = !f.contou || f.magro;
        prev.append(el("div", {class: ruim ? "erro" : f.faltam ? "fraco" : "ok"},
          `${emoji} ${f.texto || "não deu para contar o estoque"}`));
      }
      if (lote.calendario) prev.append(el("div", {class: "fraco"}, lote.calendario));
    }
    // Depois de muito tempo sem ninguém olhar, a primeira resposta é a
    // previsão guardada: a tela diz a idade enquanto o PC recalcula.
    if (p.vencida) prev.append(el("div", {class: "fraco previsao-velha"},
      `previsão ${ha(p.idade_s)}; recalculando…`));
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
    // a previsão velha está sendo refeita (leva ~2 s): busca de novo logo
    if (e.previsao && (e.previsao.vencida || e.previsao.calculando)
        && !carregarAgora.logo) {
      carregarAgora.logo = setTimeout(() => {
        carregarAgora.logo = null;
        if (tela === "vila" || tela === "agora") carregarAgora();
      }, 4000);
    }
    const erros = await api("/api/erros?n=6");
    $("erros").replaceChildren();
    desenharEventos($("erros"), erros.reverse(), "✓ nenhum erro registrado");
    conexao(true);
    // o selo da Mesa de comando na prateleira (teto, fora do ar, pendentes)
    if (tela === "vila" && typeof orquestradorSelo === "function") orquestradorSelo();
    // o selo do Grimório (escolhas esperando) vale em qualquer tela
    if (typeof grimorioSelo === "function") grimorioSelo();
    if (typeof spritesSelo === "function") spritesSelo();
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
  if (tela === "vila" || tela === "agora") carregarAgora();
  // o Controle mora em Mandar: o histórico dos comandos mostra o efeito
  if (tela === "comandos" && typeof comandosCarregarTarefas === "function")
    comandosCarregarTarefas().catch(() => {});
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
    if (!desde) $("tela-videos").scrollTo({top: 0, behavior: "smooth"});
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
// ------------------------------------------------ o interruptor do Claude
// Pedido do Adrian (29/09): "usar o Claude está proibido até segunda ordem,
// crie algo no app para ligar e desligar isso". O toque grava DIRETO no PC
// (`POST /api/claude`, com o alvo, não "inverter"): com o Claude proibido o
// orquestrador não acorda com comando, então isto não pode ser comando.
// Aparece UMA vez, no topo de Mandar, preso ao rolar (até 02/10 estava na
// Mesa e na Bancada); dois toques: o interruptor e o "Confirmar" do diálogo.
// Em Agora fica só a faixa que diz que está proibido (o porquê de nada rodar).
const Claude = {dados: null, enviando: false};
const CLAUDE_INTERRUPTORES = ["claude-bancada"];

function claudeDesde(c) {
  if (!c || !c.em) return c && c.origem === "sem_arquivo" ? "nunca foi mudado" : "";
  return `desde ${quandoCurto(c.em)}` + (c.por ? ` · ${c.por}` : "");
}

function claudeDesenhar(c) {
  if (!c) return;
  Claude.dados = c;
  const proibido = !c.liberado;
  for (const id of CLAUDE_INTERRUPTORES) {
    const alvo = $(id);
    if (!alvo) continue;
    const botao = el("button", {class: "claude-botao", type: "button",
                                "aria-pressed": String(!proibido),
                                "data-claude": proibido ? "proibido" : "liberado"},
      el("span", {class: "claude-rotulo"}, "🤖 Claude: ",
        el("strong", {}, proibido ? "PROIBIDO" : "LIBERADO")),
      el("span", {class: "claude-desde"}, claudeDesde(c)),
      el("span", {class: "claude-dica"},
        proibido ? "tocar para liberar" : "tocar para proibir"));
    botao.disabled = Claude.enviando;
    botao.addEventListener("click", claudeTrocar);
    alvo.replaceChildren(botao);
    alvo.classList.toggle("proibido", proibido);
    alvo.classList.toggle("liberado", !proibido);
  }
  const faixa = $("claude-faixa");
  if (faixa) {
    faixa.textContent = proibido
      ? `Claude proibido ${c.desde_hhmm ? "desde " + c.desde_hhmm : ""}`.trim()
        + " — nenhum agente, sonda ou apuração roda; os comandos ficam guardados."
        + (c.origem === "ilegivel" ? ` (${c.motivo})` : "")
      : "";
    faixa.classList.toggle("oculto", !proibido);
  }
}

async function claudeCarregar() {
  try { claudeDesenhar(await api("/api/claude")); } catch (err) { /* a tela já avisa */ }
}

async function claudeTrocar() {
  if (Claude.enviando || !Claude.dados) return;
  const liberar = !Claude.dados.liberado;
  const texto = liberar
    ? "Liberar o Claude? A sonda de uso, o apurador e os agentes voltam a rodar, "
      + "e o orquestrador acorda com os comandos que ficaram guardados."
    : "Proibir o Claude? Nenhum agente é disparado, a sonda de uso e a apuração "
      + "de erros param, e os comandos da Mesa ficam guardados até você liberar.";
  if (await perguntar(texto) !== "confirmar") return;
  Claude.enviando = true;
  claudeDesenhar(Claude.dados);
  try {
    const r = await api("/api/claude", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({liberar})});
    Claude.enviando = false;
    claudeDesenhar(r.claude);
    avisar(r.mudou ? (liberar ? "Claude liberado" : "Claude proibido")
      + " — avisei no Telegram" : "já estava assim");
    if (typeof orqCarregar === "function" && (tela === "agora" || tela === "comandos"))
      orqCarregar();
  } catch (err) {
    Claude.enviando = false;
    claudeDesenhar(Claude.dados);
    avisar("não consegui mudar: " + err.message, true);
  }
}

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
// O pergaminho abre já desenrolado no primeiro (antes abria vazio, com
// "Escolha um pergaminho", e pedia um toque a mais para nada). Se ele já
// escolheu outro, fica o que ele escolheu.
let arenaOpcoes = null;
let arenaP1 = null;
let arenaP2 = null;

function arenaCartoes(id, escolhido, outro) {
  const lista = $(id);
  const busca = $(id.replace("-lista", "-busca")).value.trim().toLocaleLowerCase("pt-BR");
  lista.replaceChildren();
  for (const p of arenaOpcoes.personagens) {
    if (busca && !p.nome.toLocaleLowerCase("pt-BR").includes(busca)) continue;
    const cor = String(p.cor_classe || "").replace("#", "");
    const b = el("button", {class: "arena-personagem arena-cor-" + cor
      + (p.nome === escolhido ? " escolhido" : ""), type: "button"},
      el("span", {class: "arena-bolinha", "aria-hidden": "true"}),
      el("span", {class: "arena-pessoa"}, el("strong", {}, p.nome),
        el("small", {}, `${p.classe} · ${p.arma}${p.tipo_arma ? " (" + p.tipo_arma + ")" : ""}`)));
    b.disabled = p.nome === outro;
    b.addEventListener("click", () => {
      if (id === "arena-p1-lista") arenaP1 = p.nome; else arenaP2 = p.nome;
      desenharArenaEscolhas();
    });
    lista.append(b);
  }
}

function desenharArenaEscolhas() {
  if (!arenaOpcoes) return;
  arenaCartoes("arena-p1-lista", arenaP1, arenaP2);
  arenaCartoes("arena-p2-lista", arenaP2, arenaP1);
  $("arena-vs").textContent = arenaP1 && arenaP2 ? `${arenaP1}  VS  ${arenaP2}` : "VS";
  $("arena-lutar").disabled = !arenaP1 || !arenaP2;
}

function desenharLutas(lutas) {
  const lista = $("arena-lutas");
  lista.replaceChildren();
  if (!lutas.length) lista.append(el("p", {class: "fraco"}, "Nenhuma luta ainda."));
  for (const luta of lutas) {
    const cartao = el("article", {class: "arena-luta"},
      el("strong", {}, `${luta.p1} × ${luta.p2}`),
      el("span", {class: `selo ${luta.situacao === "falhou" ? "erro" : luta.situacao === "pronta" ? "ok" : "trabalhando"}`}, luta.situacao),
      el("div", {class: "fraco"}, `${luta.mapa} · semente ${luta.semente}`));
    if (luta.video_url) cartao.append(el("video", {controls: "", playsinline: "", preload: "metadata", src: luta.video_url}));
    if (luta.vencedor) cartao.append(el("div", {class: "arena-vencedor"}, `Venceu: ${luta.vencedor}`));
    const revanche = el("button", {class: "acao", type: "button"}, "Revanche");
    revanche.addEventListener("click", () => lutarArena(luta));
    cartao.append(revanche);
    lista.append(cartao);
  }
}

async function carregarArena() {
  try {
    if (!arenaOpcoes) {
      arenaOpcoes = await api("/api/arena/opcoes");
      arenaP1 = arenaOpcoes.personagens[0] && arenaOpcoes.personagens[0].nome;
      arenaP2 = arenaOpcoes.personagens[1] && arenaOpcoes.personagens[1].nome;
      for (const mapa of arenaOpcoes.mapas)
        $("arena-mapa").append(el("option", {value: mapa.id}, `${mapa.icone || "🗺️"} ${mapa.nome}`));
      desenharArenaEscolhas();
    }
    const dados = await api("/api/arena/lutas");
    desenharLutas(dados.lutas || []);
    conexao(true);
  } catch (err) { conexao(false, err); }
}

async function lutarArena(revanche = null) {
  const mapa = revanche ? revanche.mapa : $("arena-mapa").value;
  const valor = revanche ? revanche.semente : $("arena-semente").value.trim();
  const corpo = {p1: revanche ? revanche.p1 : arenaP1, p2: revanche ? revanche.p2 : arenaP2, mapa};
  if (valor) corpo.semente = Number(valor);
  const botao = $("arena-lutar");
  botao.disabled = true;
  $("arena-progresso").textContent = "Enviando para renderizar no PC…";
  try {
    const feita = await api("/api/arena/luta", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(corpo)});
    $("arena-semente").value = feita.semente;
    $("arena-progresso").textContent = "Renderizando no PC… a luta vai aparecer abaixo.";
    await carregarArena();
  } catch (err) {
    $("arena-progresso").textContent = err.message;
  } finally { botao.disabled = !arenaP1 || !arenaP2; }
}

$("arena-p1-busca").addEventListener("input", desenharArenaEscolhas);
$("arena-p2-busca").addEventListener("input", desenharArenaEscolhas);
$("arena-dado").addEventListener("click", () => {
  $("arena-semente").value = String(Math.floor(Math.random() * 2147483647));
});
$("arena-lutar").addEventListener("click", () => lutarArena());

function abrirPergaminho() {
  const abas = $("abas-relatorio").children;
  if (abas.length && ![...abas].some((b) => b.getAttribute("aria-pressed") === "true"))
    abas[0].click();
}

const CARGAS = {vila: [carregarAgora, 15000], agora: [carregarAgora, 15000],
                diario: [carregarDiario, 5000],
                videos: [null, 0], comandos: [null, 0],
                relatorios: [abrirPergaminho, 0],
                decisoes: [null, 0], sprites: [null, 0], assembleias: [null, 0], conversa: [null, 0],
                oficina: [null, 0], biblioteca: [null, 0], atelie: [null, 0], coordenador: [null, 0],
                arena: [carregarArena, 3000]};

// As abas de um objeto (Agora, Mandar e Ver têm mais de uma tela): a mesma
// fileira no topo de cada tela dele, montada daqui (uma lista só, OBJETOS).
// Trocar de aba não empilha histórico: o voltar do Android fecha o objeto.
function montarAbasDosObjetos() {
  for (const [objeto, abas] of Object.entries(OBJETOS)) {
    if (abas.length < 2) continue;
    for (const [nome] of abas) {
      const secao = $("tela-" + nome);
      if (!secao) continue;
      const fileira = el("div", {class: "abas-objeto", role: "tablist",
                                 "aria-label": `Abas de ${objeto}`});
      for (const [alvo, emoji, rotulo] of abas) {
        const b = el("button", {class: "aba-objeto", type: "button", role: "tab",
                                "data-aba-tela": alvo, "aria-selected": String(alvo === nome)},
          el("span", {class: "aba-emoji", "aria-hidden": "true"}, emoji),
          el("span", {class: "aba-rotulo"}, rotulo));
        b.addEventListener("click", () => { if (tela !== alvo) abrir(alvo, b); });
        fileira.append(b);
      }
      secao.prepend(fileira);
    }
  }
}

function mostrar(nova) {
  if (nova && nova !== tela && nova === "diario") {
    diarioDesde = "";                     // filtro novo, lista do zero
    $("diario").replaceChildren();
  }
  if (nova) tela = nova;
  const pareado = !!localStorage.getItem(TOKEN);
  const atual = pareado ? tela : "parear";
  // A Vila fica sempre atrás (parada, quando outro objeto está aberto): o
  // objeto abre POR CIMA dela, e fechar é voltar para a praça.
  for (const s of document.querySelectorAll("main > section"))
    s.classList.toggle("oculto", s.id !== "tela-" + atual
      && !(pareado && s.id === "tela-vila"));
  document.body.classList.toggle("pareado", pareado);
  document.body.classList.toggle("objeto-aberto", pareado && tela !== "vila");
  $("nav").classList.toggle("oculto", !pareado || tela !== "vila");
  $("btn-voltar").classList.toggle("oculto", !pareado || tela === "vila");
  $("titulo").textContent = pareado ? TITULOS[tela] : "Parear";
  const objeto = objetoDe(tela);
  if (objeto) ABA_DO_OBJETO[objeto] = tela;
  for (const b of document.querySelectorAll("nav.prateleira [data-objeto]")) {
    if (b.dataset.objeto === objeto) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
  for (const b of document.querySelectorAll(".aba-objeto"))
    b.setAttribute("aria-selected", String(b.dataset.abaTela === tela));
  clearInterval(timer);
  // casca nova esperando: voltar para a Vila é o momento seguro de recarregar
  if (Casca.nova && CASCA_MINHA && pareado && cascaSegura()
      && sessionStorage.getItem("painel.recarreguei") !== Casca.nova) {
    sessionStorage.setItem("painel.recarreguei", Casca.nova);
    location.reload();
    return;
  }
  if (typeof vilaParar === "function") vilaParar();
  if (typeof comandosParar === "function") comandosParar();
  if (typeof decisoesParar === "function") decisoesParar();
  if (typeof orquestradorParar === "function") orquestradorParar();
  if (typeof coordenadorParar === "function") coordenadorParar();
  if (typeof conversaParar === "function") conversaParar();
  if (typeof oficinaParar === "function") oficinaParar();
  if (typeof bibliotecaParar === "function") bibliotecaParar();
  if (typeof atelieParar === "function") atelieParar();
  if (!pareado) return;
  // Agora mostra a gente e as travas, que vêm da vida da vila
  if ((tela === "vila" || tela === "agora") && typeof vilaMostrar === "function") {
    vilaMostrar();
  }
  if (tela === "comandos" && typeof comandosMostrar === "function") {
    comandosMostrar();
  }
  if (tela === "decisoes" && typeof decisoesMostrar === "function") {
    decisoesMostrar();
  }
  if (tela === "sprites" && typeof spritesMostrar === "function") spritesMostrar();
  if (tela === "assembleias" && typeof assembleiasMostrar === "function") {
    assembleiasMostrar();
  }
  // o orquestrador alimenta Agora (tudo, com o fluxo), Mandar ("o que você
  // mandou") e Decidir (o que ele decidiu sozinho, uma leitura ao abrir)
  if (tela === "agora" && typeof orquestradorMostrar === "function") {
    orquestradorMostrar();
  }
  if (tela === "comandos" && typeof orquestradorMostrar === "function") {
    orquestradorMostrar(false);
  }
  if (tela === "decisoes" && typeof orqCarregar === "function") {
    orqCarregar();
  }
  if (tela === "conversa" && typeof conversaMostrar === "function") {
    conversaMostrar();
  }
  if (tela === "oficina" && typeof oficinaMostrar === "function") {
    oficinaMostrar();
  }
  if (tela === "biblioteca" && typeof bibliotecaMostrar === "function") {
    bibliotecaMostrar();
  }
  if (tela === "atelie" && typeof atelieMostrar === "function") atelieMostrar();
  if (tela === "coordenador" && typeof coordenadorMostrar === "function") {
    coordenadorMostrar();
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

// Abrir um objeto da vila. A animação sai de onde o objeto está (--ox,
// --oy), e o "voltar" do Android fecha o objeto em vez de sair do app.
// Entre abas do MESMO objeto não há animação de abrir de novo (a cortina do
// Cinema, a capa do Diário) e o histórico é trocado, não empilhado.
function abrir(nova, origem) {
  const secao = $("tela-" + nova);
  if (!secao) return;
  const mesmoObjeto = tela !== nova && objetoDe(nova) && objetoDe(nova) === objetoDe(tela);
  secao.classList.toggle("sem-abrir", !!mesmoObjeto);
  if (origem && !mesmoObjeto) {
    const r = origem.getBoundingClientRect();
    secao.style.setProperty("--ox", `${Math.round(r.left + r.width / 2)}px`);
    secao.style.setProperty("--oy", `${Math.round(r.top + r.height / 2)}px`);
  }
  secao.scrollTop = 0;
  if (mesmoObjeto) history.replaceState({tela: nova}, "");
  else if (tela !== nova) history.pushState({tela: nova}, "");
  mostrar(nova);
}

// Um objeto da prateleira abre a última aba que ele usou (da primeira vez,
// a do `data-tela`).
function abrirObjeto(botao) {
  abrir(ABA_DO_OBJETO[botao.dataset.objeto] || botao.dataset.tela, botao);
}

function voltarParaVila() {
  if (history.state && history.state.tela) history.back();
  else mostrar("vila");
}

for (const b of document.querySelectorAll("nav.prateleira [data-objeto]"))
  b.addEventListener("click", () => abrirObjeto(b));
$("btn-voltar").addEventListener("click", voltarParaVila);
// o coordenador em uma linha, em Agora: tocar abre a aba dele
$("coord-mesa").addEventListener("click", (e) => abrir("coordenador", e.currentTarget));
window.addEventListener("popstate", (e) => {
  mostrar((e.state && e.state.tela) || "vila");
});
$("btn-tentar").addEventListener("click", () => mostrar());
$("btn-recarregar").addEventListener("click", () => {
  if (Casca.nova) sessionStorage.setItem("painel.recarreguei", Casca.nova);
  location.reload();
});
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
montarAbasDosObjetos();
mostrar();

// Service worker so existe em contexto seguro (HTTPS do `tailscale serve`).
if ("serviceWorker" in navigator && window.isSecureContext)
  navigator.serviceWorker.register("sw.js").catch(() => {});

// Um pedaço do app que não chegou (30/09, tarefa 74856214). No log do PC,
// a carga de 12:01:17 de 30/09 não recebeu o conversa.js (a de 14:54:07 de
// 29/09 perdeu ele e o vila.js): sem ele, o cartão do prédio mostrava só
// "Ver no diário", sem "Conversar" nem "Criar", e nada dizia por quê. Ele
// ficou 1h13 sem conseguir falar com as IAs; a carga de 13:15:09 recebeu o
// arquivo e a conversa abriu 5 s depois. Agora: uma recarga sozinho (uma
// vez só, o sessionStorage segura o laço); se ainda faltar, a faixa diz o
// nome do arquivo e pede o toque. O `load` vem depois de todos os scripts,
// inclusive os que falharam.
const MODULOS = [["vila.js", "vilaMostrar"], ["comandos.js", "comandosMostrar"],
                 ["decisoes.js", "decisoesMostrar"],
                 ["assembleia.js", "assembleiasMostrar"],
                 ["orquestrador.js", "orquestradorMostrar"], ["coordenador.js", "coordenadorMostrar"],
                 ["conversa.js", "conversaAbrir"],
                 ["oficina.js", "oficinaMostrar"], ["biblioteca.js", "bibliotecaMostrar"],
                 ["atelie.js", "atelieMostrar"]];

function modulosQueFaltam() {
  return MODULOS.filter(([, funcao]) => typeof window[funcao] !== "function")
    .map(([arquivo]) => arquivo);
}

window.addEventListener("load", () => {
  const faltam = modulosQueFaltam();
  document.documentElement.dataset.modulos = faltam.length ? faltam.join(",") : "ok";
  if (!faltam.length) {
    sessionStorage.removeItem("painel.modulos");
    return;
  }
  if (!sessionStorage.getItem("painel.modulos")) {
    sessionStorage.setItem("painel.modulos", faltam.join(","));
    location.reload();
    return;
  }
  $("modulo-faltando-texto").textContent = `Parte do app não chegou do PC (${faltam.join(", ")})`
    + (faltam.includes("conversa.js") ? ": sem ela não dá para conversar nem pedir imagem." : ".");
  $("modulo-faltando").classList.remove("oculto");
});
$("btn-recarregar-modulos").addEventListener("click", () => location.reload());
