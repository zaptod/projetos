# -*- coding: utf-8 -*-
"""Onde cada canal esta, contando o que existe em disco.

Nao pergunta ao `_estado.json` quantos videos foram medidos: CONTA os
arquivos. O estado gravado e um resumo que pode estar velho (processo morto,
pasta copiada, arquivo apagado na mao); o disco e o que e verdade. A conta e
barata porque cada etapa grava um arquivo por video, entao basta um
`iterdir`.

`proximo_passo` existe para o comando `status` responder a unica pergunta que
importa quando se volta ao trabalho no dia seguinte: e agora, o que eu rodo?
"""
from __future__ import annotations

from pathlib import Path

from . import canal as _canal
from . import config, estado

PROVEDORES = ("chatgpt", "gemini")


def _quantos(pasta: Path, sufixo: str = "") -> int:
    if not pasta.is_dir():
        return 0
    if sufixo:
        return sum(1 for p in pasta.iterdir() if p.name.endswith(sufixo))
    return sum(1 for p in pasta.iterdir())


def _em_disco(pasta: Path) -> dict:
    """Quanto de VIDEO ocupa disco agora.

    No fluxo de passagem este numero tem que ficar plano: sobe durante um
    lote, volta a quase zero quando ele fecha. Se estiver crescendo, algum
    video nao esta sendo apagado — e um acervo de centenas de videos ocupa
    centenas de gigabytes.
    """
    from . import baixar as _baixar
    midia = Path(pasta) / "midia"
    if not midia.is_dir():
        return {"videos": 0, "mb": 0.0}
    bytes_video, quantos = 0, 0
    for item in midia.iterdir():
        if not item.is_dir():
            continue
        arquivo = _baixar.video_de(pasta, item.name)
        if arquivo is not None:
            quantos += 1
            try:
                bytes_video += arquivo.stat().st_size
            except OSError:
                pass
    return {"videos": quantos, "mb": round(bytes_video / 1e6, 1)}


def do_canal(canal_id: str) -> dict:
    """O retrato de um canal: quanto de cada etapa ja existe."""
    pasta = config.pasta_do_canal(canal_id)
    try:
        cabecalho = _canal.cabecalho(pasta)
    except _canal.NaoColetou:
        cabecalho = {}
    videos = _canal.videos(pasta)
    fichas = {p: _quantos(pasta / "fichas" / p, ".json") for p in PROVEDORES}
    completos = sum(
        1 for v in videos
        if all((pasta / "fichas" / p / f"{v['id']}.json").is_file()
               for p in PROVEDORES))
    dados = {
        "canal_id": canal_id,
        "nome": cabecalho.get("nome") or "(sem nome)",
        "url": cabecalho.get("url", ""),
        "n_videos": len(videos),
        "duracao_total_s": cabecalho.get("duracao_total_s", 0.0),
        "baixados": _quantos(pasta / "midia"),
        "medidos": _quantos(pasta / "medidas", ".json"),
        "transcritos": _quantos(pasta / "transcricoes", ".srt"),
        "dossies": _quantos(pasta / "dossies", ".md"),
        "fichas": fichas,
        "fichas_total": sum(fichas.values()),
        # O que interessa no fluxo de passagem: quantos videos ja tem as DUAS
        # fichas (e portanto o mp4 pode ter ido embora), e quanto de video
        # ainda ocupa disco agora.
        "completos": completos,
        "em_disco": _em_disco(pasta),
        "biblia": (pasta / "biblia.json").is_file(),
        "preset": (pasta / "preset" / "roteiro.json").is_file(),
        "pasta": str(pasta),
        "etapas": estado.ler(pasta)["etapas"],
    }
    dados["proximo_passo"] = proximo_passo(dados)
    return dados


def proximo_passo(dados: dict) -> str:
    """O comando a rodar agora. Uma unica resposta, nunca uma lista.

    O caminho normal e o `absorver`: ele baixa, mede, transcreve, poe os dois
    provedores para ler ao mesmo tempo e apaga o video. Os comandos separados
    (`baixar`, `medir`, `transcrever`, `analisar`) continuam existindo para
    quem quer rodar uma etapa isolada, mas nao sao o que se sugere aqui —
    seguir por eles num canal de 342 videos enche o disco antes do fim.
    """
    canal_id = dados["canal_id"]
    total = dados["n_videos"]
    if not total:
        return "main.py canal <url>   (o catalogo saiu vazio)"
    if dados["completos"] < total:
        faltam = total - dados["completos"]
        return f"main.py absorver {canal_id}   ({faltam} sem as 2 fichas)"
    if not dados["biblia"]:
        return f"main.py biblia {canal_id}"
    if not dados["preset"]:
        return f"main.py preset {canal_id}"
    return "pronto — a biblia e o preset estao em disco"


def todos() -> list:
    """Um retrato por canal catalogado."""
    return [do_canal(canal_id) for canal_id in config.canais()]
