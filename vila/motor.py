# -*- coding: utf-8 -*-
"""O motor da Vila: folhas de sprites, papeis e o mundo composto.

A Vila do painel deixa de ser desenho vetorial e passa a ser um mundinho de
tiles no estilo Stardew: o Adrian gera as folhas de sprites (PicassoIA ou o
que for), a OFICINA (`vila/editor.py`) fatia e atribui, e o painel so compoe.

Tres conceitos, e mais nenhum:

  FOLHA   um PNG com uma grade uniforme de celulas (tile_w x tile_h, com
          margem/espaco opcionais). `chave` remove o fundo: "auto" usa a cor
          do canto superior esquerdo — essencial para arte gerada por IA,
          que nunca vem com transparencia de verdade.
  PAPEL   um nome com significado para o painel ("predio.picasso",
          "chao.grama", "bot.baixo") apontando para frames de uma folha.
          E o contrato: o painel pede papeis, nunca indices. `variar`
          escolhe o frame por posicao (grama que nao parece azulejo);
          `fps` anima; larg/alt em tiles para o que ocupa mais de 1 celula.
  MAPA    grade de indices na `paleta` (papeis de chao) + decoracoes +
          onde fica cada predio e a casa dos bots.

Tudo vive em `vila/config.json` e `vila/sprites/`. O painel compoe o mundo
ESTATICO uma vez (uma imagem so — e o que faz o canvas aguentar um mapa
grande) e anima por cima apenas bots e efeitos.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent
SPRITES = RAIZ / "sprites"
CONFIG = RAIZ / "config.json"

def _fabricas() -> list:
    """A lista vem do DIARIO, que e quem de fato registra o trabalho.

    Ate 01/09/2026 esta lista era escrita aqui e de novo em
    `atividade.FABRICAS` -- duas copias mantidas a mao. Uma fabrica nova
    entrava no diario e simplesmente nao ganhava predio, sem erro nenhum.
    A Vila desenha o que o diario conhece; se nao conseguir importar
    (rodando a Oficina sozinha, sem o random_builds instalado), cai na
    lista conhecida em vez de abrir vazia.
    """
    try:
        from builds.atividade import FABRICAS as do_diario
        return list(do_diario)
    except Exception:
        return ["chatgpt", "gemini", "picasso", "digen",
                "estudio", "arena", "publicacao"]


FABRICAS = _fabricas()

# O vocabulario que o painel entende. A Oficina aceita papeis novos alem
# destes (decoracao livre), mas ESTES sao os que ganham vida:
#   predio.<fabrica>/casa  — posicionaveis no mapa, clicaveis, com estado
#   chao.*                 — pintaveis na paleta do chao
#   decor.*                — carimbaveis por cima do chao
#   bot.<direcao>          — a caminhada (bot.<fabrica>.<direcao> por bot)
#   fx.*                   — trabalho/erro em cima do predio
PAPEIS_SUGERIDOS = (
    [f"predio.{f}" for f in FABRICAS] + ["predio.casa"]
    + ["chao.grama", "chao.flor", "chao.caminho", "chao.agua",
       "chao.terra", "chao.pedra"]
    + ["decor.arvore", "decor.arbusto", "decor.pedra", "decor.cerca"]
    + ["bot.baixo", "bot.cima", "bot.esq", "bot.dir"]
    + ["fx.trabalho", "fx.erro"])

PADRAO = {
    "tile": 16,          # lado da celula no MUNDO (as folhas podem diferir)
    "escala": 2,         # zoom inteiro padrao do painel (pixel art: NEAREST)
    "fundo": "#17251a",
    "folhas": {},        # nome: {arquivo, tile_w, tile_h, margem, espaco, chave}
    "papeis": {},        # nome: {folha, frames, fps, larg, alt, variar}
    "mapa": None,        # {larg, alt, paleta, chao, decor, predios, casa}
}


# ----------------------------------------------------------------- config
def carregar(caminho: Path | None = None) -> dict:
    caminho = Path(caminho) if caminho else CONFIG
    dados = {}
    if caminho.is_file():
        with open(caminho, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    cfg = dict(PADRAO)
    cfg.update(dados)
    for chave in ("folhas", "papeis"):
        cfg[chave] = dict(cfg.get(chave) or {})
    return cfg


def salvar(cfg: dict, caminho: Path | None = None) -> Path:
    caminho = Path(caminho) if caminho else CONFIG
    caminho.parent.mkdir(parents=True, exist_ok=True)
    limpo = {k: v for k, v in cfg.items() if k in PADRAO}
    caminho.write_text(json.dumps(limpo, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    return caminho


def pronto(cfg: dict) -> bool:
    """Da para renderizar em modo sprite? (Senao o painel cai no vetorial.)"""
    if not cfg.get("mapa") or not cfg.get("folhas"):
        return False
    return any(p.startswith("chao.") for p in cfg.get("papeis") or {})


def mapa_novo(larg: int, alt: int, paleta: list | None = None) -> dict:
    return {"larg": int(larg), "alt": int(alt),
            "paleta": list(paleta or []),
            "chao": [[0] * int(larg) for _ in range(int(alt))],
            "decor": [], "predios": {}, "casa": None}


# ----------------------------------------------------------------- papeis
def frames_de(cfg: dict, papel: str, fabrica: str | None = None) -> dict | None:
    """Definicao do papel; para bots tenta o especifico da fabrica antes.

    `frames_de(cfg, "bot.baixo", fabrica="picasso")` procura
    `bot.picasso.baixo` e so entao `bot.baixo` — e o que permite dar um
    personagem proprio a cada fabrica sem mudar o painel.
    """
    papeis = cfg.get("papeis") or {}
    if fabrica and papel.startswith("bot."):
        especifico = papeis.get(f"bot.{fabrica}.{papel[4:]}")
        if especifico:
            return especifico
    return papeis.get(papel)


def tamanho(cfg: dict, papel: str) -> tuple:
    """(larg, alt) em tiles do MUNDO."""
    dados = (cfg.get("papeis") or {}).get(papel) or {}
    return int(dados.get("larg", 1)), int(dados.get("alt", 1))


def variar_frame(quantidade: int, x: int, y: int) -> int:
    """Frame deterministico por posicao: grama viva, nunca azulejo.

    Hash fixo (nao random): o mundo tem que sair IGUAL em toda recomposicao,
    senao o cenario "fervilha" a cada zoom/reload.
    """
    if quantidade <= 1:
        return 0
    return ((x * 73856093) ^ (y * 19349663)) % quantidade


# ------------------------------------------------------------------ atlas
def grade(cfg: dict, folha: str) -> tuple:
    dados = cfg["folhas"][folha]
    return (int(dados.get("tile_w", cfg["tile"])),
            int(dados.get("tile_h", cfg["tile"])),
            int(dados.get("margem", 0)), int(dados.get("espaco", 0)))


def celulas(cfg: dict, folha: str, tamanho_px: tuple) -> tuple:
    """(colunas, linhas) de celulas que cabem na folha."""
    tw, th, margem, espaco = grade(cfg, folha)
    cols = max(1, (tamanho_px[0] - 2 * margem + espaco) // (tw + espaco))
    rows = max(1, (tamanho_px[1] - 2 * margem + espaco) // (th + espaco))
    return int(cols), int(rows)


def _cor(texto: str) -> tuple:
    texto = texto.lstrip("#")
    return tuple(int(texto[i:i + 2], 16) for i in (0, 2, 4))


class Atlas:
    """Recorta e cacheia sprites das folhas (com chave de transparencia)."""

    TOLERANCIA = 36  # por canal; arte de IA nunca tem o fundo exato

    def __init__(self, cfg: dict, raiz: Path | None = None):
        self.cfg = cfg
        self.raiz = Path(raiz) if raiz else RAIZ
        self._folhas: dict = {}
        self._sprites: dict = {}

    def limpar(self):
        self._folhas.clear()
        self._sprites.clear()

    def folha(self, nome: str) -> Image.Image:
        if nome in self._folhas:
            return self._folhas[nome]
        dados = self.cfg["folhas"][nome]
        img = Image.open(self.raiz / dados["arquivo"]).convert("RGBA")
        chave = dados.get("chave")
        if chave:
            alvo = (img.getpixel((0, 0))[:3] if chave == "auto"
                    else _cor(chave))
            tol = self.TOLERANCIA
            px = [(r, g, b, 0)
                  if (abs(r - alvo[0]) <= tol and abs(g - alvo[1]) <= tol
                      and abs(b - alvo[2]) <= tol) else (r, g, b, a)
                  for r, g, b, a in img.getdata()]
            img.putdata(px)
        self._folhas[nome] = img
        return img

    def sprite(self, papel: str, frame: int = 0, escala: int = 1,
               fabrica: str | None = None) -> Image.Image:
        """Imagem RGBA do papel, ja na escala do mundo (NEAREST, pixel art)."""
        dados = frames_de(self.cfg, papel, fabrica)
        if not dados:
            raise KeyError(f"papel sem sprite atribuido: {papel}")
        chave_cache = (id(dados), frame, escala)
        if chave_cache in self._sprites:
            return self._sprites[chave_cache]

        nome_folha = dados["folha"]
        img = self.folha(nome_folha)
        tw, th, margem, espaco = grade(self.cfg, nome_folha)
        cols, _rows = celulas(self.cfg, nome_folha, img.size)
        indice = int(dados["frames"][frame % len(dados["frames"])])
        col, row = indice % cols, indice // cols
        larg, alt = int(dados.get("larg", 1)), int(dados.get("alt", 1))
        x0 = margem + col * (tw + espaco)
        y0 = margem + row * (th + espaco)
        recorte = img.crop((x0, y0,
                            x0 + tw * larg + espaco * (larg - 1),
                            y0 + th * alt + espaco * (alt - 1)))

        # A folha pode ter celula diferente do tile do mundo: normaliza para
        # o tamanho no MUNDO e so entao aplica o zoom.
        tile = int(self.cfg["tile"])
        alvo = (tile * larg * escala, tile * alt * escala)
        if recorte.size != alvo:
            recorte = recorte.resize(alvo, Image.NEAREST)
        self._sprites[chave_cache] = recorte
        return recorte


# ------------------------------------------------------------------ mundo
def compor_mundo(cfg: dict, atlas: Atlas, escala: int | None = None) -> Image.Image:
    """Uma imagem so com tudo que nao se mexe: chao, decoracao, predios.

    O painel anima por cima (bots, fx). Ordem de pintura: chao, e depois
    decoracao+predios ordenados pela BASE (y+alt) — quem esta mais para
    baixo cobre quem esta atras, o truque classico de perspectiva top-down.
    Papel sem sprite atribuido e pulado em silencio: a Oficina salva
    configuracoes pela metade o tempo todo, e isso nao pode derrubar nada.
    """
    escala = int(escala or cfg.get("escala", 2))
    mapa = cfg["mapa"]
    ts = int(cfg["tile"]) * escala
    mundo = Image.new("RGBA", (mapa["larg"] * ts, mapa["alt"] * ts),
                      _cor(cfg.get("fundo", "#17251a")) + (255,))

    paleta = mapa.get("paleta") or []
    for y, linha in enumerate(mapa.get("chao") or []):
        for x, i in enumerate(linha):
            if not (0 <= int(i) < len(paleta)):
                continue
            papel = paleta[int(i)]
            dados = frames_de(cfg, papel)
            if not dados:
                continue
            quadro = (variar_frame(len(dados["frames"]), x, y)
                      if dados.get("variar") else 0)
            try:
                spr = atlas.sprite(papel, quadro, escala)
            except (KeyError, FileNotFoundError):
                continue
            mundo.paste(spr, (x * ts, y * ts), spr)

    fixos = [dict(d) for d in (mapa.get("decor") or [])]
    for nome, pos in (mapa.get("predios") or {}).items():
        fixos.append({"x": pos["x"], "y": pos["y"], "papel": f"predio.{nome}"})
    if mapa.get("casa"):
        fixos.append({"x": mapa["casa"]["x"], "y": mapa["casa"]["y"],
                      "papel": "predio.casa"})
    fixos.sort(key=lambda d: d["y"] + tamanho(cfg, d["papel"])[1])
    for item in fixos:
        try:
            spr = atlas.sprite(item["papel"], 0, escala)
        except (KeyError, FileNotFoundError):
            continue
        mundo.paste(spr, (item["x"] * ts, item["y"] * ts), spr)
    return mundo
