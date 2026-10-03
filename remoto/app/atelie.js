"use strict";
// O Atelie nao conhece caminhos do PC: cada imagem da previa e buscada com o
// token, convertida em blob: e esquecida ao trocar de tentativa.
const Atelie = {catalogo: null, sujeito: "", slot: null, arquivo: null, urls: []};

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

function atelieOpcoes(salvar = false) {
  return {sujeito: Atelie.sujeito, nome: $("atelie-nome").value.trim().toLowerCase(),
    slot: Atelie.slot.id, tolerancia: +$("atelie-tolerancia").value,
    modo: $("atelie-modo").value, colunas: +$("atelie-colunas").value,
    linhas: +$("atelie-linhas").value, espelhar: $("atelie-espelho").checked,
    salvar, arquivo: Atelie.arquivo && Atelie.arquivo.name};
}

async function atelieEnviar(salvar = false) {
  if (!Atelie.arquivo || !Atelie.slot) return;
  const aviso = $("atelie-aviso"); aviso.textContent = "processando no PC…";
  const dados = new FormData();
  dados.append("imagem", Atelie.arquivo);
  dados.append("opcoes", JSON.stringify(atelieOpcoes(salvar)));
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
  } catch (erro) { aviso.textContent = "falhou: " + erro.message; conexao(false, erro); }
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
  } catch (erro) { $("atelie-slots").textContent = "falhou: " + erro.message; conexao(false, erro); }
}

function atelieMostrar() { atelieCarregar(); }
function atelieParar() { atelieLimparUrls(); }

$("atelie-sujeito").addEventListener("change", () => { Atelie.sujeito = $("atelie-sujeito").value; atelieCarregar(); });
$("atelie-nome").addEventListener("change", atelieCarregar);
$("atelie-arquivo").addEventListener("change", () => { Atelie.arquivo = $("atelie-arquivo").files[0] || null; atelieEnviar(); });
$("atelie-refazer").addEventListener("click", () => atelieEnviar());
$("atelie-salvar").addEventListener("click", () => atelieEnviar(true));
$("atelie-descartar").addEventListener("click", () => {
  Atelie.arquivo = null; $("atelie-arquivo").value = ""; atelieLimparUrls();
  $("atelie-previas").replaceChildren(); $("atelie-editor").classList.add("oculto");
});
