# -*- coding: utf-8 -*-
"""(d) QUALIDADE E ERROS: o que falhou, e onde doi.

Erro que aparece so no console de quem estava olhando na hora nao existe.
Aqui os erros recentes viram lista, com fabrica e canal, para caberem numa
tela e num alerta do Telegram.
"""
from __future__ import annotations

from builds import atividade


def diario_ilegivel() -> str:
    """O motivo de o diario (`atividade.jsonl`) NAO poder ser lido, ou "".

    SCR-P3 (14/10/2026): com o diario ausente ou trancado, `recentes` e
    `estado_das_fabricas` devolviam vazio, e as telas diziam "0 erros, tudo
    ocioso" — igual a um dia calmo.
    """
    try:
        caminho = atividade._arquivo()
        if not caminho.is_file():
            return f"o diário não existe ({caminho})"
        with open(caminho, "rb"):
            pass
    except OSError as exc:
        return f"diário ilegível ({type(exc).__name__}: {exc})"[:200]
    return ""


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


# `qualidade_das_lutas` SAIU em 14/10/2026 (SCR-P9): lia o
# relatorio de qualidade das lutas no runtime, que nenhum codigo escreve, e mostraria "nunca
# avaliado" para sempre. Nenhuma tela lia o campo. Volta junto com um
# escritor de verdade (o `neural_fights/tools/qualidade_luta.py`).


def problemas() -> dict:
    motivo = diario_ilegivel()
    if motivo:
        return {"erro": motivo}
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
    }
