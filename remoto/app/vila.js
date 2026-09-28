"use strict";
// A Vila NOVA no celular: a mesma arte fofa da janela flutuante.
//
// Quem desenha o quê:
//   - o PC manda o FUNDO pronto (/vilanova.png, em dia e noite) e um ATLAS
//     com os personagens em todas as poses (/vilanova-atlas.png). Refazer
//     esse desenho em JavaScript seria uma segunda vila, que divergiria na
//     primeira mudança da arte;
//   - o PC também roda a VIDA (grafo de caminhos, decisões, encontros) e
//     manda um RETRATO por segundo: onde está cada habitante, em que pose,
//     com que balão;
//   - aqui só se desenha e se INTERPOLA entre dois retratos, para o passo
//     não ficar picotado.
//
// O estado pesado (placar, travas, fábricas) vem do /api/vila a cada 15 s:
// ele não precisa da cadência da animação.

const VILA_RETRATO_MS = 1000;
const VILA_ESTADO_MS = 15000;
const VILA_FPS = 20;
const VILA_PRATELEIRA = 150;   // px da prateleira + topo, que a vila não ocupa

const Vila = {
  mundo: null, retrato: null, anterior: null, estado: null,
  trocaEm: 0, selecionado: null,
  zoom: 1, panX: 0, panY: 0, ajustado: false, tocavel: false,
  fundo: null, fundoNoite: null, atlas: null,
  fio: null, relogioRetrato: null, relogioEstado: null,
};

function vilaCanvas() { return document.getElementById("vila-canvas"); }

// ------------------------------------------------------------- dados
async function vilaCarregarRetrato(comMundo) {
  const dados = await api("/api/vilanova" + (comMundo ? "?mundo=1" : ""));
  if (dados.mundo) {
    Vila.mundo = dados.mundo;
    vilaImagem("atlas",
      `/vilanova-atlas.png?v=${encodeURIComponent(dados.mundo.versao)}`);
  }
  Vila.anterior = Vila.retrato;
  Vila.retrato = dados.retrato;
  Vila.trocaEm = performance.now();
  vilaCuidarDoFundo();
  vilaDesenharGente();
}

async function vilaCarregarEstado() {
  Vila.estado = (await api("/api/vila")).estado;
  vilaDesenharPainel();
}

function vilaImagem(campo, url) {
  const img = new Image();
  img.onload = () => { Vila[campo] = img; vilaAjustar(); };
  img.src = url;
}

// O fundo só troca quando a noite chega (ou o dia volta).
function vilaCuidarDoFundo() {
  const noite = !!Vila.retrato?.noite;
  if (Vila.fundo && noite === Vila.fundoNoite) return;
  Vila.fundoNoite = noite;
  vilaImagem("fundo", `/vilanova.png?v=${encodeURIComponent(
    Vila.mundo?.versao || "")}&noite=${noite ? 1 : 0}`);
}

// ------------------------------------------------------------ desenho
function vilaAjustar() {
  const canvas = vilaCanvas();
  if (!canvas || !Vila.mundo) return;
  const largura = canvas.clientWidth || 360;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  // A vila nova e larga e baixa (704x240). Cabendo pela largura, os
  // personagens ficariam do tamanho de uma formiga no celular; entao a
  // altura e que manda, e o dedo arrasta de lado.
  // Desde 28/09 a vila ocupa a tela inteira (a caixa dela é fixa): o
  // canvas pega a altura da caixa, e a prateleira de objetos fica embaixo.
  const caixa = canvas.parentElement ? canvas.parentElement.clientHeight : 0;
  const altura = caixa > 0 ? caixa
    : Math.round(Math.min(largura * 0.58, Vila.mundo.tamanho[1]));
  canvas.width = Math.round(largura * dpr);
  canvas.height = Math.round(altura * dpr);
  canvas.style.height = altura + "px";
  if (!Vila.ajustado) {
    // cabe em pé, sobrando a faixa da prateleira; teto de 3x para o
    // aldeão não virar gigante no tablet
    const livre = caixa > 0 ? altura - VILA_PRATELEIRA : altura;
    Vila.zoom = Math.min(3, Math.max(livre / Vila.mundo.tamanho[1],
                                     largura / Vila.mundo.tamanho[0]));
    Vila.panY = 0;
    // comeca na casa, que e o meio da vila
    const casa = Vila.mundo.portas.casa || [Vila.mundo.tamanho[0] / 2, 0];
    Vila.panX = casa[0] * Vila.zoom - largura / 2;
    Vila.ajustado = true;
    vilaLimitar();
  }
}

