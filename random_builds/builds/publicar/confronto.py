# -*- coding: utf-8 -*-
"""O confronto do duelo em palavras que quem nunca viu o canal entende.

Semana 1 do plano unico (docs/PLANO.md, 20/10/2026). A pesquisa dos Shorts
que deram certo (docs/pesquisa/shorts-que-deram-certo.md) achou o mesmo
padrao em 12 de 12 canais: o titulo e o CONFRONTO ("Sword VS Dagger",
"Vampire VS Toxic Spike"), nunca um nome proprio inventado. O Neural Fights
publicava "Drusila Vyrhordan x Sigrid Brasbalmirn", que nao diz nada a quem
passa o dedo.

O rotulo de cada lado e o ESTILO da arma que o personagem tem no banco
("Facas Taticas", "Espada Longa", "Kusarigama") — o nome proprio da arma
("Dharduen") e tao inventado quanto o do personagem. Desde a decisao
`geral/canal-em-ingles` (20/10/2026) o rotulo sai EM INGLES, pelo mapa de
`ingles.py` ("Tactical Knives", "Longsword"). Desempate, quando os dois
lados dariam o mesmo rotulo:

    1. a classe           "Longsword Ninja VS Longsword Monk"
    2. o elemento da arma "Flame Longsword VS Frost Longsword"
    3. o primeiro nome    "Aldric's Longsword VS Elowen's Longsword"

Sem arma resolvida (nome que saiu do banco, ou estilo sem traducao), o
rotulo e a classe; sem classe, o nome do personagem — nunca vazio.

O mesmo rotulo vai para o titulo, a descricao (que e a legenda do TikTok) e
a faixa do topo do video, e o rodizio usa este modulo para nao escolher par
cujo titulo ja esta ocupado. Toda luta nova leva o rotulo carimbado no
``fight.json`` (``luta["confronto"]``): o titulo de um duelo nao muda depois
de gerado, mesmo que o banco mude.

Leitura pura, a nao ser ``carimbar`` (que so mexe no dict recebido).
"""
from __future__ import annotations

import time

from . import ingles

# A pergunta escrita no video, no 1o segundo (a do titulo mora no modelo do
# `publicacao.json`). Trocavel por `editing.json -> duelo.pergunta`.
PERGUNTA = ingles.PERGUNTA

_ARMAS: dict | None = None
_ARMAS_EM = 0.0
# Arma que nao esta no cache: o banco e relido no maximo uma vez a cada tanto
# (a roleta insere armas novas com o app aberto).
RELER_APOS_S = 60.0


def _carregar_armas() -> dict | None:
    try:
        from ..nf_bridge import loader as nf
        armas, _ = nf.database.carregar_database()
    except Exception:                                          # noqa: BLE001
        return None
    return {str(a.get("nome")): a for a in armas or ()
            if isinstance(a, dict) and a.get("nome")}


def armas_do_banco(recarregar: bool = False) -> dict:
    """{nome da arma: registro} do banco vivo; {} se nao deu para ler.

    So a leitura que deu certo fica guardada (a mesma doutrina do
    ``catalogo._nomes_no_banco``, PUB-5)."""
    global _ARMAS, _ARMAS_EM
    if _ARMAS is None or recarregar:
        lidas = _carregar_armas()
        _ARMAS_EM = time.monotonic()
        if lidas is None:
            return _ARMAS or {}
        _ARMAS = lidas
    return _ARMAS


def esquecer_armas() -> None:
    global _ARMAS, _ARMAS_EM
    _ARMAS, _ARMAS_EM = None, 0.0


def _arma(nome: str | None, armas: dict | None) -> dict:
    if not nome:
        return {}
    if armas is not None:
        return armas.get(nome) or {}
    banco = armas_do_banco()
    if nome not in banco and time.monotonic() - _ARMAS_EM > RELER_APOS_S:
        banco = armas_do_banco(recarregar=True)
    return banco.get(nome) or {}


def _limpo(texto) -> str:
    return " ".join(str(texto or "").split())


def classe_base(ficha: dict | None) -> str:
    """"Berserker (Furia)" -> "Berserker": o parenteses e taxonomia do motor.
    Em portugues (o que o banco guarda)."""
    return _limpo(str((ficha or {}).get("classe") or "").split("(")[0])


def classe_en(ficha: dict | None) -> str:
    """A classe que o PUBLICO le: "Necromante (Trevas)" -> "Necromancer"."""
    base = classe_base(ficha)
    return ingles.classe(base) if base else ""


