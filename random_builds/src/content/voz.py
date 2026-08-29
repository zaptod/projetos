"""Narracao FALADA do video, de graca.

`narration.json` sempre existiu com cada fala no tempo certo, mas saia com
`tts: null` — o roteiro nunca virou voz. Aqui ele vira:

    edge-tts     vozes neurais da Microsoft (pt-BR-AntonioNeural etc.), sem
                 chave e sem custo; precisa de internet. `pip install edge-tts`.
    SAPI         a voz do proprio Windows (Microsoft Maria, pt-BR), offline,
                 via PowerShell/System.Speech. E a reserva: sem rede ou sem
                 o pacote, a narracao continua existindo, so mais robotica.

Cada linha e sintetizada uma vez e guardada por hash em outputs/_voz_cache/:
um re-render nao paga a rede de novo. A trilha final (`voz.wav`) coloca cada
fala no `start` da linha; fala mais longa que o espaco dela e acelerada
(`atempo`, ate `max_atempo`) e, se ainda assim nao couber ate a proxima
linha, cortada com fade — nunca duas falas por cima uma da outra.

Sem numpy, sem ffmpeg ou com todos os motores falhando, `gerar` devolve
None e o render segue sem voz: a narracao e melhoria, nunca dependencia.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
RAIZ = Path(__file__).resolve().parents[2]
CACHE_PADRAO = RAIZ / "outputs" / "_voz_cache"

PADRAO = {
    "ativa": True,
    "motor": "edge",                 # edge | sapi
    "voz": "pt-BR-AntonioNeural",
    "taxa": "+12%",                  # edge-tts rate
    "tom": "+0Hz",                   # edge-tts pitch
    "voz_sapi": "Maria",             # trecho do nome da voz do Windows
    "taxa_sapi": 2,                  # -10..10
    "volume": 1.0,
    "max_atempo": 1.35,
    "folga": 0.3,                    # quanto uma fala pode passar do evento
    "atraso": 0.05,                  # respiro depois do corte
}


class VozIndisponivel(RuntimeError):
    pass


def config(cfg: dict | None) -> dict:
    saida = dict(PADRAO)
    saida.update({k: v for k, v in (cfg or {}).items() if v is not None})
    return saida


# --------------------------------------------------------------- texto falado
def _altura(m: re.Match) -> str:
    """'1,97m' -> '1 e 97' (um e noventa e sete); '2,01m' -> '2 metros e 1'."""
    metros, cent = m.group(1), m.group(2)
    if cent.startswith("0"):
        return f"{metros} metros e {int(cent)}" if int(cent) else f"{metros} metros"
    return f"{metros} e {cent}"


_SUBS = [
    (re.compile(r"(\d+),(\d{2})\s*m\b"), _altura),
    (re.compile(r"(\d+),(\d+)\s*kg\b"), r"\1 vírgula \2 quilos"),
    (re.compile(r"\bkg\b"), " quilos"),
    (re.compile(r"\s*/\s*100"), " de 100"),
    (re.compile(r"\bIA\b"), "inteligência artificial"),
    (re.compile(r"\bKO\b"), "nocaute"),
    (re.compile(r"[🔥💀😂😅✨⚡]+"), ""),
]


def falavel(texto: str) -> str:
    """Texto de tela -> texto para a voz: caixa alta vira frase, unidades
    viram palavra, emoji some. `2,01m` falado como '2 metros e 01' e a
    diferenca entre uma voz e um leitor de planilha."""
    t = str(texto or "").strip()
    if not t:
        return ""
    # "Duelista (Precisão)" fala "Duelista": o parentese e rotulo de tela.
    t = re.sub(r"\s*\([^)]*\)", "", t)
    if t.upper() == t and any(c.isalpha() for c in t):
        t = t.lower()
        t = t[0].upper() + t[1:]
    for padrao, troca in _SUBS:
        t = padrao.sub(troca, t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    if t and t[-1] not in ".!?…":
        t += "."
    return t


# ---------------------------------------------------------------- motores
def _chave(motor: str, voz: str, taxa, tom, texto: str) -> str:
    base = f"{motor}|{voz}|{taxa}|{tom}|{texto}".encode("utf-8")
    return hashlib.sha1(base).hexdigest()


def _edge(texto: str, destino: Path, cfg: dict) -> Path:
    try:
        import edge_tts
    except ImportError as exc:
        raise VozIndisponivel("edge-tts nao instalado (pip install edge-tts)") from exc

    async def _rodar():
        try:
            com = edge_tts.Communicate(texto, cfg["voz"], rate=str(cfg["taxa"]),
                                       pitch=str(cfg["tom"]), boundary="WordBoundary")
        except TypeError:  # versao antiga: so limites de frase
            com = edge_tts.Communicate(texto, cfg["voz"], rate=str(cfg["taxa"]),
                                       pitch=str(cfg["tom"]))
        # `stream()` em vez de `save()`: e aqui que chegam os limites
        # (WordBoundary ou SentenceBoundary, em unidades de 100 ns) — a base
        # da legenda karaoke sincronizada com a voz.
        limites = []
        with open(destino, "wb") as fh:
            async for pedaco in com.stream():
                if pedaco.get("type") == "audio":
                    fh.write(pedaco.get("data") or b"")
                elif str(pedaco.get("type", "")).endswith("Boundary"):
                    t0 = float(pedaco.get("offset", 0)) / 1e7
                    dur = float(pedaco.get("duration", 0)) / 1e7
                    limites.append({"t0": round(t0, 3), "t1": round(t0 + dur, 3),
                                    "texto": str(pedaco.get("text", "")).strip(),
                                    "tipo": str(pedaco.get("type", ""))})
        with open(palavras_de(destino), "w", encoding="utf-8") as fh:
            json.dump(_em_palavras(limites), fh, ensure_ascii=False)

    try:
        asyncio.run(_rodar())
    except Exception as exc:  # rede, voz inexistente, servico fora
        destino.unlink(missing_ok=True)
        raise VozIndisponivel(f"edge-tts falhou: {exc}") from exc
    if not destino.is_file() or destino.stat().st_size < 200:
        destino.unlink(missing_ok=True)
        raise VozIndisponivel("edge-tts devolveu arquivo vazio")
    return destino


def palavras_de(arquivo: Path) -> Path:
    """Onde ficam os limites de palavra de uma fala sintetizada."""
    return Path(arquivo).with_suffix(".words.json")


def _em_palavras(limites: list[dict]) -> list[dict]:
    """Limites de FRASE viram limites de palavra, repartindo a duracao da
    frase pelo tamanho de cada palavra. Limites de palavra passam direto."""
    saida = []
    for limite in limites:
        texto = str(limite.get("texto", "")).strip()
        if not texto:
            continue
        palavras = texto.split()
        if len(palavras) == 1 or limite.get("tipo") == "WordBoundary":
            saida.append({"t0": limite["t0"], "t1": limite["t1"], "texto": texto})
            continue
        pesos = [max(1, len(p.strip(".,!?…:;"))) for p in palavras]
        total = float(sum(pesos))
        cursor = float(limite["t0"])
        dur_total = float(limite["t1"]) - float(limite["t0"])
        for palavra, peso in zip(palavras, pesos):
            dur = dur_total * peso / total
            saida.append({"t0": round(cursor, 3), "t1": round(cursor + dur, 3),
                          "texto": palavra})
            cursor += dur
    return saida


def _palavras_da_fala(arquivo: Path, texto: str, duracao: float) -> list[dict]:
    """Limites de palavra da fala: os do motor quando existem; senao, o
    texto repartido no tempo pelo tamanho de cada palavra (SAPI nao informa
    limites — a legenda continua acompanhando, so com menos precisao)."""
    try:
        with open(palavras_de(arquivo), encoding="utf-8") as fh:
            dados = json.load(fh)
        if dados:
            return [d for d in dados if d.get("texto")]
    except (OSError, ValueError):
        pass
    palavras = [p for p in texto.split() if p.strip()]
    if not palavras or duracao <= 0:
        return []
    pesos = [max(1, len(p.strip(".,!?…:;"))) for p in palavras]
    total = float(sum(pesos))
    saida, cursor = [], 0.0
    for palavra, peso in zip(palavras, pesos):
        dur = duracao * peso / total
        saida.append({"t0": round(cursor, 3), "t1": round(cursor + dur, 3),
                      "texto": palavra})
        cursor += dur
    return saida


def _sapi(texto: str, destino: Path, cfg: dict) -> Path:
    """Voz do Windows via System.Speech (sem pip, sem rede)."""
    if sys.platform != "win32":
        raise VozIndisponivel("SAPI so existe no Windows")
    txt = destino.with_suffix(".txt")
    txt.write_text(texto, encoding="utf-8")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -like '*%s*' } "
        "| Select-Object -First 1; "
        "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; "
        "$s.Rate = %d; "
        "$s.SetOutputToWaveFile('%s'); "
        "$s.Speak([IO.File]::ReadAllText('%s', [Text.Encoding]::UTF8)); "
        "$s.Dispose()"
    ) % (cfg["voz_sapi"], int(cfg["taxa_sapi"]), str(destino).replace("'", "''"),
         str(txt).replace("'", "''"))
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                               "-Command", script],
                              capture_output=True, text=True, timeout=60,
                              creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VozIndisponivel(f"SAPI falhou: {exc}") from exc
    finally:
        txt.unlink(missing_ok=True)
    if proc.returncode != 0 or not destino.is_file() or destino.stat().st_size < 200:
        destino.unlink(missing_ok=True)
        raise VozIndisponivel(f"SAPI falhou: {(proc.stderr or '')[-200:]}")
    return destino


def sintetizar(texto: str, cfg: dict, cache: Path = CACHE_PADRAO,
               log=None) -> Path:
    """Arquivo de audio desta fala (cache por hash). Tenta o motor
    configurado e cai no outro; so levanta se os dois falharem."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    ordem = ["edge", "sapi"] if cfg["motor"] == "edge" else ["sapi", "edge"]
    erros = []
    for motor in ordem:
        ext = ".mp3" if motor == "edge" else ".wav"
        chave = _chave(motor, cfg["voz"] if motor == "edge" else cfg["voz_sapi"],
                       cfg["taxa"] if motor == "edge" else cfg["taxa_sapi"],
                       cfg["tom"] if motor == "edge" else "", texto)
        destino = cache / f"{chave}{ext}"
        if destino.is_file() and destino.stat().st_size > 200:
            return destino
        try:
            return (_edge if motor == "edge" else _sapi)(texto, destino, cfg)
        except VozIndisponivel as exc:
            erros.append(str(exc))
            if log:
                log(f"[voz] {motor}: {exc}")
    raise VozIndisponivel("; ".join(erros))


