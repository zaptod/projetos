"use strict";
// A Oficina do Codex (01/10/2026, tarefa 52dc403c): o trabalho que o
// orquestrador delega ao Codex (remoto/delegar.py), AO VIVO.
//
// Pedido do Adrian: "quero algo no app para poder ver o trabalho do Codex em
// tempo real". Só leitura nesta versão: aplicar continua com o orquestrador.
// Desde 02/10/2026 é a aba "Codex" do objeto Agora (antes só abria pela Mesa).
// A lista relê a cada 10 s; a tarefa aberta pede só os eventos NOVOS (por
// offset no eventos.jsonl) a cada 3 s enquanto ela roda, sem travar o PC.

const OFI_LISTA_MS = 10000;
const OFI_VIVO_MS = 3000;
const OFI_PARADA_MS = 15000;
const OFI_MAX_EVENTOS = 600;          // a tela guarda os últimos N
const OFI_SITUACAO = {
  criado: ["·", "criada", "fraco"], rodando: ["▶", "rodando", "trabalhando"],
  terminou: ["✓", "terminou", "ok"], falhou: ["✕", "falhou", "erro"],
  parado: ["■", "parada", "erro"], sumiu: ["⚠", "o processo sumiu", "erro"],
  ilegivel: ["⚠", "ilegível", "erro"],
};
const OFI_TIPO = {
  le: ["📖", "lê"], roda: ["▶", "roda"], testa: ["🧪", "testa"], muda: ["✎", "muda"],
  mensagem: ["💬", "diz"], pensa: ["🧠", "pensa"], plano: ["☑", "plano"],
  sessao: ["⚙", ""], despachante: ["🛠", ""], erro: ["✕", "erro"], outro: ["·", ""],
};

const Ofi = {lista: null, aberta: null, offset: -1, eventos: [], relogio: null,
             vivo: null, aba: "vivo", seguir: true, situacao: null, carregando: false};

function ofiSelo(situacao) {
  const [sim, texto, classe] = OFI_SITUACAO[situacao] || ["·", situacao || "?", "fraco"];
  return el("span", {class: "selo " + classe}, `${sim} ${texto}`);
}

function ofiTokens(t) {
  if (!t || !(t.entrada || t.saida)) return "";
  const k = (n) => n >= 1000 ? `${(n / 1000).toFixed(n >= 100000 ? 0 : 1)}k` : String(n);
  return `${k(t.entrada || 0)} entrada (${k(t.cache || 0)} cache) · ${k(t.saida || 0)} saída`;
}

function ofiDiffCurto(d) {
  if (!d) return null;
  if (d.ok) return el("span", {class: "ok"}, `diff ${d.arquivos} arquivo(s), ${d.linhas} linhas · passa`);
  return el("span", {class: "erro"}, "diff recusado: " + (d.motivos || []).join("; "));
}

function ofiTestesCurto(t) {
  if (!t) return null;
  return el("span", {class: t.ok ? "ok" : "erro"},
    `testes ${t.ok ? "ok" : "falharam"} (${t.dur_s} s)` + (t.resumo ? ` · ${t.resumo}` : ""));
}

// ------------------------------------------------------------------ uso
function ofiDesenharUso(d) {
  const u = d.uso || {};
  const teto = (d.config || {}).teto_codex_pct;
  const alvo = $("oficina-uso");
  if (u.pct == null) {
    alvo.replaceChildren(el("div", {class: "fraco"},
      "Uso do Codex: sem medição (nenhuma sessão recente). Sem medição, o despachante não começa nada."));
    return;
  }
  const linhas = [orqBarra("Codex · janela de 5 h", u.pct, u.renova_em, teto)];
  if (u.semana_pct != null)
    linhas.push(el("div", {class: "fraco"}, `semana: ${Math.round(u.semana_pct)}% · `
      + `renova ${orqHoraEpoch(u.semana_renova_em)}`));
  linhas.push(el("div", {class: "fraco"},
    (u.situacao === "renovou" ? "a janela renovou depois da última medição · " : "")
    + (u.medido_em ? `medido ${quandoCurto(u.medido_em)} (${orqDesde(u.medido_em)})` : "")
    + (u.plano ? ` · plano ${u.plano}` : "")
    + ` · passou de ${teto}%, nada começa e quem roda para`));
  alvo.replaceChildren(...linhas);
}

