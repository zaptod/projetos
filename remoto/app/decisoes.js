"use strict";
// A tela DECISOES: a arvore de habilidades do Adrian, uma aba por projeto.
// Pedido dele em 28/09/2026. Cada no e uma decisao, colorido pela situacao
// (bloqueada, pendente, decidida, a rever). Tocar abre a pergunta, a midia
// tocando, as opcoes, o comentario e o historico. Da para mudar uma decisao
// ja tomada: antes, a tela mostra o que vai para "a rever".
//
// A midia e pedida pelo id do item e pelo indice (nunca por caminho): o PC
// devolve um bilhete de 10 minutos e o <video> toca por Range. Bilhete vencido
// (pausou e voltou depois): pede outro e segue de onde parou.

const Decisoes = {projeto: null, dados: null, aberta: null};
const SITUACAO = {decidida: ["✅", "decidida"], pendente: ["⏳", "pendente"],
                  bloqueada: ["🔒", "bloqueada"], a_rever: ["↺", "a rever"]};
// O leitor (28/09/2026): cada resposta dele é LIDA pelo orquestrador, que
// registra o que ela gerou (tarefa da Mesa, ramo novo ou nada). Até lá, o nó
// leva o selo "não lida ainda"; o estado da tarefa vem da Mesa, ao vivo.
const TAREFA = {concluida: ["✓", "concluída", "ok"], andamento: ["⚙", "em andamento", "trabalhando"],
                parando: ["⏸", "parando", "trabalhando"], fila: ["…", "na fila", "fraco"],
                falhou: ["✗", "falhou", "erro"], parada: ["■", "parada", "fraco"],
                desconhecida: ["?", "fora da Mesa", "fraco"],
                sem_leitura: ["?", "Mesa ilegível", "erro"]};
// De onde veio cada linha do histórico ("app" = respondida aqui, sem rótulo).
const ORIGEM_NO_HISTORICO = {semente: "antes da árvore", mesa: "pela Mesa de comando",
                             chat: "no chat", cli: "pelo orquestrador", correcao: "correção"};

function decisoesParar() {
  for (const v of document.querySelectorAll("#tela-decisoes video")) v.pause();
}

async function decisoesMostrar() {
  decisoesParar();
  Decisoes.aberta = null;
  $("decisao-item").classList.add("oculto");
  $("decisoes-listas").classList.remove("oculto");
  try {
    Decisoes.dados = await api("/api/decisoes");
    conexao(true);
  } catch (err) {
    conexao(false, err);
    $("decisoes-lista").replaceChildren(el("div", {class: "erro"},
      "Não consegui carregar: " + err.message));
    return;
  }
  if (!Decisoes.projeto) {
    // Abre no primeiro projeto com algo esperando por ele.
    const esperando = Decisoes.dados.projetos.find(
      (p) => p.contagem.pendente + p.contagem.a_rever > 0);
    Decisoes.projeto = (esperando || Decisoes.dados.projetos[0]).id;
  }
  decisoesDesenharArvore();
}

