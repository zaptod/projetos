"use strict";
// A Vila no celular: o mesmo cenário do painel, com os bots animados por cima.
//
// Divisão de trabalho, igual à do painel: o PC manda o cenário PRONTO
// (/vila.png, 46 KB, composto uma vez) e as POSIÇÕES já calculadas
// (/api/vila?mundo=1); aqui só se anima o que muda — os bots andando de casa
// até o prédio, o efeito em cima do prédio e o balão.
//
// As contas de caminhada são as mesmas de painel/paginas/vila.py:_passo():
// velocidade 3,2 px a cada 60 ms, direção pelo eixo dominante, 2 quadros a
// 6 Hz e um "bob" senoidal (2 px andando, 0,8 px parado). Se mudarem lá,
// mudam aqui — é o preço de ter dois desenhos do mesmo mundo.

const VILA_VELOCIDADE = 3.2 / 0.06;      // px por segundo
const VILA_FPS = 20;                     // redesenho (o painel usa ~16)
const VILA_DADOS_MS = 4000;              // releitura do estado

const Vila = {
  mundo: null, estado: null, bots: {}, selecionado: null,
  zoom: 1, panX: 0, panY: 0, ajustado: false,
  cenario: null, folha: null, fio: null, relogio: null, ultimo: 0,
};

function vilaCanvas() { return document.getElementById("vila-canvas"); }

async function vilaCarregar(comMundo) {
  const dados = await api("/api/vila" + (comMundo ? "?mundo=1" : ""));
  if (dados.mundo) {
    Vila.mundo = dados.mundo;
    Vila.bots = {};
    for (const [nome, lugar] of Object.entries(dados.mundo.lugares)) {
      Vila.bots[nome] = {
        x: lugar.casa[0], y: lugar.casa[1], direcao: "baixo",
        andando: false, fase: lugar.fase, lugar,
      };
    }
    vilaImagem("cenario", `/vila.png?v=${encodeURIComponent(dados.mundo.versao)}`);
    vilaImagem("folha", "/sprites.png");
  }
  Vila.estado = dados.estado;
  vilaDesenharPainel();
  return dados;
}

function vilaImagem(campo, url) {
  const img = new Image();
  img.onload = () => { Vila[campo] = img; vilaAjustar(); };
  img.src = url;
}

// Começa mostrando o mundo inteiro na largura da tela; depois o dedo manda.
function vilaAjustar() {
  const canvas = vilaCanvas();
  if (!canvas || !Vila.mundo) return;
  const largura = canvas.clientWidth || 360;
  const altura = Math.round(largura * 0.62);
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(largura * dpr);
  canvas.height = Math.round(altura * dpr);
  canvas.style.height = altura + "px";
  if (!Vila.ajustado) {
    Vila.zoom = largura / Vila.mundo.tamanho[0];
    Vila.panX = 0;
    Vila.panY = Math.max(0, (Vila.mundo.tamanho[1] * Vila.zoom - altura) / 2);
    Vila.ajustado = true;
  }
}

function vilaEstadoDe(nome) {
  const f = (Vila.estado?.fabricas || []).find((x) => x.nome === nome);
  return f || {status: "ocioso", detalhe: "", trabalhos: []};
}

function vilaPasso(dt, agora) {
  for (const [nome, bot] of Object.entries(Vila.bots)) {
    const f = vilaEstadoDe(nome);
    const alvo = (f.status === "trabalhando" || f.status === "erro")
      ? bot.lugar.trabalho : bot.lugar.casa;
    const dx = alvo[0] - bot.x, dy = alvo[1] - bot.y;
    const distancia = Math.hypot(dx, dy);
    bot.andando = distancia > 2;
    if (bot.andando) {
      const passo = Math.min(VILA_VELOCIDADE * dt, distancia);
      bot.x += (dx / distancia) * passo;
      bot.y += (dy / distancia) * passo;
      bot.direcao = Math.abs(dx) > Math.abs(dy)
        ? (dx > 0 ? "dir" : "esq") : (dy > 0 ? "baixo" : "cima");
    }
    bot.quadro = Math.floor(agora * 6) % 2;
    bot.bob = Math.sin(agora * 6 + bot.fase) * (bot.andando ? 2 : 0.8);
  }
}

function vilaSprite(ctx, papel, quadro, x, y, ancora) {
  const info = Vila.mundo.sprites[papel];
  if (!info || !Vila.folha) return;
  const frame = info.frames[quadro % info.frames.length];
  const tile = Vila.mundo.tile, colunas = Vila.mundo.colunas;
  const lado = tile * Vila.mundo.escala;
  ctx.drawImage(Vila.folha, (frame % colunas) * tile,
                Math.floor(frame / colunas) * tile, tile, tile,
                Math.round(x - lado / 2), Math.round(y - (ancora === "s" ? lado : 0)),
                lado, lado);
}

