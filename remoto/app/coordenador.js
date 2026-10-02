"use strict";
// O supervisor so publica estado; cada toque abaixo vira um pedido pendente.

const COORD_MS = 5000;
const Coord = {dados: null, relogio: null, pedidos: new Map()};

const COORD_SELO = {rodando: ["rodando", "ok"], parado: ["parado", "ocioso"],
                    caiu: ["caiu", "erro"], reiniciando: ["reiniciando", "trabalhando"],
                    desligado: ["desligado", "ocioso"], falhou: ["falhou", "erro"]};

function coordPedido(cmd, valor) {
  return Coord.pedidos.get(`${cmd}|${valor}`);
}

function coordEventoConfirma(eventos, cmd, valor, desde) {
  const tipos = {servico_reiniciar: ["reiniciou"], servico_parar: ["aviso", "comando"],
                 servico_ligar: ["religou", "comando"], pc_acao: ["acao"]};
  return (eventos || []).some((e) => {
    const em = dataPC(e.em).getTime();
    return (!desde || isNaN(em) || em >= desde - 1000)
      && tipos[cmd].includes(e.tipo) && (cmd === "pc_acao" || e.servico === valor);
  });
}

function coordLimparPedidos(eventos) {
  for (const [chave, pedido] of Coord.pedidos) {
    const [cmd, valor] = chave.split("|");
    if (coordEventoConfirma(eventos, cmd, valor, pedido.em)) Coord.pedidos.delete(chave);
  }
}

function coordSelo(situacao) {
  const dado = COORD_SELO[situacao] || [situacao || "desconhecido", "ocioso"];
  return el("span", {class: `selo ${dado[1]}`}, dado[0]);
}

function coordServico(nome, servico, eventos) {
  const card = el("div", {class: "coord-servico"});
  const cabeca = el("div", {class: "coord-linha"}, el("strong", {}, nome), coordSelo(servico.situacao));
  card.append(cabeca);
  const saude = servico.saude || "desconhecida";
  card.append(el("div", {class: "fraco"}, `Saúde: ${saude} · ${servico.reinicios_24h || 0} reinício(s) em 24 h`));
  if (servico.codigo_velho) {
    const quando = servico.proximo_reinicio ? `, reinicia em ${quandoCurto(servico.proximo_reinicio)}` : "";
    card.append(el("div", {class: "coord-aviso"}, `Código velho${quando}${servico.motivo_espera ? ` (${servico.motivo_espera})` : ""}`));
  }
  if (servico.ultimo_erro) card.append(el("div", {class: "coord-erro"}, servico.ultimo_erro));
  const botoes = el("div", {class: "botoes"});
  const opcoes = [];
  if (servico.situacao !== "desligado") opcoes.push(["servico_reiniciar", "Reiniciar"]);
  if (["rodando", "reiniciando"].includes(servico.situacao)) opcoes.push(["servico_parar", "Parar"]);
  if (["parado", "caiu", "desligado", "falhou"].includes(servico.situacao)) opcoes.push(["servico_ligar", "Ligar"]);
  for (const [cmd, rotulo] of opcoes) {
    const pendente = coordPedido(cmd, nome);
    const botao = el("button", {class: "acao", type: "button"}, rotulo);
    botao.disabled = !!pendente;
    botao.addEventListener("click", () => coordEnviar(cmd, nome));
    botoes.append(botao);
    if (pendente) botoes.append(el("span", {class: "fraco"}, "pedido · pendente"));
  }
  if (opcoes.length) card.append(botoes);
  return card;
}

