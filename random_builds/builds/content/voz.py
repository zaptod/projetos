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
import unicodedata
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


# Fala humana em pt-BR: medido em 02/09/2026 nas 30 partes boas das historias,
# de 1,99 a 2,87 palavras por segundo. Fora dessa faixa o audio nao e a leitura
# desse texto — foi assim que 417 palavras couberam em 21,8 s e viraram um
# video com 14 s de imagem muda no fim.
#
# A FAIXA E ASSIMETRICA DE PROPOSITO. O teto e o que importa: audio cortado da
# taxa ALTA (o defeito deu 19,1), e 4,0 ja e o dobro do que a fala real usa.
# O piso e folgado porque reprovar por engano custa caro — `_edge` levanta, o
# `sintetizar` cai no SAPI, e a historia inteira sai com a voz robotica sem
# ninguem entender por que. Varrendo o cache com os limites do motor, a entrada
# mais lenta deu 1,54; contar palavra ESCRITA (que e o que esta funcao recebe)
# da numeros ainda menores, porque o motor fala numero por extenso — "R$ 1.200"
# e uma palavra escrita e cinco faladas. 1,0 fica longe de tudo isso e continua
# pegando descompasso grosseiro.
PALAVRAS_POR_S_MIN = 1.0
PALAVRAS_POR_S_MAX = 4.0
# Abaixo disto a medida nao diz nada: "Sim." em 1 s da 1 palavra/s e esta certo.
PALAVRAS_PARA_AFERIR = 12


def taxa_de_fala(texto: str, duracao: float) -> float | None:
    """Palavras por segundo, ou None quando o texto e curto demais para aferir."""
    palavras = len([p for p in str(texto or "").split() if p.strip()])
    if palavras < PALAVRAS_PARA_AFERIR or duracao <= 0:
        return None
    return palavras / float(duracao)


def implausivel(texto: str, duracao: float) -> str:
    """Por que este audio NAO pode ser a leitura deste texto ('' = pode ser).

    O motor nao avisa quando o stream termina no meio: o arquivo existe, tem
    tamanho, toca — so acaba antes da frase. Contar palavra contra segundo e a
    unica pergunta que separa "leitura" de "pedaco de leitura".
    """
    taxa = taxa_de_fala(texto, duracao)
    if taxa is None:
        return ""
    palavras = len(texto.split())
    if taxa > PALAVRAS_POR_S_MAX:
        return (f"{palavras} palavras em {duracao:.1f}s ({taxa:.1f} palavras/s): "
                "o audio veio cortado")
    if taxa < PALAVRAS_POR_S_MIN:
        return (f"{palavras} palavras em {duracao:.1f}s ({taxa:.1f} palavras/s): "
                "o audio nao corresponde ao texto")
    return ""


