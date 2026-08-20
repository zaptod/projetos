"""Traducao de um comando aprovado em mutacao do motor.

Toda funcao aqui usa **exatamente** as chamadas que o proprio motor usa quando
uma skill e conjurada. Isso nao e economia de codigo, e a propriedade central do
desenho: um efeito de gift entra pelos mesmos buffers e pela mesma API de
dominio, entao ele e drenado pela primeira fase do frame junto com o que a IA
produziu. Nao existe caminho paralelo de combate para manter em sincronia.

O momento da chamada tambem importa. ``LiveSession`` aplica comandos **antes**
de ``sim.update(dt)``: o mundo esta como ``desenhar()`` acabou de mostrar, e o
que for escrito nos buffers e consumido por ``_coletar_buffers_dos_lutadores``
no mesmo frame.

Regras que este modulo nunca quebra:

* nunca faz ``append`` direto em ``sim.areas``/``sim.projeteis`` -- essas listas
  estao sendo iteradas dentro das fases do frame;
* nunca chama ``recarregar_tudo()`` no meio do frame;
* nunca constroi dano com atacante ``None``, o que quebraria credito de abate.
"""

from __future__ import annotations

import logging
import math

from neural_fights.core.combat import AreaEffect, Buff, Projetil
from neural_fights.core.skills import get_skill_data
from neural_fights.live.catalog import get_command

logger = logging.getLogger(__name__)


class EfeitoIndisponivel(RuntimeError):
    """O comando e valido, mas o mundo nao permite aplica-lo agora."""


def _vivo(lutador) -> bool:
    return lutador is not None and not getattr(lutador, "morto", True)


def aplicar(simulador, command_id: str, *, alvo=None) -> str:
    """Executa um comando ja aprovado pela politica.

    ``alvo`` e obrigatorio para escopo ``ALVO``. Devolve um detalhe curto para o
    journal. Levanta ``EfeitoIndisponivel`` quando o mundo mudou entre a decisao
    e a aplicacao -- lutador morreu, round acabou --, caso em que quem chama
    decide adiar ou reembolsar.
    """
    dados = get_command(command_id)
    verbo = dados["efeito"]

    if dados["escopo"] == "ALVO":
        if not _vivo(alvo):
            raise EfeitoIndisponivel("alvo indisponivel")
        return _APLICADORES_ALVO[verbo](alvo, dados)

    if dados["escopo"] == "GLOBAL":
        return _aplicar_global(simulador, dados)

    raise EfeitoIndisponivel(f"escopo {dados['escopo']} nao e aplicado no round")


# ------------------------------------------------------------- escopo ALVO


def _buff_skill(alvo, dados) -> str:
    """Delegado inteiro ao motor: cura, limpeza e imunidade vem de la."""
    nome_skill = dados["skill"]
    aplicado = alvo._aplicar_buff_skill(nome_skill, get_skill_data(nome_skill), Buff)
    if not aplicado:
        raise EfeitoIndisponivel(f"skill recusada pelo alvo: {nome_skill}")
    return nome_skill


def _limpar_debuff(alvo, _dados) -> str:
    removidas = alvo.remover_debuffs()
    return f"debuffs_removidos={len(removidas)}"


def _projetil_skill(alvo, dados) -> str:
    """Dispara na direcao que o lutador ja encara, como o motor faz."""
    nome_skill = dados["skill"]
    rad = math.radians(alvo.angulo_olhar)
    spawn_x = alvo.pos[0] + math.cos(rad) * 0.6
    spawn_y = alvo.pos[1] + math.sin(rad) * 0.6
    alvo.buffer_projeteis.append(
        Projetil(nome_skill, spawn_x, spawn_y, alvo.angulo_olhar, alvo)
    )
    return nome_skill


_APLICADORES_ALVO = {
    "BUFF_SKILL": _buff_skill,
    "LIMPAR_DEBUFF": _limpar_debuff,
    "PROJETIL_SKILL": _projetil_skill,
}


# ----------------------------------------------------------- escopo GLOBAL


def _aplicar_global(simulador, dados) -> str:
    """Instancia a area uma vez por lutador, no ponto medio entre os dois.

    ``AreaEffect`` exclui o proprio dono por padrao (``afeta_caster`` e falso em
    todo o catalogo). Duas instancias espelhadas fazem cada lutador ser atingido
    pela area do outro: o efeito e simetrico, ninguem recebe credito de abate
    que nao lutou, e nenhuma entrada nova precisa ser criada no ``SKILL_DB``.
    """
    if dados["efeito"] != "AREA_SKILL":
        raise EfeitoIndisponivel(f"verbo {dados['efeito']} nao suporta escopo GLOBAL")

    lutadores = [p for p in (simulador.p1, simulador.p2) if _vivo(p)]
    if len(lutadores) < 2:
        raise EfeitoIndisponivel("caos exige os dois lutadores vivos")

    nome_skill = dados["skill"]
    centro_x = sum(p.pos[0] for p in lutadores) / len(lutadores)
    centro_y = sum(p.pos[1] for p in lutadores) / len(lutadores)

    for dono in lutadores:
        dono.buffer_areas.append(AreaEffect(nome_skill, centro_x, centro_y, dono))
    return f"{nome_skill} x{len(lutadores)}"


def resolver_alvo(simulador, slot: str):
    """Converte ``p1``/``p2`` no lutador correspondente."""
    slot = str(slot or "").strip().lower()
    if slot == "p1":
        return simulador.p1
    if slot == "p2":
        return simulador.p2
    return None


def slot_de(simulador, lutador) -> str | None:
    if lutador is simulador.p1:
        return "p1"
    if lutador is simulador.p2:
        return "p2"
    return None


def contar_areas_vivas(simulador) -> int:
    """Estado vivo usado pelo teto de saturacao da politica."""
    return len(getattr(simulador, "areas", ()) or ())


__all__ = [
    "EfeitoIndisponivel",
    "aplicar",
    "contar_areas_vivas",
    "resolver_alvo",
    "slot_de",
]
