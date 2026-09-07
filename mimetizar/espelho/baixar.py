# -*- coding: utf-8 -*-
"""Etapa 2a: o acervo em disco, retomavel, com a conta feita antes.

Tres decisoes que valem explicacao:

  A CONTA VEM ANTES. Um acervo de 300 videos passa de 300 GB sem avisar. O
  comando mostra a estimativa e, acima do teto de `config/coleta.json`, exige
  `--sim`. Encher o disco as tres da manha nao e um erro que se conserta de
  manha: derruba o Windows junto.

  A RETOMADA E DO yt-dlp. `--download-archive` grava uma linha por video
  concluido; a proxima rodada pula tudo que ja esta la. Nao ha estado nosso
  para desincronizar do disco — o disco E o estado.

  UM VIDEO QUEBRADO NAO PARA OS OUTROS. `--ignore-errors`: video removido,
  privado ou com restricao de regiao vira aviso, nao fim da coleta. No fim se
  conta quem ficou faltando e isso vira codigo de saida 1 (pendencia), nunca
  um silencio que passa por sucesso.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from . import canal as _canal
from . import config, estado, ytdlp

ARQUIVO_RETOMADA = "_baixados.txt"


class NaoBaixou(RuntimeError):
    """Erro humano: o que se tentou, e o que fazer."""


def estimativa(videos: list, coleta: dict | None = None) -> dict:
    """Quanto disco e quanto tempo aquele conjunto custa, mais ou menos."""
    coleta = coleta or config.carregar("coleta")
    segundos = sum(float(v.get("duracao_s") or 0.0) for v in videos)
    mbps = float(coleta.get("bitrate_estimado_mbps") or 2.5)
    # megabit por segundo -> gigabyte: /8 vira megabyte, /1024 vira gigabyte.
    gigabytes = segundos * mbps / 8.0 / 1024.0
    return {"n_videos": len(videos), "horas": segundos / 3600.0,
            "gb": gigabytes, "teto_gb": float(coleta.get("teto_gb") or 0)}


def pasta_midia(pasta: Path) -> Path:
    destino = Path(pasta) / "midia"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _argumentos(pasta: Path, lista: Path, coleta: dict, *,
                com_sessao: bool = False, com_retomada: bool = True) -> list:
    midia = pasta_midia(pasta)
    legendas = coleta.get("legendas") or {}
    espera = coleta.get("espera_entre_videos") or [0, 0]
    argumentos = [
        "--batch-file", str(lista),
        "--paths", str(midia),
        # Uma pasta por video: `midia/<id>/video.mp4`, e ao lado dele o
        # info.json, a thumb e as legendas. Achar o que e de quem depois vira
        # `midia/<id>/`, sem casar nome de arquivo com titulo (que tem barra,
        # emoji e dois-pontos, e quebra em Windows).
        "--output", "%(id)s/video.%(ext)s",
        "--format", coleta.get("formato") or "bv*[height<=1080]+ba/b",
        "--merge-output-format", coleta.get("container") or "mp4",
        "--ignore-errors",
        "--no-overwrites",
        "--newline",
        "--retries", str(int(coleta.get("tentativas") or 3)),
        "--sleep-requests", str(float(coleta.get("espera_entre_requisicoes") or 1)),
        "--min-sleep-interval", str(int(espera[0])),
        "--max-sleep-interval", str(int(espera[-1])),
    ]
    if com_retomada:
        # O arquivo de retomada e o que faz `baixar` pular o que ja veio. No
        # fluxo `absorver` ele ATRAPALHA: o mp4 e apagado de proposito depois
        # da analise, e com a linha no arquivo o yt-dlp se recusaria a
        # rebaixar o video para uma segunda passada.
        argumentos += ["--download-archive", str(midia / ARQUIVO_RETOMADA)]
    if coleta.get("info_json", True):
        argumentos.append("--write-info-json")
    if coleta.get("thumbnail", True):
        argumentos.append("--write-thumbnail")
    if legendas.get("baixar", True):
        argumentos += ["--write-subs", "--sub-langs",
                       ",".join(legendas.get("idiomas") or ["pt", "en"])]
        if legendas.get("automaticas", True):
            argumentos.append("--write-auto-subs")
    if com_sessao:
        argumentos += _cookies(coleta)
    return argumentos


def _cookies(coleta: dict) -> list:
    """`--cookies-from-browser` apontando o perfil que ja tem login.

    So entra com `--com-sessao`, e de proposito: ler o banco de cookies de um
    perfil de Chrome mexe num arquivo que o navegador tambem usa. Para o
    acervo publico de um canal isto e desnecessario.
    """
    servico = coleta.get("servico_do_cookie") or "youtube_web"
    try:
        import builds.contas as contas
        perfil = contas.perfil(servico, "geral")
    except Exception as exc:                                   # noqa: BLE001
        raise NaoBaixou(
            f"pedi a sessao do {servico} mas nao achei o perfil ({exc}).\n"
            "  Faca o login uma vez na pagina Contas do painel.") from exc
    return ["--cookies-from-browser", f"chrome:{perfil}"]


# O que conta como "o video chegou". A thumb (`.webp`), a legenda (`.vtt`) e
# o `.info.json` tambem casam com `video.*` e sao gravados ANTES do video —
# um download que morre no meio deixa a pasta cheia e sem filme.
EXTENSOES_DE_VIDEO = (".mp4", ".mkv", ".webm", ".mov")
# Sobra de download interrompido. Contar isso como pronto e o jeito de nunca
# mais baixar o video que faltou.
EXTENSOES_PARCIAIS = (".part", ".ytdl", ".temp")


def video_de(pasta: Path, video_id: str) -> Path | None:
    """O arquivo de video daquele id, se existir e estiver inteiro."""
    alvo = Path(pasta) / "midia" / str(video_id)
    if not alvo.is_dir():
        return None
    for caminho in sorted(alvo.glob("video.*")):
        if caminho.suffix.lower() not in EXTENSOES_DE_VIDEO:
            continue
        if any(caminho.with_suffix(caminho.suffix + p).exists()
               for p in EXTENSOES_PARCIAIS):
            continue
        if caminho.stat().st_size <= 0:
            continue
        return caminho
    return None


def baixados(pasta: Path) -> set:
    """Os ids que ja tem VIDEO em disco. Le a pasta, nao o arquivo de retomada.

    O arquivo do yt-dlp diz "concluido"; a pasta diz "esta aqui". Quando os
    dois discordam — alguem apagou um mp4 na mao, ou o download morreu depois
    da thumb — quem manda e a pasta.
    """
    midia = Path(pasta) / "midia"
    if not midia.is_dir():
        return set()
    return {item.name for item in midia.iterdir()
            if item.is_dir() and video_de(pasta, item.name) is not None}


def info_de(pasta: Path, video_id: str) -> dict:
    """O `info.json` daquele video (vazio quando nao veio)."""
    caminho = Path(pasta) / "midia" / str(video_id) / "video.info.json"
    if not caminho.is_file():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def legenda_de(pasta: Path, video_id: str, idiomas=()) -> Path | None:
    """A legenda baixada, na ordem de preferencia dos idiomas."""
    alvo = Path(pasta) / "midia" / str(video_id)
    if not alvo.is_dir():
        return None
    encontradas = sorted(alvo.glob("video.*.vtt")) + sorted(alvo.glob("video.*.srt"))
    if not encontradas:
        return None
    for idioma in idiomas:
        for caminho in encontradas:
            if f".{idioma.lower()}." in caminho.name.lower():
                return caminho
    return encontradas[0]


def baixar(canal_id: str, *, limite: int = 0, criterio: str = "canal",
           sim: bool = False, com_sessao: bool = False, log=print) -> dict:
    """Baixa o que falta. Devolve o resumo (e nunca mente sobre o que faltou)."""
    ytdlp.exigir()
    pasta = config.pasta_do_canal(canal_id)
    coleta = config.carregar("coleta")
    todos = _canal.videos(pasta)
    if not todos:
        raise NaoBaixou(
            f"o catalogo de {canal_id} esta vazio. "
            f"Rode de novo: python main.py canal <url>")

    escolhidos = _canal.selecionar(todos, limite=limite, criterio=criterio)
    prontos = baixados(pasta)
    faltando = [v for v in escolhidos if v["id"] not in prontos]

    conta = estimativa(faltando, coleta)
    log(f"[baixar] {len(escolhidos)} no alvo, {len(prontos)} ja em disco, "
        f"{len(faltando)} a baixar")
    if not faltando:
        log("[baixar] nada a fazer — o alvo inteiro ja esta em disco.")
        estado.marcar(pasta, "baixar", baixados=len(prontos),
                      alvo=len(escolhidos))
        return {"baixados": len(prontos), "alvo": len(escolhidos),
                "faltando": 0, "novos": 0}

    log(f"[baixar] estimativa: {conta['gb']:.1f} GB, "
        f"{conta['horas']:.1f}h de video")
    if conta["teto_gb"] and conta["gb"] > conta["teto_gb"] and not sim:
        raise NaoBaixou(
            f"isso passa do teto de {conta['teto_gb']:.0f} GB "
            f"(estimei {conta['gb']:.1f} GB).\n"
            "  Para baixar assim mesmo:  --sim\n"
            "  Para baixar so uma parte: --limite 30 --criterio views\n"
            "  Para mudar o teto:        config/coleta.json")

    midia = pasta_midia(pasta)
    lista = midia / "_alvo.txt"
    lista.write_text("\n".join(v["url"] for v in faltando) + "\n",
                     encoding="utf-8")
    argumentos = _argumentos(pasta, lista, coleta, com_sessao=com_sessao)

    try:
        codigo = ytdlp.rodar_streaming(argumentos, log)
    finally:
        lista.unlink(missing_ok=True)

    agora = baixados(pasta)
    novos = len(agora) - len(prontos)
    ainda_faltam = [v for v in escolhidos if v["id"] not in agora]
    _registrar_datas(pasta, todos, agora, log=log)
    estado.marcar(pasta, "baixar", baixados=len(agora), alvo=len(escolhidos),
                  faltando=len(ainda_faltam), codigo=codigo)

    log(f"\n[baixar] +{novos} video(s); {len(agora)}/{len(escolhidos)} do alvo "
        f"em disco")
    if ainda_faltam:
        log(f"[baixar] {len(ainda_faltam)} nao vieram "
            "(removido, privado, ou restrito por regiao):")
        for video in ainda_faltam[:8]:
            log(f"    {video['id']}  {video['titulo'][:60]}")
        if len(ainda_faltam) > 8:
            log(f"    ... e mais {len(ainda_faltam) - 8}")
    return {"baixados": len(agora), "alvo": len(escolhidos), "novos": novos,
            "faltando": len(ainda_faltam), "codigo": codigo}


def baixar_estes(pasta: Path, videos: list, *, coleta: dict | None = None,
                 com_sessao: bool = False, log=print) -> dict:
    """Baixa EXATAMENTE estes videos, sem arquivo de retomada.

    E a porta do fluxo `absorver`, onde o video e material de passagem: ele
    entra, vira medida/transcricao/ficha, e sai. Quem decide o que ja foi
    feito ali e a FICHA em disco, nao o arquivo de retomada do yt-dlp — que
    aqui so atrapalharia, recusando-se a rebaixar o que foi apagado de
    proposito.
    """
    coleta = coleta or config.carregar("coleta")
    faltando = [v for v in videos if video_de(pasta, v["id"]) is None]
    if not faltando:
        return {"novos": 0, "faltaram": []}

    midia = pasta_midia(pasta)
    lista = midia / "_alvo_absorver.txt"
    lista.write_text("\n".join(v["url"] for v in faltando) + "\n",
                     encoding="utf-8")
    try:
        codigo = ytdlp.rodar_streaming(
            _argumentos(pasta, lista, coleta, com_sessao=com_sessao,
                        com_retomada=False), log)
    finally:
        lista.unlink(missing_ok=True)

    ainda = [v for v in faltando if video_de(pasta, v["id"]) is None]
    return {"novos": len(faltando) - len(ainda), "faltaram": ainda,
            "codigo": codigo}


def apagar_midia(pasta: Path, video_id: str) -> int:
    """Apaga o ARQUIVO DE VIDEO e devolve quantos bytes liberou.

    O que fica: `info.json`, a thumb e a legenda. Sao quilobytes, e sao o
    que permite remontar o dossie ou reconferir uma data sem baixar o video
    de novo. O que sai e o unico item pesado da pasta.
    """
    alvo = Path(pasta) / "midia" / str(video_id)
    if not alvo.is_dir():
        return 0
    liberados = 0
    for caminho in list(alvo.iterdir()):
        sufixo = caminho.suffix.lower()
        parcial = any(caminho.name.lower().endswith(p)
                      for p in EXTENSOES_PARCIAIS)
        if sufixo not in EXTENSOES_DE_VIDEO and not parcial:
            continue
        try:
            liberados += caminho.stat().st_size
            caminho.unlink()
        except OSError:
            continue
    return liberados


def _registrar_datas(pasta: Path, todos: list, prontos: set, *, log=print) -> int:
    """Troca a data aproximada pela exata do `info.json`.

    O catalogo estima a data pela posicao do video na aba (e a unica coisa
    disponivel sem visitar 300 paginas). Baixado o video, a data EXATA veio
    junto no info.json — e cadencia de publicacao lida em cima de estimativa
    e cadencia inventada.
    """
    corrigidos = 0
    for video in todos:
        if video["id"] not in prontos or not video.get("data_aproximada"):
            continue
        info = info_de(pasta, video["id"])
        bruta = str(info.get("upload_date") or "")
        if len(bruta) == 8 and bruta.isdigit():
            video["data"] = f"{bruta[:4]}-{bruta[4:6]}-{bruta[6:]}"
            video["data_aproximada"] = False
            corrigidos += 1
        if info.get("duration"):
            video["duracao_s"] = float(info["duration"])
        if info.get("view_count"):
            video["views"] = int(info["view_count"])
        if info.get("description") and not video.get("descricao"):
            video["descricao"] = str(info["description"]).strip()
    if corrigidos:
        _canal.gravar_videos(pasta, todos)
        log(f"[baixar] {corrigidos} data(s) aproximada(s) viraram exatas.")
    return corrigidos


def amostra_por_formato(videos: list, quantos: int, semente: int = 7) -> list:
    """Uma amostra que cobre os formatos, nao so os campeoes.

    Pegar os N mais vistos da um retrato enviesado: o canal pode ter dois
    formatos e um deles concentrar as views. Aqui se divide por aba e por
    faixa de duracao, e se sorteia dentro de cada grupo com semente fixa —
    reproduzivel, que e o que permite comparar duas rodadas.
    """
    if quantos <= 0 or len(videos) <= quantos:
        return list(videos)
    grupos = {}
    for video in videos:
        duracao = float(video.get("duracao_s") or 0)
        faixa = "curto" if duracao < 90 else "medio" if duracao < 600 else "longo"
        grupos.setdefault((video.get("aba", "videos"), faixa), []).append(video)

    sorteio = random.Random(semente)
    escolhidos, rodada = [], 0
    chaves = sorted(grupos)
    for lista in grupos.values():
        lista.sort(key=lambda v: v.get("views") or 0, reverse=True)
    while len(escolhidos) < quantos:
        avancou = False
        for chave in chaves:
            if rodada < len(grupos[chave]) and len(escolhidos) < quantos:
                escolhidos.append(grupos[chave][rodada])
                avancou = True
        if not avancou:
            break
        rodada += 1
    sorteio.shuffle(escolhidos)
    return escolhidos[:quantos]
