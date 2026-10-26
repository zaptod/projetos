# -*- coding: utf-8 -*-
"""O servico do dia nao pode depender de a rodada pesada largar a trava.

13/10/2026, medido no disco: `outputs/_servico_do_dia.json` parou em
`2026-10-12`, o arquivo mais novo de `random_builds/outputs/_metricas` era de
12/10 07:45 e o diario nao tinha uma linha de `metricas` nem de
`conferencia` no dia. O log `auto_20261013.txt` mostra o porque: de 08:02 a
19:02, todo disparo disse "servico do dia pendente" e logo depois "ja tem uma
rodada em andamento. Saindo". A rodada das 07:02 de 12/10 (pid 4332) fez o
servico, emendou, comecou a historia_00074 as 11:41 e ficou presa no Gemini
(ultima linha 13:09 de 12/10) segurando `historias__auto` ate o PC cair, entre
19:03 e 22:18 de 13/10. O disparo das 07:02 de 13/10 nem abriu (0x800710E0).

O servico (metrica, tempos, conferencia) so rodava DENTRO da rodada que pega
a trava. Agora o disparo que acha a rodada ocupada faz o servico pendente,
sob trava propria, longe da postagem; e todo disparo que sai sem trabalhar
pergunta se a metrica do dia existe.

Relogio congelado, trava de mentira, metrica/tempos/conferencia dublados: nada
abre navegador, chama API ou grava no `_metricas` de verdade.
"""
from __future__ import annotations

import contextlib
import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from contos.pipeline import agenda

TERCA_08H02 = datetime(2026, 10, 13, 8, 2)     # o 1o disparo que rodou


class _Dia13(unittest.TestCase):

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pasta = Path(tmp.name)
        self._trocar(agenda, "OUTPUTS", self.pasta)
        self.agora = TERCA_08H02
        self._trocar(agenda, "_relogio", lambda: self.agora)
        self._trocar(agenda, "_dormir", lambda _s: None)
        # O estoque do log de 13/10: 15 publicaveis para um alvo de 80.
        self._trocar(agenda, "estoque_publicavel", lambda: 15)
        self._trocar(agenda, "aprovados_no_estoque", lambda: [])
        self._trocar(agenda, "barrados_no_estoque", lambda: [])
        self._trocar(agenda, "incompletas", lambda: [{"historia_id": "h74"}])
        self._trocar(agenda, "partes_publicadas", lambda publicados=None: {})
        self._trocar(agenda, "_livre_gb", lambda _c: 100.0)
        self._trocar(agenda, "avisar", lambda *a, **k: True)
        self.trabalhou = []
        self._trocar(agenda, "_trabalhar",
                     lambda *a, **k: self.trabalhou.append(1) or {})

        # A TRAVA DE 13/10: `historias__auto` presa pela rodada de 12/10.
        self.ocupadas = {agenda.TRAVA}
        from builds import travas

        @contextlib.contextmanager
        def _trava(nome, esperar=0.0):
            yield nome not in self.ocupadas

        self._trocar(travas, "trava", _trava)
        from builds.identity import controle
        self._trocar(controle, "pausado_para", lambda *a, **k: False)

        # O servico, dublado um nivel abaixo.
        from builds import tempos
        from builds.publicar import conferencia, metricas
        self.coletas, self.conferencias = [], []
        self._trocar(metricas, "atualizar_uma_vez_por_dia",
                     lambda log=None, chave=None: self.coletas.append(chave)
                     or True)
        self._trocar(tempos, "consolidar", lambda: self.pasta / "t.json")
        self._trocar(conferencia, "conferir_tudo",
                     lambda log=None, origem=None:
                     self.conferencias.append(origem))
        from builds.publicar import analise
        self.analises = []
        self._trocar(analise, "do_dia",
                     lambda log=None, **k: self.analises.append(1) or {})
        self.avisos = []
        self._trocar(metricas, "avisar_coleta_atrasada",
                     lambda agora=None, **k: self.avisos.append(
                         (agora, k.get("contexto"))))
        self.config = {**agenda.carregar(), "avisar_telegram": False,
                       "paralelo_por_gerador": {"ligado": False}}

    def _trocar(self, alvo, nome, valor):
        self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
        setattr(alvo, nome, valor)

    def rodar(self):
        return agenda.rodar(config=dict(self.config), tela=None)


