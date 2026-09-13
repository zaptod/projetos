# -*- coding: utf-8 -*-
"""A imagem e UMA cena, ou virou colagem de varias?

O QUE ACONTECEU (11/09/2026). O prompt negativo diz, em toda cena, "no
collage, no split screen" — e o modelo ignora. Varridas as 440 imagens do
disco, 48 eram colagem: painel de cima e de baixo, grade 2x2, tela dividida
ao meio com duas pessoas diferentes em cada lado. Uma delas abria a parte 3
da `historia_00005`, publicada no YouTube e no TikTok.

Num video vertical isso e pior do que parece: cada painel fica com menos de
metade da altura, o rosto encolhe, e a cena seguinte volta a ser inteira —
entao a historia pisca entre dois formatos. Foi literalmente a frase dele,
"as imagens estao desconexas".

O SINAL, e por que este e nao outro. A primeira tentativa foi medir a
descontinuidade entre linhas vizinhas: nao separa nada. Uma colagem de dois
paineis marcou 7,3 e uma foto boa marcou 8,4, porque foto de interior e cheia
de borda horizontal forte (batente, mesa, horizonte). A segunda tentativa
mediu a fracao de COLUNAS que saltam na mesma linha: tambem nao separa — o
caixilho de uma janela atravessa a imagem inteira.

O que separa e a CALHA: a faixa fina e uniforme que o gerador desenha ENTRE
os paineis. Ela tem tres propriedades ao mesmo tempo, e nenhuma cena real tem
as tres: e fina (1 a 6 px na escala reduzida), e quase sem variacao ao longo
de toda a travessia, e destoa em brilho dos dois lados. Medido nas 440: pega
as colagens obvias e nao acusa nenhuma das fotos boas.

DELIBERADAMENTE CONSERVADOR. Um falso positivo manda refazer uma imagem boa,
e refazer custa uma ida ao PicassoIA numa conta COMPARTILHADA. Entao a calha
so conta no MIOLO (15% a 85%): perto da borda ela quase sempre e uma
divisoria de vidro ou um batente, e o "painel" que ela criaria teria 6% da
tela — o que nao e colagem, e moldura.

O preco dessa escolha e nao pegar a colagem sem calha, em que os dois paineis
se encostam. Ela existe e passa. Preferir errar para o lado de deixar passar
e a decisao certa aqui: o outro lado gasta a conta de todo mundo.
"""
from __future__ import annotations

from pathlib import Path

# Escala de trabalho. Reduzir antes de medir nao e so velocidade: em 1088x1920
# o ruido de filme faz o desvio da linha subir e a calha some no meio dele.
LARGURA, ALTURA = 192, 341

# Faixa mais grossa que isto ja e um elemento da cena (uma parede, uma mesa).
CALHA_MAXIMA = 6
# Quao "lisa" a faixa tem que ser ao longo da travessia inteira.
DESVIO_MAXIMO = 12.0
# Quanto ela tem que destoar do que esta dos dois lados.
SALTO_MINIMO = 18.0
# So o miolo. Perto da borda, calha e moldura, nao divisao.
MIOLO = (0.15, 0.85)


def _faixas(cinza, eixo: str) -> list[dict]:
    g = cinza if eixo == "linha" else cinza.T
    total = g.shape[0]
    desvio = g.std(axis=1)
    media = g.mean(axis=1)
    comeco, fim = int(total * MIOLO[0]), int(total * MIOLO[1])

    achadas, i = [], comeco
    while i < fim:
        if desvio[i] >= DESVIO_MAXIMO:
            i += 1
            continue
        j = i
        while j + 1 < fim and desvio[j + 1] < DESVIO_MAXIMO:
            j += 1
        largura = j - i + 1
        if largura <= CALHA_MAXIMA:
            antes = media[max(0, i - 5)]
            depois = media[min(total - 1, j + 5)]
            centro = float(media[i:j + 1].mean())
            salto = min(abs(centro - antes), abs(centro - depois))
            if salto > SALTO_MINIMO:
                achadas.append({"eixo": eixo, "onde": round(i / total, 2),
                                "largura": int(largura),
                                "salto": round(float(salto), 1)})
        i = j + 1
    return achadas


def calhas(caminho) -> list[dict]:
    """As calhas encontradas. Lista vazia = a imagem e uma cena so."""
    try:
        import numpy as np
        from PIL import Image
        with Image.open(caminho) as imagem:
            reduzida = imagem.convert("L").resize((LARGURA, ALTURA),
                                                  Image.BILINEAR)
        cinza = np.asarray(reduzida, dtype=np.float32)
    except Exception:                                          # noqa: BLE001
        # Ilegivel nao e problema desta funcao: `fila.utilizavel` ja recusa
        # por tamanho, e recusar aqui esconderia a causa real.
        return []
    return _faixas(cinza, "linha") + _faixas(cinza, "coluna")


def e_colagem(caminho) -> bool:
    return bool(calhas(Path(caminho)))


def motivo(caminho) -> str:
    """Uma frase para o log e para a vistoria, ou `""`."""
    achadas = calhas(caminho)
    if not achadas:
        return ""
    onde = ", ".join(f"{c['eixo']} em {c['onde'] * 100:.0f}%"
                     for c in achadas[:3])
    return (f"parece colagem: {len(achadas)} calha(s) atravessando a imagem "
            f"({onde}). O prompt pede uma cena so.")


__all__ = ["calhas", "e_colagem", "motivo", "CALHA_MAXIMA", "MIOLO"]
