# -*- coding: utf-8 -*-
"""Motor único de emoções da IA (revivido na Onda 5C).

Este arquivo existiu completo e nunca foi instanciado — 234 linhas mortas
enquanto o ``AIBrain`` mantinha uma CÓPIA divergente do mesmo estado. Na
Onda 5C ele vira o dono único do estado emocional: o brain delega leitura
e escrita via properties (``brain.medo`` etc.), então os dezenas de
escritores espalhados (quirks, presets, reações) seguem funcionando.

Semânticas consertadas aqui (medidas pela investigação da Frente 2):

- **medo contínuo**: era interruptor binário (0,00 ou 1,00) — ganho só
  abaixo de zonas de HP e ZERADO por nome de traço (DETERMINADO/FRIO).
  Agora persegue um alvo em gradiente, e coragem é multiplicador por eixo
  (frieza alta ≈ ×0,3-0,5), nunca zero.
- **frustração alcançável**: só crescia APANHANDO (+0,1/hit) e tinha teto
  matemático ~0,27 com threshold de humor em 0,5. Frustração é não
  conseguir BATER: cresce com seca ofensiva, alivia ao acertar.
- **tédio alcançável**: ganho 0,6/s vs decay 0,6/s — empate eterno. Agora
  cresce com silêncio bilateral (ninguém bate em ninguém).
- **escada de humor**: DESESPERADO era penúltimo na escada e nunca vencia
  (FURIOSO/ASSUSTADO capturavam antes em HP baixo); BERSERK/EUFORICO/
  GLACIAL existiam no catálogo sem produtor nenhum.

Contratos de integração: os timers (``tempo_desde_*``) e o
``cd_mudanca_humor`` TICAM no passo de cooldowns do brain (via delegação);
``atualizar()`` daqui só faz a física emocional. Identidade (traços,
perfil de eixos, rng, lutador) é lida AO VIVO do brain — o motor não
guarda cópias que envelhecem.
"""

import random

__all__ = ["EmotionSystem"]


