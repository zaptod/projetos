# -*- coding: utf-8 -*-
"""Recorta uma folha de IA com fundo verde ou magenta liso.

Esta nao e outra limpeza generica: a entrada e deliberadamente estreita. O
fundo sai por conexao com a borda, portanto um verde dentro de um olho numa
folha magenta continua no desenho.

O recorte sai CRU (caixa justa + margem). O encaixe no gabarito da peca
(`encaixar`) so acontece quando ele manda o recorte para um destino: em
06/10/2026 o encaixe era feito na hora de subir a folha, com a peca que
estava no seletor ("Sombra"), e 4 olhos mandados aos Olhos cairam na zona da
sombra (256..767 x 552..726) -- olhos gigantes no provador e no video.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from . import limpeza
from .rotulos import rotular

FUNDOS = {"verde": (0, 255, 0), "magenta": (255, 0, 255)}
JUNCAO = {"pouco": 8, "medio": 16, "muito": 32}
# "pares de olhos": junta os pedacos de cada olho (como o medio) e depois
# casa os olhos dois a dois (`_casar_pares`).
NIVEIS = (*JUNCAO, "pares")
ZONAS = {
    "olhos": (480, 340, 645, 684),
    "sobrancelhas": (360, 342, 530, 682),
    "boca": (640, 405, 740, 620),
    "detalhe_rosto": (294, 415, 680, 727),
    "sombra": (256, 532, 768, 748),
    "acessorio_cabeca": (0, 0, 512, 1024),
    "acessorio_costas": (0, 0, 1024, 1024),
}
# Olhos (CONTRATO 2.3): o jogo ve o lutador de cima, olhando para +x; o olho
# de cima e o lado ESQUERDO do rosto. Disco de 102 px; cada olho separado
# cabe num quadrado de 122 px (o disco + 20% de folga), dentro da caixa de
# cada olho (165x160).
OLHO_CIMA = (563, 420)
OLHO_BAIXO = (563, 604)
OLHO_LADO = 122
MODOS_OLHOS = ("separar", "girar", "vista-de-cima")
# Casar dois olhos: tamanhos parecidos, lado a lado, e o vao entre eles ate
# 3x a largura de um olho (a IA desenha 24-110 px entre os olhos de um par).
PAR_PROPORCAO = 0.6
PAR_ALINHADO = 0.35
PAR_VAO = 3.0


@dataclass
class Recorte:
    imagem: np.ndarray
    caixa: tuple[int, int, int, int]
    area: int
    # Modo pares de olhos: "par" (dois olhos), "um" (olho sozinho) ou
    # "sobra" (pedacinho que so passou perto de um olho).
    tipo: str = ""
    # O par na ordem do jogo: [olho de cima, olho de baixo], cada um justo.
    olhos: list | None = None
    orientacao: str = ""              # "lado" (desenhado de frente) ou "pe" (ja de cima)


@dataclass
class Resultado:
    limpo: np.ndarray
    fundo: str
    recortes: list[Recorte]
    avisos: list[str]
    cor_chave_dentro: int


def _borda(arr: np.ndarray) -> np.ndarray:
    h, w = arr.shape[:2]
    a = min(4, h, w)
    return np.concatenate((arr[:a, :, :3].reshape(-1, 3),
                           arr[-a:, :, :3].reshape(-1, 3),
                           arr[:, :a, :3].reshape(-1, 3),
                           arr[:, -a:, :3].reshape(-1, 3)))


def detectar_fundo(arr: np.ndarray) -> str:
    """Devolve verde/magenta; outros fundos recebem uma frase para o Adrian."""
    borda = _borda(arr)
    melhor, fracao = None, 0.0
    for nome, cor in FUNDOS.items():
        perto = limpeza.distancia(borda, cor) <= 42
        atual = float(perto.mean())
        if atual > fracao:
            melhor, fracao = nome, atual
    if melhor is None or fracao < 0.60:
        raise ValueError("o fundo precisa ser verde ou magenta liso")
    return melhor


def _grupos(comps, juntar: int, area_min: int, satelites: bool = False):
    """Componentes proximos viram um desenho; poeira isolada nao vira arte.
    Com `satelites`, o pedacinho que so passou perto sai do desenho
    (`_sem_satelites`)."""
    if not comps.n:
        return []
    caixas = comps.caixas.astype(np.int64)
    pai = np.arange(comps.n)

    def raiz(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    x0, y0, x1, y1 = caixas.T
    dx = np.maximum(0, np.maximum(x0[:, None] - x1[None, :],
                                  x0[None, :] - x1[:, None]))
    dy = np.maximum(0, np.maximum(y0[:, None] - y1[None, :],
                                  y0[None, :] - y1[:, None]))
    pares = np.argwhere((np.maximum(dx, dy) <= int(juntar))
                         & (np.arange(comps.n)[:, None] < np.arange(comps.n)[None, :]))
    for a, b in pares:
        ra, rb = raiz(int(a)), raiz(int(b))
        if ra != rb:
            pai[max(ra, rb)] = min(ra, rb)
    grupos: dict[int, list[int]] = {}
    for i in range(comps.n):
        grupos.setdefault(raiz(i), []).append(i)
    saida = []
    for membros in grupos.values():
        if satelites:
            membros, soltos = _sem_satelites(caixas, comps.areas, membros)
            # O pedacinho solto vira recorte proprio (se nao for poeira): ele
            # escolhe se manda, e o desenho principal nao encolhe por causa dele.
            for s in soltos:
                if int(comps.areas[s]) >= int(area_min):
                    saida.append((_caixa_de(caixas, [s]), [s], int(comps.areas[s]), True))
        area = int(comps.areas[membros].sum())
        if area < int(area_min):
            continue
        saida.append((_caixa_de(caixas, membros), membros, area, False))
    return _leitura(saida)


# Um brilho, uma faisca ou um respingo desenhado PERTO de um olho (a menos de
# 16 px, a juncao do medio) entrava no recorte dele: a caixa crescia e, no
# encaixe (que usa a caixa), o olho encolhia (conferente, 07/10).
# SO NOS PARES DE OLHOS. Na v54 a regra valia em todo modo menos o "muito" e
# amputou arte de efeito: na folha real 11243.png (projetil com cauda de
# gotas) 24 de 26 recortes perderam a cauda, e o evento_dano ficou com
# buracos dentro da caixa (reprovacao do conferente, 07/10). Fora dos olhos o
# recorte e o mesmo de antes, byte a byte.
# Nos olhos, fica no desenho: todo pedaco grande (>= SATELITE_AREA da area do
# maior), todo pedaco ligado a eles por uma CORRENTE de vizinhos a ate
# SATELITE_VAO px (os cilios da folha realista ficam a ~6 px), e tudo o que
# toca a caixa do que ficou (nunca um buraco dentro do desenho). So o resto
# sai, como "sobra".
SATELITE_AREA = 0.10
SATELITE_VAO = JUNCAO["pouco"]


def _vao_entre(c, g) -> int:
    """O mesmo vao do `_grupos` (o maior dos dois eixos; 0 = encostam)."""
    dx = max(0, int(c[0]) - int(g[2]), int(g[0]) - int(c[2]))
    dy = max(0, int(c[1]) - int(g[3]), int(g[1]) - int(c[3]))
    return max(dx, dy)


def _sem_satelites(caixas: np.ndarray, areas: np.ndarray, membros: list[int]):
    """(ficam, soltos) de um grupo de olhos; ver o comentario acima."""
    if len(membros) < 2:
        return membros, []
    limite = SATELITE_AREA * max(int(areas[m]) for m in membros)
    ficam = [m for m in membros if int(areas[m]) >= limite]
    resto = [m for m in membros if int(areas[m]) < limite]
    mudou = True
    while mudou and resto:
        mudou = False
        caixa = _caixa_de(caixas, ficam)
        for m in list(resto):
            perto = any(_vao_entre(caixas[m], caixas[f]) <= SATELITE_VAO for f in ficam)
            if perto or _vao_entre(caixas[m], caixa) == 0:
                ficam.append(m)
                resto.remove(m)
                mudou = True
    return sorted(ficam), resto


def _leitura(itens):
    """Ordem de leitura (linha a linha, da esquerda para a direita), sem
    importar o metodo interno dos rotulos. Linha = centros a menos de meia
    altura: um olho com cilios (mais alto) fica na linha dos vizinhos, e o
    "Recorte 3" e o terceiro desenho que ele ve na folha."""
    restantes = sorted(itens, key=lambda item: (item[0][1] + item[0][3]) / 2)
    saida = []
    while restantes:
        primeiro = restantes[0]
        cy = (primeiro[0][1] + primeiro[0][3]) / 2
        meia = (primeiro[0][3] - primeiro[0][1]) / 2
        linha = [i for i in restantes if abs((i[0][1] + i[0][3]) / 2 - cy) <= max(meia, 1)]
        restantes = [i for i in restantes if not any(i is j for j in linha)]
        saida.extend(sorted(linha, key=lambda item: item[0][0]))
    return saida


def _caixa_de(caixas: np.ndarray, membros) -> tuple[int, int, int, int]:
    c = caixas[list(membros)]
    return (int(c[:, 0].min()), int(c[:, 1].min()), int(c[:, 2].max()), int(c[:, 3].max()))


# ------------------------------------------------------------ pares de olhos
def _parecidos(a, b, eixo: str):
    """(vao, ordem) se as caixas a e b sao dois olhos de um par; senao None.

    `eixo` "lado": um ao lado do outro (a IA desenha de frente); "pe": um em
    cima do outro (ja visto de cima). Tamanhos parecidos, alinhados, e o vao
    ate PAR_VAO vezes o tamanho de um olho naquele eixo."""
    wa, ha = a[2] - a[0], a[3] - a[1]
    wb, hb = b[2] - b[0], b[3] - b[1]
    if min(wa, wb) <= 0 or min(ha, hb) <= 0:
        return None
    if min(wa, wb) / max(wa, wb) < PAR_PROPORCAO or min(ha, hb) / max(ha, hb) < PAR_PROPORCAO:
        return None
    if eixo == "lado":
        alinhado = abs((a[1] + a[3]) - (b[1] + b[3])) / 2 <= PAR_ALINHADO * max(ha, hb)
        vao = max(b[0] - a[2], a[0] - b[2])
        medida = max(wa, wb)
    else:
        alinhado = abs((a[0] + a[2]) - (b[0] + b[2])) / 2 <= PAR_ALINHADO * max(wa, wb)
        vao = max(b[1] - a[3], a[1] - b[3])
        medida = max(ha, hb)
    if not alinhado or vao < 0 or vao > PAR_VAO * medida:
        return None
    return vao / medida


def _ordem_do_jogo(caixa_a, caixa_b, eixo: str) -> bool:
    """True se `a` vai no olho de CIMA. De frente, o olho da DIREITA da imagem
    e o esquerdo do rosto, que no jogo (de cima, olhando para +x) fica em cima;
    ja de cima, o de cima continua em cima."""
    if eixo == "lado":
        return caixa_a[0] + caixa_a[2] > caixa_b[0] + caixa_b[2]
    return caixa_a[1] + caixa_a[3] < caixa_b[1] + caixa_b[3]


def _dividir(caixas: np.ndarray, membros: list[int]):
    """Um desenho que ja e o par (os olhos ficaram a menos de 16 px e o medio
    os juntou): acha o vao limpo que o divide em duas metades parecidas."""
    if len(membros) < 2:
        return None
    melhor = None
    for eixo, (lo, hi) in (("lado", (0, 2)), ("pe", (1, 3))):
        ordem = sorted(membros, key=lambda m: caixas[m][lo])
        fim = -10**9
        for i in range(1, len(ordem)):
            fim = max(fim, int(caixas[ordem[i - 1]][hi]))
            if fim > int(caixas[ordem[i]][lo]):
                continue
            a, b = ordem[:i], ordem[i:]
            if min(int(caixas[m][lo]) for m in b) < fim:
                continue
            nota = _parecidos(_caixa_de(caixas, a), _caixa_de(caixas, b), eixo)
            if nota is not None and (melhor is None or nota < melhor[0]):
                melhor = (nota, eixo, a, b)
    return melhor


def _casar_pares(grupos, caixas: np.ndarray):
    """[(caixa, membros, area, tipo, metades|None, eixo)] -- metades na ordem
    do jogo (cima, baixo). Primeiro o desenho que ja e o par; depois os olhos
    soltos, casados dois a dois pelo menor vao (um olho nunca entra em dois
    pares; o vizinho de outro par fica mais longe que o proprio par)."""
    itens = []
    soltos = []
    for caixa, membros, area, sobra in grupos:
        if sobra:                                  # o pedacinho solto nunca vira olho de um par
            itens.append((caixa, membros, area, "sobra", None, ""))
            continue
        dividido = _dividir(caixas, membros)
        if dividido is not None:
            _, eixo, a, b = dividido
            cima, baixo = (a, b) if _ordem_do_jogo(_caixa_de(caixas, a), _caixa_de(caixas, b), eixo) else (b, a)
            itens.append((caixa, membros, area, "par", [cima, baixo], eixo))
        else:
            soltos.append((caixa, membros, area))
    candidatos = []
    for i in range(len(soltos)):
        for j in range(i + 1, len(soltos)):
            for eixo in ("lado", "pe"):
                nota = _parecidos(soltos[i][0], soltos[j][0], eixo)
                if nota is not None:
                    candidatos.append((nota, eixo == "pe", i, j, eixo))
    usados: set[int] = set()
    for _nota, _pe, i, j, eixo in sorted(candidatos):
        if i in usados or j in usados:
            continue
        usados.update((i, j))
        (ca, ma, aa), (cb, mb, ab) = soltos[i], soltos[j]
        cima, baixo = (ma, mb) if _ordem_do_jogo(ca, cb, eixo) else (mb, ma)
        caixa = (min(ca[0], cb[0]), min(ca[1], cb[1]), max(ca[2], cb[2]), max(ca[3], cb[3]))
        itens.append((caixa, ma + mb, aa + ab, "par", [cima, baixo], eixo))
    for i, (caixa, membros, area) in enumerate(soltos):
        if i not in usados:
            itens.append((caixa, membros, area, "um", None, ""))
    return _leitura(itens)


def _justo(img: np.ndarray) -> np.ndarray | None:
    ys, xs = np.nonzero(img[..., 3] >= 16)
    if not len(xs):
        return None
    return img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def recortar(origem, *, juntar: int = JUNCAO["medio"], area_min: int = 50,
             margem: int = 8, tolerancia: float = 34, suavidade: float = 22,
             pares: bool = False) -> Resultado:
    """Limpa e separa a folha, sem apagar a cor-chave fechada num desenho.

    Com `pares`, os desenhos sao olhos: cada par vira UM recorte (tipo "par",
    com os dois olhos guardados na ordem do jogo) e o olho sem par vira um
    recorte "um"."""
    arr = limpeza.para_array(origem)
    if arr.ndim == 3 and arr.shape[2] == 3:          # folha RGB (JPG ou array sem alfa)
        arr = np.dstack([arr, np.full(arr.shape[:2], 255, np.uint8)])
    fundo = detectar_fundo(arr)
    cor = FUNDOS[fundo]
    # `bordas` e a protecao importante: so o candidato conectado ao fundo sai.
    limpo = limpeza.remover_fundo(arr, "bordas", cor, tolerancia, suavidade,
                                  descontaminar=True)
    limpo = limpeza.alfa_minimo(limpo, 8)
    mascara = limpo[..., 3] >= 16
    comps = rotular(mascara)
    juncao = JUNCAO["medio"] if pares else juntar
    grupos = _grupos(comps, juncao, area_min, satelites=pares)
    caixas = comps.caixas.astype(np.int64) if comps.n else np.zeros((0, 4), np.int64)
    itens = (_casar_pares(grupos, caixas) if pares
             else [(caixa, membros, area, "sobra" if sobra else "", None, "")
                   for caixa, membros, area, sobra in grupos])
    h, w = mascara.shape
    recortes = []
    rotulos = comps.rotulos
    for caixa, membros, area, tipo, metades, eixo in itens:
        x0, y0, x1, y1 = caixa
        x0, y0 = max(0, x0 - int(margem)), max(0, y0 - int(margem))
        x1, y1 = min(w, x1 + int(margem)), min(h, y1 + int(margem))
        q = limpo[y0:y1, x0:x1].copy()
        # Uma coisa que passou perto nao vaza para o recorte do vizinho.
        pertence = np.isin(rotulos[y0:y1, x0:x1], np.asarray(membros) + 1)
        q[~pertence] = 0
        olhos = None
        if metades:
            olhos = []
            for metade in metades:
                so = q.copy()
                so[~np.isin(rotulos[y0:y1, x0:x1], np.asarray(metade) + 1)] = 0
                olhos.append(_justo(so))
        recortes.append(Recorte(q, (x0, y0, x1, y1), area, tipo, olhos, eixo))
    perto_chave = (limpo[..., 3] >= 16) & (limpeza.distancia(limpo[..., :3], cor) <= tolerancia)
    dentro = int(perto_chave.sum())
    visiveis = max(1, int(mascara.sum()))
    avisos = []
    if dentro > max(24, visiveis // 100):
        avisos.append(f"há bastante {fundo} parecido dentro de um desenho; confira antes de mandar")
    return Resultado(limpo, fundo, recortes, avisos, dentro)


# ------------------------------------------------------------------ encaixe
def _redimensionar(img: np.ndarray, escala: float) -> np.ndarray:
    tamanho = (max(1, round(img.shape[1] * escala)), max(1, round(img.shape[0] * escala)))
    return np.asarray(Image.fromarray(np.ascontiguousarray(img), "RGBA")
                      .resize(tamanho, Image.Resampling.LANCZOS), np.uint8)


def _colar(tela: np.ndarray, img: np.ndarray, cx: int, cy: int) -> None:
    """Cola por cima (alfa), centrado em (cx, cy), cortando o que passar da tela."""
    h, w = img.shape[:2]
    x0, y0 = cx - w // 2, cy - h // 2
    ax0, ay0 = max(0, x0), max(0, y0)
    ax1, ay1 = min(tela.shape[1], x0 + w), min(tela.shape[0], y0 + h)
    if ax1 <= ax0 or ay1 <= ay0:
        return
    pedaco = img[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0]
    destino = tela[ay0:ay1, ax0:ax1]
    a = pedaco[..., 3:4].astype(np.float32) / 255.0
    b = destino[..., 3:4].astype(np.float32) / 255.0
    sai = a + b * (1 - a)
    cor = (pedaco[..., :3] * a + destino[..., :3] * b * (1 - a)) / np.maximum(sai, 1e-6)
    destino[..., :3] = np.clip(cor, 0, 255).round().astype(np.uint8)
    destino[..., 3:4] = np.clip(sai * 255, 0, 255).round().astype(np.uint8)


def no_quadro(recorte: np.ndarray, caixa, tamanho=(1024, 1024)) -> np.ndarray:
    """Encaixa proporcionalmente (sem distorcer) e centrado em `caixa`
    (x0, y0, x1, y1) de uma tela `tamanho` (largura, altura)."""
    x0, y0, x1, y1 = caixa
    tela = np.zeros((int(tamanho[1]), int(tamanho[0]), 4), np.uint8)
    corte = _justo(recorte)
    if corte is None:
        return tela
    escala = min((x1 - x0) / corte.shape[1], (y1 - y0) / corte.shape[0])
    q = _redimensionar(corte, escala)
    py = y0 + ((y1 - y0) - q.shape[0]) // 2
    px = x0 + ((x1 - x0) - q.shape[1]) // 2
    tela[py:py + q.shape[0], px:px + q.shape[1]] = q
    return tela


def no_gabarito(recorte: np.ndarray, parte: str) -> np.ndarray:
    """Encaixa proporcionalmente no quadrado 1024, na zona da parte escolhida."""
    return no_quadro(recorte, ZONAS.get(str(parte), (256, 256, 768, 768)))


def _girar(img: np.ndarray) -> np.ndarray:
    """90 graus anti-horario: o olho da direita (o esquerdo do rosto) sobe."""
    return np.ascontiguousarray(np.rot90(img, 1))


def olhos_no_gabarito(recorte: Recorte, modo: str = "separar") -> np.ndarray:
    """O par de olhos no gabarito 1024, como o Adrian escolher (decisao
    builds/recortador-par-de-olhos):

    separar       cada olho do par no seu lugar do jogo, (563,420) e (563,604),
                  na mesma escala e sem girar; olho sozinho vira o par;
    girar         o par inteiro gira 90 graus (fica de pe) e encaixa na caixa
                  dos olhos; olho sozinho gira e vira o par;
    vista-de-cima nao mexe: encaixa como veio, na caixa dos olhos.
    """
    if modo not in MODOS_OLHOS:
        raise ValueError("modo de olhos desconhecido")
    if modo == "vista-de-cima":
        return no_gabarito(recorte.imagem, "olhos")
    if modo == "girar" and recorte.olhos:
        par = _girar(recorte.imagem) if recorte.orientacao == "lado" else recorte.imagem
        return no_gabarito(par, "olhos")
    if recorte.olhos and all(o is not None for o in recorte.olhos):
        cima, baixo = recorte.olhos
    else:
        cima = baixo = _justo(recorte.imagem)
        if cima is None:
            return np.zeros((1024, 1024, 4), np.uint8)
        if modo == "girar":
            cima = baixo = _girar(cima)
    escala = min(OLHO_LADO / max(cima.shape[:2]), OLHO_LADO / max(baixo.shape[:2]))
    tela = np.zeros((1024, 1024, 4), np.uint8)
    _colar(tela, _redimensionar(cima, escala), *OLHO_CIMA)
    _colar(tela, _redimensionar(baixo, escala), *OLHO_BAIXO)
    return tela


def encaixar(recorte: Recorte, parte: str, *, grupo: str = "lutador",
             tamanho=(1024, 1024), olhos: str = "separar") -> np.ndarray:
    """O recorte pronto para o DESTINO: na zona da peca do lutador
    (CONTRATO 2.3) ou, nas outras pecas, no quadro inteiro do slot."""
    if grupo == "lutador":
        if str(parte) == "olhos":
            return olhos_no_gabarito(recorte, olhos)
        return no_gabarito(recorte.imagem, parte)
    largura, altura = int(tamanho[0]), int(tamanho[1])
    return no_quadro(recorte.imagem, (0, 0, largura, altura), (largura, altura))


__all__ = ["FUNDOS", "JUNCAO", "MODOS_OLHOS", "NIVEIS", "Recorte", "Resultado", "detectar_fundo",
           "encaixar", "no_gabarito", "no_quadro", "olhos_no_gabarito", "recortar"]
