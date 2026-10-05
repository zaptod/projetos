# -*- coding: utf-8 -*-
"""Ausencia tem de virar numero: noite sem conferencia, canal parado, id.

Os tres casos reais de setembro/2026 que nenhum alarme pegou, porque todo
alarme reage a evento e ausencia nao escreve linha:

  - a noite de 21/09 nao teve conferencia (nem coleta), e ninguem soube;
  - builds passou 25 e 26/09 com ZERO eventos no diario;
  - de 17 a 27/09 as linhas novas de historias ficaram sem `youtube_id`.

Cada sinal tem o caso CHEIO e o caso VAZIO lado a lado: sem dado, a resposta
e "nao medi" (`None`), nunca nota boa.
"""
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from builds.publicar import sinais

AGORA = datetime(2026, 9, 28, 5, 20)


def _evento(horas_atras: float, canal="builds", fabrica="publicacao",
            status="inicio"):
    quando = (AGORA - timedelta(hours=horas_atras)).astimezone(timezone.utc)
    return {"ts": quando.isoformat(timespec="seconds"), "canal": canal,
            "fabrica": fabrica, "status": status, "detalhe": "x"}


def _sem_config_real(caso: unittest.TestCase) -> None:
    """O 1o disparo vem do config REAL das historias; aqui, do padrao
    (07:02), para o teste nao depender do que o Adrian mudar na agenda."""
    real = sinais._config_da_agenda
    sinais._config_da_agenda = lambda: Path("E:/nao/existe/agenda.json")
    caso.addCleanup(setattr, sinais, "_config_da_agenda", real)


class ANoite(unittest.TestCase):

    def setUp(self):
        _sem_config_real(self)

    def test_o_dia_esperado_vira_no_servico_mais_a_folga(self):
        # A conferencia mora no servico do dia (07:02) desde 30/09/2026; com
        # a folga de 3 h, o dia D so e cobrado a partir das 10:02 de D.
        self.assertEqual("10:02", sinais.limite_do_servico())
        self.assertEqual(date(2026, 9, 27),
                         sinais.noite_esperada(datetime(2026, 9, 28, 5, 20)))
        # 06:37 (a virada antiga) e 07:35 (a conferencia real de 05/10):
        # o servico de hoje ainda esta na folga.
        self.assertEqual(date(2026, 9, 27),
                         sinais.noite_esperada(datetime(2026, 9, 28, 6, 37)))
        self.assertEqual(date(2026, 9, 27),
                         sinais.noite_esperada(datetime(2026, 9, 28, 7, 35)))
        self.assertEqual(date(2026, 9, 28),
                         sinais.noite_esperada(datetime(2026, 9, 28, 10, 2)))
        self.assertEqual(date(2026, 9, 28),
                         sinais.noite_esperada(datetime(2026, 9, 28, 22, 30)))

    def test_ficha_da_noite_esperada_cala(self):
        ficha = {"dia": "2026-09-28", "rodadas": ["01:28", "05:20"]}
        self.assertIsNone(sinais.noites_sem_conferencia(
            ficha, datetime(2026, 9, 28, 22, 30)))

    def test_a_noite_de_21_09(self):
        # O caso real: a ultima ficha antes de 22/09 era a de 20/09.
        buraco = sinais.noites_sem_conferencia(
            {"dia": "2026-09-20"}, datetime(2026, 9, 21, 22, 30))
        self.assertEqual({"esperada": "2026-09-21", "ultima": "2026-09-20",
                          "noites": 1}, buraco)

    def test_nunca_rodou_e_buraco_e_nao_silencio(self):
        # CASO ZERO: nenhuma ficha.
        buraco = sinais.noites_sem_conferencia({}, AGORA)
        self.assertIsNotNone(buraco)
        self.assertIsNone(buraco["ultima"])

    def test_conferencia_so_feita_a_mao_nao_cobre_a_noite(self):
        # O botao do painel as 14:00 regrava a ficha do dia; sem `rodadas`,
        # ele apagaria o rastro da noite que nao rodou.
        a_mao = {"dia": "2026-09-28", "rodadas": ["14:00"]}
        buraco = sinais.noites_sem_conferencia(
            a_mao, datetime(2026, 9, 28, 22, 30))
        self.assertEqual(1, buraco["noites"])

    def test_ficha_antiga_sem_rodadas_nao_acusa(self):
        # Antes de 28/09 a ficha nao tinha `rodadas`: nao sei, e nao "faltou".
        self.assertIsNone(sinais.noites_sem_conferencia(
            {"dia": "2026-09-28"}, datetime(2026, 9, 28, 22, 30)))

    def test_a_primeira_rodada_da_noite_ve_as_noites_puladas(self):
        self.assertEqual(["2026-09-21"], sinais.noites_puladas(
            {"dia": "2026-09-20", "rodadas": ["05:20"]}, date(2026, 9, 22)))
        self.assertEqual([], sinais.noites_puladas(
            {"dia": "2026-09-21", "rodadas": ["05:20"]}, date(2026, 9, 22)))
        # As rodadas seguintes da mesma noite nao repetem.
        self.assertEqual([], sinais.noites_puladas(
            {"dia": "2026-09-22", "rodadas": ["01:28"]}, date(2026, 9, 22)))
        # Primeira vez, sem ficha anterior: nada a dizer.
        self.assertEqual([], sinais.noites_puladas({}, date(2026, 9, 22)))
        # A de ontem so teve rodada feita a mao: a noite de ontem faltou.
        self.assertEqual(["2026-09-21"], sinais.noites_puladas(
            {"dia": "2026-09-21", "rodadas": ["14:00"]}, date(2026, 9, 22)))