function vilaDesenhar() {
  const canvas = vilaCanvas();
  if (!canvas || !Vila.mundo) return;
  const ctx = canvas.getContext("2d");
  const agora = performance.now() / 1000;
  const dt = Vila.ultimo ? Math.min(agora - Vila.ultimo, 0.25) : 0;
  Vila.ultimo = agora;
  vilaPasso(dt, agora);

  const dpr = canvas.width / (canvas.clientWidth || 1);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = Vila.mundo.fundo;
  ctx.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);
  ctx.translate(-Vila.panX, -Vila.panY);
  ctx.scale(Vila.zoom, Vila.zoom);
  if (Vila.cenario) ctx.drawImage(Vila.cenario, 0, 0);

  // o prédio escolhido ganha contorno, para o toque ter resposta
  if (Vila.selecionado && Vila.mundo.predios[Vila.selecionado]) {
    const p = Vila.mundo.predios[Vila.selecionado];
    ctx.strokeStyle = "#f0a04b";
    ctx.lineWidth = 3 / Vila.zoom;
    ctx.strokeRect(p.x, p.y, p.larg, p.alt);
  }
  // efeito sobre o prédio de quem está trabalhando ou com erro
  for (const [nome, predio] of Object.entries(Vila.mundo.predios)) {
    const f = vilaEstadoDe(nome);
    if (f.status === "trabalhando" || f.status === "erro") {
      const papel = f.status === "erro" ? "fx.erro" : "fx.trabalho";
      const fps = Vila.mundo.sprites[papel]?.fps || 3;
      vilaSprite(ctx, papel, Math.floor(agora * fps),
                 predio.porta[0], predio.topo, "s");
    }
  }
  // bots, do mais alto para o mais baixo (quem está na frente cobre)
  const ordem = Object.entries(Vila.bots).sort((a, b) => a[1].y - b[1].y);
  for (const [nome, bot] of ordem) {
    const f = vilaEstadoDe(nome);
    vilaSprite(ctx, "bot." + bot.direcao, bot.quadro, bot.x, bot.y + bot.bob, "s");
    const balao = f.status === "erro" ? "❗" : (f.status === "trabalhando" ? "⚙" : "");
    if (balao) {
      ctx.font = `${Math.round(20 / Vila.zoom * Vila.zoom)}px system-ui`;
      ctx.textAlign = "center";
      ctx.fillStyle = f.status === "erro" ? "#ff6b5b" : "#f0a04b";
      ctx.fillText(balao, bot.x, bot.y - Vila.mundo.lado * 1.4);
    }
  }
}

function vilaDesenharPainel() {
  const e = Vila.estado;
  if (!e) return;
  // placar
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
    if (p.idade_s > 120) {
      placar.append(el("div", {class: "fraco"}, `há ${ha(p.idade_s)}`));
    }
  }
  // fábricas (a lista continua: é o que se lê rápido)
  const lista = document.getElementById("fabricas");
  lista.replaceChildren();
  for (const f of e.fabricas || []) {
    const sem = !Vila.mundo?.lugares?.[f.nome]?.tem_predio;
    const linha = el("div", {class: "linha"},
      el("span", {class: "emoji"}, f.emoji),
      el("span", {class: "corpo"}, f.rotulo,
        sem ? el("span", {class: "fraco"}, " (sem prédio)") : null,
        f.detalhe ? el("div", {class: "fraco"}, f.detalhe) : null,
        ...(f.trabalhos || []).map((t) => el("div", {class: "fraco"},
          `${t.canal}: ${t.detalhe}`))),
      el("span", {class: "selo " + f.status},
        f.status === "trabalhando" ? "trabalhando"
          : f.status === "erro" ? "erro" : ha(f.ha_s) || "ocioso"));
    linha.addEventListener("click", () => vilaSelecionar(f.nome));
    lista.append(linha);
  }
  // paralelismo
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
  // no DOM tambem: e assim que o teste (e quem inspeciona) enxerga a escolha
  if (canvas) canvas.dataset.selecionado = Vila.selecionado || "";
  const alvo = document.getElementById("vila-escolhido");
  if (!Vila.selecionado) {
    alvo.classList.add("oculto");
    return;
  }
  const f = vilaEstadoDe(nome);
  const lugar = Vila.mundo?.lugares?.[nome] || {};
  alvo.classList.remove("oculto");
  alvo.replaceChildren(
    el("div", {class: "linha"},
      el("span", {class: "emoji"}, f.emoji || lugar.emoji || "•"),
      el("span", {class: "corpo"}, f.rotulo || nome,
        el("div", {class: "fraco"}, lugar.faz || ""),
        el("div", {}, f.detalhe || "sem novidade"),
        ...(f.trabalhos || []).map((t) => el("div", {class: "fraco"},
          `${t.canal}: ${t.detalhe}`))),
      el("span", {class: "selo " + f.status}, f.status)),
    el("div", {class: "botoes"},
      (() => {
        const b = el("button", {class: "acao"}, "Ver no diário");
        b.addEventListener("click", () => { diarioFabrica = nome; mostrar("diario"); });
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
  for (const [nome, p] of Object.entries(Vila.mundo.predios)) {
    if (x >= p.x && x <= p.x + p.larg && y >= p.y && y <= p.y + p.alt) {
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
  Vila.panX = Math.max(Math.min(Vila.panX, largura - canvas.clientWidth), 0);
  Vila.panY = Math.max(Math.min(Vila.panY, altura - canvas.clientHeight), 0);
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
    if (arrastando && moveu < 8) vilaClique(e.changedTouches ? e.changedTouches[0] : e);
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
  Vila.zoom = Math.max(minimo, Math.min(novo, 3));
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
  if (!Vila.relogio) {
    Vila.relogio = setInterval(() => {
      if (document.visibilityState === "visible") {
        vilaCarregar(false).catch(() => {});
      }
    }, VILA_DADOS_MS);
  }
  if (!Vila.fio) vilaAnimar();
  try {
    await vilaCarregar(!Vila.mundo);
    conexao(true);
  } catch (err) { conexao(false, err); }
}

function vilaParar() {
  clearTimeout(Vila.fio); Vila.fio = null;
  clearInterval(Vila.relogio); Vila.relogio = null;
  Vila.ultimo = 0;
}

window.addEventListener("resize", () => { Vila.ajustado = false; vilaAjustar(); });

// O `app.js` monta a tela ANTES deste arquivo existir (ele carrega depois),
// e naquele instante `vilaMostrar` ainda não estava definida. Sem esta
// linha, a Vila só ligava na segunda troca de aba.
if (tela === "vila" && localStorage.getItem(TOKEN)) vilaMostrar();
