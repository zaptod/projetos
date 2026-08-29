"""Trilha e efeitos sonoros SINTETIZADOS — sem biblioteca de audio, sem custo.

O video saia praticamente mudo: `assets/music/` e `assets/sfx/` vazios e a
roleta com um estalo baixo. Em vertical, som e o que segura os primeiros
segundos, entao tudo aqui nasce por sintese (numpy), deterministico por
seed, e vira arquivo uma vez:

    trilha      loop escuro em tom menor (bumbo, caixa, chimbal, 808, pad,
                arpejo) — `garantir_trilha` grava em assets/music/ se a
                pasta estiver vazia; o catalogo passa a acha-la sozinho.
    efeitos     riser (gancho), hit (stinger/final), chime (resultado bom),
                womp (resultado ruim), bass hit (insano), whoosh
                (revelacao), rufar (nota final).

`sfx_do_evento` traduz um evento do plano em camadas (instante, amostras,
ganho) que `roleta_som.gravar` mistura com os estalos da roda — som e
imagem leem da MESMA curva de giro, entao nada aqui adivinha tempo.

Sem numpy instalado tudo devolve None/[] e o video sai como antes (so com
os estalos): a trilha e melhoria, nunca dependencia.
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

try:
    import numpy as np
except ImportError:  # pragma: no cover - ambiente sem numpy
    np = None

TAXA = 44100
NOME_TRILHA = "trilha_roleta.wav"


def disponivel() -> bool:
    return np is not None


# ------------------------------------------------------------------ blocos
def _t(dur: float, taxa: int):
    return np.arange(int(dur * taxa)) / taxa


def _env_exp(n: int, taxa: int, tau: float):
    return np.exp(-np.arange(n) / (taxa * tau))


def _norm(x, pico: float = 1.0):
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    return x * (pico / m) if m > 1e-9 else x


def _lowpass(x, taxa: int, corte: float):
    """One-pole: suficiente para tirar a aspereza de saw/ruido."""
    a = math.exp(-2 * math.pi * corte / taxa)
    y = np.empty_like(x)
    acc = 0.0
    b = 1 - a
    for i in range(len(x)):
        acc = b * x[i] + a * acc
        y[i] = acc
    return y


def _lowpass_rapido(x, taxa: int, corte: float):
    """Mesmo filtro em blocos (para trilha longa): usa lfilter-like via
    recorrencia vetorizada em pedacos — bom o bastante para pad/808."""
    a = math.exp(-2 * math.pi * corte / taxa)
    b = 1 - a
    y = np.zeros_like(x)
    acc = 0.0
    # a recorrencia e sequencial por natureza; loop em Python sobre 1 M de
    # amostras custa ~0.5 s, aceitavel para algo que roda UMA vez.
    for i in range(len(x)):
        acc = b * x[i] + a * acc
        y[i] = acc
    return y


def kick(taxa: int = TAXA, dur: float = 0.38):
    t = _t(dur, taxa)
    freq = 45 + 140 * np.exp(-t * 28)
    fase = np.cumsum(2 * np.pi * freq / taxa)
    corpo = np.sin(fase) * np.exp(-t * 7)
    clique = np.random.default_rng(1).uniform(-1, 1, len(t)) * np.exp(-t * 180) * 0.6
    return _norm(corpo + clique, 0.95)


def snare(taxa: int = TAXA, dur: float = 0.22, rng=None):
    rng = rng or np.random.default_rng(2)
    t = _t(dur, taxa)
    ruido = rng.uniform(-1, 1, len(t)) * np.exp(-t * 22)
    corpo = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 30) * 0.7
    return _norm(ruido + corpo, 0.9)


def hat(taxa: int = TAXA, dur: float = 0.05, aberto: bool = False, rng=None):
    rng = rng or np.random.default_rng(3)
    d = 0.18 if aberto else dur
    t = _t(d, taxa)
    ruido = rng.uniform(-1, 1, len(t))
    ruido = np.diff(ruido, prepend=0.0)          # highpass tosco
    return _norm(ruido * np.exp(-t * (18 if aberto else 70)), 0.6)


def bass808(freq: float, dur: float, taxa: int = TAXA):
    t = _t(dur, taxa)
    glide = freq * (1 + 0.6 * np.exp(-t * 40))
    fase = np.cumsum(2 * np.pi * glide / taxa)
    x = np.sin(fase) * np.exp(-t * 2.2)
    return np.tanh(x * 2.2) * 0.9


def saw(freq: float, n: int, taxa: int = TAXA, fase0: float = 0.0):
    t = np.arange(n) / taxa
    return 2 * ((t * freq + fase0) % 1.0) - 1


def pad(freq: float, dur: float, taxa: int = TAXA):
    n = int(dur * taxa)
    x = (saw(freq, n, taxa) + saw(freq * 1.005, n, taxa, 0.3)
         + saw(freq * 0.995, n, taxa, 0.6) + 0.5 * saw(freq * 2.0, n, taxa, 0.1))
    x = _lowpass_rapido(x, taxa, 900)
    env = np.minimum(1.0, np.arange(n) / (taxa * 0.25)) * np.minimum(
        1.0, (n - np.arange(n)) / (taxa * 0.3))
    return _norm(x * env, 0.5)


def pluck(freq: float, dur: float, taxa: int = TAXA):
    t = _t(dur, taxa)
    x = (np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * freq * 2 * t)
         + 0.2 * np.sin(2 * np.pi * freq * 3 * t))
    return _norm(x * np.exp(-t * 9), 0.6)


# ------------------------------------------------------------------- trilha
NOTAS = {"A1": 55.0, "C2": 65.41, "D2": 73.42, "E2": 82.41, "F2": 87.31,
         "G2": 98.0, "A2": 110.0, "A3": 220.0, "C4": 261.63, "D4": 293.66,
         "E4": 329.63, "F4": 349.23, "G4": 392.0, "A4": 440.0, "C5": 523.25,
         "E5": 659.25}

# Am - F - Dm - E: menor, escuro, com a dominante puxando de volta.
PROGRESSAO = [("A1", ("A3", "C4", "E4"), ("A4", "C5", "E5", "C5")),
              ("F2", ("F4", "A3", "C4"), ("A4", "C5", "F4", "C5")),
              ("D2", ("D4", "F4", "A3"), ("A4", "D4", "F4", "D4")),
              ("E2", ("E4", "G4", "A3"), ("G4", "E5", "G4", "E4"))]


def trilha(seed: int = 7, bpm: float = 142.0, compassos: int = 16,
           taxa: int = TAXA):
    """Loop estereo (float32, -1..1) de `compassos` compassos em 4/4.

    Metade A (so base) e metade B (com arpejo): o loop respira e nao soa
    igual a cada 7 s. Termina limpo para o `-stream_loop` do ffmpeg emendar.
    """
    rng = np.random.default_rng(seed)
    batida = 60.0 / bpm
    compasso = batida * 4
    total = int(compassos * compasso * taxa)
    esq = np.zeros(total)
    dir_ = np.zeros(total)

    def por(x, quando: float, ganho: float = 1.0, pan: float = 0.0):
        ini = int(quando * taxa)
        fim = min(total, ini + len(x))
        if fim <= ini:
            return
        seg = x[:fim - ini] * ganho
        esq[ini:fim] += seg * (1 - max(0.0, pan))
        dir_[ini:fim] += seg * (1 + min(0.0, pan))

    k, s = kick(taxa), snare(taxa, rng=rng)
    hf, ha = hat(taxa, rng=rng), hat(taxa, aberto=True, rng=rng)
    for c in range(compassos):
        t0 = c * compasso
        raiz, acorde, arpejo = PROGRESSAO[c % len(PROGRESSAO)]
        # bateria (trap): bumbo no 1 e no "e" do 2, caixa no 2 e no 4
        for b in (0.0, 1.5, 2.75):
            por(k, t0 + b * batida, 0.95)
        for b in (1.0, 3.0):
            por(s, t0 + b * batida, 0.8)
        # chimbal em colcheias com rolos de semicolcheia sorteados
        for i in range(8):
            por(hf, t0 + i * batida / 2, 0.35 + 0.15 * (i % 2 == 0), pan=0.25)
            if rng.random() < 0.18:
                for j in range(1, 4):
                    por(hf, t0 + i * batida / 2 + j * batida / 8, 0.22, pan=0.25)
        por(ha, t0 + 3.5 * batida, 0.3, pan=-0.2)
        # 808 seguindo a raiz, com nota de passagem no fim do compasso
        por(bass808(NOTAS[raiz], batida * 2.4, taxa), t0, 0.9)
        por(bass808(NOTAS[raiz], batida * 1.2, taxa), t0 + batida * 2.75, 0.75)
        # pad: sempre presente, mais baixo na metade A
        ganho_pad = 0.22 if c < compassos // 2 else 0.3
        for nota in acorde:
            por(pad(NOTAS[nota], compasso, taxa), t0, ganho_pad / len(acorde), pan=0.1)
        # arpejo so na metade B
        if c >= compassos // 2:
            for i, nota in enumerate(arpejo * 2):
                por(pluck(NOTAS[nota], batida * 0.9, taxa), t0 + i * batida / 2,
                    0.28, pan=-0.3 if i % 2 else 0.3)

    st = np.stack([esq, dir_], axis=1)
    st = _norm(st, 0.9)
    # nivel de fundo estavel: RMS alvo ~ -17 dBFS
    rms = float(np.sqrt(np.mean(st ** 2)))
    alvo = 10 ** (-17 / 20)
    if rms > 1e-6:
        st = np.clip(st * (alvo / rms), -0.98, 0.98)
    return st.astype(np.float32)


def gravar_wav(destino: Path, amostras, taxa: int = TAXA) -> Path:
    """Mono (n,) ou estereo (n,2) float -> WAV 16-bit estereo."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    x = np.asarray(amostras, dtype=np.float64)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    inteiro = (np.clip(x, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(destino), "wb") as arquivo:
        arquivo.setnchannels(2)
        arquivo.setsampwidth(2)
        arquivo.setframerate(taxa)
        arquivo.writeframes(inteiro.tobytes())
    return destino