class OServicoDoDia(unittest.TestCase):
    """Varredura de 05/10/2026, item 14: de 02 a 05/10 o celular recebeu
    "noite(s) sem conferencia" TODO DIA, com a conferencia rodando as
    07:04-07:35 no servico do dia. A regra pedia rodada antes das 06:37."""

    def setUp(self):
        _sem_config_real(self)

    def test_a_ficha_de_07_35_nao_gera_noite_pulada(self):
        # As fichas reais de 02 a 05/10 (sem `origens`, de antes do conserto).
        for anterior, hoje in ((["07:04"], date(2026, 10, 3)),
                               (["07:30"], date(2026, 10, 4)),
                               (["07:34"], date(2026, 10, 5)),
                               (["07:35"], date(2026, 10, 6))):
            dia = (hoje - timedelta(days=1)).isoformat()
            self.assertEqual([], sinais.noites_puladas(
                {"dia": dia, "rodadas": anterior}, hoje), (dia, anterior))
        self.assertIsNone(sinais.noites_sem_conferencia(
            {"dia": "2026-10-05", "rodadas": ["07:35"]},
            datetime(2026, 10, 5, 22, 30)))

    def test_a_origem_servico_cobre_o_dia_a_qualquer_hora(self):
        # Servico que atrasou (PC dormindo, trava ocupada) ainda e servico.
        ficha = {"dia": "2026-10-05", "rodadas": ["07:10", "14:00"],
                 "origens": ["painel", "servico"]}
        self.assertTrue(sinais.noite_rodou(ficha))
        self.assertEqual([], sinais.noites_puladas(ficha, date(2026, 10, 6)))
        self.assertIsNone(sinais.noites_sem_conferencia(
            ficha, datetime(2026, 10, 5, 22, 30)))

    def test_painel_nao_cobre_o_dia_nem_cedo(self):
        # Com origem gravada, a hora nao salva a rodada feita a mao.
        for hora in ("03:00", "07:10", "14:00"):
            ficha = {"dia": "2026-10-05", "rodadas": [hora],
                     "origens": ["painel"]}
            self.assertFalse(sinais.noite_rodou(ficha), hora)
            self.assertEqual(["2026-10-05"],
                             sinais.noites_puladas(ficha, date(2026, 10, 6)))
            buraco = sinais.noites_sem_conferencia(
                ficha, datetime(2026, 10, 5, 22, 30))
            self.assertEqual(1, buraco["noites"])

    def test_origem_desconhecida_nao_cobre(self):
        ficha = {"dia": "2026-10-05", "rodadas": ["07:35"],
                 "origens": ["servicO"]}
        self.assertFalse(sinais.noite_rodou(ficha))

    def test_origens_desalinhadas_viram_nao_sei_por_rodada(self):
        # Lista torta nao pode virar "servico": cai na regra da hora.
        self.assertTrue(sinais.noite_rodou(
            {"rodadas": ["07:35"], "origens": ["servico", "painel"]}))
        self.assertFalse(sinais.noite_rodou(
            {"rodadas": ["14:00"], "origens": []}))

    def test_CASO_ZERO_dia_sem_conferencia_continua_acendendo(self):
        # Nenhuma ficha em 04/10: a de 03/10 e a anterior da rodada de 05/10.
        self.assertEqual(["2026-10-04"], sinais.noites_puladas(
            {"dia": "2026-10-03", "rodadas": ["07:30"],
             "origens": ["servico"]}, date(2026, 10, 5)))
        buraco = sinais.noites_sem_conferencia(
            {"dia": "2026-10-03", "rodadas": ["07:30"],
             "origens": ["servico"]}, datetime(2026, 10, 5, 10, 2))
        self.assertEqual({"esperada": "2026-10-05", "ultima": "2026-10-03",
                          "noites": 2}, buraco)
        # Ficha com `rodadas` vazia: rodou ninguem.
        self.assertFalse(sinais.noite_rodou({"dia": "2026-10-05",
                                             "rodadas": []}))
        # Nenhuma ficha nunca: acende.
        self.assertIsNotNone(sinais.noites_sem_conferencia(
            {}, datetime(2026, 10, 5, 22, 30)))

    def test_o_servico_atrasado_acende_depois_da_folga(self):
        # Ultima ficha e a de ontem, e ja passou das 10:02: o de hoje faltou.
        ontem = {"dia": "2026-10-04", "rodadas": ["07:34"],
                 "origens": ["servico"]}
        self.assertIsNone(sinais.noites_sem_conferencia(
            ontem, datetime(2026, 10, 5, 10, 1)))
        self.assertEqual(1, sinais.noites_sem_conferencia(
            ontem, datetime(2026, 10, 5, 10, 2))["noites"])


