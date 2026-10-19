# -*- coding: utf-8 -*-
"""Um video em CADA HORARIO da grade — e nenhum repetido no mesmo horario.

A grade e a de `builds.grade` (00:37, 06:37, 09:37, 12:07, 15:37, 17:57,
20:37, 21:37, 22:37, 23:37), a mesma em que a agenda CRIA historia.
Correcao dele em 09/09/2026: "nao quero um video por dia, quero um video em
todos esses horarios".

O que esta travado aqui e so a REPETICAO dentro do mesmo horario, que e um
risco real e recente:

  - em 08/09 sairam DOIS de cada canal porque uma rodada manual cruzou com a
    agendada (17:06 e 17:12 nas historias, 17:07 e 17:13 nos builds);
  - em 09/09 `StartWhenAvailable` foi ligado nas dez tarefas para que horario
    perdido seja recuperado — certo para nao perder o disparo, e que por
    definicao cria disparo fora da hora.

O HORARIO E O DA GRADE, NAO A HORA DO RELOGIO (decisao do Adrian em
29/09/2026, `guarda-hora-da-grade`). Ate entao a janela era a hora do
relogio, e em 28/09 a `historia_00027:p01`, subida a mao as 22:12, contou
como o post das 22:37: a rodada leu "ja saiu nesta hora" e o horario ficou
sem video novo. Um post pertence ao horario que ele COBRE — o ultimo que ja
tinha vencido quando a linha foi gravada —, e a identidade desse horario e
`conferencia.chave_do_horario` (dia de grade, hora), a MESMA do placar de
metas (`remoto/relatorios.py`) e da conferencia da madrugada. Ha um teste
cruzado no fim deste arquivo garantindo que os tres nao discordam.

A fonte e o LEDGER, nao um arquivo de controle novo: ele ja diz o que foi
publicado, e uma segunda fonte que discordasse dele seria pior do que nenhuma.

Rode de dentro de historias/:
    python -m unittest tests.test_um_por_dia_regressions -v
"""
from __future__ import annotations

import importlib.util
import unittest
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
POSTAR = RAIZ.parent / "ferramentas" / "postar.py"
RELATORIOS = RAIZ.parent / "remoto" / "relatorios.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_grade", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _relatorios():
    """`remoto` nao esta no caminho de importacao de historias/; o arquivo
    e carregado pelo caminho, como o `postar.py`."""
    spec = importlib.util.spec_from_file_location("relatorios_cruzado",
                                                  RELATORIOS)
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
    def test_publicacao_no_MESMO_horario_bloqueia(self):
        """17:08 e 17:40 sao os dois o horario das 15:37 (o ultimo vencido)."""
        self._ledger([{"quando": "2026-09-09T17:08:12",
                       "video_id": "historia_00003:celular:p03"}])
        achado = self.postar.publicou_neste_horario(
            "historias", agora=datetime(2026, 9, 9, 17, 40))
        self.assertIsNotNone(achado)
        self.assertEqual("historia_00003:celular:p03", achado["video_id"])

    def test_publicacao_no_horario_ANTERIOR_nao_bloqueia(self):
        """Foi por isto que a versao 'um por dia' estava errada: o post das
        06:40 e do 06:37; a rodada das 09:40 e do 09:37."""
        self._ledger([{"quando": "2026-09-28T06:40:00", "video_id": "x"}])
        self.assertIsNone(self.postar.publicou_neste_horario(
            "historias", agora=datetime(2026, 9, 28, 9, 40)))

    def test_horarios_seguidos_da_grade_sao_independentes(self):
        """20:37, 21:37 e 22:37 sao seguidos: cada um publica o seu."""
        self._ledger([{"quando": "2026-09-28T20:40:30", "video_id": "vinte"},
                      {"quando": "2026-09-28T21:40:30",
                       "video_id": "vinte e um"}])
        self.assertIsNone(self.postar.publicou_neste_horario(
            "builds", agora=datetime(2026, 9, 28, 22, 40)))
        self.assertEqual("vinte e um", self.postar.publicou_neste_horario(
            "builds", agora=datetime(2026, 9, 28, 21, 55))["video_id"])

    def test_publicacao_de_ONTEM_no_mesmo_horario_nao_bloqueia(self):
        self._ledger([{"quando": "2026-09-08T17:12:45", "video_id": "x"}])
        self.assertIsNone(self.postar.publicou_neste_horario(
            "historias", agora=datetime(2026, 9, 9, 17, 7)))

    def test_sem_publicacao_nenhuma_libera(self):
        self._ledger([])
        self.assertIsNone(self.postar.publicou_neste_horario(
            "builds", agora=datetime(2026, 9, 9, 17, 7)))

    def test_linha_sem_data_nao_derruba(self):
        self._ledger([{"video_id": "sem data"}, {"quando": None},
                      {"quando": "ontem a noite", "video_id": "ilegivel"}])
        self.assertIsNone(self.postar.publicou_neste_horario(
            "builds", agora=datetime(2026, 9, 9, 17, 7)))