function decisoesDesenharArvore() {
  const {projetos, arvores, itens} = Decisoes.dados;
  const abas = $("decisoes-abas");
  abas.replaceChildren();
  for (const p of projetos) {
    const n = p.contagem.pendente + p.contagem.a_rever;
    const lidas = p.contagem.nao_lidas || 0;
    const b = el("button", {class: "acao",
                            "aria-pressed": String(Decisoes.projeto === p.id)},
                 p.rotulo + (n ? ` (${n})` : ""),
                 lidas ? el("span", {class: "nao-lidas-n",
                                     title: `${lidas} resposta(s) não lida(s)`}, String(lidas))
                   : null);
    b.addEventListener("click", () => { Decisoes.projeto = p.id; decisoesDesenharArvore(); });
    abas.append(b);
  }
  const alvo = $("decisoes-lista");
  alvo.replaceChildren();
  const nos = arvores[Decisoes.projeto] || [];
  const doProjeto = projetos.find((p) => p.id === Decisoes.projeto);
  const naoLidas = doProjeto ? doProjeto.contagem.nao_lidas || 0 : 0;
  if (naoLidas) {
    alvo.append(el("div", {class: "cartao contador-nao-lidas"},
      el("span", {class: "selo nao-lida"}, `📨 ${naoLidas}`),
      ` ${naoLidas === 1 ? "resposta sua ainda não lida" : "respostas suas ainda não lidas"}`
        + " pelo orquestrador"));
  }
  if (!nos.length) {
    alvo.append(el("div", {class: "cartao fraco"}, "Nenhuma decisão neste projeto ainda."));
    return;
  }
  const caixa = el("div", {class: "cartao arvore"});
  for (const {id, nivel} of nos) {
    const item = itens[id];
    const [icone, nome] = SITUACAO[item.situacao] || ["•", item.situacao];
    const resumo = item.vigente ? "→ " + item.vigente.opcao_rotulo
      : item.situacao === "bloqueada"
        ? "espera: " + item.depende_de.filter((d) => !d.ok)
            .map((d) => `${d.titulo} = ${d.opcao_rotulo}`).join(", ")
        : item.pergunta;
    // Nivel por classe, nao por `style`: a CSP da casca nao deixa estilo inline.
    const gerou = decisoesResumoGerou(item);
    const no = el("button", {class: `no sit-${item.situacao} nivel-${Math.min(nivel, 5)}`},
      el("span", {class: "no-icone", title: nome}, icone),
      el("span", {class: "no-corpo"},
        el("span", {class: "no-titulo"}, item.titulo,
          item.nao_lidas ? el("span", {class: "selo nao-lida"}, "não lida") : null),
        resumo ? el("span", {class: "fraco no-resumo"}, resumo) : null,
        gerou ? el("span", {class: "fraco no-gerou"}, "gerou: " + gerou) : null));
    no.addEventListener("click", () => decisoesAbrir(id));
    caixa.append(no);
  }
  alvo.append(caixa, el("div", {class: "fraco legenda"},
    "✅ decidida · ⏳ pendente · 🔒 bloqueada · ↺ a rever"));
}

function decisoesResumoGerou(item) {
  const cs = item.consequencias || [];
  const tarefas = new Set(cs.filter((c) => c.tipo === "tarefa").map((c) => c.alvo)).size;
  const ramos = new Set(cs.filter((c) => c.tipo === "no").map((c) => c.alvo)).size;
  const partes = [];
  if (tarefas) partes.push(tarefas === 1 ? "1 tarefa" : `${tarefas} tarefas`);
  if (ramos) partes.push(ramos === 1 ? "1 ramo" : `${ramos} ramos`);
  if (!partes.length && cs.length) partes.push("nada novo");
  return partes.join(" · ");
}

// "O que isto gerou": as tarefas (estado ao vivo, da Mesa) e os ramos, que
// abrem ao tocar. Sem nada e sem resposta não lida, o cartão não aparece.
function decisoesGerou(item) {
  const cs = item.consequencias || [];
  if (!cs.length && !item.nao_lidas) return null;
  const caixa = el("div", {class: "cartao gerou"}, el("h2", {}, "O que isto gerou"));
  if (item.nao_lidas) {
    caixa.append(el("div", {class: "fraco"},
      "O orquestrador ainda não leu " + (item.nao_lidas === 1 ? "a sua resposta"
        : `${item.nao_lidas} respostas suas`) + ". O que ela gerar aparece aqui."));
  }
  const vigente = item.vigente ? item.vigente.opcao : null;
  let notaAnterior = null;
  for (const c of cs) {
    const antiga = vigente && c.opcao !== vigente
      ? el("div", {class: "fraco"}, `pela resposta anterior: ${c.opcao_rotulo}`) : null;
    // Uma leitura que gerou varias coisas tem uma nota so: aparece na primeira.
    const nota = c.nota && c.nota !== notaAnterior ? el("div", {class: "fraco"}, c.nota) : null;
    notaAnterior = c.nota;
    if (c.tipo === "tarefa") {
      const t = c.tarefa || {};
      const [ic, rot, cls] = TAREFA[t.situacao] || TAREFA.desconhecida;
      caixa.append(el("div", {class: "linha gerou-tarefa"},
        el("span", {class: "emoji"}, "📋"),
        el("span", {class: "corpo"}, t.titulo || `tarefa ${c.alvo}`,
          el("div", {class: "fraco"}, `tarefa ${c.alvo}` + (t.parte ? ` · ${t.parte}` : "")),
          nota, antiga),
        el("span", {class: `selo ${cls}`}, `${ic} ${rot}`)));
    } else if (c.tipo === "no") {
      const n = c.no || {};
      const [ic, nome] = SITUACAO[n.situacao] || ["•", "sumiu"];
      const corpo = el("span", {class: "corpo"});
      if (n.existe) {
        const link = el("button", {class: "link"}, n.titulo);
        link.addEventListener("click", () => decisoesAbrir(n.id));
        corpo.append(link);
      } else {
        corpo.append(el("span", {class: "erro"}, `${c.alvo} (não existe mais)`));
      }
      corpo.append(el("div", {class: "fraco"}, "ramo novo"
        + (n.projeto && n.projeto !== item.projeto ? ` · ${n.projeto}` : "")));
      if (nota) corpo.append(nota);
      if (antiga) corpo.append(antiga);
      caixa.append(el("div", {class: "linha gerou-no"},
        el("span", {class: "emoji"}, "🌿"), corpo,
        el("span", {class: `selo sit-${n.situacao}`}, `${ic} ${nome}`)));
    } else {
      caixa.append(el("div", {class: "linha gerou-nada"},
        el("span", {class: "emoji"}, "·"),
        el("span", {class: "corpo"}, "Nada novo: nem tarefa, nem ramo", nota, antiga)));
    }
  }
  return caixa;
}

