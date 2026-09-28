# -*- coding: utf-8 -*-
"""Canal parado tem de ACENDER na conferencia da noite — e dia cheio, nao.

Em 24, 25, 26 e 27/09/2026 a conferencia devolveu `taxa 1,0` e veredito
`limpo` para o canal de builds com ZERO publicacoes no dia. A pergunta que
ela fazia era so "o que o ledger afirma esta no canal?" — e um canal que nao
publica nada nao afirma nada, entao passava com nota maxima.

O conserto (a973437) criou o `deficit`, mas contava o dia do CALENDARIO. A
conferencia roda de madrugada (01:28 a 05:20): as 05:20 o dia do calendario
so tem o horario das 00:37 vencido, entao um dia 10/10 dava deficit 9 toda
noite. O dia conferido agora e o DIA DE GRADE que acabou de fechar — 06:37
ate 00:37 do dia seguinte — e todo caso aqui roda com o relogio das 05:20.
"""
import unittest
from datetime import date, datetime, timedelta

from builds import grade
from builds.publicar import conferencia

# O relogio da ultima conferencia da madrugada de 28/09/2026.
AS_0520 = datetime(2026, 9, 28, 5, 20)
DIA_DE_GRADE = date(2026, 9, 27)
# Onde o dia de grade de 27/09 abre. Fixado aqui de proposito: se a grade
# mudar, `test_o_dia_de_grade_vai_das_0637_as_0037` avisa que estes casos
# precisam ser relidos.
ABRE = datetime(2026, 9, 27, 6, 37)

_ACEITOS_DE_VERDADE = None


def setUpModule():
    # HERMETICO: sem isto, `conferir` sem `aceitos=` leria a lista REAL de
    # rascunhos aceitos do runtime do Adrian.
    global _ACEITOS_DE_VERDADE
    _ACEITOS_DE_VERDADE = conferencia.rascunhos_aceitos
    conferencia.rascunhos_aceitos = lambda: {}


def tearDownModule():
    conferencia.rascunhos_aceitos = _ACEITOS_DE_VERDADE


def _horarios_do_dia():
    """O instante de cada horario do dia de grade de 27/09, em ordem.

    O das 00:37 cai no calendario de 28/09: e o ultimo do dia de grade.
    """
    saida = []
    for h in grade.horas_da_plataforma("youtube"):
        instante = datetime(2026, 9, 27, h, grade.minuto(h))
        if instante < ABRE:
            instante += timedelta(days=1)
        saida.append(instante)
    return sorted(saida)


def _post(n, instante, *, privacidade="public", youtube_id=None):
    """(linha do ledger, video no canal) de um post 2 min depois do horario.

    Os 2 min sao o upload: o ledger grava quando a publicacao termina.
    """
    quando = instante + timedelta(minutes=2)
    vid = youtube_id or f"y{n}"
    linha = {"plataforma": "youtube", "video_id": f"v{n}",
             "titulo": f"titulo {n}", "youtube_id": vid,
             "quando": quando.isoformat(timespec="seconds")}
    no_canal = {"id": vid, "titulo": f"titulo {n}",
                "publicado_em": (quando + timedelta(hours=3)
                                 ).isoformat(timespec="seconds") + "Z",
                "privacidade": privacidade}
    return linha, no_canal


def _dia(instantes, **kw):
    pares = [_post(n, t, **kw) for n, t in enumerate(instantes)]
    return [p[0] for p in pares], [p[1] for p in pares]


def _conferir(publicados, no_canal, agora=AS_0520, **kw):
    return conferencia.conferir("builds", publicados=publicados,
                                no_canal=no_canal, agora=agora, aceitos={},
                                **kw)


