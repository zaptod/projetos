"use strict";
// O Atelie nao conhece caminhos do PC: cada imagem da previa e buscada com o
// token, convertida em blob: e esquecida ao trocar de tentativa.
const Atelie = {catalogo: null, sujeito: "", slot: null, arquivo: null, urls: []};
const Modular = {dados: null, grupo: "lutador", alvo: "_", slot: null, expressao: "neutro", todas: false,
  pedido: 0, pedidoPrevia: 0, versao: 0, folhas: {}, blobs: {}, nova: false};
const Recortador = {arquivo: null, dados: null, selecionados: new Set(), urls: [], pedido: 0, olhosMexeu: false};

// "Ver no Godot" (painel e Provador): com o PC ocupado a folha levou 62 s
// (conferente, 06/10); o servidor para o Godot em 150 s e a tela espera até
// 3 min. `vivo()` falso (fechou o Ateliê, trocou de lutador ou de estilo)
// cancela a espera sem mexer no aviso de ninguém.
const GODOT_ESPERA_MS = 180000;
const GODOT_OCUPADO_MS = 8000;
let GodotGeracao = 0;               // sobe ao fechar o Ateliê: toda espera aberta para
async function godotEsperar(caminho, avisar, vivo) {
  const token = localStorage.getItem(TOKEN);
  const geracao = GodotGeracao, inicio = Date.now();
  const segue = () => geracao === GodotGeracao && vivo();
  while (Date.now() - inicio < GODOT_ESPERA_MS) {
    if (!segue()) return null;
    const resposta = await fetch(caminho, {headers: token ? {Authorization: `Bearer ${token}`} : {}});
    if (!segue()) return null;
    if (resposta.status === 202) {
      const dados = await resposta.json().catch(() => ({}));
      avisar(dados.situacao === "na_fila" ? dados.mensagem
        : Date.now() - inicio >= GODOT_OCUPADO_MS ? "montando… o PC está ocupado, pode levar 1–2 min"
        : (dados.mensagem || "montando no Godot…"));
      await new Promise((ok) => setTimeout(ok, 1500));
      continue;
    }
    if (!resposta.ok) {
      const dados = await resposta.json().catch(() => ({}));
      throw new Error(dados.erro || "o Godot não conseguiu desenhar a folha");
    }
    return await resposta.blob();
  }
  throw new Error("o Godot passou de 3 minutos; tente de novo quando o PC estiver mais livre");
}

// As imagens do painel modular tem chave propria (previa, folha:<estilo>,
// mini:<lugar>): a troca de tela do app revoga Atelie.urls, e a folha
// guardada de um estilo nao pode virar imagem quebrada na volta.
function modularUrl(chave, blob) {
  if (Modular.blobs[chave]) URL.revokeObjectURL(Modular.blobs[chave]);
  Modular.blobs[chave] = URL.createObjectURL(blob);
  return Modular.blobs[chave];
}

async function modularBlob(chave, caminho) {
  const token = localStorage.getItem(TOKEN);
  const resposta = await fetch(caminho, {headers: token ? {Authorization: `Bearer ${token}`} : {}});
  if (!resposta.ok) throw new Error("não consegui abrir a imagem");
  return modularUrl(chave, await resposta.blob());
}

function atelieLimparUrls() {
  Atelie.urls.forEach((url) => URL.revokeObjectURL(url));
  Atelie.urls = [];
}

function recortadorLimparUrls() {
  Recortador.urls.forEach((url) => URL.revokeObjectURL(url));
  Recortador.urls = [];
}

async function recortadorBlob(caminho) {
  const token = localStorage.getItem(TOKEN);
  const resposta = await fetch(caminho, {headers: token ? {Authorization: `Bearer ${token}`} : {}});
  if (!resposta.ok) throw new Error("não consegui abrir a prévia");
  const url = URL.createObjectURL(await resposta.blob());
  Recortador.urls.push(url);
  return url;
}

async function atelieBlob(caminho) {
  const token = localStorage.getItem(TOKEN);
  const resposta = await fetch(caminho, {headers: token ? {Authorization: `Bearer ${token}`} : {}});
  if (!resposta.ok) throw new Error("não consegui abrir a prévia");
  const url = URL.createObjectURL(await resposta.blob());
  Atelie.urls.push(url);
  return url;
}

function atelieOpcoes(salvar = false, substituir = false) {
  return {sujeito: Atelie.sujeito, nome: $("atelie-nome").value.trim().toLowerCase(),
    slot: Atelie.slot.id, tolerancia: +$("atelie-tolerancia").value,
    modo: $("atelie-modo").value, colunas: +$("atelie-colunas").value,
    linhas: +$("atelie-linhas").value, espelhar: $("atelie-espelho").checked,
    salvar, substituir, arquivo: Atelie.arquivo && Atelie.arquivo.name};
}

async function atelieEnviar(salvar = false, substituir = false) {
  if (!Atelie.arquivo || !Atelie.slot) return;
  const aviso = $("atelie-aviso"); aviso.textContent = "processando no PC…";
  const dados = new FormData();
  dados.append("imagem", Atelie.arquivo);
  dados.append("opcoes", JSON.stringify(atelieOpcoes(salvar, substituir)));
  try {
    const resposta = await api("/api/atelie/importar", {method: "POST", body: dados});
    atelieLimparUrls();
    const previas = $("atelie-previas"); previas.replaceChildren();
    for (const [rotulo, url] of [["original", resposta.original], ["limpa", resposta.limpa],
                                 ["folha", resposta.folha], ["animação", resposta.previa],
                                 ...(resposta.quadros_urls || []).map((u, i) => [`quadro ${i + 1}`, u])]) {
      const img = el("img", {alt: rotulo}); img.src = await atelieBlob(url);
      previas.append(el("figure", {}, img, el("figcaption", {class: "fraco"}, rotulo)));
    }
    aviso.textContent = `${resposta.quadros} quadro(s)` + (resposta.avisos.length ? ` · ${resposta.avisos.join(" · ")}` : "")
      + (resposta.salvo ? " · salvo" : "");
    conexao(true);
  } catch (erro) {
    if (salvar && !substituir && /confirme substituir/.test(erro.message) &&
        confirm("Já há uma imagem nesse lugar. Trocar pela nova?")) return atelieEnviar(true, true);
    aviso.textContent = "falhou: " + erro.message; conexao(false, erro);
  }
}

