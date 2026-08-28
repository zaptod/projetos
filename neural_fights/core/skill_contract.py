# -*- coding: utf-8 -*-
"""Contrato self-describing de cada skill — o "MCP interno" (Onda 11A).

Cada skill declara, num objeto único e queryável, o que o RUNTIME de verdade
faz com ela: geometria correta de cast, categoria de efeito vinda de
``STATUS_RUNTIME`` (nunca listas literais), custos efetivos, gates, combos e
as consequências observáveis que um cast bem-sucedido produz.

Doutrina:
- É um módulo DERIVADO, não um segundo catálogo: funções puras sobre
  ``SKILL_DB`` + ``STATUS_RUNTIME`` + ``CLASSES_DATA``. Não há literal novo
  por skill aqui — campos novos entram no catálogo pelo rito da auditoria.
- Import-safe: sem pygame, sem simulador. O inspetor CLI e a IA consomem o
  MESMO contrato; as heurísticas locais divergentes da estratégia morreram
  na Onda 11A.
- ``consequencia_esperada`` é o oráculo do harness 1-a-1: o teste casta a
  skill num cenário determinístico e exige que pelo menos uma consequência
  declarada aconteça de verdade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from neural_fights.core.skills import SKILL_DB, get_skill_data
from neural_fights.core.status_runtime import (
    STATUS_RUNTIME,
    normalizar_efeito,
)
from neural_fights.models.constants import CLASSES_DATA, KIT_PAPEIS, KIT_POOLS
from neural_fights.utils.config import ALCANCE_CAST_PADRAO


# Categorias de STATUS_RUNTIME que são CONTROLE duro (o alvo perde agência).
CATEGORIAS_CONTROLE = frozenset({"cc", "controle_mental"})

# Limiar padrão de ALVO_BAIXA_VIDA quando o catálogo não declara
# ``condicao_limiar`` (espelha combat.alvo_cumpre_condicao).
CONDICAO_LIMIAR_PADRAO = 0.3

# Condição -> status normalizado que a prepara (None = não é status).
_CONDICAO_STATUS = {
    "ALVO_QUEIMANDO": "QUEIMANDO",
    "ALVO_CONGELADO": "CONGELADO",
    "ALVO_BAIXA_VIDA": None,
}


def _num(valor, padrao=0.0):
    """Número finito ou o padrão (NaN/Inf/None nunca contaminam o contrato)."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return float(padrao)
    if numero != numero or numero in (float("inf"), float("-inf")):
        return float(padrao)
    return numero


def categoria_do_efeito(efeito) -> str:
    """Categoria canônica de STATUS_RUNTIME ('' quando não é status)."""
    if not efeito:
        return ""
    return str(
        STATUS_RUNTIME.get(normalizar_efeito(efeito), {}).get("categoria", "")
    )


