"use strict";
// A tela CONVERSA (Vila das IAs, fase 2, 29/09/2026): o Adrian fala com uma
// IA pelo app. Tocar num prédio de IA -> "Conversar" abre esta tela por cima
// da Vila, com o histórico da CASA daquela IA (o chat de longa duração,
// decisão `ias-chat-persistente`), a caixa de texto e um anexo opcional.
//
// Nada aqui abre navegador: a mensagem vai para o CORREIO do PC
// (`ias/correio.py`), o CARTEIRO (`python -m ias carteiro`) a entrega e
// grava a resposta; a tela relê a caixa a cada 6 s e mostra cada mensagem
// como "na caixa", "entregue · esperando a resposta", "respondida" ou
// "falhou: motivo". Enquanto esta tela está aberta o PC sabe que ele está
// olhando (presença) e a resposta NÃO vai ao Telegram; fora dela, vai.
//
// O Grok não tem prédio na Vila ainda (é do painel-e-vila): daqui ele entra
// pelos chips, junto das outras três.

const Conversa = {ia: null, dados: null, relogio: null, anexo: null, enviando: false,
                  assinatura: "", rolarNoFim: true};
const CONVERSA_MS = 6000;
const CONVERSA_IAS = [["deepseek", "🐋", "DeepSeek"], ["chatgpt", "🤖", "ChatGPT"],
                      ["gemini", "✨", "Gemini"], ["grok", "🚀", "Grok"]];
const CONVERSA_ROTULO = Object.fromEntries(CONVERSA_IAS.map(([ia, e, r]) => [ia, `${e} ${r}`]));

function conversaAbrir(ia, origem) {
  Conversa.ia = CONVERSA_IAS.some(([x]) => x === ia) ? ia : "deepseek";
  Conversa.assinatura = "";
  abrir("conversa", origem);
}

function conversaChips() {
  $("conversa-ias").replaceChildren(...CONVERSA_IAS.map(([ia, emoji, rotulo]) => {
    const b = el("button", {class: "acao", "data-ia": ia, "aria-pressed": String(ia === Conversa.ia)},
      `${emoji} ${rotulo}`);
    b.addEventListener("click", () => {
      if (Conversa.ia === ia) return;
      Conversa.ia = ia;
      Conversa.assinatura = "";
      Conversa.rolarNoFim = true;
      conversaChips();
      conversaCarregar();
    });
    return b;
  }));
}

// O que a linha de situação de uma mensagem diz, e a cor dela.
function conversaSituacao(m) {
  if (m.situacao === "respondida") {
    const dur = m.dur_s ? ` em ${Math.round(m.dur_s)} s` : "";
    return [`respondida ${hora(m.respondida_em || m.atualizado_em)}${dur}`
      + (m.modelo ? ` · ${m.modelo}` : ""), "ok"];
  }
  if (m.situacao === "falhou") return [`falhou: ${m.erro || "sem motivo"}`, "erro"];
  if (m.situacao === "entregue")
    return [`entregue ${hora(m.entregue_em || m.atualizado_em)} · esperando a resposta…`,
            "trabalhando"];
  if (m.nota) return [m.nota, "trabalhando"];
  return ["na caixa, esperando o carteiro", "fraco"];
}

// O carteiro, dito para quem está olhando ESTA caixa.
function conversaTextoDoCarteiro(c, ia) {
  if (!c || c.situacao === "nunca")
    return ["nenhum carteiro rodou ainda: a mensagem fica na caixa até ele subir "
            + "(no PC: python -m ias carteiro)", "erro"];
  const rot = CONVERSA_ROTULO[c.ia] || c.ia || "";
  const ha = c.pulso_ha_s != null ? ` (sinal ${hora(c.pulso_em)})` : "";
  if (c.situacao === "parado")
    return [`o carteiro está parado${ha}: a mensagem fica na caixa até ele voltar`, "erro"];
  if (c.situacao === "esperando_trava")
    return [`o carteiro está esperando a pipeline soltar a conta do ${rot}`, "trabalhando"];
  if (c.situacao === "resumindo")
    return [`o carteiro está pedindo ao ${rot} o resumo da casa`, "trabalhando"];
  if (c.situacao === "entregando") {
    if (c.ia === ia) return [`o carteiro está entregando ao ${rot}${c.nota ? " · " + c.nota : ""}`,
                             "trabalhando"];
    return [`o carteiro está com o ${rot} agora; a sua entra em seguida`, "trabalhando"];
  }
  return [`carteiro pronto${ha}`, "fraco"];
}

function conversaBalao(lado, ...filhos) {
  return el("div", {class: "balao " + lado}, ...filhos);
}