# ----------------------------------------------------------------- mixagem
def _duracao(caminho: Path) -> float:
    try:
        saida = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(caminho)],
            capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
        return float(saida.stdout.strip())
    except (ValueError, subprocess.SubprocessError, OSError):
        return 0.0


def _pcm(caminho: Path, taxa: int, atempo: float | None = None):
    """Amostras mono float32 via ffmpeg (com atempo quando pedido).
    Tambem apara o silencio das pontas, que o TTS costuma deixar."""
    # So o silencio do FIM sai, e de um jeito que NAO toca nas pausas do
    # meio: `silenceremove=stop_periods=1` corta na PRIMEIRA pausa
    # ("Guerreiro. Na media." virava so "Guerreiro" - medido em 29/08, era
    # isso que decapitava a narracao). Inverter, aparar o inicio e
    # desinverter remove exatamente o silencio final e nada mais. O inicio
    # fica intacto: os limites de palavra sao relativos a ele.
    filtros = ["areverse",
               "silenceremove=start_periods=1:start_threshold=-45dB:detection=peak",
               "areverse"]
    if atempo and abs(atempo - 1.0) > 0.01:
        filtros.append(f"atempo={min(2.0, max(0.5, atempo)):.3f}")
    cmd = ["ffmpeg", "-v", "error", "-i", str(caminho), "-af", ",".join(filtros),
           "-ac", "1", "-ar", str(taxa), "-f", "f32le", "pipe:"]
    saida = subprocess.run(cmd, capture_output=True, timeout=120,
                           creationflags=NO_WINDOW)
    if saida.returncode != 0:
        raise VozIndisponivel("ffmpeg nao decodificou a fala")
    return np.frombuffer(saida.stdout, dtype=np.float32).astype(np.float64)