class ODiaDeGradeAs0520(unittest.TestCase):
    """Os tres casos pedidos: cheio, ZERO e parcial, com o relogio das 05:20."""

    def test_o_dia_de_grade_vai_das_0637_as_0037(self):
        horarios = _horarios_do_dia()
        self.assertEqual(ABRE, horarios[0])
        self.assertEqual(datetime(2026, 9, 28, 0, 37), horarios[-1])
        ficha = _conferir([], [])
        self.assertEqual("2026-09-27", ficha["dia_de_grade"])
        self.assertEqual(["2026-09-27T06:37", "2026-09-28T00:37"],
                         ficha["janela_da_grade"])
        # O arquivo da ficha continua sendo o do dia em que ela rodou.
        self.assertEqual("2026-09-28", ficha["dia"])

    def test_dia_10_de_10_nao_tem_deficit(self):
        publicados, no_canal = _dia(_horarios_do_dia())
        ficha = _conferir(publicados, no_canal)
        self.assertEqual(len(grade.horas_da_plataforma("youtube")),
                         ficha["slots_da_grade"])
        self.assertEqual(ficha["slots_da_grade"], ficha["horarios_cumpridos"])
        self.assertEqual(0, ficha["deficit"])
        self.assertEqual([], ficha["horarios_em_falta"])
        self.assertEqual("cumprida", ficha["grade"])
        self.assertEqual("limpo", ficha["veredito"])

    def test_dia_0_de_10_tem_deficit_cheio(self):
        """O CASO ZERO: nada no ledger e nada no canal."""
        ficha = _conferir([], [])
        self.assertEqual(0, ficha["horarios_cumpridos"])
        self.assertEqual(0, ficha["linhas_no_dia_de_grade"])
        self.assertEqual(ficha["slots_da_grade"], ficha["deficit"])
        self.assertEqual(10, ficha["deficit"])
        self.assertEqual([f"{t:%H:%M}" for t in _horarios_do_dia()],
                         ficha["horarios_em_falta"])
        self.assertEqual("em falta", ficha["grade"])
        # As duas perguntas continuam separadas: um canal parado tem ledger
        # coerente (taxa 1,0, limpo) e grade furada. Por isso a grade e um
        # veredito proprio.
        self.assertEqual(1.0, ficha["taxa"])
        self.assertEqual("limpo", ficha["veredito"])

    def test_dia_parcial_tem_o_deficit_dos_horarios_que_faltaram(self):
        horarios = _horarios_do_dia()
        faltaram = [horarios[1], horarios[4], horarios[-1]]
        publicados, no_canal = _dia([t for t in horarios if t not in faltaram])
        ficha = _conferir(publicados, no_canal)
        self.assertEqual(len(horarios) - 3, ficha["horarios_cumpridos"])
        self.assertEqual(3, ficha["deficit"])
        self.assertEqual([f"{t:%H:%M}" for t in faltaram],
                         ficha["horarios_em_falta"])
        self.assertEqual("em falta", ficha["grade"])

    def test_post_das_0037_conta_para_o_dia_de_grade_anterior(self):
        # 00:39 de 28/09 no calendario, mas o ultimo horario do dia de 27/09.
        publicados, no_canal = _dia([datetime(2026, 9, 28, 0, 37)])
        ficha = _conferir(publicados, no_canal)
        self.assertEqual("2026-09-27", ficha["dia_de_grade"])
        self.assertEqual(1, ficha["horarios_cumpridos"])
        self.assertNotIn("00:37", ficha["horarios_em_falta"])
        self.assertEqual(9, ficha["deficit"])
        # E NAO paga o dia de grade de 28/09, conferido na noite seguinte.
        seguinte = _conferir(publicados, no_canal,
                             agora=AS_0520 + timedelta(days=1))
        self.assertEqual("2026-09-28", seguinte["dia_de_grade"])
        self.assertEqual(0, seguinte["horarios_cumpridos"])
        self.assertEqual(10, seguinte["deficit"])


class ODiaConferido(unittest.TestCase):

    def test_o_relogio_da_madrugada_confere_o_dia_que_acabou(self):
        for agora, esperado in (
                (datetime(2026, 9, 28, 1, 28), date(2026, 9, 27)),
                (datetime(2026, 9, 28, 5, 20), date(2026, 9, 27)),
                # O das 00:37 ainda nao venceu: o de 27 nao fechou.
                (datetime(2026, 9, 28, 0, 30), date(2026, 9, 26)),
                # De dia, o de 28 esta em curso: o fechado e o de 27.
                (datetime(2026, 9, 28, 14, 0), date(2026, 9, 27))):
            with self.subTest(agora=agora):
                self.assertEqual(
                    esperado, conferencia.dia_de_grade_fechado(agora))

    def test_recuperacao_antes_da_abertura_ainda_e_do_dia_anterior(self):
        # O disparo das 00:37 que so saiu as 06:34 e aquele horario,
        # atrasado — e nao um horario de 28/09.
        linha, video = _post(0, datetime(2026, 9, 28, 6, 32))
        ficha = _conferir([linha], [video],
                          agora=datetime(2026, 9, 28, 7, 0))
        self.assertEqual("2026-09-27", ficha["dia_de_grade"])
        self.assertEqual(1, ficha["horarios_cumpridos"])
        self.assertNotIn("00:37", ficha["horarios_em_falta"])

    def test_a_janela_de_dias_nao_corta_o_dia_de_grade(self):
        # Com `--dias 0` a janela do ledger comeca em 28/09, e a parte do dia
        # de grade antes da meia-noite ficaria de fora da conta.
        publicados, no_canal = _dia(_horarios_do_dia())
        ficha = _conferir(publicados, no_canal, dias=0)
        self.assertEqual(0, ficha["deficit"])

    def test_so_hoje_confere_o_dia_de_grade_da_vespera(self):
        # Quem passa so `hoje` recebe o relogio no fim desse dia.
        ficha = conferencia.conferir("builds", publicados=[], no_canal=[],
                                     hoje=date(2026, 9, 27), aceitos={})
        self.assertEqual("2026-09-26", ficha["dia_de_grade"])
        self.assertEqual("2026-09-27", ficha["dia"])


