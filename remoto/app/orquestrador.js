"use strict";
// A Mesa de comando: o orquestrador (a sessão principal do Claude Code)
// publica o que faz em arquivos no PC; esta tela mostra e manda comandos.
//
// Nada aqui muda nada sozinho: cada toque vira um COMANDO que fica
// "pendente" até o orquestrador aplicar (ou recusar, com o motivo). A
// capacidade na tela é a que ele aceitou; a pedida aparece ao lado.

const ORQ_MS = 10000;
const ORQ_FLUXO_MS = 60000;
const ORQ_SELO_MS = 60000;
const ORQ_SIMBOLO = {ok: "✓", rodando: "▶", fila: "…", falhou: "✕", ausente: "·"};
// Agente sem relato ha mais que isto pode estar preso: a ficha avisa.
const ORQ_SEM_NOTICIA_S = 30 * 60;
const ORQ_PARTES = ["geral", "builds", "historias", "publicacao", "metricas", "app-e-bot",
                    "painel-e-vila", "jogo-zombie"];
const ORQ_FONTE = {app: "pelo app", chat: "pelo chat", orquestrador: "pelo orquestrador"};
const ORQ_CHAVE = {max_paralelo: "agentes em paralelo", modo: "modo",
                   teto_sessao_pct: "teto de uso", forca_total_antes_min: "força total",
                   fila_pausada: "fila pausada"};

const Orq = {dados: null, relogio: null, relogioFluxo: null, seloEm: 0};

function orqHora(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d) ? String(iso).slice(11, 16) : hora(iso);
}

function orqHoraEpoch(s) {
  if (s == null) return "—";
  return quandoCurto(new Date(Number(s) * 1000).toISOString());
}

function orqFalta(s) {
  if (s == null) return "";
  const m = Math.round((Number(s) * 1000 - Date.now()) / 60000);
  if (m <= 0) return "já renovou";
  if (m < 60) return `em ${m} min`;
  const h = Math.floor(m / 60);
  return h < 48 ? `em ${h} h ${m % 60} min` : `em ${Math.floor(h / 24)} d`;
}

function orqDesde(iso) {
  const d = new Date(iso);
  return isNaN(d) ? "" : ha((Date.now() - d.getTime()) / 1000);
}

// Os comandos ainda não aplicados, do mais novo para o mais velho.
function orqPendentes(nome) {
  const lista = (Orq.dados && Orq.dados.comandos) || [];
  return lista.filter((c) => c.situacao === "pendente" && (!nome || c.comando === nome));
}

async function orqEnviar(comando, valor = null) {
  try {
    await api("/api/orquestrador/comando", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({comando, valor}),
    });
    avisar("enviado — fica pendente até o orquestrador aplicar");
  } catch (err) { avisar(err.message, true); }
  orqCarregar();
}

// Um texto livre pelo diálogo de campos (o mesmo das fichas da Bancada).
function orqPerguntarTexto(titulo, explicacao, rotulo) {
  const d = $("dialogo-campos");
  const caixa = el("textarea", {class: "decisao-comentario", rows: "4", maxlength: "1500"});
  $("campos-corpo").replaceChildren(el("p", {}, titulo),
    el("p", {class: "fraco"}, explicacao), el("label", {class: "campo"}, rotulo, caixa));
  return new Promise((resolve) => {
    d.returnValue = "cancelar";
    d.addEventListener("close", () => {
      resolve(d.returnValue === "ok" ? caixa.value.trim() : null);
    }, {once: true});
    d.showModal();
  });
}

// ---------------------------------------------------------------- faixa
function orqFaixa(d) {
  const faixa = $("orq-faixa");
  const linhas = [];
  let ruim = false;
  if (!d.estado_existe) {
    linhas.push("O orquestrador ainda não publicou nada aqui. Os comandos ficam pendentes.");
    ruim = true;
  } else if (d.fora_do_ar) {
    linhas.push(`Orquestrador fora do ar: sem sinal desde ${orqHora(d.estado.atualizado_em)}`
      + ` (${ha(d.idade_s)}). Os comandos ficam pendentes até a sessão voltar.`);
    ruim = true;
  }
  for (const e of d.erros || []) linhas.push("⚠ " + e);
  faixa.replaceChildren(...linhas.map((l) => el("div", {}, l)));
  faixa.classList.toggle("oculto", !linhas.length);
  faixa.classList.toggle("ruim", ruim);
}

// ---------------------------------------------------------------- agora
function orqFicha(parte) {
  const letras = String(parte || "?").split(/[-_ ]/).filter(Boolean)
    .map((p) => p[0]).join("").slice(0, 2).toUpperCase();
  return el("span", {class: "orq-ficha", "aria-hidden": "true"}, letras || "?");
}

function orqIdade(iso) {
  const t = new Date(iso).getTime();
  return isNaN(t) ? null : (Date.now() - t) / 1000;
}