class OPrimeiroDisparo(unittest.TestCase):

    def _config(self, dados):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        caminho = Path(pasta.name) / "agenda.json"
        caminho.write_text(json.dumps(dados) if not isinstance(dados, str)
                           else dados, encoding="utf-8")
        return caminho

    def test_o_1o_disparo_dentro_da_janela(self):
        caminho = self._config({"janela_pesada": {"inicio": 7, "fim": 22},
                                "horas": [1, 2, "07:02", "08:02", "23:02"]})
        self.assertEqual((7, 2), sinais.primeiro_disparo(caminho))
        self.assertEqual("10:02", sinais.limite_do_servico(caminho))

    def test_janela_que_atravessa_a_meia_noite(self):
        caminho = self._config({"janela_pesada": {"inicio": 22, "fim": 6},
                                "horas": [3, "22:30", 23]})
        self.assertEqual((22, 30), sinais.primeiro_disparo(caminho))
        # 22:30 + 3 h passa da meia-noite: o limite e o fim do dia.
        self.assertEqual("23:59", sinais.limite_do_servico(caminho))

    def test_hora_cheia_dispara_as_20(self):
        caminho = self._config({"janela_pesada": {"inicio": 8, "fim": 20},
                                "horas": [5, 9]})
        self.assertEqual((9, 20), sinais.primeiro_disparo(caminho))

    def test_config_torto_cai_no_padrao(self):
        for dados in ("{nao e json", {"horas": "x"},
                      {"janela_pesada": {"inicio": 7, "fim": 22},
                       "horas": [1, 2]}):
            self.assertEqual(sinais.PRIMEIRO_DISPARO_PADRAO,
                             sinais.primeiro_disparo(self._config(dados)))

    def test_o_config_real_e_lido(self):
        # Contrato com `historias/config/agenda.json`: o disparo lido cai na
        # hora em que a janela pesada abre.
        with open(sinais._config_da_agenda(), encoding="utf-8-sig") as fh:
            janela = json.load(fh)["janela_pesada"]
        hora, _minuto = sinais.primeiro_disparo()
        self.assertEqual(int(janela["inicio"]), hora)


