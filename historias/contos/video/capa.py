# -*- coding: utf-8 -*-
"""A capa da historia — o unico frame que a pessoa ve antes de decidir.

DIAGNOSTICO, com a tela na mao (11/09/2026). Na prateleira de Shorts da casa
do YouTube, "A verdadeira face (Parte 6)" aparecia como um frame cru: dois
homens gritando, sem uma letra na tela. Do lado, na mesma fileira: um cartao
com titulo enorme em duas cores (63 mil views), uma arte desenhada com frase
por cima (1,4 milhao), outra com balao de fala (2,7 milhoes). O nosso tinha
zero.

O video JA desenha o titulo, mas por 2,2 s e com fade — e a miniatura que o
YouTube escolhe sozinho quase nunca cai nesses 2,2 s. Ou seja: o trabalho de
titulo existia e nao chegava em quem estava decidindo.

POR QUE VERTICAL, e nao 1280x720 como a capa dos builds. A capa de builds
serve a pagina do canal e a busca, que sao 16:9. Esta aqui serve a
prateleira de Shorts e o TikTok, que recortam VERTICAL — uma capa 16:9 com o
titulo no meio chega recortada pelas beiradas, e o titulo e justamente a
parte que precisa sobreviver.

O QUE ELA NAO E: um cartao estatico prefixado no video. Isso foi descartado
no canal de builds pelo mesmo motivo que vale aqui — o feed rola, e segurar
meio segundo de placa antes da historia comecar custa exatamente os frames
que decidem. A capa e ARQUIVO separado, entregue no upload.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from builds.visualization.draw_common import gradient, hex_rgb, load_font

LARGURA, ALTURA = 1080, 1920
# O YouTube recusa miniatura acima de 2 MB. Cair em 2,1 MB depois de todo o
# trabalho e perder a capa na ultima linha, entao a qualidade cede sozinha.
PESO_MAXIMO = 2 * 1024 * 1024
QUALIDADES = (92, 86, 78, 70, 60)

# Quanto a imagem da cena e empurrada. Miniatura compete com outras vinte na
# mesma tela: a mesma imagem que fica bonita em movimento fica apagada
# parada, e o que some primeiro e a cor.
SATURACAO = 1.28
CONTRASTE = 1.14
BRILHO = 1.04

MAX_LINHAS = 4
# Fracao da altura onde a base do titulo se apoia. Nao e o centro: o rosto da
# cena costuma estar no terco de cima, e cobrir o rosto com texto tira o que
# faz a pessoa parar.
Y_BASE = 0.86
LARGURA_UTIL = 0.90


def _preencher(imagem: Image.Image) -> Image.Image:
    """1080x1920 a partir da imagem da cena, sem espremer.

    Retrato: corta o excedente do lado maior. Quadrada ou deitada (fotos 1:1
    desde 14/09/2026): recortar para 9:16 jogaria fora quase metade da
    largura, entao ela entra INTEIRA sobre o borrado dela mesma, no terco de
    cima — o mesmo "nao cortar a foto" que ele pediu para o video.
    """
    origem = imagem.convert("RGB")
    if origem.width / max(1, origem.height) > 0.75:
        escala = max(LARGURA / origem.width, ALTURA / origem.height)
        fundo = origem.resize((max(1, round(origem.width * escala)),
                               max(1, round(origem.height * escala))),
                              Image.LANCZOS)
        esquerda = (fundo.width - LARGURA) // 2
        topo = (fundo.height - ALTURA) // 2
        fundo = fundo.crop((esquerda, topo, esquerda + LARGURA, topo + ALTURA))
        fundo = ImageEnhance.Brightness(
            fundo.filter(ImageFilter.GaussianBlur(40))).enhance(0.55)
        alto = max(1, round(origem.height * LARGURA / origem.width))
        fundo.paste(origem.resize((LARGURA, alto), Image.LANCZOS),
                    (0, max(0, (ALTURA - alto) // 3)))
        return fundo
    escala = max(LARGURA / origem.width, ALTURA / origem.height)
    novo = (max(1, round(origem.width * escala)),
            max(1, round(origem.height * escala)))
    origem = origem.resize(novo, Image.LANCZOS)
    esquerda = (origem.width - LARGURA) // 2
    # Do TERCO de cima, e nao do centro: em retrato o rosto fica em cima, e
    # cortar centralizado decapita metade das cenas.
    topo = min(max(0, (origem.height - ALTURA) // 3), origem.height - ALTURA)
    return origem.crop((esquerda, topo, esquerda + LARGURA, topo + ALTURA))


def _fundo_de_reserva(cores: dict) -> Image.Image:
    return gradient(LARGURA, ALTURA, cores.get("bg_top", "#0d0b12"),
                    cores.get("bg_bottom", "#191320")).convert("RGB")


def _realcar(imagem: Image.Image) -> Image.Image:
    imagem = ImageEnhance.Color(imagem).enhance(SATURACAO)
    imagem = ImageEnhance.Contrast(imagem).enhance(CONTRASTE)
    return ImageEnhance.Brightness(imagem).enhance(BRILHO)


def _escurecer_o_pe(imagem: Image.Image) -> Image.Image:
    """Sombra que sobe do pe, para o titulo ter onde se apoiar.

    Escurecer a imagem INTEIRA seria mais simples e e o erro classico: a capa
    perde o brilho que faz o olho parar. Aqui so o pe cede.
    """
    camada = Image.new("RGBA", (LARGURA, ALTURA), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(camada)
    comeco = int(ALTURA * 0.46)
    for linha in range(comeco, ALTURA):
        t = (linha - comeco) / max(1, ALTURA - comeco)
        desenho.line([(0, linha), (LARGURA, linha)],
                     fill=(6, 5, 10, int(232 * (t ** 1.5))))
    # Um toque no topo tambem: e onde mora o selo da parte.
    for linha in range(0, int(ALTURA * 0.16)):
        t = 1 - linha / max(1, ALTURA * 0.16)
        desenho.line([(0, linha), (LARGURA, linha)],
                     fill=(6, 5, 10, int(150 * (t ** 1.4))))
    return Image.alpha_composite(imagem.convert("RGBA"), camada).convert("RGB")


def sem_o_selo(titulo: str) -> str:
    """Tira o `(Parte 6)` do fim do titulo.

    `titulo_da_parte` acrescenta esse sufixo porque no YouTube ele e o titulo
    do VIDEO, e ali ele precisa estar. Na capa o selo amarelo ja diz a parte,
    e manter os dois gastava uma das quatro linhas repetindo o que estava
    escrito a 1600 px dali.
    """
    import re
    return re.sub(r"\s*[\(\[]\s*parte\s+\d+\s*[\)\]]\s*$", "",
                  str(titulo or ""), flags=re.IGNORECASE).strip()


PALAVRA_ORFA = 3


def _quebrar(texto: str, fonte, largura: int) -> list[str]:
    """Quebra gulosa simples: a linha enche ate nao caber mais."""
    linhas, atual = [], ""
    for palavra in str(texto).split():
        teste = f"{atual} {palavra}".strip()
        if not atual or fonte.getlength(teste) <= largura:
            atual = teste
            continue
        linhas.append(atual)
        atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def _tem_orfa(linhas: list) -> bool:
    """Alguma linha e uma palavra curta sozinha?

    "A VERDADEIRA FACE" saia como "A" / "VERDADEIRA" / "FACE": uma letra
    ocupando uma linha inteira de 150 px de altura. Nao da para consertar isso
    empurrando a palavra para a linha seguinte — ela nao cabe. O que conserta
    e escolher um corpo MENOR, onde "A VERDADEIRA" cabe junto.
    """
    return any(len(L.split()) == 1 and len(L) <= PALAVRA_ORFA for L in linhas)


def _fonte_e_linhas(texto: str, caminho: str, largura: int,
                    maximo: int = 150, minimo: int = 54):
    """O maior corpo que quebra BEM: dentro da largura, do teto de linhas e
    sem palavra orfa. A busca desce de 6 em 6 e para no primeiro que serve."""
    reserva = None
    for tamanho in range(maximo, minimo - 1, -6):
        fonte = load_font(caminho, tamanho)
        linhas = _quebrar(texto, fonte, largura)
        cabe = all(fonte.getlength(L) <= largura for L in linhas)
        if not cabe or len(linhas) > MAX_LINHAS:
            continue
        if reserva is None:
            reserva = (fonte, linhas)
        if not _tem_orfa(linhas):
            return fonte, linhas
    # Titulo de uma palavra so, ou palavra gigante: orfa e inevitavel e uma
    # capa com orfa ganha de uma capa sem titulo.
    if reserva is not None:
        return reserva
    fonte = load_font(caminho, minimo)
    return fonte, _quebrar(texto, fonte, largura)[:MAX_LINHAS]


def _selo_da_parte(imagem: Image.Image, texto: str, fontes: dict,
                   cores: dict) -> None:
    """A faixa `PARTE 6` no alto. Numa serie ela e informacao, nao enfeite:
    quem achou a parte 6 no feed precisa saber que existem cinco antes."""
    fonte = load_font(fontes.get("black", "arialbd.ttf"), 58)
    desenho = ImageDraw.Draw(imagem)
    largura = int(fonte.getlength(texto))
    alto = 84
    x, y = int(LARGURA * 0.055), int(ALTURA * 0.045)
    caixa = (x, y, x + largura + 56, y + alto)
    desenho.rounded_rectangle(caixa, radius=14,
                              fill=hex_rgb(cores.get("accent", "#ffb703")))
    desenho.text((x + 28, y + alto // 2), texto, font=fonte,
                 fill=(18, 14, 8), anchor="lm")


def _titulo(imagem: Image.Image, texto: str, fontes: dict, cores: dict) -> None:
    largura = int(LARGURA * LARGURA_UTIL)
    fonte, linhas = _fonte_e_linhas(texto, fontes.get("black", "arialbd.ttf"),
                                    largura)
    desenho = ImageDraw.Draw(imagem)
    alto = fonte.size + 14
    base = int(ALTURA * Y_BASE)
    topo = base - alto * len(linhas)

    # A barra de acento CENTRADA e colada no bloco. Encostada a esquerda e a
    # 34 px do topo calculado, ela caia longe do texto quando o titulo tinha
    # menos linhas — e ali no meio do nada ela nao lia como acento, lia como
    # risco perdido na imagem.
    meio = LARGURA // 2
    desenho.rounded_rectangle(
        (meio - 80, topo - 26, meio + 80, topo - 14),
        radius=6, fill=hex_rgb(cores.get("accent", "#ffb703")))

    cor = hex_rgb(cores.get("text", "#f7f3ea"))
    for i, linha in enumerate(linhas):
        y = topo + alto * i + alto // 2
        desenho.text((LARGURA // 2, y), linha, font=fonte, fill=cor,
                     anchor="mm", stroke_width=max(6, fonte.size // 14),
                     stroke_fill=(10, 8, 14))


def _gravar(imagem: Image.Image, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    for qualidade in QUALIDADES:
        imagem.save(destino, "JPEG", quality=qualidade, optimize=True,
                    progressive=True)
        if destino.stat().st_size <= PESO_MAXIMO:
            return destino
    return destino


def montar(titulo: str, cena: Path | None, destino: Path, *,
           parte: int = 1, partes: int = 1,
           config_render: dict | None = None) -> Path:
    """A capa de UMA parte. `cena` e a imagem do gancho daquela parte."""
    config_render = config_render or {}
    cores = config_render.get("colors") or {}
    fontes = config_render.get("fonts") or {}

    base = None
    if cena is not None and Path(cena).is_file():
        try:
            with Image.open(cena) as aberta:
                base = _preencher(aberta)
        except Exception:                                      # noqa: BLE001
            base = None
    if base is None:
        # Sem imagem a capa ainda sai: um fundo do canal e o titulo. Uma capa
        # feia ganha de nenhuma capa, e "nenhuma" e o frame que o YouTube
        # escolher sozinho.
        base = _fundo_de_reserva(cores)
        base = base.filter(ImageFilter.GaussianBlur(2))
    else:
        base = _realcar(base)
    base = _escurecer_o_pe(base)

    texto = str(titulo or "").strip()
    if partes > 1:
        _selo_da_parte(base, f"PARTE {int(parte)}", fontes, cores)
        texto = sem_o_selo(texto) or texto
    _titulo(base, texto.upper(), fontes, cores)
    return _gravar(base, Path(destino))


def caminho(pasta: Path, parte: int, partes: int) -> Path:
    """Onde a capa daquela parte mora, ao lado do mp4."""
    sufixo = f"_p{int(parte):02d}" if partes > 1 else ""
    return Path(pasta) / f"capa{sufixo}.jpg"


__all__ = ["montar", "caminho", "LARGURA", "ALTURA"]