function atelieDesenharSlots() {
  const alvo = $("atelie-slots"); alvo.replaceChildren();
  const dados = Atelie.catalogo.sujeitos[Atelie.sujeito];
  for (const slot of dados.slots) {
    const b = el("button", {class: "acao atelie-slot", type: "button"},
      slot.vazio ? "vazio · " + slot.rotulo : "✓ " + slot.rotulo);
    b.addEventListener("click", () => {
      Atelie.slot = slot; $("atelie-slot-titulo").textContent = slot.rotulo;
      $("atelie-editor").classList.remove("oculto"); $("atelie-previas").replaceChildren();
      $("atelie-aviso").textContent = slot.vazio ? "Escolha uma imagem." : "Este slot já tem uma imagem; salvar pede confirmação.";
    });
    alvo.append(b);
  }
}

async function atelieCarregar() {
  const nome = $("atelie-nome").value.trim().toLowerCase();
  const sufixo = Atelie.sujeito ? `?sujeito=${encodeURIComponent(Atelie.sujeito)}&nome=${encodeURIComponent(nome)}` : "";
  try {
    const dados = await api("/api/atelie" + sufixo);
    Atelie.catalogo = dados;
    const sujeitos = Object.keys(dados.sujeitos);
    if (!Atelie.sujeito || !dados.sujeitos[Atelie.sujeito]) Atelie.sujeito = sujeitos[0];
    const select = $("atelie-sujeito");
    if (!select.options.length) {
      for (const id of sujeitos) select.append(el("option", {value: id}, dados.sujeitos[id].rotulo || id));
      select.value = Atelie.sujeito;
    }
    // Com sujeito especifico, a resposta traz somente ele e marca os vazios.
    if (dados.sujeitos[Atelie.sujeito]) atelieDesenharSlots();
    // A aba e carregada por demanda pelo app; encadear aqui garante que o
    // painel novo acompanhe a mesma abertura, mesmo numa casca antiga.
    modularCarregar();
  } catch (erro) { $("atelie-slots").textContent = "falhou: " + erro.message; conexao(false, erro); }
}

// O Ateliê tem dois modos: montar as peças (anexo, recortador, antigo) e o
// Provador (o jogo de vestir). O último usado volta na próxima abertura.
const ATELIE_MODO = "painel.atelie.modo";
function atelieModo() { return localStorage.getItem(ATELIE_MODO) === "provador" ? "provador" : "montar"; }

function atelieTrocarModo(modo) {
  localStorage.setItem(ATELIE_MODO, modo);
  $("atelie-montar").classList.toggle("oculto", modo !== "montar");
  $("atelie-provador").classList.toggle("oculto", modo !== "provador");
  $("atelie-modo-montar").setAttribute("aria-pressed", String(modo === "montar"));
  $("atelie-modo-provador").setAttribute("aria-pressed", String(modo === "provador"));
  if (modo === "provador" && typeof provadorMostrar === "function") provadorMostrar();
  else atelieCarregar();
}

function atelieMostrar() { atelieTrocarModo(atelieModo()); }
function atelieParar() { atelieLimparUrls(); recortadorLimparUrls(); GodotGeracao++; }

// Rola até `alvo` deixando o topo dele LOGO ABAIXO da prévia presa (em pé
// ela fica por cima do conteúdo; o scrollIntoView punha o topo da folha do
// Godot embaixo dela). Deitado a prévia mora na outra coluna: não conta.
// No Montar (prévia escondida) o topo fica logo abaixo do cabeçalho do app
// (v54: o scrollIntoView punha a folha embaixo dele).
function atelieRolarAte(alvo) {
  const livro = alvo.closest(".livro");
  if (!livro) return alvo.scrollIntoView({block: "start"});
  const palco = document.querySelector("#provador .provador-palco");
  const a = alvo.getBoundingClientRect(), p = palco ? palco.getBoundingClientRect() : {height: 0};
  const moldura = parseFloat(getComputedStyle(livro).paddingTop) || 64;      // 64 px + safe-area
  const cobre = !!palco && p.height > 0 && getComputedStyle(palco).position === "sticky" && p.right > a.left && p.left < a.right;
  // Presa, a prévia vai de (moldura − 10) até (moldura − 10 + altura): o
  // mesmo `top: -10px` do CSS. Conta a altura dela, não onde ela está agora.
  const folga = (cobre ? moldura - 10 + p.height : moldura) + 8;
  livro.scrollBy({top: a.top - livro.getBoundingClientRect().top - folga, behavior: "smooth"});
}

// ------------------------------------------------------------ Montar sprites
// O servidor responde so o pedido (grupo + para quem). Cada carga leva um
// numero: resposta de um pedido antigo (trocou de estilo no meio) e jogada
// fora, para a tela nunca mostrar os cartoes de outro estilo.
function modularTexto(id, texto) { $(id).textContent = texto; }

// O resultado de um toque (anexar, trocar, apagar, desfazer, gabarito) aparece
// DENTRO do cartão tocado. O #modular-aviso mora no fim da lista (~230 px
// abaixo da tela depois de anexar, passada de 07/10), e o aviso flutuante da
// v54 cobria a galeria recém-anexada por 5 s (conferente). A frase fica no
// cartão até o próximo toque; o redesenho a mantém (`Modular.avisoCartao`).
function modularAvisar(texto, ruim = false, slot = Modular.slot) {
  modularTexto("modular-aviso", texto);
  Modular.avisoCartao = slot ? {slot: slot.id, texto, ruim} : null;
  for (const linha of document.querySelectorAll("#modular-slots .modular-cartao-aviso")) {
    const meu = !!slot && linha.closest(".modular-slot").dataset.slot === slot.id;
    linha.textContent = meu ? texto : "";
    linha.classList.toggle("oculto", !meu);
    linha.classList.toggle("ruim", meu && ruim);
  }
}

function modularCartaoAviso(slot) {
  const aviso = Modular.avisoCartao && Modular.avisoCartao.slot === slot.id ? Modular.avisoCartao : null;
  return el("p", {class: "modular-cartao-aviso" + (aviso ? "" : " oculto") + (aviso && aviso.ruim ? " ruim" : ""),
    role: "status"}, aviso ? aviso.texto : "");
}

// "Carinha" e feminino: "carinha neutra"; substantivos (fúria, pânico) ficam.
const MODULAR_FEMININO = {neutro: "neutra", focado: "focada", determinado: "determinada", animado: "animada",
  "eufórico": "eufórica", nervoso: "nervosa", morto: "morta", tonto: "tonta", confuso: "confusa",
  concentrado: "concentrada"};
function modularCarinha(nome) { return MODULAR_FEMININO[nome] || nome; }

function modularCarregando(sim) { $("modular-carregando").classList.toggle("oculto", !sim); }

