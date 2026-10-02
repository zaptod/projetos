"""A biblia textual de estilo enviada a cada pedido de imagem.

Uma biblia por perfil (`config.PERFIS`): o palco segue com o texto de sempre;
a Vila (decisao `painel-e-vila/vila-estilo-novo`) usa o MESMO estilo do Neural
-- cartoon, contorno escuro, 2 tons -- e descreve a folha linha a linha,
porque cada linha da folha da Vila e um ciclo de animacao.
"""
from __future__ import annotations

from . import config

# O estilo escolhido pelo Adrian no Grimorio (builds/imagem-mestra-v2 = "2 Anime",
# 02/10/2026): o mesmo texto que gerou a imagem-mestra, para o palco e a Vila.
# O ChatGPT nao recebe anexo, entao o estilo tem de ir escrito.
ESTILO = ("Estilo anime cel-shading de jogo de luta moderno: formas dinâmicas, brilhos marcados, "
          "contorno preto forte de tinta com espessura variada, contraste de cor dramático, "
          "luz do alto à esquerda, legível pequeno. Nada de pixel art, nada de 3D.")

ROXOS_OU_ROSAS = ("TREVAS", "ARCANO", "VOID", "TEMPO", "GRAVITACAO",
                   "ROXO", "ROXA", "ROSA", "MAGENTA")


def fundo_do(item: dict) -> str:
    # `chroma` explicito no item (inventario da Vila) manda; sem ele, a
    # regra antiga por palavra-chave, que e a do palco.
    chroma = str(item.get("chroma") or "").strip().upper()
    if chroma in ("#00FF00", "#FF00FF"):
        return chroma
    texto = " ".join((str(item.get("id", "")), str(item.get("nome_arquivo", "")),
                       str(item.get("descricao", "")))).upper()
    return "#00FF00" if any(nome in texto for nome in ROXOS_OU_ROSAS) else "#FF00FF"


def opaco(item: dict) -> bool:
    """Textura opaca (chao, caminho): sem chroma, emenda nos 4 lados."""
    return str(item.get("fundo", "")).strip().lower().startswith("opaco")


def grade(item: dict) -> tuple[int, int]:
    """(colunas, linhas) da folha; 4x4 quando o item nao diz."""
    valor = (item.get("animacao") or {}).get("grade") or (4, 4)
    return int(valor[0]), int(valor[1])


def animacao(item: dict) -> dict | None:
    """A animacao em ciclo do item, ou None (peca, ou folha de impacto)."""
    anim = item.get("animacao") or {}
    if item.get("tipo") != "folha" or not anim.get("ciclo") or not anim.get("ciclos"):
        return None
    return anim


def montar(item: dict, defeitos: str = "", perfil: str | None = None) -> str:
    if (perfil or config.PERFIL) == "vila":
        return _vila(item, defeitos)
    return _palco(item, defeitos)


def _palco(item: dict, defeitos: str) -> str:
    fundo = fundo_do(item)
    tipo = item.get("tipo", "peca")
    partes = [
        "Arte 2D para Neural Fights.",
        ESTILO,
        f"Desenhe: {item.get('descricao') or item.get('nome_arquivo') or item['id']}.",
        "Sem texto, numeros, grade desenhada ou moldura.",
        f"Fundo liso uniforme {fundo}, sem sombra no fundo.",
    ]
    if tipo == "folha":
        partes.append("Folha 4x4 com exatamente 16 quadros de animacao, igualmente espacados, sem linhas entre quadros.")
    else:
        partes.append("Peca parada: um objeto unico, centrado, sem tocar a borda.")
        texto = " ".join(str(item.get(k, "")) for k in ("id", "nome_arquivo", "descricao")).lower()
        if "arma" in texto or "projetil" in texto:
            partes.append("Arma ou projetil aponta para a direita.")
    if config.mestra().is_file():
        partes.append("Siga rigorosamente o estilo da imagem-mestra aprovada do Neural Fights.")
    if defeitos:
        partes.append(f"Corrija estes defeitos da tentativa anterior: {defeitos}.")
    return " ".join(partes)


def _onde(quadros: list, colunas: int) -> str:
    linhas = sorted({q // colunas for q in quadros})
    if len(linhas) == 1 and len(quadros) == colunas:
        return f"Linha {linhas[0] + 1}"
    return f"Quadros {quadros[0] + 1} a {quadros[-1] + 1} (da esquerda para a direita, de cima para baixo)"


def _vila(item: dict, defeitos: str) -> str:
    desenho = str(item.get("descricao") or item.get("nome_arquivo") or item["id"]).rstrip(". ")
    partes = [
        "Arte para a Vila do Neural Fights, no MESMO estilo dos lutadores do Neural Fights:",
        ESTILO,
    ]
    if not opaco(item):
        partes.append("Vista de frente, levemente de cima (3/4), como uma vila de jogo.")
    partes += [f"Desenhe: {desenho}.",
               "Sem texto, letras, números, logotipo de marca, grade desenhada ou moldura."]
    if opaco(item):
        partes.append("Imagem OPACA que emenda sem costura nos 4 lados (textura contínua vista de cima), "
                      "sem objeto central, sem moldura e sem sombra projetada.")
    else:
        fundo = fundo_do(item)
        partes.append(f"Fundo liso uniforme {fundo}, sem sombra no fundo; nenhuma cor do desenho parecida com {fundo}.")
    anim = animacao(item)
    if item.get("tipo") == "folha":
        colunas, linhas = grade(item)
        n = colunas * linhas
        partes.append(f"Folha {colunas}x{linhas} com exatamente {n} quadros igualmente espaçados, "
                      "sem linhas entre quadros, o MESMO desenho, do MESMO tamanho, em todos.")
        for ciclo in (anim or {}).get("ciclos", []):
            quadros = list(ciclo.get("quadros") or [])
            if not quadros:
                continue
            laco = ", em laço: o último quadro emenda no primeiro" if ciclo.get("loop") else ", sem laço"
            texto = f"{_onde(quadros, colunas)}: {ciclo.get('nome', '')} ({len(quadros)} quadros{laco})"
            if ciclo.get("descricao"):
                texto += f", {ciclo['descricao']}"
            partes.append(texto + ".")
        if anim and anim.get("ancora") == "pes":
            partes.append("Os pés tocam a MESMA linha de chão em todos os quadros, no centro da célula; "
                          "nenhum membro some de um quadro para o outro.")
    elif not opaco(item):
        partes.append("Peça parada: um objeto único, centrado, sem tocar a borda.")
    if config.mestra().is_file():
        partes.append("O estilo de referência é a imagem-mestra aprovada do Neural Fights.")
    if defeitos:
        partes.append(f"Corrija estes defeitos da tentativa anterior: {defeitos}.")
    return " ".join(partes)