@dataclass(frozen=True)
class SkillContract:
    """O que o runtime FAZ com a skill — legível por IA, testes e humanos."""

    # --- identidade ---
    nome: str
    tipo: str
    elemento: str
    descricao: str
    cor: Tuple[int, int, int]
    fontes: Tuple[str, ...]          # ("classe:<Classe>:<PAPEL>", ...) — quem alcança
    # --- geometria (a conta CERTA, não a heurística antiga) ---
    alcance_lancamento: float        # até onde o CAST chega (0 = self-cast)
    raio_efeito: float               # raio do volume que impacta ao aterrissar
    centrado_no_caster: bool
    ancorado_no_alvo: bool           # AREA cai na posição PREVISTA do alvo
    pilares: int
    raio_pilar: float
    velocidade_projetil: float       # 0 = instantâneo/estático
    # --- tempo ---
    cooldown: float
    delay: float                     # telegraph (aviso antes do impacto)
    aviso_visual: bool
    duracao: float
    canalizavel: bool
    imobiliza_caster: bool
    # --- efeito (via STATUS_RUNTIME, nunca listas literais) ---
    efeito: str                      # normalizado ("" quando NORMAL/nenhum)
    categoria_efeito: str            # "" | dot | cc | debuff | controle_mental | especial | transporte
    efeito2: str
    categoria_efeito2: str
    chance_efeito: float             # chance_stun declarada (1.0 = sempre)
    efeito_aleatorio: bool
    # --- custos declarados (efetivos via custo_efetivo/cooldown_efetivo) ---
    custo_mana: float
    custo_vida: float                # absoluto declarado
    custo_vida_percent: float
    # --- gates de cast ---
    condicao: str                    # "" | ALVO_QUEIMANDO | ALVO_CONGELADO | ALVO_BAIXA_VIDA
    condicao_limiar: float           # fração de vida p/ ALVO_BAIXA_VIDA
    condicao_status: str             # status normalizado que prepara a condição ("")
    executa: bool
    # --- combos ---
    combo_apos: Tuple[str, ...]      # skills declaradas como setup DESTA skill
    # --- consequências observáveis (oráculo do harness 1-a-1) ---
    consequencias: frozenset = field(default_factory=frozenset)
    # --- estimativas para a decisão ---
    dano_estimado: float = 0.0

    # Alcance total de ameaça: onde o cast chega + o raio do volume.
    @property
    def alcance_perigo(self) -> float:
        return self.alcance_lancamento + self.raio_efeito

    def to_dict(self) -> Dict:
        """Dump JSON-serializável (o "tools/list" do MCP interno)."""
        return {
            "nome": self.nome,
            "tipo": self.tipo,
            "elemento": self.elemento,
            "descricao": self.descricao,
            "cor": list(self.cor),
            "fontes": list(self.fontes),
            "alcance_lancamento": self.alcance_lancamento,
            "raio_efeito": self.raio_efeito,
            "alcance_perigo": self.alcance_perigo,
            "centrado_no_caster": self.centrado_no_caster,
            "ancorado_no_alvo": self.ancorado_no_alvo,
            "pilares": self.pilares,
            "raio_pilar": self.raio_pilar,
            "velocidade_projetil": self.velocidade_projetil,
            "cooldown": self.cooldown,
            "delay": self.delay,
            "aviso_visual": self.aviso_visual,
            "duracao": self.duracao,
            "canalizavel": self.canalizavel,
            "imobiliza_caster": self.imobiliza_caster,
            "efeito": self.efeito,
            "categoria_efeito": self.categoria_efeito,
            "efeito2": self.efeito2,
            "categoria_efeito2": self.categoria_efeito2,
            "chance_efeito": self.chance_efeito,
            "efeito_aleatorio": self.efeito_aleatorio,
            "custo_mana": self.custo_mana,
            "custo_vida": self.custo_vida,
            "custo_vida_percent": self.custo_vida_percent,
            "condicao": self.condicao,
            "condicao_limiar": self.condicao_limiar,
            "condicao_status": self.condicao_status,
            "executa": self.executa,
            "combo_apos": list(self.combo_apos),
            "consequencias": sorted(self.consequencias),
            "dano_estimado": self.dano_estimado,
        }


# ---------------------------------------------------------------------------
# Derivação
# ---------------------------------------------------------------------------

def _fontes_da_skill(nome: str) -> Tuple[str, ...]:
    """Onde a skill é alcançável hoje: POOL de qual classe, em qual papel.

    Onda 11C: a fonte é o ``KIT_POOLS`` (o kit fixo é a primeira opção de
    cada papel); classes sem pool caem no ``skills_afinidade``.
    """
    fontes = []
    for classe, dados in CLASSES_DATA.items():
        pools = KIT_POOLS.get(classe)
        if pools:
            for papel in KIT_PAPEIS:
                if nome in (pools.get(papel) or ()):
                    fontes.append(f"classe:{classe}:{papel}")
            continue
        kit = dados.get("skills_afinidade") or []
        for idx, skill_nome in enumerate(kit):
            if skill_nome == nome:
                papel = KIT_PAPEIS[idx] if idx < len(KIT_PAPEIS) else f"SLOT{idx}"
                fontes.append(f"classe:{classe}:{papel}")
    return tuple(fontes)


def _geometria(data: Dict, tipo: str) -> Tuple[float, float, bool, bool, float]:
    """(alcance_lancamento, raio_efeito, centrado, ancorado, velocidade)."""
    centrado = bool(data.get("centrado_no_caster", False))
    if tipo == "PROJETIL":
        vel = max(0.0, _num(data.get("velocidade"), 10.0))
        vida = max(0.0, _num(data.get("vida"), 1.5))
        if vel > 0.0 and vida > 0.0:
            alcance = vel * vida * 0.8
        else:
            # Projétil estacionário nasce à frente do conjurador e só
            # atinge em contato — zero não significa alcance ilimitado.
            alcance = max(1.25, _num(data.get("alcance")))
        raio = max(0.0, _num(data.get("raio"), 0.3))
        if _num(data.get("raio_explosao")) > 0.0:
            raio = max(raio, _num(data.get("raio_explosao")))
        return alcance, raio, False, False, vel
    if tipo == "AREA":
        raio = max(0.0, _num(data.get("raio_area"), 2.0))
        if centrado:
            return 0.0, raio, True, False, 0.0
        # O runtime lança a área na posição PREVISTA do alvo, clampada em
        # alcance_cast (entities._ponto_alvo_area) — a geometria REAL.
        alcance = max(0.0, _num(data.get("alcance_cast"), ALCANCE_CAST_PADRAO))
        return alcance, raio, False, True, 0.0
    if tipo in ("BEAM", "CHANNEL"):
        return max(0.0, _num(data.get("alcance"), 6.0)), 0.0, False, False, 0.0
    if tipo == "DASH":
        return max(0.0, _num(data.get("distancia"), 4.0)), 0.0, False, False, 0.0
    # BUFF / SUMMON / TRAP / TRANSFORM: no próprio conjurador.
    return 0.0, 0.0, True, False, 0.0