async function modularCarregar() {
  const pedido = ++Modular.pedido;
  modularCarregando(true);
  try {
    const dados = await api(`/api/sprites/modulares?grupo=${encodeURIComponent(Modular.grupo)}` +
      `&alvo=${encodeURIComponent(Modular.alvo)}`);
    if (pedido !== Modular.pedido) return;      // chegou atrasada: ja e outro pedido
    // Igual ao que esta na tela (o cartao ja mudou com a resposta do anexo):
    // nao redesenha, para um toque no meio nao cair num botao trocado.
    const igual = Modular.dados && JSON.stringify(Modular.dados) === JSON.stringify(dados);
    Modular.dados = dados; Modular.alvo = dados.alvo;
    if (!igual) modularDesenhar();
  } catch (erro) {
    if (pedido === Modular.pedido) modularTexto("modular-aviso", "Não consegui abrir os lugares: " + erro.message);
  } finally {
    if (pedido === Modular.pedido) modularCarregando(false);
  }
}

function modularAlvos() {
  const seletor = $("modular-alvo"); seletor.replaceChildren();
  for (const alvo of Modular.dados.alvos || []) seletor.append(el("option", {value: alvo.chave}, alvo.rotulo));
  seletor.value = Modular.alvo;
  $("modular-alvo-caixa").classList.toggle("oculto", (Modular.dados.alvos || []).length < 2);
}

function modularProgresso() {
  const p = Modular.dados.progresso;
  const caixa = $("modular-progresso"); caixa.replaceChildren();
  if (!p) {
    const slots = Modular.dados.slots;
    caixa.append(el("span", {}, `${slots.filter((s) => s.situacao === "anexado").length} de ${slots.length} lugares com desenho aqui.`));
    return;
  }
  for (const [rotulo, [feitos, total]] of [["Lutador básico", p.basico], ["Rosto que reage", p.rosto],
                                           ["Classes com identidade", p.classes]]) {
    caixa.append(el("span", {class: "modular-contador" + (feitos >= total ? " completo" : "")},
      `${rotulo}: ${feitos} de ${total}`));
  }
}

function modularExpressoes() {
  const caixa = $("modular-expressoes"); caixa.replaceChildren();
  const lista = Modular.dados.expressoes || [];
  $("modular-expressoes-caixa").classList.toggle("oculto", !lista.length);
  const atual = lista.find((e) => e.id === Modular.expressao) || lista[0];
  if (!atual) return;
  // O rótulo e os botões falam igual: "Carinha: neutra" e "✓ neutra".
  modularTexto("modular-expressao-nome", modularCarinha(atual.nome));
  for (const expressao of lista) {
    if (!Modular.todas && !expressao.representante && expressao.id !== Modular.expressao) continue;
    const escolhida = expressao.id === Modular.expressao;
    const botao = el("button", {class: "acao modular-expressao" + (escolhida ? " escolhida" : ""), type: "button",
      "aria-pressed": escolhida ? "true" : "false"}, (escolhida ? "✓ " : "") + modularCarinha(expressao.nome));
    botao.addEventListener("click", () => { Modular.expressao = expressao.id; modularDesenhar(); });
    caixa.append(botao);
  }
  const todas = $("modular-todas");
  todas.textContent = Modular.todas ? "Mostrar só as 6 principais" : `Ver todas as ${lista.length}`;
  todas.setAttribute("aria-expanded", Modular.todas ? "true" : "false");
}

// "Olhos · neutra": o título do cartão fala igual ao botão da carinha.
function modularTitulo(slot) {
  const [peca, carinha] = String(slot.rotulo).split(" · ");
  return carinha ? `${peca} · ${modularCarinha(carinha)}` : peca;
}

// Com 2+ variantes, o Trocar/Apagar do topo mexe só na carinha da variante 1
// e o Apagar da galeria leva a variante inteira: os nomes dizem qual é qual
// (decisão do Adrian, 07/10: app-e-bot/atelie-dois-apagar).
function modularVarias(slot) {
  return Modular.grupo === "lutador" && (slot.variantes || []).length >= 2;
}

function modularCartao(slot) {
  const anexado = slot.situacao === "anexado";
  const situacao = anexado ? "Anexado" : slot.situacao === "herdando" ? "Herdando" : "Vazio";
  const varias = modularVarias(slot);
  const anexar = el("button", {class: "acao", type: "button"},
    anexado ? (varias ? "Trocar esta carinha" : "Trocar") : "Anexar");
  // `nova` desliga aqui: um "+ Nova variante" cancelado não vira o próximo Anexar.
  anexar.addEventListener("click", () => { Modular.slot = slot; Modular.nova = false; $("modular-arquivo").click(); });
  const botoes = el("div", {class: "botoes modular-acoes"}, anexar);
  if (slot.tem_anterior) {
    const desfazer = el("button", {class: "acao", type: "button"}, "Desfazer");
    desfazer.addEventListener("click", () => modularMutar(slot, "desfazer")); botoes.append(desfazer);
  }
  if (anexado) {
    const apagar = el("button", {class: "acao", type: "button"}, varias ? "Apagar esta carinha" : "Apagar");
    apagar.addEventListener("click", () => modularMutar(slot, "apagar")); botoes.append(apagar);
  }
  if (Modular.grupo === "lutador") {
    const nova = el("button", {class: "acao", type: "button"}, "+ Nova variante");
    nova.addEventListener("click", () => { Modular.slot = slot; Modular.nova = true; $("modular-arquivo").click(); });
    botoes.append(nova);
    const gabarito = el("button", {class: "acao modular-gabarito", type: "button"}, "Baixar gabarito");
    gabarito.addEventListener("click", () => modularGabarito(slot)); botoes.append(gabarito);
  }
  const miniatura = el("img", {class: "modular-mini oculto", alt: ""});
  if (anexado) modularMiniatura(slot, miniatura);
  return el("div", {class: "acao modular-slot " + slot.situacao, "data-slot": slot.id},
    el("div", {class: "modular-slot-topo"}, miniatura,
      el("div", {}, el("strong", {}, modularTitulo(slot)),
        el("span", {class: "modular-situacao"}, situacao + (slot.aviso ? ` · ${slot.aviso}` : "")))),
    botoes, modularCartaoAviso(slot), modularGaleria(slot));
}

