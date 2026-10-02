"use strict";
// A Biblioteca: coisas que o Adrian publicou ou guardou, sempre so para ler.

const Biblioteca = {dados: null, aba: "paginas", busca: "", carregando: false};

function bibliotecaEscapar(texto) {
  return String(texto).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function bibliotecaEmLinha(texto) {
  let saida = bibliotecaEscapar(texto);
  saida = saida.replace(/`([^`]+)`/g, "<code>$1</code>");
  saida = saida.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_tudo, rotulo, url) => {
      try {
        if (!/^https?:$/.test(new URL(url).protocol)) return rotulo;
      } catch (_) { return rotulo; }
      return `<a href="${url}" target="_blank" rel="noopener">${rotulo}</a>`;
    });
  saida = saida.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  saida = saida.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  return saida.replace(/(^|[^\w])_([^_]+)_/g, "$1<em>$2</em>");
}

// A funcao e pura: o unico HTML que ela recebe e escapado ANTES de formatar.
function bibliotecaMarkdown(texto) {
  const linhas = String(texto).replace(/\r\n?/g, "\n").split("\n");
  const saida = [];
  let codigo = null, lista = null, paragrafo = [];
  const fecharParagrafo = () => {
    if (paragrafo.length) saida.push(`<p>${paragrafo.map(bibliotecaEmLinha).join("<br>")}</p>`);
    paragrafo = [];
  };
  const fecharLista = () => { if (lista) saida.push(`</${lista}>`); lista = null; };
  for (let i = 0; i < linhas.length; i += 1) {
    const linha = linhas[i];
    if (linha.startsWith("```")) {
      fecharParagrafo(); fecharLista();
      if (codigo === null) codigo = [];
      else { saida.push(`<pre><code>${bibliotecaEscapar(codigo.join("\n"))}</code></pre>`); codigo = null; }
      continue;
    }
    if (codigo !== null) { codigo.push(linha); continue; }
    const titulo = linha.match(/^(#{1,6})\s+(.+)$/);
    const item = linha.match(/^\s*[-*+]\s+(.+)$/);
    const numero = linha.match(/^\s*\d+[.)]\s+(.+)$/);
    if (titulo) {
      fecharParagrafo(); fecharLista();
      const nivel = titulo[1].length;
      saida.push(`<h${nivel}>${bibliotecaEmLinha(titulo[2])}</h${nivel}>`);
    } else if (item || numero) {
      fecharParagrafo();
      const tipo = numero ? "ol" : "ul";
      if (lista !== tipo) { fecharLista(); saida.push(`<${tipo}>`); lista = tipo; }
      saida.push(`<li>${bibliotecaEmLinha((item || numero)[1])}</li>`);
    } else if (/^\s*\|.*\|\s*$/.test(linha)
               && i + 1 < linhas.length && /^\s*\|?\s*:?-{3,}/.test(linhas[i + 1])) {
      fecharParagrafo(); fecharLista();
      const celulas = (s) => s.trim().replace(/^\||\|$/g, "").split("|");
      const cabeca = celulas(linha);
      i += 1;
      const corpo = [];
      while (i + 1 < linhas.length && /^\s*\|.*\|\s*$/.test(linhas[i + 1])) {
        i += 1; corpo.push(celulas(linhas[i]));
      }
      saida.push("<table><thead><tr>" + cabeca.map((c) => `<th>${bibliotecaEmLinha(c)}</th>`).join("")
        + "</tr></thead><tbody>" + corpo.map((linhaTabela) => "<tr>"
          + linhaTabela.map((c) => `<td>${bibliotecaEmLinha(c)}</td>`).join("")
          + "</tr>").join("") + "</tbody></table>");
    } else if (!linha.trim()) {
      fecharParagrafo(); fecharLista();
    } else {
      fecharLista(); paragrafo.push(linha);
    }
  }
  fecharParagrafo(); fecharLista();
  if (codigo !== null) saida.push(`<pre><code>${bibliotecaEscapar(codigo.join("\n"))}</code></pre>`);
  return saida.join("\n");
}

function bibliotecaItens() {
  const grupos = (Biblioteca.dados || {}).grupos || {};
  return grupos[Biblioteca.aba] || [];
}

function bibliotecaCartao(item) {
  const meta = [item.tipo, ...(item.tags || [])].join(" · ");
  const corpo = [el("strong", {}, item.titulo), el("div", {class: "fraco"}, meta)];
  if (item.descricao) corpo.push(el("div", {class: "fraco"}, item.descricao));
  if (item.tipo === "pagina" && /^https:\/\//.test(item.url || "")) {
    return el("a", {class: "biblioteca-cartao", href: item.url, target: "_blank", rel: "noopener"}, ...corpo);
  }
  const botao = el("button", {class: "biblioteca-cartao", type: "button"}, ...corpo);
  botao.addEventListener("click", () => bibliotecaAbrir(item));
  return botao;
}

function bibliotecaDesenhar() {
  const termo = Biblioteca.busca.trim().toLocaleLowerCase();
  const itens = bibliotecaItens().filter((item) => !termo || [item.titulo, item.descricao,
    item.tipo, ...(item.tags || [])].join(" ").toLocaleLowerCase().includes(termo));
  $("biblioteca-lista").replaceChildren(...(itens.length ? itens.map(bibliotecaCartao) :
    [el("div", {class: "fraco"}, "Nenhum artefato neste grupo.")]));
}

async function bibliotecaAbrir(item) {
  if (item.tipo === "pagina") return;
  try {
    const dados = await api(`/api/biblioteca/doc/${encodeURIComponent(item.id)}`);
    $("biblioteca-titulo").textContent = item.titulo;
    // `bibliotecaMarkdown` escapa integralmente o texto antes de inserir tags seguras.
    $("biblioteca-texto").innerHTML = bibliotecaMarkdown(dados.texto);
    $("biblioteca-listas").classList.add("oculto");
    $("biblioteca-leitor").classList.remove("oculto");
    conexao(true);
  } catch (err) { conexao(false, err); }
}

async function bibliotecaMostrar() {
  $("biblioteca-leitor").classList.add("oculto");
  $("biblioteca-listas").classList.remove("oculto");
  if (Biblioteca.carregando) return;
  Biblioteca.carregando = true;
  try {
    Biblioteca.dados = await api("/api/biblioteca");
    bibliotecaDesenhar(); conexao(true);
  } catch (err) { conexao(false, err); }
  Biblioteca.carregando = false;
}

function bibliotecaParar() {}

$("biblioteca-abas").addEventListener("click", (evento) => {
  const botao = evento.target.closest("button[data-aba]");
  if (!botao) return;
  Biblioteca.aba = botao.dataset.aba;
  for (const aba of $("biblioteca-abas").querySelectorAll("button"))
    aba.setAttribute("aria-pressed", String(aba === botao));
  bibliotecaDesenhar();
});
$("biblioteca-busca").addEventListener("input", (evento) => {
  Biblioteca.busca = evento.target.value; bibliotecaDesenhar();
});
$("biblioteca-voltar-lista").addEventListener("click", () => {
  $("biblioteca-leitor").classList.add("oculto");
  $("biblioteca-listas").classList.remove("oculto");
});
