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
//
// A VILA EM PÉ (28/09/2026). O mundo é largo (704x240); caber pela altura
// do celular mostrava 2 prédios de 11, e o erro dos outros ficava fora da
// tela. Agora o PC manda a Vila DOBRADA (`painel/flutuante/retrato.py`):
// a metade esquerda em cima, a direita embaixo, uma sebe no meio, céu e
// grama nas pontas, tudo desenhado já em 3x (nítido, sem ampliar). A vida
// continua em coordenadas do MUNDO; `vilaDobrar` é a mesma conta do
// `retrato.para_retrato`. Como a câmera abre (perto, na casa, ou a Vila
// inteira) é a decisão `vila-zoom-celular` do Adrian; pinça e "+"
// aproximam, "−" afasta até a Vila inteira.
//
// A VILA DEITADA (28/09/2026, mesmo nó: "também adicionei suporte se eu
// deitar o celular"). Com a tela mais larga que alta, o PC manda o mundo
// INTEIRO numa fileira só (`painel/flutuante/paisagem.py`); a prateleira
// vira uma coluna à direita e o placar sobe para o cabeçalho (CSS, pela
// classe `deitado` no body), e a fileira fica com a altura quase toda.
// Girar troca o arranjo na hora, sem recarregar: o prédio escolhido e o
// objeto aberto continuam onde estavam. Os dois arranjos são uma lista de
// FILEIRAS ([x0 do mundo, y na imagem]); toda conta passa por ela.

const VILA_RETRATO_MS = 1000;
const VILA_ESTADO_MS = 15000;
const VILA_FPS = 20;
const VILA_ZOOM_MAX = 3;        // vezes o "vila inteira"
const VILA_CEU = {dia: "#7cc4ec", noite: "#10163a"};
const VILA_CHAO = {dia: "#62a64f", noite: "#3c5f4b"};

const VILA_DEITADA = window.matchMedia("(orientation: landscape)");

const Vila = {
  mundo: null, retrato: null, anterior: null, estado: null,
  arranjo: "retrato",           // "retrato" (em pé, dobrada) | "paisagem"
  fundos: {},                   // "arranjo|noite" -> imagem já baixada
  trocaEm: 0, selecionado: null,
  zoom: 1, zoomInteira: 1, panX: 0, panY: 0, ajustado: false, tocavel: false,
  modo: null,                   // "inteira" | "perto" | "livre" (o dedo mexeu)
  faixa: [0, 0],                // [topo, base] livres entre placar e prateleira
  fundo: null, fundoNoite: null, atlas: null,
  folhas: {},                   // url da folha da esteira -> imagem (ou false)
  fio: null, relogioRetrato: null, relogioEstado: null,
};

function vilaCanvas() { return document.getElementById("vila-canvas"); }
// a geometria do arranjo de agora (o deitado só existe com servidor novo)
function vilaGeo() {
  if (!Vila.mundo) return null;
  return (Vila.arranjo === "paisagem" && Vila.mundo.paisagem) || Vila.mundo.retrato;
}
// o arranjo que está de fato na tela (sem o deitado no servidor, é o em pé)
function vilaArranjoDesenhado() {
  return vilaGeo() === Vila.mundo.paisagem ? "paisagem" : "retrato";
}
// o atlas é um só para os dois arranjos
function vilaAtlasInfo() { return Vila.mundo.retrato.atlas; }

// As fileiras do arranjo: {x0, y} (onde o pedaço do mundo começa e em que
// y da imagem ele está), de cima para baixo.
function vilaFileiras() {
  const g = vilaGeo();
  const lista = g.fileiras || [[0, g.ceu], [g.dobra, g.linha2]];
  return lista.map(([x0, y]) => ({x0, y}));
}

// (x, y) do mundo -> (x, y) na imagem do arranjo
function vilaDobrar(x, y) {
  const fileiras = vilaFileiras();
  let f = fileiras[0];
  for (const outra of fileiras) if (x >= outra.x0) f = outra;
  return [x - f.x0, y + f.y];
}

// o inverso, para o toque; null no céu, na sebe, no pé e fora do mundo
function vilaDesdobrar(x, y) {
  const g = vilaGeo();
  if (x < 0 || x >= g.largura) return null;
  for (const f of vilaFileiras()) {
    if (y >= f.y && y < f.y + g.fileira) return [x + f.x0, y - f.y];
  }
  return null;
}

// o topo da primeira fileira e o pé da última, na imagem
function vilaBloco() {
  const g = vilaGeo(), fileiras = vilaFileiras();
  return [fileiras[0].y, fileiras[fileiras.length - 1].y + g.fileira];
}