// A sessão principal (o orquestrador), em uma linha, com a hora: o relato
// que ele dá (`eu "..."`) e o último movimento que a CLI registrou sozinha.
function orqDesenharPrincipal(d) {
  const p = d.principal || {};
  const alvo = $("orq-principal");
  const partes = [el("div", {class: "orq-sub"}, "Sessão principal")];
  if (p.relato) {
    partes.push(el("div", {class: "orq-principal-relato"}, p.relato),
      el("div", {class: "fraco"}, `${orqHora(p.relato_em)} (${orqDesde(p.relato_em)})`));
  } else {
    partes.push(el("div", {class: "fraco"}, "Ele ainda não disse no que está."));
  }
  if (p.movimento) {
    partes.push(el("div", {class: "fraco"},
      `último movimento ${orqHora(p.movimento_em)}: ${p.movimento}`));
  }
  const sinal = d.estado.atualizado_em;
  partes.push(el("div", {class: d.fora_do_ar ? "erro" : "fraco"}, sinal
    ? `sinal de vida ${orqHora(sinal)} (${ha(d.idade_s)})` : "nunca deu sinal de vida"));
  const linha = p.linha || [];
  if (linha.length) {
    partes.push(orqDetalhes(`Linha do tempo (${linha.length})`, linha.map((x) =>
      el("div", {class: "linha"}, el("span", {class: "orq-hora"}, orqHora(x.em)),
        el("span", {class: "corpo" + (x.tipo === "relato" ? "" : " fraco")}, x.texto)))));
  }
  alvo.replaceChildren(...partes);
}

// O resumo que responde "cabe mais um?": vagas, uso contra o teto, fila.
function orqDesenharResumo(d) {
  const ocupadas = (d.estado.agora || []).length;
  const vagas = d.paralelo_efetivo;
  const u = d.uso || {};
  const itens = [
    [`${ocupadas} de ${vagas}`, "vagas ocupadas", ocupadas > vagas ? "erro" : ""],
    u.situacao === "ok" && u.medicao
      ? [`${Math.round(u.medicao.sessao_pct)}%`, `da sessão · teto ${u.teto}%`,
         u.passou_teto ? "erro" : ""]
      : ["—", "uso sem medição", "erro"],
    [String((d.estado.fila || []).length),
     d.config.fila_pausada ? "na fila (pausada)" : "na fila", d.config.fila_pausada ? "erro" : ""],
  ];
  $("orq-resumo").replaceChildren(...itens.map(([n, r, c]) =>
    el("span", {class: "orq-passo " + c}, el("strong", {}, n), r)));
  $("orq-agentes-titulo").textContent = `Agentes (${ocupadas} de ${vagas} vagas)`;
}

function orqDesenharAgora(d) {
  orqDesenharPrincipal(d);
  orqDesenharResumo(d);
  const alvo = $("orq-agora");
  const agora = d.estado.agora || [];
  if (!agora.length) {
    alvo.replaceChildren(el("div", {class: "fraco"}, "Nenhum agente trabalhando agora."));
  } else {
    const parando = new Set(orqPendentes("parar_agente").map((c) => c.valor));
    alvo.replaceChildren(...agora.map((a) => {
      const botao = el("button", {class: "acao perigo"}, "⏹ parar");
      botao.disabled = parando.has(a.id) || a.situacao === "parando";
      botao.addEventListener("click", async () => {
        const r = await perguntar(`Pedir ao orquestrador para parar «${a.titulo}» (${a.parte})?`
          + " Ele para o agente num ponto consistente.");
        if (r === "confirmar") orqEnviar("parar_agente", a.id);
      });
      return el("div", {class: "linha orq-agente"}, orqFicha(a.parte),
        el("span", {class: "corpo"},
          el("strong", {}, a.titulo),
          el("div", {class: "fraco"}, `${a.parte} · desde ${orqHora(a.desde)} `
            + `(${orqDesde(a.desde)})` + (a.situacao !== "trabalhando" ? ` · ${a.situacao}` : "")
            + (parando.has(a.id) ? " · parar pedido (pendente)" : "")),
          a.relato ? el("div", {class: "orq-relato"}, "“" + a.relato + "”"
            + (a.relato_em ? ` · ${orqHora(a.relato_em)}` : "")) : null,
          orqSemNoticia(a)),
        botao);
    }));
  }
  const feitos = d.estado.concluidos_hoje || [];
  $("orq-concluidos").textContent = feitos.length
    ? "Hoje: " + feitos.map((c) => `${c.titulo} (${c.situacao}`
      + (c.commits && c.commits.length ? ` · ${c.commits.join(" ")}` : "") + ")").join(" · ")
    : "";
}

