"use strict";
// O supervisor so publica estado; cada toque abaixo vira um pedido pendente.
// Desde 02/10/2026 o painel dele e a Conversa sao a aba Coordenador de Agora,
// e o "Controlar o PC" (as acoes fechadas do PC) mora em Mandar, com os outros
// botoes de comando; os mesmos ids, desenhados por `coordDesenhar`.

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
    // cartão vazio parece "nada a mostrar"; é "não há como saber" (14/10)
    coordSemDados("o coordenador está fora do ar, então não há retrato do PC.");
    // em Mandar o cartão não pode ficar vazio sem dizer por quê
    $("coord-acoes").replaceChildren(el("span", {class: "fraco"},
      "O coordenador está fora do ar: nada a controlar agora."));
    return;
  }
  coordTrabalho(dados.trabalho);
  topo.replaceChildren(el("h2", {}, "Coordenador"),
    el("div", {class: "grande coord-vivo"}, "NO AR"),
    el("div", {class: "fraco"}, `desde ${quandoCurto(dados.desde) || "—"} · versão ${dados.versao || "—"}`));
  const eventos = Array.isArray(dados.eventos) ? dados.eventos : [];
  coordLimparPedidos(eventos);
  const servicos = dados.servicos && typeof dados.servicos === "object" ? dados.servicos : {};
  // PC ligado e lista vazia: o cartão diz que não há nada, e desde quando
  // (conferente, 14/10, v70: em branco parecia defeito ou dado perdido). Os
  // eventos são os do coordenador desde que ele ligou (`desde`).
  const vazio = (texto) => [el("div", {class: "fraco coord-vazio"}, texto)];
  const nomes = Object.entries(servicos);
  $("coord-servicos").replaceChildren(...(nomes.length ? nomes.map(([nome, s]) =>
    coordServico(nome, s && typeof s === "object" ? s : {}, eventos))
    : vazio("Nenhum serviço publicado pelo coordenador.")));
  const acoes = Array.isArray(dados.acoes_pc) ? dados.acoes_pc : [];
  if (!acoes.some((a) => a && a.id)) {
    $("coord-acoes").replaceChildren(el("span", {class: "fraco"}, "Nenhuma ação do PC publicada."));
  } else $("coord-acoes").replaceChildren(...acoes.filter((a) => a && a.id).map((acao) => {
    const pendente = coordPedido("pc_acao", acao.id);
    const botao = el("button", {class: `acao${acao.perigo ? " perigo" : ""}`, type: "button"}, acao.rotulo || acao.id);
    botao.disabled = !!pendente;
    botao.addEventListener("click", () => acao.perigo ? coordPedirConfirmacao(acao) : coordEnviar("pc_acao", acao.id));
    return botao;
  }));
  const ligou = quandoCurto(dados.desde);
  $("coord-eventos").replaceChildren(...(eventos.length ? eventos.slice().sort((a, b) =>
    dataPC(b.em).getTime() - dataPC(a.em).getTime()).map((evento) =>
    el("div", {class: "linha"}, el("span", {class: "coord-evento-hora"}, quandoCurto(evento.em)),
      el("div", {class: "corpo"}, evento.texto || evento.tipo || "evento")))
    : vazio(ligou ? `Nada de novo desde ${ligou} (quando o coordenador ligou).`
      : "Nada de novo desde que o coordenador ligou.")));
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
  try {
    const dados = await api("/api/coordenador");
    Coord.mesaEm = new Date().toISOString();
    const linha = $("coord-mesa");
    linha.textContent = coordResumo(dados);
    linha.classList.remove("velho");
    linha.classList.toggle("fora", !dados.vivo);
  } catch (err) { coordMesaSemDados(err); }
  if (typeof pedidosCarregar === "function") pedidosCarregar();
}

