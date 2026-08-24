"""Os arquivos que a build entrega junto do mp4 (secoes 18 e 19).

    timeline.json    a montagem em forma legivel: roleta, resultado, reacao,
                     video. E o mesmo corte do edit_plan, sem o peso dos dados
                     internos - da para ler, versionar e comparar duas builds.
    subtitles.srt    as legendas ja no tempo do video.
    evaluation.json  o julgamento editorial de cada rolagem (secao 11) e o que
                     a edicao decidiu fazer com ele.

Nada aqui decide nada: os tres saem do edit_plan que ja foi montado. Se um dia
a montagem mudar, estes arquivos mudam junto sem precisar ser reescritos.
"""
from __future__ import annotations

from ..evaluation.reaction_classifier import classify_all


def timeline(edit_plan: dict) -> list[dict]:
    """A montagem em forma semantica (secao 19)."""
    saida = []
    for evento in edit_plan["events"]:
        tipo = evento["type"]
        linha = {"type": tipo, "start": evento["start"],
                 "duration": evento["duration"]}
        if tipo == "roulette":
            roll = evento["roll"]
            linha.update({
                "entity": roll["entity"],
                "category": roll["category"],
                "result": roll["display_value"],
                "classification": evento.get("classification"),
                "tier": roll["tier"],
            })
        elif tipo == "reaction":
            linha.update({
                "type": "reaction",
                "category": evento.get("category"),
                "classification": evento.get("classification"),
                "reason": evento.get("reason"),
                "clip": (evento.get("asset") or {}).get("id"),
            })
        elif tipo == "identity":
            # E ESTE o formato que a secao 19 pede: um evento que aponta para o
            # arquivo entregue pela build. O rotulo segue a MIDIA — chamar de
            # "video" a imagem do personagem faria o timeline.json mentir sobre
            # o que a build produziu, que e a unica coisa que ele existe para
            # nao fazer.
            midia = (evento.get("asset") or {}).get("media") or "video"
            linha.update({"type": "image" if midia == "imagem" else "video",
                          "slot": evento["slot"], "asset": _nome(evento)})
        elif tipo == "nameplate":
            linha.update({"slot": evento["slot"],
                          "titulo": evento["nameplate"]["titulo"],
                          "faltando": _arquivo_do_slot(evento["slot"])})
        elif tipo == "synergy":
            linha["score"] = evento["compatibility"]["compatibility_score"]
        elif tipo == "final":
            linha["score"] = evento["build"]["final_score"]
            linha["verdict"] = evento["build"]["verdict_label"]
        else:
            linha["caption"] = evento.get("caption", "")
        saida.append(linha)
    return saida


def _nome(evento: dict) -> str:
    from pathlib import Path
    return Path((evento.get("asset") or {}).get("path", "")).name


def _arquivo_do_slot(slot: str) -> str:
    from ..identity.slots import ARQUIVO
    return ARQUIVO.get(slot, "")


def _tempo(segundos: float) -> str:
    total = max(0.0, float(segundos))
    horas, resto = divmod(total, 3600)
    minutos, segundos = divmod(resto, 60)
    inteiros = int(segundos)
    milis = int(round((segundos - inteiros) * 1000))
    if milis == 1000:          # 1,9995 s nao pode virar ":02,1000"
        inteiros, milis = inteiros + 1, 0
    return f"{int(horas):02d}:{int(minutos):02d}:{inteiros:02d},{milis:03d}"


def srt(edit_plan: dict) -> str:
    """Legendas no tempo do video, prontas para queimar ou subir separadas."""
    blocos = []
    for evento in edit_plan["events"]:
        texto = (evento.get("caption") or "").strip()
        if not texto:
            continue
        inicio = evento["start"]
        fim = inicio + evento["duration"]
        blocos.append((inicio, fim, texto))

    linhas = []
    for indice, (inicio, fim, texto) in enumerate(blocos, start=1):
        linhas.append(str(indice))
        linhas.append(f"{_tempo(inicio)} --> {_tempo(fim)}")
        linhas.append(texto)
        linhas.append("")
    return "\n".join(linhas)


def evaluation(generation: dict, edit_plan: dict,
               editing_config: dict | None = None) -> dict:
    """Como cada rolagem foi julgada e o que a edicao fez com isso."""
    classificacoes = classify_all(generation["rolls"], editing_config)

    # Reacao pertence a rolagem imediatamente anterior a ela na timeline.
    # A chave e (entidade, index): `index` sozinho colide, porque ele reinicia
    # do zero na primeira rolagem da arma.
    reacoes = {}
    ultima_roleta = None
    for evento in edit_plan["events"]:
        if evento["type"] == "roulette":
            roll = evento["roll"]
            ultima_roleta = (roll.get("entity"), roll.get("index"))
        elif evento["type"] == "reaction" and ultima_roleta is not None:
            reacoes[ultima_roleta] = {
                "category": evento.get("category"),
                "clip": (evento.get("asset") or {}).get("id"),
                "duration": evento["duration"],
            }

    for linha in classificacoes:
        linha["reaction"] = reacoes.get((linha["entity"], linha["index"]))

    build = generation["build"]
    return {
        "generation_id": generation["generation_id"],
        "seed": generation["seed"],
        "final_score": build["final_score"],
        "verdict": build["verdict_label"],
        "compatibility_score": generation["compatibility"]["compatibility_score"],
        "total_duration": edit_plan["total_duration"],
        "reaction_count": len(reacoes),
        "rolls": classificacoes,
    }
