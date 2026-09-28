# -*- coding: utf-8 -*-
"""O video tem som ONDE IMPORTA? A medida unica de "mudo" da publicacao.

A medida antiga (`postar._audio_mudo`, ate 28/09/2026) olhava o arquivo
INTEIRO: media abaixo de -60 dB, ou calado (-50 dB por mais de 0,5 s) em
metade do tempo. Ela pega o render 100% mudo e a estreia calada do render
antigo — e nao ve uma LUTA muda debaixo de musica. Medido pela parte Builds em
28/09/2026: 38 de 129 publicacoes desde 15/09 sairam com a luta calada,
inclusive a `generation_00083:build:celular:B` das 00:45 — o `seg_021` (a
luta) a -91 dB, e a musica de fundo cobrindo o resto.

Aqui a mesma medida roda tambem em cada TRECHO DE LUTA, no arquivo do trecho
antes da mixagem (`_segments_<perfil>/seg_NNN.mp4`), achado pelo
`edit_plan.json` ao lado do video: o evento de indice N e o `seg_NNN` (e o
que o `concat.txt` do render lista, na mesma ordem). Luta e o evento
`gameplay` em todo formato (build, estreia, duelo, torneio).

Tres respostas, e nenhuma e palpite:
  motivo  — mudo (o arquivo, ou algum trecho de luta): o video NAO sai;
  ""      — tem som onde importa (ou nao ha luta nenhuma no plano);
  None    — nao deu para medir (arquivo apagado, ffmpeg falhou). Nao barra —
            "nao sei" nunca barra video aqui —, mas nao e lembrado, nao solta
            marca, e o publicador registra no diario que a guarda ficou cega.

Quem usa: `postar._audio_mudo` (a fila e os contadores de estoque, a mesma
funcao), e a guarda `barrar_luta_muda`, chamada de dentro dos dois
publicadores — o funil por onde passam a grade, a recuperacao, a reserva, o
`main.py publicar`, o bot e o app.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

LIMIAR_MUDO_DB = -60.0
# Fracao do trecho em silencio (abaixo de -50 dB por mais de 0,5 s) a partir
# da qual ele conta como mudo. A MEDIA sozinha so pegava o render 100% calado:
# a revisao de 15/09/2026 achou estreias do render antigo mudas quase inteiras e
# com som so no fim, media -27 a -30 dB. Medido nos 23 builds prontos: 20 com
# 0% de silencio, e as tres estreias defeituosas com 93%, 95% e 100%.
FRACAO_MUDA = 0.5
TIPOS_DE_LUTA = ("gameplay",)
MARCA_DA_LUTA = "a luta esta muda"
# O comeco do `estado` de toda marca "a conferir" posta por AUDIO. E o que
# permite soltar SO estas quando o som volta, sem nunca tocar numa marca de
# clique sem confirmacao (que so sai por conferencia humana).
PREFIXO_DA_MARCA = "[audio] "
_SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class LutaMuda(RuntimeError):
    """O video tem trecho de luta calado. Nao e falha de publicacao: e o video
    que nao pode sair, e so sai depois de re-renderizado."""


def _ffprobe(caminho: Path) -> dict:
    """A mesma pergunta que `contos.publicar.qualidade._ffprobe` faz (e que a
    medida usava ate 28/09): duracao e tipo de cada faixa. Copiada, e nao
    importada, porque `builds` nao depende de `contos`."""
    try:
        saida = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration,size:format_tags=comment:"
             "stream=codec_type,codec_name",
             "-of", "json", str(caminho)],
            capture_output=True, text=True, timeout=60,
            creationflags=_SEM_JANELA)
        return json.loads(saida.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


def medir(caminho: Path, *, fracao: bool = True):
    """O motivo quando o arquivo sai calado; "" com som; None se nao mediu.

    `fracao=False` e a regua da LUTA: so a media (abaixo de -60 dB) e a faixa
    ausente contam. A regra "calado em metade do tempo" foi medida em videos
    FINAIS, com musica; no trecho de luta antes da mixagem so ha o efeito dos
    golpes, e o silencio entre as trocas e normal. Medido em 28/09/2026: com
    ela, tres duelos novos (00014, 00016, 00017) sairiam da fila por "calado
    em 57-63%" com media de -19 a -21 dB — golpe de verdade, nao luta muda.

    `None` e a ferramenta que falhou ou que rodou sem medir nada: isso e "nao
    sei", e "nao sei" nao pode ser lembrado nem contado como "tem som".
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        return None
    dados = _ffprobe(caminho)
    faixas = dados.get("streams") if isinstance(dados, dict) else None
    if faixas and not any(f.get("codec_type") == "audio" for f in faixas):
        return "o mp4 nao tem faixa de audio"
    try:
        duracao = float(((dados or {}).get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        duracao = 0.0
    try:
        saida = subprocess.run(
            ["ffmpeg", "-v", "info", "-i", str(caminho), "-vn", "-af",
             "silencedetect=n=-50dB:d=0.5,volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300, creationflags=_SEM_JANELA)
    except (OSError, subprocess.SubprocessError):
        return None
    texto = saida.stderr or ""
    media = re.search(r"mean_volume: (-?[\d.]+) dB", texto)
    if media is None:
        return None
    if float(media.group(1)) < LIMIAR_MUDO_DB:
        return f"o audio esta mudo (media {float(media.group(1)):.1f} dB)"
    if duracao > 0:
        calado = sum(float(x) for x in re.findall(r"silence_duration: ([\d.]+)", texto))
        inicios = re.findall(r"silence_start: (-?[\d.]+)", texto)
        if len(inicios) > len(re.findall(r"silence_end:", texto)):
            # silencio que vai ate o fim do arquivo pode nao ganhar fechamento
            calado += max(0.0, duracao - float(inicios[-1]))
        parte = min(1.0, calado / duracao)
        if fracao and parte >= FRACAO_MUDA:
            return (f"o video fica calado em {parte:.0%} do tempo "
                    f"({calado:.0f} de {duracao:.0f} s)")
    return ""


# A MEDIDA LEMBRADA. Os contadores de estoque medem todo build pronto e rodam
# em processo novo a cada chamada: o painel a cada 10 min, o /metas do bot,
# cada rodada da grade. Medido em 28/09/2026: com a lembranca morando no
# `postar.py` (que o bot carrega do zero a cada relatorio), os seis testes de
# `relatorios.metas` mediam 148 builds cada um, e a suite do bot passou de
# 900 s. Aqui ela mora num modulo importado normalmente (vale para o
# processo inteiro) e num arquivo no diretorio de runtime (vale entre
# processos; os testes o isolam).
#
# A chave e o arquivo NESTA versao (caminho, tamanho, data em ns) e o
# criterio (limiar e fracao): re-render ou mudanca de limiar mede de novo. So
# medida de verdade e guardada — "nao sei" nunca: o cache de voz envenenado
# de 11/09 era uma falha servida para sempre como resultado.
_LEMBRADO: dict = {}
LEMBRADOS_NO_DISCO = 3000


def _chave(caminho: Path, fracao: bool = True) -> str:
    info = caminho.stat()
    regua = f"{FRACAO_MUDA}" if fracao else "so-media"
    return (f"{caminho.resolve()}|{info.st_size}|{info.st_mtime_ns}|"
            f"{LIMIAR_MUDO_DB}|{regua}")


def _arquivo_lembrado() -> Path | None:
    try:
        from ..contas import runtime_dir
        return Path(runtime_dir()) / "audio_medido.json"
    except Exception:                                          # noqa: BLE001
        return None


def _ler_lembrado(arquivo: Path | None) -> dict:
    if arquivo is None:
        return {}
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def _gravar_lembrado(arquivo: Path | None, chave: str, motivo: str) -> None:
    """Acrescenta sem travar: perder uma entrada numa corrida so custa medir
    de novo, e a troca e atomica (nunca meio arquivo)."""
    if arquivo is None:
        return
    try:
        dados = _ler_lembrado(arquivo)
        dados.pop(chave, None)
        dados[chave] = motivo
        if len(dados) > LEMBRADOS_NO_DISCO:
            dados = dict(list(dados.items())[-LEMBRADOS_NO_DISCO:])
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = arquivo.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, arquivo)
    except OSError:
        pass


def medir_lembrado(caminho, *, medir=None, fracao: bool = True):
    """`medir`, lembrado por arquivo e criterio. Mesmas tres respostas."""
    if medir is None:
        medida = globals()["medir"]
        medir = lambda c: medida(c, fracao=fracao)            # noqa: E731
    caminho = Path(caminho)
    try:
        chave = _chave(caminho, fracao)
    except OSError:
        return None
    if chave in _LEMBRADO:
        return _LEMBRADO[chave]
    arquivo = _arquivo_lembrado()
    no_disco = _ler_lembrado(arquivo).get(chave)
    if isinstance(no_disco, str):
        _LEMBRADO[chave] = no_disco
        return no_disco
    motivo = medir(caminho)
    if motivo is None:
        return None
    _LEMBRADO[chave] = motivo
    _gravar_lembrado(arquivo, chave, motivo)
    return motivo


def trechos_de_luta(video) -> list | None:
    """Os arquivos dos trechos de luta, pelo plano ao lado do mp4.

    `None` quando nao ha plano (historia, pedaco cortado): nao ha luta a
    medir, e isso nao e "nao sei". Lista vazia: ha plano e nenhuma luta.
    """
    caminho = Path(str(getattr(video, "caminho", "") or ""))
    plano = caminho.parent / "edit_plan.json"
    try:
        eventos = json.loads(plano.read_text(encoding="utf-8")).get("events")
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(eventos, list):
        return None
    perfil = str(getattr(video, "perfil", "") or "celular")
    pasta = caminho.parent / f"_segments_{perfil}"
    return [pasta / f"seg_{i:03d}.mp4" for i, evento in enumerate(eventos)
            if isinstance(evento, dict) and evento.get("type") in TIPOS_DE_LUTA]


def luta_muda(video, *, medir=None):
    """So a luta: motivo, "" ou None (ver o topo do modulo).

    A regua e a da luta (`fracao=False`): muda e a luta sem som nenhum
    (-91 dB, faixa ausente), e nao a luta com silencio entre os golpes.
    """
    medir = medir or (lambda t: medir_lembrado(t, fracao=False))
    trechos = trechos_de_luta(video)
    if not trechos:
        return ""
    cego = False
    for trecho in trechos:
        motivo = medir(trecho)
        if motivo is None:
            cego = True
            continue
        if motivo:
            return f"{MARCA_DA_LUTA} ({trecho.stem}: {motivo})"
    return None if cego else ""


def veredito(video):
    """O arquivo inteiro E a luta: motivo, "" ou None.

    "" so quando as duas medidas disseram "tem som". Um "nao sei" de qualquer
    uma vira None — que nao barra, mas tambem nao solta marca.
    """
    inteiro = medir_lembrado(Path(str(getattr(video, "caminho", "") or "")))
    if inteiro:
        return inteiro
    luta = luta_muda(video)
    if luta:
        return luta
    if inteiro is None or luta is None:
        return None
    return ""


# ------------------------------------------------------------ a guarda
def barrar_luta_muda(video, canal: str, plataforma: str) -> None:
    """A GUARDA DO FUNIL: levanta `LutaMuda` antes de abrir o navegador.

    Todo caminho que publica passa por `youtube.publicar_como_configurado` ou
    `tiktok.publicar` — a grade, a recuperacao, a reserva, o `main.py
    publicar`, o bot e o app. A fila da grade ja pula o video mudo; esta
    guarda e para os outros caminhos, que nunca mediram audio nenhum.

    SO A LUTA, de proposito: a medida do arquivo inteiro sempre foi so da
    fila de builds, e aplica-la aqui passaria a valer tambem para as
    historias, com um criterio que nunca foi medido nelas.

    O motivo vai para a lista "a conferir" DAQUELE destino, que o app e o bot
    mostram. A fila de builds solta a marca sozinha quando o video volta a ter
    som (`revisar_marcas`) — o re-render muda o arquivo e a medida e refeita.
    """
    motivo = luta_muda(video)
    vid = str(getattr(video, "id", "") or "")
    if motivo is None:
        _diario(canal, vid, (
            f"{vid}: nao consegui medir o som da luta (trecho ausente ou "
            f"ffmpeg falhou); publiquei sem essa guarda."), erro=True)
        return
    if not motivo:
        return
    marcar(canal, vid, motivo, plataforma)
    raise LutaMuda(f"{vid}: {motivo}. Nao publico: sai depois do re-render.")


def marcar(canal: str, video_id: str, motivo: str, plataforma: str) -> None:
    """Poe na lista "a conferir" com o motivo. Nunca levanta: o bloqueio de
    verdade e quem chama nao publicar, e a lista e o aviso visivel."""
    try:
        from . import desfecho
        desfecho.marcar_para_conferir(
            canal, video_id, PREFIXO_DA_MARCA + motivo, plataforma,
            aviso=(f"{video_id}: {motivo}. Fica fora do {plataforma} ate "
                   f"voltar a ter som (re-render); a marca sai sozinha."),
            etapa="publicar.audio", erro=False)
    except Exception as exc:                                   # noqa: BLE001
        _diario(canal, video_id, (
            f"{video_id}: {motivo}; e NAO consegui por na lista a conferir "
            f"({type(exc).__name__})."), erro=True)


def revisar_marcas(canal: str, videos, *, julgar=None,
                   plataformas=("youtube", "tiktok")) -> list:
    """Solta a marca de AUDIO de quem voltou a ter som. Devolve os soltos.

    So marca que comeca com `PREFIXO_DA_MARCA` — a de clique sem confirmacao
    nunca, essa so sai por conferencia humana. E so com veredito "" (as duas
    medidas disseram "tem som"): "nao sei" deixa a marca onde esta. Nunca
    levanta: nao conseguir soltar so adia o video.
    """
    julgar = julgar or veredito
    por_id = {str(getattr(v, "id", "")): v for v in videos or ()}
    if not por_id:
        return []
    from . import desfecho
    soltos = []
    for plataforma in plataformas:
        try:
            marcas = desfecho.marcas(canal, plataforma)
        except Exception:                                      # noqa: BLE001
            continue
        for vid, marca in marcas.items():
            estado = str((marca or {}).get("estado") or "")
            if vid not in por_id or not estado.startswith(PREFIXO_DA_MARCA):
                continue
            try:
                if julgar(por_id[vid]) != "":
                    continue
                if desfecho.soltar_marca(canal, vid, plataforma,
                                         prefixo=PREFIXO_DA_MARCA):
                    soltos.append((vid, plataforma))
                    _diario(canal, vid, (
                        f"{vid}: voltou a ter som; saiu da lista a conferir "
                        f"do {plataforma}."), erro=False)
            except Exception:                                  # noqa: BLE001
                continue
    return soltos


def _diario(canal: str, ref: str, texto: str, *, erro: bool) -> None:
    try:
        from .. import atividade
        atividade.registrar("publicacao",
                            atividade.ERRO if erro else atividade.LOG,
                            texto, canal, etapa="publicar.audio", ref=ref)
    except Exception:                                          # noqa: BLE001
        pass