def medir(linhas: list[dict], cfg: dict, taxa: int = 44100,
          cache: Path = CACHE_PADRAO, log=None) -> dict[int, float]:
    """Duracao real (sem o silencio do fim) de cada fala, por indice.

    E o que permite a cena ESPERAR a fala: o plano e cronometrado depois de
    saber quanto cada linha dura na velocidade natural. Linhas que nao
    puderam ser sintetizadas ficam de fora (a cena mantem a duracao
    visual). Tudo passa pelo cache: medir e sintetizar sao o mesmo custo.
    """
    saida: dict[int, float] = {}
    if np is None or not shutil.which("ffmpeg"):
        return saida
    for i, linha in enumerate(linhas):
        texto = falavel(linha.get("text", ""))
        if not texto:
            continue
        try:
            arquivo = sintetizar(texto, cfg, cache, log)
            pcm = _pcm(arquivo, taxa)
        except VozIndisponivel as exc:
            if log:
                log(f"[voz] nao medi a linha {i}: {exc}")
            continue
        saida[i] = round(len(pcm) / taxa, 3)
    return saida


def montar(linhas: list[dict], destino: Path, cfg: dict, taxa: int = 44100,
           cache: Path = CACHE_PADRAO, log=None) -> Path | None:
    """`linhas` = [{start, duration, text}] -> WAV estereo com as falas no
    tempo. Devolve None se nenhuma linha pode ser sintetizada."""
    if np is None or not linhas or not shutil.which("ffmpeg"):
        return None
    linhas = sorted((dict(l) for l in linhas if str(l.get("text", "")).strip()),
                    key=lambda l: float(l["start"]))
    if not linhas:
        return None
    fim_video = max(float(l["start"]) + float(l["duration"]) for l in linhas) + 1.0
    buf = np.zeros(int(fim_video * taxa))
    colocadas = 0
    cortadas = 0
    palavras_no_video: list[dict] = []
    max_atempo = float(cfg["max_atempo"])
    folga, atraso = float(cfg["folga"]), float(cfg["atraso"])

    for i, linha in enumerate(linhas):
        texto = falavel(linha["text"])
        if not texto:
            continue
        inicio = float(linha["start"]) + atraso
        # A fala pode passar do evento por `folga`, mas NUNCA entra na
        # proxima fala: o limite e o menor dos dois.
        limite = float(linha["start"]) + float(linha["duration"]) + folga
        if i + 1 < len(linhas):
            limite = min(limite, float(linhas[i + 1]["start"]) - 0.05)
        espaco = limite - inicio
        if espaco < 0.35:
            continue
        try:
            arquivo = sintetizar(texto, cfg, cache, log)
        except VozIndisponivel as exc:
            if log:
                log(f"[voz] linha {i} pulada: {exc}")
            continue
        bruto = _duracao(arquivo)
        atempo = None
        if bruto > espaco:
            atempo = min(max_atempo, bruto / espaco)
        try:
            pcm = _pcm(arquivo, taxa, atempo)
        except VozIndisponivel:
            continue
        maximo = int(espaco * taxa)
        if len(pcm) > maximo:
            cortadas += 1
            if log:
                log(f"[voz] fala {i} cortada em {espaco:.2f}s (tinha "
                    f"{len(pcm) / taxa:.2f}s): {texto[:40]!r}")
            pcm = pcm[:maximo]
            rampa = min(len(pcm), int(0.06 * taxa))
            if rampa:
                pcm[-rampa:] *= np.linspace(1.0, 0.0, rampa)
        pos = int(inicio * taxa)
        fim = min(len(buf), pos + len(pcm))
        if fim > pos:
            buf[pos:fim] += pcm[:fim - pos]
            colocadas += 1
            # Palavras no relogio do VIDEO: o atempo encurta os tempos do
            # motor na mesma proporcao; o que ficou depois do corte some.
            fator = float(atempo or 1.0)
            limite_fala = len(pcm) / taxa
            for palavra in _palavras_da_fala(arquivo, texto, limite_fala):
                t0 = float(palavra["t0"]) / fator
                t1 = float(palavra["t1"]) / fator
                if t0 >= limite_fala - 0.02:
                    continue
                palavras_no_video.append({
                    "t0": round(inicio + t0, 3),
                    "t1": round(inicio + min(t1, limite_fala), 3),
                    "texto": palavra["texto"], "linha": i})
    if not colocadas:
        return None
    if cortadas and log:
        # Com o plano ajustado ao roteiro isto nao deveria acontecer: se
        # aparecer, a cena foi cronometrada sem medir a fala.
        log(f"[voz] ATENCAO: {cortadas} fala(s) cortada(s) antes do fim")
    pico = float(np.max(np.abs(buf)))
    if pico > 1e-6:
        buf *= min(1.0, 0.92 / pico) * float(cfg.get("volume", 1.0))
    from ..video.trilha import gravar_wav
    with open(caminho_palavras(destino), "w", encoding="utf-8") as fh:
        json.dump(palavras_no_video, fh, ensure_ascii=False)
    return gravar_wav(destino, np.clip(buf, -1, 1), taxa)