// entre dois retratos o habitante anda, em vez de pular de um ponto a outro
function vilaPosicao(h, t) {
  const antes = (Vila.anterior?.habitantes || []).find((x) => x.nome === h.nome);
  if (!antes) return [h.x, h.y];
  if (Math.hypot(h.x - antes.x, h.y - antes.y) > 120) return [h.x, h.y];
  return [antes.x + (h.x - antes.x) * t, antes.y + (h.y - antes.y) * t];
}

function vilaRetanguloDoLote(nome) {
  const lote = Vila.mundo.lotes[nome];
  const tile = 16;
  return [lote.x * tile, lote.y * tile, 4 * tile, 3 * tile];
}

function vilaSprite(ctx, h, x, y) {
  if (!Vila.atlas) return;
  const mapa = Vila.mundo.atlas.mapa;
  const pos = mapa[`${h.nome}|${h.pose}|${h.olhos}|${h.direcao}`]
    || mapa[`${h.nome}|parado|abertos|${h.direcao}`]
    || mapa[`${h.nome}|parado|abertos|dir`];
  if (!pos) return;
  const larg = Vila.mundo.atlas.larg, alt = Vila.mundo.atlas.alt;
  ctx.drawImage(Vila.atlas, pos[0], pos[1], larg, alt,
                Math.round(x - larg / 2), Math.round(y - alt), larg, alt);
}

function vilaDesenhar() {
  const canvas = vilaCanvas();
  if (!canvas || !Vila.mundo || !Vila.retrato) return;
  const ctx = canvas.getContext("2d");
  const dpr = canvas.width / (canvas.clientWidth || 1);
  const t = Math.min(1, (performance.now() - Vila.trocaEm) / VILA_RETRATO_MS);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
  ctx.save();
  ctx.translate(-Vila.panX, -Vila.panY);
  ctx.scale(Vila.zoom, Vila.zoom);
  if (Vila.fundo) ctx.drawImage(Vila.fundo, 0, 0);

  if (Vila.selecionado && Vila.mundo.lotes[Vila.selecionado]) {
    const l = vilaRetanguloDoLote(Vila.selecionado);
    ctx.strokeStyle = "#f0a04b";
    ctx.lineWidth = 2 / Vila.zoom;
    ctx.strokeRect(l[0], l[1], l[2], l[3]);
  }

  // o sinal de trabalho ou de erro, em cima do prédio
  for (const [nome, info] of Object.entries(Vila.retrato.predios || {})) {
    const porta = Vila.mundo.portas[nome];
    if (!porta) continue;
    const sinal = info.status === "erro" ? "❗"
      : info.status === "trabalhando" ? "⚙" : "";
    if (!sinal) continue;
    ctx.font = "16px system-ui";
    ctx.textAlign = "center";
    ctx.fillStyle = info.status === "erro" ? "#ff6b5b" : "#f0a04b";
    ctx.fillText(sinal, porta[0], porta[1] - 62);
  }

  // habitantes, de trás para a frente (quem está mais embaixo cobre)
  const gente = [...(Vila.retrato.habitantes || [])].sort((a, b) => a.y - b.y);
  for (const h of gente) {
    const [x, y] = vilaPosicao(h, t);
    vilaSprite(ctx, h, x, y);
    if (h.emote) {
      ctx.font = "13px system-ui";
      ctx.textAlign = "center";
      ctx.fillStyle = Vila.fundoNoite ? "#fff6d8" : "#2b2016";
      ctx.fillText(h.emote, x, y - Vila.mundo.atlas.alt - 3);
    }
  }
  ctx.restore();
}

