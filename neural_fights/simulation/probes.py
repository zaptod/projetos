"""Sonda de qualidade de luta.

Mede, por luta, o material bruto de "luta interessante": ritmo, drama, origem
do dano e legibilidade de intencao. E a fonte unica das metricas que o
harness (``neural_fights.tools.qualidade_luta``) agrega e compara com os
alvos versionados.

A sonda e passiva por desenho: le contadores que o motor ja incrementa e
drena o ``registro_eventos_dano`` que o proprio ``Lutador`` anota quando uma
lista esta instalada. Ela nunca altera estado de combate — o overhead medido
precisa ficar abaixo de 10% do custo do frame headless.
"""

from __future__ import annotations

import math
from typing import Any

# Janela sem nenhum dano a ninguem que conta como "tempo seco" para o
# espectador. Quatro segundos e mais que o intervalo mediano entre golpes
# medido no baseline (0,93s) por uma ordem de grandeza.
JANELA_SECA = 4.0

# Amostragem da serie de HP usada para trocas de lideranca. Mais fino que
# 0,25s so adiciona ruido; o drama acontece em escala de segundos.
PASSO_HP = 0.25

# Histerese da lideranca: so conta troca quando a vantagem cruza +-5pp de HP.
HISTERESE_LIDERANCA = 0.05

# Os primeiros segundos sao aproximacao; lideranca ali e ruido de spawn.
IGNORAR_LIDERANCA_ATE = 3.0

# Grupos de origem de dano (alvo S3). ``tipo_fonte`` e a etiqueta que o motor
# ja carrega em cada impacto.
_FONTES_BASICAS = frozenset({
    "ataque_corpo_a_corpo",
    "projetil_arma",
    "orbe_arma",
})


def grupo_da_fonte(categoria: str) -> str:
    if categoria in _FONTES_BASICAS:
        return "basico"
    if categoria.endswith("_skill") or categoria in {"beam", "area", "trap"}:
        return "skill"
    if "dot" in categoria or "encant" in categoria:
        return "dot_encanto"
    return "outros"


class _RastreadorDeAcoes:
    """Duracao das intencoes de um lutador (alvo V2), em frames."""

    def __init__(self) -> None:
        self.runs: list[int] = []
        self.frames_por_acao: dict[str, int] = {}
        self._acao_atual: str | None = None
        self._frames_na_acao = 0

    def observar(self, acao: object) -> None:
        acao = str(acao)
        self.frames_por_acao[acao] = self.frames_por_acao.get(acao, 0) + 1
        if acao == self._acao_atual:
            self._frames_na_acao += 1
            return
        if self._acao_atual is not None and self._frames_na_acao > 0:
            self.runs.append(self._frames_na_acao)
        self._acao_atual = acao
        self._frames_na_acao = 1

    def encerrar(self) -> None:
        if self._acao_atual is not None and self._frames_na_acao > 0:
            self.runs.append(self._frames_na_acao)
            self._frames_na_acao = 0


