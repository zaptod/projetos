"""Juiz consultivo: pergunta por defeitos e registra controles de qualidade."""
from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image, ImageDraw
from ias import correio

from . import config, ficha, prompt

TEXTO_ANIMACAO = ("Isto e uma folha de ANIMACAO em ciclo (cada linha da folha e um ciclo; o GIF "
                  "anexo toca os ciclos lado a lado). Liste o que esta errado NA ANIMACAO "
                  "(continuidade, pes deslizando, pulos de tamanho, membros que somem).")


def _xadrez(origem: str, destino: Path) -> Path:
    arte = Image.open(origem).convert("RGBA")
    fundo = Image.new("RGBA", arte.size, "#B0B0B0")
    desenho = ImageDraw.Draw(fundo)
    for y in range(0, arte.height, 12):
        for x in range(0, arte.width, 12):
            if (x // 12 + y // 12) % 2:
                desenho.rectangle((x, y, x + 11, y + 11), fill="#D8D8D8")
    fundo.alpha_composite(arte)
    fundo.save(destino, "PNG")
    return destino


def _estragado(origem: str, destino: Path) -> Path:
    """Controle visivel: corta metade da arte para testar o juiz."""
    arte = Image.open(origem).convert("RGBA")
    pixels = arte.load()
    for y in range(arte.height):
        for x in range(arte.width // 2, arte.width):
            pixels[x, y] = (0, 0, 0, 0)
    arte.save(destino, "PNG")
    return destino


def _controle(dados: dict) -> bool:
    return (sum(len(d.get("tentativas", [])) for d in _fichas()) + 1) % 10 == 0


def _fichas() -> list[dict]:
    saida = []
    raiz = config.pasta_do_perfil()
    if not raiz.exists():
        return saida
    for caminho in raiz.glob("*/ficha.json"):
        try:
            saida.append(json.loads(caminho.read_text(encoding="utf-8")))
        except ValueError:
            pass
    return saida


def perguntar(item_id: str) -> bool:
    dados = ficha.ler(item_id)
    if not dados or dados.get("estado") != "medido":
        return False
    tentativa = dados["tentativas"][-1]
    pasta = ficha.caminho(item_id).parent
    visual = _xadrez(tentativa["caminhos"]["limpo"], pasta / "para_juiz.png")
    anexos = [str(visual)]
    if config.mestra().is_file():
        anexos.append(str(config.mestra()))
    controle = _controle(dados)
    if controle:
        anexos[0] = str(_estragado(tentativa["caminhos"]["limpo"], pasta / "controle_estragado.png"))
    texto = ("Liste o que esta errado neste sprite; nunca responda se esta bom. "
             "Responda JSON estrito: {\"defeitos\":[{\"o_que\":str,\"gravidade\":\"leve|media|grave\"}],"
             "\"notas\":{\"silhueta\":0-3,\"estilo\":0-3,\"cor_do_elemento\":0-3,\"continuidade\":0-3,\"recorte\":0-3}}.")
    if prompt.animacao(dados["item"]) is not None:
        # animacao: a folha E o ciclo tocando (GIF), e a pergunta e da animacao
        gif = tentativa.get("caminhos", {}).get("previa_gif")
        if gif and Path(gif).is_file() and not controle:
            anexos.insert(1, gif)
        texto = TEXTO_ANIMACAO + " " + texto
    if controle:
        texto += " Este e um controle deliberadamente estragado; aponte o defeito grave."
    mensagem = correio.enviar("grok", texto, de="esteira_sprites", anexos=anexos)
    tentativa["juiz_id"] = mensagem["id"]
    tentativa["controle"] = controle
    dados["estado"] = "julgado"
    ficha.registrar(dados, "juiz_pedido", correio_id=mensagem["id"], controle=controle)
    ficha.gravar(dados)
    return True


def ler_json(texto: str) -> dict | None:
    decodificador = json.JSONDecoder()
    for inicio in (m.start() for m in re.finditer(r"\{", texto or "")):
        try:
            valor, _ = decodificador.raw_decode(texto[inicio:])
            if isinstance(valor, dict) and isinstance(valor.get("defeitos"), list):
                return valor
        except ValueError:
            continue
    return None


def colher(item_id: str) -> bool:
    dados = ficha.ler(item_id)
    if not dados or dados.get("estado") != "julgado":
        return False
    tentativa = dados["tentativas"][-1]
    mensagem = correio.uma("grok", tentativa["juiz_id"])
    if not mensagem or mensagem.get("situacao") not in ("respondida", "falhou"):
        return False
    veredito = ler_json(mensagem.get("resposta") or "") if mensagem["situacao"] == "respondida" else None
    if veredito is None:
        veredito = {"defeitos": [{"o_que": mensagem.get("erro") or "juiz sem JSON", "gravidade": "grave"}], "notas": {}}
    tentativa["veredito"] = veredito
    graves = [d.get("o_que", "defeito grave") for d in veredito["defeitos"] if d.get("gravidade") == "grave"]
    if tentativa.get("controle") and not graves:
        tentativa["juiz_fraco"] = True
        ficha.registrar(dados, "juiz_fraco", motivo="controle sem defeito grave")
    if graves:
        if len(dados["tentativas"]) <= 2:
            from .pedir import pedir
            ficha.gravar(dados)
            pedir(item_id, "; ".join(graves))
            return True
        dados["estado"] = "a_conferir"
    else:
        dados["estado"] = "a_conferir"
    ficha.registrar(dados, "juiz_respondeu", veredito=veredito)
    ficha.gravar(dados)
    return True
