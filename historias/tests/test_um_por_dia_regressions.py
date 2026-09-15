# -*- coding: utf-8 -*-
"""Um video em CADA HORARIO da grade — e nenhum repetido no mesmo disparo.

A grade e 6, 7, 8, 10, 12, 15, 17 e 20, a mesma em que a agenda CRIA
historia. Correcao dele em 09/09/2026: "nao quero um video por dia, quero um
video em todos esses horarios".

O que esta travado aqui e so a REPETICAO dentro do mesmo horario, que e um
risco real e recente:

  - em 08/09 sairam DOIS de cada canal porque uma rodada manual cruzou com a
    agendada (17:06 e 17:12 nas historias, 17:07 e 17:13 nos builds);
  - em 09/09 `StartWhenAvailable` foi ligado nas dez tarefas para que horario
    perdido seja recuperado — certo para nao perder o disparo, e que por
    definicao cria disparo fora da hora.

A janela e a HORA DO RELOGIO porque a grade nunca tem dois horarios na mesma
hora — 6, 7 e 8 sao seguidos, e isso basta para separa-los.

A fonte e o LEDGER, nao um arquivo de controle novo: ele ja diz o que foi
publicado, e uma segunda fonte que discordasse dele seria pior do que nenhuma.

Rode de dentro de historias/:
    python -m unittest tests.test_um_por_dia_regressions -v
"""
from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
POSTAR = RAIZ.parent / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_grade", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class Base(unittest.TestCase):
    def setUp(self):
        self.postar = _postar()
        self._real = self.postar._publicados_do_canal
        self.addCleanup(
            lambda: setattr(self.postar, "_publicados_do_canal", self._real))

    def _ledger(self, linhas):
        self.postar._publicados_do_canal = lambda _canal: list(linhas)


class GradeTests(Base):
    def test_a_grade_tem_os_dez_horarios(self):
        """15/09/2026: horas vagas das pessoas, com minuto proprio."""
        self.assertEqual((0, 6, 9, 12, 15, 17, 20, 21, 22, 23),
                         self.postar.HORAS_PADRAO)

    def test_cada_horario_vira_uma_tarefa_com_nome_proprio(self):
        self.assertEqual("NeuralFights_postar_06",
                         self.postar.nome_da_tarefa(6))
        self.assertEqual("NeuralFights_postar_20",
                         self.postar.nome_da_tarefa(20))

    def test_a_tarefa_antiga_sem_numero_e_removida(self):
        """Se ficasse, as 17:07 haveria ela E a `_17` — duas no mesmo horario."""
        fonte = POSTAR.read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def instalar_grade("):]
        corpo = corpo[:corpo.index("\ndef ")]
        self.assertIn("/Delete", corpo)


class NaoRepeteNoMesmoHorarioTests(Base):
    def test_publicacao_na_MESMA_hora_bloqueia(self):
        self._ledger([{"quando": "2026-09-09T17:08:12",
                       "video_id": "historia_00003:celular:p03"}])
        achado = self.postar.publicou_neste_horario(
            "historias", agora=datetime(2026, 9, 9, 17, 40))
        self.assertIsNotNone(achado)
        self.assertEqual("historia_00003:celular:p03", achado["video_id"])

    def test_publicacao_na_hora_ANTERIOR_nao_bloqueia(self):
        """Foi por isto que a versao 'um por dia' estava errada."""
        self._ledger([{"quando": "2026-09-09T07:08:00", "video_id": "x"}])
        self.assertIsNone(self.postar.publicou_neste_horario(
            "historias", agora=datetime(2026, 9, 9, 8, 7)))

    def test_horarios_seguidos_da_grade_sao_independentes(self):
        """6, 7 e 8 sao horas seguidas: cada uma publica a sua."""
        self._ledger([{"quando": "2026-09-09T06:07:30", "video_id": "seis"},
                      {"quando": "2026-09-09T07:07:30", "video_id": "sete"}])
        self.assertIsNone(self.postar.publicou_neste_horario(
            "builds", agora=datetime(2026, 9, 9, 8, 7)))
        self.assertEqual("sete", self.postar.publicou_neste_horario(
            "builds", agora=datetime(2026, 9, 9, 7, 55))["video_id"])

    def test_publicacao_de_ONTEM_na_mesma_hora_nao_bloqueia(self):
        self._ledger([{"quando": "2026-09-08T17:12:45", "video_id": "x"}])
        self.assertIsNone(self.postar.publicou_neste_horario(
            "historias", agora=datetime(2026, 9, 9, 17, 7)))

    def test_sem_publicacao_nenhuma_libera(self):
        self._ledger([])
        self.assertIsNone(self.postar.publicou_neste_horario(
            "builds", agora=datetime(2026, 9, 9, 17, 7)))

    def test_linha_sem_data_nao_derruba(self):
        self._ledger([{"video_id": "sem data"}, {"quando": None}])
        self.assertIsNone(self.postar.publicou_neste_horario(
            "builds", agora=datetime(2026, 9, 9, 17, 7)))


class MotivoTests(Base):
    def test_o_motivo_diz_a_hora_e_o_video(self):
        """Quem le o log tem que saber que nao foi falha, foi regra."""
        self._ledger([{"quando": "2026-09-09T17:08:12",
                       "video_id": "historia:p03"}])
        ficha = self.postar._ja_foi_neste_horario(
            "historias", agora=datetime(2026, 9, 9, 17, 40))
        self.assertFalse(ficha["feito"])
        self.assertTrue(ficha["repetido"])
        self.assertIn("17:08", ficha["motivo"])
        self.assertIn("historia:p03", ficha["motivo"])

    def test_sem_publicacao_devolve_None(self):
        self._ledger([])
        self.assertIsNone(self.postar._ja_foi_neste_horario(
            "builds", agora=datetime(2026, 9, 9, 17, 7)))


class OndeEAplicadoTests(unittest.TestCase):
    def _corpo(self, nome: str) -> str:
        fonte = POSTAR.read_text(encoding="utf-8")
        inicio = fonte.index(f"def {nome}(")
        fim = fonte.find("\ndef ", inicio + 10)
        return fonte[inicio:fim if fim > 0 else len(fonte)]

    def test_a_guarda_vale_nos_DOIS_canais(self):
        for nome in ("postar_historia", "postar_build"):
            self.assertIn("_ja_foi_neste_horario(", self._corpo(nome), nome)

    def test_ela_vem_ANTES_de_escolher_o_video(self):
        """Escolher decodifica mp4 na vistoria: caro para depois desistir."""
        corpo = self._corpo("postar_historia")
        self.assertLess(corpo.index("_ja_foi_neste_horario("),
                        corpo.index("proxima_historia()"))

    def test_o_ensaio_NAO_e_bloqueado_pela_guarda(self):
        """`--ver` tem que responder o que postaria mesmo depois de postar.

        Cobra a INTENCAO e nao a forma: a guarda passou a ser consultada uma
        vez por DESTINO (em 10/09, quando o TikTok entrou na grade), entao o
        `if not so_ver:` de antes virou `None if so_ver else ...`. O que nao
        pode mudar e o efeito — em ensaio, a guarda nao e consultada.
        """
        for nome in ("postar_historia", "postar_build"):
            corpo = self._corpo(nome)
            trecho = corpo[:corpo.index("publicou_neste_horario(")]
            self.assertIn("so_ver", trecho, nome)
            # e o ensaio nunca chega a publicar
            self.assertIn('"motivo": "so vendo"', corpo, nome)


if __name__ == "__main__":
    unittest.main()