// ---------------------------------------------------------------- lista
function ofiCartao(t) {
  const linhas = [
    el("div", {class: "ofi-topo"}, el("strong", {}, t.titulo || t.id), ofiSelo(t.situacao)),
    el("div", {class: "fraco"}, `#${t.id} · ${t.modelo || "modelo padrão"}`
      + (t.rodadas > 1 ? ` · ${t.rodadas} rodadas` : "")
      + (t.inicio ? ` · ${t.situacao === "rodando" ? "desde" : "começou"} ${quandoCurto(t.inicio)}` : "")
      + (t.fim ? ` · fim ${quandoCurto(t.fim)}` : "")),
  ];
  const tok = ofiTokens(t.tokens);
  if (tok) linhas.push(el("div", {class: "fraco"}, tok));
  if (t.motivo) linhas.push(el("div", {class: "erro"}, t.motivo));
  const extra = [ofiDiffCurto(t.diff), ofiTestesCurto(t.testes)].filter(Boolean);
  if (extra.length) linhas.push(el("div", {class: "ofi-extra"}, ...extra));
  if (t.aplicado) linhas.push(el("div", {class: "ok"}, `aplicado ${quandoCurto(t.aplicado.em)}`));
  if (t.limpo) linhas.push(el("div", {class: "fraco"}, "worktree já limpa"));
  const b = el("button", {class: "ofi-cartao " + (t.situacao || ""), "data-id": t.id}, ...linhas);
  b.addEventListener("click", () => ofiAbrir(t.id));
  return b;
}

function ofiDesenharLista(d) {
  const alvo = $("oficina-lista");
  const lista = d.delegados || [];
  if (!lista.length) {
    alvo.replaceChildren(el("div", {class: "fraco"},
      "Nenhuma tarefa delegada ainda. Quando o orquestrador mandar uma ao Codex, "
      + "ela aparece aqui e você acompanha ao vivo."));
    return;
  }
  alvo.replaceChildren(...lista.map(ofiCartao));
}

async function ofiCarregarLista() {
  try {
    const d = await api("/api/delegados");
    Ofi.lista = d;
    ofiDesenharUso(d);
    ofiDesenharLista(d);
    $("oficina-erros").textContent = (d.erros || []).join(" · ");
    conexao(true);
  } catch (err) { conexao(false, err); }
}

// ------------------------------------------------------------- detalhe
function ofiEvento(e) {
  const [icone, verbo] = OFI_TIPO[e.tipo] || OFI_TIPO.outro;
  const classe = "ofi-ev " + (e.tipo || "outro") + (e.ok === false ? " falhou" : "");
  const corpo = el("div", {class: "ofi-ev-corpo"},
    el("div", {class: "ofi-ev-texto"}, e.texto || ""));
  if (e.detalhe)
    corpo.append(el("details", {}, el("summary", {}, "saída"),
      el("pre", {class: "ofi-pre"}, e.detalhe)));
  return el("div", {class: classe},
    el("span", {class: "ofi-ev-icone", title: verbo}, icone),
    el("span", {class: "orq-hora"}, e.em ? hora(e.em) : ""), corpo);
}

function ofiDesenharCabeca(t) {
  $("oficina-cabeca").replaceChildren(...[
    el("div", {class: "ofi-topo"}, el("strong", {}, t.titulo || t.id), ofiSelo(t.situacao)),
    el("div", {class: "fraco"}, `#${t.id} · ${t.modelo || "modelo padrão"}`
      + (t.esforco ? ` · esforço ${t.esforco}` : "")
      + (t.inicio ? ` · começou ${quandoCurto(t.inicio)}` : "")
      + (t.situacao === "rodando" && t.ultimo_evento_em
        ? ` · último sinal ${orqDesde(t.ultimo_evento_em)}` : "")),
    ofiTokens(t.tokens) ? el("div", {class: "fraco"}, ofiTokens(t.tokens)) : null,
    t.motivo ? el("div", {class: "erro"}, t.motivo) : null,
    el("div", {class: "fraco"}, "pode mexer em: " + (t.permitidos || []).join(", "))]
    .filter((x) => x != null));   // replaceChildren(null) escreveria "null"
}

