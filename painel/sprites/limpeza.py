# -*- coding: utf-8 -*-
"""A limpeza da folha: fundo, alfa minimo, despill, linhas de grade, ilhas.

Tudo recebe e devolve um array `uint8` HxWx4 (RGBA) NOVO -- nada e alterado
no lugar, e e isso que deixa a pagina ter "desfazer" guardando so a receita.

O QUE A FOLHA DO CHATGPT TEM, medido na `11243.png` (1942x809, 28/09/2026),
e que nenhum limiar de branco resolve:

  - ela ja vem RGBA, e 256 mil pixels tem alfa 1 ou 2 com a cor (0,255,0): um
    "fantasma" verde vivo em volta de cada quadro e em cima das linhas da
    grade. Num visualizador que ignora o alfa (ou numa mistura que o soma), e
    exatamente a franja verde e a grade que o Adrian viu;
  - a grade desenhada tem 1 a 3 px e entorta: nao e reta nem continua;
  - o limiar de 240 do `piriri.py` nao acha branco nenhum ali -- e onde acha,
    fura o BRILHO BRANCO de dentro da bola (215 pixels de alfa 254 viraram
    buraco). Por isso o fundo aqui sai por PREENCHIMENTO A PARTIR DAS BORDAS:
    branco de dentro do desenho nao encosta na borda e fica.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from .rotulos import rotular

RAIZ3 = float(np.sqrt(3.0))


# ------------------------------------------------------------------ basico
def abrir(caminho) -> Image.Image:
    """PNG, JPG, WEBP... sempre em RGBA."""
    with Image.open(caminho) as img:
        img.load()
        return img.convert("RGBA")


def para_array(img) -> np.ndarray:
    if isinstance(img, np.ndarray):
        return img
    return np.asarray(img.convert("RGBA"), dtype=np.uint8).copy()


def para_imagem(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.ascontiguousarray(arr, dtype=np.uint8), "RGBA")


def distancia(rgb: np.ndarray, cor) -> np.ndarray:
    """Distancia de cor na escala 0..255 (euclidiana / raiz de 3)."""
    k = np.asarray(cor, np.float32)[:3]
    return np.sqrt(((rgb.astype(np.float32) - k) ** 2).sum(-1)) / RAIZ3


def caixa(valores: np.ndarray, raio: int) -> np.ndarray:
    """Soma numa janela (2r+1)x(2r+1) por imagem integral. 2D ou HxWxC."""
    raio = max(0, int(raio))
    v = valores.astype(np.float64)
    if raio == 0:
        return v
    # separavel: soma acumulada num eixo, depois no outro (fatias, sem
    # indice sofisticado -- e o que a deixa rapida numa folha inteira)
    for eixo in (0, 1):
        largura = [(0, 0)] * v.ndim
        largura[eixo] = (raio + 1, raio)
        acumulado = np.pad(v, largura).cumsum(axis=eixo)
        n = v.shape[eixo]
        fim = [slice(None)] * v.ndim
        ini = [slice(None)] * v.ndim
        fim[eixo] = slice(2 * raio + 1, 2 * raio + 1 + n)
        ini[eixo] = slice(0, n)
        v = acumulado[tuple(fim)] - acumulado[tuple(ini)]
    return v


# ------------------------------------------------------------------- fundo
def estimar_fundo(arr: np.ndarray) -> dict:
    """De que cor e o fundo, e se a folha ja vem transparente.

    Borda de 2 px. Se ela e quase toda transparente, a folha ja tem alfa: a
    "cor do fundo" que interessa entao e a do FANTASMA (a cor que sobrou nos
    pixels de alfa baixo), que e a que o despill deve tirar. Senao, e a cor
    mais comum da borda.
    """
    h, w = arr.shape[:2]
    anel = np.concatenate([arr[:2].reshape(-1, 4), arr[-2:].reshape(-1, 4),
                           arr[:, :2].reshape(-1, 4),
                           arr[:, -2:].reshape(-1, 4)])
    transparente = float((anel[:, 3] < 128).mean()) > 0.5
    if transparente:
        a = arr[..., 3]
        fantasmas = arr[(a > 0) & (a < 64)][:, :3]
        cor = _moda(fantasmas) if len(fantasmas) else None
        return {"cor": cor, "transparente": True}
    return {"cor": _moda(anel[anel[:, 3] >= 128][:, :3]), "transparente": False}


def _moda(rgb: np.ndarray):
    """A cor mais comum (em degraus de 8), devolvida pela media do degrau."""
    q = (rgb.astype(np.int32) // 8)
    chave = q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]
    valores, contagem = np.unique(chave, return_counts=True)
    vencedor = valores[int(np.argmax(contagem))]
    media = rgb[chave == vencedor].mean(0)
    return tuple(int(round(c)) for c in media)


def remover_fundo(arr: np.ndarray, metodo: str = "bordas", cor=None,
                  tolerancia: float = 24, suavidade: float = 16,
                  descontaminar: bool = True) -> np.ndarray:
    """Tira o fundo. Metodos:

    `nenhum`  a folha ja vem transparente;
    `bordas`  preenche a partir da moldura so o que parece fundo E encosta
              nela (o branco do brilho, la dentro, fica);
    `cor`     cor-chave em qualquer lugar (o conta-gotas escolhe a cor).

    `suavidade` e a faixa de tolerancia em que o alfa cai aos poucos, em vez
    de cortar em degrau: e o que tira o serrilhado. `descontaminar` tira a
    cor do fundo que ficou misturada nesse pixel meio transparente
    (F = (C - (1-a)K)/a); sem isso, sobre fundo escuro sobra um halo claro.
    """
    if metodo == "nenhum":
        return arr.copy()
    if cor is None:
        cor = estimar_fundo(arr)["cor"] or (255, 255, 255)
    rgb = arr[..., :3].astype(np.float32)
    alfa = arr[..., 3].astype(np.float32)
    d = distancia(rgb, cor)
    tolerancia = float(tolerancia)
    suavidade = max(0.0, float(suavidade))
    candidato = (d <= tolerancia + suavidade) | (alfa == 0)
    if metodo == "bordas":
        comps = rotular(candidato)
        ids = np.nonzero(comps.tocam_a_borda())[0] + 1
        fundo = np.isin(comps.rotulos, ids)
    elif metodo == "cor":
        fundo = candidato
    else:
        raise ValueError(f"metodo de fundo desconhecido: {metodo}")

    fator = np.ones_like(alfa)
    if suavidade > 0:
        fator[fundo] = np.clip((d[fundo] - tolerancia) / suavidade, 0.0, 1.0)
    else:
        fator[fundo] = 0.0
    saida = arr.copy()
    if descontaminar:
        meio = fundo & (fator > 0) & (fator < 1)
        if meio.any():
            f = fator[meio][:, None]
            k = np.asarray(cor, np.float32)[:3]
            limpo = (rgb[meio] - (1.0 - f) * k) / np.maximum(f, 1e-3)
            saida[..., :3][meio] = np.clip(limpo, 0, 255).round().astype(
                np.uint8)
    saida[..., 3] = np.clip(alfa * fator, 0, 255).round().astype(np.uint8)
    return zerar_transparentes(saida)


def alfa_minimo(arr: np.ndarray, limite: int) -> np.ndarray:
    """Pixel com alfa abaixo do limite vira transparente de vez.

    E o passo que apaga o fantasma verde de alfa 1-2 da folha do ChatGPT --
    e com ele a grade desenhada por cima, que era feita do mesmo fantasma.
    """
    saida = arr.copy()
    saida[..., 3][saida[..., 3] < int(limite)] = 0
    return zerar_transparentes(saida)


def zerar_transparentes(arr: np.ndarray) -> np.ndarray:
    """RGB de pixel de alfa 0 vira preto.

    Nao e cosmetico: o fantasma verde e COR guardada em pixel invisivel. Um
    visualizador que ignora o alfa mostra; um filtro de textura (o palco
    amplia a folha) mistura essa cor na borda. O palco ainda roda o
    `fix_alpha_border` do Godot na importacao, que parte daqui.
    """
    saida = arr.copy()
    saida[..., :3][saida[..., 3] == 0] = 0
    return saida


# ------------------------------------------------------------------ despill
def cor_de_dentro(arr: np.ndarray, confiavel: np.ndarray,
                  raio: int = 4, onde: np.ndarray | None = None) -> np.ndarray:
    """A cor media dos pixels CONFIAVEIS em volta de cada pixel.

    Janela crescente (r, 2r, 4r, 8r): o pixel da franja pega a cor do
    desenho mais proximo, nao a media da folha inteira. Com `onde`, so a
    regiao em volta desses pixels e calculada (o resto sai com a propria
    cor) -- a franja costuma ser uma fracao da folha.
    """
    if onde is not None and onde.any():
        ys, xs = np.nonzero(onde)
        folga = raio * 8 + 1
        y0, y1 = max(0, ys.min() - folga), min(arr.shape[0], ys.max() + folga)
        x0, x1 = max(0, xs.min() - folga), min(arr.shape[1], xs.max() + folga)
        saida = arr[..., :3].astype(np.float64)
        saida[y0:y1, x0:x1] = cor_de_dentro(arr[y0:y1, x0:x1],
                                            confiavel[y0:y1, x0:x1], raio)
        return saida
    rgb = arr[..., :3].astype(np.float64)
    peso = confiavel.astype(np.float64)
    saida = np.zeros_like(rgb)
    falta = np.ones(confiavel.shape, bool)
    for r in (raio, raio * 2, raio * 4, raio * 8):
        soma_p = caixa(peso, r)
        soma_c = caixa(rgb * peso[..., None], r)
        tem = falta & (soma_p > 0)
        saida[tem] = soma_c[tem] / soma_p[tem][:, None]
        falta &= ~tem
        if not falta.any():
            break
    saida[falta] = rgb[falta]
    return saida


def despill(arr: np.ndarray, cor, forca: float = 1.0,
            tolerancia: float = 40, alfa_solido: int = 200,
            raio: int = 4) -> np.ndarray:
    """Tira a franja da cor do fundo.

    O despill classico (`verde = min(verde, max(vermelho, azul))`) apagaria o
    verde de um projetil ACIDO VERDE. Aqui o pixel so e trocado na medida em
    que PARECE a cor da franja (distancia menor que `tolerancia`), e ganha a
    cor do desenho que esta em volta dele (`cor_de_dentro`), nao cinza.
    """
    if cor is None or forca <= 0:
        return arr.copy()
    d = distancia(arr[..., :3], cor)
    alfa = arr[..., 3]
    tolerancia = max(1.0, float(tolerancia))
    confiavel = (alfa >= int(alfa_solido)) & (d > tolerancia)
    peso = np.clip(1.0 - d / tolerancia, 0.0, 1.0) * float(forca)
    peso[alfa == 0] = 0
    alvo = peso > 0
    if not alvo.any():
        return arr.copy()
    dentro = cor_de_dentro(arr, confiavel, raio, onde=alvo)
    saida = arr.copy()
    p = peso[alvo][:, None]
    novo = arr[..., :3][alvo] * (1 - p) + dentro[alvo] * p
    saida[..., :3][alvo] = np.clip(novo, 0, 255).round().astype(np.uint8)
    return saida


# ------------------------------------------------------------ linhas de grade
def _maior_corrida(mascara: np.ndarray) -> np.ndarray:
    """Por linha: a maior corrida seguida de True, em fracao da largura."""
    from .rotulos import corridas
    h, w = mascara.shape
    linhas, x0, x1 = corridas(mascara)
    saida = np.zeros(h)
    if len(linhas):
        np.maximum.at(saida, linhas, (x1 - x0).astype(float))
    return saida / max(1, w)


def detectar_linhas(mascara: np.ndarray, espessura_max: int = 8,
                    minimo: float = 0.3, destaque: float = 0.25) -> list:
    """Faixas (y0, y1) de linhas HORIZONTAIS desenhadas. Para as verticais,
    passe a mascara transposta.

    Uma linha da grade e uma fileira com uma corrida LONGA que os vizinhos
    nao tem. Medido na 11243: a linha tem corrida de 50-100% da largura; as
    fileiras que cruzam os quadros, ate 16% (os quadros tem vao entre si).
    Cobertura simples nao serve: o fantasma verde cobre 85% das fileiras dos
    quadros tambem. A mascara e engrossada 2 px antes porque a linha entorta.
    """
    h, _w = mascara.shape
    grossa = mascara.copy()
    for s in (1, 2):
        grossa[s:] |= mascara[:-s]
        grossa[:-s] |= mascara[s:]
    f = _maior_corrida(grossa)
    perto, longe = espessura_max // 2 + 2, espessura_max + 8
    candidatas = []
    for y in range(h):
        if f[y] < minimo:
            continue
        cima = f[max(0, y - longe):max(0, y - perto)]
        baixo = f[min(h, y + perto):min(h, y + longe)]
        vizinho = max(float(np.median(cima)) if len(cima) else 0.0,
                      float(np.median(baixo)) if len(baixo) else 0.0)
        if f[y] - vizinho >= destaque:
            candidatas.append(y)
    faixas = []
    for y in candidatas:
        if faixas and y - faixas[-1][1] <= 2:
            faixas[-1][1] = y + 1
        else:
            faixas.append([y, y + 1])
    saida = []
    for y0, y1 in faixas:
        # a espessura de verdade: onde a mascara ORIGINAL ainda e longa
        pico = y0 + int(np.argmax(f[y0:y1]))
        fina = _maior_corrida(mascara[max(0, pico - espessura_max):
                                      min(h, pico + espessura_max + 1)])
        base = max(0, pico - espessura_max)
        acima = [base + i for i, v in enumerate(fina) if v >= minimo / 2]
        if acima:
            y0, y1 = min(acima[0], y0), max(acima[-1] + 1, y1)
        if y1 - y0 <= espessura_max + 4:
            saida.append((int(y0), int(y1)))
    return saida


def apagar_linhas(arr: np.ndarray, horizontais: list, verticais: list,
                  folga: int = 2, alfa: int = 16) -> np.ndarray:
    """Apaga as faixas das linhas, MENOS onde um desenho as atravessa.

    Coluna a coluna (linha a linha, nas verticais): se logo acima E logo
    abaixo da faixa ha desenho, aquele trecho e do sprite e fica.
    """
    saida = arr.copy()
    a = arr[..., 3]
    h, w = a.shape
    for y0, y1 in horizontais:
        i0, i1 = max(0, y0 - folga), min(h, y1 + folga)
        cima = a[max(0, i0 - 3):i0].max(0) if i0 > 0 else np.zeros(w)
        baixo = a[i1:min(h, i1 + 3)].max(0) if i1 < h else np.zeros(w)
        livre = ~((cima >= alfa) & (baixo >= alfa))
        faixa = saida[i0:i1]
        faixa[:, livre, 3] = 0
    for x0, x1 in verticais:
        i0, i1 = max(0, x0 - folga), min(w, x1 + folga)
        esq = a[:, max(0, i0 - 3):i0].max(1) if i0 > 0 else np.zeros(h)
        dir_ = a[:, i1:min(w, i1 + 3)].max(1) if i1 < w else np.zeros(h)
        livre = ~((esq >= alfa) & (dir_ >= alfa))
        faixa = saida[:, i0:i1]
        faixa[livre, :, 3] = 0
    return zerar_transparentes(saida)


# ------------------------------------------------------------------- ilhas
def tirar_ilhas(arr: np.ndarray, area_min: int, alfa: int = 16):
    """Some com os pontinhos soltos: componente menor que `area_min` px.

    Devolve (array, quantas ilhas sairam). As gotas do acido sao componentes
    proprios tambem (medido: de ~40 a ~700 px), por isso o minimo e ajustavel
    e comeca baixo.
    """
    if area_min <= 1:
        return arr.copy(), 0
    comps = rotular(arr[..., 3] >= int(alfa))
    pequenas = np.nonzero(comps.areas < int(area_min))[0] + 1
    if not len(pequenas):
        return arr.copy(), 0
    saida = arr.copy()
    fora = np.isin(comps.rotulos, pequenas)
    # o halo fraco em volta do pontinho vai junto
    em_volta = caixa(fora.astype(np.float32), 2) > 0
    fraco = arr[..., 3] < int(alfa)
    saida[..., 3][fora | (em_volta & fraco)] = 0
    return zerar_transparentes(saida), int(len(pequenas))


__all__ = ["abrir", "alfa_minimo", "apagar_linhas", "caixa", "cor_de_dentro",
           "despill", "detectar_linhas", "distancia", "estimar_fundo",
           "para_array", "para_imagem", "remover_fundo", "tirar_ilhas",
           "zerar_transparentes"]
