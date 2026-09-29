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
// PEDIR IMAGEM (29/09, tarde: "os modelos que geram imagem, eu preciso ter
// suporte para isso também"): quem gera imagem ganha o modo "🎨 Criar"
// (prompt, a proporção que a FICHA do gerador diz que ele oferece, e o
// modelo quando há escolha) e a "🖼 Galeria". O pedido entra no correio com
// `tipo: "imagem"`; a imagem volta no balão (miniatura; tocar abre em tela
// cheia, com baixar e compartilhar). Quem não gera hoje (DreamFace, Digen)
// aparece com o Criar desabilitado e o motivo da ficha. "🎲 Livre" é o
// rodízio: o carteiro escolhe o primeiro gerador com a conta livre.

const Conversa = {ia: null, modo: "texto", dados: null, relogio: null, ticker: null,
                  anexo: null, enviando: false, assinatura: "", rolarNoFim: true,
                  proporcao: {}, galeria: null};
const CONVERSA_MS = 6000;
const CONVERSA_IAS = [["deepseek", "🐋", "DeepSeek"], ["chatgpt", "🤖", "ChatGPT"],
                      ["gemini", "✨", "Gemini"], ["grok", "🚀", "Grok"],
                      ["picasso", "🎨", "PicassoIA"], ["dreamface", "🌙", "DreamFace"],
                      ["digen", "🎥", "Digen"], ["livre", "🎲", "Livre"]];
const CONVERSA_CHATS = new Set(["deepseek", "chatgpt", "gemini", "grok"]);
const CONVERSA_GERADORES = new Set(["picasso", "grok", "gemini", "chatgpt", "dreamface",
                                    "digen"]);
const CONVERSA_ROTULO = Object.fromEntries(CONVERSA_IAS.map(([ia, e, r]) => [ia, `${e} ${r}`]));

function conversaModoPadrao(ia) {
  return CONVERSA_CHATS.has(ia) ? "texto" : "imagem";
}

function conversaAbrir(ia, origem, modo) {
  Conversa.ia = CONVERSA_IAS.some(([x]) => x === ia) ? ia : "deepseek";
  Conversa.modo = modo || conversaModoPadrao(Conversa.ia);
  if (!CONVERSA_CHATS.has(Conversa.ia) && Conversa.modo === "texto") Conversa.modo = "imagem";
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
      // fica no modo em que estava, se a IA nova tiver ele
      if (Conversa.modo === "texto" && !CONVERSA_CHATS.has(ia)) Conversa.modo = "imagem";
      if (Conversa.modo !== "texto" && !CONVERSA_GERADORES.has(ia) && ia !== "livre")
        Conversa.modo = "texto";
      Conversa.assinatura = "";
      Conversa.galeria = null;
      Conversa.rolarNoFim = true;
      conversaChips();
      // os modos são da IA: a prova de tela pegou o Grok com os modos do
      // PicassoIA (sem 💬) porque a troca de chip não os redesenhava
      conversaModos();
      conversaAplicarModo();
      conversaCarregar();
    });
    return b;
  }));
}

// os modos que a IA tem: 💬 (chat), 🎨 Criar e 🖼 Galeria (quem gera)
function conversaModos() {
  const ia = Conversa.ia;
  const modos = [];
  if (CONVERSA_CHATS.has(ia)) modos.push(["texto", "💬 Conversar"]);
  if (CONVERSA_GERADORES.has(ia) || ia === "livre") {
    modos.push(["imagem", "🎨 Criar"], ["galeria", "🖼 Galeria"]);
  }
  const alvo = $("conversa-modos");
  alvo.classList.toggle("oculto", modos.length < 2);
  alvo.replaceChildren(...modos.map(([modo, rotulo]) => {
    const b = el("button", {class: "acao", "data-modo": modo,
                            "aria-pressed": String(modo === Conversa.modo)}, rotulo);
    b.addEventListener("click", () => {
      if (Conversa.modo === modo) return;
      Conversa.modo = modo;
      Conversa.assinatura = "";
      Conversa.rolarNoFim = true;
      conversaModos();
      conversaAplicarModo();
      if (Conversa.dados) conversaDesenhar(Conversa.dados);
      if (modo === "galeria") conversaGaleria();
    });
    return b;
  }));
}