// A linha do coordenador em Agora sem resposta do PC: "sem dados", com o
// diagnóstico da faixa e a hora do último retrato bom, marcada como velha.
// Nunca o "no ar · N/N" de antes da queda (v71), e nunca FORA DO AR, que a
// tela não sabe: FORA DO AR só quando o /api/coordenador responde `vivo:
// false` (conferente, 14/10, v72).
function coordMesaSemDados(err) {
  if (err && err.status === 401) return;             // o pareamento já trata
  if (err && !(err instanceof ErroApi)) { console.error("erro na tela:", err); return; }
  const linha = $("coord-mesa");
  const ultimo = Coord.mesaEm ? quandoFoi(Coord.mesaEm) : "";
  linha.textContent = `Coordenador: sem dados — ${diagnosticoPC(err).motivo}`
    + (ultimo ? ` (último ${ultimo})` : "");
  linha.classList.remove("fora");
  linha.classList.add("velho");
}

// Os três cartões do painel sem dado: diz POR QUÊ, em vez de ficarem vazios
// (o conferente, 14/10: com o PC fora, TRABALHO, SERVIÇOS e O QUE ACONTECEU
// apareciam em branco, como se não houvesse nada). Nunca o retrato velho como
// se fosse de agora: ele sai, e a próxima leitura boa redesenha.
function coordSemDados(porque) {
  const linha = () => el("div", {class: "fraco coord-sem-dados"}, `Dados indisponíveis: ${porque}`);
  $("coord-trabalho").replaceChildren(linha());
  $("coord-servicos").replaceChildren(linha());
  $("coord-eventos").replaceChildren(linha());
}

async function coordCarregar() {
  try { coordDesenhar(await api("/api/coordenador")); conexao(true); } catch (err) {
    conexao(false, err);
    if (err && err.status === 401) return;          // o pareamento já trata
    // erro do próprio JavaScript não é "PC fora": vai ao console (conexao)
    if (err && !(err instanceof ErroApi)) return;
    const contato = localStorage.getItem(CONTATO);
    const desde = contato ? ` (último contato ${quandoCurto(contato)})` : "";
    // o mesmo diagnóstico da faixa (diagnosticoPC, app.js): uma frase só na tela
    const porque = `${diagnosticoPC(err).motivo}${desde}.`;
    $("coord-topo").replaceChildren(el("h2", {}, "Coordenador"),
      el("div", {class: "grande coord-fora"}, "SEM DADOS"),
      el("div", {class: "fraco"}, porque.charAt(0).toUpperCase() + porque.slice(1)));
    coordSemDados(porque);
  }
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
const CoordConv = {aba: "painel", enviando: false, armado: null, passar: null, passando: null};

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
  const quem = de === "adrian" ? "você" : m.de === "orquestrador" ? "🧭 orquestrador" : "🛰 coordenador";
  const pelo = m.origem === "telegram" ? " · pelo Telegram" : "";
  const bolha = el("div", {class: `coord-msg ${de}`}, m.texto || "",
    el("span", {class: "fraco"}, `${quem} · ${quandoCurto(m.em) || ""}${pelo}`));
  if (m.pode_passar && m.pedido) bolha.append(coordPassarBotao(m.pedido));
  return bolha;
}

// 07/10 (Grimório app-e-bot/conversa-pergunta-livre, "O modelo decide"): a
// pergunta livre que ficou como conversa — o modelo a leu como conversa, ou
// não conseguiu ler — vira trabalho só pelo toque dele. Dois toques: um toque
// perdido ao rolar a conversa não contrata ninguém.
// O segundo toque vale por 4 s. A conversa se redesenha a cada 5 s: o botão
// do primeiro toque já não é o da tela quando o prazo acaba (conferente,
// 07/10: o rótulo "Tocar de novo" ficava velho). O prazo mora no estado, o
// rótulo nasce dele, e ao vencer muda o botão que ESTIVER na tela.
const COORD_TOQUE_MS = 4000;

function coordArmado(campo, id) {
  const armado = CoordConv[campo];
  return !!armado && armado.id === id && Date.now() < armado.ate;
}