def _dano_estimado(data: Dict, tipo: str) -> float:
    """Potencial ofensivo declarado (a MESMA conta da estratégia, uma vez só).

    CHANNEL consome somente DPS no runtime; um eventual campo ``dano`` é
    inerte e não pode inflar o plano da IA.
    """
    dano_base = max(0.0, _num(data.get("dano")))
    if tipo == "CHANNEL":
        duracao = max(0.0, _num(data.get("duracao_max"), 3.0))
        return max(0.0, _num(data.get("dano_por_segundo"))) * duracao
    if tipo == "SUMMON":
        duracao = max(0.0, _num(data.get("duracao"), 10.0))
        return max(0.0, _num(data.get("summon_dano"), 10.0)) * duracao * 0.5

    total = dano_base
    duracao = max(0.0, _num(data.get("duracao"), 3.0))
    total += max(0.0, _num(data.get("dano_tick"))) * duracao
    total += max(0.0, _num(data.get("dano_por_segundo"))) * duracao

    multi_shot = max(1, int(_num(data.get("multi_shot"), 1)))
    ondas = max(1, int(_num(data.get("ondas"), 1)))
    total *= multi_shot * ondas

    meteoros = max(0, int(_num(data.get("meteoros_aleatorios"))))
    if meteoros:
        total += meteoros * max(0.0, _num(data.get("dano_meteoro"), dano_base))

    # Pilar: dano/2 por pilar (doutrina Onda 11B); estimativa = âncora
    # garantida + um acerto esperado da coroa.
    pilares = max(0, int(_num(data.get("pilares"))))
    if pilares > 1:
        total = dano_base  # âncora (dano/2) + ~1 acerto esperado (dano/2)

    # ``chain``: cada salto herda o dano já decaído do segmento anterior.
    saltos = max(0, int(_num(data.get("chain"))))
    decay = max(0.0, _num(data.get("chain_decay"), 0.8))
    dano_salto = dano_base
    for _ in range(saltos):
        dano_salto *= decay
        total += dano_salto
    return total