function ofiDesenharEventos(novos) {
  const alvo = $("oficina-eventos");
  const perto = alvo.scrollHeight - alvo.scrollTop - alvo.clientHeight < 80;
  if (novos === null || alvo.querySelector(".ofi-vazio")) alvo.replaceChildren();
  for (const e of novos || Ofi.eventos) alvo.append(ofiEvento(e));
  while (alvo.children.length > OFI_MAX_EVENTOS) alvo.firstChild.remove();
  if (!alvo.children.length)
    alvo.replaceChildren(el("div", {class: "fraco ofi-vazio"}, "Nenhum evento ainda."));
  if (Ofi.seguir && (perto || novos === null)) alvo.scrollTop = alvo.scrollHeight;
}

function ofiLinhaDoDiff(linha) {
  const c = linha[0];
  const classe = linha.startsWith("+++") || linha.startsWith("---") || linha.startsWith("diff ")
    ? "cab" : c === "+" ? "mais" : c === "-" ? "menos" : linha.startsWith("@@") ? "bloco" : "";
  return el("div", {class: "ofi-diff-linha " + classe}, linha || " ");
}

function ofiDesenharPesado(d) {
  const t = d.tarefa;
  // diff
  const diff = $("oficina-diff");
  const filhos = [];
  if (t.diff) filhos.push(el("div", {class: t.diff.ok ? "ok" : "erro"},
    t.diff.ok ? `passa no validador · ${t.diff.arquivos} arquivo(s), ${t.diff.linhas} linhas`
      : "RECUSADO: " + (t.diff.motivos || []).join("; ")));
  if (d.diff_arquivos && d.diff_arquivos.length)
    filhos.push(el("div", {class: "fraco"}, d.diff_arquivos.map((a) =>
      `${a.binario ? "BIN" : `+${a.mais} −${a.menos}`} ${a.caminho}`).join(" · ")));
  if (d.diff_texto) {
    const caixa = el("div", {class: "ofi-diff"});
    for (const linha of d.diff_texto.split("\n").slice(0, 4000)) caixa.append(ofiLinhaDoDiff(linha));
    filhos.push(caixa);
  } else filhos.push(el("div", {class: "fraco"},
    t.situacao === "rodando" ? "O diff sai quando o Codex terminar; até lá, veja “muda” ao vivo."
      : "Sem diff ainda."));
  diff.replaceChildren(...filhos);
  // testes
  const testes = $("oficina-testes");
  if (t.testes) {
    testes.replaceChildren(...[
      el("div", {class: t.testes.ok ? "ok" : "erro"}, `${t.testes.ok ? "✓ passaram" : "✕ falharam"}`
        + ` · código ${t.testes.codigo} · ${t.testes.dur_s} s · ${quandoCurto(t.testes.em)}`),
      el("div", {class: "fraco"}, "$ " + t.testes.cmd),
      t.diff && t.testes.diff_sha !== t.diff.sha
        ? el("div", {class: "erro"}, "o diff mudou depois destes testes") : null,
      d.testes_cauda ? el("pre", {class: "ofi-pre"}, d.testes_cauda) : null]
      .filter((x) => x != null));
  } else testes.replaceChildren(el("div", {class: "fraco"},
    "O orquestrador ainda não rodou os testes desta tarefa."));
  // pedido e resposta
  $("oficina-pedido").textContent = d.pedido || "(sem o pedido)";
  $("oficina-resposta").textContent = d.resposta || (t.situacao === "rodando"
    ? "Ainda trabalhando…" : "(sem resposta final)");
}

function ofiMostrarAba(aba) {
  Ofi.aba = aba;
  for (const b of document.querySelectorAll("#oficina-abas button"))
    b.setAttribute("aria-pressed", String(b.dataset.aba === aba));
  for (const [nome, id] of [["vivo", "oficina-eventos"], ["diff", "oficina-diff"],
    ["testes", "oficina-testes"], ["pedido", "oficina-pedido"], ["resposta", "oficina-resposta"]])
    $(id).classList.toggle("oculto", nome !== aba);
  $("oficina-seguir").classList.toggle("oculto", aba !== "vivo");
}