def _edge(texto: str, destino: Path, cfg: dict) -> Path:
    try:
        import edge_tts
    except ImportError as exc:
        raise VozIndisponivel("edge-tts nao instalado (pip install edge-tts)") from exc

    # NADA e escrito no nome de cache antes de a sintese INTEIRA terminar. O
    # `async for` abaixo grava o mp3 aos pedacos: se o processo morre no meio
    # (Ctrl+C, painel parado, servico cortando o stream), o que sobra e um
    # audio pela metade — e o `except` daqui nao roda para apagar. Foi assim
    # que a parte 1 da historia 8 ficou com 21,8 s de uma narracao de 150 s,
    # e o cache serviu esse pedaco em TODA re-renderizacao seguinte.
    parcial = destino.with_name(destino.name + ".parcial")
    parcial_palavras = destino.with_name(destino.name + ".parcial.words.json")

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
        with open(parcial, "wb") as fh:
            async for pedaco in com.stream():
                if pedaco.get("type") == "audio":
                    fh.write(pedaco.get("data") or b"")
                elif str(pedaco.get("type", "")).endswith("Boundary"):
                    t0 = float(pedaco.get("offset", 0)) / 1e7
                    dur = float(pedaco.get("duration", 0)) / 1e7
                    limites.append({"t0": round(t0, 3), "t1": round(t0 + dur, 3),
                                    "texto": str(pedaco.get("text", "")).strip(),
                                    "tipo": str(pedaco.get("type", ""))})
        with open(parcial_palavras, "w", encoding="utf-8") as fh:
            json.dump(_em_palavras(limites), fh, ensure_ascii=False)

    def _limpar():
        parcial.unlink(missing_ok=True)
        parcial_palavras.unlink(missing_ok=True)

    try:
        asyncio.run(_rodar())
    except Exception as exc:  # rede, voz inexistente, servico fora
        _limpar()
        raise VozIndisponivel(f"edge-tts falhou: {exc}") from exc
    if not parcial.is_file() or parcial.stat().st_size < 200:
        _limpar()
        raise VozIndisponivel("edge-tts devolveu arquivo vazio")
    motivo = implausivel(texto, _duracao(parcial))
    if motivo:
        _limpar()
        raise VozIndisponivel(f"edge-tts: {motivo}")
    # As palavras entram PRIMEIRO: se morrermos entre os dois renames, sobra um
    # .words.json orfao (o cache erra, re-sintetiza, ninguem se machuca) em vez
    # de um audio sem alinhamento, que e o estado que fabricava tempos falsos.
    parcial_palavras.replace(palavras_de(destino))
    parcial.replace(destino)
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


def _palavras_da_fala(arquivo: Path, texto: str, duracao: float,
                      log=None) -> list[dict]:
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
    if log and Path(arquivo).suffix == ".mp3":
        # Para o SAPI isto e o normal. Para o edge e sintoma: ele SEMPRE manda
        # os limites, entao nao te-los significa que a sintese nao terminou, e
        # o que sai daqui abaixo e um tempo inventado sobre um audio incompleto.
        log(f"[voz] {Path(arquivo).name} sem limites de palavra: os tempos "
            "abaixo sao repartidos, nao medidos.")
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
    # Mesma doutrina do edge: a PowerShell escreve o wav aos poucos, entao ela
    # escreve num nome que o cache nao procura e so no fim ele vira o definitivo.
    parcial = destino.with_name(destino.name + ".parcial")
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
    ) % (cfg["voz_sapi"], int(cfg["taxa_sapi"]), str(parcial).replace("'", "''"),
         str(txt).replace("'", "''"))
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                               "-Command", script],
                              capture_output=True, text=True, timeout=60,
                              creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as exc:
        parcial.unlink(missing_ok=True)
        raise VozIndisponivel(f"SAPI falhou: {exc}") from exc
    finally:
        txt.unlink(missing_ok=True)
    if proc.returncode != 0 or not parcial.is_file() or parcial.stat().st_size < 200:
        parcial.unlink(missing_ok=True)
        raise VozIndisponivel(f"SAPI falhou: {(proc.stderr or '')[-200:]}")
    motivo = implausivel(texto, _duracao(parcial))
    if motivo:
        parcial.unlink(missing_ok=True)
        raise VozIndisponivel(f"SAPI: {motivo}")
    parcial.replace(destino)
    return destino


def motivo_do_cache_ruim(arquivo: Path, texto: str, motor: str = "edge") -> str:
    """Por que esta entrada do cache NAO serve para este texto ('' = serve).

    Antes bastava "existe e tem mais de 200 bytes", e por isso um mp3 gravado
    pela metade continuou sendo servido para sempre: re-renderizar nao adianta
    quando a resposta ja esta guardada.
    """
    arquivo = Path(arquivo)
    if not arquivo.is_file() or arquivo.stat().st_size < 200:
        return "arquivo vazio"
    if motor == "edge" and not palavras_de(arquivo).is_file():
        # O sidecar so e escrito depois do audio inteiro: sem ele, a sintese
        # daquele arquivo nao chegou ao fim.
        return "sem os limites de palavra (sintese interrompida)"
    return implausivel(texto, _duracao(arquivo))


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
        if destino.is_file():
            ruim = motivo_do_cache_ruim(destino, texto, motor)
            if not ruim:
                return destino
            # Entrada envenenada se apaga sozinha: sem isso, so um rm manual
            # tirava o video quebrado do caminho.
            if log:
                log(f"[voz] cache de {motor} descartado ({ruim}); re-sintetizando.")
            destino.unlink(missing_ok=True)
            palavras_de(destino).unlink(missing_ok=True)
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