// Um botão de dois toques que sobrevive ao redesenho: `campo` é "passar" ou
// "armado" em CoordConv; o botão leva data-dois-toques="<campo>:<id>".
function coordDoisToques(campo, id, classe, rotulo, rotuloArmado, fazer) {
  const chave = `${campo}:${id}`;
  const b = el("button", {class: `acao ${classe}`, type: "button", "data-dois-toques": chave},
    coordArmado(campo, id) ? rotuloArmado : rotulo);
  b.addEventListener("click", () => {
    if (!coordArmado(campo, id)) {               // o primeiro toque só arma
      CoordConv[campo] = {id, ate: Date.now() + COORD_TOQUE_MS};
      b.textContent = rotuloArmado;
      setTimeout(() => {
        if (coordArmado(campo, id)) return;      // armado de novo depois: o prazo é outro
        if (CoordConv[campo] && CoordConv[campo].id === id) CoordConv[campo] = null;
        for (const atual of document.querySelectorAll("[data-dois-toques]"))
          if (atual.dataset.doisToques === chave) atual.textContent = rotulo;
      }, COORD_TOQUE_MS + 50);
      return;
    }
    CoordConv[campo] = null;
    fazer();
  });
  return b;
}

function coordPassarBotao(id) {
  const b = coordDoisToques("passar", id, "coord-passar", "↪ Passar para a equipe",
    "Tocar de novo para passar", () => coordPassar(id));
  b.disabled = CoordConv.passando === id;
  return el("div", {class: "botoes"}, b);
}

async function coordPassar(id) {
  if (CoordConv.passando) return;
  CoordConv.passando = id;
  try {
    const r = await api(`/api/coordenador/pedido/${encodeURIComponent(id)}/equipe`, {method: "POST",
      headers: {"Content-Type": "application/json"}, body: "{}"});
    avisar(pedidoAvisoDoEnvio(r || {}));
  } catch (err) { avisar(err.message, true); }
  CoordConv.passando = null;
  coordConversaCarregar();
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
  const sim = coordDoisToques("armado", p.id, "perigo", "Confirmar", "Tocar de novo para confirmar",
    () => coordDecidir(p.id, "confirmar"));
  const nao = el("button", {class: "acao", type: "button"}, "Recusar");
  nao.addEventListener("click", () => coordDecidir(p.id, "recusar"));
  botoes.append(sim, nao);
  card.append(botoes);
  return card;
}

// Os pedidos (03/10): cada pedido livre vai a um trabalhador `orquestrador`
// do servidor; o estado dele aparece aqui e no cartão "Pedir" do Agora.
// v2 (05/10): "no Grimório" só quando o pedido espera um nó (grimorio_ref).
const PEDIDO_ROTULO = {recebido: "recebido", trabalhando: "trabalhando", esperando: "em espera",
  esperando_voce: "esperando você", entregue: "entregue",
  parado_limite: "parado no limite — volta sozinho",
  executando: "o servidor está executando",
  // 05/10 (conferente 5): o pulso solta a trava enquanto cria a worktree
  contratando: "chamando o trabalhador",
  conferido: "conferido", respondido: "respondido", falhou: "falhou"};
// 05/10 (conferente 3): texto solto NUNCA continua um pedido (grudava no
// "ativo mais novo", de outro assunto). Continuar é só pelo Responder, que
// manda o id do pedido: /api/coordenador/pedido/<id>/responder. Executando
// (o servidor rodando uma ação) não recebe resposta.
const PEDIDO_SEM_RESPONDER = ["executando"];
const PedidoResp = {aberto: null, rascunho: new Map(), enviando: false, decidindo: null};

function pedidoTitulo(p) {
  return String(p.texto || p.id).split("\n")[0];
}