// Sem relato há muito tempo: pode estar preso, ou só calado. A ficha diz.
function orqSemNoticia(a) {
  const idade = orqIdade(a.relato_em || a.desde);
  if (idade == null || idade < ORQ_SEM_NOTICIA_S) return null;
  return el("div", {class: "erro"}, `sem notícia ${ha(idade)}`);
}

// ----------------------------------------------------------------- fila
function orqDesenharFila(d) {
  const fila = d.estado.fila || [];
  const pausada = d.config.fila_pausada;
  const pedPausa = orqPendentes("pausar_fila").length;
  const pedRetomar = orqPendentes("retomar_fila").length;
  $("orq-fila-situacao").textContent = (pausada ? "⏸ fila pausada" : "▶ fila andando")
    + (pedPausa ? " · pausar pedido (pendente)" : "")
    + (pedRetomar ? " · retomar pedido (pendente)" : "");
  $("orq-fila-situacao").className = pausada ? "erro" : "fraco";
  const movendo = orqPendentes("priorizar");
  const tirando = new Set(orqPendentes("tirar_da_fila").map((c) => c.valor));
  const pondo = orqPendentes("adicionar_a_fila").map((c) => el("div", {class: "linha"},
    el("span", {class: "orq-ordem"}, "+"),
    el("span", {class: "corpo"}, c.valor.item,
      el("div", {class: "fraco"}, `${c.valor.parte} · pedido (pendente)`))));
  const alvo = $("orq-fila");
  if (!fila.length) {
    alvo.replaceChildren(el("div", {class: "fraco"}, "A fila está vazia."), ...pondo);
    return;
  }
  alvo.replaceChildren(...fila.map((f, n) => {
    const subir = el("button", {class: "acao", "aria-label": "Subir"}, "↑");
    const descer = el("button", {class: "acao", "aria-label": "Descer"}, "↓");
    subir.disabled = n === 0;
    descer.disabled = n === fila.length - 1;
    subir.addEventListener("click", () => orqEnviar("priorizar", {item: f.id, direcao: "subir"}));
    descer.addEventListener("click", () => orqEnviar("priorizar", {item: f.id, direcao: "descer"}));
    const tirar = el("button", {class: "acao perigo", "aria-label": "Tirar da fila"}, "✕");
    tirar.disabled = tirando.has(f.id);
    tirar.addEventListener("click", async () => {
      const r = await perguntar(`Tirar «${f.item}» (${f.parte}) da fila?`);
      if (r === "confirmar") orqEnviar("tirar_da_fila", f.id);
    });
    const pedido = movendo.filter((c) => c.valor && c.valor.item === f.id)
      .map((c) => c.valor.direcao).join(", ");
    return el("div", {class: "linha"},
      el("span", {class: "orq-ordem"}, String(n + 1)),
      el("span", {class: "corpo"}, f.item,
        el("div", {class: "fraco"}, f.parte + (f.pedido ? ` · pedido por ${f.pedido}` : "")
          + (f.desde ? ` · desde ${quandoCurto(f.desde)}` : "")
          + (pedido ? ` · ${pedido} (pendente)` : "")
          + (tirando.has(f.id) ? " · tirar pedido (pendente)" : ""))),
      subir, descer, tirar);
  }), ...pondo);
}

// Pôr na fila: a parte e o que fazer. Vira comando; o orquestrador põe.
async function orqPorNaFila() {
  const d = $("dialogo-campos");
  const parte = el("select", {});
  for (const p of ORQ_PARTES) parte.append(el("option", {value: p}, p));
  const item = el("textarea", {class: "decisao-comentario", rows: "3", maxlength: "200"});
  $("campos-corpo").replaceChildren(el("p", {}, "Pôr na fila do orquestrador"),
    el("p", {class: "fraco"}, "Entra no fim; depois dá para subir. Fica pendente até ele aplicar."),
    el("label", {class: "campo"}, "Parte", parte),
    el("label", {class: "campo"}, "O que fazer", item));
  const ok = await new Promise((resolve) => {
    d.returnValue = "cancelar";
    d.addEventListener("close", () => resolve(d.returnValue === "ok"), {once: true});
    d.showModal();
  });
  if (!ok) return;
  if (!item.value.trim()) { avisar("diga o que fazer", true); return; }
  orqEnviar("adicionar_a_fila", {parte: parte.value, item: item.value.trim()});
}

// ----------------------------------------------------------- capacidade
function orqAlvo(nome, atual) {
  const p = orqPendentes(nome);
  return p.length ? p[p.length - 1].valor : atual;
}

