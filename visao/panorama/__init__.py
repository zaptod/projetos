# -*- coding: utf-8 -*-
"""As quatro familias de numero, num dicionario so — e sempre o MESMO.

    from panorama import resumo
    dados = resumo()

Por que existe: o painel, a Vila e o bot do Telegram respondiam "como estao
as coisas?" cada um do seu jeito. A Vila contava LINHAS de dois arquivos
(o que conta tambem o que falhou), o painel rodava um CLI e despejava o texto
num log, e o bot tinha a terceira versao. Tres respostas para a mesma
pergunta e uma delas errada -- e ninguem sabe qual.

    saude       (a) o que roda AGORA, o que espera, o que travou
    desempenho  (b) o que foi publicado e como se saiu
    inventario  (c) quanto ha pronto, por etapa
    qualidade   (d) o que falhou, e o placar das lutas

REGRAS, e elas nao sao decoracao:

  SO LE. Nao escreve arquivo, nao abre navegador, nao chama rede. Ha teste
  apontando o runtime para uma pasta somente-leitura para garantir. Um
  agregador que escreve corrompe estado quando alguem abre uma tela.

  NAO LEVANTA. Projeto ausente, disco lento, JSON quebrado -- cada familia
  se vira sozinha e devolve o que conseguiu. Uma tela de resumo que estoura
  por causa de um arquivo e pior do que uma tela incompleta.

  TEM TTL. Cada leitura toca disco (globs, JSONs, travas); sem cache, um
  poller de 3 s viraria I/O continuo.
"""
from __future__ import annotations

import threading
import time

from . import desempenho, inventario, qualidade, saude

# Quanto tempo uma leitura vale. Curto o bastante para a tela parecer viva,
# longo o bastante para varios paineis pedindo junto nao virarem enxurrada
# de disco.
VALIDADE_S = 3.0

_cache: dict = {}
_quando: float = 0.0
_porta = threading.Lock()


def resumo(forcar: bool = False) -> dict:
    """As quatro familias. Repetido dentro da validade, devolve o cache."""
    global _cache, _quando
    with _porta:
        if not forcar and _cache and (time.monotonic() - _quando) < VALIDADE_S:
            return _cache
        _cache = {
            "saude": _seguro(saude.agora),
            "desempenho": _seguro(desempenho.publicado),
            "inventario": _seguro(inventario.estoque),
            "qualidade": _seguro(qualidade.problemas),
        }
        _quando = time.monotonic()
        return _cache


def _seguro(funcao) -> dict:
    """Uma familia que falha nao pode levar as outras tres junto."""
    try:
        return funcao()
    except Exception as erro:
        return {"erro": f"{type(erro).__name__}: {erro}"}


def esquecer() -> None:
    """Joga o cache fora — para o teste nao depender do relogio."""
    global _cache, _quando
    with _porta:
        _cache, _quando = {}, 0.0


__all__ = ["VALIDADE_S", "desempenho", "esquecer", "inventario", "qualidade",
           "resumo", "saude"]
