"use strict";
// O Provador do Ateliê (06/10/2026): o "jogo de vestir" dos lutadores.
// O jogo sorteia uma combinação fixa para cada lutador; aqui ele vê o
// lutador montado, troca cada peça com ‹ ›, sorteia, e o cadeado (Fixar)
// grava no guarda-roupa do PC. O que ele experimenta (setas e dado) mora só
// nesta tela (`Provador.escolha`) e vai junto em cada pedido: o servidor
// devolve a combinação já resolvida, com as URLs das imagens prontas.
const Provador = {lista: null, lutador: localStorage.getItem("painel.provador.lutador") || "",
  dados: null, escolha: {}, expressao: "neutro", todas: false, pedido: 0, pedidoPrevia: 0,
  ocupado: false, blobs: {}, escolhendo: true};
const PROVADOR_MAX_LISTA = 40;

function provadorTexto(id, texto) { $(id).textContent = texto; }

function provadorUrl(chave, blob) {
  if (Provador.blobs[chave]) URL.revokeObjectURL(Provador.blobs[chave]);
  Provador.blobs[chave] = URL.createObjectURL(blob);
  return Provador.blobs[chave];
}

// Busca a imagem com o token; a URL blob: so e criada por quem vai mostrar
// (uma resposta atrasada nao revoga a imagem que esta na tela).
async function provadorBuscar(caminho) {
  const token = localStorage.getItem(TOKEN);
  const resposta = await fetch(caminho, {headers: token ? {Authorization: `Bearer ${token}`} : {}});
  if (!resposta.ok) throw new Error("não consegui abrir a imagem");
  return {blob: await resposta.blob(), pecas: +(resposta.headers.get("X-Previa-Pecas") || 0)};
}

function provadorEscolhaTexto() {
  return Object.entries(Provador.escolha).map(([parte, v]) => `${parte}:${v}`).join(",");
}

async function provadorMostrar() {
  if (!Provador.lista) {
    try {
      Provador.lista = await api("/api/sprites/provador/lutadores");
      const seletor = $("provador-classe");
      for (const classe of Provador.lista.classes) seletor.append(el("option", {value: classe.chave}, classe.rotulo));
    } catch (erro) { return provadorTexto("provador-aviso", "Não consegui abrir a lista de lutadores: " + erro.message); }
  }
  provadorListar();
  if (Provador.lutador) provadorCarregar(); else provadorModoEscolher(true);
}

function provadorModoEscolher(sim) {
  Provador.escolhendo = sim;
  $("provador-escolher").classList.toggle("oculto", !sim);
  $("provador-quem").classList.toggle("oculto", sim || !Provador.dados);
  $("provador-palco-caixa").classList.toggle("oculto", sim || !Provador.dados);
  if (sim) $("provador-busca").focus({preventScroll: true});
}