class EmotionSystem:
    """Dono único do estado emocional de um ``AIBrain``."""

    def __init__(self, brain):
        self._brain = brain

        # === EMOÇÕES (0.0 a 1.0) ===
        self.medo = 0.0
        self.raiva = 0.0
        self.confianca = 0.5
        self.frustracao = 0.0
        self.adrenalina = 0.0
        self.excitacao = 0.0
        self.tedio = 0.0

        # === HUMOR ===
        self.humor = "CALMO"
        self.cd_mudanca_humor = 0.0

        # === MEMÓRIA DE COMBATE ===
        self.hits_recebidos_total = 0
        self.hits_dados_total = 0
        self.hits_recebidos_recente = 0
        self.hits_dados_recente = 0
        self.tempo_desde_dano = 5.0
        self.tempo_desde_hit = 5.0
        self.combo_atual = 0
        self.max_combo = 0

    # ------------------------------------------------------------ identidade
    # Lida ao vivo do brain: o motor nunca guarda cópia que envelhece.

    @property
    def rng(self):
        return getattr(self._brain, "rng", random)

    @property
    def tracos(self):
        return getattr(self._brain, "tracos", [])

    @property
    def perfil(self):
        perfil = getattr(self._brain, "perfil", None)
        return perfil if perfil is not None else {}

    @property
    def parent(self):
        return getattr(self._brain, "parent", None)

    # --------------------------------------------------------------- física

    def atualizar(self, dt, distancia, inimigo, tempo_combate):
        """Física emocional de um frame (timers/cds ticam no brain)."""
        p = self.parent
        if p is None:
            return
        hp_pct = p.vida / p.vida_max if p.vida_max > 0 else 1.0
        inimigo_hp_pct = (
            inimigo.vida / inimigo.vida_max
            if getattr(inimigo, "vida_max", 0) > 0
            else 1.0
        )
        perfil = self.perfil
        frieza = perfil.get("frieza", 0.0)

        # Decay: frieza segura a emoção; esquentado oscila mais.
        decay = max(0.004, 0.015 - frieza * 0.010)
        self.raiva = max(0.0, self.raiva - decay * dt * 60)
        self.frustracao = max(0.0, self.frustracao - 0.002 * dt * 60)
        self.adrenalina = max(0.0, self.adrenalina - 0.01 * dt * 60)
        self.excitacao = max(0.0, self.excitacao - 0.008 * dt * 60)
        self.tedio = max(0.0, self.tedio - 0.01 * dt * 60)

        # Contadores recentes esfriam depois de 3s sem evento.
        if self.tempo_desde_dano > 3.0:
            self.hits_recebidos_recente = max(0, self.hits_recebidos_recente - 1)
        if self.tempo_desde_hit > 3.0:
            self.hits_dados_recente = max(0, self.hits_dados_recente - 1)

        # === MEDO CONTÍNUO (5C) ===
        # Persegue um alvo em gradiente (como a confiança já fazia). A
        # coragem é multiplicador por eixo: frieza 1,0 → ~0,4; eixo medo
        # 1,0 → ~1,5. Nunca zera — era o interruptor binário do :2849.
        alvo_medo = max(0.0, (0.45 - hp_pct) * 1.8)
        alvo_medo += min(0.25, self.hits_recebidos_recente * 0.07)
        coragem = 1.0 + perfil.get("medo", 0.0) * 0.5 - max(0.0, frieza) * 0.6
        coragem = max(0.3, min(1.5, coragem))
        alvo_medo = min(1.0, alvo_medo * coragem)
        self.medo += (alvo_medo - self.medo) * min(1.0, 0.05 * dt * 60)
        self.medo = max(0.0, min(1.0, self.medo))

        # Confiança (mantida: já era gradiente).
        hp_diff = hp_pct - inimigo_hp_pct
        alvo_conf = 0.5 + hp_diff * 0.4
        self.confianca += (alvo_conf - self.confianca) * 0.05 * dt * 60
        self.confianca = max(0.1, min(1.0, self.confianca))

        # === FRUSTRAÇÃO = SECA OFENSIVA (5C) ===
        # Cresce quando NÃO se consegue bater há um tempo; apanhar soma
        # em reagir_ao_dano; acertar alivia em on_hit_dado.
        if self.tempo_desde_hit > 3.5 and distancia < 12.0:
            self.frustracao = min(1.0, self.frustracao + 0.025 * dt * 60)

        # Excitação: proximidade e combos.
        if distancia < 3.0:
            self.excitacao = min(1.0, self.excitacao + 0.02 * dt * 60)
        if self.combo_atual > 2:
            self.excitacao = min(1.0, self.excitacao + 0.05)

        # === TÉDIO = SILÊNCIO BILATERAL (5C) ===
        # Antes: ganho 0,6/s vs decay 0,6/s — teto matemático. Agora o
        # silêncio real (ninguém acerta ninguém) vence o decay com folga.
        if self.tempo_desde_dano > 5.0 and self.tempo_desde_hit > 5.0:
            self.tedio = min(1.0, self.tedio + 0.02 * dt * 60)

        # Adrenalina: beira da morte ou briga colada com raiva.
        if hp_pct < 0.2 or (distancia < 2.0 and self.raiva > 0.5):
            self.adrenalina = min(1.0, self.adrenalina + 0.04 * dt * 60)

    # ---------------------------------------------------------------- humor

    def atualizar_humor(self):
        """Escada de humor (5C): 13 humores com produtor real.

        DESESPERADO subiu para o topo (era penúltimo e nunca vencia);
        BERSERK/EUFORICO/GLACIAL ganharam produtores — existiam no catálogo
        de HUMORES sem nenhum caminho até eles.
        """
        if self.cd_mudanca_humor > 0:
            return

        brain = self._brain
        p = self.parent
        hp_pct = 1.0
        if p is not None and getattr(p, "vida_max", 0) > 0:
            hp_pct = p.vida / p.vida_max
        momentum = getattr(brain, "momentum", 0.0)
        frieza = self.perfil.get("frieza", 0.0)

        if getattr(brain, "modo_berserk", False):
            novo_humor = "BERSERK"
        elif hp_pct < 0.18 and (self.medo > 0.25 or hp_pct < 0.10):
            novo_humor = "DESESPERADO"
        elif self.raiva > 0.7:
            novo_humor = "FURIOSO"
        elif self.medo > 0.6:
            novo_humor = "ASSUSTADO"
        elif self.medo > 0.4 and self.confianca < 0.35:
            novo_humor = "NERVOSO"
        elif self.adrenalina > 0.6:
            novo_humor = "DETERMINADO"
        elif self.excitacao > 0.85 and momentum > 0.4:
            novo_humor = "EUFORICO"
        elif self.tedio > 0.5:
            novo_humor = "ENTEDIADO"
        elif self.frustracao > 0.5:
            novo_humor = "FURIOSO" if self.rng.random() < 0.5 else "NERVOSO"
        elif self.confianca > 0.7:
            novo_humor = "CONFIANTE"
        elif self.excitacao > 0.6:
            novo_humor = "ANIMADO"
        elif frieza > 0.5 and self.medo < 0.15 and self.raiva < 0.2:
            novo_humor = "GLACIAL"
        elif self.confianca > 0.4 and self.raiva < 0.3 and self.medo < 0.3:
            novo_humor = "CALMO"
        else:
            novo_humor = "FOCADO"

        if novo_humor != self.humor:
            self.humor = novo_humor
            self.cd_mudanca_humor = self.rng.uniform(2.0, 5.0)

    # -------------------------------------------------------------- eventos

    def reagir_ao_dano(self, dano):
        """Reação emocional a um golpe REAL recebido (DoT não passa aqui:
        queimar não é ser acertado — Onda 5C tirou o tick de DoT da
        contagem de hits que alimentava medo/momentum)."""
        self.tempo_desde_dano = 0.0
        self.hits_recebidos_total += 1
        self.hits_recebidos_recente += 1
        self.combo_atual = 0

        perfil = self.perfil
        ganho_raiva = 0.05 * (1.0 - max(0.0, perfil.get("frieza", 0.0)) * 0.5)
        ganho_raiva += max(0.0, perfil.get("agressao", 0.0)) * 0.15
        self.raiva = min(1.0, self.raiva + ganho_raiva)
        self.medo = min(1.0, self.medo + max(0.0, perfil.get("medo", 0.0)) * 0.15)
        if perfil.get("caos", 0.0) > 0.4:
            self.adrenalina = min(1.0, self.adrenalina + 0.1)
        self.frustracao = min(1.0, self.frustracao + 0.1)

    def on_hit_dado(self):
        """Acertou um golpe: confiança sobe, frustração e tédio aliviam."""
        self.hits_dados_total += 1
        self.hits_dados_recente += 1
        self.tempo_desde_hit = 0.0
        self.combo_atual += 1
        self.max_combo = max(self.max_combo, self.combo_atual)

        self.confianca = min(1.0, self.confianca + 0.05)
        self.frustracao = max(0.0, self.frustracao - 0.25)
        self.tedio = max(0.0, self.tedio - 0.3)
        self.excitacao = min(1.0, self.excitacao + 0.1)

    def on_momento_cinematografico(self, tipo, iniciando):
        """Callback dos momentos do coreógrafo."""
        if not iniciando:
            return
        if tipo == "CLASH":
            self.excitacao = 1.0
            self.adrenalina = min(1.0, self.adrenalina + 0.3)
        elif tipo == "STANDOFF":
            self.confianca = 0.5
        elif tipo == "FINAL_SHOWDOWN":
            self.adrenalina = 1.0
            self.excitacao = 1.0
        elif tipo == "FACE_OFF":
            self.excitacao = min(1.0, self.excitacao + 0.2)

    # ------------------------------------------------------------- consulta

    def get_modificadores_humor(self):
        from neural_fights.ai.personalities import HUMORES

        return HUMORES.get(self.humor, HUMORES["CALMO"])

    def get_estado(self):
        return {
            "medo": self.medo,
            "raiva": self.raiva,
            "confianca": self.confianca,
            "frustracao": self.frustracao,
            "adrenalina": self.adrenalina,
            "excitacao": self.excitacao,
            "tedio": self.tedio,
            "humor": self.humor,
            "combo_atual": self.combo_atual,
            "max_combo": self.max_combo,
        }