async function decisoesUrl(item, m) {
  const r = await api(`/api/decisao/${encodeURIComponent(item.id)}/midia/${m.indice}`);
  return r.url;
}

function decisoesMidia(item, m, muitos) {
  const caixa = el("div", {class: "decisao-midia"},
    el("div", {class: "decisao-rotulo"}, m.rotulo || m.nome,
      m.rotulo ? el("span", {class: "fraco"}, "  " + m.nome) : null));
  if (!m.existe || !m.tipo) {
    caixa.append(el("div", {class: "erro"}, "mídia não existe mais"));
    return caixa;
  }
  const video = m.tipo.startsWith("video/");
  const alvo = video
    ? el("video", {controls: "", playsinline: "",
                   preload: muitos ? "none" : "metadata"})
    : el("img", {alt: m.rotulo || m.nome});
  caixa.append(alvo);
  let renovacoes = 0;
  const carregar = async (desde = 0) => {
    try {
      alvo.src = await decisoesUrl(item, m);
      if (video && desde) alvo.currentTime = desde;
    } catch (err) {
      caixa.append(el("div", {class: "erro"}, err.message));
    }
  };
  if (video) {
    alvo.addEventListener("error", () => {
      if (renovacoes >= 3) return;
      renovacoes += 1;
      carregar(alvo.currentTime || 0);
    });
    // Tocar um pausa os outros: doze duelos juntos nao cabem no ouvido.
    alvo.addEventListener("play", () => {
      for (const v of document.querySelectorAll("#tela-decisoes video"))
        if (v !== alvo) v.pause();
    });
  }
  carregar();
  return caixa;
}