// ------------------------------------------------------- painéis de texto
function vilaDesenharGente() {
  const r = Vila.retrato;
  if (!r) return;
  const alvo = document.getElementById("vila-gente");
  const ocupados = (r.habitantes || []).filter(
    (h) => h.balao || h.modo === "trabalho" || h.modo === "erro");
  alvo.replaceChildren(...ocupados.map((h) => {
    const predio = Vila.mundo?.predios?.[h.nome] || {};
    const linha = el("div", {class: "linha"},
      el("span", {class: "emoji"}, predio.emoji || "•"),
      el("span", {class: "corpo"}, predio.rotulo || h.nome,
        el("div", {class: "fraco"}, h.balao || h.descricao || "")),
      el("span", {class: "selo " + (h.modo === "erro" ? "erro"
        : h.modo === "trabalho" ? "trabalhando" : "ocioso")}, h.modo));
    linha.addEventListener("click", () => vilaSelecionar(h.nome));
    return linha;
  }));
  if (!ocupados.length) {
    alvo.replaceChildren(el("div", {class: "fraco"},
      "a vila está tranquila: ninguém trabalhando agora"));
  }
}

function vilaDesenharPainel() {
  const e = Vila.estado;
  if (!e) return;
  const placar = document.getElementById("vila-placar");
  const p = e.placar || {};
  if (p.calculando) {
    placar.replaceChildren(el("div", {class: "fraco"}, "somando o placar…"));
  } else if (p.falhou) {
    placar.replaceChildren(el("div", {class: "fraco"}, "placar indisponível"));
  } else {
    placar.replaceChildren(...[
      ["📤", p.publicados, "publicados"], ["🎬", p.prontos, "prontos"],
      ["⚙", p.trabalhando, "trabalhando"], ["⚠", p.problemas, "problemas"],
    ].map(([emoji, n, rotulo]) => el("div", {class: "numero"},
      el("div", {class: "n"}, `${emoji} ${n == null ? "—" : n}`),
      el("div", {class: "fraco"}, rotulo))));
  }

  const lista = document.getElementById("fabricas");
  lista.replaceChildren();
  for (const f of e.fabricas || []) {
    const linha = el("div", {class: "linha"},
      el("span", {class: "emoji"}, f.emoji),
      el("span", {class: "corpo"}, f.rotulo,
        f.detalhe ? el("div", {class: "fraco"}, f.detalhe) : null,
        ...(f.trabalhos || []).map((t) => el("div", {class: "fraco"},
          `${t.canal}: ${t.detalhe}`))),
      el("span", {class: "selo " + f.status},
        f.status === "trabalhando" ? "trabalhando"
          : f.status === "erro" ? "erro" : ha(f.ha_s) || "ocioso"));
    linha.addEventListener("click", () => vilaSelecionar(f.nome));
    lista.append(linha);
  }

  const par = document.getElementById("vila-travas");
  const travas = e.paralelismo || [];
  par.replaceChildren(...travas.map((t) => el("div", {class: "linha"},
    el("span", {class: "corpo"}, t.servico,
      t.dividida ? el("span", {class: "erro"}, " · dividida entre canais") : null,
      el("div", {class: "fraco"}, t.canais.join(" e ") || "—")),
    el("span", {class: "selo " + (t.ocupada ? "trabalhando" : "ocioso")},
      t.ocupada === null ? "não sei" : t.ocupada ? "em uso" : "livre"))));
  const emUso = travas.filter((t) => t.ocupada).length;
  const divididas = travas.filter((t) => t.dividida).length;
  par.append(el("div", {class: "fraco"},
    `${emUso} em uso · ${divididas} pasta(s) usada(s) por dois canais`));
}