# ------------------------------------------------------- leitura continua
# O "robotico" nao vinha da voz: vinha do RECORTE. Cada cena era uma sintese
# separada, entao a entonacao reiniciava a cada ~14 s — o narrador tomava
# folego do zero, terminava em cadencia de ponto final e recomecava, catorze
# vezes. Medido em 01/09/2026 numa parte de 206 s: 97% de fala, so 5,5 s de
# silencio total. Nao era falta de audio; era falta de CONTINUIDADE.
#
# Aqui o texto inteiro da parte vai numa sintese so. A prosodia atravessa as
# cenas, as pausas nascem da pontuacao, e o video passa a seguir o audio (e
# nao o contrario): os limites de palavra dizem onde cada cena comeca.
def _normalizar_palavra(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                   if unicodedata.category(c) != "Mn").lower().strip(
                       ".,!?…:;\"'()[]—–-")


def _marcos_das_falas(linhas: list, palavras: list, duracao: float,
                      com_indices: bool = False):
    """Onde cada fala COMECA dentro da leitura continua.

    Anda pelas palavras do audio na ordem, consumindo as palavras esperadas
    de cada fala. Quando o motor divide diferente do `split()` (contracao,
    numero por extenso), o passo tolera: procura a proxima palavra que casa
    dentro de uma janela curta, e se nao achar segue em frente — perder o
    alinhamento de uma palavra desloca a cena em decimos, nao quebra nada.
    """
    ditas = [_normalizar_palavra(p.get("texto")) for p in palavras]
    marcos, indices, cursor = [], [], 0
    for linha in linhas:
        esperadas = [w for w in (_normalizar_palavra(x) for x
                                 in falavel(linha.get("text", "")).split()) if w]
        if not esperadas:
            marcos.append(marcos[-1] if marcos else 0.0)
            indices.append(indices[-1] if indices else 0)
            continue
        indices.append(min(cursor, max(0, len(palavras) - 1)))
        marcos.append(float(palavras[min(cursor, len(palavras) - 1)]["t0"])
                      if palavras else 0.0)
        # CONSOME o fluxo palavra a palavra em vez de pular um bloco do
        # tamanho da frase. O motor fala numero por extenso ("R$ 1.200" vira
        # cinco palavras, "17 de setembro de 2009" vira seis), entao contar
        # `split()` desalinha — e o erro ACUMULA: na parte de 206 s a ultima
        # cena chegava 9 s atrasada e ficava sem tempo para a propria fala.
        for esperada in esperadas:
            janela = min(cursor + 8, len(ditas))
            achou = next((k for k in range(cursor, janela)
                          if ditas[k] == esperada), None)
            # Nao achou = essa palavra nao foi FALADA como esta escrita
            # ("R$", "17"). Avancar mesmo assim comeria uma palavra da cena
            # seguinte, e o erro acumularia ate a ultima cena ficar sem
            # tempo — foi o que aconteceu na primeira tentativa.
            if achou is not None:
                cursor = achou + 1
            if cursor >= len(ditas):
                break
    # a primeira cena sempre abre o video, mesmo que a voz demore um instante
    if marcos:
        marcos[0] = 0.0
    # nunca andar para tras (um desalinhamento nao pode inverter cenas)
    for i in range(1, len(marcos)):
        marcos[i] = max(marcos[i], marcos[i - 1] + 0.4)
        marcos[i] = min(marcos[i], max(0.0, duracao - 0.4))
    return (marcos, indices) if com_indices else marcos


