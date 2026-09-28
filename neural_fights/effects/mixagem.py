"""Mistura OFFLINE dos sons que o gravador anotou (Onda 16A).

O ``AnotadorDeAudio`` (``effects/audio_anotador.py``) devolve a lista ``sons``
— cada pedido de som do jogo com instante, chave, volume e pitch. Aqui essa
lista vira audio de verdade, com os arquivos que o jogo tocaria:

- o arquivo sai da CHAVE na hora da mistura, pela mesma cadeia do jogo
  (``sound_config.json`` do runtime > pacote > ``SOUND_FALLBACKS``). Trocar um
  wav vale para o proximo render, sem regravar a luta;
- o volume e o que o jogo aplicaria (a categoria "ambiente" em 0,03 no
  ``sound_config.json`` do Adrian continua quase calada, como ao vivo);
- o pitch muda a velocidade de leitura (como uma fita), que e o que um motor
  de jogo faz para variar um golpe repetido.

A soma de dezenas de golpes passa de 1,0 com facilidade. Dois passos seguram
isso, POR TRECHO (a trilha de cada luta e normalizada sozinha):

1. nivel: a media de energia dos momentos ativos vai para ``alvo_db``;
2. limitador com antecipacao de um bloco: nenhum pico passa de ``teto``.

Sem numpy nada aqui funciona e as funcoes devolvem ``None``: o som real e
melhoria, nunca dependencia (a mesma doutrina da trilha sintetizada).
"""
from __future__ import annotations

import math
import subprocess
import wave
from pathlib import Path

try:
    import numpy as np
except ImportError:  # pragma: no cover - ambiente sem numpy
    np = None

