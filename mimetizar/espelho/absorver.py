# -*- coding: utf-8 -*-
"""O fluxo de passagem: baixa o que vai usar, analisa nos dois, e apaga.

E o modo normal de trabalhar com um canal grande. O acervo do Hiryo tem 342
videos e passaria de 400 GB em disco; aqui o disco fica PLANO — no maximo um
lote por vez, alguns gigabytes — porque o mp4 e material de passagem:

    baixa o lote -> mede -> transcreve -> monta o dossie
                 -> ChatGPT e Gemini leem AO MESMO TEMPO
                 -> apaga os videos -> proximo lote

O que fica em disco depois que o video sai: a medida, a transcricao, o
mosaico de frames, o dossie e as duas fichas. Sao quilobytes por video, e sao
eles — nao o mp4 — que a biblia usa. O video ja deu o que tinha para dar.

POR QUE DOIS PROCESSOS, e nao duas threads: o cliente de LLM usa a API
SINCRONA do patchright, que nao e segura entre threads. Um processo por
provedor tambem e a doutrina do resto do repositorio (tres janelas, tres
processos). As travas de `builds.travas` sao por pasta de perfil do Chrome,
entao ChatGPT e Gemini nao disputam nada e rodam de verdade em paralelo.

POR QUE EM LOTE, e nao um a um: abrir o Chrome custa alguns segundos, e um
lote de 4 paga esse custo uma vez em vez de quatro. `--lote 1` existe para
quem quiser estritamente um por vez; o disco e o mesmo, o relogio e que muda.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

from . import analise
from . import baixar as _baixar
from . import canal as _canal
from . import config, dossie, estado, ffmpeg, medidas, transcrever

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PROVEDORES = ("chatgpt", "gemini")


class NaoAbsorveu(RuntimeError):
    """Erro humano: o que se tentou, e o que fazer."""


def tem_ficha(pasta: Path, video_id: str, provedor: str) -> bool:
    return (Path(pasta) / "fichas" / provedor / f"{video_id}.json").is_file()


def falta_alguma(pasta: Path, video_id: str, provedores) -> bool:
    return any(not tem_ficha(pasta, video_id, p) for p in provedores)


def alvos(canal_id: str, *, provedores=PROVEDORES, limite: int = 0,
          criterio: str = "views") -> list:
    """Os videos que ainda nao tem ficha de todos os provedores pedidos."""
    pasta = config.pasta_do_canal(canal_id)
    escolhidos = _canal.selecionar(_canal.videos(pasta), limite=limite,
                                   criterio=criterio)
    return [v for v in escolhidos
            if falta_alguma(pasta, v["id"], provedores)]


def _lotes(itens: list, tamanho: int) -> list:
    tamanho = max(1, int(tamanho))
    return [itens[i:i + tamanho] for i in range(0, len(itens), tamanho)]


def _preparar(pasta: Path, lote: list, *, log=print) -> list:
    """Mede, transcreve e monta o dossie. Devolve os que ficaram prontos."""
    cfg_medidas = config.carregar("medidas")
    cfg_analise = config.carregar("analise")
    prontos = []
    for video in lote:
        video_id = video["id"]
        arquivo = _baixar.video_de(pasta, video_id)
        if arquivo is None:
            log(f"    ! {video_id}: o video nao veio; pulo.")
            continue
        try:
            if not (pasta / "medidas" / f"{video_id}.json").is_file():
                medida = medidas.medir_video(
                    arquivo, cfg=cfg_medidas,
                    contato_em=pasta / "contatos" / f"{video_id}.jpg")
                medida["video_id"] = video_id
                medida["titulo"] = video.get("titulo", "")
                (pasta / "medidas").mkdir(parents=True, exist_ok=True)
                (pasta / "medidas" / f"{video_id}.json").write_text(
                    json.dumps(medida, ensure_ascii=False, indent=2),
                    encoding="utf-8")
                log(f"    medido: {medida['cortes_por_min']} cortes/min, "
                    f"{medida['duracao_s'] / 60:.1f}min")
        except (ffmpeg.NaoMediu, ffmpeg.SemFerramenta, medidas.NaoMediu) as exc:
            log(f"    ! {video_id}: nao medi ({exc}); pulo.")
            continue

        if not (pasta / "transcricoes" / f"{video_id}.srt").is_file():
            _transcrever_um(pasta, video, log=log)

        dossie.gravar(pasta, video, cfg=cfg_analise)
        prontos.append(video)
    return prontos


def _transcrever_um(pasta: Path, video: dict, *, log=print) -> bool:
    """A transcricao de UM video, sem varrer o canal inteiro."""
    coleta = config.carregar("coleta")
    idiomas = (coleta.get("legendas") or {}).get("idiomas") or ["pt", "en"]
    video_id = video["id"]
    destino = pasta / "transcricoes"
    destino.mkdir(parents=True, exist_ok=True)

    falas, origem = [], ""
    legenda = _baixar.legenda_de(pasta, video_id, idiomas)
    if legenda is not None:
        try:
            falas = transcrever.ler_legenda(legenda)
            origem = f"legenda ({legenda.suffix.lstrip('.')})"
        except (OSError, ValueError):
            falas = []
    if not falas and transcrever.whisper_disponivel():
        arquivo = _baixar.video_de(pasta, video_id)
        alvo = destino / f"{video_id}.srt"
        if arquivo is not None and transcrever.por_whisper(arquivo, alvo,
                                                           log=log):
            falas = transcrever.ler_legenda(alvo)
            origem = "whisper"
    if not falas:
        log(f"    {video_id}: sem legenda e sem whisper — o dossie vai dizer "
            "que nao houve fala analisada.")
        return False

    medida = medidas.carregar(pasta, video_id)
    stats = transcrever.estatisticas(falas, medida.get("duracao_s", 0.0))
    (destino / f"{video_id}.srt").write_text(transcrever.para_srt(falas),
                                             encoding="utf-8")
    (destino / f"{video_id}.txt").write_text(transcrever.para_texto(falas),
                                             encoding="utf-8")
    (destino / f"{video_id}.json").write_text(
        json.dumps({"video_id": video_id, "origem": origem, **stats},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"    transcrito: {stats['palavras']} palavras, "
        f"{stats['wpm']:.0f} wpm ({origem})")
    return True


def _rodar_provedor(canal_id: str, provedor: str, ids: list, *,
                    headless: bool, log) -> int:
    """Um subprocesso `analisar --provedor X --video ...`. Devolve o codigo."""
    comando = [sys.executable, "-u", "-X", "utf8", "main.py", "analisar",
               canal_id, "--provedor", provedor, "--video", *ids]
    if headless:
        comando.append("--headless")
    proc = subprocess.Popen(
        comando, cwd=str(config.RAIZ), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", bufsize=1, creationflags=NO_WINDOW)
    try:
        for linha in proc.stdout:
            texto = linha.rstrip()
            if texto:
                # O prefixo e o que torna a saida dos dois legivel enquanto
                # eles escrevem ao mesmo tempo no mesmo console.
                log(f"  [{provedor}] {texto}")
        return proc.wait()
    finally:
        if proc.stdout:
            proc.stdout.close()


def _analisar_em_paralelo(canal_id: str, ids: list, provedores, *,
                          headless: bool, log) -> dict:
    """Levanta um processo por provedor e espera os dois."""
    codigos, threads = {}, []

    def trabalho(provedor: str) -> None:
        try:
            codigos[provedor] = _rodar_provedor(
                canal_id, provedor, ids, headless=headless, log=log)
        except OSError as exc:                                 # noqa: BLE001
            log(f"  [{provedor}] nao consegui rodar: {exc}")
            codigos[provedor] = 2

    for provedor in provedores:
        linha = threading.Thread(target=trabalho, args=(provedor,),
                                 daemon=True)
        linha.start()
        threads.append(linha)
    for linha in threads:
        linha.join()
    return codigos


def absorver(canal_id: str, *, provedores=PROVEDORES, limite: int = 0,
             criterio: str = "views", lote: int = 4, manter: bool = False,
             com_sessao: bool = False, headless: bool = False,
             log=print) -> dict:
    """Baixa, analisa nos dois ao mesmo tempo, apaga, e vai para o proximo."""
    ffmpeg.exigir()
    pasta = config.pasta_do_canal(canal_id)
    provedores = tuple(provedores)
    pendentes = alvos(canal_id, provedores=provedores, limite=limite,
                      criterio=criterio)
    if not pendentes:
        log("[absorver] nada pendente — todos os videos do alvo ja tem as "
            "duas fichas.")
        return {"analisados": 0, "liberado_mb": 0.0, "falharam": 0}

    lotes = _lotes(pendentes, lote)
    log(f"[absorver] {len(pendentes)} video(s) em {len(lotes)} lote(s) de "
        f"ate {lote}.")
    log(f"[absorver] o disco segura no maximo {lote} video(s) por vez: "
        "cada um sai assim que os dois provedores terminam com ele.")
    analise._diario("inicio", f"absorver {canal_id}: {len(pendentes)} videos",
                    canal_id)

    feitos, liberados, falharam = 0, 0, []
    for numero, grupo in enumerate(lotes, 1):
        log(f"\n[absorver] lote {numero}/{len(lotes)} "
            f"({len(grupo)} video(s))")
        baixado = _baixar.baixar_estes(pasta, grupo, com_sessao=com_sessao,
                                       log=lambda t: log(f"  {t}"))
        for video in baixado["faltaram"]:
            falharam.append((video["id"], "o download nao veio"))

        prontos = _preparar(pasta, grupo, log=log)
        if not prontos:
            log("[absorver] nenhum video deste lote ficou analisavel; sigo.")
            continue

        ids = [v["id"] for v in prontos]
        log(f"[absorver] {', '.join(provedores)} lendo {len(ids)} dossie(s) "
            "ao mesmo tempo...")
        codigos = _analisar_em_paralelo(canal_id, ids, provedores,
                                        headless=headless, log=log)
        if all(codigo == 2 for codigo in codigos.values()):
            raise NaoAbsorveu(
                "os dois provedores falharam de conserto "
                f"({codigos}). Nada foi apagado.\n"
                "  Confira a sessao com: python main.py llm probe "
                "--provedor chatgpt")

        for video in prontos:
            video_id = video["id"]
            if falta_alguma(pasta, video_id, provedores):
                falharam.append((video_id, "ficou sem ficha de algum provedor"))
                continue
            feitos += 1
            if manter:
                continue
            bytes_liberados = _baixar.apagar_midia(pasta, video_id)
            liberados += bytes_liberados
        if not manter:
            log(f"[absorver] lote {numero}: {liberados / 1e6:.0f} MB "
                "liberados no total (o derivado fica).")

    estado.marcar(pasta, "absorver", analisados=feitos,
                  falharam=len(falharam), liberado_mb=round(liberados / 1e6, 1))
    analise._diario("ok", f"absorver {canal_id}: {feitos} videos", canal_id)

    log(f"\n[absorver] {feitos} video(s) com as {len(provedores)} fichas.")
    if not manter:
        log(f"[absorver] {liberados / 1e6:.0f} MB de video apagados; "
            "medidas, transcricoes, mosaicos e fichas ficaram.")
    if falharam:
        log(f"[absorver] {len(falharam)} nao fecharam:")
        for video_id, motivo in falharam[:8]:
            log(f"    {video_id}: {motivo}")
    return {"analisados": feitos, "liberado_mb": round(liberados / 1e6, 1),
            "falharam": len(falharam)}


def em_disco(canal_id: str) -> dict:
    """Quanto de video esta ocupando disco agora, e quanto ja saiu."""
    pasta = config.pasta_do_canal(canal_id)
    bytes_video, quantos = 0, 0
    midia = pasta / "midia"
    if midia.is_dir():
        for item in midia.iterdir():
            if not item.is_dir():
                continue
            arquivo = _baixar.video_de(pasta, item.name)
            if arquivo is not None:
                quantos += 1
                bytes_video += arquivo.stat().st_size
    return {"videos_em_disco": quantos, "mb": round(bytes_video / 1e6, 1),
            "liberado_mb": estado.etapa(pasta, "absorver").get("liberado_mb", 0)}
