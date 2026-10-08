"use strict";
// Editor local de folhas: as alteracoes so vao ao servidor ao salvar.
const AnimAtelie = {arvore: [], grupo: null, peca: null, estado: null, animacao: null,
  folha: null, imagem: null, quadros: [], ancora: {x: .5, y: 1}, fundo: "xadrez",
  quadro: 0, direcao: 1, selecionado: 0, duracoes: {}, relogio: 0, gatilhos: []};
const anim$ = (id) => document.getElementById(id);
const animTexto = (v) => String(v || "").replace(/[-_]/g, " ");
const animId = (v) => String(v || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-|-$/g, "");
const animAviso = (v) => { anim$("anim-aviso").textContent = v || ""; };
const animAtual = () => AnimAtelie.animacao || {};
const animPost = (rota, corpo) => api(rota, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(corpo)});
function animBotao(texto, acao, classe = "") { const b = el("button", {class: "acao " + classe, type: "button"}, texto); b.addEventListener("click", acao); return b; }
function animGrupoNome(g) { return ({lutador: "Lutador", arma: "Armas", skill: "Habilidades", habilidade: "Habilidades", efeito: "Efeitos", elemento: "Elementos", estado_personagem: "Estados", estado: "Estados", buff: "Buffs"}[String(g).toLowerCase()] || g); }
function animOrdenarFaltam(lista) { return lista; } // ponto de troca para a frequencia real das lutas
function animContar(itens) { let total = 0, arte = 0; itens.forEach(p => p.estados.forEach(e => e.animacoes.forEach(a => { total++; if (a.tem_arte) arte++; }))); return {total, arte}; }
function animDesenharGrupos() {
  const alvo = anim$("anim-grupos"); alvo.replaceChildren();
  const ordem = ["lutador", "arma", "skill", "efeito", "elemento", "estado_personagem", "buff"];
  AnimAtelie.arvore.slice().sort((a, b) => ordem.indexOf(a.grupo) - ordem.indexOf(b.grupo)).forEach(g => { const n = animContar(g.pecas); const b = animBotao(animGrupoNome(g.grupo) + " " + n.arte + "/" + n.total, () => { AnimAtelie.grupo = g; AnimAtelie.peca = null; AnimAtelie.estado = null; animDesenhar(); }, "anim-chip"); b.setAttribute("aria-pressed", String(AnimAtelie.grupo === g)); alvo.append(b); });
}
async function animCarregar() { const d = await api("/api/animacoes/arvore"); AnimAtelie.arvore = d.grupos || []; if (!AnimAtelie.grupo) AnimAtelie.grupo = AnimAtelie.arvore[0] || null; animDesenhar(); }
function animDesenhar() {
  animDesenharGrupos(); const alvo = anim$("anim-lista"); alvo.replaceChildren();
  const todos = AnimAtelie.arvore.flatMap(g => g.pecas), c = animContar(todos);
  anim$("anim-progresso").textContent = c.arte + " de " + c.total + " com arte";
  anim$("anim-busca-caixa").classList.toggle("oculto", !!AnimAtelie.estado);
  anim$("anim-caminho").textContent = [AnimAtelie.grupo && animGrupoNome(AnimAtelie.grupo.grupo), AnimAtelie.peca && (AnimAtelie.peca.rotulo || animTexto(AnimAtelie.peca.id)), AnimAtelie.estado && (AnimAtelie.estado.rotulo || animTexto(AnimAtelie.estado.id))].filter(Boolean).join(" › ") || "Grupo › peça › estado › animação";
  if (!AnimAtelie.peca) return animDesenharPecas(alvo);
  if (!AnimAtelie.estado) return animDesenharEstados(alvo);
  animDesenharAnimacoes(alvo); animAtivarCartoes();
}
function animAtivarCartoes() {
  document.querySelectorAll(".anim-cartao").forEach((cartao, indice) => {
    const abrir = () => animAbrir(AnimAtelie.estado.animacoes[indice]);
    cartao.tabIndex = 0; cartao.setAttribute("role", "button");
    cartao.addEventListener("click", (evento) => { if (!evento.target.closest("button")) abrir(); });
    cartao.addEventListener("keydown", (evento) => { if (evento.key === "Enter" || evento.key === " ") abrir(); });
  });
}
function animDesenharPecas(alvo) {
  const termo = anim$("anim-busca").value.trim().toLowerCase(); const pecas = (AnimAtelie.grupo ? AnimAtelie.grupo.pecas : []).filter(p => !termo || (p.rotulo || p.id).toLowerCase().includes(termo));
  if (!pecas.length) alvo.append(el("p", {class: "fraco"}, "Nenhuma peça encontrada."));
  const armas = /arma/i.test(String(AnimAtelie.grupo && AnimAtelie.grupo.grupo)); let ultimo = "";
  if (armas) pecas.forEach(p => { const tipo = (p.heranca || []).find(h => /^arma\.tipo\./.test(h)) || (String(p.id).startsWith("arma.tipo.") ? p.id : "arma.outros"); p.tipo = tipo.split(".").pop(); });
  pecas.forEach(p => { const tipo = String(p.tipo || p.id).split(/[./_-]/)[0]; if (armas && tipo !== ultimo) { alvo.append(el("h2", {}, animTexto(tipo))); ultimo = tipo; } const n = animContar([p]); alvo.append(animBotao((p.rotulo || animTexto(p.id)) + " · " + n.arte + "/" + n.total, () => { AnimAtelie.peca = p; animDesenhar(); }, "anim-peca")); });
}
function animDesenharEstados(alvo) { alvo.append(el("p", {class: "fraco"}, "Escolha o estado da peça.")); AnimAtelie.peca.estados.forEach(e => { const n = animContar([{estados: [e]}]); alvo.append(animBotao((e.rotulo || animTexto(e.id)) + " · " + n.arte + "/" + n.total, () => { AnimAtelie.estado = e; animDesenhar(); })); }); }
function animMiniatura(a, caixa) {
  if (!a.tem_arte) return caixa.append(el("span", {class: "anim-sem-arte"}, a.usa_a_de ? "◌ usa a de " + a.usa_a_de : "◌ falta desenhar"));
  const canvas = el("canvas", {class: "anim-miniatura", width: 72, height: 54, "aria-label": "Miniatura animada"}); caixa.append(canvas); animAnimarMiniatura(canvas, a);
}
async function animAnimarMiniatura(canvas, a) {
  try { const rota = "/api/animacoes/" + encodeURIComponent(AnimAtelie.peca.id) + "/" + encodeURIComponent(AnimAtelie.estado.id) + "/" + encodeURIComponent(a.id); const r = await fetch(rota + "/folha", {headers: {Authorization: "Bearer " + localStorage.getItem(TOKEN)}}); if (!r.ok) throw new Error(); const folha = new Image(); folha.src = URL.createObjectURL(await r.blob()); await folha.decode(); const d = await api(rota); let i = 0; const desenhar = () => { if (!document.body.contains(canvas)) { URL.revokeObjectURL(folha.src); return; } const q = d.quadros[i++ % d.quadros.length], x = canvas.getContext("2d"); x.clearRect(0, 0, 72, 54); x.drawImage(folha, q.x, q.y, q.w, q.h, 3, 3, 66, 48); setTimeout(desenhar, 1000 / (d.fps || 8)); }; desenhar(); } catch (_) {}
}
function animContain(x, imagem, q, dx, dy, dw, dh) { const escala = Math.min(dw / q.w, dh / q.h), w = q.w * escala, h = q.h * escala; x.drawImage(imagem, q.x, q.y, q.w, q.h, dx + (dw - w) / 2, dy + (dh - h) / 2, w, h); }
function animFolha() {
  const c = anim$("anim-folha-canvas"), x = c.getContext("2d"); x.clearRect(0, 0, c.width, c.height); if (!AnimAtelie.imagem) return;
  const escala = Math.min(c.width / AnimAtelie.imagem.width, c.height / AnimAtelie.imagem.height), w = AnimAtelie.imagem.width * escala, h = AnimAtelie.imagem.height * escala, ox = (c.width - w) / 2, oy = (c.height - h) / 2;
  x.drawImage(AnimAtelie.imagem, ox, oy, w, h); AnimAtelie.quadros.forEach((q, i) => { x.strokeStyle = i === AnimAtelie.selecionado ? "#f60" : "#fff"; x.lineWidth = 2; x.strokeRect(ox + q.x * escala, oy + q.y * escala, q.w * escala, q.h * escala); x.fillStyle = "#111"; x.fillText(String(i + 1), ox + q.x * escala + 3, oy + q.y * escala + 12); });
}
function animPrevia() {
  const c = anim$("anim-canvas"), x = c.getContext("2d"), q = AnimAtelie.quadros; c.className = "anim-fundo-" + AnimAtelie.fundo; x.clearRect(0, 0, c.width, c.height);
  if (AnimAtelie.imagem && q.length) { const r = q[AnimAtelie.quadro % q.length], escala = +anim$("anim-escala").value || 1; x.save(); x.translate(160, 90); x.rotate((+anim$("anim-rotacao").value || 0) * Math.PI / 180); x.scale(anim$("anim-espelho").checked ? -escala : escala, escala); animContain(x, AnimAtelie.imagem, r, -120, -75, 240, 150); x.restore(); }
  x.strokeStyle = "#e85b20"; x.beginPath(); x.moveTo(160 + 120 * (AnimAtelie.ancora.x - .5), 10); x.lineTo(160 + 120 * (AnimAtelie.ancora.x - .5), 170); x.moveTo(40, 90 + 120 * (AnimAtelie.ancora.y - .5)); x.lineTo(280, 90 + 120 * (AnimAtelie.ancora.y - .5)); x.stroke(); anim$("anim-quadros").textContent = q.length ? q.length + " quadros · arraste a cruz para a âncora" : "Escolha uma folha.";
}
function animDesenharAnimacoes(alvo) {
  const e = AnimAtelie.estado; e.animacoes.forEach(a => { const caixa = el("article", {class: "anim-cartao"}); const abrir = animBotao("", () => animAbrir(a), "anim-cartao-abrir"); abrir.append(el("strong", {}, a.rotulo || animTexto(a.id)), el("span", {class: "fraco"}, "quando toca: " + animTexto(a.gatilho)), el("small", {}, a.loop ? "repete" : "não repete")); animMiniatura(a, abrir); caixa.append(abrir, animBotao("Esconder", () => animEsconder(a))); alvo.append(caixa); }); alvo.append(animBotao("+ Nova animação", animMostrarCriar, "primario"));
}
// A folha herdada mora na peca pai; nunca se pede uma folha inexistente da filha.
function animMiniatura(a, caixa) {
  if (!a.tem_arte && !a.usa_a_de) return caixa.append(el("span", {class: "anim-sem-arte"}, "falta desenhar"));
  const canvas = el("canvas", {class: "anim-miniatura", width: 72, height: 54, "aria-label": "Miniatura animada"});
  caixa.append(canvas); animAnimarMiniatura(canvas, a, a.usa_a_de || AnimAtelie.peca.id);
}
async function animAnimarMiniatura(canvas, a, peca) {
  try {
    const rota = "/api/animacoes/" + encodeURIComponent(peca) + "/" + encodeURIComponent(AnimAtelie.estado.id) + "/" + encodeURIComponent(a.id);
    const r = await fetch(rota + "/folha", {headers: {Authorization: "Bearer " + localStorage.getItem(TOKEN)}}); if (!r.ok) throw new Error();
    const folha = new Image(); folha.src = URL.createObjectURL(await r.blob()); await folha.decode(); const d = await api(rota); let i = 0;
    const desenhar = () => { if (!document.body.contains(canvas)) { URL.revokeObjectURL(folha.src); return; } const q = d.quadros[i++ % d.quadros.length], x = canvas.getContext("2d"); x.clearRect(0, 0, 72, 54); animContain(x, folha, q, 3, 3, 66, 48); setTimeout(desenhar, 1000 / (d.fps || 8)); };
    desenhar();
  } catch (_) {}
}
function animFaltam() { const falta = animOrdenarFaltam(AnimAtelie.arvore.flatMap(g => g.pecas.flatMap(p => p.estados.flatMap(e => e.animacoes.filter(a => !a.tem_arte && !a.usa_a_de).map(a => ({p, e, a})))))); const alvo = anim$("anim-lista"); alvo.replaceChildren(el("h2", {}, "O que falta desenhar")); falta.forEach(({p, e, a}) => alvo.append(animBotao((p.rotulo || p.id) + " › " + (e.rotulo || e.id) + " › " + (a.rotulo || a.id), () => { AnimAtelie.peca = p; AnimAtelie.estado = e; animAbrir(a); }))); if (!falta.length) alvo.append(el("p", {class: "fraco"}, "Tudo tem arte ou herança.")); }
async function animAbrir(a) { AnimAtelie.animacao = a; AnimAtelie.folha = null; AnimAtelie.imagem = null; AnimAtelie.quadros = []; AnimAtelie.duracoes = {}; anim$("anim-editor").classList.remove("oculto"); anim$("anim-titulo").textContent = a.rotulo || a.id; anim$("anim-heranca").textContent = a.usa_a_de ? "usa a de " + a.usa_a_de : "marcador neutro"; try { animPreencher(await api("/api/animacoes/" + encodeURIComponent(AnimAtelie.peca.id) + "/" + encodeURIComponent(AnimAtelie.estado.id) + "/" + encodeURIComponent(a.id))); } catch (_) { animPreencher(a); } animDesenhar(); anim$("anim-editor").scrollIntoView({block: "start"}); }
function animPreencher(d) { ["escala", "rotacao"].forEach(k => anim$("anim-" + k).value = d[k] == null ? (k === "escala" ? 1 : 0) : d[k]); animFps(d.fps || 12); anim$("anim-loop").checked = d.loop !== false; anim$("anim-ida-volta").checked = !!d.ida_e_volta; anim$("anim-espelho").checked = !!d.espelho; AnimAtelie.ancora = d.ancora || {x: .5, y: 1}; AnimAtelie.quadros = d.quadros || []; AnimAtelie.duracoes = d.duracao_por_quadro || {}; animQuadros(); animPrevia(); }
function animFps(v) { v = Math.max(1, Math.min(60, +v || 12)); anim$("anim-fps").value = v; anim$("anim-fps-numero").value = v; }
function animBase64(buf) { let s = "", a = new Uint8Array(buf); for (let i = 0; i < a.length; i += 8192) s += String.fromCharCode(...a.subarray(i, i + 8192)); return btoa(s); }
async function animSubir() { const f = anim$("anim-arquivo").files[0]; if (!f) return; AnimAtelie.folha = await f.arrayBuffer(); AnimAtelie.imagem = new Image(); AnimAtelie.imagem.src = URL.createObjectURL(f); await AnimAtelie.imagem.decode(); return animRefatiar(); }
async function animRefatiar() { if (!AnimAtelie.folha) return; const grade = anim$("anim-grade").checked; const d = await api("/api/animacoes/subir", {method: "POST", body: JSON.stringify({imagem: animBase64(AnimAtelie.folha), linhas: grade ? +anim$("anim-linhas").value : 0, colunas: grade ? +anim$("anim-colunas").value : 0, margem: +anim$("anim-margem").value, espaco: +anim$("anim-espaco").value})}); AnimAtelie.quadros = d.quadros || []; AnimAtelie.selecionado = 0; AnimAtelie.duracoes = {}; animQuadros(); animFolha(); animPrevia(); animAviso(AnimAtelie.quadros.length + " quadros encontrados"); }
function animFolha() {
  const c = anim$("anim-folha-canvas"), x = c.getContext("2d"); x.clearRect(0, 0, c.width, c.height); if (!AnimAtelie.imagem) return;
  const escala = Math.min(c.width / AnimAtelie.imagem.width, c.height / AnimAtelie.imagem.height), w = AnimAtelie.imagem.width * escala, h = AnimAtelie.imagem.height * escala, ox = (c.width - w) / 2, oy = (c.height - h) / 2;
  x.drawImage(AnimAtelie.imagem, ox, oy, w, h); AnimAtelie.quadros.forEach((q, i) => { x.strokeStyle = i === AnimAtelie.selecionado ? "#f60" : "#fff"; x.lineWidth = 2; x.strokeRect(ox + q.x * escala, oy + q.y * escala, q.w * escala, q.h * escala); x.fillStyle = "#111"; x.fillText(String(i + 1), ox + q.x * escala + 3, oy + q.y * escala + 12); });
}
function animQuadros() { const alvo = anim$("anim-lista-quadros"); alvo.replaceChildren(); AnimAtelie.quadros.forEach((q, i) => { const b = animBotao(String(i + 1), () => { AnimAtelie.selecionado = i; anim$("anim-segurar").value = AnimAtelie.duracoes[i] || 0; animFolha(); }, i === AnimAtelie.selecionado ? "selecionado" : ""); const apagar = animBotao("×", () => { AnimAtelie.quadros.splice(i, 1); AnimAtelie.selecionado = Math.max(0, i - 1); animQuadros(); animFolha(); }); const antes = animBotao("←", () => animMover(i, -1)); const depois = animBotao("→", () => animMover(i, 1)); alvo.append(el("span", {class: "anim-quadro"}, b, antes, depois, apagar)); }); }
function animMover(i, delta) { const j = i + delta; if (j < 0 || j >= AnimAtelie.quadros.length) return; [AnimAtelie.quadros[i], AnimAtelie.quadros[j]] = [AnimAtelie.quadros[j], AnimAtelie.quadros[i]]; AnimAtelie.selecionado = j; animQuadros(); animFolha(); }
function animPrevia() { const c = anim$("anim-canvas"), x = c.getContext("2d"), q = AnimAtelie.quadros; c.className = "anim-fundo-" + AnimAtelie.fundo; x.clearRect(0, 0, c.width, c.height); if (AnimAtelie.imagem && q.length) { const r = q[AnimAtelie.quadro % q.length], escala = +anim$("anim-escala").value || 1; x.save(); x.translate(160, 90); x.rotate((+anim$("anim-rotacao").value || 0) * Math.PI / 180); x.scale(anim$("anim-espelho").checked ? -escala : escala, escala); x.drawImage(AnimAtelie.imagem, r.x, r.y, r.w, r.h, -r.w / 2, -r.h / 2, r.w, r.h); x.restore(); } x.strokeStyle = "#e85b20"; x.beginPath(); x.moveTo(160 + 120 * (AnimAtelie.ancora.x - .5), 10); x.lineTo(160 + 120 * (AnimAtelie.ancora.x - .5), 170); x.moveTo(40, 90 + 120 * (AnimAtelie.ancora.y - .5)); x.lineTo(280, 90 + 120 * (AnimAtelie.ancora.y - .5)); x.stroke(); anim$("anim-quadros").textContent = q.length ? q.length + " quadros · arraste a cruz para a âncora" : "Escolha uma folha."; }
function animTocar(t) { if (!document.body.contains(anim$("anim-canvas"))) return; const q = AnimAtelie.quadros; if (q.length && t - AnimAtelie.relogio > 1000 / (+anim$("anim-fps").value || 12) + (+AnimAtelie.duracoes[AnimAtelie.quadro] || 0) * 1000) { AnimAtelie.relogio = t; AnimAtelie.quadro += AnimAtelie.direcao; if (anim$("anim-ida-volta").checked && q.length > 1 && (AnimAtelie.quadro >= q.length || AnimAtelie.quadro < 0)) { AnimAtelie.direcao *= -1; AnimAtelie.quadro += 2 * AnimAtelie.direcao; } else if (AnimAtelie.quadro >= q.length) AnimAtelie.quadro = anim$("anim-loop").checked ? 0 : q.length - 1; animPrevia(); } requestAnimationFrame(animTocar); }
function animDados() { const d = {}; Object.entries(AnimAtelie.duracoes).forEach(([k, v]) => { if (+v > 0) d[k] = +v; }); return {quadros: AnimAtelie.quadros, fps: +anim$("anim-fps").value, loop: anim$("anim-loop").checked, ida_e_volta: anim$("anim-ida-volta").checked, ancora: AnimAtelie.ancora, escala: +anim$("anim-escala").value, rotacao: +anim$("anim-rotacao").value, espelho: anim$("anim-espelho").checked, gatilho: animAtual().gatilho || "ocioso", duracao_por_quadro: d, versao: 1}; }
async function animSalvar(substituir = false) { if (!AnimAtelie.folha || !AnimAtelie.quadros.length) return animAviso("Escolha uma folha primeiro."); if (animAtual().tem_arte && !substituir && !confirm("Já existe uma versão. Substituir?") ) return; await api("/api/animacoes/salvar", {method: "POST", body: JSON.stringify({peca: AnimAtelie.peca.id, estado: AnimAtelie.estado.id, animacao: AnimAtelie.animacao.id, imagem: animBase64(AnimAtelie.folha), dados: animDados()})}); animAtual().tem_arte = true; animAviso("Salvo."); await animCarregar(); }
async function animDesfazer() { await api("/api/animacoes/desfazer", {method: "POST", body: JSON.stringify({peca: AnimAtelie.peca.id, estado: AnimAtelie.estado.id, animacao: AnimAtelie.animacao.id})}); animAviso("Versão anterior restaurada."); }
async function animEsconder(a = AnimAtelie.animacao) { await api("/api/animacoes/esconder", {method: "POST", body: JSON.stringify({peca: AnimAtelie.peca.id, estado: AnimAtelie.estado.id, animacao: a.id})}); anim$("anim-editor").classList.add("oculto"); AnimAtelie.animacao = null; await animCarregar(); }
async function animMostrarCriar() { const d = await api("/api/animacoes/gatilhos"); AnimAtelie.gatilhos = d.gatilhos || []; const s = anim$("anim-novo-gatilho"); s.replaceChildren(...AnimAtelie.gatilhos.map(g => el("option", {value: g.id || g}, g.rotulo || animTexto(g.id || g)))); anim$("anim-criar").classList.remove("oculto"); }
async function animCriar() { const nome = anim$("anim-novo-nome").value.trim(), id = animId(nome); if (!id) return animAviso("Dê um nome à animação."); const g = anim$("anim-novo-gatilho").value; await api("/api/animacoes/criar", {method: "POST", body: JSON.stringify({peca: AnimAtelie.peca.id, estado: AnimAtelie.estado.id, animacao: {id, rotulo: nome, gatilho: g, loop: true}})}); anim$("anim-criar").classList.add("oculto"); await animCarregar(); }
function animVoltar() { if (AnimAtelie.animacao) { anim$("anim-editor").classList.add("oculto"); AnimAtelie.animacao = null; } else if (AnimAtelie.estado) AnimAtelie.estado = null; else if (AnimAtelie.peca) AnimAtelie.peca = null; animDesenhar(); }
function atelieMostrar() { animCarregar().catch(e => anim$("anim-progresso").textContent = "Falhou: " + e.message); } function atelieParar() {}
anim$("anim-voltar").addEventListener("click", animVoltar); anim$("anim-faltam").addEventListener("click", animFaltam); anim$("anim-busca").addEventListener("input", animDesenhar); anim$("anim-arquivo").addEventListener("change", () => animSubir().catch(e => animAviso(e.message)));
["anim-grade", "anim-linhas", "anim-colunas", "anim-margem", "anim-espaco"].forEach(id => anim$(id).addEventListener("change", () => animRefatiar().catch(e => animAviso(e.message)))); anim$("anim-fps").addEventListener("input", () => animFps(anim$("anim-fps").value)); anim$("anim-fps-numero").addEventListener("input", () => animFps(anim$("anim-fps-numero").value)); ["anim-escala", "anim-rotacao", "anim-espelho", "anim-loop", "anim-ida-volta"].forEach(id => anim$(id).addEventListener("input", animPrevia)); anim$("anim-segurar").addEventListener("input", () => { AnimAtelie.duracoes[AnimAtelie.selecionado] = +anim$("anim-segurar").value || 0; });
["claro", "escuro", "xadrez"].forEach(f => anim$("anim-" + f).addEventListener("click", () => { AnimAtelie.fundo = f; animPrevia(); })); anim$("anim-canvas").addEventListener("pointerdown", e => { const r = e.currentTarget.getBoundingClientRect(); AnimAtelie.ancora = {x: Math.max(0, Math.min(1, .5 + (e.clientX - r.left - r.width / 2) / (r.width * .75))), y: Math.max(0, Math.min(1, .5 + (e.clientY - r.top - r.height / 2) / (r.height * .75)))}; animPrevia(); });
anim$("anim-salvar").addEventListener("click", () => animSalvar().catch(e => animAviso(e.message))); anim$("anim-substituir").addEventListener("click", () => { if (confirm("Substituir a versão atual?")) animSalvar(true).catch(e => animAviso(e.message)); }); anim$("anim-desfazer").addEventListener("click", () => animDesfazer().catch(e => animAviso(e.message))); anim$("anim-esconder").addEventListener("click", () => animEsconder().catch(e => animAviso(e.message))); anim$("anim-fechar").addEventListener("click", animVoltar); anim$("anim-criar-botao").addEventListener("click", () => animCriar().catch(e => animAviso(e.message))); anim$("anim-godot").addEventListener("click", async () => { try { await api("/api/animacoes/previa-godot"); } catch (e) { animAviso(e.message || "Prévia no Godot ainda não disponível."); } }); requestAnimationFrame(animTocar);
