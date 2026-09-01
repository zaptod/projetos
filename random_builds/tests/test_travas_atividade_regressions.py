# -*- coding: utf-8 -*-
"""Contratos do paralelismo (travas por perfil) e do diario da Vila.

O que este arquivo trava:

1. TRAVAS POR RECURSO. Recursos com nomes diferentes rodam em paralelo
   (Digen + PicassoIA + ChatGPT ao mesmo tempo); o MESMO recurso continua
   exclusivo — e o nome vem do registro de contas, entao duas contas do
   mesmo servico tambem rodam juntas. Era a trava global unica que
   serializava a pipeline inteira.
2. DIARIO. `registrar` nunca levanta; `estado_das_fabricas` deriva
   trabalhando/erro/ocioso do ULTIMO evento; um `inicio` de horas atras e
   processo morto, nao trabalho (o bot nao pode morar na fabrica).

Rode de dentro de random_builds/:
    python -m unittest tests.test_travas_atividade_regressions -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src import atividade, travas                              # noqa: E402


class TravasTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._pasta = travas._pasta
        travas._pasta = lambda: Path(self._tmp.name)
        self.addCleanup(lambda: setattr(travas, "_pasta", self._pasta))

    def test_recursos_diferentes_rodam_juntos(self):
        with travas.trava("digen__principal") as a:
            self.assertTrue(a)
            with travas.trava("picasso__principal") as b:
                self.assertTrue(b, "perfis diferentes nao podem se bloquear")
                with travas.trava("chatgpt__principal") as c:
                    self.assertTrue(c)

    def test_o_mesmo_recurso_e_exclusivo(self):
        with travas.trava("picasso__principal") as a:
            self.assertTrue(a)
            with travas.trava("picasso__principal") as b:
                self.assertFalse(b, "o mesmo perfil aberto duas vezes = Chrome quebrado")
        # liberou: da para pegar de novo
        with travas.trava("picasso__principal") as c:
            self.assertTrue(c)

    def test_contas_diferentes_do_mesmo_servico_rodam_juntas(self):
        with travas.trava("tiktok__principal") as a, \
                travas.trava("tiktok__historias") as b:
            self.assertTrue(a)
            self.assertTrue(b)

    def test_ocupada_testa_sem_segurar(self):
        self.assertFalse(travas.ocupada("digen__principal"))
        with travas.trava("digen__principal"):
            self.assertTrue(travas.ocupada("digen__principal"))
        self.assertFalse(travas.ocupada("digen__principal"))

    def test_nome_da_trava_vem_do_registro_de_contas(self):
        nome = travas.do_perfil("picasso", "builds")
        self.assertTrue(nome.startswith("picasso__"))
        self.assertNotIn("/", nome)


class AtividadeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._arquivo = atividade._arquivo
        atividade._arquivo = lambda: Path(self._tmp.name) / "atividade.jsonl"
        self.addCleanup(lambda: setattr(atividade, "_arquivo", self._arquivo))

    def test_registrar_e_ler(self):
        atividade.registrar("picasso", "inicio", "3 cenas", "historias")
        atividade.registrar("picasso", "ok", "3 cenas", "historias")
        eventos = atividade.recentes(5)
        self.assertEqual(["ok", "inicio"], [e["status"] for e in eventos])
        self.assertEqual("historias", eventos[0]["canal"])

    def test_estado_deriva_do_ultimo_evento(self):
        atividade.registrar("digen", "inicio", "payoff")
        atividade.registrar("picasso", "inicio", "imagens")
        atividade.registrar("picasso", "ok", "imagens")
        atividade.registrar("estudio", "erro", "ffmpeg sumiu")
        estado = atividade.estado_das_fabricas()
        self.assertEqual("trabalhando", estado["digen"]["status"])
        self.assertEqual("ocioso", estado["picasso"]["status"])
        self.assertEqual("erro", estado["estudio"]["status"])
        self.assertEqual("ocioso", estado["arena"]["status"])

    def test_log_nao_muda_o_estado(self):
        atividade.registrar("picasso", "inicio", "5 cenas")
        atividade.registrar("picasso", "log", "cena 2 pronta")
        self.assertEqual("trabalhando",
                         atividade.estado_das_fabricas()["picasso"]["status"])

    def test_inicio_velho_e_processo_morto(self):
        """Worker derrubado no meio nao deixa o bot morando na fabrica."""
        velho = (datetime.now(timezone.utc)
                 - timedelta(seconds=atividade.INICIO_VELHO_S + 60))
        caminho = atividade._arquivo()
        caminho.write_text(
            '{"ts": "%s", "fabrica": "digen", "canal": "builds", '
            '"status": "inicio", "detalhe": "x"}\n'
            % velho.isoformat(timespec="seconds"), encoding="utf-8")
        self.assertEqual("ocioso",
                         atividade.estado_das_fabricas()["digen"]["status"])

    def test_contexto_anota_ok_e_erro(self):
        with atividade.fabrica("arena", "estreia"):
            pass
        self.assertEqual("ok", atividade.recentes(1)[0]["status"])
        with self.assertRaises(ValueError):
            with atividade.fabrica("arena", "estreia"):
                raise ValueError("faltou lutador")
        ultimo = atividade.recentes(1)[0]
        self.assertEqual("erro", ultimo["status"])
        self.assertIn("faltou lutador", ultimo["detalhe"])

    def test_registrar_nunca_levanta(self):
        atividade._arquivo = lambda: Path(self._tmp.name) / "nao" / "\0invalido"
        atividade.registrar("picasso", "inicio", "nada")  # nao pode explodir

    def test_toda_fabrica_do_mapa_tem_rotulo_e_emoji(self):
        for nome, dados in atividade.FABRICAS.items():
            self.assertTrue(dados.get("rotulo"), nome)
            self.assertTrue(dados.get("emoji"), nome)


if __name__ == "__main__":
    unittest.main()