# ------------------------------------------------------------- o respiro
# Medido em 01/09/2026 na leitura continua de uma parte de 210 s: 66 pausas,
# das quais 54 entre 0,88 e 0,98 s e 12 entre 0,26 e 0,30 s. ZERO entre 0,40
# e 0,80 s, ZERO acima de 1 s. Isso nao e respiracao — e uma grade. O motor
# neural aplica a mesma pausa em todo ponto final, e a regularidade e o que
# sobra de robotico depois que a entonacao ja parou de reiniciar.
#
# Aqui as pausas sao REESCRITAS pelo que veio antes delas: virgula pede um
# suspiro, ponto pede uma parada, fim de paragrafo pede ar, e de vez em
# quando uma frase merece um silencio que faz a pessoa esperar. O jitter e
# deterministico (indice da palavra), senao trocariamos uma grade por outra.
# As faixas para onde cada pausa e levada. Elas se sobrepoem de proposito:
# o objetivo nao e criar tres tamanhos novos, e espalhar o que era um valor
# unico por uma faixa continua.
PAUSAS = {
    "curta": (0.18, 0.42),        # respiro de virgula
    "frase": (0.55, 0.95),        # fim de frase
    "cena": (1.00, 1.45),         # a imagem trocou: o olho precisa de tempo
    "dramatica": (1.70, 2.30),    # o silencio que faz a pessoa esperar
}
# Abaixo disto e transicao entre palavras, nao pausa: nao se mexe.
PAUSA_MINIMA_S = 0.15
# O motor deixa a MESMA pausa em todo ponto final. Acima deste valor a
# pausa e tratada como fim de frase; abaixo, como respiro de virgula.
PAUSA_LONGA_S = 0.55
# Uma parada dramatica a cada N pausas de frase.
DRAMATICA_A_CADA = 11


def _sorteio(indice: int, faixa: tuple) -> float:
    """Valor deterministico dentro da faixa (mesma entrada, mesmo audio)."""
    passo = ((indice * 2654435761) % 997) / 997.0
    return faixa[0] + (faixa[1] - faixa[0]) * passo


def respirar(pcm, palavras: list, taxa: int, paragrafos=None, log=None):
    """Varia o TAMANHO das pausas que ja existem. Devolve (pcm, palavras).

    Por que existe: medido em 01/09/2026 numa parte de 210 s, das 66 pausas
    54 tinham entre 0,88 e 0,98 s e 12 entre 0,26 e 0,30 s — ZERO entre 0,40
    e 0,80 s e ZERO acima de 1 s. O motor neural aplica a mesma pausa em
    todo ponto final, e essa regularidade e o que sobra de robotico depois
    que a entonacao ja parou de reiniciar.

    O que este codigo NAO faz: decidir onde ha pausa. Quem decide isso e a
    pontuacao, e o motor ja aplicou — os limites de palavra dele, porem, nao
    trazem pontuacao nenhuma, entao tentar reconstruir isso pelo texto
    apagou 43 s de silencio na primeira tentativa. Aqui a pausa existente e
    o sinal: ela so muda de tamanho.

    A voz nao e tocada. Apenas o que existe entre as palavras muda.
    """
    if np is None or not palavras or len(palavras) < 2:
        return pcm, palavras

    paragrafos = set(paragrafos or ())
    pedacos, novas = [], []
    cursor, frases, mexidas = 0.0, 0, 0
    for i, palavra in enumerate(palavras):
        t0, t1 = float(palavra["t0"]), float(palavra["t1"])
        trecho = pcm[int(t0 * taxa):int(t1 * taxa)]
        if not len(trecho):
            continue
        pedacos.append(trecho)
        novas.append({**palavra, "t0": round(cursor, 3),
                      "t1": round(cursor + len(trecho) / taxa, 3)})
        cursor += len(trecho) / taxa
        if i + 1 >= len(palavras):
            break

        natural = max(0.0, float(palavras[i + 1]["t0"]) - t1)
        if natural < PAUSA_MINIMA_S:
            # transicao entre palavras da mesma frase: fica como esta
            silencio = natural
        else:
            if i + 1 in paragrafos:
                tipo = "cena"
            elif natural >= PAUSA_LONGA_S:
                frases += 1
                tipo = ("dramatica" if frases % DRAMATICA_A_CADA == 0
                        else "frase")
            else:
                tipo = "curta"
            silencio = _sorteio(i, PAUSAS[tipo])
            mexidas += 1
        if silencio > 0:
            pedacos.append(np.zeros(int(silencio * taxa), dtype=pcm.dtype))
            cursor += silencio

    if not pedacos:
        return pcm, palavras
    novo = np.concatenate(pedacos)
    if log:
        log(f"[voz] respiro: {mexidas} pausa(s) redistribuida(s); "
            f"{len(pcm) / taxa:.1f}s -> {cursor:.1f}s")
    return novo, novas


