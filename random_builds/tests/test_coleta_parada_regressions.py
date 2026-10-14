# -*- coding: utf-8 -*-
"""A coleta que NEM RODA tem de virar alarme; a que mede ZERO nao e "ok".

13/10/2026: o arquivo mais novo de `random_builds/outputs/_metricas` era de
12/10 07:45 e o diario nao tinha UMA linha da fabrica `metricas` nem da
`conferencia` no dia 13. A coleta mora no servico do dia das historias, e uma
rodada presa desde 12/10 11:41 segurou a trava `historias__auto` ate o PC
cair: quinze disparos sairam com "ja tem uma rodada em andamento". A coleta
que FALHA ja escrevia erro; a que nao roda nao escrevia nada.

E o caso zero: uma parte que voltava `vazio` (0 videos sem excecao) contava
como feita E renovava `ultimo_ok` — o painel diria "metrica de hoje" sem um
numero novo. Ledger que some (caminho errado, arquivo ilegivel) e assim.

Nada aqui toca rede, navegador, a marca de verdade ou o diario de verdade.
"""
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from builds import atividade
from builds.publicar import metricas, sinais
from builds.publicar import tiktok_metricas as T

# A marca como estava no disco em 14/10/2026 (resumida): a ultima noite boa.
MARCA_DE_12_10 = {
    "dia": "dia-2026-10-12", "completa": True,
    "quando": "2026-10-12T07:45:21",
    "partes": {
        "builds": {"estado": "ok", "videos": 252,
                   "quando": "2026-10-12T07:17:18", "chave": "dia-2026-10-12",
                   "ultimo_ok": "2026-10-12T07:17:18",
                   "videos_no_ultimo_ok": 252},
        "builds_tiktok": {"estado": "ok", "videos": 242,
                          "quando": "2026-10-12T07:24:46",
                          "chave": "dia-2026-10-12",
                          "ultimo_ok": "2026-10-12T07:24:46",
                          "videos_no_ultimo_ok": 242},
        "historias": {"estado": "ok", "videos": 272,
                      "quando": "2026-10-12T07:37:05",
                      "chave": "dia-2026-10-12",
                      "ultimo_ok": "2026-10-12T07:37:05",
                      "videos_no_ultimo_ok": 272},
        "historias_tiktok": {"estado": "ok", "videos": 276,
                             "quando": "2026-10-12T07:45:21",
                             "chave": "dia-2026-10-12",
                             "ultimo_ok": "2026-10-12T07:45:21",
                             "videos_no_ultimo_ok": 276},
    },
}
QUATRO = ["builds", "builds_tiktok", "historias", "historias_tiktok"]


def _copia(marca):
    return json.loads(json.dumps(marca))


class _Hermetico(unittest.TestCase):
    """O horario do servico e o padrao (07:02 + 3 h = 10:02), nao o do
    `agenda.json` de quem estiver rodando; o diario e uma lista."""

    def setUp(self):
        reais = (sinais._config_da_agenda, atividade.registrar)
        self.addCleanup(self._restaurar, reais)
        sinais._config_da_agenda = lambda: "E:/nao/existe/agenda.json"
        self.diario = []

        def registrar(fabrica, status, detalhe="", canal="builds", **_k):
            self.diario.append({"fabrica": fabrica, "status": status,
                                "detalhe": detalhe, "canal": canal})

        atividade.registrar = registrar

    @staticmethod
    def _restaurar(reais):
        sinais._config_da_agenda, atividade.registrar = reais