// A galeria de variantes do cartão: cada desenho da coleção (o jogo sorteia
// um por lutador), com Apagar a variante inteira e o Desfazer da última.
function modularGaleria(slot) {
  const variantes = slot.variantes || [];
  if (Modular.grupo !== "lutador" || (variantes.length < 2 && !slot.variantes_apagadas)) return null;
  const grade = el("div", {class: "modular-variantes"});
  const semCarinha = new Set(slot.sem_carinha || []);
  variantes.forEach((variante, i) => {
    const img = el("img", {class: "modular-variante-img oculto", alt: `Variante ${i + 1}`});
    // Variante sem esta carinha: um quadrado com a frase, sem pedir imagem.
    const sem = semCarinha.has(variante)
      ? el("span", {class: "modular-variante-img modular-variante-sem"}, "sem esta carinha") : null;
    if (!sem) modularCartaoImagem(img,
      `/api/sprites/modulares/${encodeURIComponent(slot.id)}/imagem?variante=${variante}&v=${Modular.versao}`)
      .catch(() => {});
    const apagar = el("button", {class: "acao", type: "button", "aria-label": `Apagar a variante ${i + 1}`},
      "Apagar variante");
    apagar.addEventListener("click", () => modularApagarVariante(slot, variante, i + 1));
    grade.append(el("figure", {class: "modular-variante", "data-variante": variante}, sem || img,
      el("figcaption", {}, `Variante ${i + 1}`), apagar));
  });
  const caixa = el("div", {class: "modular-galeria"},
    el("p", {class: "fraco"}, variantes.length > 1
      ? `${variantes.length} variantes: cada lutador recebe uma por sorteio (o Provador fixa).`
      : "Uma variante só: o jogo usa esta em todos."), grade);
  // A frase do último Apagar/Desfazer fica AQUI, junto do toque (o aviso do
  // painel mora no fim da lista, longe da galeria).
  if (Modular.avisoGaleria && Modular.avisoGaleria.slot === slot.id)
    caixa.append(el("p", {class: "modular-galeria-aviso", role: "status"}, Modular.avisoGaleria.texto));
  if (slot.variantes_apagadas) {
    const desfazer = el("button", {class: "acao modular-desfazer-variante", type: "button"},
      "Desfazer: trazer a variante apagada");
    desfazer.addEventListener("click", () => modularDesfazerVariante(slot));
    caixa.append(desfazer);
  }
  return caixa;
}

async function modularVariantePost(slot, caminho, falhou) {
  try {
    const resposta = await api(`/api/sprites/modulares/${encodeURIComponent(slot.id)}/variante/${caminho}`,
      {method: "POST"});
    Modular.avisoGaleria = {slot: slot.id, texto: resposta.mensagem};
    modularAvisar(resposta.mensagem, false, null);     // a frase já fica junto da galeria
    modularAplicar(resposta);
  } catch (erro) {
    Modular.avisoGaleria = {slot: slot.id, texto: falhou + erro.message};
    modularAvisar(falhou + erro.message, true, null);
    modularDesenhar();
  }
}

function modularApagarVariante(slot, variante, numero) {
  const peca = slot.rotulo.split(" · ")[0].toLowerCase();
  if (!confirm(`Apagar a variante ${numero} de ${peca} inteira (todas as carinhas dela)? ` +
               "Quem a usava fixa volta ao sorteio. Dá para voltar com Desfazer.")) return;
  return modularVariantePost(slot, `${variante}/apagar`, "Não deu para apagar: ");
}

function modularDesfazerVariante(slot) { return modularVariantePost(slot, "desfazer", "Não deu: "); }

// As imagens dos cartões (miniatura e galeria) valem por desenho da lista: a
// lista é redesenhada duas vezes seguidas (a resposta do anexo e a carga
// completa), e com uma chave por lugar a resposta atrasada do 1º desenho
// revogava a imagem do 2º (medido em 06/10: 4 de 5 variantes em branco).
// Agora a URL só nasce se a <img> ainda está na tela, e cai no redesenho.
const CartaoUrls = [];
function modularCartaoUrlsLimpar() { CartaoUrls.splice(0).forEach((url) => URL.revokeObjectURL(url)); }

async function modularCartaoImagem(img, caminho) {
  const token = localStorage.getItem(TOKEN);
  const resposta = await fetch(caminho, {headers: token ? {Authorization: `Bearer ${token}`} : {}});
  if (!resposta.ok) throw new Error("não consegui abrir a imagem");
  const blob = await resposta.blob();
  if (!img.isConnected) return;
  const url = URL.createObjectURL(blob);
  CartaoUrls.push(url);
  img.src = url; img.classList.remove("oculto");
}

async function modularMiniatura(slot, img) {
  // A miniatura e a previa do proprio lugar: so ele, sem as outras pecas.
  try {
    await modularCartaoImagem(img, `/api/sprites/modulares/${encodeURIComponent(slot.id)}/imagem?v=${Modular.versao}`);
  } catch (_) { img.classList.add("oculto"); }
}

function modularDesenhar() {
  modularCartaoUrlsLimpar();
  modularAlvos();
  modularProgresso();
  const lutador = Modular.grupo === "lutador";
  $("modular-ver-godot").classList.toggle("oculto", !lutador || !Modular.dados.godot_previa);
  $("modular-previa-caixa").classList.toggle("oculto", !lutador);
  if (lutador) modularExpressoes(); else $("modular-expressoes-caixa").classList.add("oculto");
  const folha = Modular.folhas[Modular.alvo];
  $("modular-folha").classList.toggle("oculto", !lutador || !folha);
  if (lutador && folha) $("modular-folha").src = folha;
  const lista = $("modular-slots"); lista.replaceChildren();
  const slots = Modular.dados.slots.filter((slot) => !lutador || !slot.estado || slot.estado === "base" ||
    slot.estado === Modular.expressao);
  for (const slot of slots) lista.append(modularCartao(slot));
  recortadorDestinos();
  if (lutador) modularPrevia();
}

// "Mandar para" em DOIS passos (conferente, 07/10: era uma lista só de 83
// opções que abria em "Sombra"): primeiro a peça (6 no lutador), depois a
// carinha dela (6 principais + "Outras"). A tela abre no lugar mais
// provável: o que o nome do arquivo diz ("olhos_furia.png"), senão o último
// usado, senão os Olhos na carinha que o painel mostra.
const RECORTADOR_ULTIMO = "painel.recortador.destino";

function recortadorPecaDe(slot) { return slot.rotulo.split(" · ")[0]; }

function recortadorSlots() { return Modular.dados ? Modular.dados.slots.filter((s) => s.parte) : []; }

function recortadorDestinoTexto(slot) {
  const carinha = slot.rotulo.split(" · ")[1];
  return carinha ? modularCarinha(carinha) : recortadorPecaDe(slot);
}