function vilaSelecionar(nome) {
  Vila.selecionado = Vila.selecionado === nome ? null : nome;
  const canvas = vilaCanvas();
  if (canvas) canvas.dataset.selecionado = Vila.selecionado || "";
  const alvo = document.getElementById("vila-escolhido");
  if (!Vila.selecionado) { alvo.classList.add("oculto"); return; }
  const predio = Vila.mundo?.predios?.[nome] || {};
  const info = Vila.retrato?.predios?.[nome] || {};
  const morador = (Vila.retrato?.habitantes || []).find((h) => h.nome === nome);
  alvo.classList.remove("oculto");
  alvo.replaceChildren(
    el("div", {class: "linha"},
      el("span", {class: "emoji"}, predio.emoji || "•"),
      el("span", {class: "corpo"}, predio.rotulo || nome,
        el("div", {class: "fraco"}, predio.faz || ""),
        el("div", {}, info.balao || morador?.descricao || "sem novidade"),
        ...(info.trabalhos || []).map((t) => el("div", {class: "fraco"}, t)),
        info.erro ? el("div", {class: "erro"}, info.erro) : null,
        (info.contas || []).length
          ? el("div", {class: "fraco"}, "conta: " + info.contas.join(", "))
          : null),
      el("span", {class: "selo " + (info.status || "ocioso")},
        info.status || "")),
    el("div", {class: "botoes"},
      (() => {
        const b = el("button", {class: "acao"}, "Ver no diário");
        b.addEventListener("click", () => {
          diarioFabrica = nome; abrir("diario", b);
        });
        return b;
      })()));
}

// ------------------------------------------------------------ toque
function vilaParaMundo(evento) {
  const canvas = vilaCanvas();
  const r = canvas.getBoundingClientRect();
  const toque = evento.touches ? evento.touches[0] : evento;
  return [(toque.clientX - r.left + Vila.panX) / Vila.zoom,
          (toque.clientY - r.top + Vila.panY) / Vila.zoom];
}

function vilaClique(evento) {
  if (!Vila.mundo) return;
  const [x, y] = vilaParaMundo(evento);
  const canvas = vilaCanvas();
  if (canvas) canvas.dataset.toque = `${Math.round(x)},${Math.round(y)}`;
  // primeiro o habitante (ele anda por cima), depois o lote
  const perto = (Vila.retrato?.habitantes || []).find(
    (h) => Math.abs(h.x - x) < 16 && y > h.y - 34 && y < h.y + 6);
  if (perto) { vilaSelecionar(perto.nome); return; }
  for (const nome of Object.keys(Vila.mundo.lotes)) {
    const [lx, ly, lw, lh] = vilaRetanguloDoLote(nome);
    if (x >= lx && x <= lx + lw && y >= ly - 20 && y <= ly + lh) {
      vilaSelecionar(nome);
      return;
    }
  }
  vilaSelecionar(null);
}

function vilaLimitar() {
  const canvas = vilaCanvas();
  const largura = Vila.mundo.tamanho[0] * Vila.zoom;
  const altura = Vila.mundo.tamanho[1] * Vila.zoom;
  // o mundo menor que a tela fica no meio (em pé, um pouco para cima,
  // longe da prateleira), em vez de grudado no canto
  Vila.panX = largura <= canvas.clientWidth
    ? -Math.round((canvas.clientWidth - largura) / 2)
    : Math.max(Math.min(Vila.panX, largura - canvas.clientWidth), 0);
  Vila.panY = altura <= canvas.clientHeight
    ? -Math.round((canvas.clientHeight - altura) * 0.4)
    : Math.max(Math.min(Vila.panY, altura - canvas.clientHeight), 0);
}

