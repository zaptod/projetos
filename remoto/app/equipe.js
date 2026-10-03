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
  const linha = el("div", {class: "linha"}, el("span", {class: "corpo"},
    `${t.cargo || "trabalhador"} pede ${p.o_que || "permissao"}`,
    el("div", {class: "fraco"}, `${p.por_que || ""} · alvo: ${p.alvo || ""}`)));
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

function equipeLinha(t) {
  const acoes = el("div", {class: "botoes"},
    el("button", {class: "acao", type: "button"}, "Ver ao vivo"),
    el("button", {class: "acao", type: "button"}, "Renovar agora"),
    el("button", {class: "acao", type: "button"}, "Corrigir"),
    el("button", {class: "acao", type: "button"}, "Aplicar"),
    el("button", {class: "acao", type: "button"}, "Parar"));
  acoes.children[0].addEventListener("click", () => abrir("oficina"));
  async function mandar(acao, corpo = {}) {
    try { await api(`/api/equipe/${encodeURIComponent(t.id)}/${acao}`, {method: "POST",
      headers: {"Content-Type": "application/json"}, body: JSON.stringify(corpo)}); equipeCarregar(); }
    catch (err) { avisar(err.message, true); }
  }
  acoes.children[1].addEventListener("click", () => mandar("renovar"));
  acoes.children[2].addEventListener("click", () => {
    const texto = prompt("O que corrigir?"); if (texto) mandar("corrigir", {texto});
  });
  acoes.children[3].addEventListener("click", () => mandar("aplicar"));
  acoes.children[4].addEventListener("click", async () => {
    try { await api(`/api/equipe/${encodeURIComponent(t.id)}/parar`, {method: "POST",
      headers: {"Content-Type": "application/json"}, body: "{}"}); equipeCarregar(); }
    catch (err) { avisar(err.message, true); }
  });
  return el("div", {class: "linha"}, el("span", {class: "corpo"},
    `${t.cargo || "trabalhador"} · ${(t.ia || "codex").toUpperCase()} · ${t.titulo || t.id}`,
    el("div", {class: "fraco"}, `${t.situacao} · ${t.rodadas || 0} turnos · ${t.renovacoes || 0} renovações`)), acoes);
}

async function equipeCarregar() {
  try {
    const dados = await api("/api/equipe");
    const lista = $("equipe-lista"); lista.replaceChildren(...(dados.trabalhadores || []).map(equipeLinha));
    if (!(dados.trabalhadores || []).length) lista.append(el("div", {class: "fraco"}, "Nenhum trabalhador contratado."));
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