class ColetaAtrasadaTests(_Hermetico):

    def test_o_13_10_de_verdade_acende_depois_das_10h02(self):
        atraso = metricas.coleta_atrasada(MARCA_DE_12_10,
                                          datetime(2026, 10, 13, 10, 3))
        self.assertIsNotNone(atraso)
        self.assertEqual(date(2026, 10, 13), atraso["esperada"])
        self.assertEqual(QUATRO, atraso["partes"])
        self.assertEqual("2026-10-12T07:45:21", atraso["ultimo_ok"])

    def test_antes_das_10h02_a_de_ontem_basta(self):
        # 08:02 de 13/10: a coleta de 13/10 ainda tem ate 10:02.
        self.assertIsNone(metricas.coleta_atrasada(
            MARCA_DE_12_10, datetime(2026, 10, 13, 8, 2)))

    def test_a_noite_seguinte_ainda_cobra_o_dia_que_faltou(self):
        # 00:02 de 14/10 (o PC voltou as 22:43 de 13/10): esperada e 13/10.
        atraso = metricas.coleta_atrasada(MARCA_DE_12_10,
                                          datetime(2026, 10, 14, 0, 2))
        self.assertEqual(date(2026, 10, 13), atraso["esperada"])

    def test_caso_zero_marca_vazia_e_atraso_e_nao_em_dia(self):
        atraso = metricas.coleta_atrasada({}, datetime(2026, 10, 13, 10, 3))
        self.assertEqual(QUATRO, atraso["partes"])
        self.assertIsNone(atraso["ultimo_ok"])

    def test_marca_ilegivel_acende(self):
        atraso = metricas.coleta_atrasada(None, datetime(2026, 10, 13, 10, 3))
        self.assertTrue(atraso["ilegivel"])

    def test_parte_que_tentou_e_falhou_hoje_nao_e_atraso(self):
        # Ela ja avisou pelo caminho do erro; aqui so a que SUMIU.
        marca = _copia(MARCA_DE_12_10)
        for nome in QUATRO:
            marca["partes"][nome]["quando"] = "2026-10-13T07:20:00"
        marca["partes"]["builds"]["estado"] = "erro"
        self.assertIsNone(metricas.coleta_atrasada(
            marca, datetime(2026, 10, 13, 10, 3)))

    def test_so_a_parte_que_sumiu_aparece(self):
        marca = _copia(MARCA_DE_12_10)
        for nome in ("builds", "historias", "historias_tiktok"):
            marca["partes"][nome]["quando"] = "2026-10-13T07:20:00"
            marca["partes"][nome]["ultimo_ok"] = "2026-10-13T07:20:00"
        atraso = metricas.coleta_atrasada(marca,
                                          datetime(2026, 10, 13, 10, 3))
        self.assertEqual(["builds_tiktok"], atraso["partes"])


class AvisoUmaVezPorDiaTests(_Hermetico):

    def _avisar(self, agora, eventos=..., marca=MARCA_DE_12_10, **k):
        return metricas.avisar_coleta_atrasada(
            agora, marca=marca, log=lambda *_a: None,
            eventos=self.diario if eventos is ... else eventos, **k)

    def test_vira_uma_linha_de_erro_da_fabrica_metricas(self):
        texto = self._avisar(datetime(2026, 10, 13, 10, 3),
                             contexto="a rodada pesada segura a trava")
        self.assertIsNotNone(texto)
        linha, = self.diario
        self.assertEqual("metricas", linha["fabrica"])
        self.assertEqual(atividade.ERRO, linha["status"])
        self.assertIn("[coleta parada 2026-10-13]", linha["detalhe"])
        self.assertIn("NAO RODOU", linha["detalhe"])
        self.assertIn("12/10 07:45", linha["detalhe"])
        self.assertIn("segura a trava", linha["detalhe"])

    def test_quinze_disparos_no_mesmo_dia_sao_um_aviso(self):
        for hora in range(10, 24):
            self._avisar(datetime(2026, 10, 13, hora, 3))
        self._avisar(datetime(2026, 10, 14, 0, 2))
        self.assertEqual(1, len(self.diario))

    def test_dia_novo_sem_coleta_avisa_de_novo(self):
        self._avisar(datetime(2026, 10, 13, 10, 3))
        self._avisar(datetime(2026, 10, 14, 10, 3))
        self.assertEqual(2, len(self.diario))
        self.assertIn("2026-10-14", self.diario[1]["detalhe"])

    def test_em_dia_nao_escreve_nada(self):
        self.assertIsNone(self._avisar(datetime(2026, 10, 12, 10, 3)))
        self.assertEqual([], self.diario)

    def test_diario_ilegivel_avisa_em_vez_de_calar(self):
        self._avisar(datetime(2026, 10, 13, 10, 3), eventos=None)
        self._avisar(datetime(2026, 10, 13, 11, 3), eventos=None)
        self.assertEqual(2, len(self.diario))

    def test_vigia_quebrado_vira_erro_e_nao_silencio(self):
        original = metricas.coleta_atrasada

        def _quebra(*_a, **_k):
            raise KeyError("partes")

        metricas.coleta_atrasada = _quebra
        self.addCleanup(setattr, metricas, "coleta_atrasada", original)
        self.assertIsNone(self._avisar(datetime(2026, 10, 13, 10, 3)))
        linha, = self.diario
        self.assertEqual(atividade.ERRO, linha["status"])
        self.assertIn("nao consegui conferir", linha["detalhe"])