def caminho_palavras(voz_wav: Path) -> Path:
    """`voz.wav` -> `voz_palavras.json` (as palavras no relogio do video)."""
    return Path(voz_wav).with_name("voz_palavras.json")


def gerar(out_dir: Path, cfg: dict | None, taxa: int = 44100,
          log=print) -> Path | None:
    """`outputs/<id>/narration.json` -> `outputs/<id>/voz.wav` (ou None).

    Regrava so quando o roteiro mudou (hash guardado ao lado): o worker de
    identidade re-renderiza a mesma geracao varias vezes e a voz e a mesma.
    """
    cfg = config(cfg)
    if not cfg.get("ativa", True):
        return None
    out_dir = Path(out_dir)
    roteiro = out_dir / "narration.json"
    destino = out_dir / "voz.wav"
    marca = out_dir / "voz.hash"
    if not roteiro.is_file():
        return None
    try:
        with open(roteiro, encoding="utf-8-sig") as fh:
            linhas = json.load(fh).get("lines") or []
    except (OSError, ValueError):
        return None
    assinatura = hashlib.sha1(
        json.dumps([linhas, {k: cfg[k] for k in ("motor", "voz", "taxa", "tom",
                                                 "voz_sapi", "taxa_sapi")}],
                   ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    if destino.is_file() and marca.is_file() and marca.read_text().strip() == assinatura:
        return destino
    try:
        pronto = montar(linhas, destino, cfg, taxa=taxa, log=log)
    except Exception as exc:  # nunca derruba o render por causa da voz
        if log:
            log(f"[voz] desligada nesta geracao: {exc}")
        return None
    if pronto is not None:
        marca.write_text(assinatura)
        if log:
            log(f"[voz] {len(linhas)} fala(s) -> {pronto.name}")
    return pronto
