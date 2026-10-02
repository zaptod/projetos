"use strict";
// O objeto Mandar: tudo o que dá para mandar fazer do celular.
//
// Nada aqui sabe QUAIS são os comandos: o servidor manda o catálogo
// (/api/catalogo) com os campos de cada um, e esta tela se monta sozinha.
// Uma segunda lista de botões escrita aqui divergiria do servidor na
// primeira mudança — e seria a tela mentindo sobre o que existe.
//
// O que é pesado vira uma tarefa no PC: o pedido devolve uma chave, e o log
// aparece ao vivo enquanto o processo roda. ONDE aparece (02/10/2026, pedido
// do Adrian: "E esse TAREFAS da bancada serve pra que??"): logo abaixo do
// botão que o disparou (as últimas daquele comando) e, embaixo de todos os
// botões, a lista "Últimos que você mandou" — que some quando está vazia.
// Antes era um cartão "Tarefas" ACIMA dos botões, quase sempre vazio.

const TAREFAS_MS = 4000;
const LOG_MS = 2000;
const HISTORICO_POR_COMANDO = 2;      // quantas linhas sob cada botão

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
  // o log aberto pode estar dentro de um comando: volta para casa antes de
  // redesenhar (um elemento fora da página não é achado pelo id)
  comandosFecharLog();
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
      caixa.append(el("div", {class: "comando", "data-acao": acao.nome}, botao,
        el("div", {class: "fraco"}, acao.descricao || ""),
        el("div", {class: "comando-historico", "data-historico": acao.nome})));
    }
    alvo.append(caixa);
  }
  comandosDesenharTarefas();
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

// ------------------------------------------- o que você mandou (histórico)
function comandosLinha(t, ancora) {
  const quando = t.inicio ? quandoCurto(t.inicio) : "";
  const selo = t.situacao === "rodando" ? "trabalhando"
    : (t.codigo === 0 ? "ok" : "erro");
  const texto = t.situacao === "rodando" ? "rodando"
    : t.situacao === "sumiu" ? "sumiu"
      : (t.codigo === 0 ? "pronto" : `saiu ${t.codigo}`);
  const linha = el("div", {class: "linha comando-linha", "data-chave": t.chave,
                           role: "button", tabindex: "0", title: "ver o log"},
    el("span", {class: "corpo"}, t.rotulo || t.acao,
      el("div", {class: "fraco"}, `${quando} · ${t.acao} · ver o log`)),
    el("span", {class: "selo " + selo}, texto));
  linha.addEventListener("click", () => comandosAbrirLog(t.chave, ancora || null));
  return linha;
}

function comandosDesenharTarefas() {
  // logo abaixo de cada botão: as últimas que ELE disparou
  for (const caixa of document.querySelectorAll("#comandos-grupos [data-historico]")) {
    const minhas = Comandos.tarefas.filter((t) => t.acao === caixa.dataset.historico)
      .slice(0, HISTORICO_POR_COMANDO);
    caixa.replaceChildren(...minhas.map((t) => comandosLinha(t, caixa.parentElement)));
  }
  // embaixo de todos os botões: tudo, do mais novo para o mais velho; vazio
  // não ocupa lugar
  $("comandos-ultimos").classList.toggle("oculto", !Comandos.tarefas.length);
  $("tarefas-lista").replaceChildren(...Comandos.tarefas.map((t) => comandosLinha(t, null)));
}

// O log abre logo abaixo de onde ele tocou: sob o comando, ou no fim da lista
// "Últimos que você mandou" (a casa dele).
async function comandosAbrirLog(chave, ancora = null) {
  Comandos.aberta = chave;
  Comandos.desde = 0;
  const caixaLog = $("tarefa-caixa");
  (ancora || $("comandos-ultimos")).append(caixaLog);
  $("tarefa-log").textContent = "abrindo…";
  caixaLog.classList.remove("oculto");
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
  const caixaLog = $("tarefa-caixa");
  caixaLog.classList.add("oculto");
  $("comandos-ultimos").append(caixaLog);          // de volta para casa
}

// --------------------------------------------------------- ciclo de vida
async function comandosMostrar() {
  if (!Comandos.relogio) {
    Comandos.relogio = setInterval(() => {
      if (document.visibilityState === "visible") {
        comandosCarregarTarefas().catch(() => {});
        // "Controlar o PC": as ações do coordenador moram aqui
        if (typeof coordCarregar === "function") coordCarregar();
      }
    }, TAREFAS_MS);
  }
  claudeCarregar();                       // o interruptor do Claude, no topo
  if (typeof coordCarregar === "function") coordCarregar();
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