def garantir_trilha(pasta_music: Path, seed: int = 7, nome: str = NOME_TRILHA,
                    regerar: bool = False) -> Path | None:
    """Cria a trilha padrao em assets/music/ se nao houver NENHUMA musica la.

    Uma musica que o usuario colocou a mao sempre vence: a sintetizada so
    entra numa pasta vazia (ou com --regerar).
    """
    if np is None:
        return None
    pasta = Path(pasta_music)
    pasta.mkdir(parents=True, exist_ok=True)
    existentes = [p for p in pasta.iterdir()
                  if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".m4a", ".flac")]
    destino = pasta / nome
    if existentes and not (regerar and destino in existentes):
        return existentes[0] if destino not in existentes else destino
    if destino.exists() and not regerar:
        return destino
    return gravar_wav(destino, trilha(seed=seed))


# ------------------------------------------------------------------ efeitos
def sfx_riser(dur: float = 1.5, taxa: int = TAXA):
    """Sobe e para: o gancho pede que algo VAI acontecer."""
    t = _t(dur, taxa)
    rng = np.random.default_rng(11)
    ruido = rng.uniform(-1, 1, len(t))
    ruido = _lowpass(ruido, taxa, 400) * 4
    tom = np.sin(np.cumsum(2 * np.pi * (180 + 900 * (t / dur) ** 2) / taxa))
    env = (t / dur) ** 1.6
    return _norm((ruido * 0.7 + tom * 0.5) * env, 0.85)