// Escolhe a peça e preenche as carinhas dela; `preferido` é o id do lugar.
function recortadorEscolher(preferido = "") {
  const slots = recortadorSlots();
  const pecaSel = $("recortador-peca"), seletor = $("recortador-destino");
  const alvo = slots.find((s) => s.id === preferido);
  const peca = alvo ? recortadorPecaDe(alvo) : pecaSel.value;
  if ([...pecaSel.options].some((o) => o.value === peca)) pecaSel.value = peca;
  // As carinhas na ordem dos botões do painel (neutra, fúria, animada…).
  const ordem = (Modular.dados.expressoes || []).map((e) => e.id);
  const posicao = (s) => { const i = ordem.indexOf(s.estado); return i < 0 ? -1 : i; };
  const daPeca = slots.filter((s) => recortadorPecaDe(s) === pecaSel.value).sort((a, b) => posicao(a) - posicao(b));
  const antes = alvo ? alvo.estado : (slots.find((s) => s.id === seletor.value) || {}).estado;
  seletor.replaceChildren();
  const principais = new Set((Modular.dados.expressoes || []).filter((e) => e.representante).map((e) => e.id));
  const comCarinha = daPeca.filter((s) => s.estado && s.estado !== "base");
  if (comCarinha.length > 6) {
    const cima = el("optgroup", {label: "Principais"}), baixo = el("optgroup", {label: "Outras carinhas"});
    for (const slot of daPeca) (principais.has(slot.estado) ? cima : baixo)
      .append(el("option", {value: slot.id, "data-parte": slot.parte}, recortadorDestinoTexto(slot)));
    seletor.append(cima, baixo);
  } else {
    for (const slot of daPeca) seletor.append(el("option", {value: slot.id, "data-parte": slot.parte}, recortadorDestinoTexto(slot)));
  }
  // A carinha: a do lugar pedido, senão a mesma de antes (olhos·fúria → boca·fúria),
  // senão a que o painel mostra, senão a neutra.
  const carinha = [antes, Modular.expressao, "neutro"].find((e) => e && daPeca.some((s) => s.estado === e));
  const escolhido = daPeca.find((s) => s.estado === carinha) || daPeca[0];
  if (escolhido) seletor.value = escolhido.id;
  $("recortador-carinha-caixa").classList.toggle("oculto", daPeca.length < 2);
  recortadorOlhosCaixa();
}

function recortadorDestinos() {
  const pecaSel = $("recortador-peca");
  if (!pecaSel || !Modular.dados) return;
  const primeira = !pecaSel.options.length;
  const antes = $("recortador-destino").value;
  pecaSel.replaceChildren();
  for (const peca of new Set(recortadorSlots().map(recortadorPecaDe))) pecaSel.append(el("option", {value: peca}, peca));
  const slots = recortadorSlots();
  const ultimo = localStorage.getItem(RECORTADOR_ULTIMO) || "";
  const olhos = slots.find((s) => s.parte === "olhos" && s.estado === Modular.expressao) || slots.find((s) => s.parte === "olhos");
  const preferido = [antes, ultimo, olhos && olhos.id].find((id) => id && slots.some((s) => s.id === id)) || "";
  recortadorEscolher(preferido);
  // A junção segue o destino: abre em "pares de olhos" com os Olhos, e trocar
  // o grupo (Lutador → Habilidades) volta ao médio e recorta de novo (v54:
  // ficava em pares e o "Refazer" recortava como olhos). Só quando o destino
  // muda de lado (olhos / não olhos): um redesenho depois de mandar não mexe
  // na junção que ele escolheu à mão.
  if (primeira || (recortadorParte() === "olhos") !== Recortador.destinoOlhos) recortadorTrocouDestino(!primeira);
  // O modo do par de olhos abre na resposta do Adrian (Grimório), até ele mexer.
  if (!Recortador.olhosMexeu) recortadorOlhosPadrao();
}

function recortadorOlhosPadrao() {
  $("recortador-olhos").value = (Modular.dados && Modular.dados.recortador_olhos) || "separar";
}

// O nome do arquivo diz o destino ("olhos-furia.png", "boca_morta.png"): a
// peça e, se houver, a carinha. Sem acento, sem caixa e por PALAVRA inteira
// (v54 casava pedaço: "surface" virava rosto por "face", "dorso" virava dor).
// A primeira palavra que é peça manda ("sobrancelha_olho" é sobrancelha); a
// carinha vale nos dois gêneros ("animada", "morta"). Nome que só diz a peça
// mantém a carinha que está na tela ("olhos.png" em Boca · fúria → Olhos · fúria).
const RECORTADOR_NOMES = {
  olhos: ["olho", "olhos", "eye", "eyes"],
  sobrancelhas: ["sobrancelha", "sobrancelhas", "sombrancelha", "sombrancelhas", "brow", "brows", "eyebrow", "eyebrows"],
  boca: ["boca", "bocas", "mouth", "lip", "lips", "labio", "labios"],
  detalhe_rosto: ["detalhe", "detalhes", "rosto", "bochecha", "bochechas", "blush", "lagrima", "lagrimas", "suor", "face"],
  sombra: ["sombra", "shadow"],
  pele: ["pele", "corpo", "body", "skin"]};

function recortadorPalavras(nome) {
  return atelieSemAcento(String(nome).replace(/\.[a-z0-9]+$/i, "")).split(/[^a-z0-9]+/).filter(Boolean);
}

// As formas de uma carinha: o id, o nome sem acento e o outro gênero
// ("animado" ↔ "animada").
function recortadorFormas(expressao) {
  const formas = new Set([expressao.id, atelieSemAcento(expressao.nome), atelieSemAcento(modularCarinha(expressao.nome))]);
  for (const f of [...formas]) {
    if (f.endsWith("o")) formas.add(f.slice(0, -1) + "a");
    if (f.endsWith("a")) formas.add(f.slice(0, -1) + "o");
  }
  return formas;
}

function recortadorPeloNome(nome) {
  const palavras = recortadorPalavras(nome);
  let parte = "";
  for (const palavra of palavras) {
    parte = Object.keys(RECORTADOR_NOMES).find((p) => RECORTADOR_NOMES[p].includes(palavra)) || "";
    if (parte) break;
  }
  if (!parte) return "";
  const slots = recortadorSlots().filter((s) => s.parte === parte);
  if (!slots.length) return "";
  const carinha = (Modular.dados.expressoes || []).find((e) => {
    const formas = recortadorFormas(e);
    return palavras.some((p) => formas.has(p)) && slots.some((s) => s.estado === e.id);
  });
  const naTela = (recortadorSlots().find((s) => s.id === $("recortador-destino").value) || {}).estado;
  const escolhido = [carinha && carinha.id, naTela, Modular.expressao, "neutro"]
    .map((estado) => estado && slots.find((s) => s.estado === estado)).find(Boolean);
  // Sem nenhuma dessas carinhas, a primeira na ordem dos botões (a mesma do seletor).
  const ordem = (Modular.dados.expressoes || []).map((e) => e.id);
  const primeira = slots.slice().sort((x, y) => ordem.indexOf(x.estado) - ordem.indexOf(y.estado))[0];
  return (escolhido || primeira).id;
}

