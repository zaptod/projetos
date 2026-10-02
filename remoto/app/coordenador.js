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
    return;
  }
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

function coordenadorMostrar() {
  coordCarregar();
  clearInterval(Coord.relogio);
  Coord.relogio = setInterval(() => { if (document.visibilityState === "visible") coordCarregar(); }, COORD_MS);
}

function coordenadorParar() {
  clearInterval(Coord.relogio); Coord.relogio = null;
}
