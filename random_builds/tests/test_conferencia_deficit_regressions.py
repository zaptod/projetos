# -*- coding: utf-8 -*-
"""Canal parado tem de ACENDER na conferencia da noite.

Em 24, 25, 26 e 27/09/2026 a conferencia devolveu `taxa 1,0` e veredito
`limpo` para o canal de builds com ZERO publicacoes no dia. A pergunta que
ela fazia era so "o que o ledger afirma esta no canal?" — e um canal que nao
publica nada nao afirma nada, entao passava com nota maxima. Quem nao publica
nao pode tirar a mesma nota de quem publicou os dez horarios.
"""
import unittest
from datetime import date

from builds import grade
from builds.publicar import conferencia

HOJE = date(2026, 9, 27)


def _linhas(quantas, dia="2026-09-27"):
    return [{"plataforma": "youtube", "video_id": f"v{i}",
             "titulo": f"titulo {i}", "youtube_id": f"y{i}",
             "quando": f"{dia}T1{i}:05:00"} for i in range(quantas)]


def _canal(quantas, dia="2026-09-27", privacidade="public"):
    return [{"id": f"y{i}", "titulo": f"titulo {i}",
             "publicado_em": f"{dia}T1{i}:06:00Z",
             "privacidade": privacidade} for i in range(quantas)]


class CanalParadoReprova(unittest.TestCase):
    def test_zero_publicacoes_no_dia_suja_o_veredito(self):
        ficha = conferencia.conferir("builds", publicados=[], no_canal=[],
                                     hoje=HOJE)
        self.assertEqual(ficha["grade"], "em falta")
        self.assertEqual(ficha["publicados_confirmados_hoje"], 0)
        self.assertEqual(ficha["deficit"],
                         len(grade.horas_da_plataforma("youtube")))
        # A taxa antiga continua 1,0 sem linha nenhuma: e por isso que ela
        # sozinha nunca poderia ter pegado este caso.
        self.assertEqual(ficha["taxa"], 1.0)

    def test_grade_cumprida_fica_limpa(self):
        quantos = len(grade.horas_da_plataforma("youtube"))
        ficha = conferencia.conferir(
            "builds", publicados=_linhas(quantos), no_canal=_canal(quantos),
            hoje=HOJE)
        self.assertEqual(ficha["deficit"], 0)
        self.assertEqual(ficha["publicados_confirmados_hoje"], quantos)
        self.assertEqual(ficha["grade"], "cumprida")

    def test_linha_sem_video_no_canal_nao_conta_como_cumprida(self):
        """Fantasma nao paga horario: seria o ledger medindo a si mesmo."""
        quantos = len(grade.horas_da_plataforma("youtube"))
        ficha = conferencia.conferir(
            "builds", publicados=_linhas(quantos), no_canal=[], hoje=HOJE)
        self.assertEqual(ficha["publicados_confirmados_hoje"], 0)
        self.assertEqual(ficha["deficit"], quantos)
        self.assertEqual(ficha["grade"], "em falta")
        # O ledger afirmando o que o canal nao tem continua sendo "sujo":
        # sao dois defeitos distintos e as duas perguntas continuam vivas.
        self.assertEqual(ficha["veredito"], "sujo")

    def test_publicacao_de_ontem_nao_paga_o_horario_de_hoje(self):
        ficha = conferencia.conferir(
            "builds", publicados=_linhas(3, dia="2026-09-26"),
            no_canal=_canal(3, dia="2026-09-26"), hoje=HOJE)
        self.assertEqual(ficha["publicados_confirmados_hoje"], 0)
        self.assertGreater(ficha["deficit"], 0)


if __name__ == "__main__":
    unittest.main()