// Deitado ou em pé: a MESMA pergunta do CSS (a classe `deitado` no body),
// para a tela e a conta nunca discordarem. Trocou? A câmera volta a abrir
// como a decisão manda, no prédio escolhido (ou na casa), e o placar muda
// de lugar. Nada recarrega: seleção e objeto aberto ficam.
function vilaArranjar() {
  const deitado = VILA_DEITADA.matches;
  document.body.classList.toggle("deitado", deitado);
  const placar = document.getElementById("vila-placar");
  const conexao = document.getElementById("conexao");
  const canvas = vilaCanvas();
  if (placar && conexao && canvas) {
    if (deitado && placar.parentElement !== conexao.parentElement) {
      conexao.before(placar);
    } else if (!deitado && placar.parentElement !== canvas.parentElement) {
      canvas.after(placar);
    }
  }
  const novo = deitado ? "paisagem" : "retrato";
  if (canvas) canvas.dataset.arranjo = novo;
  if (novo === Vila.arranjo) return false;
  Vila.arranjo = novo;
  if (Vila.modo !== "inteira") Vila.modo = "perto";
  return true;
}

// ------------------------------------------------------------- dados
async function vilaCarregarRetrato(comMundo) {
  const dados = await api("/api/vilanova" + (comMundo ? "?mundo=1" : ""));
  if (dados.mundo) {
    Vila.mundo = dados.mundo;
    vilaArranjar();
    vilaImagem("atlas", `/vilanova-atlas.png?escala=${dados.mundo.retrato.escala}`
      + `&v=${encodeURIComponent(dados.mundo.versao)}`);
  }
  Vila.anterior = Vila.retrato;
  Vila.retrato = dados.retrato;
  Vila.trocaEm = performance.now();
  vilaCuidarDoFundo();
  vilaDesenharGente();
}

async function vilaCarregarEstado() {
  // o correio (a conversa dele com cada IA) vem junto: uma resposta que ele
  // ainda não viu vira balão em cima do prédio e entra no cartão
  const [vila, correio] = await Promise.all([
    api("/api/vila"), api("/api/correio").catch(() => null)]);
  Vila.estado = vila.estado;
  Vila.correio = correio;
  vilaDesenharPainel();
  if (Vila.selecionado) vilaMostrarEscolhido();
}

// as IAs com que ele conversa pelo app (Vila das IAs, fase 2); desde 29/09
// o Grok também tem prédio (entre o DeepSeek e o ChatGPT)
const VILA_CONVERSA = new Set(["deepseek", "chatgpt", "gemini", "grok"]);

function vilaCaixa(nome) {
  const c = Vila.correio || {};
  // as caixas de chat e, desde 29/09 (tarde), as de imagem (PicassoIA...)
  return [...(c.ias || []), ...(c.imagens || [])].find((x) => x.ia === nome) || null;
}

// quem gera imagem (pela ficha, vinda do PC): o "🎨 Criar" do cartão
function vilaGerador(nome) {
  return ((Vila.correio || {}).geradores || []).find((g) => g.ia === nome) || null;
}

// a última resposta ainda não vista daquela IA (o texto curto do balão)
function vilaRespostaNova(nome) {
  const c = vilaCaixa(nome);
  if (!c || !c.nao_vistas || !c.ultima) return null;
  const u = c.ultima;
  if (u.situacao === "respondida" && u.resposta) return u.resposta;
  if (u.situacao === "falhou") return "✗ " + (u.erro || "falhou");
  return null;
}

function vilaImagem(campo, url) {
  const img = new Image();
  img.onload = () => { Vila[campo] = img; vilaAjustar(); };
  img.src = url;
}

// O fundo troca quando a noite chega (ou o dia volta) e quando o aparelho
// gira. Cada um é baixado uma vez: girar de volta é instantâneo.
function vilaCuidarDoFundo() {
  if (!Vila.mundo) return;
  const noite = !!Vila.retrato?.noite;
  const chave = `${vilaArranjoDesenhado()}|${noite}`;
  Vila.fundoNoite = noite;
  Vila.fundo = Vila.fundos[chave] || null;
  if (Vila.fundo || Vila.fundos[chave] === false) return;
  Vila.fundos[chave] = false;                // pedido em voo
  const img = new Image();
  img.onload = () => {
    Vila.fundos[chave] = img;
    if (`${vilaArranjoDesenhado()}|${!!Vila.retrato?.noite}` === chave) {
      Vila.fundo = img;
      vilaAjustar();
    }
  };
  img.onerror = () => { delete Vila.fundos[chave]; };
  img.src = `/vilanova-${vilaArranjoDesenhado()}.webp?v=${encodeURIComponent(
    Vila.mundo.versao || "")}&noite=${noite ? 1 : 0}`;
}