// A permissão do estado do servidor (gerente, renovação, paralelo) pedida pelo
// trabalhador: texto não aprova nem nega, então o cartão mostra Permitir e
// Negar (a mesma rota de Agora › Equipe) em vez de Responder.
function pedidoPermissao(p) {
  const pe = p.permissao_estado;
  if (pe.pendente === false) {
    return el("div", {class: "pedido-responder fraco"},
      `Decidido: o servidor cuida de \`${pe.comando || "?"}\` no próximo pulso e responde aqui.`);
  }
  const caixa = el("div", {class: "pedido-responder"},
    el("div", {class: "fraco"}, `Permitir que o servidor execute \`${pe.comando || "?"}\`? `
      + "Aprovado, o servidor executa, relê para conferir e responde aqui."));
  async function decidir(decisao) {
    if (PedidoResp.decidindo) return;
    PedidoResp.decidindo = p.id;
    try {
      await api(`/api/equipe/${encodeURIComponent(pe.trabalhador || p.trabalhador)}/permissao`, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({decisao, sempre: false})});
      avisar(`${decisao === "permitir" ? "Permitido" : "Negado"}: ${pe.comando || "?"} `
        + `(${p.id}). O servidor responde no pedido.`);
    } catch (err) { avisar(err.message, true); }
    PedidoResp.decidindo = null;
    pedidosCarregar();
  }
  const permitir = el("button", {class: "acao primario", type: "button"}, "✅ Permitir");
  permitir.addEventListener("click", () => decidir("permitir"));
  const negar = el("button", {class: "acao", type: "button"}, "❌ Negar");
  negar.addEventListener("click", () => decidir("negar"));
  permitir.disabled = negar.disabled = PedidoResp.decidindo === p.id;
  caixa.append(el("div", {class: "botoes"}, permitir, negar));
  return caixa;
}

function pedidoRotulo(p) {
  const rotulo = PEDIDO_ROTULO[p.situacao] || p.situacao || "recebido";
  return p.situacao === "esperando_voce" && p.grimorio_ref
    ? `${rotulo} no Grimório (${p.grimorio_ref})` : rotulo;
}

function pedidoLinha(p) {
  const titulo = pedidoTitulo(p);
  const card = el("div", {class: "coord-proposta"},
    el("strong", {}, `${pedidoRotulo(p)} · ${titulo.slice(0, 120)}`),
    el("div", {class: "fraco"}, [p.id, p.ia ? `${p.ia} orquestrador` : "",
      p.trabalhador && p.trabalhador !== p.id ? p.trabalhador : "",
      p.progresso || "", quandoCurto(p.atualizado_em) || ""].filter(Boolean).join(" · ")),
    p.motivo ? el("div", {class: "coord-aviso"}, p.motivo) : null);
  if (p.situacao === "esperando_voce" && p.permissao_estado && p.permissao_estado.comando) {
    card.append(pedidoPermissao(p));
  } else if (p.trabalhador && !PEDIDO_SEM_RESPONDER.includes(p.situacao)) {
    card.append(pedidoResponder(p));
  }
  return card;
}

function pedidoResponder(p) {
  const caixa = el("div", {class: "pedido-responder"});
  if (PedidoResp.aberto !== p.id) {
    const b = el("button", {class: "acao", type: "button"}, "Responder");
    b.addEventListener("click", () => { PedidoResp.aberto = p.id; pedidosCarregar(); });
    caixa.append(b);
    return caixa;
  }
  const campo = el("textarea", {class: "pedido-resposta", rows: "3", maxlength: "4000",
    "aria-label": `Resposta ao pedido ${p.id}`, placeholder: "Sua resposta a este pedido"});
  campo.value = PedidoResp.rascunho.get(p.id) || "";
  campo.addEventListener("input", () => PedidoResp.rascunho.set(p.id, campo.value));
  const enviar = el("button", {class: "acao primario", type: "button"}, "Enviar a este pedido");
  enviar.disabled = PedidoResp.enviando;
  enviar.addEventListener("click", () => pedidoEnviarResposta(p.id, campo.value));
  const cancelar = el("button", {class: "acao", type: "button"}, "Cancelar");
  cancelar.addEventListener("click", () => { PedidoResp.aberto = null; pedidosCarregar(); });
  caixa.append(campo, el("div", {class: "botoes"}, enviar, cancelar));
  return caixa;
}

