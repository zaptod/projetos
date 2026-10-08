# -*- coding: utf-8 -*-
"""A arte PRONTA da Vila: a da esteira de sprites, item a item.

PEDIDO DO ADRIAN (02/10/2026, 02:1x): "POR QUE A VILA AINDA ESTA DO MESMO
JEITO?" A esteira (`esteira_sprites --perfil vila`) ja aprovava arte no
estilo do Neural (decisao `painel-e-vila/vila-estilo-novo`), mas nada na
Vila lia o que ela entregava.

O CONTRATO, item a item, pelo `nome_arquivo` do inventario
(`docs/vila/inventario_vila.json`):

  - a esteira aprovada copia a folha para `painel/flutuante/arte_vila/
    <nome_arquivo>` com um `.json` ao lado (grade, ciclos, fps, laco);
  - quem desenha (`arte.py`) pergunta aqui primeiro; se a peca existe, usa
    a arte; se nao, cai no desenho de codigo de sempre, sem mudar um byte;
  - folha animada toca o ciclo do `.json` (cada linha uma direcao) no fps
    dele; o habitante escolhe a linha pela direcao em que anda;
  - a escala e a do mundo, como esta no inventario ("no mundo 72x64").

Nada aqui desenha por codigo nem pede imagem: so le o que foi aprovado.
As leituras ficam em memoria; `conferir()` (barato: so `stat`) diz se a
pasta mudou, e quem guarda imagem pronta joga a sua fora quando muda. E
assim que uma peca aprovada aparece sem reiniciar ninguem.

Teste: `usar(pasta, inventario)` aponta para outro lugar (e `usar(None)`
volta ao padrao). A variavel `NF_ARTE_VILA` faz o mesmo para um processo.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw
from neural_fights.tools import atelie_animacoes, catalogo_vila

RAIZ = Path(__file__).resolve().parents[2]
PASTA_PADRAO = Path(__file__).with_name("arte_vila")
INVENTARIO_PADRAO = RAIZ / "docs" / "vila" / "inventario_vila.json"
ANIMACOES_ATELIE = RAIZ / "palco" / "biblioteca" / "animacoes"

# Textura sem "no mundo WxH" no inventario: o lado do ladrilho em pixels do
# mundo. Medido na arte de 02/10: com 128 os tufos da grama ficam com ~6 px
# e as florzinhas com ~4 px, o tamanho das flores da floreira da casa; a
# terra em 96 deixa a pedra maior com ~5 px numa rua de 14.
LADO_DO_LADRILHO = {"cenario/chao_grama.png": 128,
                    "cenario/caminho_terra.png": 96}
LADO_PADRAO = 128

# A vida (`vida.Vida.pose`) fala em poses; a esteira, em animacoes. Pose sem
# folha propria cai na de ficar parado e depois na de andar: um habitante
# com arte nunca volta a ter pernas no meio de uma animacao.
POSE_PARA_ANIMACAO = {
    "parado": "parado", "passo1": "andar", "passo2": "andar",
    "trabalhar": "trabalhar", "acenar": "conversar", "triste": "triste",
    "feliz": "comemorar", "sentado": "sentado",
}
RESERVA_DE_ANIMACAO = ("parado", "andar")
DIRECAO_PARA_CICLO = {"dir": "direita", "esq": "esquerda"}

_trava = threading.RLock()
_pasta: Path | None = None
_inventario: Path | None = None
_itens: dict | None = None            # nome_arquivo -> item do inventario
_indice: dict | None = None           # nome_arquivo -> Path (so o que existe)
_assinatura: str | None = None
_cache: dict = {}


# ------------------------------------------------------------- onde
def usar(pasta: str | Path | None = None,
         inventario: str | Path | None = None) -> None:
    """Aponta para outra pasta/inventario (testes). None = o padrao."""
    global _pasta, _inventario
    with _trava:
        _pasta = Path(pasta) if pasta is not None else None
        _inventario = Path(inventario) if inventario is not None else None
        _limpar()


def pasta() -> Path:
    if _pasta is not None:
        return _pasta
    return Path(os.environ.get("NF_ARTE_VILA") or PASTA_PADRAO)


def caminho_do_inventario() -> Path:
    return _inventario or INVENTARIO_PADRAO


def _limpar() -> None:
    global _itens, _indice, _assinatura
    _itens = None
    _indice = None
    _assinatura = None
    _cache.clear()


def itens() -> dict:
    """{nome_arquivo: item}. Inventario ilegivel = nenhum item (nada de arte)."""
    global _itens
    with _trava:
        if _itens is None:
            try:
                dados = json.loads(caminho_do_inventario().read_text(
                    encoding="utf-8"))
                lista = dados.get("itens", []) if isinstance(dados, dict) else []
            except (OSError, ValueError):
                lista = []
            _itens = {str(i["nome_arquivo"]): i for i in lista
                      if isinstance(i, dict) and i.get("nome_arquivo")}
        return _itens


def _arquivos() -> list[Path]:
    raiz = pasta()
    if not raiz.is_dir():
        return []
    return sorted(p for p in raiz.rglob("*")
                  if p.is_file() and p.suffix.lower() in (".png", ".json"))


def _arquivos_atelie() -> list[Path]:
    raiz = atelie_animacoes.ANIMACOES
    if not raiz.is_dir():
        return []
    return sorted(p for p in raiz.glob("vila.*/*/*/*")
                  if p.is_file() and p.name in ("folha.png", "animacao.json"))


def _calcular_assinatura() -> str:
    raiz = pasta()
    h = hashlib.sha1(str(raiz).encode("utf-8"))
    for p in _arquivos():
        try:
            st = p.stat()
        except OSError:
            continue
        h.update(f"{p.relative_to(raiz).as_posix()}|{st.st_size}|"
                 f"{st.st_mtime_ns};".encode("utf-8"))
    for p in _arquivos_atelie():
        try:
            st = p.stat()
        except OSError:
            continue
        h.update(f"atelie/{p.relative_to(atelie_animacoes.ANIMACOES).as_posix()}|{st.st_size}|{st.st_mtime_ns};".encode("utf-8"))
    return h.hexdigest()[:12]


def assinatura() -> str:
    """Muda quando uma peca entra, sai ou e trocada (vai na versao do app)."""
    global _assinatura
    with _trava:
        if _assinatura is None:
            _assinatura = _calcular_assinatura()
        return _assinatura


def conferir() -> str:
    """Rele a assinatura da pasta (so `stat`) e, se mudou, esquece tudo o
    que leu. Devolve a assinatura de agora: cada consumidor guarda a que
    viu e joga fora a SUA imagem pronta quando ela muda (dois consumidores
    no mesmo processo nao roubam a novidade um do outro)."""
    global _assinatura
    with _trava:
        agora = _calcular_assinatura()
        if agora != _assinatura:
            _limpar()
            _assinatura = agora
        return agora


def indice() -> dict:
    """{nome_arquivo: Path} das pecas aprovadas que estao no inventario."""
    global _indice
    with _trava:
        if _indice is None:
            raiz = pasta()
            conhecidos = itens()
            _indice = {}
            for p in _arquivos():
                if p.suffix.lower() != ".png":
                    continue
                nome = p.relative_to(raiz).as_posix()
                if nome in conhecidos:
                    _indice[nome] = p
        return _indice


def tem(nome_arquivo: str) -> bool:
    return nome_arquivo in indice() or peca_do_atelie(nome_arquivo) is not None


# ------------------------------------------------------------- leitura
def peca_do_atelie(nome_arquivo: str) -> Image.Image | None:
    """O 1o quadro da arte do Atelie para este item do inventario, ou None.

    08/10/2026: a Vila so lia o Atelie nos habitantes; a arvore que o Adrian
    salvou nunca foi procurada. Toda leitura de peca passa por aqui primeiro.
    Animacao do Atelie: a de gatilho/nome "parado" se houver, senao a 1a."""
    item = itens().get(nome_arquivo) or {}
    chave = catalogo_vila.chave_do_item(item) if item else None
    if not chave:
        return None
    pasta_estado = atelie_animacoes.ANIMACOES / chave[0] / chave[1]
    try:
        animacoes = sorted(d.name for d in pasta_estado.iterdir() if (d / "folha.png").is_file())
    except OSError:
        return None
    if not animacoes:
        return None
    nome_anim = "parado" if "parado" in animacoes else animacoes[0]
    png = pasta_estado / nome_anim / "folha.png"
    try:
        marca = png.stat().st_mtime_ns
    except OSError:
        return None
    guardada = _PECAS_ATELIE.get(nome_arquivo)
    if guardada and guardada[0] == marca:
        return guardada[1]
    dados = atelie_animacoes.ler(chave[0], chave[1], nome_anim) or {}
    q = (dados.get("quadros") or [None])[0]
    try:
        with Image.open(png) as imagem:
            img = imagem.convert("RGBA")
    except (OSError, ValueError):
        return None
    if q:
        img = img.crop((q["x"], q["y"], q["x"] + q["w"], q["y"] + q["h"]))
    _PECAS_ATELIE[nome_arquivo] = (marca, img)
    return img


_PECAS_ATELIE: dict = {}


def peca(nome_arquivo: str) -> Image.Image | None:
    """A imagem aprovada em RGBA (tamanho original), ou None. A arte do
    Atelie vence a da esteira."""
    do_atelie = peca_do_atelie(nome_arquivo)
    if do_atelie is not None:
        return do_atelie
    caminho = indice().get(nome_arquivo)
    if caminho is None:
        return None
    chave = ("peca", nome_arquivo)
    with _trava:
        if chave not in _cache:
            try:
                with Image.open(caminho) as img:
                    _cache[chave] = img.convert("RGBA")
            except OSError:
                _cache[chave] = None
        return _cache[chave]


def meta(nome_arquivo: str) -> dict:
    """O `.json` ao lado da peca (o que a esteira gravou ao aprovar)."""
    caminho = indice().get(nome_arquivo)
    if caminho is None:
        return {}
    try:
        dados = json.loads(caminho.with_suffix(".json").read_text(
            encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def tamanho_no_mundo(nome_arquivo: str) -> tuple[int, int] | None:
    """O "no mundo WxH" do inventario, em pixels do mundo."""
    item = itens().get(nome_arquivo) or {}
    m = re.search(r"no mundo\s+(\d+)\s*x\s*(\d+)", str(item.get("tamanho", "")))
    return (int(m.group(1)), int(m.group(2))) if m else None


def ajustada(nome_arquivo: str, largura: int, altura: int,
             escala: int = 1) -> Image.Image | None:
    """A peca recortada no desenho e encaixada em `largura`x`altura` do
    MUNDO (vezes `escala`), sem deformar: centrada e com a base no chao."""
    e = max(1, int(escala))
    chave = ("ajustada", nome_arquivo, largura, altura, e)
    with _trava:
        if chave in _cache:
            return _cache[chave]
    img = peca(nome_arquivo)
    if img is None:
        return None
    caixa = img.getchannel("A").getbbox() or (0, 0, img.width, img.height)
    desenho = img.crop(caixa)
    w, h = largura * e, altura * e
    fator = min(w / desenho.width, h / desenho.height)
    nw = max(1, round(desenho.width * fator))
    nh = max(1, round(desenho.height * fator))
    reduzida = desenho.resize((nw, nh), Image.LANCZOS)
    saida = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    saida.alpha_composite(reduzida, ((w - nw) // 2, h - nh))
    with _trava:
        _cache[chave] = saida
    return saida


def ladrilho(nome_arquivo: str, lado_px: int) -> Image.Image | None:
    """A textura que emenda nos 4 lados, reduzida para `lado_px` (opaca)."""
    chave = ("ladrilho", nome_arquivo, int(lado_px))
    with _trava:
        if chave in _cache:
            return _cache[chave]
    img = peca(nome_arquivo)
    if img is None:
        return None
    saida = img.resize((int(lado_px), int(lado_px)), Image.LANCZOS)
    with _trava:
        _cache[chave] = saida
    return saida


def lado_do_ladrilho(nome_arquivo: str) -> int:
    """Lado do ladrilho em pixels do mundo (inventario, senao a tabela)."""
    no_mundo = tamanho_no_mundo(nome_arquivo)
    if no_mundo:
        return no_mundo[0]
    return LADO_DO_LADRILHO.get(nome_arquivo, LADO_PADRAO)


def ladrilhar(nome_arquivo: str, largura_px: int, altura_px: int,
              px_por_mundo: float,
              origem: tuple[float, float] = (0, 0)) -> Image.Image | None:
    """Uma imagem `largura_px`x`altura_px` coberta pela textura.

    `origem` e onde o canto de cima da imagem cai no MUNDO: um pedaco
    desenhado a parte (o campo que completa a Vila do celular, a grama de
    baixo) continua o ladrilho do chao sem emenda.
    """
    lado = max(1, round(lado_do_ladrilho(nome_arquivo) * px_por_mundo))
    tile = ladrilho(nome_arquivo, lado)
    if tile is None:
        return None
    dx = -(round(origem[0] * px_por_mundo) % lado)
    dy = -(round(origem[1] * px_por_mundo) % lado)
    saida = Image.new("RGBA", (largura_px, altura_px))
    for y in range(dy, altura_px, lado):
        for x in range(dx, largura_px, lado):
            saida.paste(tile, (x, y))
    return saida


# ------------------------------------------------------------- folhas
@dataclass
class Folha:
    """Uma folha de animacao: grade, ciclos (cada um uma linha) e o pe."""
    nome: str
    imagem: Image.Image
    colunas: int
    linhas: int
    ciclos: dict = field(default_factory=dict)  # nome -> {quadros,fps,loop}
    ordem: list = field(default_factory=list)
    pe: float = 1.0                             # fundo do desenho / altura

    @property
    def celula(self) -> tuple[float, float]:
        return self.imagem.width / self.colunas, self.imagem.height / self.linhas

    def ciclo(self, direcao: str) -> str:
        """O ciclo (a linha) da direcao; sem ele, o primeiro da folha."""
        desejado = DIRECAO_PARA_CICLO.get(direcao, direcao)
        if desejado in self.ciclos:
            return desejado
        return self.ordem[0] if self.ordem else ""

    def indice(self, ciclo: str, t: float) -> int:
        """Qual quadro do ciclo toca no instante `t` (segundos)."""
        info = self.ciclos.get(ciclo) or {}
        n = len(info.get("quadros") or []) or 1
        passo = int(max(0.0, t) * float(info.get("fps") or 1))
        return passo % n if info.get("loop", True) else min(passo, n - 1)

    def quadro(self, ciclo: str, i: int) -> int:
        """O numero do quadro NA FOLHA (0 = canto de cima a esquerda)."""
        quadros = (self.ciclos.get(ciclo) or {}).get("quadros") or [0]
        return int(quadros[int(i) % len(quadros)])

    def recorte(self, numero: int) -> Image.Image:
        cw, ch = self.celula
        col, lin = numero % self.colunas, numero // self.colunas
        caixa = (round(col * cw), round(lin * ch),
                 round((col + 1) * cw), round((lin + 1) * ch))
        return self.imagem.crop(caixa)

    def sprite(self, ciclo: str, i: int, largura: int, altura: int,
               escala: int = 1, sombra: bool = True) -> Image.Image:
        """O quadro `i` do `ciclo` no tamanho do mundo: a ALTURA da celula
        vira `altura`, o pe vai para a ultima linha (ancora `s` da cena)."""
        e = max(1, int(escala))
        chave = ("sprite", self.nome, ciclo, int(i), largura, altura, e, sombra)
        with _trava:
            if chave in _cache:
                return _cache[chave]
        cw, ch = self.celula
        fator = altura * e / ch
        cel = self.recorte(self.quadro(ciclo, i))
        nw = max(1, round(cel.width * fator))
        nh = max(1, round(cel.height * fator))
        w = largura * e
        h = altura * e
        saida = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if sombra:
            camada = Image.new("RGBA", (w * 4, h * 4), (0, 0, 0, 0))
            d = ImageDraw.Draw(camada)
            cx = w * 2
            d.ellipse([cx - 8 * e * 4, (altura - 3.5) * e * 4,
                       cx + 8 * e * 4, (altura - .2) * e * 4],
                      fill=(50, 80, 40, 70))
            saida.alpha_composite(camada.resize((w, h), Image.LANCZOS))
        y = round((altura - 1) * e - self.pe * ch * fator)
        # a celula pode ser mais larga que o sprite (margem vazia dos lados):
        # o sprite fica com a largura do contrato (o atlas do app empilha
        # sprites lado a lado e um vizinho nao pode receber a sobra)
        reduzida = cel.resize((nw, nh), Image.LANCZOS)
        if y < 0:                     # desenho encostado no fim da celula
            reduzida, y = reduzida.crop((0, -y, nw, nh)), 0
        larga = Image.new("RGBA", (max(w, nw), h), (0, 0, 0, 0))
        larga.alpha_composite(reduzida, ((larga.width - nw) // 2, y))
        corte = (larga.width - w) // 2
        saida.alpha_composite(larga.crop((corte, 0, corte + w, h)))
        with _trava:
            _cache[chave] = saida
        return saida


def _animacao(nome_arquivo: str) -> dict:
    """A animacao: a do `.json` da esteira; sem ela, a do inventario."""
    dados = meta(nome_arquivo).get("animacao")
    if isinstance(dados, dict) and dados.get("ciclos"):
        return dados
    item = itens().get(nome_arquivo) or {}
    return item.get("animacao") or {}


def folha(nome_arquivo: str) -> Folha | None:
    chave = ("folha", nome_arquivo)
    with _trava:
        if chave in _cache:
            return _cache[chave]
    img = peca(nome_arquivo)
    if img is None:
        return None
    anim = _animacao(nome_arquivo)
    grade = anim.get("grade") or meta(nome_arquivo).get("grade") or [1, 1]
    colunas, linhas = max(1, int(grade[0])), max(1, int(grade[1]))
    ciclos, ordem = {}, []
    for c in anim.get("ciclos") or []:
        if not isinstance(c, dict) or not c.get("nome"):
            continue
        ciclos[c["nome"]] = {"quadros": [int(q) for q in c.get("quadros") or [0]],
                             "fps": float(c.get("fps") or 1),
                             "loop": bool(c.get("loop", True))}
        ordem.append(c["nome"])
    if not ciclos:
        ciclos = {"tudo": {"quadros": list(range(colunas * linhas)),
                           "fps": 4.0, "loop": True}}
        ordem = ["tudo"]
    f = Folha(nome_arquivo, img, colunas, linhas, ciclos, ordem)
    # o pe: a linha mais baixa com desenho em QUALQUER celula, a mesma para
    # todas (assim o quadro nao sobe e desce; quem pula e o codigo)
    _cw, ch = f.celula
    fundo = 0.0
    for n in range(colunas * linhas):
        caixa = f.recorte(n).getchannel("A").getbbox()
        if caixa:
            fundo = max(fundo, caixa[3])
    f.pe = (fundo / ch) if fundo else 1.0
    with _trava:
        _cache[chave] = f
    return f


def arquivo_do_habitante(nome: str, animacao: str) -> str:
    return f"habitantes/{nome}/{animacao}.png"


def animacao_do_habitante(nome: str, pose: str) -> str | None:
    """A animacao com arte para a pose (ou a reserva), ou None."""
    pedida = POSE_PARA_ANIMACAO.get(pose, "parado")
    for animacao in (pedida,) + RESERVA_DE_ANIMACAO:
        if tem(arquivo_do_habitante(nome, animacao)):
            return animacao
    return None


# Direcao que o Adrian nao desenhou usa a que existe: a direita espelhada vira a
# esquerda (e vice-versa); frente e costas usam a que houver. 08/10/2026: ele
# desenhou so "andar > direita" do Bot e da Arena e, virados para os outros
# lados, eles voltavam ao desenho antigo ("a animacao nao entrou na Vila").
OUTRAS_DIRECOES = {
    "esquerda": (("direita", True), ("frente", False), ("costas", False)),
    "direita": (("esquerda", True), ("frente", False), ("costas", False)),
    "frente": (("direita", False), ("esquerda", False), ("costas", False)),
    "costas": (("frente", False), ("direita", False), ("esquerda", False)),
}
_FOLHAS_ATELIE: dict = {}


def _folha_do_atelie(peca: str, estado: str, direcao: str, espelhar: bool, ciclo: str) -> Folha | None:
    png = atelie_animacoes.caminho(peca, estado, direcao) / "folha.png"
    meta = atelie_animacoes.caminho(peca, estado, direcao) / "animacao.json"
    try:
        marca = (png.stat().st_mtime_ns, meta.stat().st_mtime_ns)
    except OSError:
        return None
    chave = (peca, estado, direcao, espelhar, ciclo)
    guardada = _FOLHAS_ATELIE.get(chave)
    if guardada and guardada[0] == marca:
        return guardada[1]
    dados = atelie_animacoes.ler(peca, estado, direcao)
    quadros = (dados or {}).get("quadros") or []
    if not quadros:
        return None
    try:
        with Image.open(png) as imagem:
            img = imagem.convert("RGBA")
    except (OSError, ValueError):
        return None
    largura, altura = max(q["w"] for q in quadros), max(q["h"] for q in quadros)
    folha_atelie = Image.new("RGBA", (largura * len(quadros), altura))
    fundo_do_desenho = 0
    for i, q in enumerate(quadros):
        recorte = img.crop((q["x"], q["y"], q["x"] + q["w"], q["y"] + q["h"]))
        if espelhar:
            recorte = recorte.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        caixa = recorte.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
        if caixa:
            fundo_do_desenho = max(fundo_do_desenho, caixa[3])
        folha_atelie.alpha_composite(recorte, (i * largura, 0))
    # o pe e onde o desenho acaba (a ancora do Atelie e do Godot e outra coisa:
    # com ela no meio o Bot saia cortado ao meio na Vila, 08/10)
    pe = (fundo_do_desenho / altura) if fundo_do_desenho else 1.0
    ciclos = {ciclo: {"quadros": list(range(len(quadros))), "fps": dados.get("fps", 1),
                      "loop": dados.get("loop", True)}}
    f = Folha(f"atelie:{peca}/{estado}/{direcao}" + (":espelho" if espelhar else ""), folha_atelie,
              len(quadros), 1, ciclos, [ciclo], pe)
    _FOLHAS_ATELIE[chave] = (marca, f)
    return f


def habitante(nome: str, pose: str, direcao: str) -> tuple[Folha, str] | None:
    """(folha, ciclo) do habitante nessa pose e direcao, se houver arte."""
    # a vida fala "dir"/"esq"; o Atelie grava "direita"/"esquerda" (08/10: sem
    # esta traducao a folha do Atelie nunca era achada na Vila de verdade)
    direcao_atelie = DIRECAO_PARA_CICLO.get(direcao, direcao)
    for animacao in (POSE_PARA_ANIMACAO.get(pose, "parado"),) + RESERVA_DE_ANIMACAO:
        arquivo = arquivo_do_habitante(nome, animacao)
        item = itens().get(arquivo) or {}
        chave = catalogo_vila.chave_do_item(item)
        if not chave:
            continue
        for fonte, espelhar in ((direcao_atelie, False),) + OUTRAS_DIRECOES.get(direcao_atelie, ()):
            f = _folha_do_atelie(chave[0], chave[1], fonte, espelhar, direcao_atelie)
            if f is not None:
                return f, direcao_atelie
    animacao = animacao_do_habitante(nome, pose)
    if animacao is None:
        return None
    arquivo = arquivo_do_habitante(nome, animacao)
    f = folha(arquivo)
    if f is None:
        return None
    return f, f.ciclo(direcao)


# ------------------------------------------- o Atelie para o celular
# 08/10/2026: o celular recebia so o quadro 0 da arte do Atelie (o atlas) e a
# lista de folhas tocaveis (`para_o_app`) so conhecia a esteira. Agora cada
# habitante com arte do Atelie vira UMA folha com uma linha por direcao
# (frente/esquerda/direita/costas, com o espelho/reserva de `habitante`), salva
# numa pasta de saida e servida pela mesma rota so de leitura.
DIRECOES_DA_FOLHA = ("frente", "esquerda", "direita", "costas")
ALTURA_APP_ATELIE = 128
PASTA_APP_ATELIE = Path(__file__).resolve().parents[2] / "palco" / "_saida" / "arte_vila_atelie"
_NOME_SEGURO = re.compile(r"^[a-z0-9_]+$")


def animacao_atelie(nome: str, pose: str) -> str | None:
    """A animacao (da pose ou a reserva) que tem arte do Atelie, ou None."""
    for animacao in (POSE_PARA_ANIMACAO.get(pose, "parado"),) + RESERVA_DE_ANIMACAO:
        chave = catalogo_vila.chave_do_item(itens().get(arquivo_do_habitante(nome, animacao)) or {})
        if chave and any((atelie_animacoes.caminho(chave[0], chave[1], d) / "folha.png").is_file()
                         for d in DIRECOES_DA_FOLHA):
            return animacao
    return None


def _folha_app_atelie(nome: str, animacao: str) -> tuple[Path, dict] | None:
    chave = catalogo_vila.chave_do_item(itens().get(arquivo_do_habitante(nome, animacao)) or {})
    if not chave:
        return None
    linhas = []
    for direcao in DIRECOES_DA_FOLHA:
        f = None
        for fonte, espelhar in ((direcao, False),) + OUTRAS_DIRECOES.get(direcao, ()):
            f = _folha_do_atelie(chave[0], chave[1], fonte, espelhar, direcao)
            if f is not None:
                break
        if f is None:
            return None
        linhas.append((direcao, f))
    cw = max(int(f.celula[0]) for _, f in linhas)
    ch = max(int(f.celula[1]) for _, f in linhas)
    # o celular desenha o habitante com ~32 px de mundo x a escala dele: 128 px
    # de celula basta (a folha cheia do Bot tinha 5008 px de largura)
    fator = min(1.0, ALTURA_APP_ATELIE / ch)
    cw, ch = max(1, round(cw * fator)), max(1, round(ch * fator))
    colunas = max(f.colunas for _, f in linhas)
    marca = "|".join(f"{f.nome}:{f.colunas}:{f.imagem.width}" for _, f in linhas) + f"|{ALTURA_APP_ATELIE}"
    destino = PASTA_APP_ATELIE / f"{nome}__{animacao}.png"
    info_arquivo = destino.with_suffix(".json")
    ciclos = {}
    for r, (direcao, f) in enumerate(linhas):
        dado = f.ciclos.get(direcao) or {}
        ciclos[direcao] = {"quadros": [r * colunas + i for i in range(f.colunas)],
                           "fps": dado.get("fps", 8), "loop": dado.get("loop", True)}
    info = {"marca": marca, "grade": [colunas, len(linhas)], "tamanho": [cw * colunas, ch * len(linhas)],
            "ciclos": ciclos, "pe": round(linhas[0][1].pe, 4)}
    try:
        antigo = json.loads(info_arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        antigo = {}
    if antigo.get("marca") != marca or not destino.is_file():
        folha_app = Image.new("RGBA", (cw * colunas, ch * len(linhas)), (0, 0, 0, 0))
        for r, (_, f) in enumerate(linhas):
            for i in range(f.colunas):
                quadro = f.recorte(i)
                if fator < 1.0:
                    quadro = quadro.resize((max(1, round(quadro.width * fator)),
                                            max(1, round(quadro.height * fator))), Image.LANCZOS)
                folha_app.alpha_composite(quadro, (i * cw + (cw - quadro.width) // 2, r * ch + (ch - quadro.height)))
        PASTA_APP_ATELIE.mkdir(parents=True, exist_ok=True)
        folha_app.save(destino)
        info_arquivo.write_text(json.dumps(info), encoding="utf-8")
    return destino, info


# ------------------------------------------------------------- o app
ROTA = "/arte-vila/"


def para_o_app() -> dict:
    """O que o celular precisa para tocar as folhas dos habitantes: a URL
    (rota so de leitura), a grade, os ciclos e onde fica o pe."""
    saida: dict = {"habitantes": {}, "versao": assinatura()}
    for nome_arquivo in sorted(indice()):
        partes = nome_arquivo.split("/")
        if len(partes) != 3 or partes[0] != "habitantes":
            continue
        f = folha(nome_arquivo)
        if f is None:
            continue
        mundo = tamanho_no_mundo(nome_arquivo) or (26, 32)
        saida["habitantes"].setdefault(partes[1], {})[partes[2][:-4]] = {
            "url": f"{ROTA}{nome_arquivo}?v={assinatura()}",
            "grade": [f.colunas, f.linhas],
            "tamanho": [f.imagem.width, f.imagem.height],
            "ciclos": f.ciclos, "pe": round(f.pe, 4),
            "mundo": list(mundo)}
    for nome_arquivo, item in sorted(itens().items()):
        partes = nome_arquivo.split("/")
        if len(partes) != 3 or partes[0] != "habitantes":
            continue
        nome, animacao = partes[1], partes[2].rsplit(".", 1)[0]
        feita = _folha_app_atelie(nome, animacao)
        if feita is None:
            continue
        _, info = feita
        mundo = tamanho_no_mundo(nome_arquivo) or (26, 32)
        saida["habitantes"].setdefault(nome, {})[animacao] = {
            "url": f"{ROTA}atelie/{nome}/{animacao}.png?v={assinatura()}",
            "grade": info["grade"], "tamanho": info["tamanho"], "ciclos": info["ciclos"],
            "pe": info["pe"], "mundo": list(mundo)}
    return saida


def arquivo_publico(rota: str) -> Path | None:
    """O arquivo de `/arte-vila/<nome_arquivo>`, so se for uma peca aprovada
    do inventario. A URL nunca e juntada com a pasta: e uma consulta exata
    no indice (nada de `..`, de barra invertida ou de arquivo fora dele)."""
    if not rota.startswith(ROTA):
        return None
    resto = rota[len(ROTA):]
    if resto.startswith("atelie/"):
        partes = resto[len("atelie/"):].split("/")
        if len(partes) != 2 or not partes[1].endswith(".png"):
            return None
        nome, animacao = partes[0], partes[1][:-4]
        if not (_NOME_SEGURO.match(nome) and _NOME_SEGURO.match(animacao)):
            return None
        feita = _folha_app_atelie(nome, animacao)
        return feita[0] if feita else None
    return indice().get(resto)


__all__ = ["Folha", "POSE_PARA_ANIMACAO", "ROTA", "ajustada",
           "animacao_do_habitante", "arquivo_publico", "assinatura",
           "conferir", "folha", "habitante", "indice", "itens", "ladrilhar",
           "ladrilho", "meta", "para_o_app", "pasta", "peca", "tem",
           "tamanho_no_mundo", "usar"]