// ------------------------------------------------------------ desenho
// A faixa livre da tela: do fim do placar ao topo da prateleira. É nela que
// as duas fileiras têm de caber; o céu fica atrás do título e do placar.
function vilaFaixaLivre(canvas) {
  const caixa = canvas.getBoundingClientRect();
  const placar = document.getElementById("vila-placar");
  const nav = document.getElementById("nav");
  let topo = 0, base = caixa.height;
  if (placar && placar.offsetParent) {
    topo = placar.getBoundingClientRect().bottom - caixa.top + 8;
  }
  if (document.body.classList.contains("deitado")) {
    // deitado, a prateleira é uma coluna do lado: a altura toda é da Vila
    // (a caixa da Vila já termina onde a coluna começa)
    const titulo = document.getElementById("titulo");
    if (titulo) topo = Math.max(topo, titulo.getBoundingClientRect().bottom - caixa.top + 6);
    document.documentElement.style.setProperty("--prateleira", "0px");
  } else if (nav && !nav.classList.contains("oculto")) {
    const r = nav.getBoundingClientRect();
    base = r.top - caixa.top - 8;
    // o cartão do escolhido se apoia na prateleira, seja qual for a altura
    document.documentElement.style.setProperty("--prateleira",
      `${Math.round(caixa.bottom - r.top)}px`);
  }
  if (base - topo < 120) { topo = 0; base = caixa.height; }
  return [topo, base];
}

function vilaAjustar() {
  const canvas = vilaCanvas();
  const g = vilaGeo();
  if (!canvas || !g) return;
  const largura = canvas.clientWidth || 360;
  // 3 e não 2: o celular dele tem ~2,75 pixels por px, e o teto de 2 era
  // mais uma ampliação borrando a arte
  const dpr = Math.min(window.devicePixelRatio || 1, 3);
  const caixa = canvas.parentElement ? canvas.parentElement.clientHeight : 0;
  const altura = caixa > 0 ? caixa : Math.round(largura * 1.6);
  canvas.width = Math.round(largura * dpr);
  canvas.height = Math.round(altura * dpr);
  canvas.style.height = altura + "px";
  Vila.faixa = vilaFaixaLivre(canvas);
  const [topo, base] = Vila.faixa;
  // "vila inteira": todas as fileiras (e a sebe, em pé) cabem na faixa livre
  const [cima, baixo] = vilaBloco();
  Vila.zoomInteira = Math.min(largura / g.largura, (base - topo) / (baixo - cima));
  // Como abre: a decisão `painel-e-vila/vila-zoom-celular` do Adrian, que o
  // servidor lê (pendente = "perto", como era). Não se escolhe aqui.
  if (!Vila.ajustado) Vila.modo = g.enquadramento === "longe" ? "inteira" : "perto";
  Vila.ajustado = true;
  if (Vila.modo === "inteira") {
    Vila.zoom = Vila.zoomInteira;
  } else if (Vila.modo === "perto") {
    // uma fileira enche a altura livre (nada debaixo do placar), com a
    // casa no meio na horizontal (o de antes); depois de girar com um
    // prédio escolhido, é ele que fica no meio
    Vila.zoom = Math.min(Vila.zoomInteira * VILA_ZOOM_MAX, (base - topo) / g.fileira);
    const foco = vilaFoco();
    const [cx, fy] = vilaDobrar(foco[0], foco[1]);
    const cy = fy - foco[1] + g.fileira / 2;
    Vila.panX = cx * Vila.zoom - largura / 2;
    Vila.panY = cy * Vila.zoom - (topo + base) / 2;
  }
  Vila.zoom = Math.max(Vila.zoomInteira,
                       Math.min(Vila.zoom, Vila.zoomInteira * VILA_ZOOM_MAX));
  vilaLimitar();
  vilaMarcarZoom();
}

// o ponto do mundo em que a câmera "perto" abre: o prédio escolhido, o
// habitante escolhido, ou a casa
function vilaFoco() {
  const tile = Vila.mundo.tile || 16;
  const lote = Vila.selecionado && Vila.mundo.lotes[Vila.selecionado];
  if (lote) return [(lote.x + 2) * tile, (lote.y + 1.5) * tile];
  const morador = Vila.selecionado && (Vila.retrato?.habitantes || []).find(
    (h) => h.nome === Vila.selecionado);
  if (morador) return [morador.x, morador.y];
  return Vila.mundo.portas.casa || [200, 120];
}

// entre dois retratos o habitante anda, em vez de pular de um ponto a outro
function vilaPosicao(h, t) {
  const antes = (Vila.anterior?.habitantes || []).find((x) => x.nome === h.nome);
  if (!antes) return [h.x, h.y];
  if (Math.hypot(h.x - antes.x, h.y - antes.y) > 120) return [h.x, h.y];
  return [antes.x + (h.x - antes.x) * t, antes.y + (h.y - antes.y) * t];
}

// o lote em coordenadas da vila em pé (nenhum lote cruza a dobra)
function vilaRetanguloDoLote(nome) {
  const lote = Vila.mundo.lotes[nome];
  const tile = Vila.mundo.tile || 16;
  const [x, y] = vilaDobrar(lote.x * tile, lote.y * tile);
  return [x, y, 4 * tile, 3 * tile];
}

// A ARTE DA ESTEIRA (02/10/2026). Habitante com folha aprovada não vem do
// atlas: o PC diz qual animação e qual ciclo (a linha da direção) e manda a
// folha pela rota só de leitura /arte-vila/; aqui só se escolhe o quadro
// pelo relógio, no fps do .json. É a mesma conta da janela flutuante
// (`arte_pronta.Folha.indice`), e a folha é baixada uma vez.
function vilaQuadroDaFolha(ciclo, t) {
  const n = (ciclo.quadros || []).length || 1;
  const passo = Math.floor(Math.max(0, t) * (ciclo.fps || 1));
  const i = ciclo.loop === false ? Math.min(passo, n - 1) : passo % n;
  return (ciclo.quadros || [0])[i];
}