def _consequencias(data: Dict, tipo: str, categoria: str, categoria2: str) -> frozenset:
    """Consequências OBSERVÁVEIS que um cast bem-sucedido produz."""
    con = set()
    efeito = normalizar_efeito(data.get("efeito")) if data.get("efeito") else ""

    if tipo == "PROJETIL":
        con.add("objeto:projetil")
    elif tipo == "AREA":
        con.add("objeto:area")
    elif tipo == "BEAM":
        con.add("canalizacao" if data.get("canalizavel") else "objeto:beam")
    elif tipo == "SUMMON":
        con.add("objeto:summon")
    elif tipo == "TRAP":
        con.add("objeto:trap")
    elif tipo == "DASH":
        con.add("deslocamento:dash")
    elif tipo == "BUFF":
        # "buff" = um estado persistente no conjurador. Curas/purgas
        # instantâneas têm outras consequências (cura), não um buff ativo.
        persistente = any(
            data.get(campo)
            for campo in (
                "duracao", "efeito_buff", "buff_dano", "buff_velocidade",
                "bonus_dano", "bonus_dano_magico", "bonus_area",
                "bonus_velocidade", "bonus_velocidade_ataque",
                "bonus_velocidade_movimento", "escudo", "reflete_dano",
                "reflete_projeteis", "reflete_skills", "refletir",
                "esquiva_garantida", "ve_ataques", "voo", "imune_debuffs",
                "dano_contato", "consome_ao_causar_dano", "stats_aleatorios",
                "sem_cooldown", "custo_mana_metade", "cura_tick",
            )
        )
        if persistente:
            con.add("buff")
    elif tipo == "TRANSFORM":
        con.add("transformacao")
    elif tipo == "CHANNEL":
        con.add("canalizacao")

    if data.get("cria_portal"):
        con.add("objeto:portal")
    dano_de_summon = _num(data.get("summon_dano")) > 0 and not data.get(
        "copia_caster"
    )  # a cópia ECOA os ataques do dono — dano condicional, não do cast
    if _num(data.get("dano")) > 0 or _num(data.get("dano_por_segundo")) > 0 or \
            _num(data.get("dano_tick")) > 0 or dano_de_summon:
        con.add("dano")
    if categoria == "dot" or categoria2 == "dot":
        con.add("dot")
    for cat, ef in ((categoria, efeito),
                    (categoria2, normalizar_efeito(data.get("efeito2"))
                     if data.get("efeito2") else "")):
        # Transporte (PUXADO/VORTEX/TROCAR_POS) não é status persistente: o
        # deslocamento físico É a consequência, já declarada abaixo.
        if cat and ef and cat != "transporte":
            con.add(f"status:{ef}")
    if data.get("efeito_aleatorio"):
        con.add("status:ALEATORIO")
    if efeito == "EMPURRAO" or _num(data.get("forca_empurrao")) > 0:
        con.add("deslocamento:empurra")
    if efeito in ("PUXADO", "VORTEX") or data.get("puxa_para_centro") or \
            data.get("puxa_continuo"):
        con.add("deslocamento:puxa")
    if efeito == "TROCAR_POS":
        con.add("deslocamento:troca")
    if data.get("ground"):
        con.add("terreno")
    if data.get("bloqueia_projeteis"):
        con.add("bloqueio_projeteis")
    if data.get("bloqueia_movimento"):
        con.add("bloqueio_movimento")
    if any(_num(data.get(c)) > 0 for c in (
            "cura", "cura_por_segundo", "cura_tick", "cura_percent")):
        con.add("cura")
    if _num(data.get("escudo")) > 0:
        con.add("escudo")
    # Lifesteal em BUFF/TRANSFORM só cura quando o dono acertar depois —
    # consequência condicional, não do cast em si.
    if _num(data.get("lifesteal")) > 0 and tipo not in ("BUFF", "TRANSFORM"):
        con.add("cura")
    return frozenset(con)


def derivar_contrato(nome: str) -> SkillContract:
    """Deriva o contrato completo de uma skill do catálogo."""
    return derivar_contrato_de_data(nome, get_skill_data(nome))


def derivar_contrato_de_data(nome: str, data: Dict) -> SkillContract:
    """Deriva o contrato de um registro explícito (testes e hipóteses usam
    registros fora do catálogo; a derivação é a mesma)."""
    tipo = str(data.get("tipo", "NADA"))

    alcance, raio, centrado, ancorado, vel = _geometria(data, tipo)

    efeito_bruto = data.get("efeito")
    efeito = normalizar_efeito(efeito_bruto) if efeito_bruto else ""
    if efeito == "NORMAL":
        efeito = ""
    categoria = categoria_do_efeito(efeito) if efeito else ""
    efeito2_bruto = data.get("efeito2")
    efeito2 = normalizar_efeito(efeito2_bruto) if efeito2_bruto else ""
    categoria2 = categoria_do_efeito(efeito2) if efeito2 else ""

    condicao = str(data.get("condicao") or "")
    condicao_status = _CONDICAO_STATUS.get(condicao) or ""

    canalizavel = bool(data.get("canalizavel", False))

    return SkillContract(
        nome=nome,
        tipo=tipo,
        elemento=str(data.get("elemento") or ""),
        descricao=str(data.get("descricao") or ""),
        cor=tuple(data.get("cor", (255, 255, 255)))[:3],
        fontes=_fontes_da_skill(nome),
        alcance_lancamento=alcance,
        raio_efeito=raio,
        centrado_no_caster=centrado,
        ancorado_no_alvo=ancorado,
        pilares=max(0, int(_num(data.get("pilares")))),
        raio_pilar=max(0.0, _num(data.get("raio_pilar"), 0.75))
        if _num(data.get("pilares")) > 0 else 0.0,
        velocidade_projetil=vel,
        cooldown=max(0.0, _num(data.get("cooldown"), 5.0)),
        delay=max(0.0, _num(data.get("delay"))),
        aviso_visual=bool(data.get("aviso_visual", _num(data.get("delay")) > 0)),
        duracao=max(
            0.0,
            _num(
                data.get("duracao_max")
                if tipo == "CHANNEL"
                else data.get("duracao")
            ),
        ),
        canalizavel=canalizavel,
        imobiliza_caster=bool(data.get("imobiliza", False)),
        efeito=efeito,
        categoria_efeito=categoria,
        efeito2=efeito2,
        categoria_efeito2=categoria2,
        chance_efeito=min(1.0, max(0.0, _num(data.get("chance_stun"), 1.0))),
        efeito_aleatorio=bool(data.get("efeito_aleatorio", False)),
        custo_mana=max(0.0, _num(data.get("custo"), 15.0)),
        custo_vida=max(0.0, _num(data.get("custo_vida"))),
        custo_vida_percent=max(0.0, _num(data.get("custo_vida_percent"))),
        condicao=condicao,
        condicao_limiar=min(
            1.0,
            max(0.0, _num(data.get("condicao_limiar"), CONDICAO_LIMIAR_PADRAO)),
        ),
        condicao_status=condicao_status,
        executa=bool(data.get("executa", False)),
        combo_apos=tuple(str(s) for s in (data.get("combo_apos") or ())),
        consequencias=_consequencias(data, tipo, categoria, categoria2),
        dano_estimado=_dano_estimado(data, tipo),
    )


