"use strict";
// A assembleia e uma consulta: o cartao deixa isso claro e o Grimorio recebe
// somente a recomendacao com a ata quando a segunda rodada fecha.
const ASSEMBLEIA_IAS = ["gemini", "chatgpt", "deepseek", "grok"];

function assembleiasLinha(a) {
  const ata = a.ata || {};
  const caixa = el("details", {class: "cartao"},
    el("summary", {}, `${a.situacao === "fechada" ? "✓" : "…"} ${a.pergunta}`));
  const corpo = el("div", {class: "corpo"},
    el("p", {class: "fraco"}, `Rodada: ${a.situacao.replace("_", " ")}`));
  for (const [rodada, nome] of [[a.rodada_1, "Rodada 1"], [a.rodada_2, "Rodada 2"]]) {
    if (!rodada) continue;
    const lista = el("div", {}, el("h3", {}, nome));
    for (const ia of a.participantes || []) {
      const r = (rodada.respostas || {})[ia] || {};
      const texto = r.situacao === "respondeu"
        ? `${r.voto || "sem voto"}: ${r.por_que || "sem justificativa"}${r.mudou ? " (mudou de voto)" : ""}`
        : (r.situacao || "aguardando");
      lista.append(el("div", {class: "fraco"}, `${ia}: ${texto}`));
    }
    corpo.append(lista);
  }
  if (a.ata) corpo.append(el("p", {}, `Ata: ${ata.consenso}; contagem ${JSON.stringify(ata.contagem || {})}`));
  if (a.decisao_id) corpo.append(el("p", {}, `Nó no Grimório: ${a.decisao_id}`));
  caixa.append(corpo);
  return caixa;
}

async function assembleiasMostrar() {
  const alvo = $("assembleias-lista");
  try {
    const dados = await api("/api/assembleias");
    alvo.replaceChildren(...(dados.assembleias || []).map(assembleiasLinha));
    if (!(dados.assembleias || []).length) alvo.append(el("div", {class: "fraco"}, "Nenhuma assembleia ainda."));
  } catch (err) {
    alvo.replaceChildren(el("div", {class: "erro"}, "Não consegui carregar: " + err.message));
  }
}

function assembleiaPreparar() {
  const participantes = $("assembleia-participantes");
  participantes.replaceChildren(...ASSEMBLEIA_IAS.map((ia) => {
    const entrada = el("input", {type: "checkbox", value: ia}); entrada.checked = true;
    return el("label", {class: "acao"}, entrada, " " + ia);
  }));
  $("assembleia-enviar").addEventListener("click", async () => {
    const pergunta = $("assembleia-pergunta").value.trim();
    const contexto = $("assembleia-contexto").value.trim();
    const aviso = $("assembleia-aviso");
    if (!pergunta || contexto.length < 80) {
      aviso.textContent = "Escreva a pergunta e ao menos 80 caracteres sobre o que está em jogo.";
      aviso.className = "erro";
      return;
    }
    const opcoes = $("assembleia-opcoes").value.split("\n").map((x) => x.trim()).filter(Boolean);
    const selecionados = [...participantes.querySelectorAll("input:checked")].map((x) => x.value);
    try {
      const r = await api("/api/assembleia", {method: "POST", body: JSON.stringify({pergunta,
        contexto, opcoes, participantes: selecionados, projeto: "geral"})});
      aviso.className = "fraco";
      aviso.textContent = "Assembleia convocada (" + r.id + ").";
      $("assembleia-pergunta").value = ""; $("assembleia-opcoes").value = "";
    } catch (err) { aviso.className = "erro"; aviso.textContent = err.message; }
  });
}

document.addEventListener("DOMContentLoaded", assembleiaPreparar);