function vilaFolha(url) {
  const pronta = Vila.folhas[url];
  if (pronta || pronta === false) return pronta || null;
  Vila.folhas[url] = false;                  // pedido em voo
  const img = new Image();
  img.onload = () => { Vila.folhas[url] = img; };
  img.onerror = () => { delete Vila.folhas[url]; };
  img.src = url;
  return null;
}

// o retângulo da folha e onde ele cai no mundo (null = sem arte pronta)
function vilaQuadroDoHabitante(h, agora) {
  const pedido = h.arte;
  const info = pedido && Vila.mundo?.arte?.habitantes?.[h.nome]?.[pedido.animacao];
  const ciclo = info && info.ciclos[pedido.ciclo];
  if (!ciclo) return null;
  const q = vilaQuadroDaFolha(ciclo, agora + (pedido.fase || 0));
  const [cols, lins] = info.grade;
  const cw = info.tamanho[0] / cols, ch = info.tamanho[1] / lins;
  const alt = info.mundo[1];
  return {url: info.url, sx: (q % cols) * cw, sy: Math.floor(q / cols) * ch,
          sw: cw, sh: ch, larg: cw * alt / ch, alt,
          topo: -1 - info.pe * alt};       // em relação ao pé
}

// Cada fileira mostra um pedaço do mundo. Quem anda perto da dobra aparece
// nas duas, cortado: sai de uma e entra na outra.
function vilaSprite(ctx, h, x, y) {
  const quadro = vilaQuadroDoHabitante(h, performance.now() / 1000);
  const folha = quadro && vilaFolha(quadro.url);
  if (folha) return vilaSpriteDaFolha(ctx, folha, quadro, x, y);
  if (!Vila.atlas) return;
  const info = vilaAtlasInfo();
  const mapa = info.mapa;
  const pos = mapa[`${h.nome}|${h.pose}|${h.olhos}|${h.direcao}`]
    || mapa[`${h.nome}|parado|abertos|${h.direcao}`]
    || mapa[`${h.nome}|parado|abertos|dir`];
  if (!pos) return;
  const larg = info.larg / info.escala, alt = info.alt / info.escala;
  const g = vilaGeo();
  for (const f of vilaFileiras()) {
    const rx = x - f.x0;
    if (rx + larg / 2 < 0 || rx - larg / 2 > g.largura) continue;
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, f.y - alt, g.largura, g.fileira + alt);
    ctx.clip();
    ctx.drawImage(Vila.atlas, pos[0], pos[1], info.larg, info.alt,
                  rx - larg / 2, f.y + y - alt, larg, alt);
    ctx.restore();
  }
}

function vilaSpriteDaFolha(ctx, folha, q, x, y) {
  const g = vilaGeo();
  for (const f of vilaFileiras()) {
    const rx = x - f.x0;
    if (rx + q.larg / 2 < 0 || rx - q.larg / 2 > g.largura) continue;
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, f.y - q.alt, g.largura, g.fileira + q.alt);
    ctx.clip();
    ctx.fillStyle = "rgba(50, 80, 40, 0.27)";   // a sombra no chão
    ctx.beginPath();
    ctx.ellipse(rx, f.y + y - 1.85, 8, 1.65, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.drawImage(folha, q.sx, q.sy, q.sw, q.sh,
                  rx - q.larg / 2, f.y + y + q.topo, q.larg, q.alt);
    ctx.restore();
  }
}

