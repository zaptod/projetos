"use strict";
// A tela Comandos: tudo o que dá para mandar fazer do celular.
//
// Nada aqui sabe QUAIS são os comandos: o servidor manda o catálogo
// (/api/catalogo) com os campos de cada um, e esta tela se monta sozinha.
// Uma segunda lista de botões escrita aqui divergiria do servidor na
// primeira mudança — e seria a tela mentindo sobre o que existe.
//
// O que é pesado vira TAREFA: o pedido devolve uma chave, e o log aparece
// aqui, ao vivo, enquanto o processo roda no PC.

const TAREFAS_MS = 4000;
const LOG_MS = 2000;

const Comandos = {
  catalogo: null, tarefas: [], aberta: null, desde: 0,
  relogio: null, relogioLog: null,
};

async function comandosCarregarCatalogo() {
  if (Comandos.catalogo) return Comandos.catalogo;
  Comandos.catalogo = await api("/api/catalogo");
  return Comandos.catalogo;
}

async function comandosCarregarTarefas() {
  const dados = await api("/api/tarefas?n=15");
  Comandos.tarefas = dados.tarefas || [];
  comandosDesenharTarefas();
}

// ---------------------------------------------------------------- tela
function comandosDesenhar() {
  const alvo = $("comandos-grupos");
  const cat = Comandos.catalogo;
  alvo.replaceChildren();
  if (!cat || !cat.acoes.length) {
    alvo.append(el("div", {class: "fraco"},
      "as ações estão desligadas neste servidor"));
    return;
  }
  for (const grupo of cat.grupos) {
    const acoes = cat.acoes.filter((a) => a.grupo === grupo.nome);
    if (!acoes.length) continue;
    const caixa = el("div", {class: "cartao" + (grupo.nome === "perigo"
      ? " perigo-caixa" : "")},
      el("h2", {}, grupo.rotulo));
    for (const acao of acoes) {
      const botao = el("button",
        {class: "acao" + (grupo.nome === "perigo" ? " perigo" : "")},
        acao.rotulo);
      botao.addEventListener("click", () => comandosPedir(acao));
      caixa.append(el("div", {class: "comando"}, botao,
        el("div", {class: "fraco"}, acao.descricao || "")));
    }
    alvo.append(caixa);
  }
}

// O formulário sai da ficha: cada campo vira o controle do seu tipo.
async function comandosPedir(acao) {
  let args = {};
  if (acao.campos.length || acao.perigo) {
    args = await comandosFormulario(acao);
    if (args === null) return;
  }
  await agir(acao.nome, args);
  comandosCarregarTarefas().catch(() => {});
}

function comandosFormulario(acao) {
  const d = $("dialogo-campos");
  const corpo = $("campos-corpo");
  corpo.replaceChildren(el("p", {}, acao.rotulo),
                        el("p", {class: "fraco"}, acao.descricao || ""));
  const entradas = {};
  for (const campo of acao.campos) {
    let entrada;
    if (campo.tipo === "escolha") {
      entrada = el("select", {});
      entrada.replaceChildren(...campo.opcoes.map(
        (o) => el("option", {value: o}, o)));
    } else if (campo.tipo === "bool") {
      entrada = el("input", {type: "checkbox"});
    } else if (campo.tipo === "numero") {
      entrada = el("input", {type: "number", inputmode: "numeric"});
      if (campo.minimo != null) entrada.min = campo.minimo;
      if (campo.maximo != null) entrada.max = campo.maximo;
      if (campo.padrao != null) entrada.value = campo.padrao;
    } else if (campo.tipo === "build" || campo.tipo === "historia") {
      entrada = el("select", {});
      entrada.replaceChildren(el("option", {value: ""}, "carregando…"));
      comandosPreencherIds(entrada, campo.tipo);
    } else {
      entrada = el("input", {type: "text"});
    }
    entradas[campo.nome] = entrada;
    corpo.append(el("label", {class: "campo"}, campo.rotulo, entrada));
  }
  const perigo = acao.perigo || acao.perigo_se;
  let confirmo = null;
  if (perigo) {
    confirmo = el("input", {type: "text", placeholder: "digite para confirmar"});
    corpo.append(el("label", {class: "campo erro"},
      "Isto não tem desfazer. Digite o alvo para confirmar:", confirmo));
  }
  return new Promise((resolve) => {
    d.returnValue = "cancelar";
    d.addEventListener("close", () => {
      if (d.returnValue !== "ok") { resolve(null); return; }
      const args = {};
      for (const [nome, entrada] of Object.entries(entradas)) {
        args[nome] = entrada.type === "checkbox" ? entrada.checked : entrada.value;
      }
      if (confirmo) args.confirmo = confirmo.value.trim();
      resolve(args);
    }, {once: true});
    d.showModal();
  });
}