async function pedidoEnviarResposta(id, texto) {
  texto = String(texto || "").trim();
  if (!texto || PedidoResp.enviando) return;
  PedidoResp.enviando = true;
  try {
    const r = await api(`/api/coordenador/pedido/${encodeURIComponent(id)}/responder`, {method: "POST",
      headers: {"Content-Type": "application/json"}, body: JSON.stringify({texto})});
    PedidoResp.rascunho.delete(id);
    PedidoResp.aberto = null;
    avisar(`Resposta enviada ao pedido ${id}${r && r.titulo ? ` («${r.titulo.slice(0, 60)}»)` : ""}.`);
  } catch (err) { avisar(err.message, true); }
  PedidoResp.enviando = false;
  pedidosCarregar();
}

function pedidosDesenhar(dados) {
  // escrevendo uma resposta: o pulso de 5 s não redesenha por cima (perderia o foco)
  const ativo = document.activeElement;
  if (ativo && ativo.classList && ativo.classList.contains("pedido-resposta")) return;
  const pedidos = Array.isArray(dados.pedidos) ? dados.pedidos : [];
  const vivos = pedidos.filter((p) => !["conferido", "respondido", "falhou"].includes(p.situacao));
  const recentes = [...vivos, ...pedidos.filter((p) => !vivos.includes(p))].slice(0, 6);
  // duas listas montadas, não clonadas: o clone perdia os toques do Responder
  const montar = (quantos) => {
    return recentes.length ? recentes.slice(0, quantos).map(pedidoLinha)
      : [el("div", {class: "fraco"}, "Nenhum pedido ainda.")];
  };
  $("coord-pedidos").replaceChildren(...montar(6));
  $("pedido-estado").replaceChildren(...montar(3).slice(0, 3));
}

function coordConversaDesenhar(dados) {
  const conversa = Array.isArray(dados.conversa) ? dados.conversa : [];
  const propostas = Array.isArray(dados.propostas) ? dados.propostas : [];
  const cerebro = dados.cerebro || {};
  $("coord-cerebro").textContent = (cerebro.proibido
    ? `${cerebro.proibido}: o cérebro não pensa até você liberar.`
    : `Pensou ${cerebro.pensamentos_na_hora ?? 0} de ${cerebro.limite_hora ?? "?"} vezes nesta hora.`)
    + " Pergunta curta de estado vai ao cérebro; pedido vai ao 🧭 orquestrador do servidor.";
  const pendentes = propostas.filter((p) => p.situacao === "pendente");
  const recentes = propostas.filter((p) => p.situacao !== "pendente").slice(0, 5);
  $("coord-propostas").replaceChildren(...(pendentes.length || recentes.length
    ? [...pendentes, ...recentes].map(coordProposta)
    : [el("div", {class: "fraco"}, "Nenhuma proposta.")]));
  pedidosDesenhar(dados);
  const caixa = $("coord-mensagens");
  const noFim = caixa.scrollHeight - caixa.scrollTop - caixa.clientHeight < 40;
  const itens = conversa.map(coordMensagem);
  // "pensando…" enquanto houver entrada do cerebro sem resposta; a linha do
  // pedido nao conta (o orquestrador responde "recebido" na hora)
  const ultima = conversa[conversa.length - 1];
  // 06/10: a conversa solta ("oi", "orquestrador?") espera a resposta do
  // modelo leve por alguns segundos; a linha dele leva `papo`
  if (cerebro.na_fila > 0 || (ultima && ultima.de === "adrian"
      && ((!ultima.entrada && !ultima.pedido) || ultima.papo))) {
    itens.push(el("div", {class: "coord-msg coordenador fraco"},
      cerebro.na_fila > 1 ? `pensando… (${cerebro.na_fila} na fila)` : "pensando…"));
  }
  caixa.replaceChildren(...(itens.length ? itens : [el("div", {class: "fraco"}, "Escreva abaixo: uma pergunta de estado ou um pedido.")]));
  if (noFim) caixa.scrollTop = caixa.scrollHeight;
}