function vilaDesenhar() {
  const canvas = vilaCanvas();
  const g = vilaGeo();
  if (!canvas || !g || !Vila.retrato) return;
  const ctx = canvas.getContext("2d");
  const dpr = canvas.width / (canvas.clientWidth || 1);
  const t = Math.min(1, (performance.now() - Vila.trocaEm) / VILA_RETRATO_MS);
  const W = canvas.clientWidth, H = canvas.clientHeight;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  // fora da imagem: o céu em cima e a grama embaixo, da mesma cor da borda
  const noite = Vila.fundoNoite ? "noite" : "dia";
  const meio = Math.round(g.ceu * Vila.zoom - Vila.panY);
  ctx.fillStyle = VILA_CEU[noite];
  ctx.fillRect(0, 0, W, Math.max(0, meio));
  ctx.fillStyle = VILA_CHAO[noite];
  ctx.fillRect(0, Math.max(0, meio), W, H);
  ctx.save();
  ctx.translate(-Vila.panX, -Vila.panY);
  ctx.scale(Vila.zoom, Vila.zoom);
  if (Vila.fundo) ctx.drawImage(Vila.fundo, 0, 0, g.largura, g.altura);

  if (Vila.selecionado && Vila.mundo.lotes[Vila.selecionado]) {
    const l = vilaRetanguloDoLote(Vila.selecionado);
    ctx.strokeStyle = "#f0a04b";
    ctx.lineWidth = 2.5 / Vila.zoom;
    ctx.beginPath();
    ctx.roundRect(l[0] - 2, l[1] - 18, l[2] + 4, l[3] + 20, 8);
    ctx.stroke();
  }

  vilaPatos(ctx);

  // o sinal de trabalho ou de erro, em cima do prédio
  for (const [nome, info] of Object.entries(Vila.retrato.predios || {})) {
    const porta = Vila.mundo.portas[nome];
    if (!porta) continue;
    const sinal = info.status === "erro" ? "❗"
      : info.status === "trabalhando" ? "⚙" : "";
    if (!sinal) continue;
    const [px, py] = vilaDobrar(porta[0], porta[1]);
    vilaSelo(ctx, px + 22, py - 56, sinal, info.status === "erro");
  }

  // habitantes, de trás para a frente (quem está mais embaixo cobre)
  const gente = [...(Vila.retrato.habitantes || [])].sort((a, b) => a.y - b.y);
  const alt = vilaAtlasInfo().alt / vilaAtlasInfo().escala;
  for (const h of gente) {
    const [x, y] = vilaPosicao(h, t);
    vilaSprite(ctx, h, x, y);
  }
  // os emotes por cima de todo mundo (um balão não fica atrás de ninguém)
  for (const h of gente) {
    if (!h.emote) continue;
    const [x, y] = vilaPosicao(h, t);
    const [ex, ey] = vilaDobrar(x, y);
    vilaBalao(ctx, ex, ey - alt - 2, h.emote);
  }
  // a resposta de uma IA que ele ainda não viu (o correio, fase 2), por
  // cima de todo mundo: quando desvia para baixo do prédio, é ela a
  // novidade, não o habitante parado na porta
  vilaDesenharCorreio(ctx);
  ctx.restore();
}

// Os dois patos do lago, na mesma volta da janela flutuante (cena.py):
// só enfeite, e por isso é o único movimento que o celular inventa.
function vilaPatos(ctx) {
  const info = vilaAtlasInfo();
  if (!info.pato || !info.lago || !Vila.atlas) return;
  const agora = performance.now() / 1000;
  const [w, h] = info.pato;
  for (let i = 0; i < 2; i++) {
    const a = agora * 0.35 + i * Math.PI;
    const x = info.lago[0] + Math.cos(a) * 18;
    const y = info.lago[1] + Math.sin(a) * 7 - 2;
    const lado = Math.sin(a) < 0 ? "dir" : "esq";
    const pos = info.mapa[`pato|${Math.floor(agora * 2 + i) % 2}|${lado}`];
    if (!pos) continue;
    const [px, py] = vilaDobrar(x, y);
    ctx.drawImage(Vila.atlas, pos[0], pos[1], w * info.escala, h * info.escala,
                  px - w / 2, py - h / 2, w, h);
  }
}

// o selo redondo em cima do prédio: ⚙ trabalhando, ❗ erro
function vilaSelo(ctx, x, y, sinal, erro) {
  ctx.beginPath();
  ctx.arc(x, y, 8, 0, Math.PI * 2);
  ctx.fillStyle = erro ? "#ff6b5b" : "#fff6d8";
  ctx.fill();
  ctx.lineWidth = 1.2;
  ctx.strokeStyle = erro ? "#a8321f" : "#d9822b";
  ctx.stroke();
  ctx.font = "10px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = erro ? "#ffffff" : "#b8661b";
  ctx.fillText(erro ? "!" : sinal, x, y + 0.5);
  ctx.textBaseline = "alphabetic";
}