function decisoesAbrir(id) {
  decisoesParar();
  const {itens} = Decisoes.dados;
  const item = itens[id];
  Decisoes.aberta = id;
  // Um ramo pode ser de outro projeto: o "‹ Árvore" volta para a árvore dele.
  Decisoes.projeto = item.projeto;
  $("decisoes-listas").classList.add("oculto");
  const caixa = $("decisao-item");
  caixa.classList.remove("oculto");
  caixa.replaceChildren();

  const voltar = el("button", {class: "acao"}, "‹ Árvore");
  voltar.addEventListener("click", decisoesMostrar);
  caixa.append(el("div", {class: "botoes"}, voltar));

  const [icone, nome] = SITUACAO[item.situacao] || ["•", item.situacao];
  const cabeca = el("div", {class: "cartao"},
    el("div", {class: `selo sit-${item.situacao}`}, `${icone} ${nome}`),
    item.nao_lidas ? el("div", {class: "selo nao-lida"}, "📨 não lida ainda") : null,
    el("h2", {class: "decisao-h"}, item.titulo),
    item.pergunta ? el("p", {class: "decisao-pergunta"}, item.pergunta) : null,
    item.contexto ? el("p", {class: "fraco"}, item.contexto) : null);
  if (item.depende_de.length) {
    const deps = el("div", {class: "fraco"}, "Depende de: ");
    item.depende_de.forEach((d, n) => {
      const link = el("button", {class: "link"},
        `${d.ok ? "✓" : "✗"} ${d.titulo} = ${d.opcao_rotulo}`);
      link.addEventListener("click", () => decisoesAbrir(d.decisao));
      if (n) deps.append(" · ");
      deps.append(link);
    });
    cabeca.append(deps);
  }
  caixa.append(cabeca);
  const gerou = decisoesGerou(item);
  if (gerou) caixa.append(gerou);

  if (item.midias.length) {
    const midias = el("div", {class: "cartao"});
    // Ate seis, cada video ja traz a duracao (so os metadados, por Range);
    // mais que isso (os doze duelos do zombie), so carrega quando tocar.
    const muitos = item.midias.length > 6;
    for (const m of item.midias) midias.append(decisoesMidia(item, m, muitos));
    caixa.append(midias);
  }

  const escolha = el("div", {class: "cartao"});
  escolha.append(el("h2", {}, item.vigente ? "Mudar a decisão" : "Sua decisão"));
  if (item.situacao === "bloqueada") {
    escolha.append(el("div", {class: "fraco"},
      "Bloqueada: decida antes " + item.depende_de.filter((d) => !d.ok)
        .map((d) => `“${d.titulo}” = ${d.opcao_rotulo}`).join(" e ") + "."));
  }
  let marcada = null;
  const aviso = el("div", {class: "decisao-respec oculto"});
  const botoes = item.opcoes.map((o) => {
    const vigente = item.vigente && item.vigente.opcao === o.id;
    const b = el("button", {class: "acao decisao-opcao" + (vigente ? " vigente" : ""),
                            "aria-pressed": "false"},
      el("div", {}, o.rotulo + (vigente ? "  · vigente" : "")),
      o.descricao ? el("div", {class: "fraco"}, o.descricao) : null);
    if (item.situacao === "bloqueada") b.disabled = true;
    b.addEventListener("click", () => {
      marcada = o.id;
      for (const outro of botoes) outro.setAttribute("aria-pressed", String(outro === b));
      comentario.placeholder = o.pede_comentario
        ? "Esta opção pede um comentário" : "Comentário (opcional)";
      // O "respec": trocar a opcao manda para "a rever" o que dependia dela.
      const troca = item.vigente && item.vigente.opcao !== o.id;
      const afetados = troca ? item.a_rever_se_mudar : [];
      aviso.classList.toggle("oculto", !afetados.length);
      aviso.replaceChildren();
      if (afetados.length) {
        aviso.append("Mudar esta decisão manda para “a rever”: ",
          afetados.map((a) => a.titulo).join(", "), ".");
      }
      enviar.disabled = false;
      enviar.textContent = vigente ? "Confirmar de novo" : item.vigente ? "Mudar" : "Responder";
    });
    return b;
  });
  escolha.append(...botoes, aviso);
  const comentario = el("textarea", {class: "decisao-comentario", rows: "3",
                                     maxlength: "2000",
                                     placeholder: "Comentário (opcional)"});
  if (!item.comentario || item.situacao === "bloqueada") comentario.classList.add("oculto");
  escolha.append(comentario);
  const enviar = el("button", {class: "acao primario"}, "Responder");
  enviar.disabled = true;
  if (item.situacao === "bloqueada") enviar.classList.add("oculto");
  enviar.addEventListener("click", async () => {
    if (marcada === null) return;
    enviar.disabled = true;
    try {
      const r = await api("/api/decisao/responder", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({id: item.id, opcao: marcada, comentario: comentario.value}),
      });
      const ev = r.evento;
      let texto = "Registrado: " + ev.opcao_rotulo;
      if (ev.a_rever && ev.a_rever.length) texto += ` · ${ev.a_rever.length} foram para “a rever”`;
      const falhou = String(ev.commit || "").startsWith("falhou");
      if (falhou) texto += " · o commit ficou para depois";
      avisar(texto, falhou);
      decisoesMostrar();
    } catch (err) {
      avisar(err.message, true);
      enviar.disabled = false;
    }
  });
  escolha.append(el("div", {class: "botoes"}, enviar));
  caixa.append(escolha);

  if (item.historico.length) {
    const hist = el("div", {class: "cartao"}, el("h2", {}, "Histórico"));
    for (const h of [...item.historico].reverse()) {
      hist.append(el("div", {class: "linha"},
        el("span", {class: "corpo"}, h.opcao_rotulo,
          h.comentario ? el("div", {class: "fraco"}, `“${h.comentario}”`) : null,
          h.nota ? el("div", {class: "fraco"}, `correção: ${h.nota}`) : null),
        el("span", {class: "fraco"},
          (ORIGEM_NO_HISTORICO[h.origem] ? ORIGEM_NO_HISTORICO[h.origem] + " · " : "")
          + String(h.em || "").slice(0, 16).replace("T", " "))));
    }
    caixa.append(hist);
  }
}