class VazioNaoEColetaBoaTests(_Hermetico):
    """Caso ZERO dentro da coleta: 0 videos sem excecao."""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        reais = (metricas.MARCA_DO_DIA, metricas.reconciliar,
                 metricas.atualizar, T.coletar)
        self.addCleanup(self._volta, reais)
        metricas.MARCA_DO_DIA = Path(tmp.name) / "_atualizado_em.json"
        metricas.reconciliar = lambda canal, log=print: 0
        self.vazio = set()

        def atualizar(log=print, canal="builds"):
            if canal in self.vazio:
                return []
            return [{"youtube_id": f"{canal}-1"}, {"youtube_id": f"{canal}-2"}]

        def coletar(canal, log=print, resumo=None, **_k):
            if f"{canal}_tiktok" in self.vazio:
                return []
            return [{"tiktok_id": "t1"}]

        metricas.atualizar = atualizar
        T.coletar = coletar

    @staticmethod
    def _volta(reais):
        (metricas.MARCA_DO_DIA, metricas.reconciliar, metricas.atualizar,
         T.coletar) = reais

    def _rodar(self, chave):
        return metricas.atualizar_uma_vez_por_dia(log=lambda *_a: None,
                                                  chave=chave)

    def _parte(self, nome):
        return metricas.partes_da_marca(metricas.ler_marca())[nome]

    def test_zero_depois_de_ter_medido_e_erro_e_nao_fecha_o_dia(self):
        self.assertTrue(self._rodar("dia-2026-10-12"))
        boa = self._parte("builds")["ultimo_ok"]
        self.vazio.add("builds")
        self.assertFalse(self._rodar("dia-2026-10-13"))
        parte = self._parte("builds")
        self.assertEqual("erro", parte["estado"])
        self.assertIn("ColetaVazia", parte["erro"])
        self.assertIn("mediu 2", parte["erro"])
        self.assertEqual(boa, parte["ultimo_ok"])
        self.assertFalse(metricas.ler_marca()["completa"])
        linha, = [d for d in self.diario if d["fabrica"] == "metricas"]
        self.assertIn("de builds falhou", linha["detalhe"])

    def test_vazio_de_sempre_nao_vira_coleta_boa(self):
        # Nunca mediu nada: continua `vazio` (nao e falha), mas sem
        # `ultimo_ok` — ausencia nao e frescor.
        self.vazio.add("historias_tiktok")
        self._rodar("dia-2026-10-13")
        parte = self._parte("historias_tiktok")
        self.assertEqual("vazio", parte["estado"])
        self.assertNotIn("ultimo_ok", parte)
        self.assertEqual([], self.diario)


if __name__ == "__main__":
    unittest.main()