// o balãozinho branco do emote, igual ao da janela flutuante
function vilaBalao(ctx, x, y, emote) {
  const r = 7.5;
  ctx.beginPath();
  ctx.arc(x, y - r, r, 0, Math.PI * 2);
  ctx.moveTo(x - 2.5, y - 1.5);
  ctx.lineTo(x, y + 2.5);
  ctx.lineTo(x + 2.5, y - 1.5);
  ctx.fillStyle = "rgba(255, 255, 255, .95)";
  ctx.fill();
  ctx.lineWidth = .6;
  ctx.strokeStyle = "#d8cfc4";
  ctx.stroke();
  ctx.font = "9px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#2b2016";
  ctx.fillText(emote, x, y - r + 0.5);
  ctx.textBaseline = "alphabetic";
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
  // o placar mudou de altura? a faixa livre da vila muda junto
  const canvas = vilaCanvas();
  if (canvas) {
    const faixa = vilaFaixaLivre(canvas);
    if (faixa[0] !== Vila.faixa[0] || faixa[1] !== Vila.faixa[1]) vilaAjustar();
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
  vilaMostrarEscolhido();
}

// O cartão do escolhido. Separado do toque porque girar o aparelho o
// redesenha (o lugar dele depende do arranjo) sem desmarcar ninguém.
function vilaMostrarEscolhido() {
  const nome = Vila.selecionado;
  const canvas = vilaCanvas();
  if (canvas) canvas.dataset.selecionado = nome || "";
  const alvo = document.getElementById("vila-escolhido");
  if (!nome || !Vila.mundo) { alvo.classList.add("oculto"); return; }
  const predio = Vila.mundo?.predios?.[nome] || {};
  const info = Vila.retrato?.predios?.[nome] || {};
  const morador = (Vila.retrato?.habitantes || []).find((h) => h.nome === nome);
  alvo.classList.remove("oculto");
  // O cartão não pode tapar o que foi escolhido: prédio na metade de baixo
  // da tela, cartão em cima (logo abaixo do placar); senão, embaixo.
  let ySel = null;
  if (Vila.mundo.lotes[nome]) ySel = vilaRetanguloDoLote(nome)[1] + 24;
  else if (morador) ySel = vilaDobrar(morador.x, morador.y)[1];
  const [topo, base] = Vila.faixa;
  if (document.body.classList.contains("deitado")) {
    // deitado sobra largura, não altura: o cartão fica embaixo, do lado
    // oposto ao escolhido
    let xSel = null;
    if (Vila.mundo.lotes[nome]) {
      const l = vilaRetanguloDoLote(nome);
      xSel = l[0] + l[2] / 2;
    } else if (morador) xSel = vilaDobrar(morador.x, morador.y)[0];
    const largura = canvas ? canvas.clientWidth : 0;
    const esquerda = xSel != null && xSel * Vila.zoom - Vila.panX < largura / 2;
    alvo.classList.remove("em-cima");
    alvo.classList.toggle("lado-dir", esquerda);
    alvo.style.top = "";
  } else {
    const emCima = ySel != null && ySel * Vila.zoom - Vila.panY > (topo + base) / 2;
    alvo.classList.remove("lado-dir");
    alvo.classList.toggle("em-cima", emCima);
    alvo.style.top = emCima ? `${Math.round(topo)}px` : "";
  }
  const resposta = vilaRespostaNova(nome);
  const caixa = vilaCaixa(nome);
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
          : null,
        resposta ? el("div", {class: "vila-resposta"}, "💬 " + resposta.slice(0, 160)
          + (resposta.length > 160 ? "…" : "")) : null,
        caixa && (caixa.pendentes || caixa.em_andamento)
          ? el("div", {class: "fraco"}, caixa.em_andamento
            ? "sua mensagem foi entregue; esperando a resposta"
            : `${caixa.pendentes} mensagem(ns) sua(s) na caixa`)
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
      })(),
      VILA_CONVERSA.has(nome) && typeof conversaAbrir === "function"
        ? (() => {
          const b = el("button", {class: "acao primario", id: "vila-conversar"}, "💬 Conversar");
          b.addEventListener("click", () => conversaAbrir(nome, b, "texto"));
          return b;
        })() : null,
      vilaGerador(nome) && typeof conversaAbrir === "function"
        ? (() => {
          const g = vilaGerador(nome);
          const b = el("button", {class: "acao" + (VILA_CONVERSA.has(nome) ? "" : " primario"),
                                  id: "vila-criar"}, "🎨 Criar");
          if (!g.disponivel) {
            b.disabled = true;
            b.title = g.motivo || "não gera imagem hoje";
          }
          b.addEventListener("click", () => conversaAbrir(nome, b, "imagem"));
          return b;
        })() : null),
    vilaGerador(nome) && !vilaGerador(nome).disponivel
      ? el("div", {class: "fraco", id: "vila-criar-motivo"},
        `🎨 não gera imagem hoje: ${vilaGerador(nome).motivo}`
          + (vilaGerador(nome).proximo_passo ? " (próximo passo)" : ""))
      : null);
}

// o balão de fala em cima do prédio: a resposta que ele ainda não viu.
// `y` é a ponta do rabo; com `paraCima`, o balão fica ABAIXO de y e o rabo
// aponta para cima (é o desvio de quando o topo ficaria atrás do placar).
const VILA_BALAO_ALTURA = 14, VILA_BALAO_RABO = 4, VILA_BALAO_ACIMA = 70,
  VILA_BALAO_ABAIXO = 24;