def sfx_hit(taxa: int = TAXA):
    """Impacto seco: stinger, corte, nota final."""
    k = kick(taxa, 0.5)
    t = _t(0.5, taxa)
    ruido = np.random.default_rng(12).uniform(-1, 1, len(t)) * np.exp(-t * 14) * 0.5
    sub = np.sin(2 * np.pi * 52 * t) * np.exp(-t * 4) * 0.8
    return _norm(k + ruido + sub, 0.95)


def sfx_bass_hit(taxa: int = TAXA):
    """Grave que desce e distorce: o resultado INSANO."""
    t = _t(0.8, taxa)
    freq = 38 + 90 * np.exp(-t * 12)
    x = np.sin(np.cumsum(2 * np.pi * freq / taxa)) * np.exp(-t * 2.5)
    return _norm(np.tanh(x * 3.5), 0.98)


def sfx_chime(taxa: int = TAXA, forte: bool = False):
    """Arpejo curto subindo: resultado bom (GOOD/GREAT)."""
    notas = ("C5", "E5", "A4", "C5") if forte else ("A4", "C5")
    passo = 0.07
    dur = passo * len(notas) + 0.45
    saida = np.zeros(int(dur * taxa))
    for i, nota in enumerate(notas):
        x = pluck(NOTAS[nota] * (2 if forte else 1.5), 0.45, taxa)
        ini = int(i * passo * taxa)
        saida[ini:ini + len(x)] += x
    return _norm(saida, 0.7)