function orqDesenharCapacidade(d) {
  const c = d.config;
  const alvoMax = orqAlvo("max_paralelo", c.max_paralelo);
  $("orq-max").textContent = String(c.max_paralelo);
  $("orq-menos").disabled = alvoMax <= 1;
  $("orq-mais").disabled = alvoMax >= 8;
  $("orq-menos").onclick = () => orqEnviar("max_paralelo", alvoMax - 1);
  $("orq-mais").onclick = () => orqEnviar("max_paralelo", alvoMax + 1);
  $("orq-efetivo").textContent = c.modo === "um_por_vez"
    ? `No modo "um por vez" roda 1 agente, qualquer que seja o máximo.`
    : `Até ${d.paralelo_efetivo} agente(s) ao mesmo tempo.`;

  const modos = $("orq-modos");
  const alvoModo = orqAlvo("modo", c.modo);
  modos.replaceChildren(...d.modos.map((m) => {
    const b = el("button", {class: "acao", "aria-pressed": String(m.id === c.modo)},
      m.rotulo + (m.id === alvoModo && m.id !== c.modo ? " (pedido)" : ""));
    b.addEventListener("click", () => { if (m.id !== alvoModo) orqEnviar("modo", m.id); });
    return b;
  }));
  $("orq-modo-ajuda").textContent = {
    um_por_vez: "Um por vez: 1 agente, qualquer que seja o máximo.",
    paralelo: "Paralelo: até o máximo acima, e para no teto de uso.",
    forca_total: "Força total: até o máximo, e o teto de uso NÃO para os agentes.",
  }[c.modo] || "";

  const teto = $("orq-teto");
  const valores = [30, 40, 50, 60, 70, 80, 90, 100];
  if (!valores.includes(c.teto_sessao_pct)) valores.push(c.teto_sessao_pct);
  valores.sort((a, b) => a - b);
  teto.replaceChildren(...valores.map((v) => el("option", {value: String(v)}, `${v}%`)));
  teto.value = String(orqAlvo("teto_uso", c.teto_sessao_pct));
  teto.onchange = () => orqEnviar("teto_uso", Number(teto.value));

  const forca = $("orq-forca");
  const ligada = c.forca_total_antes_min != null;
  forca.setAttribute("aria-pressed", String(ligada));
  forca.textContent = ligada ? `ligada (${c.forca_total_antes_min} min antes)` : "desligada";
  forca.onclick = () => orqEnviar("forca_total", !ligada);

  const pedidos = ["max_paralelo", "modo", "teto_uso", "forca_total"]
    .flatMap((n) => orqPendentes(n))
    .map((p) => `${p.rotulo}: ${orqValor(p)}`);
  $("orq-capacidade-pendente").textContent = pedidos.length
    ? "Pedido, esperando o orquestrador: " + pedidos.join(" · ") : "";
  orqDesenharGrimorio(d);
  orqDesenharHistoricoCapacidade(d);
}

// O que muda aqui vira a regra (decisão geral/capacidade-pelo-app): o
// orquestrador responde o Grimório ao aplicar. Aqui, a prova: o que o
// Grimório diz, e se bate com o que vale na Mesa.
function orqDesenharGrimorio(d) {
  const lista = d.grimorio || [];
  const linhas = lista.map((g) => {
    if (g.erro) return el("div", {class: "erro"}, g.erro);
    if (!g.existe) return el("div", {class: "erro"}, `⚠ o Grimório não tem o nó ${g.no}`);
    return el("div", {class: "linha"},
      el("span", {class: "corpo"}, el("strong", {}, g.titulo),
        el("div", {class: "fraco"}, `${g.rotulo || "sem resposta"}`
          + (g.comentario ? ` · “${g.comentario}”` : "")),
        g.bate ? null : el("div", {class: "erro"},
          `⚠ não bate com a Mesa (${g.esperado})` + (g.situacao !== "decidida"
            ? ` · está ${g.situacao === "a_rever" ? "a rever" : g.situacao}` : ""))),
      el("span", {class: "selo " + (g.bate ? "ok" : "erro")}, g.bate ? "bate" : "diverge"));
  });
  $("orq-grimorio").replaceChildren(
    el("h3", {class: "orq-sub"}, "No Grimório (vira regra)"),
    el("div", {class: "fraco"}, "O que você muda aqui o orquestrador registra no Grimório, "
      + "com commit — igual a uma instrução sua no chat."),
    ...linhas);
}

function orqDesenharHistoricoCapacidade(d) {
  const h = d.historico_config || [];
  const texto = (v) => v == null ? "desligada" : v === true ? "sim" : v === false ? "não"
    : String(v);
  $("orq-cap-historico").replaceChildren(orqDetalhes(`Histórico das mudanças (${h.length})`,
    h.length ? h.map((x) => el("div", {class: "linha"},
      el("span", {class: "orq-hora"}, quandoCurto(x.em)),
      el("span", {class: "corpo"}, `${ORQ_CHAVE[x.chave] || x.chave}: ${texto(x.de)} → `
        + `${texto(x.para)}`, el("div", {class: "fraco"}, ORQ_FONTE[x.origem] || x.origem))))
      : [el("div", {class: "fraco"}, "Nada mudou ainda.")]));
}