_CACHE_CONTRATOS: Optional[Dict[str, SkillContract]] = None


def catalogo_de_contratos() -> Dict[str, SkillContract]:
    """Contratos de TODAS as skills do catálogo (cache de processo)."""
    global _CACHE_CONTRATOS
    if _CACHE_CONTRATOS is None:
        _CACHE_CONTRATOS = {
            nome: derivar_contrato(nome)
            for nome in SKILL_DB
            if nome != "Nenhuma"
        }
    return _CACHE_CONTRATOS


def limpar_cache_contratos() -> None:
    """Para testes que mutam SKILL_DB (o catálogo real nunca muda em jogo)."""
    global _CACHE_CONTRATOS
    _CACHE_CONTRATOS = None


# ---------------------------------------------------------------------------
# Custos efetivos (a conta que o runtime REALMENTE cobra)
# ---------------------------------------------------------------------------

def custo_efetivo(custo_base, lutador, *, origem="classe", esperado=False):
    """Custo de mana que o cast vai cobrar DE VERDADE.

    Espelha usar_skill_arma/usar_skill_classe: Mago ×0,8 e o modificador de
    buff são determinísticos e entram sempre; a passiva ``no_mana_cost`` (só
    skills de ARMA) é sorteio — por padrão NÃO desconta (gate seguro), e com
    ``esperado=True`` entra como valor esperado (nunca sorteio na decisão).
    """
    custo = max(0.0, _num(custo_base))
    classe = str(getattr(lutador, "classe_nome", "") or "")
    if "Mago" in classe:
        custo *= 0.8
    mod = getattr(lutador, "_get_modificador_mana_custo_buff", None)
    if callable(mod):
        try:
            custo *= max(0.0, float(mod()))
        except (TypeError, ValueError):
            pass
    if esperado and origem == "arma":
        passiva = getattr(lutador, "arma_passiva", None) or {}
        if passiva.get("efeito") == "no_mana_cost":
            chance = max(0.0, min(1.0, _num(passiva.get("valor")) / 100.0))
            custo *= 1.0 - chance
    return custo


def cooldown_efetivo(cooldown_base, lutador, *, origem="classe"):
    """Cooldown que o cast vai gravar DE VERDADE (buffs + passiva de arma)."""
    cd = max(0.0, _num(cooldown_base))
    mod = getattr(lutador, "_get_modificador_cooldown_buff", None)
    if callable(mod):
        try:
            cd *= max(0.0, float(mod()))
        except (TypeError, ValueError):
            pass
    if origem == "arma":
        passiva = getattr(lutador, "arma_passiva", None) or {}
        if passiva.get("efeito") == "cooldown":
            cd *= 1.0 - max(0.0, min(1.0, _num(passiva.get("valor")) / 100.0))
    return cd


def custo_vida_do_cast(contrato_ou_data, vida_max) -> float:
    """Custo de vida com a precedência do runtime (absoluto > percentual)."""
    if isinstance(contrato_ou_data, SkillContract):
        absoluto = contrato_ou_data.custo_vida
        percentual = contrato_ou_data.custo_vida_percent
    else:
        absoluto = max(0.0, _num(contrato_ou_data.get("custo_vida")))
        percentual = max(0.0, _num(contrato_ou_data.get("custo_vida_percent")))
    if absoluto > 0.0:
        return absoluto
    return percentual * max(0.0, _num(vida_max))


__all__ = [
    "CATEGORIAS_CONTROLE",
    "CONDICAO_LIMIAR_PADRAO",
    "SkillContract",
    "catalogo_de_contratos",
    "categoria_do_efeito",
    "cooldown_efetivo",
    "custo_efetivo",
    "custo_vida_do_cast",
    "derivar_contrato",
    "derivar_contrato_de_data",
    "limpar_cache_contratos",
]