def _estilo(ficha: dict, armas: dict | None) -> str:
    """O estilo da arma em portugues, como o banco guarda."""
    estilo = _limpo(ficha.get("arma_estilo"))
    if estilo:
        return estilo
    return _limpo(_arma(ficha.get("nome_arma"), armas).get("estilo"))


def _elemento(ficha: dict, armas: dict | None) -> str:
    bruto = _limpo(_arma(ficha.get("nome_arma"), armas).get("afinidade_elemento"))
    return ingles.elemento(bruto) if bruto else ""


def _primeiro_nome(ficha: dict, nome: str | None) -> str:
    return (_limpo(nome or ficha.get("nome")).split(" ") or [""])[0]


def rotulo_base(ficha: dict | None, nome: str | None = None,
                armas: dict | None = None) -> str:
    """O rotulo de UM lado, sem olhar o outro, em ingles: a arma, senao a
    classe, senao o nome."""
    ficha = ficha or {}
    return (ingles.rotulo_da_arma(_estilo(ficha, armas)) or classe_en(ficha)
            or _limpo(nome or ficha.get("nome")))


def _igual(a: str, b: str) -> bool:
    return a.casefold() == b.casefold()


def rotulos(f1: dict | None, f2: dict | None, *, nome1: str | None = None,
            nome2: str | None = None, armas: dict | None = None) -> tuple[str, str]:
    """(rotulo do p1, rotulo do p2), ja desempatados."""
    f1, f2 = f1 or {}, f2 or {}
    r1, r2 = rotulo_base(f1, nome1, armas), rotulo_base(f2, nome2, armas)
    if not _igual(r1, r2):
        return r1, r2
    c1, c2 = classe_en(f1), classe_en(f2)
    if c1 and c2 and not _igual(c1, c2) and not _igual(c1, r1):
        return f"{r1} {c1}", f"{r2} {c2}"
    e1, e2 = _elemento(f1, armas), _elemento(f2, armas)
    if e1 and e2 and not _igual(e1, e2):
        return f"{e1} {r1}", f"{e2} {r2}"
    n1, n2 = _primeiro_nome(f1, nome1), _primeiro_nome(f2, nome2)
    if n1 and n2 and not _igual(n1, n2):
        return f"{n1}'s {r1}", f"{n2}'s {r2}"
    return r1, r2


def do_par(p1: str, p2: str, fichas=None, armas: dict | None = None) -> tuple[str, str]:
    """Os rotulos de um par do rodizio, pelas fichas do banco (dict nome ->
    ficha). Sem ficha, o rotulo e o proprio nome."""
    banco = fichas if isinstance(fichas, dict) else {}
    return rotulos(banco.get(p1), banco.get(p2), nome1=p1, nome2=p2, armas=armas)


def da_luta(luta: dict | None, armas: dict | None = None) -> tuple[str, str]:
    """Os rotulos de uma luta gravada: o carimbo, se houver; senao das fichas
    que o ``fight.json`` guardou (com a arma lida do banco)."""
    luta = luta or {}
    carimbo = luta.get("confronto") or {}
    if isinstance(carimbo, dict) and carimbo.get("p1") and carimbo.get("p2"):
        return str(carimbo["p1"]), str(carimbo["p2"])
    return rotulos(luta.get("p1_ficha"), luta.get("p2_ficha"),
                   nome1=luta.get("p1"), nome2=luta.get("p2"), armas=armas)


def carimbar(fight: dict, armas: dict | None = None) -> tuple[str, str] | None:
    """Grava ``confronto`` em cada luta do fight que ainda nao tem.

    ``fight["luta"]`` (o que o catalogo le) e cada item de ``fight["lutas"]``
    (o que a edicao le) sao dicts separados depois de um ``json.load``; os
    dois recebem o mesmo rotulo. Devolve o rotulo da luta principal."""
    principal = fight.get("luta") if isinstance(fight, dict) else None
    if not isinstance(principal, dict):
        return None
    l1, l2 = da_luta(principal, armas)
    for luta in [principal, *(fight.get("lutas") or [])]:
        if isinstance(luta, dict) and not (luta.get("confronto") or {}).get("p1"):
            if luta.get("p1") == principal.get("p1") and luta.get("p2") == principal.get("p2"):
                luta["confronto"] = {"p1": l1, "p2": l2}
            else:
                a, b = da_luta(luta, armas)
                luta["confronto"] = {"p1": a, "p2": b}
    return l1, l2


__all__ = ["PERGUNTA", "armas_do_banco", "carimbar", "classe_base", "classe_en",
           "da_luta", "do_par", "esquecer_armas", "rotulo_base", "rotulos"]
