"""Previa Tk da arte enviada ao Atelie.

Este modulo le o mesmo catalogo e os mesmos caminhos do Atelie.  Assim a
previsao do launcher nao inventa uma segunda hierarquia de arte.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageTk

from neural_fights.tools import atelie_animacoes as atelie
from neural_fights.tools.catalogo_animacoes import slug


COR_MARCADOR = "#8b8d96"


@dataclass
class QuadrosArte:
    peca: str
    fonte: str | None
    dados: dict
    quadros: list[Image.Image]
    marcador: str


def _catalogo() -> dict:
    try:
        return json.loads(atelie.CATALOGO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"pecas": []}


def _peca(ident: str, catalogo: dict) -> dict | None:
    return next((p for p in catalogo.get("pecas", []) if p.get("id") == ident), None)


def peca_lutador(personagem) -> str:
    classe = str(getattr(personagem, "classe", ""))
    return f"classe.{slug(classe)}" if classe else "lutador.corpo"


def peca_arma(arma) -> str:
    estilo = str(getattr(arma, "estilo", ""))
    tipo = str(getattr(arma, "tipo", ""))
    estilo_id = f"arma.estilo.{slug(estilo)}"
    # Um banco salvo antes da regeneracao pode conhecer o estilo antes do
    # catalogo. Nesse intervalo a arte por tipo continua sendo a melhor previa.
    if estilo and _peca(estilo_id, _catalogo()):
        return estilo_id
    return f"arma.tipo.{slug(tipo)}"


def _candidatas(ident: str, catalogo: dict) -> list[str]:
    peca = _peca(ident, catalogo)
    saida = [ident]
    if peca:
        saida.extend(peca.get("heranca", []))
    # Classes atuais herdam a generica no catalogo; o launcher tambem procura
    # o corpo comum antes dela, como o preview de um lutador pede.
    if ident.startswith("classe."):
        saida.extend(("lutador.corpo", "lutador.generico"))
    if ident.startswith("arma.estilo.") and peca is None:
        saida.append("arma.generica")
    return list(dict.fromkeys(saida))


def _animacao_preferida(peca: dict) -> tuple[dict, dict] | tuple[None, None]:
    """Prefere ocioso, mas toda peca valida continua previsualizavel."""
    primeira = (None, None)
    for estado in peca.get("estados", []):
        for animacao in estado.get("animacoes", []):
            if primeira == (None, None):
                primeira = estado, animacao
            if animacao.get("gatilho") == "ocioso":
                return estado, animacao
    return primeira


def resolver(ident: str, *, catalogo: dict | None = None) -> tuple[dict | None, dict | None, str | None]:
    """Resolve a primeira folha, do especifico para a heranca."""
    catalogo = catalogo or _catalogo()
    solicitada = _peca(ident, catalogo)
    estado, animacao = _animacao_preferida(solicitada) if solicitada else (None, None)
    for candidata in _candidatas(ident, catalogo):
        peca = _peca(candidata, catalogo)
        if not peca:
            continue
        estado_c, animacao_c = _animacao_preferida(peca)
        # Primeiro tenta o mesmo estado da peca pedida. Classes e corpo, porem,
        # possuem nomes historicos diferentes (base/ociosa e parado/parado),
        # entao a primeira animacao valida da herdada e a segunda tentativa.
        opcoes = [(estado, animacao), (estado_c, animacao_c)]
        for estado_usada, animacao_usada in opcoes:
            if not estado_usada or not animacao_usada:
                continue
            folha = atelie.caminho(candidata, estado_usada["id"], animacao_usada["id"]) / "folha.png"
            if folha.is_file():
                return estado_usada, animacao_usada, candidata
    return estado, animacao, None


def _tamanho(animacao: dict, corpo: float) -> float:
    try:
        base = float(str(animacao.get("tamanho_padrao", "1")).replace(",", ".").split()[0])
    except (TypeError, ValueError):
        base = 1.0
    return max(1.0, base * corpo)


def carregar_quadros(ident: str, *, corpo: float = 100, catalogo: dict | None = None) -> QuadrosArte:
    """Recorta e redimensiona uma folha pela regra do maior lado do quadro."""
    estado, animacao, fonte = resolver(ident, catalogo=catalogo)
    marcador = "arma" if ident.startswith("arma.") else "lutador"
    if not fonte or not estado or not animacao:
        return QuadrosArte(ident, None, {}, [], marcador)
    pasta = atelie.caminho(fonte, estado["id"], animacao["id"])
    try:
        dados = atelie.ler(fonte, estado["id"], animacao["id"])
        if not dados:
            raise ValueError("sem contrato")
        with Image.open(pasta / "folha.png") as folha:
            folha = folha.convert("RGBA")
            lado = _tamanho(animacao, corpo) * float(dados.get("escala", 1))
            quadros = []
            for quadro in dados["quadros"]:
                imagem = folha.crop((quadro["x"], quadro["y"], quadro["x"] + quadro["w"], quadro["y"] + quadro["h"]))
                escala = lado / max(imagem.size)
                quadros.append(imagem.resize((max(1, round(imagem.width * escala)), max(1, round(imagem.height * escala))), Image.Resampling.LANCZOS))
    except (OSError, ValueError, KeyError):
        return QuadrosArte(ident, None, {}, [], marcador)
    return QuadrosArte(ident, fonte, dados, quadros, marcador)


def _marcador(canvas, tipo: str, x: int, y: int, corpo: int) -> None:
    if tipo == "arma":
        canvas.create_line(x, y, x + corpo, y - corpo // 3, fill=COR_MARCADOR, width=max(3, corpo // 12), tags="arte")
    else:
        canvas.create_oval(x - corpo // 2, y - corpo // 2, x + corpo // 2, y + corpo // 2,
                           fill=COR_MARCADOR, outline="#565861", width=2, tags="arte")


def desenhar(canvas, arte: QuadrosArte, x: int, y: int, *, indice: int = 0,
             limpar: bool = True) -> None:
    """Desenha um quadro ou o marcador neutro; guarda PhotoImage no Canvas."""
    if limpar:
        canvas.delete("arte")
    if not arte.quadros:
        _marcador(canvas, arte.marcador, x, y, 70)
        return
    imagem = arte.quadros[indice % len(arte.quadros)]
    foto = ImageTk.PhotoImage(imagem)
    canvas._arte_atelie_foto = foto
    canvas.create_image(x, y, image=foto, anchor="center", tags="arte")


def animar(canvas, arte: QuadrosArte, x: int, y: int, *, ao_desenhar=None) -> None:
    """Inicia uma animacao leve; uma nova chamada invalida a anterior."""
    token = object(); canvas._arte_atelie_token = token
    fps = max(1.0, float(arte.dados.get("fps", 8))) if arte.dados else 8.0
    def passo(indice=0):
        if getattr(canvas, "_arte_atelie_token", None) is not token:
            return
        if ao_desenhar:
            ao_desenhar(indice)
        else:
            desenhar(canvas, arte, x, y, indice=indice)
        if len(arte.quadros) > 1:
            canvas.after(max(1, round(1000 / fps)), lambda: passo(indice + 1))
    passo()


def linhas_arte(ident: str) -> list[str]:
    """Linhas do quadro Arte, incluindo heranca e falta de arte."""
    catalogo = _catalogo(); peca = _peca(ident, catalogo)
    if not peca:
        return ["✗ peça ainda não existe no catálogo"]
    linhas = []
    for estado in peca.get("estados", []):
        for animacao in estado.get("animacoes", []):
            fonte = next((origem for origem in _candidatas(ident, catalogo)
                          if (atelie.caminho(origem, estado["id"], animacao["id"]) / "folha.png").is_file()), None)
            nome = f"{estado.get('rotulo', estado['id'])} › {animacao.get('rotulo', animacao['id'])} ({animacao.get('gatilho', '')})"
            linhas.append(f"✓ {nome}" if fonte == ident else (f"↳ {nome}: usa a de {fonte}" if fonte else f"✗ {nome}"))
    return linhas or ["✗ sem animações cadastradas"]