function vilaBalaoDeFala(ctx, x, y, texto, paraCima, ocupados) {
  const curto = texto.length > 26 ? texto.slice(0, 25) + "…" : texto;
  ctx.font = "8px system-ui, sans-serif";
  const largura = Math.min(150, ctx.measureText(curto).width + 12);
  const altura = VILA_BALAO_ALTURA, rabo = VILA_BALAO_RABO;
  const ex = Math.round(x - largura / 2);
  let ey = Math.round(paraCima ? y + rabo : y - rabo - altura);
  // dois vizinhos com resposta (o Grok fica a 72 px do DeepSeek e do
  // ChatGPT) não se cobrem: o segundo sobe (ou desce) um degrau
  const lista = ocupados || [];
  const cruza = () => lista.some((o) => ex < o[0] + o[2] && ex + largura > o[0]
    && ey < o[1] + o[3] && ey + altura > o[1]);
  for (let i = 0; i < 4 && cruza(); i++) ey += (paraCima ? 1 : -1) * (altura + 3);
  lista.push([ex, ey, largura, altura]);
  ctx.beginPath();
  ctx.roundRect(ex, ey, largura, altura, 5);
  // o rabo vai até a ponta pedida (`y`), mesmo se o balão subiu um degrau
  if (paraCima) {
    ctx.moveTo(x - 4, ey);
    ctx.lineTo(x, y);
    ctx.lineTo(x + 4, ey);
  } else {
    ctx.moveTo(x - 4, ey + altura);
    ctx.lineTo(x, y);
    ctx.lineTo(x + 4, ey + altura);
  }
  ctx.fillStyle = "rgba(255, 255, 255, .96)";
  ctx.fill();
  ctx.lineWidth = .8;
  ctx.strokeStyle = "#8a5a2e";
  ctx.stroke();
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#2b2016";
  ctx.fillText(curto, x, ey + altura / 2 + 0.5, largura - 8);
  ctx.textBaseline = "alphabetic";
}

// Onde o balão da resposta fica, em coordenadas da imagem: em cima do
// prédio, como sempre; mas se o topo dele ficaria atrás do placar (prédio
// da fileira de cima com a câmera no topo, medido em 29/09), desvia para
// BAIXO do prédio, no caminho da porta, com o rabo apontando para cima.
// Pura, para o teste: recebe a porta na imagem, o zoom, o panY e o topo da
// faixa livre da tela (o fim do placar).
function vilaOndeFicaOBalao(px, py, zoom, panY, topoLivre) {
  const topoNaTela = (py - VILA_BALAO_ACIMA - VILA_BALAO_RABO - VILA_BALAO_ALTURA)
    * zoom - panY;
  if (topoNaTela >= topoLivre) return {x: px + 22, y: py - VILA_BALAO_ACIMA, paraCima: false};
  return {x: px, y: py + VILA_BALAO_ABAIXO, paraCima: true};
}

function vilaDesenharCorreio(ctx) {
  const ocupados = [];
  for (const c of ((Vila.correio || {}).ias || [])) {
    const porta = Vila.mundo.portas[c.ia];
    const texto = vilaRespostaNova(c.ia);
    if (!porta || !texto) continue;
    const [px, py] = vilaDobrar(porta[0], porta[1]);
    const b = vilaOndeFicaOBalao(px, py, Vila.zoom, Vila.panY, Vila.faixa[0]);
    vilaBalaoDeFala(ctx, b.x, b.y, texto, b.paraCima, ocupados);
  }
}

// ------------------------------------------------------------ toque
// o toque em coordenadas do MUNDO (null no céu, na sebe e no pé)
function vilaParaMundo(evento) {
  const canvas = vilaCanvas();
  const r = canvas.getBoundingClientRect();
  const toque = evento.touches ? evento.touches[0] : evento;
  return vilaDesdobrar((toque.clientX - r.left + Vila.panX) / Vila.zoom,
                       (toque.clientY - r.top + Vila.panY) / Vila.zoom);
}

function vilaClique(evento) {
  if (!vilaGeo()) return;
  const ponto = vilaParaMundo(evento);
  const canvas = vilaCanvas();
  if (!ponto) { vilaSelecionar(null); return; }
  const [x, y] = ponto;
  if (canvas) canvas.dataset.toque = `${Math.round(x)},${Math.round(y)}`;
  // o dedo é grosso e a vila inteira é pequena: a folga cresce quando ela
  // está longe (em px da tela, ~14 de cada lado)
  const folga = Math.max(0, 14 / Vila.zoom - 12);
  // primeiro o habitante (ele anda por cima), depois o lote
  const perto = (Vila.retrato?.habitantes || []).find(
    (h) => Math.abs(h.x - x) < 16 + folga
      && y > h.y - 34 - folga && y < h.y + 6 + folga);
  if (perto) { vilaSelecionar(perto.nome); return; }
  const tile = Vila.mundo.tile || 16;
  for (const [nome, lote] of Object.entries(Vila.mundo.lotes)) {
    const lx = lote.x * tile, ly = lote.y * tile;
    if (x >= lx - folga && x <= lx + 4 * tile + folga
        && y >= ly - 20 - folga && y <= ly + 3 * tile + folga) {
      vilaSelecionar(nome);
      return;
    }
  }
  vilaSelecionar(null);
}

