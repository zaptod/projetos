"use strict";
// Editor local de folhas: as alteracoes so vao ao servidor ao salvar.
const AnimAtelie = {arvore: [], grupo: null, peca: null, estado: null, animacao: null,
  folha: null, imagem: null, quadros: [], ancora: {x: .5, y: 1}, fundo: "xadrez",
  quadro: 0, direcao: 1, selecionado: 0, duracoes: {}, relogio: 0, gatilhos: [], montagem: null};
const anim$ = (id) => document.getElementById(id);
const animTexto = (v) => String(v || "").replace(/[-_]/g, " ");
const animId = (v) => String(v || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-|-$/g, "");
const animAviso = (v) => { anim$("anim-aviso").textContent = v || ""; };
const animAtual = () => AnimAtelie.animacao || {};
const animPost = (rota, corpo) => api(rota, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(corpo)});
function animBotao(texto, acao, classe = "") { const b = el("button", {class: "acao " + classe, type: "button"}, texto); b.addEventListener("click", acao); return b; }
function animGrupoNome(g) { return ({lutador: "Lutador", arma: "Armas", skill: "Habilidades", habilidade: "Habilidades", efeito: "Efeitos", elemento: "Elementos", estado_personagem: "Estados", estado: "Estados", buff: "Buffs", vila: "Vila"}[String(g).toLowerCase()] || g); }
function animOrdenarFaltam(lista) { return lista; } // ponto de troca para a frequencia real das lutas
function animContar(itens) { let total = 0, arte = 0; itens.forEach(p => p.estados.forEach(e => e.animacoes.forEach(a => { total++; if (a.tem_arte) arte++; }))); return {total, arte}; }
function animDesenharGrupos() {
  const alvo = anim$("anim-grupos"); alvo.replaceChildren();
  const ordem = ["lutador", "arma", "skill", "efeito", "elemento", "estado_personagem", "buff", "vila"];
  AnimAtelie.arvore.slice().sort((a, b) => ordem.indexOf(a.grupo) - ordem.indexOf(b.grupo)).forEach(g => { const n = animContar(g.pecas); const b = animBotao(animGrupoNome(g.grupo) + " " + n.arte + "/" + n.total, () => { AnimAtelie.grupo = g; AnimAtelie.peca = null; AnimAtelie.estado = null; animDesenhar(); }, "anim-chip"); b.setAttribute("aria-pressed", String(AnimAtelie.grupo === g)); alvo.append(b); });
}
async function animCarregar() {
  const d = await api("/api/animacoes/arvore"); AnimAtelie.arvore = d.grupos || [];
  // a arvore nova traz objetos novos: reencontra grupo, peca e estado pelo id
  // (08/10: a lista velha seguia na tela e o "Mostrar de volta" nao aparecia)
  const g = AnimAtelie.grupo && AnimAtelie.arvore.find(x => x.grupo === AnimAtelie.grupo.grupo);
  AnimAtelie.grupo = g || AnimAtelie.arvore[0] || null;
  AnimAtelie.peca = AnimAtelie.peca && AnimAtelie.grupo ? (AnimAtelie.grupo.pecas.find(p => p.id === AnimAtelie.peca.id) || null) : null;
  AnimAtelie.estado = AnimAtelie.estado && AnimAtelie.peca ? (AnimAtelie.peca.estados.find(e => e.id === AnimAtelie.estado.id) || null) : null;
  animDesenhar();
}
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
  const vila = String(AnimAtelie.grupo && AnimAtelie.grupo.grupo) === "vila";
  const ordemVila = ["Habitantes", "Prédios", "Cenário", "Bichos", "Objetos", "Interface"];
  let categoria = "";
  pecas.sort((a, b) => vila ? (ordemVila.indexOf(a.categoria_vila) - ordemVila.indexOf(b.categoria_vila) || (a.rotulo || "").localeCompare(b.rotulo || "", "pt-BR")) : 0).forEach(p => { const herdada = (p.heranca || []).find(h => String(h).startsWith("arma.tipo.")); const tipo = herdada ? String(herdada).split(".").pop() : String(p.tipo || p.id).split(/[./_-]/)[0]; const proxima = vila ? p.categoria_vila : tipo; if ((armas || vila) && proxima !== categoria) { alvo.append(el("h2", {}, vila ? proxima : tipo.charAt(0).toUpperCase() + animTexto(tipo).slice(1))); categoria = proxima; } const n = animContar([p]); const b = animBotao((p.rotulo || animTexto(p.id)) + " · " + n.arte + "/" + n.total, () => { AnimAtelie.peca = p; animDesenhar(); }, "anim-peca"); alvo.append(b); const aparece = p.aparece_em || []; alvo.append(el("small", {class: aparece.length ? "fraco" : "anim-sem-arte"}, aparece.length ? "Aparece: " + aparece.join(", ") : "⚠ Ainda não aparece em lugar nenhum" + (p.motivo_sem_consumidor ? " — " + p.motivo_sem_consumidor : ""))); if (p.descricao) { const texto = p.descricao + (p.tamanho ? " · " + p.tamanho : ""); alvo.append(el("details", {class: "anim-descricao"}, el("summary", {}, "O que desenhar · mais"), el("small", {class: "fraco"}, texto))); } });
}
function animDesenharEstados(alvo) { alvo.append(el("p", {class: "fraco"}, "Escolha o estado da peça.")); AnimAtelie.peca.estados.slice().sort((a, b) => (a.rotulo || a.id).localeCompare(b.rotulo || b.id, "pt-BR")).forEach(e => { const n = animContar([{estados: [e]}]); alvo.append(animBotao((e.rotulo || animTexto(e.id)) + " · " + n.arte + "/" + n.total, () => { AnimAtelie.estado = e; animDesenhar(); })); }); }
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
  // escondida tem volta (08/10: o Adrian escondeu a Ociosa e nao havia como desfazer)
  (e.escondidas || []).forEach(a => { const linha = el("div", {class: "anim-escondida"}, el("span", {class: "fraco"}, "Escondida: " + (a.rotulo || animTexto(a.id)))); linha.append(animBotao("Mostrar de volta", () => animMostrarDeVolta(a))); alvo.append(linha); });
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
async function animAbrir(a) { AnimAtelie.animacao = a; AnimAtelie.folha = null; AnimAtelie.imagem = null; AnimAtelie.quadros = []; AnimAtelie.duracoes = {}; const vila = String(AnimAtelie.peca.id).startsWith("vila."); anim$("anim-godot").textContent = vila ? "Ver na Vila" : "Ver no Godot"; anim$("anim-montado-perto").hidden = vila; anim$("anim-editor").classList.remove("oculto"); anim$("anim-titulo").textContent = a.rotulo || a.id; anim$("anim-heranca").textContent = a.usa_a_de ? "usa a de " + a.usa_a_de : "marcador neutro"; const fonte = a.tem_arte ? AnimAtelie.peca.id : a.usa_a_de; if (fonte) { try { animPreencher(await api("/api/animacoes/" + encodeURIComponent(fonte) + "/" + encodeURIComponent(AnimAtelie.estado.id) + "/" + encodeURIComponent(a.id))); } catch (_) { animPreencher(a); } } else animPreencher(a); animDesenhar(); anim$("anim-editor").scrollIntoView({block: "start"}); }
function animOrdemDaFolha() { return AnimAtelie.quadros.slice().sort((a, b) => a.y - b.y || a.x - b.x); }
function animOrdemMudada() { return AnimAtelie.quadros.some((q, i) => q !== animOrdemDaFolha()[i]); }
function animPreencher(d) { ["escala", "rotacao"].forEach(k => anim$("anim-" + k).value = d[k] == null ? (k === "escala" ? 1 : 0) : d[k]); animFps(d.fps || 12); anim$("anim-loop").checked = d.loop !== false; anim$("anim-ida-volta").checked = !!d.ida_e_volta; anim$("anim-espelho").checked = !!d.espelho; AnimAtelie.ancora = d.ancora || {x: .5, y: 1}; AnimAtelie.quadros = d.quadros || []; AnimAtelie.duracoes = d.duracao_por_quadro || {}; anim$("anim-ordem-aviso").hidden = !animOrdemMudada(); animQuadros(); animPrevia(); animMontado(); }