class ServicoComARodadaPresaTests(_Dia13):

    def test_o_13_10_coleta_mesmo_com_a_rodada_presa(self):
        resultado = self.rodar()
        self.assertEqual("ja rodando", resultado["motivo"])
        self.assertEqual([], self.trabalhou, "nao pode trabalhar sem a trava")
        self.assertEqual(["dia-2026-10-13"], self.coletas)
        self.assertEqual(["servico"], self.conferencias)
        self.assertTrue(resultado["servico_do_dia"])
        self.assertFalse(agenda.servico_pendente(self.agora))

    def test_o_disparo_seguinte_nao_coleta_de_novo(self):
        self.rodar()
        self.agora = datetime(2026, 10, 13, 10, 2)
        self.rodar()
        self.assertEqual(["dia-2026-10-13"], self.coletas)

    def test_perto_da_postagem_espera_o_proximo_disparo(self):
        # 09:02: o post das 09:37 esta a 35 min, e o servico leva ~43.
        self.agora = datetime(2026, 10, 13, 9, 2)
        resultado = self.rodar()
        self.assertFalse(resultado["servico_do_dia"])
        self.assertEqual([], self.coletas)
        self.assertTrue(agenda.servico_pendente(self.agora))

    def test_servico_ja_rodando_em_outro_processo_nao_duplica(self):
        self.ocupadas.add(agenda.TRAVA_DO_SERVICO)
        resultado = self.rodar()
        self.assertFalse(resultado["servico_do_dia"])
        self.assertEqual([], self.coletas)

    def test_servico_ja_feito_hoje_nao_roda(self):
        agenda._marcar_servico(self.agora)
        self.rodar()
        self.assertEqual([], self.coletas)

    def test_madrugada_nao_faz_servico(self):
        # 03:20: a madrugada da transicao nunca pediu o servico.
        self.agora = datetime(2026, 10, 13, 3, 20)
        self.rodar()
        self.assertEqual([], self.coletas)

    def test_a_rodada_que_pega_a_trava_usa_a_trava_do_servico(self):
        self.ocupadas = {agenda.TRAVA_DO_SERVICO}
        self.assertFalse(agenda._servico_do_dia({}, False, lambda *_a: None))
        self.assertEqual([], self.coletas)
        self.ocupadas = set()
        self.assertTrue(agenda._servico_do_dia({}, False, lambda *_a: None))
        self.assertEqual(["dia-2026-10-13"], self.coletas)

    def test_supervisor_das_faixas_tambem_coleta(self):
        config = {**self.config, "paralelo_por_gerador": {"ligado": True}}
        self._trocar(agenda, "faixas", lambda _c=None: ["gemini", "chatgpt"])
        resultado = agenda.rodar_faixas(config=config, tela=None,
                                        lancar=lambda *a: None)
        self.assertEqual("ja rodando", resultado["motivo"])
        self.assertEqual(["dia-2026-10-13"], self.coletas)


class VigiaDeTodoDisparoTests(_Dia13):

    def test_disparo_com_a_trava_presa_pergunta_e_diz_a_causa(self):
        self.agora = datetime(2026, 10, 13, 9, 2)
        self.rodar()
        (quando, contexto), = self.avisos
        self.assertEqual(self.agora, quando)
        self.assertIn("historias__auto", contexto)

    def test_disparo_fora_da_janela_tambem_pergunta(self):
        # 23:02 de 13/10, "fora da janela": e o disparo que acusaria o dia.
        self.agora = datetime(2026, 10, 13, 23, 2)
        self._trocar(agenda, "aprovados_no_estoque", lambda: [object()] * 72)
        self._trocar(agenda, "estoque_zero", lambda *_a, **_k: False)
        resultado = self.rodar()
        self.assertEqual("fora da janela", resultado["motivo"])
        self.assertEqual(1, len(self.avisos))

    def test_pausa_tambem_pergunta(self):
        from builds.identity import controle
        self._trocar(controle, "pausado_para", lambda *a, **k: True)
        self.rodar()
        (_quando, contexto), = self.avisos
        self.assertIn("PAUSADA", contexto)

    def test_vigia_que_quebra_nao_derruba_o_disparo(self):
        from builds.publicar import metricas

        def _quebra(*_a, **_k):
            raise RuntimeError("marca")

        self._trocar(metricas, "avisar_coleta_atrasada", _quebra)
        resultado = self.rodar()
        self.assertEqual("ja rodando", resultado["motivo"])


class AvisoDeVerdadeNoDiarioTests(_Dia13):
    """O caminho inteiro, com a marca de 12/10 e o diario numa lista: o dia
    13 sem coleta vira UMA linha de erro, nao quinze."""

    def setUp(self):
        super().setUp()
        from builds import atividade
        from builds.publicar import metricas, sinais
        # O vigia DE VERDADE (o `_Dia13` o dubla).
        self._trocar(metricas, "avisar_coleta_atrasada",
                     type(self)._vigia_real)
        self._trocar(sinais, "_config_da_agenda",
                     lambda: "E:/nao/existe/agenda.json")
        marca = self.pasta / "_atualizado_em.json"
        marca.write_text(json.dumps({"dia": "dia-2026-10-12", "partes": {
            nome: {"estado": "ok", "videos": 5, "chave": "dia-2026-10-12",
                   "quando": "2026-10-12T07:45:21",
                   "ultimo_ok": "2026-10-12T07:45:21",
                   "videos_no_ultimo_ok": 5}
            for nome in ("builds", "builds_tiktok", "historias",
                         "historias_tiktok", "bluelock",
                         "bluelock_tiktok")}}), encoding="utf-8")
        self._trocar(metricas, "MARCA_DO_DIA", marca)
        self.diario = []
        self._trocar(atividade, "registrar",
                     lambda fabrica, status, detalhe="", canal="builds", **k:
                     self.diario.append({"fabrica": fabrica,
                                         "status": status,
                                         "detalhe": detalhe}))
        self._trocar(sinais, "ler_diario", lambda caminho=None:
                     list(self.diario))
        # O servico em si tambem preso: so o vigia pode falar.
        self.ocupadas.add(agenda.TRAVA_DO_SERVICO)

    from builds.publicar.metricas import avisar_coleta_atrasada as _vigia_real

    def test_quinze_disparos_um_alarme(self):
        for hora, minuto in ((8, 2), (9, 2), (10, 2), (11, 2), (12, 32),
                             (13, 2), (14, 2), (15, 2), (16, 2), (17, 2),
                             (18, 22), (19, 2), (22, 24), (23, 2)):
            self.agora = datetime(2026, 10, 13, hora, minuto)
            self.rodar()
        erros = [d for d in self.diario if d["fabrica"] == "metricas"]
        self.assertEqual(1, len(erros), erros)
        self.assertIn("[coleta parada 2026-10-13]", erros[0]["detalhe"])
        self.assertIn("historias__auto", erros[0]["detalhe"])


if __name__ == "__main__":
    unittest.main()
