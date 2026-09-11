"""A escala de impacto tem que medir o jogo que existe (Onda 15C).

`get_impact_tier` decidia o peso visual do golpe por limiares de forca em
8 / 14 / 20. O roster vivo (`data/personagens.json`, 64 personagens) vai de
4,5 a 7,7, com mediana 6,5: NENHUM personagem alcancava o segundo tier, e
todo golpe de todo video ja publicado saiu no tier mais fraco que existe.
A onda de choque do corpo-a-corpo nascia com `0.6 * 0.3` de tamanho, contra
1,2 e 2,5 dos impactos de projetil — o soco nao tinha peso.

Nenhum teste cobria esses limiares, e e exatamente por isso que ninguem viu.
Os daqui amarram a escala ao roster: se um dos dois andar sem o outro, cai.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from neural_fights.effects.attack import (IMPACT_TIERS,  # noqa: E402
                                          LIMIARES_FORCA, get_impact_tier)

RAIZ = Path(__file__).resolve().parents[1]
NOMES = {"light", "medium", "heavy", "colossal"}


def _forcas_do_roster() -> list[float]:
    with open(RAIZ / "neural_fights" / "data" / "personagens.json",
              encoding="utf-8") as fh:
        dados = json.load(fh)
    itens = dados if isinstance(dados, list) else list(dados.values())
    return [float(p["forca"]) for p in itens
            if isinstance(p, dict) and "forca" in p]


def _nome_do_tier(tier: dict) -> str:
    for nome, valor in IMPACT_TIERS.items():
        if valor is tier:
            return nome
    raise AssertionError("tier fora da tabela")


class LimiaresTests(unittest.TestCase):
    def test_os_limiares_cobrem_a_forca_que_o_roster_tem(self):
        """Os quatro tiers precisam existir no jogo, nao so na tabela.

        Tier vazio e efeito visual que nunca acontece — codigo morto com
        cara de recurso. Foi o estado de medium, heavy e colossal ate
        11/09/2026.
        """
        forcas = _forcas_do_roster()
        self.assertGreater(len(forcas), 30, "roster pequeno demais para medir")
        ocupacao = {nome: 0 for nome in NOMES}
        for forca in forcas:
            ocupacao[_nome_do_tier(get_impact_tier(forca))] += 1
        for nome, quantos in ocupacao.items():
            with self.subTest(tier=nome):
                self.assertGreater(quantos, 0, f"tier {nome} nao acontece nunca")

    def test_nenhum_tier_abocanha_o_roster_inteiro(self):
        """Se quase todo mundo cai no mesmo tier, a escala nao separa nada."""
        forcas = _forcas_do_roster()
        ocupacao = {nome: 0 for nome in NOMES}
        for forca in forcas:
            ocupacao[_nome_do_tier(get_impact_tier(forca))] += 1
        maior = max(ocupacao.values()) / len(forcas)
        self.assertLessEqual(maior, 0.60, f"ocupacao: {ocupacao}")

    def test_a_forca_mediana_nao_e_o_tier_mais_fraco(self):
        """Pino direto do sintoma: o golpe TIPICO nao pode ser o mais fraco."""
        forcas = sorted(_forcas_do_roster())
        mediana = forcas[len(forcas) // 2]
        self.assertNotEqual("light", _nome_do_tier(get_impact_tier(mediana)))

    def test_o_tier_e_monotonico_na_forca(self):
        ordem = {"light": 0, "medium": 1, "heavy": 2, "colossal": 3}
        anterior = -1
        forca = 0.0
        while forca <= 25.0:
            atual = ordem[_nome_do_tier(get_impact_tier(forca))]
            self.assertGreaterEqual(atual, anterior, f"desceu em forca={forca}")
            anterior = atual
            forca += 0.1

    def test_a_onda_de_choque_cresce_com_o_tier(self):
        """O unico efeito do tier que hoje esta LIGADO e o tamanho da onda.

        O resto de `effects/attack.py` (ScreenFlash, CraterMark, GroundCrack,
        ImpactEffect) e caminho morto: `criar_impacto_completo` nao e chamado
        por ninguem. Este teste trava o que de fato chega ao video.
        """
        tamanhos = [IMPACT_TIERS[n]["shockwave_size"]
                    for n in ("light", "medium", "heavy", "colossal")]
        self.assertEqual(tamanhos, sorted(tamanhos))
        self.assertLess(tamanhos[0], tamanhos[-1])

    def test_os_limiares_estao_ordenados_e_dentro_do_roster(self):
        self.assertGreater(LIMIARES_FORCA["colossal"], LIMIARES_FORCA["heavy"])
        self.assertGreater(LIMIARES_FORCA["heavy"], LIMIARES_FORCA["medium"])
        forcas = _forcas_do_roster()
        for nome, limiar in LIMIARES_FORCA.items():
            with self.subTest(tier=nome):
                self.assertLessEqual(limiar, max(forcas),
                                     "limiar acima do roster = tier inalcancavel")


class PortasAbsolutasTests(unittest.TestCase):
    """As portas de forca dentro de `criar_impacto_completo` tinham o mesmo
    defeito dos limiares: 18, 16 e 12 numa escala que vai ate 7,7."""

    def test_nenhum_numero_de_forca_solto_sobrou_no_modulo(self):
        """Varredura por REGEX, nao por lista: limiar novo tambem cai aqui.

        Eram seis numeros crus espalhados (8, 12, 14, 15, 16, 18, 20), em
        quatro lugares diferentes, todos na mesma escala que o jogo nao
        tem. Uma lista fixa de proibidos deixaria passar o setimo.
        """
        import re

        fonte = (RAIZ / "neural_fights" / "effects" / "attack.py").read_text(
            encoding="utf-8")
        soltos = re.findall(r"forca\s*[<>]=?\s*\d+(?:\.\d+)?", fonte)
        self.assertEqual([], soltos,
                         "porta de forca fora de LIMIARES_FORCA")


if __name__ == "__main__":
    unittest.main()