function vilaLigarToque() {
  const canvas = vilaCanvas();
  let arrastando = false, moveu = 0, ultimo = null, pinca = 0;
  const comeco = (e) => {
    if (e.touches && e.touches.length === 2) {
      pinca = Math.hypot(e.touches[0].clientX - e.touches[1].clientX,
                         e.touches[0].clientY - e.touches[1].clientY);
      return;
    }
    arrastando = true; moveu = 0;
    const t = e.touches ? e.touches[0] : e;
    ultimo = [t.clientX, t.clientY];
  };
  const mover = (e) => {
    if (e.touches && e.touches.length === 2 && pinca) {
      const agora = Math.hypot(e.touches[0].clientX - e.touches[1].clientX,
                               e.touches[0].clientY - e.touches[1].clientY);
      vilaZoom(Vila.zoom * (agora / pinca), true);
      pinca = agora;
      e.preventDefault();
      return;
    }
    if (!arrastando) return;
    const t = e.touches ? e.touches[0] : e;
    const dx = t.clientX - ultimo[0], dy = t.clientY - ultimo[1];
    moveu += Math.abs(dx) + Math.abs(dy);
    Vila.panX -= dx; Vila.panY -= dy;
    ultimo = [t.clientX, t.clientY];
    vilaLimitar();
    e.preventDefault();
  };
  const fim = (e) => {
    if (arrastando && moveu < 8) {
      vilaClique(e.changedTouches ? e.changedTouches[0] : e);
    }
    arrastando = false; pinca = 0;
  };
  canvas.addEventListener("touchstart", comeco, {passive: true});
  canvas.addEventListener("touchmove", mover, {passive: false});
  canvas.addEventListener("touchend", fim);
  canvas.addEventListener("mousedown", comeco);
  canvas.addEventListener("mousemove", mover);
  canvas.addEventListener("mouseup", fim);
}

function vilaZoom(novo, manterCentro) {
  const canvas = vilaCanvas();
  if (!Vila.mundo || !canvas) return;
  const minimo = (canvas.clientWidth || 360) / Vila.mundo.tamanho[0];
  const antes = Vila.zoom;
  Vila.zoom = Math.max(minimo, Math.min(novo, 4));
  if (manterCentro !== false) {
    const meio = [(Vila.panX + canvas.clientWidth / 2) / antes,
                  (Vila.panY + canvas.clientHeight / 2) / antes];
    Vila.panX = meio[0] * Vila.zoom - canvas.clientWidth / 2;
    Vila.panY = meio[1] * Vila.zoom - canvas.clientHeight / 2;
  }
  vilaLimitar();
}

// --------------------------------------------------------- ciclo de vida
function vilaAnimar() {
  vilaDesenhar();
  Vila.fio = setTimeout(() => requestAnimationFrame(vilaAnimar), 1000 / VILA_FPS);
}

async function vilaMostrar() {
  vilaAjustar();
  if (!Vila.tocavel) { vilaLigarToque(); Vila.tocavel = true; }
  if (!Vila.relogioRetrato) {
    Vila.relogioRetrato = setInterval(() => {
      if (document.visibilityState === "visible") {
        vilaCarregarRetrato(false).catch(() => {});
      }
    }, VILA_RETRATO_MS);
    Vila.relogioEstado = setInterval(() => {
      if (document.visibilityState === "visible") {
        vilaCarregarEstado().catch(() => {});
      }
    }, VILA_ESTADO_MS);
  }
  if (!Vila.fio) vilaAnimar();
  try {
    await vilaCarregarRetrato(!Vila.mundo);
    await vilaCarregarEstado();
    conexao(true);
  } catch (err) { conexao(false, err); }
}

function vilaParar() {
  clearTimeout(Vila.fio); Vila.fio = null;
  clearInterval(Vila.relogioRetrato); Vila.relogioRetrato = null;
  clearInterval(Vila.relogioEstado); Vila.relogioEstado = null;
}

window.addEventListener("resize", () => { Vila.ajustado = false; vilaAjustar(); });

// O `app.js` monta a tela ANTES deste arquivo existir (ele carrega depois),
// e naquele instante `vilaMostrar` ainda não estava definida. Sem esta
// linha, a Vila só ligaria na segunda troca de aba.
if (tela === "vila" && localStorage.getItem(TOKEN)) vilaMostrar();