// -------------------------------------------------------------- limites
function orqBarra(rotulo, pct, renova, teto) {
  const barra = el("div", {class: "orq-barra"});
  const cheio = el("div", {class: "orq-barra-cheio" + (teto != null && pct >= teto ? " passou" : "")});
  cheio.style.width = Math.max(0, Math.min(100, pct)) + "%";
  barra.append(cheio);
  if (teto != null) {
    const marca = el("div", {class: "orq-barra-teto", title: `teto ${teto}%`});
    marca.style.left = Math.min(100, teto) + "%";
    barra.append(marca);
  }
  return el("div", {class: "orq-limite"},
    el("div", {class: "orq-limite-topo"},
      el("span", {}, rotulo), el("strong", {}, `${Math.round(pct)}%`)),
    barra,
    el("div", {class: "fraco"}, `renova ${orqHoraEpoch(renova)} (${orqFalta(renova)})`
      + (teto != null ? ` · teto ${teto}%` : "")));
}

function orqDesenharLimites(d) {
  const u = d.uso || {};
  const alvo = $("orq-limites");
  const aviso = $("orq-teto-aviso");
  aviso.classList.add("oculto");
  if (u.situacao !== "ok" || !u.medicao) {
    // NUNCA um número velho como se fosse atual: sem medição válida, sem barra.
    const texto = u.situacao === "velha"
      ? `Sem medição desde ${orqHoraEpoch(u.desde)}` + (u.motivo ? ` — ${u.motivo}` : "")
      : "Sem medição ainda" + (u.motivo ? ` — ${u.motivo}` : "");
    alvo.replaceChildren(el("div", {class: "orq-sem-medicao"}, texto),
      el("div", {class: "fraco"}, orqSonda(d)));
  } else {
    const m = u.medicao;
    // replaceChildren escreveria "null" por extenso: so os que existem
    alvo.replaceChildren(...[
      orqBarra("Sessão (5 h)", m.sessao_pct, m.sessao_renova_em, u.teto),
      m.semana_pct != null ? orqBarra("Semana", m.semana_pct, m.semana_renova_em, null)
        : el("div", {class: "fraco"}, "semana: a medição não trouxe"),
      el("div", {class: "fraco"}, `medido às ${orqHoraEpoch(m.gravado_em)} · ${u.fonte}`
        + ` · ${orqSonda(d)}`),
      u.forca_total_antes_min && m.sessao_renova_em
        ? el("div", {class: "fraco"}, `força total a partir de `
          + `${orqHoraEpoch(Number(m.sessao_renova_em) - u.forca_total_antes_min * 60)}`
          + ` (${u.forca_total_antes_min} min antes de renovar)`)
        : el("div", {class: "fraco"}, "força total desligada: o teto vale até renovar"),
      u.janela_forca_total
        ? el("div", {class: "ok"}, `Janela da força total: faltam menos de `
          + `${u.forca_total_antes_min} min para renovar.`) : null].filter(Boolean));
    if (u.passou_teto) {
      aviso.textContent = `Passou do teto: a sessão está em ${Math.round(m.sessao_pct)}%, `
        + `e o teto é ${u.teto}%. Pela regra, os agentes param.`;
      aviso.classList.remove("oculto");
    }
  }
  orqGrafico(d.historico_uso || [], u.teto);
}

function orqSonda(d) {
  const n = Number(d.config.sonda_min || 0);
  return n > 0 ? `sonda a cada ${n} min` : "sonda desligada (sonda_min 0)";
}