function coordDesenhar(dados) {
  Coord.dados = dados;
  const topo = $("coord-topo");
  if (!dados.vivo) {
    topo.replaceChildren(el("h2", {}, "Coordenador"),
      el("div", {class: "grande coord-fora"}, "FORA DO AR"),
      el("div", {class: "fraco"}, dados.motivo || "sem pulso recente"));
    $("coord-servicos").replaceChildren(); $("coord-acoes").replaceChildren(); $("coord-eventos").replaceChildren();
    coordTrabalho(null);
    return;
  }
  coordTrabalho(dados.trabalho);
  topo.replaceChildren(el("h2", {}, "Coordenador"),
    el("div", {class: "grande coord-vivo"}, "NO AR"),
    el("div", {class: "fraco"}, `desde ${quandoCurto(dados.desde) || "—"} · versão ${dados.versao || "—"}`));
  const eventos = Array.isArray(dados.eventos) ? dados.eventos : [];
  coordLimparPedidos(eventos);
  const servicos = dados.servicos && typeof dados.servicos === "object" ? dados.servicos : {};
  $("coord-servicos").replaceChildren(...Object.entries(servicos).map(([nome, s]) =>
    coordServico(nome, s && typeof s === "object" ? s : {}, eventos)));
  const acoes = Array.isArray(dados.acoes_pc) ? dados.acoes_pc : [];
  $("coord-acoes").replaceChildren(...acoes.filter((a) => a && a.id).map((acao) => {
    const pendente = coordPedido("pc_acao", acao.id);
    const botao = el("button", {class: `acao${acao.perigo ? " perigo" : ""}`, type: "button"}, acao.rotulo || acao.id);
    botao.disabled = !!pendente;
    botao.addEventListener("click", () => acao.perigo ? coordPedirConfirmacao(acao) : coordEnviar("pc_acao", acao.id));
    return botao;
  }));
  $("coord-eventos").replaceChildren(...eventos.slice().sort((a, b) =>
    dataPC(b.em).getTime() - dataPC(a.em).getTime()).map((evento) =>
    el("div", {class: "linha"}, el("span", {class: "coord-evento-hora"}, quandoCurto(evento.em)),
      el("div", {class: "corpo"}, evento.texto || evento.tipo || "evento"))));
}

function coordPedirConfirmacao(acao) {
  const caixa = $("coord-confirmar");
  caixa.replaceChildren(el("span", {}, `Confirmar: ${acao.rotulo || acao.id}?`), (() => {
    const sim = el("button", {class: "acao perigo", type: "button"}, "Confirmar");
    sim.addEventListener("click", () => { caixa.classList.add("oculto"); coordEnviar("pc_acao", acao.id, true); });
    return sim;
  })(), (() => {
    const nao = el("button", {class: "acao", type: "button"}, "Cancelar");
    nao.addEventListener("click", () => caixa.classList.add("oculto"));
    return nao;
  })());
  caixa.classList.remove("oculto");
}

async function coordEnviar(cmd, valor, confirmar = false) {
  const chave = `${cmd}|${valor}`;
  if (Coord.pedidos.has(chave)) return;
  Coord.pedidos.set(chave, {em: agoraPC()});
  coordDesenhar(Coord.dados || {});
  try {
    await api("/api/coordenador/comando", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({cmd, valor, ...(confirmar ? {confirmar: true} : {})})});
  } catch (err) { Coord.pedidos.delete(chave); avisar(err.message, true); }
  coordCarregar();
}

function coordResumo(dados) {
  if (!dados.vivo) return "Coordenador: FORA DO AR";
  const servicos = Object.values(dados.servicos || {});
  const ok = servicos.filter((s) => s && s.saude === "ok").length;
  return `Coordenador: no ar · ${ok}/${servicos.length} serviços ok`;
}

async function coordenadorMesa() {
  try { $("coord-mesa").textContent = coordResumo(await api("/api/coordenador")); } catch (err) {
    $("coord-mesa").textContent = "Coordenador: FORA DO AR";
  }
}

async function coordCarregar() {
  try { coordDesenhar(await api("/api/coordenador")); conexao(true); } catch (err) { conexao(false, err); }
}

// ------------------------------------------------ o vigia de trabalho (02/10)
function coordLinha(texto, classe = "") {
  return el("div", {class: `coord-trabalho-linha ${classe}`.trim()}, texto);
}

