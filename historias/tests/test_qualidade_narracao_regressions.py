# -*- coding: utf-8 -*-
"""Contratos da qualidade do vídeo de história (01/09/2026).

As três queixas do Adrian, e o que a medição mostrou por trás de cada uma:

1. "A VOZ NÃO CONDIZ." Toda história saía em `pt-BR-AntonioNeural` —
   catalogada pelo próprio motor como *Friendly, Positive* — mesmo quando
   quem narrava era outra pessoa. Agora a voz vem da descrição do
   protagonista, que a bíblia já fixava para manter as imagens parecidas.

2. "A LEITURA É CORTADA, ROBÓTICA." Não era a voz: era o RECORTE. Cada cena
   era uma síntese separada, então a entonação reiniciava a cada ~14 s.
   Medido: 97% de fala e só 5,5 s de silêncio numa parte de 206 s — não
   faltava áudio, faltava continuidade.

3. "NÃO É CATIVANTE." O roteiro media bem (24% de perguntas, 24% de frases
   curtas). O problema era VISUAL: uma troca de imagem a cada 14,7 s, contra
   2,5 s do vídeo de build. Foto parada com zoom lento por quinze segundos é
   slideshow.

Rode de dentro de historias/:
    python -m unittest tests.test_qualidade_narracao_regressions -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from contos.roteiro import narrador                                # noqa: E402
from contos.video import timeline                                  # noqa: E402

RENDER = timeline.carregar_config("render.json")


class NarradorTests(unittest.TestCase):
    """A voz sai de QUEM NARRA, não de um padrão fixo."""

    def test_protagonista_mulher_recebe_voz_de_mulher(self):
        cfg = narrador.voz_para(
            {"protagonista": "A 34-year-old woman with red hair"},
            {"por_narrador": True})
        self.assertEqual("mulher", cfg["narrador"])
        self.assertIn("Francisca", cfg["voz"])

    def test_protagonista_homem_recebe_voz_de_homem(self):
        cfg = narrador.voz_para(
            {"protagonista": "a man in his late thirties, shaved head"},
            {"por_narrador": True})
        self.assertEqual("homem", cfg["narrador"])
        self.assertIn("Antonio", cfg["voz"])

    def test_campo_explicito_vence_a_descricao(self):
        """Se a bíblia disser quem narra, a adivinhação não opina."""
        cfg = narrador.voz_para(
            {"narrador": "mulher", "protagonista": "A 30-year-old man"},
            {"por_narrador": True})
        self.assertEqual("mulher", cfg["narrador"])

    def test_sem_pista_nenhuma_nao_quebra(self):
        for roteiro in ({}, {"protagonista": ""}, {"protagonista": None}):
            cfg = narrador.voz_para(roteiro, {"por_narrador": True})
            self.assertTrue(cfg["voz"])

    def test_desligar_mantem_a_voz_do_config(self):
        cfg = narrador.voz_para(
            {"protagonista": "A 34-year-old woman"},
            {"por_narrador": False, "voz": "pt-BR-AntonioNeural"})
        self.assertEqual("pt-BR-AntonioNeural", cfg["voz"])

    def test_idade_ajusta_o_tom(self):
        velho = narrador.voz_para(
            {"protagonista": "A 58-year-old man"}, {"por_narrador": True})
        jovem = narrador.voz_para(
            {"protagonista": "A 19-year-old man"}, {"por_narrador": True})
        self.assertTrue(velho["tom"].startswith("-"))
        self.assertTrue(jovem["tom"].startswith("+"))

    def test_a_config_original_nao_e_modificada(self):
        original = {"por_narrador": True, "voz": "pt-BR-AntonioNeural"}
        narrador.voz_para({"protagonista": "A 34-year-old woman"}, original)
        self.assertEqual("pt-BR-AntonioNeural", original["voz"])

    def test_idade_lida_da_descricao(self):
        self.assertEqual(29, narrador.idade(
            {"protagonista": "A 29-year-old man with curly hair"}))
        self.assertIsNone(narrador.idade({"protagonista": "a man"}))


def _roteiro(cenas=4, tempo=4.0):
    return {"titulo": "T", "cta": "E você?",
            "cenas": [{"n": i, "imagem": f"a room, scene {i}, night",
                       "tempo": tempo, "narracao": f"Fala da cena {i}."}
                      for i in range(1, cenas + 1)]}


class LeituraContinuaTests(unittest.TestCase):
    """Com os marcos do áudio, a cena é RECORTE da fala, não previsão dela."""

    def test_os_marcos_definem_o_inicio_das_cenas(self):
        plano = timeline.montar(_roteiro(3), {}, marcos=[0.0, 10.0, 25.0],
                                duracao_audio=40.0, config_render=RENDER)
        principais = [e for e in plano["events"] if not e.get("continuacao")]
        self.assertEqual([0.0, 10.0, 25.0],
                         [e["start"] for e in principais])

    def test_a_ultima_cena_vai_ate_o_fim_do_audio(self):
        plano = timeline.montar(_roteiro(2), {}, marcos=[0.0, 10.0],
                                duracao_audio=30.0, config_render=RENDER)
        self.assertAlmostEqual(30.0, plano["total_duration"], delta=1.5)

    def test_sem_marcos_o_caminho_antigo_continua(self):
        plano = timeline.montar(_roteiro(3), {0: 6.0, 1: 3.0, 2: 3.0},
                                config_render=RENDER)
        self.assertGreater(plano["total_duration"], 0)

    def test_marcos_do_tamanho_errado_sao_ignorados(self):
        """Meia lista de marcos alinharia as cenas erradas — melhor ignorar."""
        plano = timeline.montar(_roteiro(4), {}, marcos=[0.0, 10.0],
                                duracao_audio=40.0, config_render=RENDER)
        self.assertGreater(plano["total_duration"], 0)


class RitmoVisualTests(unittest.TestCase):
    """Imagem parada por 15 s é slideshow — o enquadramento tem que mudar."""

    @staticmethod
    def _cenas(quantas=2, duracao=15.0, com_imagem=True):
        return [{"type": "cena", "n": i + 1, "start": round(i * duracao, 3),
                 "duration": duracao, "narracao": f"Fala da cena {i + 1}.",
                 "imagem": "a room", "titulo": "T" if i == 0 else None,
                 "camera": {"zoom": [1.0, 1.12],
                            "centro": [[0.5, 0.46], [0.54, 0.52]]},
                 **({"arquivo": f"/tmp/cena{i + 1}.png"} if com_imagem else {})}
                for i in range(quantas)]

    def _dividir(self, cenas=None, **camera):
        config = {"camera": {**(RENDER.get("camera") or {}), **camera}}
        return timeline.dividir_planos(cenas or self._cenas(), config)

    def test_cena_longa_vira_varios_planos(self):
        planos = self._dividir(corte_visual_s=5.0)
        self.assertGreater(len(planos), 2, "a cena longa não foi dividida")
        self.assertTrue(any(p.get("continuacao") for p in planos))

    def test_os_planos_da_mesma_cena_mudam_o_enquadramento(self):
        planos = self._dividir(corte_visual_s=5.0)
        centros = [tuple(map(tuple, p["camera"]["centro"])) for p in planos[:2]]
        self.assertNotEqual(centros[0], centros[1],
                            "dois planos iguais não são um corte")

    def test_desligar_devolve_uma_cena_por_evento(self):
        self.assertEqual(2, len(self._dividir(corte_visual_s=0)))

    def test_cena_curta_nao_e_dividida(self):
        curtas = self._cenas(quantas=2, duracao=6.0)
        self.assertEqual(2, len(self._dividir(curtas, corte_visual_s=5.0)))

    def test_cartao_de_texto_nao_e_dividido(self):
        """Sem imagem, o quadro é gerado — reenquadrar não acrescenta nada."""
        sem_imagem = self._cenas(quantas=2, com_imagem=False)
        self.assertEqual(2, len(self._dividir(sem_imagem, corte_visual_s=5.0)))

    def test_a_continuacao_nao_repete_o_texto(self):
        planos = self._dividir(corte_visual_s=5.0)
        continuacoes = [p for p in planos if p.get("continuacao")]
        self.assertTrue(continuacoes)
        for plano in continuacoes:
            self.assertNotIn("titulo", plano)

    def test_a_fala_nao_e_duplicada_no_audio(self):
        plano = {"events": self._dividir(corte_visual_s=5.0)}
        self.assertEqual(2, len(timeline.linhas_do_plano(plano)),
                         "a voz falaria a mesma cena duas vezes")

    def test_a_legenda_nao_repete_a_fala(self):
        plano = {"events": self._dividir(corte_visual_s=5.0)}
        self.assertEqual(2, timeline.legenda_srt(plano).count("Fala da cena"))

    def test_o_tempo_total_nao_muda(self):
        planos = self._dividir(corte_visual_s=5.0)
        self.assertAlmostEqual(30.0, sum(p["duration"] for p in planos),
                               delta=0.05)

    def test_os_planos_ficam_em_sequencia_sem_buraco(self):
        planos = self._dividir(corte_visual_s=5.0)
        for anterior, seguinte in zip(planos, planos[1:]):
            self.assertAlmostEqual(anterior["start"] + anterior["duration"],
                                   seguinte["start"], delta=0.05)

    def test_plano_nunca_fica_curto_demais(self):
        planos = self._dividir(corte_visual_s=1.0, plano_minimo_s=3.0)
        for plano in planos:
            self.assertGreaterEqual(plano["duration"], 2.9)


class TrilhaTests(unittest.TestCase):
    def test_a_cama_da_historia_nao_tem_bateria(self):
        """A trilha de builds é trap; sob um desabafo ela vira videoclipe."""
        from builds.video import trilha
        if not trilha.disponivel():
            self.skipTest("numpy ausente")
        import numpy as np
        ambiente = trilha.ambiente(seed=21, compassos=4)
        batida = trilha.trilha(seed=21, bpm=92, compassos=4)
        rms_amb = float(np.sqrt(np.mean(ambiente ** 2)))
        rms_bat = float(np.sqrt(np.mean(batida ** 2)))
        self.assertLess(rms_amb, rms_bat,
                        "a cama tem que ficar ABAIXO da trilha de builds")
        # sem percussão, a energia não tem picos periódicos fortes
        pico = float(np.max(np.abs(ambiente)))
        self.assertLess(pico / max(rms_amb, 1e-9), 12.0,
                        "picos de bateria na cama da história")


class LegendaCobreAFalaTests(unittest.TestCase):
    """A legenda tem que durar o que a FALA dura (08/09/2026).

    `dividir_planos` corta cena longa em 2-3 enquadramentos da mesma imagem, e
    so o PRIMEIRO plano fica sem `continuacao`. `legenda_srt` usava a duracao
    desse evento — que e a do primeiro plano, nao a da cena. Medido na
    historia 9, parte 2: a fala final durava 15,1 s e a legenda sumia aos
    5,2 s, deixando o CTA (a pergunta que segura o inscrito) sem texto na tela
    por dez segundos.

    O .srt e um arquivo separado, para subir como faixa de legenda; o karaoke
    desenhado no quadro vem de `voz_palavras.json` e nunca teve esse defeito.
    """

    def _plano(self):
        # `dividir_planos` so parte cena COM imagem — um cartao de texto
        # partido ao meio nao ganharia nada. Entao o teste finge que a imagem
        # existe, senao a cena longa nunca vira varios planos.
        from contos.imagens import fila
        original = fila.utilizavel
        fila.utilizavel = lambda _a: True
        self.addCleanup(setattr, fila, "utilizavel", original)

        roteiro = {
            "titulo": "T", "serie": True,
            "partes": [{"n": 1, "titulo": "P1", "cenas": [
                {"n": 1, "imagem": "a photo", "tempo": 5, "narracao": "curta"},
                # 20 s de fala: `dividir_planos` parte esta em varios planos
                {"n": 2, "imagem": "a photo", "tempo": 5, "narracao": "longa"},
                {"n": 3, "imagem": "a photo", "tempo": 5, "narracao": "fim"},
            ]}],
        }
        return timeline.montar(roteiro, marcos=[0.0, 8.0, 28.0],
                               duracao_audio=40.0, parte=1,
                               pasta=RAIZ / "outputs" / "historia_00099")

    @staticmethod
    def _fins(srt: str) -> list:
        import re
        saida = []
        for m in re.finditer(r"(\d+):(\d+):(\d+),(\d+) --> "
                             r"(\d+):(\d+):(\d+),(\d+)", srt):
            v = list(map(int, m.groups()))
            saida.append((v[0] * 3600 + v[1] * 60 + v[2] + v[3] / 1000,
                          v[4] * 3600 + v[5] * 60 + v[6] + v[7] / 1000))
        return saida

    def test_a_cena_partida_em_planos_mantem_a_legenda_inteira(self):
        plano = self._plano()
        partidos = [e for e in plano["events"] if e.get("continuacao")]
        self.assertTrue(partidos, "o teste precisa de uma cena partida")
        faixas = self._fins(timeline.legenda_srt(plano))
        # a cena 2 vai de 8 s a 28 s: a legenda dela tem que durar os 20 s
        self.assertAlmostEqual(faixas[1][0], 8.0, places=1)
        self.assertAlmostEqual(faixas[1][1], 28.0, places=1)

    def test_a_ultima_legenda_vai_ate_o_fim_do_video(self):
        plano = self._plano()
        faixas = self._fins(timeline.legenda_srt(plano))
        self.assertAlmostEqual(faixas[-1][1], plano["total_duration"], places=1)

    def test_as_legendas_nao_deixam_buraco_entre_si(self):
        """Cena termina onde a proxima comeca: legenda sem vao no meio."""
        faixas = self._fins(timeline.legenda_srt(self._plano()))
        for (_ini, fim), (prox, _f) in zip(faixas, faixas[1:]):
            self.assertAlmostEqual(fim, prox, places=2)


if __name__ == "__main__":
    unittest.main()