// O gráfico do dia: uma linha (a sessão), o teto tracejado, eixo de 0 a 24 h.
// Buraco de mais de 30 min entre medições não vira reta: a linha quebra.
function orqGrafico(pontos, teto) {
  const NS = "http://www.w3.org/2000/svg";
  const L = 340, A = 130, E = 34, D = 8, T = 10, B = 20;
  const x = (dt) => E + ((dt.getHours() * 60 + dt.getMinutes()) / 1440) * (L - E - D);
  const y = (p) => T + (1 - Math.max(0, Math.min(100, p)) / 100) * (A - T - B);
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${L} ${A}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Uso da sessão ao longo do dia");
  const add = (tag, attrs, texto) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (texto != null) n.textContent = texto;
    svg.append(n);
    return n;
  };
  for (const p of [0, 50, 100]) {
    add("line", {x1: E, x2: L - D, y1: y(p), y2: y(p), class: "orq-g-grade"});
    add("text", {x: E - 4, y: y(p) + 3, class: "orq-g-rotulo", "text-anchor": "end"}, `${p}%`);
  }
  for (const h of [0, 6, 12, 18, 24]) {
    const xx = E + (h / 24) * (L - E - D);
    add("text", {x: xx, y: A - 5, class: "orq-g-rotulo", "text-anchor": "middle"}, `${h}h`);
  }
  if (teto != null) {
    add("line", {x1: E, x2: L - D, y1: y(teto), y2: y(teto), class: "orq-g-teto"});
    add("text", {x: L - D, y: y(teto) - 3, class: "orq-g-rotulo", "text-anchor": "end"},
      `teto ${teto}%`);
  }
  const validos = pontos.filter((p) => p.sessao_pct != null && !isNaN(new Date(p.em)))
    .map((p) => ({...p, dt: new Date(p.em)}));
  let trecho = [];
  const fechar = () => {
    if (trecho.length > 1) add("polyline", {class: "orq-g-linha",
      points: trecho.map((p) => `${x(p.dt).toFixed(1)},${y(p.sessao_pct).toFixed(1)}`).join(" ")});
    trecho = [];
  };
  validos.forEach((p, n) => {
    if (n && p.dt - validos[n - 1].dt > 30 * 60000) fechar();
    trecho.push(p);
  });
  fechar();
  const leitura = $("orq-grafico-leitura");
  if (validos.length) {
    const ultimo = validos[validos.length - 1];
    add("circle", {cx: x(ultimo.dt), cy: y(ultimo.sessao_pct), r: 4, class: "orq-g-ponto"});
    const pico = validos.reduce((a, b) => (b.sessao_pct > a.sessao_pct ? b : a));
    leitura.textContent = `${validos.length} medição(ões) hoje · pico ${Math.round(pico.sessao_pct)}%`
      + ` às ${hora(pico.em)} · toque no gráfico para ler um ponto`;
    const cruz = add("line", {x1: 0, x2: 0, y1: T, y2: A - B, class: "orq-g-cruz oculto"});
    const ler = (ev) => {
      const r = svg.getBoundingClientRect();
      const px = ((ev.clientX - r.left) / r.width) * L;
      const perto = validos.reduce((a, b) => (Math.abs(x(b.dt) - px) < Math.abs(x(a.dt) - px) ? b : a));
      cruz.setAttribute("x1", x(perto.dt)); cruz.setAttribute("x2", x(perto.dt));
      cruz.classList.remove("oculto");
      leitura.textContent = `${hora(perto.em)} — sessão ${Math.round(perto.sessao_pct)}%`
        + (perto.semana_pct != null ? ` · semana ${Math.round(perto.semana_pct)}%` : "");
    };
    svg.addEventListener("pointermove", ler);
    svg.addEventListener("pointerdown", ler);
  } else {
    add("text", {x: L / 2, y: A / 2, class: "orq-g-rotulo", "text-anchor": "middle"},
      "nenhuma medição hoje");
    leitura.textContent = "";
  }
  $("orq-grafico").replaceChildren(svg);
}

// ------------------------------------------------------------- decisões
function orqDesenharDecisoes(d) {
  const alvo = $("orq-decisoes");
  const lista = d.decisoes || [];
  if (!lista.length) {
    alvo.replaceChildren(el("div", {class: "fraco"}, "Nenhuma decisão registrada."));
    return;
  }
  alvo.replaceChildren(...lista.map((x) => {
    let botao;
    if (x.contestada) {
      botao = el("span", {class: "selo trabalhando"}, "contestada · no Grimório");
    } else {
      botao = el("button", {class: "acao"}, "Contestar");
      botao.addEventListener("click", async () => {
        const comentario = await orqPerguntarTexto(`Contestar: ${x.titulo}`,
          "Vira uma pergunta no Grimório; a sua resposta vale sobre a escolha dele.",
          "O que está errado (opcional)");
        if (comentario === null) return;
        try {
          const r = await api("/api/orquestrador/contestar", {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({id: x.id, comentario}),
          });
          avisar(`Virou o nó ${r.no} no Grimório` + (String(r.commit).startsWith("falhou")
            ? " (o commit ficou para depois)" : ""));
        } catch (err) { avisar(err.message, true); }
        orqCarregar();
      });
    }
    return el("div", {class: "linha orq-decisao"},
      el("span", {class: "corpo"},
        el("strong", {}, x.titulo),
        el("div", {}, "→ " + x.escolha),
        x.porque ? el("div", {class: "fraco"}, "porque: " + x.porque) : null,
        x.alternativa ? el("div", {class: "fraco"}, "alternativa: " + x.alternativa) : null,
        el("div", {class: "fraco"}, `${x.parte} · ${quandoCurto(x.em)}`)),
      botao);
  }));
}

// -------------------------------------------------------------- acessos
function orqDetalhes(titulo, filhos) {
  return el("details", {class: "orq-detalhes"}, el("summary", {}, titulo), ...filhos);
}