function coordTrabalho(t) {
  const caixa = $("coord-trabalho");
  if (!t || !t.em) {
    caixa.replaceChildren(coordLinha("O vigia de trabalho ainda não passou.", "fraco"));
    return;
  }
  const linhas = [coordLinha(`visto ${quandoCurto(t.em) || "—"}`
    + (t.resumo_em ? ` · último resumo ${quandoCurto(t.resumo_em)}` : ""), "fraco")];
  if (t.proibido) linhas.push(coordLinha(`${t.proibido}: só observo`, "coord-aviso"));
  for (const o of t.olho || []) linhas.push(coordLinha(`⚠ ${o.id}: ${o.motivo}`, "coord-erro"));
  for (const [id, motivo] of Object.entries(t.esperando || {})) linhas.push(coordLinha(`⏳ ${id}: ${motivo}`, "coord-aviso"));
  for (const id of t.corrigindo || []) linhas.push(coordLinha(`🔧 ${id}: o Codex está corrigindo`));
  for (const a of (t.aplicados || []).slice().reverse()) linhas.push(coordLinha(`✓ ${a.id} → ${a.commit}`));
  for (const r of t.rodando || []) linhas.push(coordLinha(`▶ Codex: ${r.titulo || r.id}`));
  for (const m of t.mesa || []) {
    const parada = typeof m.sem_relato_min === "number" && m.sem_relato_min >= 45;
    linhas.push(coordLinha(`🗺 ${m.titulo || m.id}` + (typeof m.sem_relato_min === "number"
      ? ` · ${m.sem_relato_min} min sem relato` : ""), parada ? "coord-aviso" : ""));
  }
  const espera = t.espera_adrian || {};
  linhas.push(coordLinha(`Espera você: ${espera.decisoes ?? "?"} decisão(ões) no Grimório, `
    + `${espera.propostas ?? "?"} proposta(s)`));
  if (t.fila) linhas.push(coordLinha(`Fila: ${t.fila.n} item(ns)`
    + ((t.fila.primeiros || [])[0] ? ` · ${t.fila.primeiros[0]}` : ""), "fraco"));
  if ((t.antigos || []).length) linhas.push(coordLinha(`${t.antigos.length} entrega(s) antiga(s) sem aplicar (de antes do vigia)`, "fraco"));
  caixa.replaceChildren(...linhas);
}

// ------------------------------------------------ a Conversa com o cerebro (02/10)
const CoordConv = {aba: "painel", enviando: false, armado: null};

function coordAba(aba) {
  CoordConv.aba = aba;
  for (const b of document.querySelectorAll("#coord-abas [data-aba]")) {
    b.setAttribute("aria-pressed", String(b.dataset.aba === aba));
  }
  $("coord-painel").classList.toggle("oculto", aba !== "painel");
  $("coord-conversa").classList.toggle("oculto", aba !== "conversa");
  if (aba === "conversa") coordConversaCarregar();
}

function coordMensagem(m) {
  const de = m.de === "adrian" ? "adrian" : "coordenador";
  const quem = de === "adrian" ? "você" : "🛰 coordenador";
  const pelo = m.origem === "telegram" ? " · pelo Telegram" : "";
  return el("div", {class: `coord-msg ${de}`}, m.texto || "",
    el("span", {class: "fraco"}, `${quem} · ${quandoCurto(m.em) || ""}${pelo}`));
}

function coordProposta(p) {
  const card = el("div", {class: "coord-proposta"});
  card.append(el("div", {}, el("strong", {}, p.texto || p.id)));
  if (p.porque) card.append(el("div", {class: "fraco"}, `por quê: ${p.porque}`));
  const valor = (p.acao && p.acao.valor) || {};
  if (p.acao && p.acao.tipo === "delegar_codex" && Array.isArray(valor.permitidos)) {
    card.append(el("div", {class: "coord-aviso"}, `Caminhos que o Codex pode mexer: ${valor.permitidos.join(", ")}`));
  }
  if (p.situacao !== "pendente") {
    card.append(el("div", {class: "fraco"}, `${p.situacao}${p.nota ? ` · ${p.nota}` : ""}`));
    return card;
  }
  card.append(el("div", {class: "fraco"}, `vale até ${quandoCurto(p.vence_em) || "—"}`));
  const botoes = el("div", {class: "botoes"});
  const sim = el("button", {class: "acao perigo", type: "button"},
    CoordConv.armado === p.id ? "Tocar de novo para confirmar" : "Confirmar");
  sim.addEventListener("click", () => {
    if (CoordConv.armado !== p.id) {           // dois toques: o primeiro so arma
      CoordConv.armado = p.id;
      sim.textContent = "Tocar de novo para confirmar";
      setTimeout(() => { if (CoordConv.armado === p.id) { CoordConv.armado = null; sim.textContent = "Confirmar"; } }, 4000);
      return;
    }
    CoordConv.armado = null;
    coordDecidir(p.id, "confirmar");
  });
  const nao = el("button", {class: "acao", type: "button"}, "Recusar");
  nao.addEventListener("click", () => coordDecidir(p.id, "recusar"));
  botoes.append(sim, nao);
  card.append(botoes);
  return card;
}

