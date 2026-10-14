# -*- coding: utf-8 -*-
"""Com `_pareceres.json` ilegivel, a parte reprovada NAO sai livre.

Achado da verificacao de 14/10/2026 (`consertos/publicacao.md`, "Veto que
falha aberto"): desde 11/10 a leitura de `_pareceres.json` levanta em vez de
virar `{}`, mas os leitores engoliam a excecao e respondiam "sem parecer".
Enquanto o arquivo estivesse corrompido ou trancado, a parte que a IA
REPROVOU saia como se ninguem a tivesse visto.

Agora `parecer.situacao_do_video` responde "reprovado" quando nao le, e a
valvula da publicacao (`postar._retencao`, por `estado_do_video`) segura a
parte como RETIDA: ela so sai se o horario fosse ficar vazio, e marcada "a
conferir" (decisao `historias/reprovado-ou-nao-assistido`). A agenda mantem
a escolha documentada dela (sem ler, conta "a mais").

Nada de producao e tocado: `LEMBRETES` e o diario sao desviados, e o
`postar.py` e carregado pelo caminho, sem `sys.path`.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from contos.pipeline import agenda
from contos.publicar import parecer

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"
VIDEO = "historia_00001:celular:p01"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_pareceres", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.arquivo = Path(tmp.name) / "_pareceres.json"
        self.addCleanup(setattr, parecer, "LEMBRETES", parecer.LEMBRETES)
        parecer.LEMBRETES = self.arquivo
        self.addCleanup(setattr, parecer, "_ILEGIVEL_AVISADO", False)
        parecer._ILEGIVEL_AVISADO = False
        self.diario = []
        import builds.atividade as atividade
        patcher = mock.patch.object(
            atividade, "registrar",
            lambda *a, **k: self.diario.append((a, k)))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(parecer.time, "sleep", lambda _s: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _corromper(self):
        self.arquivo.write_text('{"historia_00001:celular:p01": {"aprov',
                                encoding="utf-8")


class ParecerIlegivelBarra(_Base):
    def test_ilegivel_e_reprovado_e_nao_sem_parecer(self):
        self._corromper()
        self.assertFalse(parecer.pareceres_legiveis())
        self.assertEqual(parecer.SITUACAO_REPROVADO,
                         parecer.situacao_do_video(VIDEO))
        self.assertEqual(parecer.SITUACAO_REPROVADO,
                         parecer.estado_do_video(VIDEO))
        self.assertFalse(parecer.nao_assistido(VIDEO))

    def test_avisa_no_diario_uma_vez(self):
        self._corromper()
        parecer.situacao_do_video(VIDEO)
        parecer.situacao_do_video("historia_00002:celular:p01")
        avisos = [(a, k) for (a, k) in self.diario
                  if k.get("etapa") == "parecer.ilegivel"]
        self.assertEqual(1, len(avisos))
        self.assertEqual("aviso", avisos[0][0][1])

    def test_legivel_continua_como_antes(self):
        self.arquivo.write_text(json.dumps({}), encoding="utf-8")
        self.assertTrue(parecer.pareceres_legiveis())
        self.assertEqual("", parecer.situacao_do_video(VIDEO))
        self.arquivo.unlink()                       # sem arquivo: sem parecer
        self.assertTrue(parecer.pareceres_legiveis())
        self.assertEqual("", parecer.situacao_do_video(VIDEO))
        self.assertEqual([], self.diario)

    def test_a_publicacao_retem_a_parte(self):
        """O caminho real da publicacao: `postar._retencao`."""
        postar = _postar()
        alvo = SimpleNamespace(id=VIDEO, fonte_id="historia_00001", parte=1,
                               caminho=self.arquivo.parent / "nao_existe.mp4")
        with mock.patch.object(postar, "_veto_vencido", lambda _a: False):
            self.arquivo.write_text(json.dumps({}), encoding="utf-8")
            self.assertEqual("", postar._retencao(alvo))       # legivel: livre
            self._corromper()
            # retida (texto nao vazio); a frase do motivo e do postar.py,
            # que desde o conserto da publicacao (14/10) diz que nao leu
            motivo = postar._retencao(alvo)
            self.assertTrue(motivo)
            self.assertIn("pareceres", motivo)

    def test_a_agenda_mantem_conta_a_mais(self):
        """A agenda escolheu o outro lado (cria de menos): continua."""
        self._corromper()
        self.assertFalse(agenda._retida(SimpleNamespace(id=VIDEO)))


if __name__ == "__main__":
    unittest.main()
