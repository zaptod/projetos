"use strict";
// A tela DECISOES: o que o Adrian precisa decidir, com os videos e imagens
// para olhar, e as opcoes para responder. Pedido dele em 28/09/2026.
//
// A midia e pedida pelo id do item e pelo indice (nunca por caminho): o PC
// devolve um bilhete de 10 minutos, o mesmo dos videos do catalogo, e o
// <video> toca por Range. Bilhete vencido (pausou e voltou depois): pede outro
// e segue de onde parou.

const Decisoes = {aba: "pendentes", dados: null, aberta: null};

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
  decisoesDesenharLista();
}

function decisoesDesenharLista() {
  const {pendentes = [], respondidas = []} = Decisoes.dados || {};
  const abas = $("decisoes-abas");
  abas.replaceChildren();
  for (const [nome, rotulo, n] of [["pendentes", "Pendentes", pendentes.length],
                                   ["respondidas", "Respondidas", respondidas.length]]) {
    const b = el("button", {class: "acao",
                            "aria-pressed": String(Decisoes.aba === nome)},
                 `${rotulo} (${n})`);
    b.addEventListener("click", () => { Decisoes.aba = nome; decisoesDesenharLista(); });
    abas.append(b);
  }
  const alvo = $("decisoes-lista");
  alvo.replaceChildren();
  const itens = Decisoes.aba === "pendentes" ? pendentes : respondidas;
  if (!itens.length) {
    alvo.append(el("div", {class: "cartao ok"}, Decisoes.aba === "pendentes"
      ? "✓ nada para decidir agora" : "nenhuma respondida ainda"));
    return;
  }
  for (const item of itens) {
    const midias = item.midias.length
      ? `${item.midias.length} mídia(s)` : "sem mídia";
    const cartao = el("button", {class: "cartao decisao-cartao"},
      el("div", {class: "decisao-titulo"}, item.titulo),
      item.pergunta ? el("div", {class: "fraco"}, item.pergunta) : null,
      item.resposta
        ? el("div", {class: "ok"}, "→ " + item.resposta.opcao_rotulo
            + (item.resposta.comentario ? ` · “${item.resposta.comentario}”` : ""))
        : el("div", {class: "fraco"}, midias + " · " + item.opcoes.length + " opções"));
    cartao.addEventListener("click", () => decisoesAbrir(item));
    alvo.append(cartao);
  }
}

async function decisoesUrl(item, m) {
  const r = await api(`/api/decisao/${encodeURIComponent(item.id)}/midia/${m.indice}`);
  return r.url;
}

function decisoesMidia(item, m, muitos) {
  const caixa = el("div", {class: "decisao-midia"},
    el("div", {class: "decisao-rotulo"}, m.rotulo || m.nome,
      m.rotulo ? el("span", {class: "fraco"}, "  " + m.nome) : null));
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
      caixa.append(el("div", {class: "erro"}, "não abriu: " + err.message));
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

function decisoesAbrir(item) {
  decisoesParar();
  Decisoes.aberta = item;
  $("decisoes-listas").classList.add("oculto");
  const caixa = $("decisao-item");
  caixa.classList.remove("oculto");
  caixa.replaceChildren();

  const voltar = el("button", {class: "acao"}, "‹ Voltar");
  voltar.addEventListener("click", decisoesMostrar);
  caixa.append(el("div", {class: "botoes"}, voltar));

  const cabeca = el("div", {class: "cartao"},
    el("h2", {}, item.titulo),
    item.pergunta ? el("p", {class: "decisao-pergunta"}, item.pergunta) : null,
    item.contexto ? el("p", {class: "fraco"}, item.contexto) : null);
  caixa.append(cabeca);

  if (item.midias.length) {
    const midias = el("div", {class: "cartao"});
    // Ate seis, cada video ja traz a duracao (so os metadados, por Range);
    // mais que isso (os doze duelos do zombie), so carrega quando tocar.
    const muitos = item.midias.length > 6;
    for (const m of item.midias) midias.append(decisoesMidia(item, m, muitos));
    caixa.append(midias);
  }

  const escolha = el("div", {class: "cartao"});
  if (item.resposta) {
    escolha.append(el("h2", {}, "Sua resposta"),
      el("div", {class: "ok"}, item.resposta.opcao_rotulo),
      item.resposta.comentario ? el("p", {}, item.resposta.comentario) : null,
      el("div", {class: "fraco"}, "em " + quandoCurto(item.resposta.em)));
    caixa.append(escolha);
    return;
  }

  escolha.append(el("h2", {}, "Sua decisão"));
  let marcada = null;
  const botoes = item.opcoes.map((o, n) => {
    const b = el("button", {class: "acao decisao-opcao", "aria-pressed": "false"},
      el("div", {}, o.rotulo),
      o.descricao ? el("div", {class: "fraco"}, o.descricao) : null);
    b.addEventListener("click", () => {
      marcada = n;
      for (const outro of botoes) outro.setAttribute("aria-pressed", String(outro === b));
      comentario.placeholder = o.pede_comentario
        ? "Esta opção pede um comentário" : "Comentário (opcional)";
      enviar.disabled = false;
    });
    return b;
  });
  escolha.append(...botoes);
  const comentario = el("textarea", {class: "decisao-comentario", rows: "3",
                                     maxlength: "2000",
                                     placeholder: "Comentário (opcional)"});
  if (!item.comentario) comentario.classList.add("oculto");
  escolha.append(comentario);
  const enviar = el("button", {class: "acao primario"}, "Responder");
  enviar.disabled = true;
  enviar.addEventListener("click", async () => {
    if (marcada === null) return;
    enviar.disabled = true;
    try {
      await api("/api/decisao/responder", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({id: item.id, opcao: marcada,
                              comentario: comentario.value}),
      });
      avisar("Resposta registrada: " + item.opcoes[marcada].rotulo);
      Decisoes.aba = "pendentes";
      decisoesMostrar();
    } catch (err) {
      avisar(err.message, true);
      enviar.disabled = false;
    }
  });
  escolha.append(el("div", {class: "botoes"}, enviar));
  caixa.append(escolha);
}
