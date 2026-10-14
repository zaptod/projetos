# -*- coding: utf-8 -*-
"""Relatorio que diz "metrica em dia" com ZERO coletado e medidor verde.

Dois caminhos davam isso ate 14/10/2026:

1. A coleta que volta `vazio` (0 videos, sem excecao — ledger que some,
   caminho errado) renovava `ultimo_ok`. A pagina Confiabilidade e o
   relatorio das 22:30 leem `ultimo_ok`: diriam "em dia" sem um numero novo.
2. `desempenho.atualizado_em` era o mtime do `*.json` mais novo de
   `_metricas` — e a marca do dia mora ali e e regravada ate com erro.

O caminho inteiro aqui: a coleta (dublada um nivel abaixo, marca numa pasta
descartavel) grava a marca, e o relatorio le ESSA marca.
"""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from builds import atividade
from builds.publicar import metricas, sinais
from builds.publicar import tiktok_metricas as T
from panorama import confiabilidade as C
from panorama import desempenho

VELHA = "2026-10-12T07:17:18"


class _Coleta(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        reais = (metricas.MARCA_DO_DIA, metricas.reconciliar,
                 metricas.atualizar, T.coletar, atividade.registrar,
                 sinais._config_da_agenda)
        self.addCleanup(self._volta, reais)
        metricas.MARCA_DO_DIA = Path(tmp.name) / "_atualizado_em.json"
        metricas.reconciliar = lambda canal, log=print: 0
        atividade.registrar = lambda *a, **k: None
        sinais._config_da_agenda = lambda: "E:/nao/existe/agenda.json"
        self.vazio = False

        def atualizar(log=print, canal="builds"):
            return [] if self.vazio else [{"youtube_id": f"{canal}-1"}]

        def coletar(canal, log=print, resumo=None, **_k):
            return [] if self.vazio else [{"tiktok_id": f"{canal}-t"}]

        metricas.atualizar = atualizar
        T.coletar = coletar

    @staticmethod
    def _volta(reais):
        (metricas.MARCA_DO_DIA, metricas.reconciliar, metricas.atualizar,
         T.coletar, atividade.registrar, sinais._config_da_agenda) = reais

    def _rodar(self, chave):
        metricas.atualizar_uma_vez_por_dia(log=lambda *_a: None, chave=chave)

    def _envelhecer(self):
        """A noite boa foi a de 12/10: `ultimo_ok` de dois dias atras."""
        marca = metricas.ler_marca()
        for ficha in marca["partes"].values():
            ficha["ultimo_ok"] = VELHA
            ficha["quando"] = VELHA
        metricas._gravar_marca(marca["dia"], marca["partes"])

    def _alertas_de_metrica(self):
        agora = datetime.now()
        ficha = C.hoje(agora.date().isoformat(), builds=[], historias=[],
                       eventos=[], conferencias={}, marca=metricas.ler_marca(),
                       agora=agora)
        return ficha, [a for a in ficha["alertas"] if "métrica" in a]


class ZeroNaoEMetricaEmDiaTests(_Coleta):

    def test_ledger_que_sumiu_acende_no_relatorio(self):
        self._rodar("dia-2026-10-12")
        self._envelhecer()
        self.vazio = True
        self._rodar("dia-2026-10-14")
        ficha, alertas = self._alertas_de_metrica()
        self.assertEqual(4, len(alertas), alertas)
        self.assertTrue(all("falhou" in a and "ColetaVazia" in a
                            for a in alertas), alertas)
        self.assertNotEqual("ok", ficha["veredito"])

    def test_nunca_mediu_nada_e_nenhuma_coleta_boa(self):
        self.vazio = True
        self._rodar("dia-2026-10-14")
        _ficha, alertas = self._alertas_de_metrica()
        self.assertEqual(4, sum("nenhuma coleta boa" in a for a in alertas),
                         alertas)

    def test_noite_boa_de_verdade_nao_acende(self):
        self._rodar("dia-2026-10-14")
        _ficha, alertas = self._alertas_de_metrica()
        self.assertEqual([], alertas)


class AtualizadoEmDoDesempenhoTests(_Coleta):

    def test_marca_regravada_com_erro_nao_vira_atualizado_agora(self):
        self._rodar("dia-2026-10-12")
        self._envelhecer()
        self.vazio = True
        self._rodar("dia-2026-10-14")     # a marca e regravada AGORA
        self.assertEqual("2026-10-12T07:17", desempenho._quando_atualizou())

    def test_caso_zero_sem_marca_e_vazio(self):
        self.assertEqual("", desempenho._quando_atualizou(marca={}))
        self.assertEqual("", desempenho._quando_atualizou(marca=None))

    def test_parte_que_nunca_coletou_nao_deixa_dizer_atualizado(self):
        self.vazio = True
        self._rodar("dia-2026-10-14")
        self.assertEqual("", desempenho._quando_atualizou())

    def test_a_mais_velha_das_partes_manda(self):
        self._rodar("dia-2026-10-14")
        marca = metricas.ler_marca()
        marca["partes"]["historias_tiktok"]["ultimo_ok"] = VELHA
        self.assertEqual("2026-10-12T07:17",
                         desempenho._quando_atualizou(marca=marca))


if __name__ == "__main__":
    unittest.main()
