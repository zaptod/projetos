"use strict";
// A Equipe e comando do servidor; a Oficina segue sendo a unica tela de log.
let equipeTimer = null;
let equipeSeloEm = 0;

async function equipeSelo() {
  if (Date.now() - equipeSeloEm < 60000) return;
  equipeSeloEm = Date.now();
  try {
    const dados = await api("/api/equipe");
    const obj = $("obj-agora"), n = (dados.pedidos_permissao || []).length;
    obj.classList.toggle("selo-contador", n > 0);
    if (n > 0) obj.dataset.pendentes = n > 9 ? "9+" : String(n);
    else delete obj.dataset.pendentes;
    obj.title = n ? `${n} permiss${n > 1 ? "oes" : "ao"} esperando voce` : "Agora";
  } catch (err) { /* a tela principal já mostra a falha de conexão */ }
}

function equipePedidoPermissao(t) {
  const p = t.pedido_permissao || {};
  // cartao em COLUNA: em linha, os botoes espremiam o texto a uma letra (03/10)
  const linha = el("div", {class: "equipe-cartao equipe-permissao"},
    el("div", {class: "equipe-titulo"}, `${t.cargo || "trabalhador"} pede: ${p.o_que || "permissão"}`),
    el("div", {class: "fraco"}, [p.por_que, p.alvo ? `alvo: ${p.alvo}` : ""].filter(Boolean).join(" · ")),
    el("div", {class: "fraco"}, t.titulo || t.id));
  const acoes = el("div", {class: "botoes"});
  if (p.decisao_id) {
    acoes.append(el("span", {class: "fraco"}, "Decida no Grimorio para retomar."));
    linha.append(acoes); return linha;
  }
  async function decidir(decisao, sempre = false) {
    try {
      await api(`/api/equipe/${encodeURIComponent(t.id)}/permissao`, {method: "POST",
        headers: {"Content-Type": "application/json"}, body: JSON.stringify({decisao, sempre})});
      equipeCarregar();
    } catch (err) { avisar(err.message, true); }
  }
  const permitir = el("button", {class: "acao primario", type: "button"}, "✅ Permitir");
  permitir.addEventListener("click", () => decidir("permitir"));
  const negar = el("button", {class: "acao", type: "button"}, "❌ Negar");
  negar.addEventListener("click", () => decidir("negar"));
  const sempre = el("button", {class: "acao", type: "button"}, "✅ Permitir sempre para este cargo");
  sempre.addEventListener("click", () => decidir("permitir", true));
  acoes.append(permitir, negar, sempre); linha.append(acoes);
  return linha;
}

// So os botoes que fazem sentido na situacao (antes eram os 5 em todos, 03/10).
const EQUIPE_ACOES = {
  rodando: ["ver", "renovar", "parar"], criado: ["ver", "parar"],
  terminou: ["ver", "corrigir", "aplicar"], parado: ["ver", "corrigir"],
  falhou: ["ver", "corrigir"], aguardando_permissao: ["ver"],
};
const EQUIPE_ROTULO = {ver: "Ver ao vivo", renovar: "Renovar", parar: "Parar",
                       corrigir: "Corrigir", aplicar: "Aplicar"};

function equipeLinha(t) {
  async function mandar(acao, corpo = {}) {
    try { await api(`/api/equipe/${encodeURIComponent(t.id)}/${acao}`, {method: "POST",
      headers: {"Content-Type": "application/json"}, body: JSON.stringify(corpo)}); equipeCarregar(); }
    catch (err) { avisar(err.message, true); }
  }
  const acoes = el("div", {class: "botoes"});
  for (const nome of EQUIPE_ACOES[t.situacao] || ["ver"]) {
    const b = el("button", {class: "acao" + (nome === "aplicar" ? " primario" : ""), type: "button"},
                 EQUIPE_ROTULO[nome]);
    b.addEventListener("click", () => {
      if (nome === "ver") abrir("oficina");
      else if (nome === "corrigir") { const texto = prompt("O que corrigir?"); if (texto) mandar("corrigir", {texto}); }
      else mandar(nome);
    });
    acoes.append(b);
  }
  return el("div", {class: `equipe-cartao equipe-${t.situacao || "x"}`},
    el("div", {class: "equipe-titulo"}, t.titulo || t.id),
    el("div", {class: "fraco"}, `${t.cargo || "trabalhador"} · ${(t.ia || "codex").toUpperCase()} · `
      + `${t.situacao} · ${t.rodadas || 0} turnos · ${t.renovacoes || 0} renovações`),
    acoes);
}