class OsEventosDoCanal(unittest.TestCase):

    def _diario_cheio(self, builds=0, historias=40):
        # Um evento de historias bem velho garante que o diario cobre 24 h.
        eventos = [_evento(30, "historias")]
        eventos += [_evento(1 + n * 0.5, "historias") for n in range(historias)]
        eventos += [_evento(2 + n, "builds") for n in range(builds)]
        return eventos

    def test_builds_parado_acende(self):
        # 25 e 26/09/2026: builds 0, historias centenas.
        conta = sinais.eventos_por_canal(self._diario_cheio(builds=0), AGORA)
        self.assertEqual(0, conta["builds"]["eventos"])
        self.assertEqual(10, conta["builds"]["minimo"])
        self.assertIs(True, conta["builds"]["poucos"])
        self.assertIs(False, conta["historias"]["poucos"])

    def test_um_evento_por_horario_basta(self):
        conta = sinais.eventos_por_canal(self._diario_cheio(builds=10), AGORA)
        self.assertIs(False, conta["builds"]["poucos"])

    def test_o_alarme_do_observador_nao_conta_como_trabalho(self):
        # A ARMADILHA: a conferencia escreve dois erros por noite justamente
        # sobre o canal parado. Contados, fariam o morto parecer vivo.
        eventos = self._diario_cheio(builds=0)
        eventos += [_evento(3, "builds", fabrica="conferencia", status="erro")
                    for _ in range(12)]
        eventos += [_evento(3, "builds", fabrica="metricas", status="erro")
                    for _ in range(12)]
        conta = sinais.eventos_por_canal(eventos, AGORA)
        self.assertEqual(0, conta["builds"]["eventos"])
        self.assertIs(True, conta["builds"]["poucos"])

    def test_log_e_conversa_e_nao_trabalho(self):
        eventos = self._diario_cheio(builds=0)
        eventos += [_evento(3, "builds", fabrica="estudio", status="log")
                    for _ in range(50)]
        conta = sinais.eventos_por_canal(eventos, AGORA)
        self.assertIs(True, conta["builds"]["poucos"])

    def test_diario_vazio_nao_mede_e_nao_acusa(self):
        # CASO ZERO: nada lido cobre 0 h — `None`, e nao "poucos".
        conta = sinais.eventos_por_canal([], AGORA)
        self.assertEqual(0, conta["builds"]["horas_cobertas"])
        self.assertIsNone(conta["builds"]["poucos"])

    def test_diario_podado_encolhe_o_minimo(self):
        # O diario so cobre as ultimas 14 h (desde 15:20 de 27/09): cabem
        # nelas 7 horarios (15:37 ... 00:37). Nao se acusa ausencia no trecho
        # que nao foi lido.
        eventos = [_evento(14, "historias")] + [_evento(1, "historias")]
        conta = sinais.eventos_por_canal(eventos, AGORA)
        self.assertEqual(14.0, conta["builds"]["horas_cobertas"])
        self.assertEqual(7, conta["builds"]["minimo"])
        self.assertIs(True, conta["builds"]["poucos"])

    def test_janela_curta_demais_nao_acusa(self):
        # Cinco horas de diario sao evidencia fraca: `None`, nao alarme.
        eventos = [_evento(5, "historias")] + [_evento(1, "historias")]
        conta = sinais.eventos_por_canal(eventos, AGORA)
        self.assertEqual(5.0, conta["builds"]["horas_cobertas"])
        self.assertIsNone(conta["builds"]["poucos"])

    def test_evento_torto_nao_derruba(self):
        conta = sinais.eventos_por_canal([None, 3, {"ts": "x"}], AGORA)
        self.assertIn("builds", conta)


class OIdNoLedger(unittest.TestCase):

    def _linha(self, dias_atras: float, com_id: bool, **extra):
        quando = AGORA - timedelta(days=dias_atras)
        linha = {"plataforma": "youtube", "quando": quando.isoformat(),
                 "url": "https://youtu.be/x" if com_id else "publicado",
                 "youtube_id": "abc" if com_id else ""}
        linha.update(extra)
        return linha

    def test_reconciliacao_parada_acende(self):
        # 17 a 27/09/2026: as linhas novas de historias sem id.
        linhas = [self._linha(2, False) for _ in range(8)]
        linhas += [self._linha(3, True) for _ in range(2)]
        medida = sinais.cobertura_de_ids(linhas, AGORA)
        self.assertEqual((10, 2), (medida["linhas"], medida["com_id"]))
        self.assertIs(True, medida["baixa"])

    def test_tudo_com_id_e_nao_baixa(self):
        medida = sinais.cobertura_de_ids(
            [self._linha(2, True) for _ in range(5)], AGORA)
        self.assertIs(False, medida["baixa"])
        self.assertEqual(1.0, medida["cobertura"])

    def test_sem_linha_na_janela_e_nao_medi(self):
        # CASO ZERO: canal que nao publicou nada. Nao e 100%.
        medida = sinais.cobertura_de_ids([], AGORA)
        self.assertIsNone(medida["cobertura"])
        self.assertIsNone(medida["baixa"])

    def test_linha_de_hoje_e_linha_antiga_ficam_fora(self):
        # Hoje ainda nao passou uma noite de reconciliacao; o acervo antigo
        # nao muda nunca e so esconderia o numero novo.
        linhas = [self._linha(0.2, False), self._linha(30, False),
                  self._linha(2, True)]
        medida = sinais.cobertura_de_ids(linhas, AGORA)
        self.assertEqual(1, medida["linhas"])
        self.assertIs(False, medida["baixa"])

    def test_tiktok_e_linha_que_nao_saiu_nao_entram(self):
        linhas = [self._linha(2, False, plataforma="tiktok"),
                  self._linha(2, False, publicado=False),
                  self._linha(2, True)]
        self.assertEqual(1, sinais.cobertura_de_ids(linhas, AGORA)["linhas"])


class ODiarioInteiro(unittest.TestCase):

    def test_le_alem_das_1200_linhas_de_recentes(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "atividade.jsonl"
            arquivo.write_text("\n".join(
                json.dumps({"ts": "2026-09-27T10:00:00+00:00", "n": n})
                for n in range(3000)) + "\nnao e json\n", encoding="utf-8")
            self.assertEqual(3000, len(sinais.ler_diario(arquivo)))

    def test_diario_que_nao_abre_e_none(self):
        self.assertIsNone(sinais.ler_diario("E:/nao/existe/atividade.jsonl"))


if __name__ == "__main__":
    unittest.main()
