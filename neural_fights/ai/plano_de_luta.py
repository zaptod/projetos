# -*- coding: utf-8 -*-
"""Plano de luta (Onda 10C): a intenção tática vira OBJETO visível.

Até a 8E o plano era um dict ``{tipo, expira_em, compromisso}`` que só
enviesava a proposta de movimento em parte das decisões. Aqui ele ganha:

- ``rotulo``: o que o espectador lê sob o lutador ("PRESSÃO", "ISCA"...);
- ``verbos``: o conjunto de ações que SERVEM ao plano (a pilha de
  personalidade escolhe dentro dele; a variação anti-repetição também);
- ``objetivo`` com ``sucesso``/``falha``: o plano termina quando cumpre ou
  fracassa, não só quando o relógio expira (``progresso`` 0-1 para o HUD);
- planos ADAPTATIVOS, escolhidos pelo que o lutador OBSERVA no oponente
  (guarda repetida, fuga, HP baixo, parede) — sem telepatia.

Compatibilidade: ``PlanoDeLuta`` responde a ``plano["tipo"]``,
``"tipo" in plano`` e ``plano.get(...)`` como o dict antigo.

Tudo aqui é puro (sem RNG): quem sorteia é o brain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class PlanoDeLuta:
    tipo: str
    expira_em: float
    compromisso: float
    inicio: float = 0.0
    rotulo: str = ""
    verbos: tuple = ()
    adaptativo: bool = False
    objetivo: str = ""
    progresso: float = 0.0
    encerrado_por: Optional[str] = None
    punicoes_inicio: int = 0
    marcadores: dict = field(default_factory=dict)

    # --- compat com o dict da 8E -------------------------------------
    def __getitem__(self, chave):
        try:
            return getattr(self, chave)
        except AttributeError:
            raise KeyError(chave) from None

    def __setitem__(self, chave, valor):
        setattr(self, chave, valor)

    def __contains__(self, chave):
        return hasattr(self, chave)

    def get(self, chave, padrao=None):
        return getattr(self, chave, padrao)


@dataclass
class ContextoPlano:
    """O que o plano precisa saber para julgar a si mesmo — só deltas desde
    o início do plano e estado observável."""

    tempo: float = 0.0            # segundos desde o início do plano
    distancia: float = 999.0
    alcance: float = 1.5          # alcance efetivo do próprio golpe
    hp: float = 1.0
    hp_inimigo: float = 1.0
    hp_delta: float = 0.0         # hp agora - hp no início
    medo: float = 0.0
    hits_dados: int = 0           # hits reais conectados desde o início
    punicoes: int = 0
    agarroes: int = 0
    wall_splats: int = 0
    skills: int = 0
    oponente_contra_parede: bool = False
    inimigo_morto: bool = False


@dataclass(frozen=True)
class DefinicaoPlano:
    rotulo: str
    verbos: tuple
    adaptativo: bool = False
    objetivo: str = ""
    sucesso: Optional[Callable[[ContextoPlano], bool]] = None
    falha: Optional[Callable[[ContextoPlano], bool]] = None
    progresso: Optional[Callable[[ContextoPlano], float]] = None
    # Antes disso o plano não pode terminar por sucesso/falha — evita que
    # um hit de sorte no primeiro frame encerre a intenção (alvo A5).
    min_duracao: float = 1.2


def _hits(n):
    return lambda c: c.hits_dados >= n


def _prog_hits(n):
    return lambda c: min(1.0, c.hits_dados / float(n))


DEFINICOES: dict[str, DefinicaoPlano] = {
    "PRESSIONAR": DefinicaoPlano(
        "PRESSÃO",
        ("PRESSIONAR", "APROXIMAR", "MATAR", "ATAQUE_RAPIDO", "FLANQUEAR",
         "ESMAGAR", "COMBATE"),
        objetivo="conectar 2 golpes",
        sucesso=_hits(2), progresso=_prog_hits(2),
    ),
    "BAITAR_E_PUNIR": DefinicaoPlano(
        "ISCA",
        ("POKE", "CIRCULAR", "COMBATE", "RECUAR", "BLOQUEAR", "CONTRA_ATAQUE"),
        objetivo="punir um whiff",
        sucesso=lambda c: c.punicoes >= 1,
        progresso=lambda c: min(1.0, float(c.punicoes)),
    ),
    "MANTER_ZONA_MORTA": DefinicaoPlano(
        "ZONA MORTA",
        ("APROXIMAR", "PRESSIONAR", "MATAR", "COMBATE", "ATAQUE_RAPIDO",
         "CIRCULAR"),
        objetivo="golpear de dentro da zona morta",
        sucesso=_hits(2), progresso=_prog_hits(2),
    ),
    "LEVAR_PARA_PAREDE": DefinicaoPlano(
        "PRA PAREDE",
        ("PRESSIONAR", "FLANQUEAR", "APROXIMAR", "MATAR", "ATAQUE_RAPIDO"),
        objetivo="encurralar",
        sucesso=lambda c: c.oponente_contra_parede,
        progresso=lambda c: 1.0 if c.oponente_contra_parede else 0.3,
    ),
    "CACAR_JANELA_SKILL": DefinicaoPlano(
        "JANELA",
        ("RECUAR", "CIRCULAR", "POKE", "COMBATE", "APROXIMAR"),
        objetivo="lançar uma skill",
        sucesso=lambda c: c.skills >= 1,
        progresso=lambda c: min(1.0, float(c.skills)),
    ),
    "RECUPERAR": DefinicaoPlano(
        "RECUPERAR",
        ("RECUAR", "CIRCULAR", "POKE", "BLOQUEAR", "FUGIR", "DESVIO"),
        objetivo="abrir distância ou recuperar vida",
        sucesso=lambda c: c.hp_delta >= 0.05 or c.distancia > 6.0,
        progresso=lambda c: max(min(1.0, c.hp_delta / 0.05), min(1.0, c.distancia / 6.0)),
    ),
    # ---- adaptativos (nascem do que o lutador OBSERVA) ----
    "QUEBRAR_GUARDA": DefinicaoPlano(
        "QUEBRAR GUARDA",
        ("PRESSIONAR", "APROXIMAR", "ESMAGAR", "MATAR", "FLANQUEAR"),
        adaptativo=True, objetivo="furar a guarda (pesado ou agarrão)",
        sucesso=lambda c: c.hits_dados >= 1 or c.agarroes >= 1,
        falha=lambda c: c.tempo > 3.0,
        progresso=lambda c: min(1.0, c.hits_dados + c.agarroes + c.tempo / 3.0 * 0.5),
    ),
    "CORTAR_FUGA": DefinicaoPlano(
        "CORTAR FUGA",
        ("PRESSIONAR", "APROXIMAR", "FLANQUEAR", "ATAQUE_RAPIDO"),
        adaptativo=True, objetivo="fechar a distância de quem foge",
        sucesso=lambda c: c.distancia <= c.alcance * 1.2,
        falha=lambda c: c.tempo > 4.0,
        progresso=lambda c: max(0.0, min(1.0, 1.0 - (c.distancia - c.alcance) / 6.0)),
    ),
    "TROCAR_GOLPES": DefinicaoPlano(
        "TROCAÇÃO",
        ("MATAR", "ATAQUE_RAPIDO", "COMBATE", "CONTRA_ATAQUE", "PRESSIONAR"),
        adaptativo=True, objetivo="trocar na cara",
        sucesso=_hits(2),
        falha=lambda c: c.hp_delta <= -0.15 and c.hits_dados == 0,
        progresso=_prog_hits(2),
    ),
    "ACABAR": DefinicaoPlano(
        "ACABAR",
        ("MATAR", "PRESSIONAR", "ATAQUE_RAPIDO", "ESMAGAR", "APROXIMAR"),
        adaptativo=True, objetivo="nocaute",
        sucesso=lambda c: c.inimigo_morto,
        falha=lambda c: c.hp < 0.2 and c.medo > 0.5,
        progresso=lambda c: max(0.0, min(1.0, 1.0 - c.hp_inimigo / 0.25)),
        min_duracao=0.6,
    ),
    "ESMAGAR_NA_PAREDE": DefinicaoPlano(
        "ESMAGAR",
        ("PRESSIONAR", "ESMAGAR", "MATAR", "ATAQUE_RAPIDO"),
        adaptativo=True, objetivo="estatelar na parede",
        sucesso=lambda c: c.wall_splats >= 1 or c.hits_dados >= 1,
        falha=lambda c: (not c.oponente_contra_parede) and c.tempo > 1.5,
        progresso=lambda c: min(1.0, c.wall_splats + c.hits_dados * 0.5),
    ),
}

TIPOS_ADAPTATIVOS = frozenset(t for t, d in DEFINICOES.items() if d.adaptativo)


def criar_plano(tipo, tempo, duracao, compromisso, marcadores=None,
                punicoes_inicio=0) -> PlanoDeLuta:
    definicao = DEFINICOES.get(tipo)
    return PlanoDeLuta(
        tipo=tipo,
        expira_em=tempo + duracao,
        compromisso=compromisso,
        inicio=tempo,
        rotulo=definicao.rotulo if definicao else str(tipo),
        verbos=tuple(definicao.verbos) if definicao else (),
        adaptativo=bool(definicao.adaptativo) if definicao else False,
        objetivo=definicao.objetivo if definicao else "",
        punicoes_inicio=int(punicoes_inicio),
        marcadores=dict(marcadores or {}),
    )


def avaliar(plano: PlanoDeLuta, ctx: ContextoPlano, permitir_fim=True):
    """Atualiza ``plano.progresso`` e devolve ``"sucesso"``, ``"falha"`` ou
    ``None``. Puro: não mexe em mais nada."""
    definicao = DEFINICOES.get(getattr(plano, "tipo", None))
    if definicao is None:
        return None
    if definicao.progresso is not None:
        try:
            plano.progresso = max(0.0, min(1.0, float(definicao.progresso(ctx))))
        except Exception:
            plano.progresso = 0.0
    if not permitir_fim or ctx.tempo < definicao.min_duracao:
        return None
    if definicao.sucesso is not None and definicao.sucesso(ctx):
        plano.progresso = 1.0
        return "sucesso"
    if definicao.falha is not None and definicao.falha(ctx):
        return "falha"
    return None


__all__ = [
    "ContextoPlano",
    "DEFINICOES",
    "DefinicaoPlano",
    "PlanoDeLuta",
    "TIPOS_ADAPTATIVOS",
    "avaliar",
    "criar_plano",
]