async function equipeCarregar() {
  try {
    const dados = await api("/api/equipe");
    // ativos em cima; os ja terminados recolhidos (eram uma parede de cartoes)
    const todos = dados.trabalhadores || [];
    const ativos = todos.filter((t) => ["rodando", "criado", "aguardando_permissao"].includes(t.situacao));
    const resto = todos.filter((t) => !ativos.includes(t));
    const lista = $("equipe-lista"); lista.replaceChildren(...ativos.map(equipeLinha));
    if (!ativos.length) lista.append(el("div", {class: "fraco"}, "Ninguém trabalhando agora."));
    if (resto.length) {
      const det = el("details", {class: "equipe-concluidos"}, el("summary", {}, `Terminados (${resto.length})`));
      det.append(...resto.map(equipeLinha));
      lista.append(det);
    }
    const cargo = $("equipe-cargo"), atual = cargo.value;
    cargo.replaceChildren(...(dados.cargos || []).map((c) => el("option", {value: c}, c)));
    cargo.value = atual || (dados.cargos || [])[0] || "";
    const detalhes = dados.cargos_detalhes || {};
    if (!$("equipe-repo").value) $("equipe-repo").value = (detalhes[cargo.value] || {}).repo || "";
    const c = dados.config || {};
    $("equipe-gerente-ligado").checked = !!c.gerente_ligado;
    $("equipe-renovar-turnos").value = c.renovar_apos_turnos || 60;
    $("equipe-renovar-min").value = c.renovar_apos_min || 90;
    $("equipe-gerente").textContent = `Gerente ${c.gerente_ligado ? "ligado" : "desligado"} · renovação ${c.renovar_apos_turnos || 60} turnos / ${c.renovar_apos_min || 90} min`;
    $("equipe-passagem").textContent = (dados.nota || "(sem NOTA)") + "\n\n" + (dados.retrato || "");
    const pedidos = $("equipe-pedidos-permissao");
    pedidos.replaceChildren(...(dados.pedidos_permissao || []).map(equipePedidoPermissao));
    if (!(dados.pedidos_permissao || []).length) pedidos.append(el("div", {class: "fraco"}, "Nenhum pedido de permissao."));
    $("equipe-politica-permissoes").value = JSON.stringify(dados.permissoes || {}, null, 2);
    conexao(true);
  } catch (err) { conexao(false, err); }
}

function equipeMostrar() {
  equipeCarregar(); clearInterval(equipeTimer);
  equipeTimer = setInterval(() => { if (document.visibilityState === "visible") equipeCarregar(); }, 5000);
}
function equipeParar() { clearInterval(equipeTimer); equipeTimer = null; }

$("equipe-contratar").addEventListener("click", async () => {
  try {
    const r = await api("/api/equipe/contratar", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({cargo: $("equipe-cargo").value, ia: $("equipe-ia").value,
                            tarefa: $("equipe-tarefa").value, repo: $("equipe-repo").value})});
    $("equipe-tarefa").value = ""; avisar(`Contratado: ${r.trabalhador.id}`); equipeCarregar();
  } catch (err) { avisar(err.message, true); }
});

$("equipe-cargo").addEventListener("change", async () => {
  try {
    const dados = await api("/api/equipe");
    $("equipe-repo").value = ((dados.cargos_detalhes || {})[$("equipe-cargo").value] || {}).repo || "";
  } catch (err) { avisar(err.message, true); }
});

$("equipe-salvar-permissoes").addEventListener("click", async () => {
  try {
    const politica = JSON.parse($("equipe-politica-permissoes").value);
    await api("/api/equipe/permissoes", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(politica)});
    equipeCarregar();
  } catch (err) { avisar(err.message || "Politica invalida", true); }
});

$("equipe-salvar-gerente").addEventListener("click", async () => {
  try {
    await api("/api/equipe/config", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({gerente_ligado: $("equipe-gerente-ligado").checked,
        renovar_apos_turnos: Number($("equipe-renovar-turnos").value),
        renovar_apos_min: Number($("equipe-renovar-min").value)})});
    equipeCarregar();
  } catch (err) { avisar(err.message, true); }
});
