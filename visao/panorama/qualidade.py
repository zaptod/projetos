# -*- coding: utf-8 -*-
"""(d) QUALIDADE E ERROS: o que falhou, e onde doi.

Erro que aparece so no console de quem estava olhando na hora nao existe.
Aqui os erros recentes viram lista, com fabrica e canal, para caberem numa
tela e num alerta do Telegram.
"""
from __future__ import annotations

from builds import atividade


def _erros_recentes(quantos: int = 12) -> list:
    """Os ultimos eventos de erro do diario, do mais novo para o mais velho."""
    try:
        eventos = atividade.recentes(300)
    except Exception:
        return []
    erros = []
    for evento in eventos:
        if evento.get("status") != atividade.ERRO:
            continue
        erros.append({
            "quando": evento.get("ts", ""),
            "fabrica": evento.get("fabrica", ""),
            "canal": evento.get("canal", ""),
            "detalhe": (evento.get("detalhe") or "")[:160],
        })
        if len(erros) >= quantos:
            break
    return erros


def _ledger() -> dict:
    """O placar das lutas: quem venceu, quantas, quem e campeao."""
    try:
        from builds.arena.ledger import Ledger
        registro = Ledger()
        return {"ranking": registro.ranking(limite=5),
                "campeao": registro.campeao_atual()}
    except Exception:
        return {}


def _alvos_do_jogo() -> dict:
    """A ultima avaliacao de qualidade de luta, se ela ja foi rodada.

    So LE o relatorio salvo. Rodar o corpus custa minutos de simulacao e nao
    pode acontecer porque alguem abriu uma tela.
    """
    try:
        import json
        from pathlib import Path
        from neural_fights.data import database
        caminho = Path(database.RUNTIME_DIR) / "relatorio_qualidade.json"
        if not caminho.is_file():
            return {}
        with open(caminho, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
        return {"quando": dados.get("quando", ""),
                "reprovados": len(dados.get("reprovados") or [])}
    except Exception:
        return {}


def problemas() -> dict:
    erros = _erros_recentes()
    por_fabrica: dict[str, int] = {}
    for erro in erros:
        chave = erro["fabrica"] or "?"
        por_fabrica[chave] = por_fabrica.get(chave, 0) + 1
    return {
        "erros_recentes": erros,
        "erros_por_fabrica": por_fabrica,
        "total_erros": len(erros),
        "ledger": _ledger(),
        "qualidade_das_lutas": _alvos_do_jogo(),
    }