async function coordConversaCarregar() {
  try { coordConversaDesenhar(await api("/api/coordenador/conversa")); } catch (err) { conexao(false, err); }
}

async function pedidosCarregar() {
  try {
    pedidosDesenhar(await api("/api/coordenador/conversa"));
    Coord.pedidosEm = new Date().toISOString();
  } catch (err) { pedidosSemDados(err); }
}

// Sem resposta do PC, a lista de pedidos (PEDIR em Agora e a do Coordenador)
// não fica com o "esperando você…" e o Responder de antes da queda como se
// fossem de agora (conferente, 14/10, v72). A próxima leitura boa redesenha.
function pedidosSemDados(err) {
  if (err && err.status === 401) return;
  if (err && !(err instanceof ErroApi)) { console.error("erro na tela:", err); return; }
  const ativo = document.activeElement;            // escrevendo uma resposta: não apaga
  if (ativo && ativo.classList && ativo.classList.contains("pedido-resposta")) return;
  const ultimo = Coord.pedidosEm ? ` (último dado ${quandoFoi(Coord.pedidosEm)})` : "";
  const linha = () => el("div", {class: "fraco orq-sem-dados"},
    `sem dados — ${diagnosticoPC(err).motivo}${ultimo}`);
  $("pedido-estado").replaceChildren(linha());
  $("coord-pedidos").replaceChildren(linha());
}

// 05/10: chamava-se coordEnviar, o MESMO nome da função dos botões de serviço
// (acima); a segunda declaração vencia e "Reiniciar" virava um pedido de texto.
async function coordMandarTexto(texto) {
  return api("/api/coordenador/falar", {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({texto})});
}

// O aviso diz QUAL pedido nasceu (05/10, conferente 3: "Continuação enviada
// ao mesmo orquestrador" não dizia a qual).
function pedidoAvisoDoEnvio(r) {
  if (r.para === "cerebro") return "Pergunta de estado: o cérebro responde na Conversa.";
  // 05/10 (conferente 5): agradecimento solto da lista fixa ("ok", "valeu",
  // "obrigado", "beleza") não contrata ninguém; o resto do texto é pedido
  // 06/10: a resposta de verdade está na Conversa, escrita como gente; o
  // aviso só diz onde (sem id nem retrato)
  if (r.para === "conversa" && r.curto) return "De nada! Agradecimento não abre pedido; "
    + "para responder a um pedido, toque Responder nele.";
  if (r.para === "conversa") return "Respondendo na Conversa…";
  return `Entendi${r.titulo ? ` («${String(r.titulo).slice(0, 60)}»)` : ""}: vou passar para `
    + "a equipe. Na Conversa eu digo quando começa.";
}

async function coordFalar() {
  const campo = $("coord-texto");
  const texto = campo.value.trim();
  if (!texto || CoordConv.enviando) return;
  CoordConv.enviando = true;
  $("coord-enviar").disabled = true;
  try {
    const r = await coordMandarTexto(texto);
    campo.value = "";
    avisar(pedidoAvisoDoEnvio(r || {}));
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

let pedidoEnviando = false;
async function pedidoRapido() {
  const campo = $("pedido-texto"), texto = campo.value.trim();
  // toque duplo mandava o pedido duas vezes (03/10)
  if (!texto || pedidoEnviando) return;
  pedidoEnviando = true;
  $("pedido-enviar").disabled = true;
  try {
    const r = await coordMandarTexto(texto);
    campo.value = "";
    avisar(pedidoAvisoDoEnvio(r || {}));
  } catch (err) { avisar(err.message, true); }
  finally {
    pedidoEnviando = false;
    $("pedido-enviar").disabled = false;
  }
  pedidosCarregar();
}

$("coord-enviar").addEventListener("click", () => coordFalar());
$("pedido-enviar").addEventListener("click", () => pedidoRapido());
$("pedido-conversa").addEventListener("click", (e) => { CoordConv.aba = "conversa"; abrir("coordenador", e.currentTarget); coordAba("conversa"); });
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