function coordConversaDesenhar(dados) {
  const conversa = Array.isArray(dados.conversa) ? dados.conversa : [];
  const propostas = Array.isArray(dados.propostas) ? dados.propostas : [];
  const cerebro = dados.cerebro || {};
  $("coord-cerebro").textContent = cerebro.proibido
    ? `${cerebro.proibido}: ele não pensa até você liberar.`
    : `Pensou ${cerebro.pensamentos_na_hora ?? 0} de ${cerebro.limite_hora ?? "?"} vezes nesta hora.`;
  const pendentes = propostas.filter((p) => p.situacao === "pendente");
  const recentes = propostas.filter((p) => p.situacao !== "pendente").slice(0, 5);
  $("coord-propostas").replaceChildren(...(pendentes.length || recentes.length
    ? [...pendentes, ...recentes].map(coordProposta)
    : [el("div", {class: "fraco"}, "Nenhuma proposta.")]));
  const caixa = $("coord-mensagens");
  const noFim = caixa.scrollHeight - caixa.scrollTop - caixa.clientHeight < 40;
  const itens = conversa.map(coordMensagem);
  // "pensando…" enquanto houver entrada sem resposta (nao so a ultima linha:
  // confirmar uma proposta escreve uma linha do coordenador no meio)
  const ultima = conversa[conversa.length - 1];
  if (cerebro.na_fila > 0 || (ultima && ultima.de === "adrian" && !ultima.entrada)) {
    itens.push(el("div", {class: "coord-msg coordenador fraco"},
      cerebro.na_fila > 1 ? `pensando… (${cerebro.na_fila} na fila)` : "pensando…"));
  }
  caixa.replaceChildren(...(itens.length ? itens : [el("div", {class: "fraco"}, "Escreva abaixo: ele lê o estado do PC e responde aqui.")]));
  if (noFim) caixa.scrollTop = caixa.scrollHeight;
}

async function coordConversaCarregar() {
  try { coordConversaDesenhar(await api("/api/coordenador/conversa")); } catch (err) { conexao(false, err); }
}

async function coordFalar() {
  const campo = $("coord-texto");
  const texto = campo.value.trim();
  if (!texto || CoordConv.enviando) return;
  CoordConv.enviando = true;
  $("coord-enviar").disabled = true;
  try {
    await api("/api/coordenador/falar", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({texto})});
    campo.value = "";
  } catch (err) { avisar(err.message, true); }
  CoordConv.enviando = false;
  $("coord-enviar").disabled = false;
  coordConversaCarregar();
}

async function coordDecidir(id, decisao) {
  try {
    await api(`/api/coordenador/proposta/${encodeURIComponent(id)}`, {method: "POST",
      headers: {"Content-Type": "application/json"}, body: JSON.stringify({decisao})});
    avisar(decisao === "confirmar" ? "confirmada" : "recusada");
  } catch (err) { avisar(err.message, true); }
  coordConversaCarregar();
}

$("coord-enviar").addEventListener("click", coordFalar);
for (const b of document.querySelectorAll("#coord-abas [data-aba]")) {
  b.addEventListener("click", () => coordAba(b.dataset.aba));
}

function coordenadorMostrar() {
  coordCarregar();
  if (CoordConv.aba === "conversa") coordConversaCarregar();
  clearInterval(Coord.relogio);
  Coord.relogio = setInterval(() => {
    if (document.visibilityState !== "visible") return;
    coordCarregar();
    if (CoordConv.aba === "conversa") coordConversaCarregar();
  }, COORD_MS);
}

function coordenadorParar() {
  clearInterval(Coord.relogio); Coord.relogio = null;
}