TAXA = 44100
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Nivel dos momentos ativos da luta, em dBFS de energia (media quadratica das
# janelas de 50 ms acima do portao). Calibrado em 28/09/2026 contra o trecho
# de luta do som sintetizado que o video ja tinha (duelo_00016: -18,3 LUFS; com
# os sons reais da mesma luta, -17 dava -21,4 LUFS e -13 da -18,1): o som real
# entra no mesmo volume percebido, e a musica e a voz nao mudam de lugar.
ALVO_DB = -13.0
# Teto do limitador (-2,5 dBFS). A mixagem final ainda passa por alimiter e
# loudnorm; aqui e so para a soma nunca estourar antes disso. Nao e -1 dBFS
# porque o trecho vira aac antes da mixagem final, e o aac passa do pico da
# fonte: medido em 28/09/2026, o wav limitado em -1,0 dBFS saiu do aac com 289
# amostras em 0 dB.
TETO = 0.75
# Janela do medidor de nivel e o portao relativo: janela mais de 40 dB abaixo
# da mais forte e silencio entre golpes, nao "momento ativo".
JANELA_NIVEL_S = 0.05
PORTAO_RELATIVO_DB = 40.0

_CACHE: dict[tuple, "np.ndarray"] = {}


def disponivel() -> bool:
    return np is not None


def decodificar(caminho: Path, taxa: int = TAXA):
    """Arquivo de som -> matriz (n, 2) float32 em -1..1, ou None.

    ffmpeg e nao ``wave``/pygame: le mp3, wav de qualquer profundidade e ogg,
    ja reamostrado para a taxa do video. Decodificado uma vez por processo
    (cache por caminho + data de modificacao: o wav trocado e relido).
    """
    if np is None:
        return None
    caminho = Path(caminho)
    try:
        chave = (str(caminho), caminho.stat().st_mtime_ns, int(taxa))
    except OSError:
        return None
    if chave in _CACHE:
        return _CACHE[chave]
    try:
        saida = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(caminho), "-f", "f32le",
             "-acodec", "pcm_f32le", "-ac", "2", "-ar", str(int(taxa)), "pipe:1"],
            capture_output=True, timeout=60, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    if saida.returncode != 0 or not saida.stdout:
        return None
    amostras = np.frombuffer(saida.stdout, dtype="<f4")
    amostras = amostras[: len(amostras) // 2 * 2].reshape(-1, 2).astype(np.float32)
    _CACHE[chave] = amostras
    return amostras


def com_pitch(amostras, pitch: float):
    """Le o som mais rapido (pitch > 1) ou mais devagar, como uma fita."""
    if np is None or amostras is None or len(amostras) < 2:
        return amostras
    pitch = float(pitch or 1.0)
    if abs(pitch - 1.0) < 1e-4 or pitch <= 0:
        return amostras
    n_saida = max(1, int(len(amostras) / pitch))
    posicoes = np.arange(n_saida, dtype=np.float64) * pitch
    origem = np.arange(len(amostras), dtype=np.float64)
    saida = np.empty((n_saida, 2), dtype=np.float32)
    for canal in range(2):
        saida[:, canal] = np.interp(posicoes, origem, amostras[:, canal])
    return saida


def mixar(sons, duracao: float, *, arquivos: dict | None = None,
          taxa: int = TAXA, inicio: float = 0.0):
    """Soma CRUA dos sons em ``[inicio, inicio + duracao]`` -> (buffer, relatorio).

    ``inicio`` e o ``start_offset`` de quem mostra so um trecho do clipe (o
    round decisivo no fim do video de build): o som que comecou antes do
    trecho entra pela cauda, se ela ainda soar dentro dele. Sem numpy,
    ``(None, relatorio)``.
    """
    if arquivos is None:
        from neural_fights.effects.audio_anotador import arquivos_de_som
        arquivos = arquivos_de_som()
    relatorio = {"sons": 0, "ids": [], "arquivos": [], "sem_arquivo": []}
    if np is None:
        return None, relatorio
    total = max(1, int(round(float(duracao) * taxa)))
    buf = np.zeros((total, 2), dtype=np.float32)
    ids, usados, faltando = set(), set(), set()
    fim = float(inicio) + float(duracao)
    for som in sons or []:
        try:
            t = float(som["t"])
            chave = str(som["id"])
            volume = float(som.get("volume", 1.0))
            pitch = float(som.get("pitch", 1.0) or 1.0)
        except (KeyError, TypeError, ValueError):
            continue
        if t >= fim or volume <= 0.0:
            continue
        arquivo = arquivos.get(chave)
        if arquivo is None:
            faltando.add(chave)
            continue
        amostras = decodificar(arquivo, taxa)
        if amostras is None:
            faltando.add(chave)
            continue
        amostras = com_pitch(amostras, pitch)
        ini = int(round((t - float(inicio)) * taxa))
        corte = 0
        if ini < 0:                       # comecou antes do trecho: so a cauda
            corte = -ini
            ini = 0
        if corte >= len(amostras):
            continue
        pedaco = amostras[corte: corte + (total - ini)]
        if not len(pedaco):
            continue
        buf[ini: ini + len(pedaco)] += pedaco * volume
        relatorio["sons"] += 1
        ids.add(chave)
        usados.add(Path(arquivo).name)
    relatorio["ids"] = sorted(ids)
    relatorio["arquivos"] = sorted(usados)
    relatorio["sem_arquivo"] = sorted(faltando)
    return buf, relatorio


def nivel_ativo_db(buf, taxa: int = TAXA) -> float | None:
    """Energia media dos momentos ativos, em dBFS (None se tudo e silencio)."""
    if np is None or buf is None or not len(buf):
        return None
    passo = max(1, int(taxa * JANELA_NIVEL_S))
    mono = np.mean(buf, axis=1) if buf.ndim == 2 else buf
    n = len(mono) // passo
    if n == 0:
        janelas = np.array([float(np.mean(mono ** 2))])
    else:
        janelas = np.mean(mono[: n * passo].reshape(n, passo) ** 2, axis=1)
    maior = float(np.max(janelas))
    if maior <= 1e-12:
        return None
    portao = maior * 10 ** (-PORTAO_RELATIVO_DB / 10)
    ativas = janelas[janelas >= portao]
    return 10 * math.log10(float(np.mean(ativas)))


def limitar(buf, taxa: int = TAXA, *, teto: float = TETO,
            bloco_ms: float = 5.0, soltura_ms: float = 80.0):
    """Limitador de picos com antecipacao de um bloco (5 ms) e soltura suave.

    O ganho de cada bloco ja cobre o pico do bloco SEGUINTE, entao ele desce
    antes do golpe chegar (sem estalo de ataque) e volta devagar depois.

    O ganho e interpolado entre as FRONTEIRAS dos blocos, cada uma no menor
    ganho dos dois vizinhos: assim nenhuma amostra de um bloco recebe mais
    ganho que o dele, e o corte seco do fim (`clip`) nao chega a agir. Com a
    interpolacao entre os centros, o fim de um bloco forte herdava um pouco do
    ganho do vizinho mais baixo, o `clip` achatava o pico, e o aac do trecho
    devolvia esse canto com 2,5 dB a mais (medido em 28/09/2026: 139 amostras
    em 0 dB saindo de um wav limitado em -2,5).
    """
    if np is None or buf is None or not len(buf):
        return buf
    pico = np.max(np.abs(buf), axis=1)
    bloco = max(1, int(taxa * bloco_ms / 1000.0))
    nb = int(math.ceil(len(pico) / bloco))
    cheio = np.zeros(nb * bloco, dtype=np.float32)
    cheio[: len(pico)] = pico
    picos = cheio.reshape(nb, bloco).max(axis=1)
    exigido = np.minimum(1.0, teto / np.maximum(picos, 1e-9))
    adiante = np.append(exigido[1:], 1.0)
    exigido = np.minimum(exigido, adiante)
    soltura = math.exp(-bloco / (taxa * soltura_ms / 1000.0))
    ganhos = np.empty(nb, dtype=np.float64)
    atual = 1.0
    for i in range(nb):
        alvo = float(exigido[i])
        atual = alvo if alvo < atual else alvo + (atual - alvo) * soltura
        ganhos[i] = atual
    fronteiras = np.minimum(np.concatenate(([ganhos[0]], ganhos)),
                            np.concatenate((ganhos, [ganhos[-1]])))
    posicoes = np.arange(nb + 1, dtype=np.float64) * bloco
    ganho = np.interp(np.arange(len(buf)), posicoes, fronteiras).astype(np.float32)
    saida = buf * ganho[:, None]
    return np.clip(saida, -teto, teto)


def normalizar(buf, taxa: int = TAXA, *, alvo_db: float = ALVO_DB,
               teto: float = TETO):
    """Nivel ativo em ``alvo_db`` e picos sob ``teto`` -> (buffer, ganho_db)."""
    nivel = nivel_ativo_db(buf, taxa)
    if nivel is None:
        return buf, 0.0
    ganho_db = float(alvo_db) - nivel
    ajustado = buf * np.float32(10 ** (ganho_db / 20))
    return limitar(ajustado, taxa, teto=teto), ganho_db


def gravar_wav(destino: Path, buf, taxa: int = TAXA) -> Path:
    """(n, 2) float -> WAV estereo 16-bit."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    x = np.asarray(buf, dtype=np.float64)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    inteiro = (np.clip(x, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(destino), "wb") as arquivo:
        arquivo.setnchannels(2)
        arquivo.setsampwidth(2)
        arquivo.setframerate(int(taxa))
        arquivo.writeframes(inteiro.tobytes())
    return destino


def trilha_da_luta(sons, duracao: float, destino: Path, *, inicio: float = 0.0,
                   taxa: int = TAXA, alvo_db: float = ALVO_DB,
                   arquivos: dict | None = None, extra=None) -> dict | None:
    """Mistura, normaliza por trecho e grava ``destino`` (WAV). Relatorio ou None.

    ``extra`` e uma matriz (n, 2) somada ANTES de normalizar — e por onde o
    som sintetizado antigo entra quando ligado como reforco. None quando nao
    ha numpy ou nenhum som caiu no trecho: quem chama decide o que fazer com
    o silencio (e nao e fingir que ha som).
    """
    buf, relatorio = mixar(sons, duracao, arquivos=arquivos, taxa=taxa, inicio=inicio)
    if buf is None:
        return None
    if extra is not None and len(extra):
        n = min(len(buf), len(extra))
        buf[:n] += np.asarray(extra[:n], dtype=np.float32)
    if relatorio["sons"] == 0 and (extra is None or not len(extra)):
        return None
    buf, ganho_db = normalizar(buf, taxa, alvo_db=alvo_db)
    gravar_wav(destino, buf, taxa)
    relatorio["ganho_db"] = round(ganho_db, 2)
    relatorio["arquivo"] = str(destino)
    return relatorio