function atelieSemAcento(texto) {
  return String(texto).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function recortadorParte() {
  const opcao = $("recortador-destino").selectedOptions[0];
  return opcao ? opcao.dataset.parte : "";
}

function recortadorOlhosCaixa() { $("recortador-olhos-caixa").classList.toggle("oculto", recortadorParte() !== "olhos"); }

// Destino Olhos junta os olhos em PARES (a IA desenha o par lado a lado);
// saiu dos olhos, volta ao médio. Com folha na tela, recorta de novo.
function recortadorTrocouDestino(recortar = true) {
  recortadorOlhosCaixa();
  const olhos = recortadorParte() === "olhos", juncao = $("recortador-juncao");
  Recortador.destinoOlhos = olhos;
  const antes = juncao.value;
  if (olhos && antes !== "pares") juncao.value = "pares";
  else if (!olhos && antes === "pares") juncao.value = "medio";
  if (recortar && juncao.value !== antes && Recortador.arquivo) recortadorEnviar();
}

// Folha nova: o destino pelo nome do arquivo (se ele disser), o modo do par
// de olhos volta ao padrão (conferente, 07/10: o "girar" de uma folha ficava
// valendo para a seguinte) e só então recorta.
function recortadorFolhaNova() {
  Recortador.arquivo = $("recortador-arquivo").files[0] || null;
  if (!Recortador.arquivo) return;
  Recortador.olhosMexeu = false;
  recortadorOlhosPadrao();
  const pelo = recortadorPeloNome(Recortador.arquivo.name);
  if (pelo) recortadorEscolher(pelo);
  recortadorTrocouDestino(false);
  recortadorEnviar();
}

function recortadorNome(recorte, i) {
  const tipo = recorte.tipo === "par" ? " · par de olhos" : recorte.tipo === "um" ? " · um olho só"
    : recorte.tipo === "sobra" ? " · pedacinho solto" : "";
  return `Recorte ${i + 1} · ${recorte.tamanho[0]}×${recorte.tamanho[1]} px${tipo}`;
}

// O pedacinho solto (brilho, faísca perto de um desenho; 07/10) vem
// desmarcado: ele só vai se for tocado.
function recortadorMarcadoDeInicio(recorte) { return recorte.tipo !== "sobra"; }

function recortadorResumo(dados) {
  const sobras = dados.recortes.filter((r) => r.tipo === "sobra").length;
  const n = dados.recortes.length - sobras, pares = dados.recortes.filter((r) => r.tipo === "par").length;
  const soltos = dados.recortes.filter((r) => r.tipo === "um").length;
  const extra = sobras ? ` · ${sobras === 1 ? "1 pedacinho solto (desmarcado)" : `${sobras} pedacinhos soltos (desmarcados)`}` : "";
  if (dados.juncao === "pares") {
    const partes = [];
    if (pares) partes.push(pares === 1 ? "1 par de olhos" : `${pares} pares de olhos`);
    if (soltos) partes.push(soltos === 1 ? "1 olho sozinho" : `${soltos} olhos sozinhos`);
    return `Fundo ${dados.fundo} · ${partes.join(" e ") || "nenhum olho achado"}${extra}`;
  }
  return `Fundo ${dados.fundo} · ${n === 1 ? "1 recorte" : `${n} recortes`}${extra}`;
}

// O botão diz quantos vão ("Mandar 3 selecionados"): o pedacinho solto vem
// desmarcado e a conta mostra isso antes do toque.
function recortadorContar() {
  const n = Recortador.dados ? Recortador.selecionados.size : 0;
  $("recortador-mandar").textContent = !n ? "Mandar selecionados"
    : n === 1 ? "Mandar 1 selecionado" : `Mandar ${n} selecionados`;
}

// Esquece a folha da tela: uma recusa não deixa a anterior pronta para mandar.
function recortadorEsquecer() {
  Recortador.dados = null; Recortador.selecionados = new Set();
  recortadorLimparUrls();
  $("recortador-lista").replaceChildren();
  $("recortador-limpa").removeAttribute("src");
  $("recortador-fundo").textContent = "";
  $("recortador-folha-caixa").classList.add("oculto");
  recortadorContar();
}

async function recortadorDesenhar(dados, pedido) {
  recortadorLimparUrls();
  const lista = $("recortador-lista"); lista.replaceChildren();
  const folha = await recortadorBlob(dados.folha || dados.limpa);
  if (pedido !== Recortador.pedido) return;
  $("recortador-limpa").src = folha;
  $("recortador-folha-caixa").classList.remove("oculto");
  $("recortador-fundo").textContent = recortadorResumo(dados);
  for (const [i, recorte] of dados.recortes.entries()) {
    const marcado = Recortador.selecionados.has(recorte.id);
    const nome = recortadorNome(recorte, i);
    const caixa = el("label", {class: "recortador-item" + (marcado ? " escolhido" : "")});
    const marcar = el("input", {type: "checkbox", "data-recorte": recorte.id, "aria-label": nome}); marcar.checked = marcado;
    marcar.addEventListener("change", () => {
      if (marcar.checked) Recortador.selecionados.add(recorte.id); else Recortador.selecionados.delete(recorte.id);
      caixa.classList.toggle("escolhido", marcar.checked);
      recortadorContar();
    });
    const imagem = el("img", {alt: nome});
    const url = await recortadorBlob(recorte.url);
    if (pedido !== Recortador.pedido) return;
    imagem.src = url;
    caixa.append(marcar, imagem, el("span", {}, nome));
    lista.append(caixa);
  }
}

async function recortadorEnviar() {
  if (!Recortador.arquivo) return;
  const pedido = ++Recortador.pedido;
  $("recortador-aviso").textContent = "recortando no PC…";
  $("recortador-mandar").disabled = true;
  const dados = new FormData(); dados.append("imagem", Recortador.arquivo);
  dados.append("opcoes", JSON.stringify({juncao: $("recortador-juncao").value}));
  try {
    const resposta = await api("/api/sprites/recortar", {method: "POST", body: dados});
    if (pedido !== Recortador.pedido) return;
    Recortador.dados = resposta;
    Recortador.selecionados = new Set(resposta.recortes.filter(recortadorMarcadoDeInicio).map((r) => r.id));
    recortadorContar();
    await recortadorDesenhar(resposta, pedido);
    if (pedido !== Recortador.pedido) return;
    $("recortador-aviso").textContent = resposta.avisos.join(" · ") || "Toque nos recortes que quer mandar.";
  } catch (erro) {
    if (pedido !== Recortador.pedido) return;
    recortadorEsquecer();
    $("recortador-aviso").textContent = "Não deu: " + erro.message;
  } finally {
    if (pedido === Recortador.pedido) $("recortador-mandar").disabled = false;
  }
}

async function recortadorMandar() {
  const destino = $("recortador-destino").value;
  const escolhidos = Recortador.dados?.recortes.filter((r) => Recortador.selecionados.has(r.id)) || [];
  if (!destino || !escolhidos.length) return $("recortador-aviso").textContent = "Escolha pelo menos um recorte e uma peça.";
  $("recortador-mandar").disabled = true;
  // O encaixe no gabarito é do DESTINO, feito agora pelo PC (06/10: era feito
  // ao subir a folha, com a peça do seletor naquela hora, e olhos caíram na
  // zona da sombra). Nos olhos vai junto o modo do par.
  const consulta = `?destino=${encodeURIComponent(destino)}` +
    (recortadorParte() === "olhos" ? `&olhos=${encodeURIComponent($("recortador-olhos").value)}` : "");
  try {
    for (const recorte of escolhidos) {
      const token = localStorage.getItem(TOKEN);
      const resposta = await fetch(recorte.url + consulta, {headers: token ? {Authorization: `Bearer ${token}`} : {}});
      if (!resposta.ok) throw new Error("não consegui encaixar o recorte");
      const dados = new FormData(); dados.append("imagem", await resposta.blob(), `recorte-${recorte.id + 1}.png`);
      dados.append("opcoes", JSON.stringify({nova: true}));
      // nova=1: o guarda-roupa cria a proxima variante (vNN) sem trocar a arte base.
      await api(`/api/sprites/modulares/${encodeURIComponent(destino)}/anexar?nova=1`, {method: "POST", body: dados});
    }
    localStorage.setItem(RECORTADOR_ULTIMO, destino);
    const slotDestino = Modular.dados.slots.find((s) => s.id === destino);
    const rotulo = slotDestino ? modularTitulo(slotDestino).toLowerCase() : "a peça";
    $("recortador-aviso").textContent = (escolhidos.length === 1 ? "1 recorte virou variante nova"
      : `${escolhidos.length} recortes viraram variantes novas`) + ` de ${rotulo}. Veja na galeria do cartão, acima.`;
    // O cartão de destino fica à vista: a carinha do painel passa a ser a dele.
    const slot = Modular.dados.slots.find((s) => s.id === destino);
    if (slot && slot.estado && slot.estado !== "base") Modular.expressao = slot.estado;
    Modular.versao++;
    modularCarregar();
  } catch (erro) { $("recortador-aviso").textContent = "Não deu: " + erro.message; }
  finally { $("recortador-mandar").disabled = false; }
}

async function modularPrevia() {
  const pedido = ++Modular.pedidoPrevia;
  const token = localStorage.getItem(TOKEN);
  try {
    const resposta = await fetch(`/api/sprites/modulares/previa?alvo=${encodeURIComponent(Modular.alvo)}` +
      `&expressao=${encodeURIComponent(Modular.expressao)}&v=${Modular.versao}`,
      {headers: token ? {Authorization: `Bearer ${token}`} : {}});
    if (!resposta.ok) throw new Error("sem prévia");
    const pecas = +(resposta.headers.get("X-Previa-Pecas") || 0);
    const blob = await resposta.blob();
    if (pedido !== Modular.pedidoPrevia) return;
    $("modular-previa").src = modularUrl("previa", blob);
    $("modular-previa").classList.toggle("oculto", !pecas);
    $("modular-hoje").classList.toggle("oculto", !!pecas);
    modularTexto("modular-previa-legenda", pecas
      ? `Prévia rápida · carinha ${modularCarinha($("modular-expressao-nome").textContent)}`
      : "Nada anexado aqui ainda: o jogo ainda usa o desenho de hoje.");
  } catch (_) {
    if (pedido !== Modular.pedidoPrevia) return;
    $("modular-previa").classList.add("oculto"); $("modular-hoje").classList.remove("oculto");
    modularTexto("modular-previa-legenda", "Não consegui montar a prévia; o jogo ainda usa o desenho de hoje.");
  }
}

async function modularGabarito(slot) {
  try {
    const url = await atelieBlob(`/api/sprites/modulares/${encodeURIComponent(slot.id)}/gabarito`);
    const a = el("a", {href: url, download: `gabarito_${slot.parte}.png`});
    document.body.append(a); a.click(); a.remove();
    modularAvisar(`Gabarito de ${modularTitulo(slot).toLowerCase()} baixado. Desenhe por cima e anexe aqui.`, false, slot);
  } catch (erro) { modularAvisar("Não consegui baixar o gabarito: " + erro.message, true, slot); }
}

// Depois de anexar, apagar ou desfazer, o servidor devolve o lugar como
// ficou: o cartao muda na hora, e a lista completa vem logo atras.
function modularAplicar(resposta) {
  Modular.versao++;
  Modular.folhas = {};          // a folha do Godot ficou velha: "Ver no Godot" monta outra
  const slot = resposta.slot;
  if (slot) Modular.dados.slots = Modular.dados.slots.map((s) => s.id === slot.id ? slot : s);
  if (resposta.progresso && Modular.dados.progresso) Modular.dados.progresso = resposta.progresso;
  modularDesenhar();
  modularCarregar();
}

async function modularMutar(slot, acao) {
  if (acao === "apagar" && !confirm(modularVarias(slot)
    ? `Apagar só esta carinha (${modularTitulo(slot).toLowerCase()}) da variante 1? As outras variantes ficam. Dá para voltar com Desfazer.`
    : `Apagar o desenho de ${modularTitulo(slot).toLowerCase()}? Dá para voltar com Desfazer.`)) return;
  try {
    const resposta = await api(`/api/sprites/modulares/${encodeURIComponent(slot.id)}/${acao}`, {method: "POST"});
    const novo = resposta.slot || {};
    modularAvisar(acao === "desfazer" ? "Pronto: voltou a versão anterior."
      : novo.situacao === "herdando" ? `Desenho apagado; ${novo.aviso}. Desfazer traz de volta.`
      : "Desenho apagado; o jogo volta ao desenho de hoje. Desfazer traz de volta.", false, slot);
    modularAplicar(resposta);
  } catch (erro) { modularAvisar("Não deu: " + erro.message, true, slot); }
}

async function modularVerGodot() {
  if (!Modular.dados || !Modular.dados.godot_previa) return;
  const alvo = Modular.alvo;
  const botao = $("modular-ver-godot"); botao.disabled = true;
  modularTexto("modular-godot-aviso", "montando no Godot…");
  try {
    // O estilo trocado no meio: a folha continua sendo montada (fica guardada
    // para quando ele voltar), mas o aviso é do estilo que está na tela.
    const blob = await godotEsperar(`/api/sprites/modulares/previa?godot=1&alvo=${encodeURIComponent(alvo)}`,
      (texto) => { if (Modular.alvo === alvo) modularTexto("modular-godot-aviso", texto); }, () => true);
    if (!blob) return;                      // fechou o Ateliê: a espera foi cancelada
    const url = modularUrl("folha:" + alvo, blob);
    Modular.folhas[alvo] = url;
    if (Modular.alvo === alvo) {
      $("modular-folha").src = url; $("modular-folha").classList.remove("oculto");
      modularTexto("modular-godot-aviso", "Folha montada no Godot: as seis carinhas como vão aparecer na luta.");
      await $("modular-folha").decode().catch(() => {});
      if (Modular.alvo === alvo) atelieRolarAte($("modular-folha"));
    }
  } catch (erro) { if (Modular.alvo === alvo) modularTexto("modular-godot-aviso", "Não deu para ver no Godot: " + erro.message); }
  finally { botao.disabled = false; }
}

// "+ Nova variante" aceita VÁRIOS arquivos de uma vez: cada um vira a próxima
// variante (antes só o primeiro ia; o seletor já era `multiple`).
async function modularAnexarVariantes(arquivos) {
  const slot = Modular.slot;
  Modular.nova = false;
  let feitas = 0, resposta = null;
  try {
    for (const arquivo of arquivos) {
      modularAvisar(`enviando a variante ${feitas + 1} de ${arquivos.length}…`, false, slot);
      const dados = new FormData(); dados.append("imagem", arquivo);
      dados.append("opcoes", JSON.stringify({nova: true}));
      resposta = await api(`/api/sprites/modulares/${encodeURIComponent(slot.id)}/anexar`, {method: "POST", body: dados});
      feitas++;
    }
    modularAvisar(feitas === 1 ? "Variante nova anexada." : `${feitas} variantes novas anexadas.`);
  } catch (erro) {
    modularAvisar((feitas ? `${feitas} de ${arquivos.length} anexadas; ` : "") +
      "não deu para anexar: " + erro.message, true);
  }
  if (resposta) modularAplicar(resposta);
}

async function modularAnexar(arquivoRecebido = null) {
  const lista = arquivoRecebido ? [arquivoRecebido] : [...$("modular-arquivo").files];
  const arquivo = lista[0];
  $("modular-arquivo").value = "";
  const slot = Modular.slot;
  if (!arquivo || !slot) return;
  if (Modular.nova) return modularAnexarVariantes(lista);
  // Vários arquivos num lugar vazio de lutador: cada um vira uma variante
  // (o seletor é `multiple`; antes só o primeiro ia e o resto sumia calado).
  if (lista.length > 1 && Modular.grupo === "lutador" && slot.situacao !== "anexado")
    return modularAnexarVariantes(lista);
  if (lista.length > 1)
    return modularAvisar(slot.situacao === "anexado"
      ? "Trocar usa um arquivo só. Para mandar vários de uma vez, use “+ Nova variante”."
      : "Este lugar recebe um desenho só: escolha um arquivo.", true);
  const trocar = slot.situacao === "anexado" && !Modular.nova;
  if (trocar && !confirm(modularVarias(slot)
    ? `Trocar só esta carinha (${modularTitulo(slot).toLowerCase()}) da variante 1 pelo desenho novo? As outras variantes ficam. (Desfazer volta o antigo.)`
    : `Já há um desenho em ${modularTitulo(slot).toLowerCase()}. Trocar pelo novo? (Desfazer volta o antigo.)`)) return;
  const dados = new FormData(); dados.append("imagem", arquivo);
  dados.append("opcoes", JSON.stringify({substituir: trocar, nova: Modular.nova}));
  modularAvisar("enviando o desenho…");
  try {
    const resposta = await api(`/api/sprites/modulares/${encodeURIComponent(slot.id)}/anexar`, {method: "POST", body: dados});
    modularAvisar((trocar ? "Desenho trocado." : "Desenho anexado.") +
      (resposta.avisos?.length ? " " + resposta.avisos.join(" · ") : ""));
    Modular.nova = false; modularAplicar(resposta);
  } catch (erro) { modularAvisar("Não deu para anexar: " + erro.message, true); }
}

$("atelie-modo-montar").addEventListener("click", () => atelieTrocarModo("montar"));
$("atelie-modo-provador").addEventListener("click", () => atelieTrocarModo("provador"));
$("atelie-sujeito").addEventListener("change", () => { Atelie.sujeito = $("atelie-sujeito").value; atelieCarregar(); });
$("atelie-nome").addEventListener("change", () => atelieCarregar());
$("atelie-arquivo").addEventListener("change", () => { Atelie.arquivo = $("atelie-arquivo").files[0] || null; atelieEnviar(); });
$("recortador-arquivo").addEventListener("change", () => recortadorFolhaNova());
$("recortador-refazer").addEventListener("click", () => recortadorEnviar());
$("recortador-peca").addEventListener("change", () => { recortadorEscolher(); recortadorTrocouDestino(); });
$("recortador-destino").addEventListener("change", () => recortadorTrocouDestino());
$("recortador-olhos").addEventListener("change", () => { Recortador.olhosMexeu = true; });
$("recortador-mandar").addEventListener("click", () => recortadorMandar());
$("atelie-refazer").addEventListener("click", () => atelieEnviar());
$("atelie-salvar").addEventListener("click", () => atelieEnviar(true));
$("atelie-descartar").addEventListener("click", () => {
  Atelie.arquivo = null; $("atelie-arquivo").value = ""; atelieLimparUrls();
  $("atelie-previas").replaceChildren(); $("atelie-editor").classList.add("oculto");
});
$("modular-grupo").addEventListener("change", () => {
  Modular.grupo = $("modular-grupo").value; Modular.alvo = ""; Modular.slot = null; Modular.avisoGaleria = null; Modular.avisoCartao = null;
  modularTexto("modular-aviso", "");   // o aviso era do grupo anterior
  $("modular-slots").replaceChildren(); modularCarregar();
});
$("modular-alvo").addEventListener("change", () => {
  Modular.alvo = $("modular-alvo").value; Modular.slot = null; Modular.avisoGaleria = null; Modular.avisoCartao = null;
  $("modular-slots").replaceChildren(); modularCarregar();
});
// Tocar na folha abre em tela cheia, com zoom do proprio navegador.
$("modular-folha").addEventListener("click", () => { if ($("modular-folha").src) window.open($("modular-folha").src, "_blank"); });
$("modular-todas").addEventListener("click", () => { Modular.todas = !Modular.todas; modularExpressoes(); });
$("modular-ver-godot").addEventListener("click", () => modularVerGodot());
// O "change" entrega um Event: o arquivo sai do proprio campo.
$("modular-arquivo").addEventListener("change", () => modularAnexar());
$("sprites-modulares").addEventListener("dragover", (evento) => evento.preventDefault());
$("sprites-modulares").addEventListener("drop", (evento) => {
  evento.preventDefault();
  const arquivo = evento.dataTransfer.files[0];
  if (!Modular.slot) return modularTexto("modular-aviso", "Toque primeiro em Anexar no lugar que vai receber o desenho.");
  modularAnexar(arquivo);
});