class PeloHorarioDaGradeTests(Base):
    """A guarda conta pelo horario da grade (decisao de 29/09/2026).

    Conta de mao, com `conferencia.chave_do_horario`:
      28/09 22:12 -> (28/09, 21)    28/09 22:38 -> (28/09, 22)
      28/09 22:40 -> (28/09, 22)    28/09 22:50 -> (28/09, 22)
      29/09 00:10 -> (28/09, 23)    29/09 00:20 -> (28/09, 23)
      29/09 00:40 -> (28/09, 0)     28/09 18:01 -> (28/09, 17)
    """

    def test_upload_avulso_as_2212_nao_gasta_o_2237(self):
        """O caso de 28/09: a h27 p01 subiu a mao as 22:12 e, pela hora do
        relogio, a rodada das 22:37 achou que o YouTube ja tinha saido."""
        self._ledger([{"quando": "2026-09-28T22:12:00", "plataforma": "youtube",
                       "video_id": "historia_00027:celular:p01"}])
        self.assertIsNone(self.postar.publicou_neste_horario(
            "historias", "youtube", datetime(2026, 9, 28, 22, 38)))
        # ...mas ela cobre o horario das 21:37: a rodada dele, se atrasada
        # ate as 22:20, nao publica um segundo.
        self.assertIsNotNone(self.postar.publicou_neste_horario(
            "historias", "youtube", datetime(2026, 9, 28, 22, 20)))

    def test_recuperacao_depois_da_meia_noite_e_do_2337_da_vespera(self):
        self._ledger([{"quando": "2026-09-29T00:10:00", "plataforma": "tiktok",
                       "video_id": "x"}])
        # ainda o das 23:37 de 28/09 (o 00:37 nao venceu)
        self.assertIsNotNone(self.postar.publicou_neste_horario(
            "historias", "tiktok", datetime(2026, 9, 29, 0, 20)))
        # a rodada das 00:37 e outro horario
        self.assertIsNone(self.postar.publicou_neste_horario(
            "historias", "tiktok", datetime(2026, 9, 29, 0, 40)))

    def test_dois_posts_no_mesmo_horario_barrado(self):
        self._ledger([{"quando": "2026-09-28T22:40:00", "plataforma": "youtube",
                       "video_id": "primeiro"}])
        achado = self.postar.publicou_neste_horario(
            "builds", "youtube", datetime(2026, 9, 28, 22, 50))
        self.assertEqual("primeiro", achado["video_id"])
        ficha = self.postar._ja_foi_neste_horario(
            "builds", "youtube", datetime(2026, 9, 28, 22, 50))
        self.assertIn("22:40", ficha["motivo"])
        self.assertIn("horario das 22:37", ficha["motivo"])

    def test_a_rodada_que_cruza_a_hora_continua_sendo_a_das_1757(self):
        """A linha das 18:01 e a das 17:57; o disparo recuperado as 18:05
        nao publica de novo — e a hora do relogio (18) diria que sim."""
        self._ledger([{"quando": "2026-09-28T18:01:00", "plataforma": "youtube",
                       "video_id": "x"}])
        self.assertIsNotNone(self.postar.publicou_neste_horario(
            "builds", "youtube", datetime(2026, 9, 28, 18, 5)))

    def test_caso_ZERO_nada_no_ledger_libera_todo_horario(self):
        self._ledger([])
        for plataforma in ("youtube", "tiktok"):
            for agora in (datetime(2026, 9, 28, 22, 38),
                          datetime(2026, 9, 29, 0, 20),
                          datetime(2026, 9, 29, 0, 40)):
                self.assertIsNone(self.postar.publicou_neste_horario(
                    "historias", plataforma, agora), (plataforma, agora))
                self.assertIsNone(self.postar._ja_foi_neste_horario(
                    "historias", plataforma, agora), (plataforma, agora))