def sfx_womp(taxa: int = TAXA):
    """Desce e murcha: resultado ruim (BAD/TERRIBLE)."""
    t = _t(0.65, taxa)
    freq = 240 * np.exp(-t * 2.4) + 70
    vib = 1 + 0.04 * np.sin(2 * np.pi * 7 * t)
    x = np.sin(np.cumsum(2 * np.pi * freq * vib / taxa))
    x = x + 0.4 * np.sin(np.cumsum(2 * np.pi * freq * 0.5 / taxa))
    return _norm(x * np.exp(-t * 3.2), 0.75)


def sfx_click(taxa: int = TAXA):
    """Confirmacao neutra, discreta (AVERAGE/WEAK)."""
    t = _t(0.12, taxa)
    x = np.sin(2 * np.pi * 1400 * t) * np.exp(-t * 60)
    return _norm(x, 0.45)


def sfx_whoosh(dur: float = 0.45, taxa: int = TAXA):
    t = _t(dur, taxa)
    rng = np.random.default_rng(13)
    ruido = rng.uniform(-1, 1, len(t))
    ruido = _lowpass(ruido, taxa, 1200) * 3
    env = np.sin(np.pi * t / dur) ** 1.5
    return _norm(ruido * env, 0.55)


def sfx_rufar(dur: float = 0.55, taxa: int = TAXA):
    saida = np.zeros(int((dur + 0.1) * taxa))
    h = hat(taxa)
    passo = 0.045
    n = int(dur / passo)
    for i in range(n):
        ini = int(i * passo * taxa)
        saida[ini:ini + len(h)] += h * (0.4 + 0.6 * i / max(1, n - 1))
    return _norm(saida, 0.6)


def sfx_do_evento(event: dict, taxa: int = TAXA) -> list[tuple[float, list, float]]:
    """Camadas (instante, amostras, ganho) para um evento do plano.

    Roleta: o som do RESULTADO no instante em que a roda para
    (`spin_duration`), escolhido pelos `effects` que a direcao ja atribuiu
    por tier — `bass_hit` e insano, `sad_sfx` e ruim, `glow` e bom. Quem
    nao tem marca ganha um clique neutro, para nenhum resultado cair no
    silencio.
    """
    if np is None:
        return []
    tipo = event.get("type")
    efeitos = set(event.get("effects") or [])
    if tipo == "roulette":
        quando = float(event.get("spin_duration") or 0.0)
        if "bass_hit" in efeitos:
            return [(quando, sfx_bass_hit(taxa).tolist(), 1.0),
                    (quando + 0.05, sfx_chime(taxa, forte=True).tolist(), 0.7)]
        if "sad_sfx" in efeitos:
            return [(quando, sfx_womp(taxa).tolist(), 0.8)]
        if "glow" in efeitos or "punch_zoom" in efeitos:
            return [(quando, sfx_chime(taxa, forte=True).tolist(), 0.8)]
        if "glow_soft" in efeitos:
            return [(quando, sfx_chime(taxa).tolist(), 0.7)]
        return [(quando, sfx_click(taxa).tolist(), 0.6)]
    if tipo == "hook":
        dur = float(event.get("duration") or 1.6)
        return [(0.0, sfx_riser(max(0.6, dur - 0.1), taxa).tolist(), 0.8),
                (max(0.0, dur - 0.12), sfx_hit(taxa).tolist(), 0.9)]
    if tipo == "stinger":
        return [(0.0, sfx_hit(taxa).tolist(), 0.9)]
    if tipo == "final":
        return [(0.0, sfx_rufar(0.5, taxa).tolist(), 0.7),
                (0.5, sfx_hit(taxa).tolist(), 0.9)]
    if tipo in ("identity", "nameplate", "comentario"):
        return [(0.0, sfx_whoosh(0.45, taxa).tolist(), 0.7)]
    if tipo == "synergy":
        return [(0.0, sfx_chime(taxa).tolist(), 0.6)]
    return []


def gravar_mono(destino: Path, duracao: float, camadas, taxa: int = TAXA,
                volume: float = 0.9) -> Path | None:
    """Trilha de um evento SEM roleta: so as camadas de efeito."""
    if np is None or not camadas:
        return None
    total = max(1, int(duracao * taxa))
    buf = np.zeros(total)
    for quando, amostras, ganho in camadas:
        ini = int(quando * taxa)
        seg = np.asarray(amostras)[:max(0, total - ini)]
        if len(seg):
            buf[ini:ini + len(seg)] += seg * ganho
    buf = np.clip(_norm(buf, volume), -1, 1)
    return gravar_wav(destino, buf, taxa)


def _pack16(x) -> bytes:  # pragma: no cover - utilitario
    return b"".join(struct.pack("<h", int(v * 32767)) for v in x)
