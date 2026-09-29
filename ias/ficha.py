# -*- coding: utf-8 -*-
"""O schema da ficha de uma IA, e a tabela que compara todas.

Uma ficha e MEDIDA, nao suposta: cada campo que ninguem mediu fica `None`
(e a tabela imprime "—"), nunca um chute. Por isso `vazia()` e uma ficha
valida — o caso ZERO — e `validar()` a aceita. Um leitor que quebrasse com
a ficha vazia quebraria tambem no primeiro dia de uma IA nova.

Convencao de valores nos campos booleanos: `True` medido sim, `False`
medido nao, `None` nao medido. `fonte` diz de onde veio ("sonda", "logs",
"codigo", "docs") — o que a sonda viu vale mais do que o que o codigo
supunha.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

VERSAO = 1
RAIZ = Path(__file__).resolve().parent
PASTA_FICHAS = RAIZ / "fichas"

ROTULOS = {
    "gemini": "Gemini", "chatgpt": "ChatGPT", "deepseek": "DeepSeek",
    "grok": "Grok", "picasso": "PicassoIA", "dreamface": "DreamFace",
    "digen": "Digen",
}
TIPOS = {
    "gemini": "chat", "chatgpt": "chat", "deepseek": "chat", "grok": "chat",
    "picasso": "imagem", "dreamface": "imagem", "digen": "video",
}

ESTADOS_LOGIN = ("logado", "deslogado", "nao_sei", "sem_perfil",
                 "conta_ocupada", "nao_medido")

# As categorias do catalogo de textos. `catalogo.py` classifica por elas.
CATEGORIAS = ("recusa_enlatada", "limite", "upgrade", "parede", "cloudflare",
              "indisponivel", "erro_site", "consentimento", "conteudo",
              "login", "outro")


def vazia(ia: str) -> dict:
    """A ficha de uma IA sobre a qual nada foi medido ainda."""
    ia = str(ia or "").strip().lower()
    return {
        "versao": VERSAO,
        "ia": ia,
        "rotulo": ROTULOS.get(ia, ia or "?"),
        "tipo": TIPOS.get(ia),
        "site": None,
        "perfil": None,
        "trava": None,
        "medido_em": None,
        "duracao_s": None,
        "login": {"estado": "nao_medido", "detalhe": "", "prova": None},
        "texto": {"gera": None, "tempo_ok_s": None, "resposta": None,
                  "limite_chars_campo": None, "chars_aceitos_no_campo": None,
                  "prova": None},
        "modelos": {"ativo": None, "disponiveis": [], "seletor": None,
                    "prova": None},
        "anexos": {"imagem": None, "video": None, "arquivo": None,
                   "accept": None, "multiplos": None, "leu_o_anexo": None,
                   "seletor": None, "prova": None},
        "imagem": {"gera": None, "resolucao": None, "alfa": None,
                   "arquivo": None, "tempo_s": None, "prova_origem": None,
                   "prova": None},
        "video": {"assiste": None, "gera": None, "fonte": None},
        "catalogo_textos": [],
        "cota": {"o_que_o_site_diz": [], "plano": None, "creditos": None,
                 "prova": None},
        "custo": {"gratis": [], "pede_plano": []},
        # A "CASA" (decisao dele em 29/09/2026, no ias-chat-persistente): cada
        # IA tera UM chat de longa duracao com resumo periodico. O que importa
        # para isso: o chat aguenta ficar longo? ha limite de mensagens por
        # conversa? da para renomear/fixar? a IA lembra entre chats?
        "casa": {"chat_longo": None, "limite_mensagens_por_conversa": None,
                 "renomear": None, "fixar": None, "memoria_entre_chats": None,
                 "projetos": None, "fonte": None, "nota": ""},
        "pendencias": [],
        "capturas": [],
    }


class FichaInvalida(ValueError):
    """A ficha nao tem a forma do schema: diz o que falta."""


def validar(ficha: dict) -> list:
    """Lista de problemas (vazia = valida). Nunca levanta."""
    problemas = []
    if not isinstance(ficha, dict):
        return ["a ficha nao e um dicionario"]
    modelo = vazia(str(ficha.get("ia") or ""))
    for chave, valor in modelo.items():
        if chave not in ficha:
            problemas.append(f"falta a chave {chave!r}")
            continue
        if isinstance(valor, dict):
            if not isinstance(ficha[chave], dict):
                problemas.append(f"{chave!r} devia ser um bloco (dict)")
                continue
            for sub in valor:
                if sub not in ficha[chave]:
                    problemas.append(f"falta {chave}.{sub}")
        elif isinstance(valor, list) and not isinstance(ficha[chave], list):
            problemas.append(f"{chave!r} devia ser uma lista")
    if not ficha.get("ia"):
        problemas.append("a ficha nao diz de que IA e")
    estado = (ficha.get("login") or {}).get("estado")
    if estado not in ESTADOS_LOGIN:
        problemas.append(f"login.estado {estado!r} fora de {ESTADOS_LOGIN}")
    for n, item in enumerate(ficha.get("catalogo_textos") or []):
        if not isinstance(item, dict) or not item.get("texto"):
            problemas.append(f"catalogo_textos[{n}] sem texto")
        elif item.get("categoria") not in CATEGORIAS:
            problemas.append(
                f"catalogo_textos[{n}].categoria {item.get('categoria')!r} "
                f"fora de {CATEGORIAS}")
    return problemas


def caminho(ia: str, pasta: Path | None = None) -> Path:
    return Path(pasta or PASTA_FICHAS) / f"{str(ia).lower()}.json"


def carregar(ia: str, pasta: Path | None = None) -> dict:
    """A ficha gravada, ou a vazia se nao houver (ou estiver ilegivel)."""
    alvo = caminho(ia, pasta)
    try:
        with open(alvo, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return vazia(ia)
    if not isinstance(dados, dict):
        return vazia(ia)
    # Ficha antiga (schema menor) ganha as chaves novas sem perder as suas.
    base = vazia(ia)
    for chave, valor in base.items():
        if chave not in dados:
            dados[chave] = valor
        elif isinstance(valor, dict) and isinstance(dados[chave], dict):
            for sub, sv in valor.items():
                dados[chave].setdefault(sub, sv)
    return dados


def salvar(ficha: dict, pasta: Path | None = None) -> Path:
    problemas = validar(ficha)
    if problemas:
        raise FichaInvalida("; ".join(problemas))
    alvo = caminho(ficha["ia"], pasta)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    # LF explicito: em modo texto o Windows gravaria CRLF e o git avisaria a
    # cada commit ("CRLF will be replaced by LF").
    with open(alvo, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(ficha, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return alvo


def todas(pasta: Path | None = None, ias=None) -> list:
    from . import IAS
    return [carregar(ia, pasta) for ia in (ias or IAS)]


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ------------------------------------------------------------------ tabela
def _sim_nao(valor, sim="sim", nao="não") -> str:
    if valor is None:
        return "—"
    return sim if valor else nao


def _tempo(valor) -> str:
    if valor is None:
        return "—"
    try:
        return f"{float(valor):.0f}s"
    except (TypeError, ValueError):
        return "—"


def _login(ficha: dict) -> str:
    estado = (ficha.get("login") or {}).get("estado") or "nao_medido"
    return {"logado": "logado", "deslogado": "SEM LOGIN", "nao_sei": "não sei",
            "sem_perfil": "sem perfil", "conta_ocupada": "ocupada",
            "nao_medido": "—"}.get(estado, estado)


def _modelo(ficha: dict) -> str:
    bloco = ficha.get("modelos") or {}
    ativo = bloco.get("ativo")
    total = len(bloco.get("disponiveis") or [])
    if not ativo and not total:
        return "—"
    return f"{ativo or '?'}" + (f" (+{total - 1})" if total > 1 else "")


def _imagem(ficha: dict) -> str:
    bloco = ficha.get("imagem") or {}
    if bloco.get("gera") is None:
        return "—"
    if not bloco.get("gera"):
        return "não"
    res = bloco.get("resolucao")
    texto = "sim"
    if isinstance(res, (list, tuple)) and len(res) == 2:
        texto += f" {res[0]}x{res[1]}"
    if bloco.get("alfa") is not None:
        texto += " α" if bloco.get("alfa") else ""
    return texto


def _anexos(ficha: dict) -> str:
    bloco = ficha.get("anexos") or {}
    partes = []
    for chave, rotulo in (("imagem", "img"), ("video", "vid"),
                          ("arquivo", "arq")):
        valor = bloco.get(chave)
        if valor is None:
            continue
        partes.append(rotulo if valor else f"sem {rotulo}")
    return ", ".join(partes) if partes else "—"


def _video(ficha: dict) -> str:
    """Chat: se ASSISTE (recebe mp4). Gerador: se GERA. Os dois quando ha."""
    bloco = ficha.get("video") or {}
    partes = []
    if bloco.get("assiste") is not None:
        partes.append("assiste" if bloco["assiste"] else "não assiste")
    if bloco.get("gera") is not None:
        partes.append("gera" if bloco["gera"] else "não gera")
    return ", ".join(partes) if partes else "—"


def _catalogo(ficha: dict) -> str:
    itens = ficha.get("catalogo_textos") or []
    if not itens:
        return "—"
    por = {}
    for item in itens:
        por[item.get("categoria") or "outro"] = por.get(
            item.get("categoria") or "outro", 0) + 1
    return ", ".join(f"{c} {n}" for c, n in sorted(por.items()))


def _cota(ficha: dict) -> str:
    bloco = ficha.get("cota") or {}
    partes = []
    if bloco.get("plano"):
        partes.append(str(bloco["plano"]))
    if bloco.get("creditos") is not None:
        partes.append(f"{bloco['creditos']} créd.")
    ditos = bloco.get("o_que_o_site_diz") or []
    if ditos:
        partes.append(str(ditos[0])[:40])
    return "; ".join(partes) if partes else "—"


def _custo(ficha: dict) -> str:
    bloco = ficha.get("custo") or {}
    pede = bloco.get("pede_plano") or []
    gratis = bloco.get("gratis") or []
    if not pede and not gratis:
        return "—"
    partes = []
    if gratis:
        partes.append("grátis: " + ", ".join(str(g) for g in gratis[:3]))
    if pede:
        partes.append("plano: " + ", ".join(str(p) for p in pede[:3]))
    return " | ".join(partes)


COLUNAS = (
    ("IA", lambda f: f.get("rotulo") or f.get("ia") or "?"),
    ("login", _login),
    ("texto", lambda f: _tempo((f.get("texto") or {}).get("tempo_ok_s"))
     if (f.get("texto") or {}).get("gera") else _sim_nao((f.get("texto") or {}).get("gera"))),
    ("modelo", _modelo),
    ("anexos", _anexos),
    ("imagem", _imagem),
    ("vídeo", lambda f: _video(f)),
    ("campo", lambda f: (str((f.get("texto") or {}).get("chars_aceitos_no_campo"))
                         + " chars")
     if (f.get("texto") or {}).get("chars_aceitos_no_campo") is not None else "—"),
    ("textos catalogados", _catalogo),
    ("cota", _cota),
    ("custo", _custo),
    ("medido", lambda f: (f.get("medido_em") or "—")[:16].replace("T", " ")),
)


def linhas(fichas) -> list:
    """[[celula, ...], ...] com o cabecalho na primeira linha."""
    saida = [[nome for nome, _ in COLUNAS]]
    for ficha in fichas:
        linha = []
        for _, funcao in COLUNAS:
            try:
                linha.append(str(funcao(ficha)))
            except Exception:                                  # noqa: BLE001
                linha.append("?")
        saida.append(linha)
    return saida


def tabela(fichas) -> str:
    """A tabela em texto (markdown), pronta para o terminal e o docs."""
    grade = linhas(fichas)
    cabecalho = "| " + " | ".join(grade[0]) + " |"
    separador = "|" + "|".join("---" for _ in grade[0]) + "|"
    corpo = ["| " + " | ".join(c.replace("|", "/") for c in linha) + " |"
             for linha in grade[1:]]
    return "\n".join([cabecalho, separador] + corpo)


def tabela_png(fichas, destino: Path, titulo: str = "") -> Path:
    """A tabela desenhada num PNG (para o Grimorio). Fonte padrao do PIL."""
    from PIL import Image, ImageDraw, ImageFont

    grade = linhas(fichas)
    try:
        fonte = ImageFont.truetype("arial.ttf", 15)
        negrito = ImageFont.truetype("arialbd.ttf", 15)
    except OSError:
        fonte = negrito = ImageFont.load_default()
    medidor = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def largura(texto, f):
        return medidor.textbbox((0, 0), texto, font=f)[2]

    larguras = [max(min(largura(linha[i], negrito if n == 0 else fonte), 360)
                    for n, linha in enumerate(grade)) + 16
                for i in range(len(grade[0]))]
    altura_linha = 26
    topo = 40 if titulo else 10
    imagem = Image.new("RGB", (sum(larguras) + 20,
                               topo + altura_linha * len(grade) + 12), "white")
    tela = ImageDraw.Draw(imagem)
    if titulo:
        tela.text((10, 10), titulo, fill="black", font=negrito)
    y = topo
    for n, linha in enumerate(grade):
        if n == 0:
            tela.rectangle((10, y, 10 + sum(larguras), y + altura_linha),
                           fill=(235, 235, 235))
        elif n % 2 == 0:
            tela.rectangle((10, y, 10 + sum(larguras), y + altura_linha),
                           fill=(248, 248, 248))
        x = 10
        for i, celula in enumerate(linha):
            texto = celula
            while largura(texto, fonte) > larguras[i] - 12 and len(texto) > 3:
                texto = texto[:-2] + "…"
            tela.text((x + 6, y + 5), texto, fill="black",
                      font=negrito if n == 0 else fonte)
            x += larguras[i]
        y += altura_linha
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(destino)
    return destino