class BateComMetasEConferenciaTests(unittest.TestCase):
    """A guarda, o placar de metas do app e a conferencia respondem "a que
    horario pertence este post?" pela MESMA chave. Se um dia divergirem, o
    app diz "10/10" para um dia em que a guarda deixou um horario vazio."""

    INSTANTES = (datetime(2026, 9, 28, 22, 12), datetime(2026, 9, 28, 22, 40),
                 datetime(2026, 9, 29, 0, 10), datetime(2026, 9, 29, 0, 39),
                 datetime(2026, 9, 28, 18, 1), datetime(2026, 9, 29, 6, 40),
                 datetime(2026, 9, 28, 0, 5))

    def setUp(self):
        from builds.publicar import conferencia
        self.conferencia = conferencia
        self.relatorios = _relatorios()
        self.postar = _postar()

    def test_a_chave_e_a_mesma_nos_tres_lugares(self):
        c = self.conferencia
        for instante in self.INSTANTES:
            guarda = c.chave_do_horario(instante, "youtube")
            metas = self.relatorios._dia_de_grade(instante, "youtube")
            dia, hora = c._horario_da_grade(instante, "youtube")
            conferida = (c._dia_de_grade(dia, hora, "youtube"), hora)
            self.assertEqual(guarda, metas, instante)
            self.assertEqual(guarda, conferida, instante)
        self.assertEqual((date(2026, 9, 28), 21),
                         c.chave_do_horario(datetime(2026, 9, 28, 22, 12)))
        self.assertEqual((date(2026, 9, 28), 23),
                         c.chave_do_horario(datetime(2026, 9, 29, 0, 10)))
        self.assertEqual((date(2026, 9, 28), 0),
                         c.chave_do_horario(datetime(2026, 9, 29, 0, 39)))

    def test_a_guarda_barra_exatamente_o_horario_que_o_placar_conta(self):
        ledger = [{"quando": "2026-09-28T22:12:00", "plataforma": "youtube",
                   "video_id": "a"},
                  {"quando": "2026-09-28T22:40:00", "plataforma": "youtube",
                   "video_id": "b"},
                  {"quando": "2026-09-29T00:10:00", "plataforma": "youtube",
                   "video_id": "c"}]
        self.postar._publicados_do_canal = lambda _c: list(ledger)
        pagos = {self.relatorios._dia_de_grade(
            self.relatorios._instante(l["quando"]), "youtube") for l in ledger}
        self.assertEqual({(date(2026, 9, 28), 21), (date(2026, 9, 28), 22),
                          (date(2026, 9, 28), 23)}, pagos)
        esperado = {datetime(2026, 9, 28, 22, 20): True,
                    datetime(2026, 9, 28, 22, 50): True,
                    datetime(2026, 9, 28, 23, 40): True,
                    datetime(2026, 9, 29, 0, 20): True,
                    datetime(2026, 9, 29, 0, 40): False,
                    datetime(2026, 9, 29, 6, 40): False,
                    datetime(2026, 9, 28, 20, 40): False}
        for agora, barra in esperado.items():
            achado = self.postar.publicou_neste_horario("builds", "youtube",
                                                        agora)
            self.assertEqual(barra, achado is not None, agora)
            self.assertEqual(
                barra,
                self.relatorios._dia_de_grade(agora, "youtube") in pagos, agora)


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

    def test_a_guarda_nao_usa_a_hora_do_relogio(self):
        """Decisao de 29/09/2026: a identidade do horario e a chave da
        conferencia, e nao um `strftime` da hora."""
        corpo = self._corpo("publicou_neste_horario")
        self.assertIn("chave_do_horario(", corpo)
        self.assertNotIn("strftime", corpo)


if __name__ == "__main__":
    unittest.main()