function orqDesenharAcessos(d) {
  const a = d.acessos;
  const alvo = $("orq-acessos");
  if (!a) {
    alvo.replaceChildren(el("div", {class: "fraco"},
      "Ainda não gerado (o servidor gera ao subir; ou rode "
      + "python -m remoto.orquestrador acessos)."));
    return;
  }
  const app = a.app || {};
  const disparos = app.ligadas
    ? [el("div", {}, `Publica: ${app.publicar ? "sim" : "não"} · destino padrão: `
        + `${app.destino_padrao || "—"} · ${app.quem_publica || ""}`),
       el("div", {}, `Zona de perigo: ${app.perigosas ? "ligada (digitar o alvo)" : "desligada"}`
        + ` · teto de ${app.limite_por_hora} por hora`),
       el("div", {class: "fraco"}, (app.acoes || []).map((x) => x.rotulo).join(" · "))]
    : [el("div", {class: "fraco"}, app.erro ? `não consegui ler: ${app.erro}`
        : "As ações estão desligadas neste servidor.")];
  const contas = (a.contas || []).map((s) => s.erro ? el("div", {class: "erro"}, s.erro)
    : el("div", {class: "linha"}, el("span", {class: "corpo"},
      el("strong", {}, s.rotulo + (s.publica ? " · publica" : "")),
      el("div", {class: "fraco"}, s.canais.map((c) => `${c.canal}: ${c.conta}`
        + (c.destino ? ` → ${c.destino}` : "") + (c.propria ? "" : " (herdada)")).join(" · ")))));
  alvo.replaceChildren(
    el("div", {class: "fraco"}, `gerado ${quandoCurto(a.gerado_em)} · permissões: `
      + `${a.modo_permissao} · rede: ${(a.servidor || {}).rede || "—"}`),
    orqDetalhes(`O que o app dispara`, disparos),
    orqDetalhes(`Agentes (${(a.agentes || []).length})`, (a.agentes || []).map((g) =>
      el("div", {class: "linha"}, el("span", {class: "corpo"}, el("strong", {}, g.nome),
        el("div", {class: "fraco"}, g.descricao))))),
    orqDetalhes(`Conectores (${(a.conectores || []).length})`, [
      el("div", {}, (a.conectores || []).join(" · ") || "nenhum"),
      ...(a.recursos || []).map((r) => el("div", {class: "fraco"}, `${r.nome}: ${r.situacao}`))]),
    orqDetalhes(`Contas (${(a.contas || []).length} serviços, sem segredo)`, contas));
}

// ---------------------------------------------------------------- fluxo
function orqDesenharFluxoTrabalho(d) {
  const e = d.estado;
  const passo = (rotulo, n) => el("span", {class: "orq-passo"}, el("strong", {}, String(n)), rotulo);
  $("orq-fluxo-trabalho").replaceChildren(el("div", {class: "orq-fluxo-linha"},
    passo("na fila", (e.fila || []).length), el("span", {}, "→"),
    passo("agora", (e.agora || []).length), el("span", {}, "→"),
    passo("feitos hoje", (e.concluidos_hoje || []).length)),
    el("div", {class: "fraco"}, `Você manda → pendente → o orquestrador aplica ou recusa. `
      + `${d.pendentes} comando(s) esperando.`));
}

async function orqCarregarFluxo() {
  const alvo = $("orq-fluxo");
  try {
    const f = await api("/api/orquestrador/fluxo");
    if (f.calculando) {
      alvo.replaceChildren(el("div", {class: "fraco"}, "lendo a pipeline…"));
      setTimeout(() => { if (tela === "orquestrador") orqCarregarFluxo(); }, 3000);
      return;
    }
    if (f.falhou) {
      alvo.replaceChildren(el("div", {class: "erro"}, `não consegui ler o fluxo: ${f.falhou}`));
      return;
    }
    const fila = f.fila || {};
    const topo = el("div", {class: "fraco"}, `Pipeline das builds · fila: ${fila.pending ?? 0} `
      + `esperando, ${fila.running ?? 0} rodando, ${fila.failed ?? 0} com falha · `
      + `última atividade ${f.ultima_atividade} · torneio: ${f.torneio.prontos ?? "—"} pronta(s)`
      + ` · arena: ${f.arena.lutas ?? 0} luta(s)`);
    const alertas = (f.alertas || []).map((a) => el("div", {class: "erro"}, "! " + a));
    const linhas = (f.geracoes || []).map((g) => el("div", {class: "linha"},
      el("span", {class: "corpo"},
        el("strong", {}, `${g.id.replace("generation_", "#")} ${g.personagem || ""}`),
        el("div", {class: "orq-etapas"}, f.etapas.map((e) =>
          `${ORQ_SIMBOLO[g.etapas[e.id]] || "·"} ${e.rotulo}`).join("  ")),
        el("div", {class: "fraco"}, g.proximo))));
    alvo.replaceChildren(topo, ...alertas, ...linhas,
      el("div", {class: "fraco"}, "✓ pronto  ▶ gerando  … na fila  ✕ falhou  · não começou"));
  } catch (err) {
    alvo.replaceChildren(el("div", {class: "erro"}, "fluxo: " + err.message));
  }
}