async function ofiCarregarDetalhe(primeira = false) {
  if (!Ofi.aberta || Ofi.carregando) return;
  Ofi.carregando = true;
  const id = Ofi.aberta;
  const estavaRodando = Ofi.situacao === "rodando";
  try {
    // terminou agora (ou é a primeira carga): pede também o pesado
    let url = `/api/delegado/${encodeURIComponent(id)}?desde=${primeira ? -1 : Ofi.offset}`;
    const d = await api(url);
    if (Ofi.aberta !== id) return;
    const mudou = !primeira && estavaRodando && d.tarefa.situacao !== "rodando";
    Ofi.offset = d.offset;
    Ofi.situacao = d.tarefa.situacao;
    ofiDesenharCabeca(d.tarefa);
    if (primeira) {
      Ofi.eventos = d.eventos || [];
      ofiDesenharEventos(null);
      ofiDesenharPesado(d);
    } else if ((d.eventos || []).length) {
      Ofi.eventos.push(...d.eventos);
      if (Ofi.eventos.length > OFI_MAX_EVENTOS) Ofi.eventos.splice(0, Ofi.eventos.length - OFI_MAX_EVENTOS);
      ofiDesenharEventos(d.eventos);
    }
    if (mudou) {
      url = `/api/delegado/${encodeURIComponent(id)}?desde=${Ofi.offset}&completo=1`;
      const cheio = await api(url);
      if (Ofi.aberta === id) ofiDesenharPesado(cheio);
    }
    // pedaço grande ainda por vir: busca já, sem esperar o relógio
    if (d.mais) setTimeout(() => ofiCarregarDetalhe(), 50);
    ofiRelogioDoDetalhe();
    conexao(true);
  } catch (err) {
    if (err.status === 404) { avisar("essa tarefa não existe mais", true); ofiFechar(); }
    else conexao(false, err);
  } finally { Ofi.carregando = false; }
}

// rodando: de 3 em 3 s; parada: de 15 em 15 s (pode voltar a rodar numa correção)
function ofiRelogioDoDetalhe() {
  const passo = Ofi.situacao === "rodando" ? OFI_VIVO_MS : OFI_PARADA_MS;
  if (Ofi.vivo && Ofi.vivo.passo === passo) return;
  clearInterval(Ofi.vivo && Ofi.vivo.id);
  Ofi.vivo = {passo, id: setInterval(() => {
    if (document.visibilityState === "visible") ofiCarregarDetalhe();
  }, passo)};
}

function ofiAbrir(id) {
  Ofi.aberta = id; Ofi.offset = -1; Ofi.eventos = []; Ofi.situacao = null;
  $("oficina-lista-cartao").classList.add("oculto");
  $("oficina-tarefa").classList.remove("oculto");
  $("oficina-cabeca").replaceChildren(el("div", {class: "fraco"}, "carregando…"));
  $("oficina-eventos").replaceChildren();
  ofiMostrarAba("vivo");
  ofiCarregarDetalhe(true);
}

function ofiFechar() {
  Ofi.aberta = null;
  clearInterval(Ofi.vivo && Ofi.vivo.id); Ofi.vivo = null;
  $("oficina-tarefa").classList.add("oculto");
  $("oficina-lista-cartao").classList.remove("oculto");
  ofiCarregarLista();
}

function oficinaMostrar() {
  ofiCarregarLista();
  if (Ofi.aberta) ofiCarregarDetalhe(true);
  clearInterval(Ofi.relogio);
  Ofi.relogio = setInterval(() => {
    if (document.visibilityState === "visible" && !Ofi.aberta) ofiCarregarLista();
  }, OFI_LISTA_MS);
}

function oficinaParar() {
  clearInterval(Ofi.relogio); Ofi.relogio = null;
  clearInterval(Ofi.vivo && Ofi.vivo.id); Ofi.vivo = null;
}

for (const b of document.querySelectorAll("#oficina-abas button"))
  b.addEventListener("click", () => ofiMostrarAba(b.dataset.aba));
$("oficina-voltar-lista").addEventListener("click", ofiFechar);
// o antigo "‹ Mesa" virou a aba "Agora" (a Oficina é a aba Codex de Agora)
$("oficina-seguir").addEventListener("click", () => {
  Ofi.seguir = !Ofi.seguir;
  $("oficina-seguir").setAttribute("aria-pressed", String(Ofi.seguir));
  $("oficina-seguir").textContent = Ofi.seguir ? "⇣ seguindo o fim" : "⇣ seguir o fim";
  if (Ofi.seguir) { const a = $("oficina-eventos"); a.scrollTop = a.scrollHeight; }
});