class FightQualityProbe:
    """Coleta uma luta inteira; ``metricas(resultado)`` fecha o relatorio."""

    def __init__(self) -> None:
        self.t = 0.0
        self._fixed_dt = 1.0 / 60.0
        self._sim = None
        self._eventos: list[tuple[float, str, float, str]] = []
        self._serie_hp: list[tuple[float, float, float]] = []
        self._proxima_amostra_hp = 0.0
        self._acoes = {"p1": _RastreadorDeAcoes(), "p2": _RastreadorDeAcoes()}
        self._registros: dict[str, list[tuple[float, str]]] = {}

    # ------------------------------------------------------------------ hooks

    def on_inicio(self, sim) -> None:
        self._sim = sim
        self.t = 0.0
        self._proxima_amostra_hp = 0.0
        # Onda 5C: cobertura de humores e saturacao de momentum — a F2
        # mediu 5/10 humores nunca aparecendo e momentum cravado em -1 em
        # 70% dos frames; estas series vigiam os dois consertos.
        self._humores: dict[str, set] = {"p1": set(), "p2": set()}
        self._momentum_sat = {"p1": 0, "p2": 0}
        self._frames_ia = 0
        # Onda 8A: percepcao de projeteis. Vigia a janela de mundo — se a
        # percepcao for desplugada (ou voltar a ler buffer drenado), a taxa
        # despenca e o alvo A1 acusa.
        self._proj_frames = {"p1": 0, "p2": 0}
        self._proj_vistos = {"p1": 0, "p2": 0}
        # Onda 8E: cobertura do plano de luta (alvo A5).
        self._frames_com_plano = 0
        for slot in ("p1", "p2"):
            lutador = getattr(sim, slot)
            lista: list[tuple[float, str]] = []
            lutador.registro_eventos_dano = lista
            self._registros[slot] = lista
        self._amostrar_hp(sim)

    def on_frame(self, sim, dt: float) -> None:
        self.t += dt
        self._fixed_dt = dt

        for slot in ("p1", "p2"):
            lista = self._registros[slot]
            if lista:
                for dano, categoria in lista:
                    self._eventos.append((self.t, slot, dano, categoria))
                lista.clear()

            brain = getattr(getattr(sim, slot), "brain", None)
            if brain is not None:
                self._acoes[slot].observar(getattr(brain, "acao_atual", ""))
                humor = getattr(brain, "humor", None)
                if humor:
                    self._humores[slot].add(humor)
                if abs(getattr(brain, "momentum", 0.0)) >= 0.95:
                    self._momentum_sat[slot] += 1
                if getattr(brain, "plano", None) is not None:
                    self._frames_com_plano += 1

        self._frames_ia += 1

        # Onda 8A: em frames com projétil hostil no ar, o defensor deve
        # enxergá-lo pela janela de mundo (alvo A1).
        projeteis = getattr(sim, "projeteis", None)
        if projeteis:
            for slot in ("p1", "p2"):
                lutador = getattr(sim, slot)
                tem_hostil = any(
                    getattr(pr, "ativo", True)
                    and getattr(pr, "dono", None) is not lutador
                    for pr in projeteis
                )
                if not tem_hostil:
                    continue
                self._proj_frames[slot] += 1
                percep = getattr(lutador, "percepcao", None)
                if percep is not None and percep.projeteis_hostis(lutador):
                    self._proj_vistos[slot] += 1

        if self.t >= self._proxima_amostra_hp:
            self._amostrar_hp(sim)
            self._proxima_amostra_hp += PASSO_HP

    def _amostrar_hp(self, sim) -> None:
        def razao(lutador) -> float:
            vida_max = max(1e-9, float(lutador.vida_max))
            return max(0.0, float(lutador.vida)) / vida_max

        self._serie_hp.append((self.t, razao(sim.p1), razao(sim.p2)))

    # --------------------------------------------------------------- metricas

    def metricas(self, resultado) -> dict[str, Any]:
        """Fecha a coleta e devolve as metricas da luta.

        ``resultado`` e o ``HeadlessMatchResult`` do runner; a sonda nao
        recalcula o desfecho, so o enriquece.
        """
        for rastreador in self._acoes.values():
            rastreador.encerrar()

        duracao = float(resultado.duration)
        vencedor = resultado.winner_slot
        eventos = self._eventos

        met: dict[str, Any] = {
            "duracao": duracao,
            "vencedor_slot": vencedor,
            "reason": resultado.reason,
            "golpes": len(eventos),
            "primeiro_hit_t": eventos[0][0] if eventos else None,
        }
        met.update(self._metricas_drama(vencedor, resultado))
        met.update(self._metricas_cadencia(duracao))
        met.update(self._metricas_fontes())
        met.update(self._metricas_contadores())
        met.update(self._metricas_acoes())

        # Onda 5C: humores vistos e saturacao de momentum.
        met["humores_vistos"] = sorted(self._humores["p1"] | self._humores["p2"])
        frames = max(1, self._frames_ia)
        met["pct_momentum_saturado"] = (
            self._momentum_sat["p1"] + self._momentum_sat["p2"]
        ) / (2 * frames)

        # Onda 8A: taxa de percepcao de projeteis (None sem projeteis).
        proj_frames = self._proj_frames["p1"] + self._proj_frames["p2"]
        met["taxa_percepcao_projetil"] = (
            (self._proj_vistos["p1"] + self._proj_vistos["p2"]) / proj_frames
            if proj_frames
            else None
        )
        return met

    def _metricas_drama(self, vencedor, resultado) -> dict[str, Any]:
        trocas = 0
        lider = None
        max_deficit_vencedor = 0.0
        hp_min_vencedor = 1.0

        for t, hp1, hp2 in self._serie_hp:
            diff = hp1 - hp2
            if vencedor is not None:
                hp_v = hp1 if vencedor == "p1" else hp2
                hp_o = hp2 if vencedor == "p1" else hp1
                hp_min_vencedor = min(hp_min_vencedor, hp_v)
                max_deficit_vencedor = max(max_deficit_vencedor, hp_o - hp_v)
            if t < IGNORAR_LIDERANCA_ATE:
                continue
            if diff > HISTERESE_LIDERANCA:
                candidato = "p1"
            elif diff < -HISTERESE_LIDERANCA:
                candidato = "p2"
            else:
                continue
            if lider is not None and candidato != lider:
                trocas += 1
            lider = candidato

        hp_final_vencedor = None
        if vencedor is not None:
            hp_final_vencedor = (
                resultado.p1_hp_ratio if vencedor == "p1" else resultado.p2_hp_ratio
            )

        return {
            "lead_changes": trocas,
            "hp_min_vencedor": hp_min_vencedor if vencedor else None,
            "hp_final_vencedor": hp_final_vencedor,
            "max_deficit_vencedor": max_deficit_vencedor if vencedor else None,
        }

    def _metricas_cadencia(self, duracao) -> dict[str, Any]:
        tempos = [t for t, _slot, _dano, _cat in self._eventos]
        marcos = [0.0, *tempos, duracao]
        gaps = [b - a for a, b in zip(marcos, marcos[1:]) if b > a]
        maior_seca = max(gaps) if gaps else duracao
        tempo_seco = sum(g for g in gaps if g > JANELA_SECA)

        intervalos = [b - a for a, b in zip(tempos, tempos[1:]) if b > a]
        cv = None
        if len(intervalos) >= 3:
            media = sum(intervalos) / len(intervalos)
            if media > 0:
                var = sum((x - media) ** 2 for x in intervalos) / len(intervalos)
                cv = math.sqrt(var) / media

        # Janela deslizante de 1s em O(n): uma luta longa com DoT por frame
        # produz milhares de eventos, e o par de ponteiros mantem o custo
        # linear onde a forma ingenua seria quadratica.
        max_share_1s = 0.0
        total = sum(dano for _t, _s, dano, _c in self._eventos)
        if total > 0:
            inicio = 0
            soma_janela = 0.0
            for fim, (t_fim, _s, dano, _c) in enumerate(self._eventos):
                soma_janela += dano
                while self._eventos[inicio][0] <= t_fim - 1.0:
                    soma_janela -= self._eventos[inicio][2]
                    inicio += 1
                max_share_1s = max(max_share_1s, soma_janela / total)

        return {
            "maior_seca": maior_seca,
            "pct_tempo_seco": (tempo_seco / duracao) if duracao > 0 else 0.0,
            "cv_intervalos": cv,
            "max_share_1s": max_share_1s,
        }

    def _metricas_fontes(self) -> dict[str, Any]:
        por_grupo = {"basico": 0.0, "skill": 0.0, "dot_encanto": 0.0, "outros": 0.0}
        por_categoria: dict[str, float] = {}
        for _t, _slot, dano, categoria in self._eventos:
            por_grupo[grupo_da_fonte(categoria)] += dano
            por_categoria[categoria] = por_categoria.get(categoria, 0.0) + dano
        total = sum(por_grupo.values())
        return {
            "dano_total": total,
            "dano_por_grupo": por_grupo,
            "dano_por_categoria": por_categoria,
        }

    def _metricas_contadores(self) -> dict[str, Any]:
        soma = {
            "golpes_melee": 0,
            "criticos_melee": 0,
            "skills_lancadas": 0,
            "anulados_invencibilidade": 0,
            "anulados_invuln_skill": 0,
            "super_armor_absorcoes": 0,
            # Onda 8B/8C: defesa ativa (alvos A2).
            "bloqueios": 0,
            "parries": 0,
            "dashes": 0,
            "desvios_ia": 0,
            # Onda 8D: antecipação e punição (alvos A3/A4).
            "desvios_antecipados": 0,
            "punicoes": 0,
        }
        decisoes = pilha = decisoes_melee = planos = 0
        sim = self._sim
        if sim is not None:
            for slot in ("p1", "p2"):
                lutador = getattr(sim, slot)
                for chave in soma:
                    soma[chave] += lutador.contadores_luta.get(chave, 0)
                brain = getattr(lutador, "brain", None)
                if brain is not None and hasattr(brain, "contadores"):
                    decisoes += brain.contadores.get("decisoes", 0)
                    pilha += brain.contadores.get("pilha_completa", 0)
                    decisoes_melee += brain.contadores.get("decisoes_melee", 0)
                    planos += brain.contadores.get("planos", 0)

        anulados = soma["anulados_invencibilidade"]
        hits = len(self._eventos)
        return {
            **soma,
            "taxa_critico": (
                soma["criticos_melee"] / soma["golpes_melee"]
                if soma["golpes_melee"]
                else None
            ),
            "taxa_anulacao_iframes": (
                anulados / (anulados + hits) if (anulados + hits) else 0.0
            ),
            "decisoes_movimento": decisoes,
            "pilha_completa": pilha,
            "taxa_pilha": (pilha / decisoes) if decisoes else None,
            # Onda 8E (alvo A6): a personalidade decide TAMBÉM em melee.
            "decisoes_melee": decisoes_melee,
            "taxa_decisoes_melee": (
                (decisoes_melee / decisoes) if decisoes else None
            ),
            # Onda 8E (alvo A5): plano de luta vivo.
            "planos_luta": planos,
            "pct_frames_com_plano": (
                self._frames_com_plano / (2 * max(1, self._frames_ia))
            ),
        }

    def _metricas_acoes(self) -> dict[str, Any]:
        runs: list[int] = []
        historicos: dict[str, dict[str, float]] = {}
        for slot, rastreador in self._acoes.items():
            runs.extend(rastreador.runs)
            total_slot = sum(rastreador.frames_por_acao.values())
            historicos[slot] = {
                acao: frames / total_slot
                for acao, frames in rastreador.frames_por_acao.items()
            } if total_slot else {}
        if not runs:
            return {
                "acao_mediana_ms": None,
                "pct_trocas_curtas": None,
                "pct_tempo_intencao_curta": None,
                "acoes_pct_p1": historicos.get("p1", {}),
                "acoes_pct_p2": historicos.get("p2", {}),
            }
        frame_ms = self._fixed_dt * 1000.0
        ordenados = sorted(runs)
        mediana_frames = ordenados[len(ordenados) // 2]
        total_frames = sum(runs)
        curtas = sum(1 for r in runs if r <= 2)
        tempo_curto = sum(r for r in runs if r * frame_ms < 200.0)
        return {
            "acao_mediana_ms": mediana_frames * frame_ms,
            "pct_trocas_curtas": curtas / len(runs),
            "pct_tempo_intencao_curta": (
                tempo_curto / total_frames if total_frames else 0.0
            ),
            "acoes_pct_p1": historicos.get("p1", {}),
            "acoes_pct_p2": historicos.get("p2", {}),
        }


def percentil(valores: list[float], fracao: float) -> float | None:
    """Percentil por interpolacao linear; ``None`` para lista vazia."""
    dados = sorted(v for v in valores if v is not None)
    if not dados:
        return None
    if len(dados) == 1:
        return dados[0]
    posicao = fracao * (len(dados) - 1)
    baixo = int(math.floor(posicao))
    alto = min(baixo + 1, len(dados) - 1)
    peso = posicao - baixo
    return dados[baixo] * (1 - peso) + dados[alto] * peso


__all__ = [
    "FightQualityProbe",
    "HISTERESE_LIDERANCA",
    "JANELA_SECA",
    "grupo_da_fonte",
    "percentil",
]
