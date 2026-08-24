"""Som da roleta: um estalo cada vez que o ponteiro passa por uma fatia.

E isso que faz uma roleta soar como roleta — nao um efeito solto por cima. Os
estalos saem da MESMA curva de desaceleracao que gira a imagem, entao eles
rareiam junto com ela por construcao, sem ninguem ajustar nada a mao.

Sintetizado em vez de tocado de arquivo: o projeto nao tem biblioteca de SFX,
e um estalo e simples o bastante para nascer aqui — ruido curto com queda
exponencial, que e o que um pino batendo numa lingueta produz.
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

# Abaixo deste intervalo os estalos deixam de ser estalos e viram zumbido. Uma
# roleta de verdade tambem satura no comeco; o teto mantem o chiado sem virar
# ruido branco.
INTERVALO_MINIMO = 0.033

# Duracao de um estalo. Curto de proposito: o que da a sensacao de "pino" e o
# ataque, nao a cauda.
DURACAO_TICK = 0.028
DURACAO_CLACK = 0.16


def tempos_de_estalo(angulo_em, duracao_giro: float, segmentos: int,
                     passo: float = 0.002) -> list[float]:
    """Quando o ponteiro cruza cada fatia, dada a curva de giro.

    `angulo_em(t)` e a MESMA funcao que o renderer usa para desenhar. Amostra
    fina (2 ms) porque no inicio o giro cruza varias fatias por quadro — a
    30 fps o video nao mostra isso, mas o ouvido percebe.
    """
    if segmentos <= 0 or duracao_giro <= 0:
        return []
    fatia = 360.0 / segmentos
    tempos: list[float] = []
    cruzadas = -1
    t = 0.0
    while t <= duracao_giro:
        atual = int(angulo_em(t) / fatia)
        if atual > cruzadas:
            if not tempos or (t - tempos[-1]) >= INTERVALO_MINIMO:
                tempos.append(t)
            cruzadas = atual
        t += passo
    return tempos


def _estalo(amostras: int, taxa: int, agudo: float, rng: random.Random) -> list:
    """Ruido com queda exponencial: o barulho de um pino batendo."""
    saida = []
    for i in range(amostras):
        caida = math.exp(-i / (taxa * agudo))
        # ruido + um tom curto dao corpo; so ruido soa a estatica
        valor = (rng.uniform(-1.0, 1.0) * 0.7
                 + math.sin(2 * math.pi * 2100 * i / taxa) * 0.3)
        saida.append(valor * caida)
    return saida


def gravar(destino: Path, duracao: float, tempos: list[float],
           taxa: int = 44100, volume: float = 0.5,
           clack_em: float | None = None, semente: int = 7) -> Path:
    """Trilha com um estalo em cada tempo, e um `clack` mais grave no fim."""
    rng = random.Random(semente)
    total = max(1, int(duracao * taxa))
    trilha = [0.0] * total

    tick = _estalo(int(DURACAO_TICK * taxa), taxa, 0.010, rng)
    clack = _estalo(int(DURACAO_CLACK * taxa), taxa, 0.045, rng)

    for i, quando in enumerate(tempos):
        inicio = int(quando * taxa)
        # os primeiros estalos sao mais fracos: a roda passa rapido demais
        # para cada pino soar inteiro, e sem isso o comeco estoura.
        forca = 0.55 + 0.45 * (i / max(1, len(tempos) - 1))
        for j, amostra in enumerate(tick):
            pos = inicio + j
            if pos < total:
                trilha[pos] += amostra * forca

    if clack_em is not None:
        inicio = int(clack_em * taxa)
        for j, amostra in enumerate(clack):
            pos = inicio + j
            if pos < total:
                trilha[pos] += amostra * 1.3

    pico = max((abs(v) for v in trilha), default=0.0)
    escala = (volume / pico) if pico > 0 else 0.0

    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "wb") as arquivo:
        arquivo.setnchannels(2)
        arquivo.setsampwidth(2)
        arquivo.setframerate(taxa)
        quadros = bytearray()
        for valor in trilha:
            amostra = int(max(-1.0, min(1.0, valor * escala)) * 32767)
            quadros += struct.pack("<hh", amostra, amostra)
        arquivo.writeframes(bytes(quadros))
    return destino