async function animMontado() {
  if (String(AnimAtelie.peca.id).startsWith("vila.")) return;
  const reservado = document.querySelector(".anim-montado"); if (!reservado || !AnimAtelie.peca) return;
  let caixa = anim$("anim-montado-perto");
  if (!caixa) { caixa = el("div", {id: "anim-montado-perto", class: "anim-montado"}, "No lutador montado: ", el("canvas", {id: "anim-montado-canvas", width: 320, height: 180, "aria-label": "Lutador montado"})); anim$("anim-canvas").after(caixa); reservado.replaceChildren("No lutador montado acima."); }
  const editar = "?peca=" + encodeURIComponent(AnimAtelie.peca.id) + "&estado=" + encodeURIComponent(AnimAtelie.estado.id) + "&animacao=" + encodeURIComponent(AnimAtelie.animacao.id);
  try { const d = await api("/api/animacoes/montagem" + editar); AnimAtelie.montagem = d; await Promise.all(d.camadas.map(async c => { if (c.peca === AnimAtelie.peca.id) { c.dados = animDados(); c.imagem = AnimAtelie.imagem; return; } if (!c.folha_url || !c.animacao_url) return; c.dados = await api(c.animacao_url); c.imagem = new Image(); c.imagem.src = c.folha_url; await c.imagem.decode(); })); animDesenharMontado(); } catch (e) { caixa.append(" prévia indisponível"); }
}
function animDesenharMontado() {
  const c = anim$("anim-montado-canvas"), d = AnimAtelie.montagem; if (!c || !d) return; const x = c.getContext("2d"); x.clearRect(0, 0, c.width, c.height);
  const editada = d.camadas.find(camada => camada.peca === (AnimAtelie.peca || {}).id); if (editada) { editada.dados = animDados(); editada.imagem = AnimAtelie.imagem; }
  d.camadas.forEach(camada => { if (!camada.imagem || !camada.dados || !camada.dados.quadros.length) { if (camada.marcador && camada.categoria_marcador !== "efeitos") { x.fillStyle = "rgba(140,140,140,.9)"; if (camada.categoria_marcador === "armas") x.fillRect(camada.posicao.x, camada.posicao.y - 8, 100, 16); else x.beginPath(), x.arc(camada.posicao.x, camada.posicao.y, 42.5, 0, Math.PI * 2), x.fill(); } return; } const q = camada.dados.quadros[(camada.peca === AnimAtelie.peca.id ? AnimAtelie.quadro : 0) % camada.dados.quadros.length], a = camada.dados.ancora || {x: .5, y: 1}, escala = (camada.tamanho / Math.max(q.w, q.h)) * (+camada.dados.escala || 1); x.save(); x.translate(camada.posicao.x, camada.posicao.y); x.rotate((+camada.dados.rotacao || 0) * Math.PI / 180); x.scale(camada.dados.espelho ? -escala : escala, escala); x.drawImage(camada.imagem, q.x, q.y, q.w, q.h, -q.w * a.x, -q.h * a.y, q.w, q.h); x.restore(); });
}
function animFps(v) { v = Math.max(1, Math.min(60, +v || 12)); anim$("anim-fps").value = v; anim$("anim-fps-numero").value = v; }
function animBase64(buf) { let s = "", a = new Uint8Array(buf); for (let i = 0; i < a.length; i += 8192) s += String.fromCharCode(...a.subarray(i, i + 8192)); return btoa(s); }
async function animSubir() { const f = anim$("anim-arquivo").files[0]; if (!f) return; AnimAtelie.folha = await f.arrayBuffer(); AnimAtelie.imagem = new Image(); AnimAtelie.imagem.src = URL.createObjectURL(f); await AnimAtelie.imagem.decode(); return animRefatiar(); }
async function animRefatiar() { if (!AnimAtelie.folha) return; const grade = anim$("anim-grade").checked; const d = await api("/api/animacoes/subir", {method: "POST", body: JSON.stringify({imagem: animBase64(AnimAtelie.folha), linhas: grade ? +anim$("anim-linhas").value : 0, colunas: grade ? +anim$("anim-colunas").value : 0, margem: +anim$("anim-margem").value, espaco: +anim$("anim-espaco").value})}); if (d.folha) { const bin = atob(d.folha), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i); AnimAtelie.folha = u8.buffer; AnimAtelie.imagem = new Image(); AnimAtelie.imagem.src = URL.createObjectURL(new Blob([u8], {type: "image/png"})); await AnimAtelie.imagem.decode(); } AnimAtelie.quadros = d.quadros || []; if (!grade && AnimAtelie.quadros.length) { anim$("anim-linhas").value = new Set(AnimAtelie.quadros.map(q => q.y)).size; anim$("anim-colunas").value = new Set(AnimAtelie.quadros.map(q => q.x)).size; } AnimAtelie.selecionado = 0; AnimAtelie.duracoes = {}; anim$("anim-ordem-aviso").hidden = true; animQuadros(); animFolha(); animPrevia(); animAviso(AnimAtelie.quadros.length + " quadros encontrados" + (d.fundo ? " · fundo " + d.fundo + " tirado" : "")); }
function animFolha() {
  const c = anim$("anim-folha-canvas"), x = c.getContext("2d"); x.clearRect(0, 0, c.width, c.height); if (!AnimAtelie.imagem) return;
  const escala = Math.min(c.width / AnimAtelie.imagem.width, c.height / AnimAtelie.imagem.height), w = AnimAtelie.imagem.width * escala, h = AnimAtelie.imagem.height * escala, ox = (c.width - w) / 2, oy = (c.height - h) / 2;
  x.drawImage(AnimAtelie.imagem, ox, oy, w, h); AnimAtelie.quadros.forEach((q, i) => { x.strokeStyle = i === AnimAtelie.selecionado ? "#f60" : "#fff"; x.lineWidth = 2; x.strokeRect(ox + q.x * escala, oy + q.y * escala, q.w * escala, q.h * escala); x.fillStyle = "#111"; x.fillText(String(i + 1), ox + q.x * escala + 3, oy + q.y * escala + 12); });
}
function animQuadros() { const alvo = anim$("anim-lista-quadros"); alvo.replaceChildren(); AnimAtelie.quadros.forEach((q, i) => { const b = animBotao(String(i + 1), () => { AnimAtelie.selecionado = i; anim$("anim-segurar").value = AnimAtelie.duracoes[i] || 0; animFolha(); }, i === AnimAtelie.selecionado ? "selecionado" : ""); const apagar = animBotao("×", () => { AnimAtelie.quadros.splice(i, 1); AnimAtelie.selecionado = Math.max(0, i - 1); animQuadros(); animFolha(); }); const antes = animBotao("◀ antes", () => animMover(i, -1)); const depois = animBotao("depois ▶", () => animMover(i, 1)); alvo.append(el("span", {class: "anim-quadro"}, b, antes, depois, apagar)); }); }
function animMover(i, delta) { const j = i + delta; if (j < 0 || j >= AnimAtelie.quadros.length) return; [AnimAtelie.quadros[i], AnimAtelie.quadros[j]] = [AnimAtelie.quadros[j], AnimAtelie.quadros[i]]; AnimAtelie.selecionado = j; anim$("anim-ordem-aviso").hidden = !animOrdemMudada(); animQuadros(); animFolha(); }
function animReferencia() { const segue = (animAtual() || {}).segue || "lutador", orbital = /orbital/i.test(String((AnimAtelie.peca || {}).tipo || "")); if (/mao/.test(segue)) return {x: 205, y: 112, texto: "A âncora (+) fica na mão do lutador", mao: true, orbital}; if (/mundo|chao|fixo/.test(segue)) return {x: 160, y: 145, texto: "A âncora (+) fica no chão", chao: true, orbital}; return {x: 160, y: 100, texto: "A âncora (+) fica no corpo do lutador", orbital}; }
function animDesenharReferencia(x, r) { x.save(); x.strokeStyle = "rgba(115,115,115,.5)"; x.fillStyle = "rgba(150,150,150,.22)"; if (r.chao) { x.fillRect(35, 145, 250, 8); } else { x.beginPath(); x.arc(160, 100, 42, 0, Math.PI * 2); x.fill(); x.stroke(); if (r.mao) { x.beginPath(); x.arc(r.x, r.y, 5, 0, Math.PI * 2); x.fill(); } if (r.orbital) { x.setLineDash([4, 4]); x.beginPath(); x.arc(160, 100, 58, 0, Math.PI * 2); x.stroke(); x.setLineDash([]); } } x.restore(); }
function animPrevia() { const c = anim$("anim-canvas"), x = c.getContext("2d"), q = AnimAtelie.quadros, referencia = animReferencia(); c.className = "anim-fundo-" + AnimAtelie.fundo; x.clearRect(0, 0, c.width, c.height); animDesenharReferencia(x, referencia); if (AnimAtelie.imagem && q.length) { const r = q[AnimAtelie.quadro % q.length], tamanho = parseFloat((animAtual() || {}).tamanho_padrao) || 1, escala = tamanho * 80 / Math.max(r.w, r.h) * (+anim$("anim-escala").value || 1); x.save(); x.translate(referencia.x, referencia.y); x.rotate((+anim$("anim-rotacao").value || 0) * Math.PI / 180); x.scale(anim$("anim-espelho").checked ? -escala : escala, escala); x.drawImage(AnimAtelie.imagem, r.x, r.y, r.w, r.h, -r.w * AnimAtelie.ancora.x, -r.h * AnimAtelie.ancora.y, r.w, r.h); x.restore(); } x.strokeStyle = "#e85b20"; x.beginPath(); x.moveTo(referencia.x - 8, referencia.y); x.lineTo(referencia.x + 8, referencia.y); x.moveTo(referencia.x, referencia.y - 8); x.lineTo(referencia.x, referencia.y + 8); x.stroke(); anim$("anim-ancora-texto").textContent = referencia.texto + (referencia.orbital ? " · gira em volta do lutador" : "") + " · âncora " + Math.round(AnimAtelie.ancora.x * 100) + "% × " + Math.round(AnimAtelie.ancora.y * 100) + "%"; anim$("anim-quadros").textContent = q.length ? q.length + " quadros · toque nas miniaturas na ordem em que devem tocar" : "Escolha uma folha."; animDesenharMontado(); }
function animTocar(t) { if (!document.body.contains(anim$("anim-canvas"))) return; const q = AnimAtelie.quadros; if (q.length && t - AnimAtelie.relogio > 1000 / (+anim$("anim-fps").value || 12) + (+AnimAtelie.duracoes[AnimAtelie.quadro] || 0) * 1000) { AnimAtelie.relogio = t; AnimAtelie.quadro += AnimAtelie.direcao; if (anim$("anim-ida-volta").checked && q.length > 1 && (AnimAtelie.quadro >= q.length || AnimAtelie.quadro < 0)) { AnimAtelie.direcao *= -1; AnimAtelie.quadro += 2 * AnimAtelie.direcao; } else if (AnimAtelie.quadro >= q.length) AnimAtelie.quadro = anim$("anim-loop").checked ? 0 : q.length - 1; animPrevia(); animDesenharMontado(); } requestAnimationFrame(animTocar); }
function animDados() { const d = {}; Object.entries(AnimAtelie.duracoes).forEach(([k, v]) => { if (+v > 0) d[k] = +v; }); return {quadros: AnimAtelie.quadros, fps: +anim$("anim-fps").value, loop: anim$("anim-loop").checked, ida_e_volta: anim$("anim-ida-volta").checked, ancora: AnimAtelie.ancora, escala: +anim$("anim-escala").value, rotacao: +anim$("anim-rotacao").value, espelho: anim$("anim-espelho").checked, gatilho: animAtual().gatilho || "ocioso", duracao_por_quadro: d, versao: 1}; }
async function animSalvar(substituir = false) { if (!AnimAtelie.folha || !AnimAtelie.quadros.length) return animAviso("Escolha uma folha primeiro."); if (animAtual().tem_arte && !substituir && !confirm("Já existe uma versão. Substituir?") ) return; await api("/api/animacoes/salvar", {method: "POST", body: JSON.stringify({peca: AnimAtelie.peca.id, estado: AnimAtelie.estado.id, animacao: AnimAtelie.animacao.id, imagem: animBase64(AnimAtelie.folha), dados: animDados()})}); animAtual().tem_arte = true; animAviso("Salvo."); await animCarregar(); }
async function animVerNoGodot() {
  const atual = animAtual(); if (!atual || !AnimAtelie.peca || !AnimAtelie.estado) return;
  if (String(AnimAtelie.peca.id).startsWith("vila.")) { const r = await fetch("/api/animacoes/" + encodeURIComponent(AnimAtelie.peca.id) + "/" + encodeURIComponent(AnimAtelie.estado.id) + "/" + encodeURIComponent(atual.id) + "/previa-vila", {headers: {Authorization: "Bearer " + localStorage.getItem(TOKEN)}}); if (!r.ok) throw new Error("Prévia da Vila indisponível."); let caixa = document.querySelector(".anim-video-godot"); if (!caixa) { caixa = el("div", {id: "anim-video-godot", class: "anim-video-godot"}); anim$("anim-aviso").before(caixa); } caixa.replaceChildren(el("img", {alt: "Prévia na Vila", src: URL.createObjectURL(await r.blob())})); animAviso("Prévia da Vila pronta."); return; }
  // o Godot le o que esta no disco: folha nova ainda nao salva vai antes
  if (AnimAtelie.folha && !atual.tem_arte) await animSalvar(true);
  animAviso("Renderizando no Godot… (~1 min)");
  const trabalho = await api("/api/animacoes/previa-godot", {method: "POST", body: JSON.stringify({peca: AnimAtelie.peca.id, estado: AnimAtelie.estado.id, animacao: atual.id})});
  const consultar = async () => {
    const d = await api("/api/animacoes/previa-godot/" + encodeURIComponent(trabalho.id));
    if (d.situacao === "rodando") return setTimeout(() => consultar().catch(e => animAviso(e.message)), 3000);
    if (d.situacao === "falhou") return animAviso(d.erro || "Não consegui renderizar no Godot.");
    let caixa = document.querySelector(".anim-video-godot");
    if (!caixa) { caixa = el("div", {id: "anim-video-godot", class: "anim-video-godot"}); anim$("anim-aviso").before(caixa); }
    caixa.replaceChildren(el("video", {controls: true, autoplay: true, muted: true, loop: true, playsinline: true, src: d.video}));
    animAviso("Prévia do Godot pronta.");
  };
  await consultar();
}
async function animDesfazer() { await api("/api/animacoes/desfazer", {method: "POST", body: JSON.stringify({peca: AnimAtelie.peca.id, estado: AnimAtelie.estado.id, animacao: AnimAtelie.animacao.id})}); animAviso("Versão anterior restaurada."); }
async function animMostrarDeVolta(a) { await api("/api/animacoes/mostrar", {method: "POST", body: JSON.stringify({peca: AnimAtelie.peca.id, estado: AnimAtelie.estado.id, animacao: a.id})}); await animCarregar(); }
async function animEsconder(a = AnimAtelie.animacao) { if (!confirm("Esconder esta animação? Ela some da lista (dá para mostrar de volta).")) return; await api("/api/animacoes/esconder", {method: "POST", body: JSON.stringify({peca: AnimAtelie.peca.id, estado: AnimAtelie.estado.id, animacao: a.id})}); anim$("anim-editor").classList.add("oculto"); AnimAtelie.animacao = null; await animCarregar(); }
async function animMostrarCriar() { const d = await api("/api/animacoes/gatilhos"); AnimAtelie.gatilhos = d.gatilhos || []; const s = anim$("anim-novo-gatilho"); s.replaceChildren(...AnimAtelie.gatilhos.map(g => el("option", {value: g.id || g}, g.rotulo || animTexto(g.id || g)))); anim$("anim-criar").classList.remove("oculto"); }
async function animCriar() { const nome = anim$("anim-novo-nome").value.trim(), id = animId(nome); if (!id) return animAviso("Dê um nome à animação."); const g = anim$("anim-novo-gatilho").value; await api("/api/animacoes/criar", {method: "POST", body: JSON.stringify({peca: AnimAtelie.peca.id, estado: AnimAtelie.estado.id, animacao: {id, rotulo: nome, gatilho: g, loop: true}})}); anim$("anim-criar").classList.add("oculto"); await animCarregar(); }
function animVoltar() { if (AnimAtelie.animacao) { anim$("anim-editor").classList.add("oculto"); AnimAtelie.animacao = null; } else if (AnimAtelie.estado) AnimAtelie.estado = null; else if (AnimAtelie.peca) AnimAtelie.peca = null; animDesenhar(); }
function atelieMostrar() { animCarregar().catch(e => anim$("anim-progresso").textContent = "Falhou: " + e.message); } function atelieParar() {}
anim$("anim-voltar").addEventListener("click", animVoltar); anim$("anim-faltam").addEventListener("click", animFaltam); anim$("anim-busca").addEventListener("input", animDesenhar); anim$("anim-arquivo").addEventListener("change", () => animSubir().catch(e => animAviso(e.message)));
["anim-auto", "anim-grade", "anim-linhas", "anim-colunas", "anim-margem", "anim-espaco"].forEach(id => anim$(id).addEventListener("change", () => animRefatiar().catch(e => animAviso(e.message)))); anim$("anim-fps").addEventListener("input", () => animFps(anim$("anim-fps").value)); anim$("anim-fps-numero").addEventListener("input", () => animFps(anim$("anim-fps-numero").value)); ["anim-escala", "anim-rotacao", "anim-espelho", "anim-loop", "anim-ida-volta"].forEach(id => anim$(id).addEventListener("input", animPrevia)); anim$("anim-segurar").addEventListener("input", () => { AnimAtelie.duracoes[AnimAtelie.selecionado] = +anim$("anim-segurar").value || 0; });
["claro", "escuro", "xadrez"].forEach(f => anim$("anim-" + f).addEventListener("click", () => { AnimAtelie.fundo = f; animPrevia(); })); anim$("anim-canvas").addEventListener("pointerdown", e => { const r = e.currentTarget.getBoundingClientRect(); AnimAtelie.ancora = {x: Math.max(0, Math.min(1, .5 + (e.clientX - r.left - r.width / 2) / (r.width * .75))), y: Math.max(0, Math.min(1, .5 + (e.clientY - r.top - r.height / 2) / (r.height * .75)))}; animPrevia(); });
anim$("anim-ancora-central").addEventListener("click", () => { AnimAtelie.ancora = {x: .5, y: .5}; animPrevia(); });
anim$("anim-ancora-embaixo").addEventListener("click", () => { AnimAtelie.ancora = {x: .5, y: 1}; animPrevia(); });
anim$("anim-ordem-folha").addEventListener("click", () => { AnimAtelie.quadros = animOrdemDaFolha(); AnimAtelie.selecionado = 0; anim$("anim-ordem-aviso").hidden = true; animQuadros(); animFolha(); animPrevia(); });
anim$("anim-salvar").addEventListener("click", () => animSalvar().catch(e => animAviso(e.message))); anim$("anim-substituir").addEventListener("click", () => { if (confirm("Substituir a versão atual?")) animSalvar(true).catch(e => animAviso(e.message)); }); anim$("anim-desfazer").addEventListener("click", () => animDesfazer().catch(e => animAviso(e.message))); anim$("anim-esconder").addEventListener("click", () => animEsconder().catch(e => animAviso(e.message))); anim$("anim-fechar").addEventListener("click", animVoltar); anim$("anim-criar-botao").addEventListener("click", () => animCriar().catch(e => animAviso(e.message))); anim$("anim-godot").addEventListener("click", () => animVerNoGodot().catch(e => animAviso(e.message))); requestAnimationFrame(animTocar);