function conversaAplicarModo() {
  const m = Conversa.modo;
  $("conversa-caixa-texto").classList.toggle("oculto", m !== "texto");
  $("conversa-criar").classList.toggle("oculto", m !== "imagem");
  $("conversa-galeria").classList.toggle("oculto", m !== "galeria");
  $("conversa-historico").classList.toggle("oculto", m === "galeria");
}

// Segundos desde um instante do PC (o relógio do PC, não o do celular).
function conversaSegundos(iso) {
  const d = dataPC(iso);
  return isNaN(d) ? null : Math.max(0, Math.round((agoraPC() - d) / 1000));
}

// O que a linha de situação de uma mensagem diz, e a cor dela.
function conversaSituacao(m) {
  const imagem = m.tipo === "imagem";
  if (m.situacao === "respondida") {
    const dur = m.dur_s ? ` em ${Math.round(m.dur_s)} s` : "";
    return [`${imagem ? "gerada" : "respondida"} ${hora(m.respondida_em || m.atualizado_em)}${dur}`
      + (m.modelo ? ` · ${m.modelo}` : ""), "ok"];
  }
  if (m.situacao === "falhou") return [`falhou: ${m.erro || "sem motivo"}`, "erro"];
  if (m.situacao === "entregue") {
    if (imagem) {
      const s = conversaSegundos(m.entregue_em || m.atualizado_em);
      return [`gerando… (${s == null ? "?" : s}s)`, "trabalhando"];
    }
    return [`entregue ${hora(m.entregue_em || m.atualizado_em)} · esperando a resposta…`,
            "trabalhando"];
  }
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
    return [c.ia ? `o carteiro está esperando a pipeline soltar a conta do ${rot}`
                 : `o carteiro está esperando uma conta soltar${c.nota ? " · " + c.nota : ""}`,
            "trabalhando"];
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

function conversaRotuloDoGerador(m) {
  const g = m.gerador || m.para;
  return CONVERSA_ROTULO[g] || g || "";
}

// O par de balões de um PEDIDO DE IMAGEM: o dele (prompt e proporção) e o da
// IA (a miniatura, ou "gerando… (Xs)").
function conversaBaloesDeImagem(m, rotulo) {
  const [sit, cls] = conversaSituacao(m);
  const situacao = el("div", {class: "situacao " + cls}, `${hora(m.em)} · ${sit}`);
  if (m.situacao === "entregue") {
    situacao.dataset.desde = m.entregue_em || m.atualizado_em || "";
    situacao.dataset.em = m.em || "";
    situacao.classList.add("gerando");
  }
  const eu = conversaBalao("eu",
    el("div", {class: "texto"}, "🎨 " + (m.texto || "")),
    el("div", {class: "fraco"}, `proporção ${m.proporcao || "?"}`
      + (m.para === "livre" ? " · rodízio" + (m.gerador ? ` → ${conversaRotuloDoGerador(m)}` : "")
        : "")),
    situacao);
  const saida = [eu];
  const img = m.imagem || {};
  if (m.situacao === "respondida") {
    const quem = el("div", {class: "quem"}, conversaRotuloDoGerador(m) || rotulo);
    if (img.url) {
      const mini = el("img", {class: "miniatura", src: img.url, alt: m.texto || "imagem",
                              loading: "lazy", "data-id": m.id});
      mini.addEventListener("click", () => imagemAbrir({...m, caixa: m.para}));
      saida.push(conversaBalao("ia", quem, mini,
        el("div", {class: "fraco"}, (m.resposta || "")
          + (img.prova ? ` · prova: ${img.prova === "historico_prompt"
            ? "card do histórico" : img.prova === "turno_na_casa" ? "turno na casa" : img.prova}`
            : ""))));
    } else {
      saida.push(conversaBalao("ia", quem,
        el("div", {class: "erro"}, "a imagem não está mais no PC")));
    }
  }
  return saida;
}

function conversaDesenhar(d) {
  const ia = Conversa.ia;
  $("titulo").textContent = `${CONVERSA_CHATS.has(ia) && Conversa.modo === "texto"
    ? "Conversa" : "Criar"} · ${d.rotulo || ia}`;
  const casa = d.casa || {};
  const partes = [];
  if (!CONVERSA_CHATS.has(ia)) {
    partes.push(ia === "livre"
      ? `rodízio: ${(d.rodizio || []).map((g) => CONVERSA_ROTULO[g] || g).join(" → ")}`
        + " (o primeiro com a conta livre e cota)"
      : (d.gerador && d.gerador.prova ? `prova de origem: ${d.gerador.prova}` : ""));
  } else if (casa.geracao) {
    partes.push(`casa ${casa.geracao}ª · ${casa.mensagens || 0} mensagem(ns)`
      + (casa.tem_resumo ? ` · resumo ${hora(casa.ultimo_resumo_em)}` : ""));
  } else {
    partes.push("ainda sem casa: a primeira mensagem abre o chat de longa duração");
  }
  $("conversa-casa").textContent = partes.filter(Boolean).join(" · ");
  const [textoC, classeC] = conversaTextoDoCarteiro(d.carteiro, ia);
  const carteiro = $("conversa-carteiro");
  carteiro.textContent = "📮 " + textoC;
  carteiro.className = "conversa-carteiro " + classeC;

  const alvo = $("conversa-historico");
  const mensagens = d.mensagens || [];
  if (!mensagens.length) {
    alvo.replaceChildren(el("div", {class: "fraco conversa-vazia"},
      CONVERSA_CHATS.has(ia)
        ? `Nenhuma mensagem para o ${d.rotulo || ia} ainda. Escreva abaixo: a resposta chega `
          + "aqui, vira balão na Vila e vai ao Telegram se você não estiver com o app aberto."
        : `Nenhum pedido de imagem para o ${d.rotulo || ia} ainda. A imagem chega aqui e vai `
          + "ao Telegram (como documento, na qualidade original) se o app estiver fechado."));
  } else {
    alvo.replaceChildren(...mensagens.flatMap((m) => {
      if (m.tipo === "imagem") return conversaBaloesDeImagem(m, d.rotulo || ia);
      const [sit, cls] = conversaSituacao(m);
      const eu = conversaBalao("eu",
        el("div", {class: "texto"}, m.texto),
        (m.anexos || []).length
          ? el("div", {class: "fraco"}, "📎 " + m.anexos.join(", ")) : null,
        el("div", {class: "situacao " + cls}, `${hora(m.em)} · ${sit}`));
      const saida = [eu];
      if (m.situacao === "respondida" && m.resposta != null) {
        // a resposta pode ter sido uma IMAGEM (o Gemini que desenha o gato)
        const img = m.imagem || {};
        let mini = null;
        if (img.url) {
          mini = el("img", {class: "miniatura", src: img.url, alt: m.texto || "imagem",
                            loading: "lazy", "data-id": m.id});
          mini.addEventListener("click", () => imagemAbrir(
            {...m, caixa: m.para, gerador: m.gerador || m.para}));
        }
        saida.push(conversaBalao("ia",
          el("div", {class: "quem"}, d.rotulo || ia),
          mini,
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
  conversaCriarDesenhar(d);
  if (Conversa.rolarNoFim && Conversa.modo !== "galeria") {
    alvo.lastElementChild?.scrollIntoView({block: "end"});
    Conversa.rolarNoFim = false;
  }
}

// O que o "Criar" oferece para a IA aberta: da FICHA (o `gerador` da caixa),
// ou, no rodízio, a união do que os geradores disponíveis fazem.
function conversaOferta(d) {
  const ia = Conversa.ia;
  if (ia === "livre") {
    const geradores = (d.geradores || []).filter((g) => (d.rodizio || []).includes(g.ia));
    const livres = geradores.filter((g) => g.disponivel);
    const props = [];
    for (const g of livres) for (const p of g.proporcoes || []) if (!props.includes(p)) props.push(p);
    return {disponivel: livres.length > 0, rotulo: "o rodízio",
            motivo: livres.length ? "" : "nenhum gerador do rodízio gera imagem hoje",
            proporcoes: props, proporcao_padrao: "1:1", modelos: [],
            prompt_max: 5000,
            nota: "vai para o primeiro livre: "
              + livres.map((g) => g.rotulo).join(" → ")};
  }
  return d.gerador || {disponivel: false, motivo: "não gera imagem", proporcoes: [],
                       modelos: [], prompt_max: 5000};
}

function conversaCriarDesenhar(d) {
  const oferta = conversaOferta(d);
  const aviso = $("criar-aviso");
  const pode = oferta.disponivel && d.enviar !== false;
  if (!oferta.disponivel) {
    aviso.textContent = `✗ ${oferta.rotulo || d.rotulo || ""} não gera imagem hoje: ${oferta.motivo}`
      + (oferta.proximo_passo ? " (próximo passo)" : "");
    aviso.className = "fraco criar-aviso erro";
  } else if (d.enviar === false) {
    aviso.textContent = "as ações estão desligadas neste servidor: só leitura";
    aviso.className = "fraco criar-aviso erro";
  } else {
    const modelo = (oferta.modelos || []).length === 1 ? `modelo: ${oferta.modelos[0]} · ` : "";
    aviso.textContent = modelo + (oferta.nota || "");
    aviso.className = "fraco criar-aviso";
  }
  const sel = $("criar-proporcao");
  const props = oferta.proporcoes || [];
  const antes = Conversa.proporcao[Conversa.ia] || sel.value || oferta.proporcao_padrao || "1:1";
  const chave = props.join(",");
  if (sel.dataset.chave !== chave) {
    sel.replaceChildren(...props.map((p) => el("option", {value: p}, p)));
    sel.dataset.chave = chave;
  }
  if (props.includes(antes)) sel.value = antes;
  else if (props.includes(oferta.proporcao_padrao)) sel.value = oferta.proporcao_padrao;
  const modelos = oferta.modelos || [];
  $("criar-modelo-rotulo").classList.toggle("oculto", modelos.length < 2);
  const selM = $("criar-modelo");
  if (selM.dataset.chave !== modelos.join(",")) {
    selM.replaceChildren(...modelos.map((m) => el("option", {value: m}, m)));
    selM.dataset.chave = modelos.join(",");
  }
  const prompt = $("criar-prompt");
  prompt.maxLength = oferta.prompt_max || 5000;
  prompt.disabled = !pode;
  sel.disabled = !pode;
  selM.disabled = !pode;
  $("criar-enviar").disabled = !pode || Conversa.enviando;
  conversaContagem();
}

function conversaContagem() {
  const p = $("criar-prompt");
  $("criar-contagem").textContent = p.value.length ? `${p.value.length}/${p.maxLength}` : "";
}

function conversaAssinatura(d) {
  return Conversa.modo + JSON.stringify((d.mensagens || []).map(
    (m) => [m.id, m.situacao, m.atualizado_em, (m.imagem || {}).url]))
    + JSON.stringify(d.carteiro && [d.carteiro.situacao, d.carteiro.ia, d.carteiro.nota])
    + JSON.stringify(d.gerador && [d.gerador.disponivel, d.gerador.motivo]) + d.enviar;
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
    if (Conversa.modo === "galeria") conversaGaleria();
  } catch (err) {
    if (err.status !== 401) conexao(false, err);
  }
}

// ---- a galeria: as imagens daquele gerador (no rodízio, todas)
async function conversaGaleria() {
  const ia = Conversa.ia;
  const alvo = $("conversa-galeria");
  try {
    const d = await api(`/api/imagens?n=60${ia !== "livre" ? `&ia=${ia}` : ""}`);
    if (Conversa.ia !== ia || Conversa.modo !== "galeria") return;
    const assinatura = JSON.stringify((d.imagens || []).map((i) => [i.id, i.imagem.url]));
    if (assinatura === Conversa.galeria) return;
    Conversa.galeria = assinatura;
    if (!(d.imagens || []).length) {
      alvo.replaceChildren(el("div", {class: "fraco vazia"},
        `Nenhuma imagem ${ia === "livre" ? "gerada" : "do " + (CONVERSA_ROTULO[ia] || ia)} ainda.`));
      return;
    }
    alvo.replaceChildren(...d.imagens.map((item) => {
      const b = el("button", {class: "item", "data-id": item.id},
        el("img", {src: item.imagem.url, alt: item.texto || "", loading: "lazy"}),
        el("span", {}, `${hora(item.respondida_em || item.em)} · ${item.texto || ""}`));
      b.addEventListener("click", () => imagemAbrir({...item, para: item.caixa}));
      return b;
    }));
  } catch (err) {
    if (err.status !== 401) alvo.replaceChildren(el("div", {class: "erro vazia"},
      err.message || "não deu para abrir a galeria"));
  }
}

// ---- a imagem em tela cheia
const ImagemTela = {item: null};

function imagemAbrir(item) {
  const img = item.imagem || {};
  if (!img.url) return;
  ImagemTela.item = item;
  $("imagem-tela-img").src = img.url;
  $("imagem-tela-img").alt = item.texto || "imagem";
  $("imagem-tela-legenda").textContent = `${conversaRotuloDoGerador(item)} · `
    + `${item.proporcao || ""}${img.largura ? ` · ${img.largura}×${img.altura}` : ""} · `
    + (item.texto || "");
  $("imagem-tela").classList.remove("oculto");
}

function imagemFechar() {
  $("imagem-tela").classList.add("oculto");
  $("imagem-tela-img").removeAttribute("src");
  ImagemTela.item = null;
}

function imagemNome(item) {
  const img = item.imagem || {};
  return img.nome || `${item.gerador || item.para || "ia"}_${img.arquivo || item.id + ".png"}`;
}

function imagemBaixar() {
  const item = ImagemTela.item;
  if (!item || !(item.imagem || {}).url) return;
  const a = el("a", {href: item.imagem.url, download: imagemNome(item)});
  document.body.appendChild(a);
  a.click();
  a.remove();
}

async function imagemCompartilhar() {
  const item = ImagemTela.item;
  if (!item || !(item.imagem || {}).url) return;
  try {
    const resp = await fetch(item.imagem.url);
    if (!resp.ok) throw new Error(resp.status === 410 ? "o link venceu; abra de novo"
      : `o PC respondeu ${resp.status}`);
    const blob = await resp.blob();
    const arquivo = new File([blob], imagemNome(item), {type: blob.type || "image/png"});
    if (navigator.canShare && navigator.canShare({files: [arquivo]})) {
      await navigator.share({files: [arquivo], title: item.texto || "imagem"});
    } else {
      avisar("este navegador não compartilha arquivo; use ⬇ Baixar", true);
    }
  } catch (err) {
    if (err && err.name === "AbortError") return;      // ele cancelou
    avisar(`não deu para compartilhar (${err.message || err.name || "?"}); use ⬇ Baixar`, true);
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

function conversaAvisoDoCarteiro(r, destino) {
  const c = r.carteiro || {};
  if (c.situacao === "nunca" || c.situacao === "parado") {
    avisar("na caixa; o carteiro não está rodando, então ela espera ele voltar", true);
  } else {
    avisar("na caixa do " + destino
      + (c.situacao === "entregando" || c.situacao === "esperando_trava"
        ? " (o carteiro está ocupado; a sua entra em seguida)" : "; o carteiro entrega"));
  }
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
    conversaAvisoDoCarteiro(r, CONVERSA_ROTULO[Conversa.ia] || Conversa.ia);
    Conversa.rolarNoFim = true;
    await conversaCarregar();
  } catch (err) {
    avisar(err.message || "não deu para enviar", true);
  } finally {
    Conversa.enviando = false;
    $("conversa-enviar").disabled = false;
  }
}

// Um PEDIDO DE IMAGEM: direto, como a mensagem (decisão
// `mensagem-para-uma-ia-pelo-app-direto-ou`): gera na conta dele, não publica.
async function conversaCriar() {
  const prompt = $("criar-prompt").value.trim();
  if (!prompt) { avisar("descreva a imagem", true); return; }
  if (Conversa.enviando) return;
  const proporcao = $("criar-proporcao").value;
  const modelo = $("criar-modelo-rotulo").classList.contains("oculto")
    ? null : $("criar-modelo").value || null;
  Conversa.enviando = true;
  $("criar-enviar").disabled = true;
  try {
    const r = await api(`/api/correio/${Conversa.ia}/imagem`, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({prompt, proporcao, modelo}),
    });
    $("criar-prompt").value = "";
    conversaContagem();
    Conversa.proporcao[Conversa.ia] = proporcao;
    conversaAvisoDoCarteiro(r, CONVERSA_ROTULO[Conversa.ia] || Conversa.ia);
    Conversa.rolarNoFim = true;
    await conversaCarregar();
  } catch (err) {
    avisar(err.message || "não deu para pedir a imagem", true);
  } finally {
    Conversa.enviando = false;
    if (Conversa.dados) conversaCriarDesenhar(Conversa.dados);
  }
}

// "gerando… (Xs)" anda a cada segundo sem reler a caixa
function conversaTique() {
  for (const n of document.querySelectorAll("#conversa-historico .situacao.gerando")) {
    const s = conversaSegundos(n.dataset.desde);
    if (s != null) n.textContent = `${hora(n.dataset.em)} · gerando… (${s}s)`;
  }
}

function conversaMostrar() {
  if (!Conversa.ia) Conversa.ia = "deepseek";
  if (!Conversa.modo) Conversa.modo = conversaModoPadrao(Conversa.ia);
  conversaChips();
  conversaModos();
  conversaAplicarModo();
  $("conversa-historico").replaceChildren(el("div", {class: "fraco"}, "carregando…"));
  Conversa.assinatura = "";
  Conversa.galeria = null;
  Conversa.rolarNoFim = true;
  conversaCarregar();
  clearInterval(Conversa.relogio);
  Conversa.relogio = setInterval(() => {
    if (document.visibilityState === "visible") conversaCarregar();
  }, CONVERSA_MS);
  clearInterval(Conversa.ticker);
  Conversa.ticker = setInterval(conversaTique, 1000);
}

function conversaParar() {
  clearInterval(Conversa.relogio);
  clearInterval(Conversa.ticker);
  Conversa.relogio = null;
  Conversa.ticker = null;
  imagemFechar();
}

$("conversa-enviar").addEventListener("click", conversaEnviar);
$("criar-enviar").addEventListener("click", conversaCriar);
$("criar-prompt").addEventListener("input", conversaContagem);
$("criar-proporcao").addEventListener("change", (e) => {
  Conversa.proporcao[Conversa.ia] = e.target.value;
});
$("imagem-fechar").addEventListener("click", imagemFechar);
$("imagem-baixar").addEventListener("click", imagemBaixar);
$("imagem-compartilhar").addEventListener("click", imagemCompartilhar);
$("imagem-tela").addEventListener("click", (e) => {
  if (e.target === $("imagem-tela")) imagemFechar();
});
$("conversa-anexo").addEventListener("change", (e) => {
  const arquivo = e.target.files && e.target.files[0];
  Conversa.anexo = arquivo || null;
  $("conversa-anexo-nome").textContent = arquivo
    ? `${arquivo.name} (${Math.round(arquivo.size / 1024)} KB)` : "";
});
$("conversa-texto").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) conversaEnviar();
});
