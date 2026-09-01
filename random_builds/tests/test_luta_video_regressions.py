"""Contratos da Onda 9: a luta como elemento dominante do video.

O que este arquivo trava:

1. O corte de tedio tira SO as janelas secas: contexto em cada ponta, nunca
   os ultimos segundos antes do KO, nunca dentro de um combo; e o clipe
   respeita o teto. O remapeamento leva HP/eventos para o relogio do clipe.
2. Callouts sincronizados com o motor respeitam orcamento (gap, teto por
   10 s), deduplicam combos crescentes e nunca deixam placeholder na tela.
3. O video de luta unica e determinístico por seed, a luta ocupa pelo menos
   metade dele (a mesma regra que a roleta tem no video de build) e nenhuma
   cena parada passa do teto.
4. O ledger da arena e idempotente, atomico e escolhe o adversario da
   estreia por continuidade (o gerado mais recente) antes de por poder.

Rode de dentro de random_builds/:
    python -m unittest discover -s tests -p "test_*.py"
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builds.arena.ledger import Ledger, escolher_adversario                 # noqa: E402
from builds.assets.catalog import AssetCatalog                              # noqa: E402
from builds.assets.selector import AssetSelector                            # noqa: E402
from builds.content.caption_generator import CaptionGenerator               # noqa: E402
from builds.generation.random_engine import RandomEngine                    # noqa: E402
from builds.generation.session_generator import load_config                 # noqa: E402
from builds.tournament import highlights                                    # noqa: E402
from builds.tournament.timeline import (FightTimelineBuilder,               # noqa: E402
                                     planejar_callouts)

EDICAO = load_config("editing.json")
CAPTIONS = CaptionGenerator(load_config("captions.json"), load_config("frases.json"))
CENAS_PARADAS = ("hook", "fight_card", "fight_result", "outro")
TETO_CENA_PARADA = 3.0


def _gravacao(duracao: float = 40.0, ko: float | None = 36.5,
              hits: tuple[float, ...] = (2.0, 3.0, 10.0, 11.0, 20.0)) -> dict:
    eventos = [(t, "p2" if i % 2 else "p1", 8.0, "ataque_corpo_a_corpo")
               for i, t in enumerate(hits)]
    serie = [(round(t * 0.25, 2), 100.0 - t, 100.0 - t * 0.5)
             for t in range(int(duracao * 4) + 1)]
    narrativos = [{"t": t, "tipo": "parry", "slot": "p1"} for t in hits]
    if ko is not None:
        narrativos.append({"t": ko, "tipo": "ko", "slot": "p1"})
    return {"duracao_video": duracao, "ko_em_video": ko, "eventos_dano": eventos,
            "serie_hp": serie, "eventos_narrativos": narrativos}


class CorteDeTedioTests(unittest.TestCase):
    def test_luta_curta_entra_inteira(self):
        self.assertEqual([(0.0, 10.0)], highlights.planejar_corte_tedio(_gravacao(10.0, 8.0)))

    def test_janela_seca_sai_e_o_contexto_fica(self):
        trechos = highlights.planejar_corte_tedio(_gravacao())
        # gaps: 3->10 (corta 4..9), 11->20 (corta 12..19), 20->36.5 (corta 21..28.5)
        self.assertEqual([(0.0, 4.0), (9.0, 3.0), (19.0, 2.0), (28.5, 11.5)], trechos)
        for t in (2.0, 3.0, 10.0, 11.0, 20.0):
            self.assertIsNotNone(highlights.mapear_tempo(trechos, t), f"golpe em {t} cortado")
            # 1 s de contexto em volta de cada golpe continua no clipe
            self.assertIsNotNone(highlights.mapear_tempo(trechos, t - 0.9))
            self.assertIsNotNone(highlights.mapear_tempo(trechos, t + 0.9))

    def test_os_ultimos_segundos_antes_do_ko_sao_intocaveis(self):
        gravacao = _gravacao(hits=(2.0, 3.0))
        trechos = highlights.planejar_corte_tedio(gravacao, protecao_ko=8.0)
        ko = gravacao["ko_em_video"]
        for t in (ko - 7.9, ko - 4.0, ko - 0.1, ko, ko + 2.0):
            self.assertIsNotNone(highlights.mapear_tempo(trechos, t), f"{t} foi cortado")

    def test_nunca_corta_dentro_de_um_combo(self):
        combo = (10.0, 10.4, 10.8, 11.2, 11.6)
        gravacao = _gravacao(hits=(2.0,) + combo + (25.0,))
        trechos = highlights.planejar_corte_tedio(gravacao)
        mapeados = [highlights.mapear_tempo(trechos, t) for t in combo]
        self.assertTrue(all(m is not None for m in mapeados))
        # e o combo continua contiguo no relogio do clipe
        for a, b, ta, tb in zip(mapeados, mapeados[1:], combo, combo[1:]):
            self.assertAlmostEqual(b - a, tb - ta, places=2)

    def test_respeita_o_teto(self):
        hits = tuple(i * 0.9 for i in range(1, 100))      # luta densa de 90 s
        gravacao = _gravacao(duracao=93.0, ko=89.5, hits=hits)
        trechos = highlights.planejar_corte_tedio(gravacao, max_total=45.0)
        self.assertLessEqual(highlights.duracao_total(trechos), 45.0 + 0.01)
        self.assertTrue(trechos)
        # densa demais para o corte de tedio: abertura + desfecho, nunca so o fim
        self.assertEqual(0.0, trechos[0][0])
        self.assertAlmostEqual(93.0, trechos[-1][0] + trechos[-1][1], places=2)
        self.assertIsNotNone(highlights.mapear_tempo(trechos, 89.5), "KO cortado")

    def test_mapeamento_e_monotonico_e_some_no_corte(self):
        trechos = [(0.0, 4.0), (9.0, 3.0), (19.0, 2.0)]
        self.assertEqual(0.0, highlights.mapear_tempo(trechos, 0.0))
        self.assertEqual(4.0, highlights.mapear_tempo(trechos, 9.0))
        self.assertEqual(7.5, highlights.mapear_tempo(trechos, 19.5))
        self.assertIsNone(highlights.mapear_tempo(trechos, 6.0))
        self.assertIsNone(highlights.mapear_tempo(trechos, 30.0))

    def test_remapear_leva_hp_e_eventos_para_o_relogio_do_clipe(self):
        gravacao = _gravacao()
        trechos = highlights.planejar_corte_tedio(gravacao)
        remap = highlights.remapear_gravacao(gravacao, trechos)
        self.assertEqual(highlights.duracao_total(trechos), remap["duracao"])
        self.assertLessEqual(max(a[0] for a in remap["serie_hp"]), remap["duracao"] + 1e-6)
        self.assertEqual(len(gravacao["eventos_dano"]), len(remap["eventos_dano"]))
        ko = [e for e in remap["eventos_narrativos"] if e["tipo"] == "ko"][0]
        self.assertAlmostEqual(ko["t"], remap["ko_em_video"], places=2)
        self.assertLess(remap["ko_em_video"], gravacao["ko_em_video"])


class CalloutTests(unittest.TestCase):
    CFG = EDICAO["fight_callouts"]

    def _luta(self, eventos):
        return {"eventos_narrativos": eventos}

    def test_orcamento_gap_e_teto_por_10s(self):
        eventos = [{"t": 1.0 + i * 0.4, "tipo": "desvio", "slot": "p1"} for i in range(40)]
        callouts = planejar_callouts(RandomEngine(1).fork("c"), self._luta(eventos),
                                     30.0, self.CFG, CAPTIONS)
        tempos = [c["t"] for c in callouts]
        for a, b in zip(tempos, tempos[1:]):
            self.assertGreaterEqual(b - a, self.CFG["gap_min"] - 1e-6)
        for t in tempos:
            self.assertLessEqual(sum(1 for x in tempos if abs(x - t) <= 5.0),
                                 self.CFG["por_10s"])

    def test_prioridade_decide_quem_fica(self):
        eventos = [{"t": 5.0, "tipo": "desvio", "slot": "p1"},
                   {"t": 5.3, "tipo": "ko", "slot": "p2"}]
        callouts = planejar_callouts(RandomEngine(2).fork("c"), self._luta(eventos),
                                     12.0, self.CFG, CAPTIONS)
        self.assertEqual(["ko"], [c["tipo"] for c in callouts])

    def test_combo_crescente_vira_um_callout_com_o_maior_n(self):
        eventos = [{"t": 4.0, "tipo": "combo", "slot": "p2", "n": 3},
                   {"t": 4.5, "tipo": "combo", "slot": "p2", "n": 4},
                   {"t": 5.1, "tipo": "combo", "slot": "p2", "n": 5}]
        callouts = planejar_callouts(RandomEngine(3).fork("c"), self._luta(eventos),
                                     12.0, self.CFG, CAPTIONS)
        self.assertEqual(1, len(callouts))
        self.assertEqual(5, callouts[0]["n"])
        self.assertIn("5", callouts[0]["texto"])

    def test_combo_curto_nao_vira_callout(self):
        eventos = [{"t": 4.0, "tipo": "combo", "slot": "p2", "n": 2}]
        self.assertEqual([], planejar_callouts(RandomEngine(4).fork("c"), self._luta(eventos),
                                               12.0, self.CFG, CAPTIONS))

    def test_plano_vira_callout_com_rotulo(self):
        """Onda 10C: a troca de plano vira callout de fundo com o rotulo."""
        eventos = [{"t": 3.0, "tipo": "plano", "slot": "p1", "rotulo": "PRESSÃO",
                    "plano": "PRESSIONAR"}]
        callouts = planejar_callouts(RandomEngine(6).fork("c"), self._luta(eventos),
                                     12.0, self.CFG, CAPTIONS)
        self.assertEqual(1, len(callouts))
        self.assertEqual("plano", callouts[0]["tipo"])
        self.assertIn("PRESSÃO", callouts[0]["texto"])
        self.assertEqual("PRESSÃO", callouts[0]["rotulo"])

    def test_plano_sem_rotulo_nao_vira_callout(self):
        eventos = [{"t": 3.0, "tipo": "plano", "slot": "p1", "rotulo": ""}]
        self.assertEqual([], planejar_callouts(RandomEngine(7).fork("c"), self._luta(eventos),
                                               12.0, self.CFG, CAPTIONS))

    def test_plano_throttle_por_lutador(self):
        gap = float(self.CFG["plano"]["gap_min_por_lutador"])
        eventos = [{"t": 2.0, "tipo": "plano", "slot": "p1", "rotulo": "PRESSÃO"},
                   {"t": 2.0 + gap * 0.5, "tipo": "plano", "slot": "p1", "rotulo": "ISCA"},
                   {"t": 2.0 + gap * 0.5, "tipo": "plano", "slot": "p2", "rotulo": "ACABAR"},
                   {"t": 2.0 + gap + 0.5, "tipo": "plano", "slot": "p1", "rotulo": "PRA PAREDE"}]
        callouts = planejar_callouts(RandomEngine(8).fork("c"), self._luta(eventos),
                                     30.0, self.CFG, CAPTIONS)
        rotulos = [c["rotulo"] for c in callouts]
        self.assertNotIn("ISCA", rotulos)          # p1 dentro do throttle
        self.assertIn("PRESSÃO", rotulos)
        self.assertIn("PRA PAREDE", rotulos)

    def test_plano_cede_a_evento_maior_proximo(self):
        eventos = [{"t": 5.0, "tipo": "plano", "slot": "p1", "rotulo": "ACABAR"},
                   {"t": 5.8, "tipo": "ko", "slot": "p1"}]
        callouts = planejar_callouts(RandomEngine(9).fork("c"), self._luta(eventos),
                                     12.0, self.CFG, CAPTIONS)
        self.assertEqual(["ko"], [c["tipo"] for c in callouts])

    def test_texto_nunca_leva_placeholder_para_a_tela(self):
        eventos = [{"t": 2.0 + i * 2.0, "tipo": tipo, "slot": "p1", "n": 4}
                   for i, tipo in enumerate(self.CFG["textos"])]
        callouts = planejar_callouts(RandomEngine(5).fork("c"), self._luta(eventos),
                                     60.0, self.CFG, CAPTIONS)
        self.assertTrue(callouts)
        for c in callouts:
            self.assertNotIn("{", c["texto"])
            self.assertNotIn("}", c["texto"])
            self.assertTrue(c["cor"].startswith("#"))


def _fight(seed: int = 7, duracao_clipe: float = 24.0, tier: str = "GOOD") -> dict:
    ficha1 = {"nome": "Kael", "classe": "Guerreiro (Combate)", "forca": 7.0, "mana": 4.0,
              "cor_r": 50, "cor_g": 200, "cor_b": 255}
    ficha2 = {"nome": "Lyra", "classe": "Maga (Arcano)", "forca": 4.0, "mana": 8.0,
              "cor_r": 255, "cor_g": 90, "cor_b": 60}
    luta = {
        "match_id": 0, "rodada": 0, "rodada_nome": "LUTA", "origem": "luta",
        "p1": "Kael", "p2": "Lyra", "p1_ficha": ficha1, "p2_ficha": ficha2,
        "vencedor": "Kael", "perdedor": "Lyra", "vencedor_gerado": True,
        "duracao": 31.2, "motivo": "knockout", "ko_type": "KO", "hp_vencedor": 22,
        "seed": seed, "cenario": "Dojo",
        "clipes": {"celular": {"path": "x_celular.mp4", "duracao": duracao_clipe},
                   "normal": {"path": "x_normal.mp4", "duracao": duracao_clipe}},
        "serie_hp": [(t * 0.25, 100 - t, 100 - t * 1.5) for t in range(int(duracao_clipe * 4))],
        "eventos_narrativos": [{"t": 3.0, "tipo": "primeiro_sangue", "slot": "p1"},
                               {"t": 9.0, "tipo": "parry", "slot": "p2"},
                               {"t": 15.0, "tipo": "combo", "slot": "p2", "n": 4},
                               {"t": 20.5, "tipo": "ko", "slot": "p1"}],
        "score": 68, "marcas": [], "zebra": False, "favorito": "Kael", "surpresa": 29,
        "tier": tier, "tier_label": "BOM", "sentiment": "positive", "intensity": 0.4,
        "tier_color": "#7ed957",
    }
    return {"seed": seed, "kind": "fight", "origem": "luta", "luta": luta,
            "fight_id": f"fight_{seed}"}


def _plano(fight: dict) -> dict:
    builder = FightTimelineBuilder(EDICAO, CAPTIONS, AssetSelector(AssetCatalog(ROOT / "assets")))
    return builder.build(RandomEngine(fight["seed"]).fork("luta:edicao"), fight)


class SkillCardShowcaseTests(unittest.TestCase):
    """Onda 11D: o kit do ESTREANTE vira showcase — e só na estreia."""

    def _fight_estreia(self, com_kit: bool = True) -> dict:
        fight = _fight(seed=11)
        fight["origem"] = "estreia"
        fight["estreia_de"] = "Kael"
        fight["luta"]["origem"] = "estreia"
        fight["luta"]["estreia_de"] = "Kael"
        if com_kit:
            fight["luta"]["p1_ficha"]["kit"] = [
                {"nome": "Habilidade Fantasma A", "papel": "CONTROLE",
                 "elemento": "RAIO", "descricao": "Onda de choque que atordoa",
                 "cor": [220, 220, 120]},
                {"nome": "Habilidade Fantasma B", "papel": "PICO",
                 "elemento": "FISICO", "descricao": "Golpe decisivo",
                 "cor": [160, 120, 60]},
            ]
        return fight

    def test_estreia_com_kit_emite_skill_cards_entre_card_e_gameplay(self):
        plano = _plano(self._fight_estreia())
        tipos = [e["type"] for e in plano["events"]]
        self.assertIn("skill_card", tipos)
        self.assertLess(tipos.index("fight_card"), tipos.index("skill_card"))
        self.assertLess(tipos.index("skill_card"), tipos.index("gameplay"))
        cards = [e for e in plano["events"] if e["type"] == "skill_card"]
        self.assertEqual(len(cards), 2)
        primeiro = cards[0]
        self.assertEqual(primeiro["nameplate"]["titulo"], "Habilidade Fantasma A")
        self.assertEqual(primeiro["nameplate"]["subtitulo"],
                         "Onda de choque que atordoa")
        self.assertEqual(primeiro["lutador"], "Kael")
        # Sem demo gravada na biblioteca, o card sai SINTÉTICO (sem asset
        # de vídeo) — o renderer desenha a placa sozinho.
        self.assertNotIn("asset", primeiro)
        for card in cards:
            self.assertGreater(card["duration"], 0.0)

    def test_estreia_sem_kit_na_ficha_nao_quebra(self):
        plano = _plano(self._fight_estreia(com_kit=False))
        self.assertNotIn("skill_card", [e["type"] for e in plano["events"]])

    def test_luta_comum_nunca_emite_skill_card(self):
        plano = _plano(_fight())
        self.assertNotIn("skill_card", [e["type"] for e in plano["events"]])


class FightTimelineTests(unittest.TestCase):
    def test_estrutura_gancho_card_luta_resultado_cta(self):
        tipos = [e["type"] for e in _plano(_fight())["events"]]
        self.assertEqual("hook", tipos[0])
        self.assertEqual(["fight_card", "gameplay", "fight_result"], tipos[1:4])
        self.assertEqual("outro", tipos[-1])
        self.assertLessEqual(len(tipos), 6)

    def test_a_luta_e_o_elemento_dominante(self):
        for duracao in (14.0, 24.0, 45.0):
            plano = _plano(_fight(duracao_clipe=duracao))
            luta = sum(e["duration"] for e in plano["events"] if e["type"] == "gameplay")
            self.assertGreater(luta, plano["total_duration"] * 0.5, f"clipe de {duracao}s")

    def test_nenhuma_cena_parada_passa_do_teto(self):
        for evento in _plano(_fight())["events"]:
            if evento["type"] in CENAS_PARADAS:
                self.assertLessEqual(evento["duration"], TETO_CENA_PARADA, evento["type"])

    def test_deterministico_por_seed(self):
        a, b = _plano(_fight(seed=11)), _plano(_fight(seed=11))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertNotEqual(json.dumps(_plano(_fight(seed=12)), sort_keys=True),
                            json.dumps(a, sort_keys=True))

    def test_gameplay_leva_hud_e_callouts_no_relogio_do_clipe(self):
        plano = _plano(_fight())
        gameplay = [e for e in plano["events"] if e["type"] == "gameplay"][0]
        self.assertIn("serie_hp", gameplay["hud"])
        self.assertEqual("Kael", gameplay["hud"]["p1"])
        self.assertTrue(gameplay["callouts"])
        for c in gameplay["callouts"]:
            self.assertGreaterEqual(c["t"], 0.0)
            self.assertLessEqual(c["t"] + c["duracao"], gameplay["duration"] + 1.0)
        self.assertIn("ko", [c["tipo"] for c in gameplay["callouts"]])

    def test_legendas_sem_placeholder(self):
        for seed in (1, 2, 3):
            fight = _fight(seed=seed)
            fight["luta"]["origem"] = "estreia"
            fight["luta"]["estreia_de"] = "Kael"
            fight["luta"]["p1_cartel"] = "2V-1D"
            fight["luta"]["p2_cartel"] = "0V-0D"
            for evento in _plano(fight)["events"]:
                legenda = evento.get("caption") or ""
                self.assertNotIn("{", legenda, legenda)
                self.assertNotIn("}", legenda, legenda)
        hook = _plano(fight)["events"][0]["caption"]
        self.assertIn("KAEL", hook.upper())

    def test_sem_clipe_o_video_continua_de_pe(self):
        fight = _fight()
        fight["luta"].pop("clipes")
        tipos = [e["type"] for e in _plano(fight)["events"]]
        self.assertNotIn("gameplay", tipos)
        self.assertIn("fight_result", tipos)

    def test_luta_unica_nao_ganha_telas_de_serie(self):
        """O formato antigo continua exatamente como era."""
        tipos = [e["type"] for e in _plano(_fight())["events"]]
        self.assertNotIn("round_title", tipos)
        self.assertNotIn("round_result", tipos)


def _fight_serie(vencedores: tuple[str, ...], seed: int = 7,
                 duracao_clipe: float = 24.0) -> dict:
    """Um confronto melhor-de-3 no formato que `FightSession` devolve."""
    rounds = []
    placar = {"Kael": 0, "Lyra": 0}
    for indice, vencedor in enumerate(vencedores):
        luta = dict(_fight(seed=seed + indice, duracao_clipe=duracao_clipe)["luta"])
        luta.update({
            "match_id": indice, "rodada": indice,
            "rodada_nome": f"ROUND {indice + 1}",
            "round": indice + 1, "melhor_de": 3,
            "vencedor": vencedor,
            "perdedor": "Lyra" if vencedor == "Kael" else "Kael",
        })
        placar[vencedor] += 1
        luta["placar"] = [placar["Kael"], placar["Lyra"]]
        rounds.append(luta)
    campeao = "Kael" if placar["Kael"] > placar["Lyra"] else "Lyra"
    return {"seed": seed, "kind": "fight", "origem": "luta",
            "p1": "Kael", "p2": "Lyra", "melhor_de": 3,
            "placar": [placar["Kael"], placar["Lyra"]],
            "lutas": rounds, "luta": rounds[-1],
            "vencedor": campeao, "fight_id": f"fight_{seed}"}


class SerieMelhorDeTests(unittest.TestCase):
    """A estreia virou melhor de 3: o video conta a serie, nao um round."""

    def test_cada_round_entra_com_titulo_gameplay_e_placar(self):
        plano = _plano(_fight_serie(("Kael", "Lyra", "Kael")))
        tipos = [e["type"] for e in plano["events"]]
        self.assertEqual("hook", tipos[0])
        self.assertEqual("fight_card", tipos[1])
        self.assertEqual("outro", tipos[-1])
        self.assertEqual(3, tipos.count("round_title"))
        self.assertEqual(3, tipos.count("gameplay"))
        self.assertEqual(3, tipos.count("round_result"))
        # o card do confronto acontece UMA vez: quem entra na arena e o mesmo
        self.assertEqual(1, tipos.count("fight_card"))
        self.assertEqual(1, tipos.count("fight_result"))
        # e o veredito da serie fecha depois do ultimo round
        self.assertGreater(tipos.index("fight_result"),
                           max(i for i, t in enumerate(tipos) if t == "round_result"))

    def test_placar_corre_round_a_round(self):
        plano = _plano(_fight_serie(("Kael", "Lyra", "Kael")))
        placares = [e["placar"] for e in plano["events"]
                    if e["type"] == "round_result"]
        self.assertEqual([[1, 0], [1, 1], [2, 1]], placares)

    def test_veredito_leva_o_placar_da_serie(self):
        plano = _plano(_fight_serie(("Kael", "Lyra", "Kael")))
        final = [e for e in plano["events"] if e["type"] == "fight_result"][0]
        self.assertEqual([2, 1], final["placar"])
        self.assertEqual(3, final["melhor_de"])

    def test_card_anuncia_o_formato_no_lugar_da_rodada(self):
        fight = _fight_serie(("Kael", "Kael"))
        fight["origem"] = "estreia"
        fight["estreia_de"] = "Kael"
        plano = _plano(fight)
        card = [e for e in plano["events"] if e["type"] == "fight_card"][0]
        self.assertEqual("ESTREIA • MELHOR DE 3", card["luta"]["rodada_nome"])
        # o rotulo e do CARD; o round mantem o proprio nome
        self.assertEqual("ROUND 1", fight["lutas"][0]["rodada_nome"])

    def test_showcase_de_kit_acontece_uma_vez_na_serie(self):
        fight = _fight_serie(("Kael", "Kael"))
        fight["origem"] = "estreia"
        fight["estreia_de"] = "Kael"
        for r in fight["lutas"]:
            r["origem"] = "estreia"
            r["estreia_de"] = "Kael"
            r["p1_ficha"] = dict(r["p1_ficha"], kit=[
                {"nome": "Habilidade Fantasma A", "papel": "CONTROLE",
                 "elemento": "RAIO", "descricao": "Onda de choque"}])
        tipos = [e["type"] for e in _plano(fight)["events"]]
        self.assertEqual(1, tipos.count("skill_card"))
        self.assertLess(tipos.index("skill_card"), tipos.index("round_title"))

    def test_as_lutas_continuam_dominando_o_video(self):
        plano = _plano(_fight_serie(("Kael", "Lyra", "Kael")))
        luta = sum(e["duration"] for e in plano["events"] if e["type"] == "gameplay")
        self.assertGreater(luta, plano["total_duration"] * 0.5)

    def test_legendas_da_serie_sem_placeholder(self):
        plano = _plano(_fight_serie(("Kael", "Lyra", "Lyra")))
        for evento in plano["events"]:
            legenda = evento.get("caption") or ""
            self.assertNotIn("{", legenda, legenda)
            self.assertNotIn("}", legenda, legenda)

    def test_o_video_nao_repete_a_mesma_frase_de_vitoria(self):
        """Com 3 rounds, sortear solto repete a mesma frase em segundos.

        Varre seeds: uma seed sortuda esconderia exatamente o bug que a
        exclusao das frases ja usadas existe para impedir.
        """
        for seed in range(1, 26):
            for vencedores in (("Kael", "Lyra", "Kael"),
                               ("Lyra", "Kael", "Lyra")):
                plano = _plano(_fight_serie(vencedores, seed=seed))
                legendas = [e["caption"] for e in plano["events"]
                            if e["type"] in ("round_result", "fight_result")]
                self.assertEqual(len(legendas), len(set(legendas)),
                                 f"seed={seed}: {legendas}")

    def test_veredito_de_serie_varrida_fala_do_placar_e_nao_do_round(self):
        plano = _plano(_fight_serie(("Kael", "Kael")))
        final = [e for e in plano["events"] if e["type"] == "fight_result"][0]
        self.assertIn("2 x 0", final["caption"])

    def test_deterministico_por_seed(self):
        a = _plano(_fight_serie(("Kael", "Lyra", "Kael"), seed=11))
        b = _plano(_fight_serie(("Kael", "Lyra", "Kael"), seed=11))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.caminho = Path(self._tmp.name) / "arena" / "ledger.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _luta(self, p1, p2, vencedor, seed=1, match_id=0):
        return {"match_id": match_id, "seed": seed, "p1": p1, "p2": p2,
                "vencedor": vencedor, "perdedor": p2 if vencedor == p1 else p1,
                "duracao": 20.0, "ko_type": "KO", "hp_vencedor": 40, "cenario": "Dojo",
                "marcas": [], "score": 55, "tier": "AVERAGE"}

    def test_registrar_e_idempotente_e_persiste(self):
        ledger = Ledger(self.caminho)
        ledger.registrar(self._luta("A", "B", "A"), origem="luta")
        ledger.registrar(self._luta("A", "B", "A"), origem="luta")
        self.assertEqual(1, len(Ledger(self.caminho).lutas))
        self.assertTrue(self.caminho.is_file())
        self.assertFalse(list(self.caminho.parent.glob("*.tmp")))

    def test_recorde_cartel_sequencia_e_ranking(self):
        ledger = Ledger(self.caminho)
        ledger.registrar(self._luta("A", "B", "A", seed=1), origem="luta")
        ledger.registrar(self._luta("A", "C", "A", seed=2), origem="luta")
        ledger.registrar(self._luta("A", "B", "B", seed=3), origem="luta")
        self.assertEqual({"vitorias": 2, "derrotas": 1, "empates": 0, "lutas": 3,
                          "sequencia": -1}, ledger.recorde("A"))
        self.assertEqual("2V-1D", ledger.cartel("A"))
        self.assertEqual("A", ledger.ranking(1)[0]["nome"])
        self.assertEqual("B", ledger.campeao_atual())
        self.assertEqual(2, len(ledger.confrontos("A", "B")))
        self.assertEqual(2, len(ledger.confrontos("B", "A")))

    def test_ledger_corrompido_recomeca_sem_derrubar(self):
        self.caminho.parent.mkdir(parents=True)
        self.caminho.write_text("{isso nao e json", encoding="utf-8")
        ledger = Ledger(self.caminho)
        self.assertEqual([], ledger.lutas)
        ledger.registrar(self._luta("A", "B", "A"), origem="luta")
        self.assertEqual(1, len(Ledger(self.caminho).lutas))

    def test_adversario_da_estreia_prefere_o_gerado_mais_recente(self):
        rng = RandomEngine(5).fork("x")
        fichas = {n: {"forca": 5, "mana": 5} for n in ("Novo", "G1", "G2", "Banco")}
        escolhido = escolher_adversario("Novo", list(fichas), rng,
                                        gerados=["G1", "G2", "Novo"], fichas=fichas)
        self.assertEqual("G2", escolhido)
        # ja lutou com G2: passa para G1
        ledger = Ledger(self.caminho)
        ledger.registrar(self._luta("Novo", "G2", "G2"), origem="luta")
        self.assertEqual("G1", escolher_adversario("Novo", list(fichas), rng,
                                                   gerados=["G1", "G2", "Novo"],
                                                   fichas=fichas, ledger=ledger))

    def test_sem_gerados_cai_no_poder_proximo(self):
        rng = RandomEngine(6).fork("x")
        fichas = {"Novo": {"forca": 5, "mana": 5}, "Fraco": {"forca": 3, "mana": 3},
                  "Igual": {"forca": 5, "mana": 5.2}, "Forte": {"forca": 9, "mana": 9}}
        for _ in range(10):
            self.assertIn(escolher_adversario("Novo", list(fichas), rng, fichas=fichas),
                          ("Fraco", "Igual", "Forte"))
        self.assertNotEqual("Novo", escolher_adversario("Novo", list(fichas), rng, fichas=fichas))
        self.assertIsNone(escolher_adversario("Novo", ["Novo"], rng, fichas=fichas))


class FightSessionSerieTests(unittest.TestCase):
    """A serie na origem: quantos rounds rodam, e o que sai deles.

    Sem gravacao e sem banco — `simular_luta` e as fichas sao trocadas por
    dublês, entao o teste mede a REGRA da serie, nao o motor.
    """

    VENCEDORES: list[str] = []

    def setUp(self):
        from builds.tournament import runner

        self.runner = runner
        self.chamadas: list[int] = []
        fichas = {"Kael": {"forca": 7.0, "mana": 4.0},
                  "Lyra": {"forca": 4.0, "mana": 8.0}}

        def falso_simular(p1, p2, cenario, base_seed):
            indice = len(self.chamadas)
            self.chamadas.append(base_seed)
            return {"vencedor": self.VENCEDORES[indice], "duracao": 20.0,
                    "motivo": "knockout", "seed": base_seed, "hp_vencedor": 40.0}

        self._patches = [
            unittest.mock.patch.object(runner, "simular_luta", falso_simular),
            unittest.mock.patch.object(runner, "fichas_do_banco", lambda: fichas),
            unittest.mock.patch.object(runner, "personagens_gerados", lambda: ["Kael"]),
        ]
        for p in self._patches:
            p.start()
        self.sessao = runner.FightSession(load_config("scoring.json"))

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def _gerar(self, vencedores, **kwargs):
        type(self).VENCEDORES = list(vencedores)
        return self.sessao.gerar(p1="Kael", p2="Lyra", seed=100,
                                 cenario="Dojo", melhor_de=3, **kwargs)

    def test_a_serie_para_quando_o_placar_fecha(self):
        """2 x 0 nao gasta gravacao com o terceiro round."""
        fight = self._gerar(("Kael", "Kael", "Kael"))
        self.assertEqual(2, len(fight["lutas"]))
        self.assertEqual(2, len(self.chamadas))
        self.assertEqual([2, 0], fight["placar"])
        self.assertEqual("Kael", fight["vencedor"])

    def test_serie_ate_o_terceiro_round(self):
        fight = self._gerar(("Kael", "Lyra", "Lyra"))
        self.assertEqual(3, len(fight["lutas"]))
        self.assertEqual([1, 2], fight["placar"])
        self.assertEqual("Lyra", fight["vencedor"])
        # `luta` aponta para o round que FECHOU a serie
        self.assertIs(fight["lutas"][-1], fight["luta"])

    def test_cada_round_tem_seed_e_match_id_proprios(self):
        """Sem isso os tres rounds colapsariam numa linha so no ledger."""
        fight = self._gerar(("Kael", "Lyra", "Kael"))
        self.assertEqual(3, len(set(self.chamadas)))
        self.assertEqual([0, 1, 2], [r["match_id"] for r in fight["lutas"]])
        self.assertEqual([1, 2, 3], [r["round"] for r in fight["lutas"]])
        ids = {f"estreia:{r['match_id']}:{r['seed']}:{r['p1']}:{r['p2']}"
               for r in fight["lutas"]}
        self.assertEqual(3, len(ids))

    def test_todos_os_rounds_na_mesma_arena(self):
        fight = self._gerar(("Kael", "Lyra", "Kael"))
        self.assertEqual({"Dojo"}, {r["cenario"] for r in fight["lutas"]})

    def test_melhor_de_par_e_recusado(self):
        for invalido in (0, 2, 4):
            with self.assertRaises(ValueError):
                self.sessao.gerar(p1="Kael", p2="Lyra", seed=1, cenario="Dojo",
                                  melhor_de=invalido)

    def test_luta_unica_mantem_o_formato_antigo(self):
        type(self).VENCEDORES = ["Lyra"]
        fight = self.sessao.gerar(p1="Kael", p2="Lyra", seed=100, cenario="Dojo")
        self.assertEqual(1, len(fight["lutas"]))
        self.assertEqual("LUTA", fight["luta"]["rodada_nome"])
        self.assertNotIn("placar", fight["luta"])
        self.assertNotIn("round", fight["luta"])
        self.assertEqual("Lyra", fight["vencedor"])
        self.assertFalse(fight["vencedor_gerado"])


if __name__ == "__main__":
    unittest.main()