// ------------------------------------------------------------- comandos
function orqValor(c) {
  const v = c.valor;
  if (v == null) return "";
  if (c.comando === "forca_total") return v ? `ligar (${v} min antes)` : "desligar";
  if (c.comando === "priorizar") return `${v.direcao}`;
  if (c.comando === "contestar") return v.titulo || "";
  if (c.comando === "teto_uso") return `${v}%`;
  if (c.comando === "tirar_da_fila") {
    const f = ((Orq.dados && Orq.dados.estado.fila) || []).find((x) => x.id === v);
    return f ? f.item : v;
  }
  if (c.comando === "adicionar_a_fila") return `[${v.parte}] ${v.item}`;
  return typeof v === "object" ? JSON.stringify(v) : String(v);
}

function orqDesenharComandos(d) {
  const alvo = $("orq-comandos");
  const lista = d.comandos || [];
  if (!lista.length) {
    alvo.replaceChildren(el("div", {class: "fraco"}, "Nada mandado ainda."));
    return;
  }
  alvo.replaceChildren(...lista.slice(0, 20).map((c) => {
    const classe = c.situacao === "aplicado" ? "ok" : c.situacao === "recusado" ? "erro"
      : "trabalhando";
    const valor = orqValor(c);
    return el("div", {class: "linha"},
      el("span", {class: "corpo"}, c.rotulo + (valor ? `: ${valor}` : ""),
        el("div", {class: "fraco"}, quandoCurto(c.em) + ` · ${ORQ_FONTE[c.fonte || "app"]}`
          + (c.aplicado_em ? ` · ${c.situacao} ${orqHora(c.aplicado_em)}` : "")),
        c.motivo ? el("div", {class: "erro"}, "motivo: " + c.motivo) : null,
        c.nota ? el("div", {class: "fraco"}, c.nota) : null),
      el("span", {class: "selo " + classe}, c.situacao));
  }));
}

// ---------------------------------------------------------------- ciclo
async function orqCarregar() {
  try {
    const d = await api("/api/orquestrador");
    Orq.dados = d;
    orqFaixa(d);
    orqDesenharAgora(d);
    orqDesenharFila(d);
    orqDesenharCapacidade(d);
    orqDesenharLimites(d);
    orqDesenharDecisoes(d);
    orqDesenharAcessos(d);
    orqDesenharFluxoTrabalho(d);
    orqDesenharComandos(d);
    orqMarcarSelo(d);
    conexao(true);
  } catch (err) { conexao(false, err); }
}

// O objeto na prateleira avisa sem abrir: vermelho = passou do teto ou
// orquestrador fora do ar; âmbar = comando esperando.
function orqMarcarSelo(d) {
  const obj = $("obj-orquestrador");
  obj.classList.toggle("selo-alerta", !!(d.fora_do_ar || (d.uso && d.uso.passou_teto)));
  obj.classList.toggle("selo-pendente", !!d.pendentes);
}

async function orquestradorSelo() {
  if (Date.now() - Orq.seloEm < ORQ_SELO_MS) return;
  Orq.seloEm = Date.now();
  try { orqMarcarSelo(await api("/api/orquestrador")); } catch (err) { /* a vila já avisa */ }
}

function orquestradorMostrar() {
  orqCarregar();
  orqCarregarFluxo();
  clearInterval(Orq.relogio);
  clearInterval(Orq.relogioFluxo);
  Orq.relogio = setInterval(() => {
    if (document.visibilityState === "visible") orqCarregar();
  }, ORQ_MS);
  Orq.relogioFluxo = setInterval(() => {
    if (document.visibilityState === "visible") orqCarregarFluxo();
  }, ORQ_FLUXO_MS);
}

function orquestradorParar() {
  clearInterval(Orq.relogio); Orq.relogio = null;
  clearInterval(Orq.relogioFluxo); Orq.relogioFluxo = null;
}

$("orq-adicionar-fila").addEventListener("click", orqPorNaFila);
$("orq-pausar-fila").addEventListener("click", () => orqEnviar("pausar_fila"));
$("orq-retomar-fila").addEventListener("click", () => orqEnviar("retomar_fila"));
$("orq-enviar").addEventListener("click", async () => {
  const texto = $("orq-mensagem").value.trim();
  if (!texto) { avisar("a mensagem está vazia", true); return; }
  await orqEnviar("mensagem", texto);
  $("orq-mensagem").value = "";
});
for (const b of document.querySelectorAll("[data-orq]"))
  b.addEventListener("click", () => $(b.dataset.orq).scrollIntoView({behavior: "smooth"}));
