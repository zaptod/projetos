"use strict";
// O Atelie nao conhece caminhos do PC: cada imagem da previa e buscada com o
// token, convertida em blob: e esquecida ao trocar de tentativa.
const Atelie = {catalogo: null, sujeito: "", slot: null, arquivo: null, urls: []};
const Modular = {dados: null, grupo: "lutador", alvo: "_", slot: null, expressao: "neutro"};

function atelieLimparUrls() {
  Atelie.urls.forEach((url) => URL.revokeObjectURL(url));
  Atelie.urls = [];
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

function atelieMostrar() { atelieCarregar(); }
function atelieParar() { atelieLimparUrls(); }

function modularAlvos() {
  const alvos = new Map();
  for (const slot of Modular.dados.slots) {
    if (slot.grupo === Modular.grupo) alvos.set(slot.alvo.chave, slot.alvo.rotulo);
  }
  const seletor = $("modular-alvo"); seletor.replaceChildren();
  for (const [chave, rotulo] of alvos) seletor.append(el("option", {value: chave}, rotulo));
  if (!alvos.has(Modular.alvo)) Modular.alvo = alvos.has("_") ? "_" : [...alvos][0]?.[0] || "_";
  seletor.value = Modular.alvo;
}

async function modularPrevia() {
  if (Modular.grupo !== "lutador") { $("modular-previa").classList.add("oculto"); return; }
  try {
    $("modular-previa").src = await atelieBlob(`/api/sprites/modulares/previa?alvo=${encodeURIComponent(Modular.alvo)}`);
    $("modular-previa").classList.remove("oculto");
  } catch (_) { $("modular-previa").classList.add("oculto"); }
}

function modularDesenhar() {
  modularAlvos();
  const lista = $("modular-slots"); lista.replaceChildren();
  const slots = Modular.dados.slots.filter((slot) => slot.grupo === Modular.grupo &&
    (slot.alvo.chave === Modular.alvo || (Modular.grupo === "lutador" && slot.alvo.chave === "_")) &&
    (!slot.estado || slot.estado === "base" || slot.estado === Modular.expressao));
  const anexados = slots.filter((slot) => slot.situacao === "anexado").length;
  $("modular-progresso").textContent = Modular.grupo === "lutador"
    ? `Lutador básico: ${anexados} de ${slots.length} peças prontas · Rosto que reage: escolha uma das 6 carinhas.`
    : `${anexados} de ${slots.length} lugares preenchidos.`;
  for (const slot of slots) {
    const texto = slot.situacao === "anexado" ? "Anexado" : slot.situacao === "herdando" ? "Herdando" : "Vazio";
    const botao = el("button", {class: "acao modular-slot", type: "button"},
      el("strong", {}, slot.rotulo), el("span", {class: "fraco"}, texto));
    botao.addEventListener("click", () => {
      Modular.slot = slot; $("modular-arquivo").click();
    });
    lista.append(botao);
  }
  const expressoes = $("modular-expressoes"); expressoes.replaceChildren();
  if (Modular.grupo === "lutador") for (const nome of ["neutro", "furia", "animado", "panico", "dor", "morto"]) {
    const botao = el("button", {class: "acao", type: "button"}, nome);
    botao.addEventListener("click", () => { Modular.expressao = nome; modularDesenhar(); }); expressoes.append(botao);
  }
  modularPrevia();
}

async function modularCarregar() {
  try {
    Modular.dados = await api(`/api/sprites/modulares?grupo=${encodeURIComponent(Modular.grupo)}`);
    modularDesenhar();
  } catch (erro) { $("modular-aviso").textContent = "não consegui abrir os lugares: " + erro.message; }
}

async function modularAnexar(arquivoRecebido = null) {
  const arquivo = arquivoRecebido || $("modular-arquivo").files[0]; if (!arquivo || !Modular.slot) return;
  const dados = new FormData(); dados.append("imagem", arquivo);
  dados.append("opcoes", JSON.stringify({substituir: Modular.slot.situacao === "anexado" &&
    confirm("Já há um desenho aqui. Trocar pelo novo?")}));
  try {
    const resposta = await api(`/api/sprites/modulares/${Modular.slot.id}/anexar`, {method: "POST", body: dados});
    $("modular-aviso").textContent = resposta.avisos?.join(" · ") || "Desenho colocado.";
    modularCarregar();
  } catch (erro) { $("modular-aviso").textContent = erro.message; }
  $("modular-arquivo").value = "";
}

$("atelie-sujeito").addEventListener("change", () => { Atelie.sujeito = $("atelie-sujeito").value; atelieCarregar(); });
$("atelie-nome").addEventListener("change", atelieCarregar);
$("atelie-arquivo").addEventListener("change", () => { Atelie.arquivo = $("atelie-arquivo").files[0] || null; atelieEnviar(); });
$("atelie-refazer").addEventListener("click", () => atelieEnviar());
$("atelie-salvar").addEventListener("click", () => atelieEnviar(true));
$("atelie-descartar").addEventListener("click", () => {
  Atelie.arquivo = null; $("atelie-arquivo").value = ""; atelieLimparUrls();
  $("atelie-previas").replaceChildren(); $("atelie-editor").classList.add("oculto");
});
$("modular-grupo").addEventListener("change", () => { Modular.grupo = $("modular-grupo").value; modularCarregar(); });
$("modular-alvo").addEventListener("change", () => { Modular.alvo = $("modular-alvo").value; modularDesenhar(); });
$("modular-arquivo").addEventListener("change", modularAnexar);
$("sprites-modulares").addEventListener("dragover", (evento) => evento.preventDefault());
$("sprites-modulares").addEventListener("drop", (evento) => {
  evento.preventDefault();
  const arquivo = evento.dataTransfer.files[0];
  if (!Modular.slot) return $("modular-aviso").textContent = "Toque primeiro no lugar que vai receber o desenho.";
  modularAnexar(arquivo);
});