def narrar_continuo(linhas: list, destino: Path, cfg: dict, taxa: int = 44100,
                    cache: Path = CACHE_PADRAO, log=None) -> dict | None:
    """Le a parte INTEIRA de uma vez. Devolve wav, marcos e palavras.

    `marcos[i]` e o segundo em que a fala `i` comeca — e com isso o plano de
    edicao passa a ser consequencia do audio, nao uma previsao dele.
    """
    if np is None or not shutil.which("ffmpeg"):
        return None
    textos = [falavel(linha.get("text", "")) for linha in linhas]
    inteiro = " ".join(t for t in textos if t).strip()
    if not inteiro:
        return None
    try:
        arquivo = sintetizar(inteiro, cfg, cache, log)
        pcm = _pcm(arquivo, taxa)
    except VozIndisponivel as exc:
        if log:
            log(f"[voz] leitura continua indisponivel ({exc})")
        return None

    duracao = len(pcm) / float(taxa)
    palavras = _palavras_da_fala(arquivo, inteiro, duracao, log)
    if cfg.get("respiro", True):
        # Alinha uma vez so para descobrir em que PALAVRA cada cena comeca —
        # e ali que entra a respirada longa. Depois do respiro os tempos
        # mudaram, entao o alinhamento e refeito sobre o audio novo.
        _antes, indices = _marcos_das_falas(linhas, palavras, duracao,
                                            com_indices=True)
        pcm, palavras = respirar(pcm, palavras, taxa,
                                 paragrafos=set(indices[1:]), log=log)
        duracao = len(pcm) / float(taxa)
    marcos = _marcos_das_falas(linhas, palavras, duracao)

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    from ..video.trilha import gravar_wav
    pico = float(np.max(np.abs(pcm))) if len(pcm) else 0.0
    if pico > 1e-6:
        pcm = pcm * (min(1.0, 0.92 / pico) * float(cfg.get("volume", 1.0)))
    gravar_wav(destino, np.clip(pcm, -1.0, 1.0), taxa)
    # Cada palavra leva o indice da CENA em que ela cai. A legenda usa isso
    # para nao juntar num mesmo grupo o fim de uma cena e o comeco da outra.
    def cena_de(t: float) -> int:
        for i in range(len(marcos) - 1, -1, -1):
            if t >= marcos[i] - 1e-6:
                return i
        return 0

    with open(caminho_palavras(destino), "w", encoding="utf-8") as fh:
        json.dump([{**palavra, "linha": cena_de(float(palavra["t0"]))}
                   for palavra in palavras], fh, ensure_ascii=False)
    if log:
        log(f"[voz] leitura continua: {duracao:.1f}s numa sintese so "
            f"({len(linhas)} cena(s), {len(palavras)} palavras)")
    return {"wav": destino, "marcos": marcos, "palavras": palavras,
            "duracao": duracao}


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