class OQueNaoPagaHorario(unittest.TestCase):
    """Numerador e denominador falam de HORARIO: o que nao e horario com
    video publico no canal nao entra."""

    def test_linha_sem_video_no_canal_nao_paga(self):
        """Fantasma nao paga horario: seria o ledger medindo a si mesmo."""
        publicados, _ = _dia(_horarios_do_dia())
        ficha = _conferir(publicados, [])
        self.assertEqual(10, ficha["linhas_no_dia_de_grade"])
        self.assertEqual(0, ficha["horarios_cumpridos"])
        self.assertEqual(10, ficha["deficit"])
        # O ledger afirmando o que o canal nao tem continua sendo "sujo":
        # sao dois defeitos distintos e as duas perguntas continuam vivas.
        self.assertEqual("sujo", ficha["veredito"])

    def test_rascunho_no_canal_nao_paga(self):
        # A assinatura de 15/09: o ledger diz publicado, o canal tem o video
        # e ele esta privado. Para quem assiste, o horario ficou vazio.
        publicados, no_canal = _dia(_horarios_do_dia(), privacidade="private")
        ficha = _conferir(publicados, no_canal)
        self.assertEqual(0, ficha["horarios_cumpridos"])
        self.assertEqual(10, ficha["deficit"])

    def test_duas_linhas_no_mesmo_horario_pagam_um(self):
        # A normal e a recuperacao que anda junto: dez linhas, um horario.
        inicio = _horarios_do_dia()[0]
        publicados, no_canal = _dia(
            [inicio + timedelta(minutes=m) for m in range(0, 50, 5)])
        ficha = _conferir(publicados, no_canal)
        self.assertEqual(10, ficha["linhas_no_dia_de_grade"])
        self.assertEqual(1, ficha["horarios_cumpridos"])
        self.assertEqual(9, ficha["deficit"])

    def test_o_mesmo_video_em_duas_linhas_paga_um(self):
        # I9ETJSGR1A0 as 07:08 e as 08:08 de 15/09/2026: duas linhas, um
        # video. Em horarios diferentes, pagaria dois.
        horarios = _horarios_do_dia()
        a, video = _post(0, horarios[0], youtube_id="I9ETJSGR1A0")
        b, _ = _post(1, horarios[1], youtube_id="I9ETJSGR1A0")
        ficha = _conferir([a, b], [video])
        self.assertEqual(1, ficha["horarios_cumpridos"])

    def test_a_outra_plataforma_nao_paga(self):
        publicados, no_canal = _dia(_horarios_do_dia())
        for linha in publicados:
            linha["plataforma"] = "tiktok"
        ficha = _conferir(publicados, no_canal)
        self.assertEqual(0, ficha["horarios_cumpridos"])


class OAlarmeDaGrade(unittest.TestCase):
    """O alarme e a linha de erro no diario. Com o relogio das 05:20: calado
    depois de um dia 10/10, aceso depois de um dia 0/10."""

    def _rodar(self, publicados, no_canal):
        from builds import atividade
        from builds.publicar import metricas
        avisos = []
        reais = (metricas.publicados, conferencia.buscar_no_canal,
                 conferencia.salvar, atividade.registrar)
        metricas.publicados = lambda canal="builds": publicados
        conferencia.buscar_no_canal = lambda *a, **k: no_canal
        conferencia.salvar = lambda f: None
        atividade.registrar = lambda *a, **k: avisos.append((a, k))

        def restaurar():
            (metricas.publicados, conferencia.buscar_no_canal,
             conferencia.salvar, atividade.registrar) = reais

        self.addCleanup(restaurar)
        fichas = conferencia.conferir_tudo(("builds",), log=lambda _t: None,
                                           agora=AS_0520)
        return fichas["builds"], avisos

    def test_dia_cheio_nao_acende(self):
        ficha, avisos = self._rodar(*_dia(_horarios_do_dia()))
        self.assertEqual(0, ficha["deficit"])
        self.assertEqual([], avisos)

    def test_dia_zero_acende_uma_vez_com_o_numero(self):
        ficha, avisos = self._rodar([], [])
        self.assertEqual(10, ficha["deficit"])
        (args, kw), = avisos
        self.assertEqual("conferencia", args[0])
        self.assertEqual("builds", kw.get("canal"))
        self.assertIn("0 de 10", args[2])
        self.assertIn("2026-09-27 06:37 a 2026-09-28 00:37", args[2])
        self.assertIn("0 linha(s) no ledger", args[2])


if __name__ == "__main__":
    unittest.main()
