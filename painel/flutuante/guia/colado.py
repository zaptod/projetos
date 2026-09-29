# -*- coding: utf-8 -*-
"""As contas do guia, sem Tk: o que foi colado, o que ele e, onde fica.

Tres perguntas, tres blocos:

  O QUE E ISTO?   `detectar()` — HTML se comeca com `<`; seletor CSS/XPath
                  se tem cara de seletor; texto livre no resto. `previa()`
                  resume em uma linha (tag, id, aria, texto visivel) — e o
                  que a lista mostra e o que o agente le primeiro.
  COMO ACHAR?     `seletor_robusto()` — a partir do HTML colado, um seletor
                  por data-testid / id estavel / aria-label / role /
                  placeholder / name / texto visivel. NUNCA por classe
                  gerada (Tailwind, CSS modules, styled-components, radix):
                  esses mudam a cada build e e por isso que os seletores
                  escritos "de cabeca" quebram (ver `contos.llm.seletores`).
  ONDE GUARDAR?   `colado.jsonl` por IA — append de UMA linha inteira por
                  item; apagar reescreve por arquivo temporario + `replace`.
                  `_atual.json` e do agente do guia: aqui so se le.

A leitura e tolerante como a do diario: linha pela metade, lixo e arquivo
sumido devolvem o que der, nunca levantam.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

# ------------------------------------------------------------------ nomes
IAS = ("grok", "gemini", "chatgpt", "deepseek", "picasso", "dreamface",
       "digen")
ROTULOS = {"grok": "Grok", "gemini": "Gemini", "chatgpt": "ChatGPT",
           "deepseek": "DeepSeek", "picasso": "PicassoIA",
           "dreamface": "DreamFace", "digen": "Digen"}

# Os papeis que um item colado pode ter — na ordem dos botoes da janela.
PAPEIS = (
    ("campo_texto", "É o campo de texto"),
    ("enviar", "É o botão enviar"),
    ("resposta", "É a resposta"),
    ("seletor_modelo", "É o seletor de modelo"),
    ("anexo", "É o anexo"),
    ("gerar_imagem", "É gerar imagem"),
    ("erro_cota", "Texto de erro/cota"),
    ("observacao", "Observação"),
)
ROTULO_DO_PAPEL = dict(PAPEIS)
# Marcadores: nao carregam HTML, so dizem algo ao agente.
PAPEL_PROXIMO = "proximo"
PAPEL_MENSAGEM = "mensagem"
# A lapide: apagar NAO encolhe o arquivo. O agente do guia (`ias/guia.py`,
# `ler_colado`) le por CONTAGEM DE LINHAS; reescrever o arquivo com uma
# linha a menos faria o proximo item cair num indice que ele ja passou, e
# ele nunca o veria. Entao apagar e acrescentar `{"papel": "apagado",
# "alvo": id}`; `ler_itens` esconde o alvo e a lapide.
PAPEL_APAGADO = "apagado"
ROTULO_DO_PAPEL.update({PAPEL_PROXIMO: "próximo ▶",
                        PAPEL_MENSAGEM: "mensagem ao agente"})

TIPOS = ("html", "seletor", "texto")
# Quanto do conteudo vai para o jsonl. Um "Copy outerHTML" da pagina inteira
# passa de 1 MB; a linha nao pode virar isso. Cortado fica marcado.
LIMITE_CONTEUDO = 100_000
LIMITE_PREVIA = 160


# ============================================================== detectar
_TAGS_COMUNS = {"button", "textarea", "input", "div", "span", "a", "p",
                "form", "img", "svg", "li", "ul", "section", "main", "nav",
                "header", "footer", "label", "select", "option", "iframe",
                "video", "canvas", "body", "html"}
_CSS_CHARS = re.compile(r"^[\w\s#.\[\]='\"*:>+~(),\-^$|\\/!@%]+$")


def detectar(texto: str) -> str:
    """'html' | 'seletor' | 'texto' | '' (nada colado)."""
    limpo = (texto or "").strip()
    if not limpo:
        return ""
    if re.match(r"<[a-zA-Z!/]", limpo):          # mesmo sem fechar: e HTML
        return "html"
    if _parece_xpath(limpo) or _parece_css(limpo):
        return "seletor"
    return "texto"


def _parece_xpath(s: str) -> bool:
    if "\n" in s or len(s) > 500:
        return False
    return bool(re.match(r"^(xpath=|\(?//|\(?/[a-zA-Z*]|\./)", s))


def _parece_css(s: str) -> bool:
    if "\n" in s or len(s) > 400 or not _CSS_CHARS.match(s):
        return False
    if s.lower() in _TAGS_COMUNS:
        return True
    if s.startswith("css="):
        return True
    # Fora de aspas, um seletor tem poucos espacos (so os combinadores) e
    # toda palavra solta e uma tag; uma frase tem palavras que nao sao.
    fora = re.sub(r"'[^']*'|\"[^\"]*\"", "", s)
    if fora.count(" ") > 6 or re.search(r"[a-z][.:,] ", fora):
        return False
    for pedaco in fora.split():
        palavra = pedaco.strip(":,")
        if re.fullmatch(r"[A-Za-z]+", palavra) \
                and palavra.lower() not in _TAGS_COMUNS:
            return False
    if re.match(r"^[#.]\S", s):
        return True
    if any(marca in fora for marca in ("[", ">", ":", "#", ".")):
        return bool(re.match(r"^[a-zA-Z*\[#.:]", s))
    return False


# ================================================================ o HTML
_VAZIAS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
           "link", "meta", "param", "source", "track", "wbr"}
_INVISIVEIS = {"script", "style", "template", "noscript"}
_ICONES = {"svg", "path", "g", "circle", "rect", "line", "polygon",
           "polyline", "use", "defs", "clippath", "mask", "symbol"}
_ATRIBUTOS_UTEIS = ("id", "role", "aria-label", "aria-labelledby",
                    "data-testid", "data-test-id", "data-test", "placeholder",
                    "name", "type", "contenteditable", "href", "title",
                    "value", "aria-haspopup", "aria-expanded", "disabled",
                    "class")


class Elemento:
    __slots__ = ("tag", "attrs", "_texto", "profundidade")

    def __init__(self, tag: str, attrs: dict, profundidade: int):
        self.tag = tag
        self.attrs = attrs
        self._texto: list = []
        self.profundidade = profundidade

    @property
    def texto(self) -> str:
        return " ".join(" ".join(self._texto).split())

    def get(self, chave: str) -> str:
        return (self.attrs.get(chave) or "").strip()


class _Leitor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elementos: list = []
        self._abertos: list = []
        self._mudo = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        atributos = {}
        for chave, valor in attrs:
            if chave in _ATRIBUTOS_UTEIS or chave.startswith("aria-") \
                    or chave.startswith("data-"):
                atributos[chave] = valor if valor is not None else ""
        elemento = Elemento(tag, atributos, len(self._abertos))
        self.elementos.append(elemento)
        if tag in _INVISIVEIS:
            self._mudo += 1
        if tag not in _VAZIAS:
            self._abertos.append(elemento)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in _VAZIAS:
            self._fechar(tag.lower())

    def handle_endtag(self, tag):
        self._fechar(tag.lower())

    def _fechar(self, tag: str) -> None:
        for indice in range(len(self._abertos) - 1, -1, -1):
            if self._abertos[indice].tag == tag:
                del self._abertos[indice:]
                if tag in _INVISIVEIS:
                    self._mudo = max(0, self._mudo - 1)
                return

    def handle_data(self, data):
        if self._mudo or not data.strip():
            return
        # Dentro de um <svg> (o <title> do icone) nada e texto visivel —
        # nem para o botao que embrulha o icone.
        if any(aberto.tag in _ICONES for aberto in self._abertos):
            return
        for aberto in self._abertos:
            aberto._texto.append(data.strip())


def analisar_html(html: str) -> list:
    """Os elementos do trecho, na ordem do documento (o de fora primeiro).

    Tolerante: HTML pela metade e tag sem fechar nao levantam.
    """
    leitor = _Leitor()
    try:
        leitor.feed(html or "")
        leitor.close()
    except Exception:                                        # noqa: BLE001
        pass
    return leitor.elementos


# ============================================================ o seletor
# Nomes que uma ferramenta gerou e o proximo build troca. Se um id ou uma
# classe casa aqui, ele NAO serve de ancora.
_GERADO = (
    re.compile(r"[0-9a-f]{6,}", re.I),          # hash hexadecimal
    re.compile(r"\d{4,}"),                       # numero comprido
    re.compile(r":r[0-9a-z]+:"),                 # React useId / radix
    re.compile(r"^(css|sc|jsx|ember|ng|mui|chakra|mantine)-", re.I),
    re.compile(r"^(headlessui|radix)-"),
)


def parece_gerado(nome: str) -> bool:
    """`prompt-textarea`, `sendButton`, `__next` sao nomes; `x8f2Kq`,
    `radix-:r5:`, `css-1abc23`, `Message_bubble__x8f2K` sao gerados."""
    nome = (nome or "").strip()
    if not nome:
        return True
    if any(p.search(nome) for p in _GERADO):
        return True
    for segmento in re.split(r"[-_:.\s]+", nome):
        if not segmento:
            continue
        # letras e digitos misturados num bloco de 5+ (`x8f2Kq`, `Ab12Cd34`)
        if len(segmento) >= 5 and re.search(r"\d", segmento) \
                and re.search(r"[A-Za-z]", segmento):
            return True
        letras = re.sub(r"\d", "", segmento)
        # um bloco comprido sem vogal nenhuma nao e palavra de ninguem
        if len(letras) >= 5 and not re.search(r"[aeiouyAEIOUY]", letras):
            return True
    return False


def _aspas(valor: str) -> str:
    return "'" + valor.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _candidato(el: Elemento):
    """(prioridade, seletor, motivo) para UM elemento, ou None."""
    tag = el.tag
    if tag in _ICONES or tag in _INVISIVEIS:
        return None
    for chave in ("data-testid", "data-test-id", "data-test"):
        valor = el.get(chave)
        if valor and not parece_gerado(valor):
            return (0, f"{tag}[{chave}={_aspas(valor)}]", f"por {chave}")
    ident = el.get("id")
    if ident and not parece_gerado(ident):
        seletor = f"#{ident}" if re.fullmatch(r"[A-Za-z_][\w-]*", ident) \
            else f"[id={_aspas(ident)}]"
        return (1, seletor, "por id estável")
    aria = el.get("aria-label")
    if aria:
        return (2, f"{tag}[aria-label={_aspas(aria)}]", "por aria-label")
    papel = el.get("role")
    marcador = el.get("placeholder") or el.get("name")
    if papel and marcador:
        chave = "placeholder" if el.get("placeholder") else "name"
        return (3, f"{tag}[role={_aspas(papel)}][{chave}={_aspas(marcador)}]",
                "por role + " + chave)
    if el.get("placeholder"):
        return (4, f"{tag}[placeholder={_aspas(el.get('placeholder'))}]",
                "por placeholder")
    if el.get("name"):
        return (4, f"{tag}[name={_aspas(el.get('name'))}]", "por name")
    if tag == "button" and el.get("type") == "submit":
        return (5, "button[type='submit']", "por type=submit")
    if el.get("contenteditable") in ("true", "", "plaintext-only") \
            and "contenteditable" in el.attrs:
        return (5, f"{tag}[contenteditable]", "por contenteditable")
    texto = el.texto
    if texto and len(texto) <= 40:
        # O que se clica vem antes do que so embrulha: um `div` com o mesmo
        # texto do botao de dentro perde para o botao.
        peso = {"button": 6, "a": 6, "label": 6, "option": 6, "li": 7,
                "span": 7, "p": 7, "div": 8}.get(tag)
        if peso is not None:
            return (peso, f"{tag}:has-text({_aspas(texto)})",
                    "pelo texto visível")
    if papel:
        return (9, f"{tag}[role={_aspas(papel)}]", "só pelo role (fraco)")
    if tag in ("textarea", "input", "select", "video", "iframe", "img"):
        tipo = el.get("type")
        extra = f"[type={_aspas(tipo)}]" if tipo else ""
        return (10, f"{tag}{extra}", "só pela tag (fraco)")
    return None


def seletor_robusto(html: str) -> tuple:
    """(seletor, motivo). Sem ancora nenhuma: ('', 'sem âncora...').

    Entre dois candidatos de mesma prioridade vence o de FORA (o que o
    Adrian colou), nunca um filho escondido.
    """
    elementos = analisar_html(html)
    melhor = None
    for el in elementos:
        cand = _candidato(el)
        if cand is None:
            continue
        chave = (cand[0], el.profundidade)
        if melhor is None or chave < melhor[0]:
            melhor = (chave, cand)
    if melhor is None:
        if elementos:
            return (elementos[0].tag,
                    "sem âncora robusta (só classe gerada) — edite antes de "
                    "gravar")
        return ("", "não achei elemento nenhum no HTML colado")
    _, (_, seletor, motivo) = melhor
    return (seletor, motivo)


# ============================================================== a previa
def _cortar(texto: str, limite: int) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


def previa(texto: str, tipo: str | None = None) -> dict:
    """Um dicionario com `tipo`, `resumo` (uma linha) e os campos lidos."""
    tipo = tipo or detectar(texto)
    limpo = (texto or "").strip()
    if tipo == "html":
        return _previa_html(limpo)
    if tipo == "seletor":
        nome = "XPath" if _parece_xpath(limpo) else "CSS"
        return {"tipo": tipo, "resumo": _cortar(f"{nome}: {limpo}",
                                                LIMITE_PREVIA)}
    if tipo == "texto":
        return {"tipo": tipo, "resumo": _cortar(limpo, LIMITE_PREVIA),
                "linhas": limpo.count("\n") + 1}
    return {"tipo": "", "resumo": ""}


def _previa_html(html: str) -> dict:
    elementos = analisar_html(html)
    if not elementos:
        return {"tipo": "html", "resumo": "HTML sem elemento reconhecível",
                "elementos": 0}
    fora = elementos[0]
    partes = [fora.tag]
    info = {"tipo": "html", "tag": fora.tag, "elementos": len(elementos)}
    if fora.get("type"):
        partes[0] += f"[type={fora.get('type')}]"
    for chave, nome in (("id", "#"), ("role", "role "),
                        ("aria-label", "aria "),
                        ("data-testid", "testid "),
                        ("placeholder", "placeholder "),
                        ("name", "name ")):
        valor = fora.get(chave)
        if valor:
            info[chave] = valor
            partes.append(f"{nome}«{_cortar(valor, 40)}»" if nome != "#"
                          else f"#{_cortar(valor, 30)}")
    if "contenteditable" in fora.attrs:
        partes.append("editável")
    texto = fora.texto
    if texto:
        info["texto"] = _cortar(texto, 200)
        partes.append(f"«{_cortar(texto, 50)}»")
    if len(elementos) > 1:
        partes.append(f"+{len(elementos) - 1} dentro")
    info["resumo"] = _cortar(" · ".join(partes), LIMITE_PREVIA)
    return info


# ============================================================ o arquivo
def pasta_ias(raiz: Path) -> Path:
    return Path(raiz) / "random_builds" / "outputs" / "_ias"


def caminho_atual(pasta: Path) -> Path:
    return Path(pasta) / "_atual.json"


def caminho_colado(pasta: Path, ia: str) -> Path:
    return Path(pasta) / str(ia).lower() / "guia" / "colado.jsonl"


def _agora_iso(agora: datetime | None = None) -> str:
    momento = agora or datetime.now().astimezone()
    return momento.isoformat(timespec="seconds")


def novo_id(agora: datetime | None = None) -> str:
    momento = agora or datetime.now()
    return f"{momento:%Y%m%d%H%M%S}-{secrets.token_hex(2)}"


def item_novo(ia: str, papel: str, conteudo: str = "", *,
              passo: str | None = None, tipo: str | None = None,
              seletor: str | None = None,
              agora: datetime | None = None) -> dict:
    """Uma linha do `colado.jsonl`, pronta para gravar.

    Chaves fixas: `id`, `em`, `ia`, `papel`, `tipo`, `conteudo`, `previa`;
    `passo` (do `_atual.json`) e `seletor_sugerido` (o seletor como ficou
    DEPOIS de ele editar — o nome e o que `ias/guia.py` le) quando existem;
    `cortado` quando o conteudo passou de LIMITE_CONTEUDO.
    """
    conteudo = str(conteudo or "")
    tipo = tipo if tipo in TIPOS else detectar(conteudo)
    resumo = previa(conteudo, tipo) if conteudo else {"resumo": ""}
    item = {"id": novo_id(agora), "em": _agora_iso(agora),
            "ia": str(ia).lower(), "papel": papel, "tipo": tipo or "",
            "conteudo": conteudo[:LIMITE_CONTEUDO],
            "previa": resumo.get("resumo", "")}
    if len(conteudo) > LIMITE_CONTEUDO:
        item["cortado"] = True
    if passo:
        item["passo"] = passo
    if seletor:
        item["seletor_sugerido"] = seletor.strip()
    return item


def gravar_item(caminho: Path, item: dict) -> bool:
    """Acrescenta UMA linha inteira. Nunca levanta; False se nao deu."""
    try:
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        linha = json.dumps(item, ensure_ascii=False) + "\n"
        with open(caminho, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(linha)
            fh.flush()
            os.fsync(fh.fileno())
        return True
    except (OSError, TypeError, ValueError):
        return False


def ler_linhas(caminho: Path) -> list:
    """Todas as linhas validas, na ordem, lapides incluidas."""
    try:
        bruto = Path(caminho).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    linhas = []
    for linha in bruto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            dado = json.loads(linha)
        except ValueError:
            continue
        if isinstance(dado, dict) and dado.get("papel"):
            linhas.append(dado)
    return linhas


def ler_itens(caminho: Path) -> list:
    """O que esta valendo: sem os apagados e sem as lapides."""
    linhas = ler_linhas(caminho)
    apagados = {str(l.get("alvo")) for l in linhas
                if l.get("papel") == PAPEL_APAGADO}
    return [l for l in linhas
            if l.get("papel") != PAPEL_APAGADO
            and str(l.get("id")) not in apagados]


def apagar_item(caminho: Path, id_item: str,
                agora: datetime | None = None) -> bool:
    """Acrescenta a lapide (ver PAPEL_APAGADO). False se o item nao existe."""
    if not any(i.get("id") == id_item for i in ler_itens(caminho)):
        return False
    return gravar_item(caminho, {"id": novo_id(agora), "em": _agora_iso(agora),
                                 "papel": PAPEL_APAGADO, "alvo": id_item})


def ler_atual(caminho: Path) -> dict | None:
    """O `_atual.json` do agente do guia, ou None (caso zero: sem arquivo).

    Formato: {"ia": "grok", "passo": "onde escreve", "desde": iso}. Sem `ia`
    reconhecivel tambem e None — a janela cai no seletor manual.
    """
    try:
        dado = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(dado, dict):
        return None
    ia = str(dado.get("ia") or "").strip().lower()
    if not ia:
        return None
    return {"ia": ia, "passo": str(dado.get("passo") or "").strip(),
            "desde": dado.get("desde")}


def ha_quanto(desde, agora: datetime | None = None) -> str:
    """'há 3 min' a partir de um ISO; '' se nao der para ler."""
    try:
        inicio = datetime.fromisoformat(str(desde))
    except (TypeError, ValueError):
        return ""
    if agora is None:
        agora = datetime.now(inicio.tzinfo) if inicio.tzinfo \
            else datetime.now()
    try:
        segundos = int((agora - inicio).total_seconds())
    except TypeError:
        return ""
    if segundos < 60:
        return "agora"
    if segundos < 3600:
        return f"há {segundos // 60} min"
    return f"há {segundos // 3600} h {(segundos % 3600) // 60:02d}"


def hora_curta(iso) -> str:
    try:
        return datetime.fromisoformat(str(iso)).strftime("%H:%M")
    except (TypeError, ValueError):
        return "—"


# ======================================================== preferencias
# O UNICO arquivo que a janela do guia escreve fora de `_ias/`: onde ela
# estava, de que tamanho, se fica por cima e se esta recolhida.
PADRAO_PREFS = {"x": None, "y": None, "largura": 400, "altura": 660,
                "topo": True, "recolhida": False, "ia_manual": None}
TAMANHO_MINIMO = (340, 480)
ALTURA_RECOLHIDA = 34


def ler_prefs(caminho: Path) -> dict:
    dados = dict(PADRAO_PREFS)
    try:
        salvo = json.loads(Path(caminho).read_text(encoding="utf-8"))
        if isinstance(salvo, dict):
            dados.update({k: v for k, v in salvo.items()
                          if k in PADRAO_PREFS})
    except (OSError, ValueError):
        pass
    try:
        dados["largura"] = max(TAMANHO_MINIMO[0], int(dados["largura"]))
        dados["altura"] = max(TAMANHO_MINIMO[1], int(dados["altura"]))
    except (TypeError, ValueError):
        dados["largura"], dados["altura"] = (PADRAO_PREFS["largura"],
                                             PADRAO_PREFS["altura"])
    if dados["ia_manual"] not in IAS:
        dados["ia_manual"] = None
    return dados


def gravar_prefs(caminho: Path, dados: dict) -> bool:
    try:
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = caminho.with_suffix(".tmp")
        temporario.write_text(json.dumps(
            {k: dados.get(k) for k in PADRAO_PREFS}, ensure_ascii=False,
            indent=1), encoding="utf-8")
        os.replace(temporario, caminho)
        return True
    except OSError:
        return False


__all__ = ["ALTURA_RECOLHIDA", "IAS", "LIMITE_CONTEUDO", "PADRAO_PREFS",
           "PAPEIS", "PAPEL_APAGADO", "PAPEL_MENSAGEM", "PAPEL_PROXIMO",
           "ROTULOS", "ROTULO_DO_PAPEL", "TAMANHO_MINIMO", "TIPOS",
           "analisar_html", "apagar_item", "caminho_atual", "caminho_colado",
           "detectar", "gravar_item", "gravar_prefs", "ha_quanto",
           "hora_curta", "item_novo", "ler_atual", "ler_itens", "ler_linhas",
           "ler_prefs", "novo_id", "parece_gerado", "pasta_ias", "previa",
           "seletor_robusto"]