// A câmera. Na "vila inteira" as fileiras ficam no meio da faixa livre
// (entre o placar e a prateleira); de perto, o dedo passeia, sem deixar
// a borda das fileiras entrar para dentro da faixa.
function vilaLimitar() {
  const canvas = vilaCanvas();
  const g = vilaGeo();
  if (!canvas || !g) return;
  const W = canvas.clientWidth, z = Vila.zoom;
  const [topo, base] = Vila.faixa;
  const largura = g.largura * z;
  Vila.panX = largura <= W ? -Math.round((W - largura) / 2)
    : Math.max(Math.min(Vila.panX, largura - W), 0);
  const [c0, b0] = vilaBloco();
  const cima = c0 * z, baixo = b0 * z;
  const sobra = (base - topo) - (baixo - cima);
  if (sobra >= 0) {
    // cabe: a sobra vai mais para o céu do que para a grama vazia de
    // baixo (medido: com metade para cada lado, eram ~200 px de grama)
    Vila.panY = Math.round(cima - topo - sobra * 0.7);
  } else {
    Vila.panY = Math.max(Math.min(Vila.panY, baixo - base), cima - topo);
  }
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
      const r = canvas.getBoundingClientRect();
      vilaZoom(Vila.zoom * (agora / pinca), [
        (e.touches[0].clientX + e.touches[1].clientX) / 2 - r.left,
        (e.touches[0].clientY + e.touches[1].clientY) / 2 - r.top]);
      pinca = agora;
      e.preventDefault();
      return;
    }
    if (!arrastando) return;
    const t = e.touches ? e.touches[0] : e;
    const dx = t.clientX - ultimo[0], dy = t.clientY - ultimo[1];
    moveu += Math.abs(dx) + Math.abs(dy);
    Vila.panX -= dx; Vila.panY -= dy;
    if (Vila.modo === "perto") Vila.modo = "livre";
    ultimo = [t.clientX, t.clientY];
    vilaLimitar();
    e.preventDefault();
  };
  // Um toque no celular dispara o touchend E, logo depois, o mouseup de
  // compatibilidade: o clique rodava duas vezes e o segundo DESMARCAVA o
  // prédio escolhido (visto na prova de tela de 28/09). O mouse que vem
  // até 800 ms depois de um toque é esse eco, e fica de fora.
  let toqueEm = 0;
  const doMouse = (f) => (e) => {
    if (performance.now() - toqueEm < 800) return;
    f(e);
  };
  const fim = (e) => {
    if (e.changedTouches) toqueEm = performance.now();
    if (arrastando && moveu < 8) {
      vilaClique(e.changedTouches ? e.changedTouches[0] : e);
    }
    arrastando = false; pinca = 0;
  };
  canvas.addEventListener("touchstart", (e) => {
    toqueEm = performance.now(); comeco(e);
  }, {passive: true});
  canvas.addEventListener("touchmove", mover, {passive: false});
  canvas.addEventListener("touchend", fim);
  canvas.addEventListener("mousedown", doMouse(comeco));
  canvas.addEventListener("mousemove", doMouse(mover));
  canvas.addEventListener("mouseup", doMouse(fim));
}

// `centro`: o ponto da tela que fica parado (o meio da pinça); sem ele, o
// meio da faixa livre
function vilaZoom(novo, centro) {
  const canvas = vilaCanvas();
  if (!vilaGeo() || !canvas) return;
  const antes = Vila.zoom;
  Vila.zoom = Math.max(Vila.zoomInteira,
                       Math.min(novo, Vila.zoomInteira * VILA_ZOOM_MAX));
  if (Math.abs(Vila.zoom - Vila.zoomInteira) < 0.01) Vila.zoom = Vila.zoomInteira;
  Vila.modo = Vila.zoom === Vila.zoomInteira ? "inteira" : "livre";
  const [topo, base] = Vila.faixa;
  const c = centro || [canvas.clientWidth / 2, (topo + base) / 2];
  const ponto = [(Vila.panX + c[0]) / antes, (Vila.panY + c[1]) / antes];
  Vila.panX = ponto[0] * Vila.zoom - c[0];
  Vila.panY = ponto[1] * Vila.zoom - c[1];
  vilaLimitar();
  vilaMarcarZoom();
}

// os botões dizem o que ainda dá para fazer
function vilaMarcarZoom() {
  const menos = document.getElementById("vila-menos");
  const mais = document.getElementById("vila-mais");
  if (!menos || !mais) return;
  menos.disabled = Vila.zoom <= Vila.zoomInteira + 0.001;
  mais.disabled = Vila.zoom >= Vila.zoomInteira * VILA_ZOOM_MAX - 0.001;
  const canvas = vilaCanvas();
  if (canvas) canvas.dataset.zoom = (Vila.zoom / Vila.zoomInteira).toFixed(2);
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

// Girar (ou a barra do navegador aparecer) não reabre a câmera do zero:
// só a troca de arranjo volta para o "perto" da decisão. E nada recarrega.
function vilaGirou() {
  const trocou = vilaArranjar();
  vilaAjustar();
  if (trocou) vilaCuidarDoFundo();
  if (Vila.selecionado) vilaMostrarEscolhido();
}
window.addEventListener("resize", vilaGirou);
VILA_DEITADA.addEventListener("change", vilaGirou);
vilaArranjar();

// O `app.js` monta a tela ANTES deste arquivo existir (ele carrega depois),
// e naquele instante `vilaMostrar` ainda não estava definida. Sem esta
// linha, a Vila só ligaria na segunda troca de aba.
if (tela === "vila" && localStorage.getItem(TOKEN)) vilaMostrar();