function conversaDesenhar(d) {
  const ia = Conversa.ia;
  $("titulo").textContent = `Conversa · ${d.rotulo || ia}`;
  const casa = d.casa || {};
  const partes = [];
  if (casa.geracao) {
    partes.push(`casa ${casa.geracao}ª · ${casa.mensagens || 0} mensagem(ns)`
      + (casa.tem_resumo ? ` · resumo ${hora(casa.ultimo_resumo_em)}` : ""));
  } else {
    partes.push("ainda sem casa: a primeira mensagem abre o chat de longa duração");
  }
  $("conversa-casa").textContent = partes.join(" · ");
  const [textoC, classeC] = conversaTextoDoCarteiro(d.carteiro, ia);
  const carteiro = $("conversa-carteiro");
  carteiro.textContent = "📮 " + textoC;
  carteiro.className = "conversa-carteiro " + classeC;

  const alvo = $("conversa-historico");
  const mensagens = d.mensagens || [];
  if (!mensagens.length) {
    alvo.replaceChildren(el("div", {class: "fraco conversa-vazia"},
      `Nenhuma mensagem para o ${d.rotulo || ia} ainda. Escreva abaixo: a resposta chega `
      + "aqui, vira balão na Vila e vai ao Telegram se você não estiver com o app aberto."));
  } else {
    alvo.replaceChildren(...mensagens.flatMap((m) => {
      const [sit, cls] = conversaSituacao(m);
      const eu = conversaBalao("eu",
        el("div", {class: "texto"}, m.texto),
        (m.anexos || []).length
          ? el("div", {class: "fraco"}, "📎 " + m.anexos.join(", ")) : null,
        el("div", {class: "situacao " + cls}, `${hora(m.em)} · ${sit}`));
      const saida = [eu];
      if (m.situacao === "respondida" && m.resposta != null) {
        saida.push(conversaBalao("ia",
          el("div", {class: "quem"}, d.rotulo || ia),
          el("div", {class: "texto"}, m.resposta)));
      }
      return saida;
    }));
  }
  if (d.ilegiveis) {
    alvo.appendChild(el("div", {class: "erro fraco"},
      `${d.ilegiveis} linha(s) ilegível(is) nesta caixa`));
  }
  $("conversa-enviar").disabled = Conversa.enviando || d.enviar === false;
  $("conversa-texto").placeholder = d.enviar === false
    ? "as ações estão desligadas neste servidor: só leitura"
    : `Escreva para o ${d.rotulo || ia}…`;
  if (Conversa.rolarNoFim) {
    alvo.lastElementChild?.scrollIntoView({block: "end"});
    Conversa.rolarNoFim = false;
  }
}

function conversaAssinatura(d) {
  return JSON.stringify((d.mensagens || []).map((m) => [m.id, m.situacao, m.atualizado_em]))
    + JSON.stringify(d.carteiro && [d.carteiro.situacao, d.carteiro.ia, d.carteiro.nota]);
}

async function conversaCarregar() {
  const ia = Conversa.ia;
  if (!ia) return;
  try {
    const d = await api(`/api/correio/${ia}?n=60`);
    if (Conversa.ia !== ia) return;
    Conversa.dados = d;
    const assinatura = conversaAssinatura(d);
    if (assinatura !== Conversa.assinatura) {
      const antes = Conversa.assinatura;
      Conversa.assinatura = assinatura;
      if (antes) Conversa.rolarNoFim = true;
      conversaDesenhar(d);
    }
    conexao(true);
    // ele viu as respostas: o balão na Vila e a conta de "não vistas" saem
    const naoVistas = (d.mensagens || []).some(
      (m) => (m.situacao === "respondida" || m.situacao === "falhou") && !m.visto);
    if (naoVistas && document.visibilityState === "visible") {
      await api(`/api/correio/${ia}/visto`, {method: "POST",
        headers: {"Content-Type": "application/json"}, body: "{}"}).catch(() => {});
    }
  } catch (err) {
    if (err.status !== 401) conexao(false, err);
  }
}

function conversaLerAnexo(arquivo) {
  return new Promise((ok, falha) => {
    const leitor = new FileReader();
    leitor.onload = () => ok(String(leitor.result).split(",")[1] || "");
    leitor.onerror = () => falha(new Error("não consegui ler a imagem"));
    leitor.readAsDataURL(arquivo);
  });
}

async function conversaEnviar() {
  const caixa = $("conversa-texto");
  const texto = caixa.value.trim();
  if (!texto) { avisar("a mensagem está vazia", true); return; }
  if (Conversa.enviando) return;
  Conversa.enviando = true;
  $("conversa-enviar").disabled = true;
  try {
    const anexos = [];
    if (Conversa.anexo) {
      anexos.push({nome: Conversa.anexo.name, b64: await conversaLerAnexo(Conversa.anexo)});
    }
    const r = await api(`/api/correio/${Conversa.ia}`, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({texto, anexos}),
    });
    caixa.value = "";
    Conversa.anexo = null;
    $("conversa-anexo").value = "";
    $("conversa-anexo-nome").textContent = "";
    const c = r.carteiro || {};
    if (c.situacao === "nunca" || c.situacao === "parado") {
      avisar("na caixa; o carteiro não está rodando, então ela espera ele voltar", true);
    } else {
      avisar("na caixa do " + (CONVERSA_ROTULO[Conversa.ia] || Conversa.ia)
        + (c.situacao === "entregando" || c.situacao === "esperando_trava"
          ? " (o carteiro está ocupado; a sua entra em seguida)" : "; o carteiro entrega"));
    }
    Conversa.rolarNoFim = true;
    await conversaCarregar();
  } catch (err) {
    avisar(err.message || "não deu para enviar", true);
  } finally {
    Conversa.enviando = false;
    $("conversa-enviar").disabled = false;
  }
}

function conversaMostrar() {
  if (!Conversa.ia) Conversa.ia = "deepseek";
  conversaChips();
  $("conversa-historico").replaceChildren(el("div", {class: "fraco"}, "carregando…"));
  Conversa.assinatura = "";
  Conversa.rolarNoFim = true;
  conversaCarregar();
  clearInterval(Conversa.relogio);
  Conversa.relogio = setInterval(() => {
    if (document.visibilityState === "visible") conversaCarregar();
  }, CONVERSA_MS);
}

function conversaParar() {
  clearInterval(Conversa.relogio);
  Conversa.relogio = null;
}

$("conversa-enviar").addEventListener("click", conversaEnviar);
$("conversa-anexo").addEventListener("change", (e) => {
  const arquivo = e.target.files && e.target.files[0];
  Conversa.anexo = arquivo || null;
  $("conversa-anexo-nome").textContent = arquivo
    ? `${arquivo.name} (${Math.round(arquivo.size / 1024)} KB)` : "";
});
$("conversa-texto").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) conversaEnviar();
});