// A lista: a busca pelo nome (sem acento) e o filtro por classe. Com uma
// classe escolhida, o lutador de exemplo dela vem primeiro.
function provadorSemAcento(texto) {
  return String(texto).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function provadorListar() {
  const lista = $("provador-lista"); lista.replaceChildren();
  if (!Provador.lista) return;
  const busca = provadorSemAcento($("provador-busca").value.trim());
  const classe = $("provador-classe").value;
  const exemplos = classe ? Provador.lista.exemplos.filter((e) => e.classe === classe) : [];
  const achados = Provador.lista.lutadores.filter((l) => (!classe || l.classe === classe) &&
    (!busca || provadorSemAcento(l.nome).includes(busca)));
  for (const lutador of [...exemplos, ...achados].slice(0, PROVADOR_MAX_LISTA)) {
    const fixadas = lutador.fixadas ? el("span", {class: "provador-fixadas"}, `🔒 ${lutador.fixadas}`) : null;
    const botao = el("button", {class: "acao provador-item" + (lutador.id === Provador.lutador ? " escolhido" : ""),
      type: "button", role: "listitem"},
      el("span", {class: "provador-item-nome"}, lutador.nome),
      el("span", {class: "provador-item-classe"}, lutador.classe_nome), fixadas);
    botao.addEventListener("click", () => provadorEscolher(lutador.id));
    lista.append(botao);
  }
  const total = exemplos.length + achados.length;
  provadorTexto("provador-lista-nota", !total ? "Nenhum lutador com esse nome."
    : total > PROVADOR_MAX_LISTA ? `Mostrando ${PROVADOR_MAX_LISTA} de ${total}: busque pelo nome ou escolha a classe.`
    : !classe ? "Escolha uma classe para ver também o lutador de exemplo dela." : "");
}

function provadorEscolher(id) {
  Provador.lutador = id; Provador.escolha = {};
  localStorage.setItem("painel.provador.lutador", id);
  $("provador-folha").classList.add("oculto");
  provadorTexto("provador-aviso", "");
  provadorCarregar();
}

async function provadorCarregar() {
  const pedido = ++Provador.pedido;
  try {
    const dados = await api(`/api/sprites/provador?lutador=${encodeURIComponent(Provador.lutador)}` +
      `&expressao=${encodeURIComponent(Provador.expressao)}&escolha=${encodeURIComponent(provadorEscolhaTexto())}`);
    if (pedido !== Provador.pedido) return;        // chegou atrasada: já é outro pedido
    provadorAplicar(dados);
  } catch (erro) {
    if (pedido !== Provador.pedido) return;
    if (erro.status === 404) {                      // o lutador sumiu do banco
      Provador.lutador = ""; localStorage.removeItem("painel.provador.lutador");
      provadorModoEscolher(true);
    }
    provadorTexto("provador-aviso", "Não consegui abrir o lutador: " + erro.message);
  }
}

function provadorAplicar(dados) {
  Provador.dados = dados; Provador.escolha = dados.escolha || {};
  if (dados.aviso) provadorTexto("provador-aviso", dados.aviso);
  provadorModoEscolher(false);
  provadorDesenhar();
}

function provadorSelo(peca) {
  if (peca.situacao === "fixada") return ["🔒", "Fixada por você"];
  if (peca.situacao === "experimento") return ["✋", "Experimentando: ainda não guardada"];
  if (peca.total < 2) return ["🎨", "Um desenho só: todos os lutadores usam este"];
  return ["🎲", peca.fixa_perdida ? "Do sorteio (a fixada foi apagada)" : "Sorteada pelo jogo"];
}

// As miniaturas valem por desenho: o redesenho revoga as do anterior, e a
// resposta atrasada de um desenho velho não cria URL (a <img> já saiu).
const ProvadorMinis = [];

function provadorDesenhar() {
  ProvadorMinis.splice(0).forEach((url) => URL.revokeObjectURL(url));
  const dados = Provador.dados;
  provadorTexto("provador-nome", dados.lutador.nome);
  provadorTexto("provador-classe-nome", dados.lutador.classe_nome);
  $("provador-exemplo").classList.toggle("oculto", dados.pode_fixar);
  provadorExpressoes();
  const caixa = $("provador-pecas"); caixa.replaceChildren();
  for (const peca of dados.pecas) caixa.append(provadorLinha(peca));
  if (!dados.pecas.length) caixa.append(el("p", {class: "fraco"},
    "Nenhuma peça desenhada ainda para este lutador: anexe em Montar peças."));
  provadorTexto("provador-sem-desenho", dados.sem_desenho.length
    ? `Sem desenho ainda (o jogo usa o de hoje): ${dados.sem_desenho.join(", ").toLowerCase()}.` : "");
  const contagem = {fixada: 0, sorteio: 0, experimento: 0};
  // Peça com um desenho só não é sorteio nem escolha: fica fora da conta.
  for (const peca of dados.pecas) if (peca.total > 1 || peca.tem_fixa) contagem[peca.situacao]++;
  provadorBotoes();
  // A folha do Godot é de UMA combinação: trocou alguma peça, ela some (não
  // fica na tela uma folha que já não é a do lutador mostrado).
  if (Provador.folhaChave !== provadorCombinacao()) $("provador-folha").classList.add("oculto");
  const partes = [];
  if (contagem.fixada) partes.push(`🔒 ${contagem.fixada} fixada${contagem.fixada > 1 ? "s" : ""}`);
  if (contagem.sorteio) partes.push(`🎲 ${contagem.sorteio} do sorteio`);
  if (contagem.experimento) partes.push(`✋ ${contagem.experimento} experimentando`);
  provadorTexto("provador-legenda", `Carinha ${modularCarinha(provadorNomeExpressao())}` +
    (partes.length ? " · " + partes.join(" · ") : ""));
  provadorPrevia();
}

// Os botoes de baixo: sem peca com mais de um desenho nao ha o que sortear
// nem fixar; durante um pedido, nada repete o toque.
function provadorBotoes() {
  const dados = Provador.dados;
  const varias = dados.pecas.some((p) => p.total > 1);
  $("provador-sortear").disabled = !varias || Provador.ocupado;
  $("provador-fixar").classList.toggle("oculto", !dados.pode_fixar);
  $("provador-soltar").classList.toggle("oculto", !dados.pode_fixar);
  $("provador-fixar").disabled = !varias || Provador.ocupado;
  $("provador-soltar").disabled = !dados.pecas.some((p) => p.tem_fixa) || Provador.ocupado;
  $("provador-ver-godot").classList.toggle("oculto", !dados.godot_previa);
}

function provadorCombinacao() {
  const dados = Provador.dados;
  return dados ? dados.lutador.id + "|" + dados.pecas.map((p) => `${p.parte}:${p.atual}`).join(",") : "";
}

function provadorNomeExpressao() {
  const atual = (Provador.dados?.expressoes || []).find((e) => e.id === Provador.expressao);
  return atual ? atual.nome : "neutro";
}

function provadorExpressoes() {
  const caixa = $("provador-expressoes"); caixa.replaceChildren();
  const lista = Provador.dados.expressoes || [];
  provadorTexto("provador-expressao-nome", modularCarinha(provadorNomeExpressao()));
  for (const expressao of lista) {
    if (!Provador.todas && !expressao.representante && expressao.id !== Provador.expressao) continue;
    const escolhida = expressao.id === Provador.expressao;
    const botao = el("button", {class: "acao modular-expressao" + (escolhida ? " escolhida" : ""), type: "button",
      "aria-pressed": escolhida ? "true" : "false"}, (escolhida ? "✓ " : "") + expressao.nome);
    botao.addEventListener("click", () => { Provador.expressao = expressao.id; provadorCarregar(); });
    caixa.append(botao);
  }
  const todas = $("provador-todas");
  todas.textContent = Provador.todas ? "Mostrar só as 6 principais" : `Ver todas as ${lista.length}`;
  todas.setAttribute("aria-expanded", Provador.todas ? "true" : "false");
}

// Uma linha por peça: ‹ miniatura › como num jogo de vestir, a contagem
// ("Olhos 2 de 5"), o selo (cadeado, dado ou mão) e as ações dela.
function provadorLinha(peca) {
  const [icone, selo] = provadorSelo(peca);
  const uma = peca.total < 2;
  const anterior = el("button", {class: "acao provador-seta", type: "button", "aria-label": `${peca.nome}: anterior`}, "‹");
  const proxima = el("button", {class: "acao provador-seta", type: "button", "aria-label": `${peca.nome}: próxima`}, "›");
  // Um desenho só: sem setas (nada para trocar), a miniatura fica no meio.
  anterior.addEventListener("click", () => provadorSeta(peca, -1));
  proxima.addEventListener("click", () => provadorSeta(peca, +1));
  const mini = el("img", {class: "provador-mini", alt: `${peca.nome} ${peca.indice} de ${peca.total}`,
    "data-variante": peca.atual});
  provadorBuscar(peca.imagens[peca.atual])
    .then(({blob}) => {
      if (!mini.isConnected) return;
      const url = URL.createObjectURL(blob); ProvadorMinis.push(url); mini.src = url;
    })
    .catch(() => { mini.alt = `${peca.nome}: sem esta carinha`; });
  const acoes = el("div", {class: "botoes provador-acoes"});
  if (!uma) {
    const dado = el("button", {class: "acao", type: "button", "aria-label": `Sortear só ${peca.nome.toLowerCase()}`}, "🎲 Sortear");
    dado.addEventListener("click", () => provadorSortear(peca.parte));
    acoes.append(dado);
  }
  if (Provador.dados.pode_fixar && peca.situacao !== "fixada" && !uma) {
    const fixar = el("button", {class: "acao", type: "button", "aria-label": `Fixar ${peca.nome.toLowerCase()}`}, "🔒 Fixar");
    fixar.addEventListener("click", () => provadorFixar(peca.parte));
    acoes.append(fixar);
  }
  if (Provador.dados.pode_fixar && peca.tem_fixa) {
    const soltar = el("button", {class: "acao", type: "button",
      "aria-label": `${peca.nome}: voltar ao sorteio`}, "↩ Voltar ao sorteio");
    soltar.addEventListener("click", () => provadorSoltar(peca.parte));
    acoes.append(soltar);
  }
  return el("div", {class: "provador-peca " + peca.situacao, "data-parte": peca.parte},
    el("div", {class: "provador-peca-topo"},
      el("strong", {}, peca.nome),
      el("span", {class: "provador-contagem"}, uma ? "só 1 desenho" : `${peca.indice} de ${peca.total}`),
      el("span", {class: "provador-selo"}, el("span", {"aria-hidden": "true"}, icone + " "), selo)),
    el("div", {class: "provador-controles"}, uma ? el("span") : anterior, mini, uma ? el("span") : proxima),
    el("p", {class: "fraco provador-dono"}, peca.dono +
      (peca.sem_carinha ? " · esta variante não tem esta carinha: na luta ela some" : "")),
    acoes.childElementCount ? acoes : null);
}

async function provadorPrevia() {
  const pedido = ++Provador.pedidoPrevia;
  try {
    const {blob, pecas} = await provadorBuscar(Provador.dados.previa);
    if (pedido !== Provador.pedidoPrevia) return;
    $("provador-previa").src = provadorUrl("previa", blob);
    if (!pecas) provadorTexto("provador-legenda", "Nada desenhado para este lutador: o jogo ainda usa o desenho de hoje.");
  } catch (_) {
    if (pedido === Provador.pedidoPrevia) provadorTexto("provador-legenda", "Não consegui montar a prévia.");
  }
}

function provadorSeta(peca, passo) {
  const i = (peca.ordem.indexOf(peca.atual) + passo + peca.ordem.length) % peca.ordem.length;
  Provador.escolha = {...Provador.escolha, [peca.parte]: peca.ordem[i]};
  provadorTexto("provador-aviso", "Só na tela: toque em Fixar para o jogo usar.");
  provadorCarregar();
}

async function provadorPost(acao, extra = {}) {
  if (Provador.ocupado) return;
  Provador.ocupado = true;
  const pedido = ++Provador.pedido;
  try {
    const dados = await api(`/api/sprites/provador/${acao}`, {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({lutador: Provador.lutador, escolha: Provador.escolha,
                            expressao: Provador.expressao, ...extra})});
    if (pedido === Provador.pedido) provadorAplicar(dados);
    if (acao !== "sortear" && Provador.lista) provadorAtualizarLista(dados.lutador);
  } catch (erro) { provadorTexto("provador-aviso", "Não deu: " + erro.message); }
  finally { Provador.ocupado = false; if (Provador.dados) provadorBotoes(); }
}

function provadorAtualizarLista(lutador) {
  const item = Provador.lista.lutadores.find((l) => l.id === lutador.id);
  if (item) { item.fixadas = lutador.fixadas; provadorListar(); }
}

function provadorSortear(parte = "") { provadorPost("sortear", parte ? {parte} : {}); }
function provadorFixar(parte = "") { provadorPost("fixar", parte ? {parte} : {}); }
function provadorSoltar(parte = "") {
  if (!parte && !confirm(`Voltar todas as peças de ${Provador.dados.lutador.nome} ao sorteio? ` +
                         "As escolhas fixadas saem do guarda-roupa.")) return;
  provadorPost("desfixar", parte ? {parte} : {});
}

async function provadorVerGodot() {
  if (!Provador.dados || !Provador.dados.godot_previa) return;
  const caminho = Provador.dados.godot, lutador = Provador.lutador, chave = provadorCombinacao();
  const botao = $("provador-ver-godot"); botao.disabled = true;
  provadorTexto("provador-aviso", "montando no Godot…");
  const token = localStorage.getItem(TOKEN);
  try {
    for (let tentativa = 0; tentativa < 90; tentativa++) {
      const resposta = await fetch(caminho, {headers: token ? {Authorization: `Bearer ${token}`} : {}});
      if (resposta.status === 202) {
        const dados = await resposta.json().catch(() => ({}));
        if (Provador.lutador === lutador) provadorTexto("provador-aviso", dados.mensagem || "montando no Godot…");
        await new Promise((ok) => setTimeout(ok, 1000)); continue;
      }
      if (!resposta.ok) {
        const dados = await resposta.json().catch(() => ({}));
        throw new Error(dados.erro || "o Godot não conseguiu desenhar a folha");
      }
      const url = provadorUrl("folha", await resposta.blob());
      if (Provador.lutador === lutador) {
        Provador.folhaChave = chave;
        $("provador-folha").src = url;
        $("provador-folha").classList.toggle("oculto", chave !== provadorCombinacao());
        provadorTexto("provador-aviso", `Folha montada no Godot: ${Provador.dados.lutador.nome} nas seis carinhas, com esta combinação.`);
        $("provador-folha").scrollIntoView({behavior: "smooth", block: "start"});
      }
      return;
    }
    throw new Error("o Godot demorou mais do que o esperado; tente de novo");
  } catch (erro) { provadorTexto("provador-aviso", "Não deu para ver no Godot: " + erro.message); }
  finally { botao.disabled = false; }
}

$("provador-busca").addEventListener("input", () => provadorListar());
$("provador-classe").addEventListener("change", () => provadorListar());
$("provador-trocar").addEventListener("click", () => { provadorListar(); provadorModoEscolher(true); });
$("provador-todas").addEventListener("click", () => { Provador.todas = !Provador.todas; provadorExpressoes(); });
$("provador-sortear").addEventListener("click", () => provadorSortear());
$("provador-fixar").addEventListener("click", () => provadorFixar());
$("provador-soltar").addEventListener("click", () => provadorSoltar());
$("provador-ver-godot").addEventListener("click", () => provadorVerGodot());
$("provador-folha").addEventListener("click", () => { if ($("provador-folha").src) window.open($("provador-folha").src, "_blank"); });
