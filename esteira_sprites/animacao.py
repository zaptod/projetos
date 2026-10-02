"""Validador de ANIMACAO: mede a folha em ciclo antes do juiz e do Adrian.

PEDIDO DO ADRIAN (02/10/2026): "quero animacoes validadas". A IA erra
continuidade entre quadros (decisao `builds/sprites-ia-formato`), e o Grok
olhando uma folha parada nao ve pe deslizando. Entao, para cada item do tipo
folha marcado como ciclo (`animacao.ciclo` no inventario), o portao mede,
CICLO A CICLO (cada ciclo e uma lista de quadros da grade):

  - quadros nao-vazios: o numero certo, nem um a mais nem um a menos;
  - ANCORA: o centro dos pes (centroide da faixa de baixo do alfa) e a
    linha do chao nao podem variar entre os quadros;
  - ESCALA: a altura do alfa nao pode pular entre quadros vizinhos;
  - PALETA: o histograma de cor de cada quadro nao pode fugir do ciclo;
  - LOOP: com `loop`, o ultimo quadro tem de estar tao perto do primeiro
    quanto os vizinhos estao entre si;
  - CONGELADO: trocas de quadro sem mudanca nenhuma, demais;
  - CONTORNO: o contorno escuro do estilo nao pode faltar no perimetro.

Cada reprovacao sai com o NUMERO medido e o limite, que e o que o pedido de
refazer leva de volta ao gerador. Os limites sao de partida: calibrar com as
primeiras folhas de verdade (anotar aqui o que mudou e por que).

Tambem gera a PREVIA (GIF e, se o Pillow souber, WebP) com os ciclos lado a
lado em xadrez -- e ela que vai para o juiz e para a tela de conferir.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, features

from . import prompt

ALFA = 128                 # pixel "do desenho"
AREA_MIN = 50              # menos que isto e quadro vazio (px de alfa)
FAIXA_DOS_PES = 0.12       # a base: os 12% de baixo da altura do desenho
ANCORA_X_MAX = 0.08        # deriva horizontal dos pes, fracao da altura media
ANCORA_Y_MAX = 0.02        # deriva da linha do chao, fracao da altura media
ANCORA_MIN_PX = 2.0        # piso dos dois limites acima, em px
CENTRO_MAX = 0.08          # ancora "centro": deriva do centro de massa
ESCALA_MAX = 0.08          # pulo de altura entre quadros vizinhos (fracao)
PALETA_MAX = 0.25          # distancia de histograma (variacao total, 0..1)
LOOP_FATOR = 2.0           # ultimo->primeiro ate 2x a troca mediana do ciclo
LOOP_MIN = 0.05            # ...e nunca reprova abaixo disto (ciclos calmos)
REPETIDO_MAX = 0.01        # troca de quadro com distancia menor = repetido
CONGELADO_MAX = 0.34       # fracao maxima de trocas repetidas num ciclo
CONTORNO_LUMA = 90         # pixel escuro o bastante para ser contorno
CONTORNO_RAIO = 2          # o contorno pode estar ate 2 px para dentro
CONTORNO_FALTA_MAX = 0.30  # fracao maxima do perimetro sem contorno

LIMITES = {
    "area_min_px": AREA_MIN, "ancora_x": ANCORA_X_MAX, "ancora_y": ANCORA_Y_MAX,
    "ancora_min_px": ANCORA_MIN_PX, "centro": CENTRO_MAX, "escala": ESCALA_MAX,
    "paleta": PALETA_MAX, "loop_fator": LOOP_FATOR, "loop_min": LOOP_MIN,
    "repetido": REPETIDO_MAX, "congelado": CONGELADO_MAX,
    "contorno_luma": CONTORNO_LUMA, "contorno_falta": CONTORNO_FALTA_MAX,
}


# ------------------------------------------------------------------ quadros
def quadros(arr: np.ndarray, colunas: int, linhas: int) -> list[np.ndarray]:
    """Os quadros da grade, da esquerda para a direita, de cima para baixo."""
    h, w = arr.shape[:2]
    ch, cw = h // linhas, w // colunas
    return [arr[j * ch:(j + 1) * ch, i * cw:(i + 1) * cw]
            for j in range(linhas) for i in range(colunas)]


def medir_quadro(q: np.ndarray) -> dict:
    mascara = q[..., 3] >= ALFA
    area = int(mascara.sum())
    if area < AREA_MIN:
        return {"area": area, "vazio": True}
    ys, xs = np.nonzero(mascara)
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    altura = y1 - y0
    faixa = max(1, int(round(altura * FAIXA_DOS_PES)))
    base = ys >= y1 - faixa
    return {"area": area, "vazio": False, "altura": altura,
            "pe_x": float(xs[base].mean()), "chao_y": float(y1),
            "massa_x": float(xs.mean()), "massa_y": float(ys.mean())}


def distancia(a: np.ndarray, b: np.ndarray) -> float:
    """Diferenca media (0..1) em alfa pre-multiplicado, so onde ha desenho."""
    uniao = (a[..., 3] >= 16) | (b[..., 3] >= 16)
    if not uniao.any():
        return 0.0
    pa = a.astype(np.float32)
    pb = b.astype(np.float32)
    pa[..., :3] *= pa[..., 3:4] / 255.0
    pb[..., :3] *= pb[..., 3:4] / 255.0
    return float(np.abs(pa[uniao] - pb[uniao]).mean() / 255.0)


def histograma(q: np.ndarray) -> np.ndarray:
    """Histograma de cor (3 bits por canal = 512 caixas) do que e desenho."""
    mascara = q[..., 3] >= ALFA
    rgb = (q[..., :3][mascara] >> 5).astype(np.int32)
    if not len(rgb):
        return np.zeros(512)
    caixas = np.bincount(rgb[:, 0] * 64 + rgb[:, 1] * 8 + rgb[:, 2], minlength=512)
    return caixas / caixas.sum()


def _dilatar(m: np.ndarray, raio: int) -> np.ndarray:
    h, w = m.shape
    p = np.pad(m, raio)
    saida = np.zeros_like(m)
    for dy in range(-raio, raio + 1):
        for dx in range(-raio, raio + 1):
            saida |= p[raio + dy:raio + dy + h, raio + dx:raio + dx + w]
    return saida


def contorno_falta(q: np.ndarray) -> float:
    """Fracao do perimetro do desenho SEM pixel escuro por perto (0..1)."""
    mascara = q[..., 3] >= ALFA
    if mascara.sum() < AREA_MIN:
        return 0.0
    dentro = ~_dilatar(~mascara, 1)          # erosao de 1 px
    perimetro = mascara & ~dentro
    total = int(perimetro.sum())
    if not total:
        return 0.0
    rgb = q[..., :3].astype(np.float32)
    luma = rgb[..., 0] * .299 + rgb[..., 1] * .587 + rgb[..., 2] * .114
    escuro = mascara & (luma <= CONTORNO_LUMA)
    coberto = perimetro & _dilatar(escuro, CONTORNO_RAIO)
    return round(1.0 - float(coberto.sum()) / total, 3)


def _pares(n: int, laco: bool) -> list[tuple[int, int]]:
    pares = [(i, i + 1) for i in range(n - 1)]
    if laco and n > 2:
        pares.append((n - 1, 0))
    return pares


# ------------------------------------------------------------------ validar
def validar(arr: np.ndarray, item: dict) -> tuple[list[str], dict]:
    """(erros, medidas) da folha em ciclo. Sem animacao no item: ([], {})."""
    anim = prompt.animacao(item)
    if anim is None:
        return [], {}
    colunas, linhas = prompt.grade(item)
    h, w = arr.shape[:2]
    if w % colunas or h % linhas:
        return [f"folha {w}x{h} nao divide na grade {colunas}x{linhas}"], {}
    todos = quadros(arr, colunas, linhas)
    medidas_q = [medir_quadro(q) for q in todos]
    esperados = sorted({int(i) for c in anim["ciclos"] for i in c.get("quadros", [])})
    nao_vazios = sum(not m["vazio"] for m in medidas_q)
    erros: list[str] = []
    valores: dict = {"quadros_nao_vazios": nao_vazios, "esperados": len(esperados),
                     "ciclos": {}, "limites": dict(LIMITES)}
    if nao_vazios != len(esperados) or any(medidas_q[i]["vazio"] for i in esperados
                                           if i < len(medidas_q)):
        erros.append(f"animacao com {nao_vazios} quadros nao-vazios (esperados {len(esperados)})")
    ancora = anim.get("ancora", "pes")
    pior_contorno = (0.0, -1)
    for ciclo in anim["ciclos"]:
        nome = ciclo.get("nome", "?")
        indices = [int(i) for i in ciclo.get("quadros", []) if int(i) < len(todos)]
        cheios = [i for i in indices if not medidas_q[i]["vazio"]]
        if len(cheios) < 2:
            continue
        ms = [medidas_q[i] for i in cheios]
        qs = [todos[i] for i in cheios]
        laco = bool(ciclo.get("loop"))
        altura_media = float(np.mean([m["altura"] for m in ms]))
        v: dict = {"quadros": len(cheios), "altura_media_px": round(altura_media, 1)}
        # ANCORA
        if ancora in ("pes", "base"):
            pe_x = [m["pe_x"] for m in ms]
            chao = [m["chao_y"] for m in ms]
            v["deriva_pes_px"] = round(max(pe_x) - min(pe_x), 1)
            v["deriva_chao_px"] = round(max(chao) - min(chao), 1)
            lim_x = max(ANCORA_MIN_PX, ANCORA_X_MAX * altura_media)
            lim_y = max(ANCORA_MIN_PX, ANCORA_Y_MAX * altura_media)
            if v["deriva_pes_px"] > lim_x:
                erros.append(f"{nome}: os pes derivam {v['deriva_pes_px']:.1f} px na horizontal (limite {lim_x:.1f})")
            if v["deriva_chao_px"] > lim_y:
                erros.append(f"{nome}: a linha do chao varia {v['deriva_chao_px']:.1f} px (limite {lim_y:.1f})")
        elif ancora == "centro":
            cx = [m["massa_x"] for m in ms]
            cy = [m["massa_y"] for m in ms]
            v["deriva_centro_px"] = round(max(max(cx) - min(cx), max(cy) - min(cy)), 1)
            lim = max(ANCORA_MIN_PX, CENTRO_MAX * altura_media)
            if v["deriva_centro_px"] > lim:
                erros.append(f"{nome}: o centro deriva {v['deriva_centro_px']:.1f} px (limite {lim:.1f})")
        pares = _pares(len(cheios), laco)
        # ESCALA
        if anim.get("escala", True):
            pulos = [abs(ms[a]["altura"] - ms[b]["altura"]) / max(ms[a]["altura"], ms[b]["altura"])
                     for a, b in pares]
            v["pulo_de_escala"] = round(max(pulos), 3) if pulos else 0.0
            if v["pulo_de_escala"] > ESCALA_MAX:
                erros.append(f"{nome}: a altura pula {v['pulo_de_escala'] * 100:.0f}% entre quadros vizinhos "
                             f"(limite {ESCALA_MAX * 100:.0f}%)")
        # PALETA
        hists = [histograma(q) for q in qs]
        media = np.mean(hists, axis=0)
        fugas = [0.5 * float(np.abs(hh - media).sum()) for hh in hists]
        v["paleta_desvio"] = round(max(fugas), 3)
        if v["paleta_desvio"] > PALETA_MAX:
            pior = cheios[int(np.argmax(fugas))] + 1
            erros.append(f"{nome}: a paleta do quadro {pior} diverge {v['paleta_desvio']:.2f} do ciclo "
                         f"(limite {PALETA_MAX:.2f})")
        # CONGELADO e LOOP
        trocas = [distancia(qs[a], qs[b]) for a, b in _pares(len(cheios), False)]
        todas = trocas + ([distancia(qs[-1], qs[0])] if laco and len(cheios) > 2 else [])
        repetidas = sum(d < REPETIDO_MAX for d in todas)
        v["trocas_repetidas"] = repetidas
        v["trocas"] = len(todas)
        if todas and repetidas / len(todas) > CONGELADO_MAX:
            erros.append(f"{nome}: {repetidas} de {len(todas)} trocas de quadro sem mudanca (congelado; "
                         f"limite {CONGELADO_MAX * 100:.0f}%)")
        if laco and len(cheios) > 2 and trocas:
            mediana = float(np.median(trocas))
            volta = distancia(qs[-1], qs[0])
            lim = max(LOOP_FATOR * mediana, LOOP_MIN)
            v["loop_volta"] = round(volta, 4)
            v["troca_mediana"] = round(mediana, 4)
            if volta > lim:
                erros.append(f"{nome}: o loop quebra -- ultimo->primeiro {volta:.3f} contra {mediana:.3f} "
                             f"entre vizinhos (limite {lim:.3f})")
        # CONTORNO
        faltas = [contorno_falta(q) for q in qs]
        v["contorno_falta"] = max(faltas)
        if max(faltas) > pior_contorno[0]:
            pior_contorno = (max(faltas), cheios[int(np.argmax(faltas))] + 1)
        valores["ciclos"][nome] = v
    valores["contorno_falta_max"] = pior_contorno[0]
    if pior_contorno[0] > CONTORNO_FALTA_MAX:
        erros.append(f"contorno escuro falta em {pior_contorno[0] * 100:.0f}% do perimetro do quadro "
                     f"{pior_contorno[1]} (limite {CONTORNO_FALTA_MAX * 100:.0f}%)")
    return erros, valores


# ------------------------------------------------------------------- previa
def _xadrez(largura: int, altura: int, lado: int = 8) -> Image.Image:
    fundo = Image.new("RGBA", (largura, altura), "#B0B0B0")
    d = ImageDraw.Draw(fundo)
    for y in range(0, altura, lado):
        for x in range(0, largura, lado):
            if (x // lado + y // lado) % 2:
                d.rectangle((x, y, x + lado - 1, y + lado - 1), fill="#D8D8D8")
    return fundo


def previa(arr: np.ndarray, item: dict, destino: str | Path, altura: int = 160) -> dict:
    """GIF (e WebP, se houver suporte) com os ciclos lado a lado, em laco.

    `destino` sem extensao. O fps e o do primeiro ciclo; ciclos de tamanhos
    diferentes repetem do comeco quando acabam.
    """
    anim = prompt.animacao(item)
    if anim is None:
        return {}
    colunas, linhas = prompt.grade(item)
    todos = quadros(arr, colunas, linhas)
    ciclos = [c for c in anim["ciclos"] if c.get("quadros")]
    if not ciclos or not todos:
        return {}
    ch, cw = todos[0].shape[:2]
    escala = altura / max(1, ch)
    largura = max(1, int(round(cw * escala)))
    n = max(len(c["quadros"]) for c in ciclos)
    imagens = []
    for t in range(n):
        tela = _xadrez(largura * len(ciclos), altura)
        for j, ciclo in enumerate(ciclos):
            indice = int(ciclo["quadros"][t % len(ciclo["quadros"])])
            if indice >= len(todos):
                continue
            q = Image.fromarray(np.ascontiguousarray(todos[indice]), "RGBA").resize(
                (largura, altura), Image.LANCZOS)
            tela.alpha_composite(q, (j * largura, 0))
        imagens.append(tela)
    fps = float(ciclos[0].get("fps") or 8)
    duracao = max(20, int(round(1000 / fps)))
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    gif = destino.with_suffix(".gif")
    rgb = [im.convert("RGB") for im in imagens]
    rgb[0].save(gif, save_all=True, append_images=rgb[1:], duration=duracao, loop=0)
    saida = {"gif": str(gif), "webp": ""}
    if features.check_module("webp"):
        webp = destino.with_suffix(".webp")
        imagens[0].save(webp, save_all=True, append_images=imagens[1:], duration=duracao,
                        loop=0, lossless=True)
        saida["webp"] = str(webp)
    return saida