// As listas de build e de história vêm do que o app já mostra em Vídeos.
async function comandosPreencherIds(entrada, tipo) {
  try {
    const videos = await api("/api/videos?n=80");
    const canal = tipo === "build" ? "builds" : "historias";
    const ids = [...new Set(videos.filter((v) => v.canal === canal)
      .map((v) => String(v.id).split(":")[0]))];
    entrada.replaceChildren(...ids.map((i) => el("option", {value: i}, i)));
    if (!ids.length) {
      entrada.replaceChildren(el("option", {value: ""}, "nada disponível"));
    }
  } catch (err) {
    entrada.replaceChildren(el("option", {value: ""}, "não consegui listar"));
  }
}

// -------------------------------------------------------------- tarefas
function comandosDesenharTarefas() {
  const alvo = $("tarefas-lista");
  if (!Comandos.tarefas.length) {
    alvo.replaceChildren(el("div", {class: "fraco"},
      "nenhuma tarefa ainda. O que você mandar fazer aparece aqui."));
    return;
  }
  alvo.replaceChildren(...Comandos.tarefas.map((t) => {
    const quando = t.inicio ? t.inicio.slice(11, 16) : "";
    const selo = t.situacao === "rodando" ? "trabalhando"
      : (t.codigo === 0 ? "ok" : "erro");
    const texto = t.situacao === "rodando" ? "rodando"
      : t.situacao === "sumiu" ? "sumiu"
        : (t.codigo === 0 ? "pronto" : `saiu ${t.codigo}`);
    const linha = el("div", {class: "linha"},
      el("span", {class: "corpo"}, t.rotulo || t.acao,
        el("div", {class: "fraco"}, `${quando} · ${t.acao}`)),
      el("span", {class: "selo " + selo}, texto));
    linha.addEventListener("click", () => comandosAbrirLog(t.chave));
    return linha;
  }));
}

async function comandosAbrirLog(chave) {
  Comandos.aberta = chave;
  Comandos.desde = 0;
  $("tarefa-log").textContent = "abrindo…";
  $("tarefa-caixa").classList.remove("oculto");
  await comandosLerLog();
  clearInterval(Comandos.relogioLog);
  Comandos.relogioLog = setInterval(() => {
    if (document.visibilityState === "visible") comandosLerLog().catch(() => {});
  }, LOG_MS);
}

async function comandosLerLog() {
  if (!Comandos.aberta) return;
  const ficha = await api(
    `/api/tarefa/${encodeURIComponent(Comandos.aberta)}?desde=${Comandos.desde}`);
  const caixa = $("tarefa-log");
  if (Comandos.desde === 0) caixa.textContent = "";
  if (ficha.log?.texto) {
    caixa.textContent += ficha.log.texto;
    caixa.scrollTop = caixa.scrollHeight;
  }
  Comandos.desde = ficha.log?.ate || Comandos.desde;
  $("tarefa-titulo").textContent =
    `${ficha.rotulo || ficha.acao} · ${ficha.situacao}` +
    (ficha.codigo != null ? ` (saída ${ficha.codigo})` : "");
  if (ficha.situacao !== "rodando") {
    clearInterval(Comandos.relogioLog);
    Comandos.relogioLog = null;
  }
}

function comandosFecharLog() {
  Comandos.aberta = null;
  clearInterval(Comandos.relogioLog);
  Comandos.relogioLog = null;
  $("tarefa-caixa").classList.add("oculto");
}

// --------------------------------------------------------- ciclo de vida
async function comandosMostrar() {
  if (!Comandos.relogio) {
    Comandos.relogio = setInterval(() => {
      if (document.visibilityState === "visible") {
        comandosCarregarTarefas().catch(() => {});
      }
    }, TAREFAS_MS);
  }
  try {
    await comandosCarregarCatalogo();
    comandosDesenhar();
    await comandosCarregarTarefas();
    conexao(true);
  } catch (err) { conexao(false, err); }
}

function comandosParar() {
  clearInterval(Comandos.relogio); Comandos.relogio = null;
  clearInterval(Comandos.relogioLog); Comandos.relogioLog = null;
}

$("btn-fechar-log").addEventListener("click", comandosFecharLog);
$("btn-campos-ok").addEventListener("click", () => {
  $("dialogo-campos").returnValue = "ok";
});
