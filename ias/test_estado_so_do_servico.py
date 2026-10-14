# -*- coding: utf-8 -*-
"""IAS-6 (auditoria de 11/10/2026): `carteiro.json` e o diario eram escritos
por QUALQUER `Carteiro`, inclusive o dos workers, e "entregando" saia antes
de ter a conta.

O worker das historias e o do identity sobrescreviam `carteiro.json` com o
PID e o estado deles: o app mostrava o estado do worker, o supervisor
recusava reiniciar o carteiro (e podia marcar "interrompida" o pedido do
worker), e quando o worker terminava o PID morto virava "parado". No
diario, as linhas do worker saiam com `canal=adrian`.

Com dublê: nenhum navegador, conta ou Telegram (`NF_IAS_PASTA`).
"""
from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from ias import carteiro as carteiro_mod, correio, imagem


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._antes = os.environ.get("NF_IAS_PASTA")
        os.environ["NF_IAS_PASTA"] = str(Path(self._tmp.name) / "ias")

    def tearDown(self):
        if self._antes is None:
            os.environ.pop("NF_IAS_PASTA", None)
        else:
            os.environ["NF_IAS_PASTA"] = self._antes
        self._tmp.cleanup()


@contextmanager
def _trava_livre(nome, esperar=0.0):
    yield True


def _carteiro(**kw):
    kw.setdefault("trava", _trava_livre)
    return carteiro_mod.Carteiro(
        fabrica_de_sessao=carteiro_mod.fabrica_duble(responder=lambda t: "OK"),
        fabrica_imagem=imagem.fabrica_imagem_duble(),
        nome_da_trava=lambda ia: f"perfil__{ia}__teste", avisar=lambda _t: False,
        avisar_arquivo=lambda *_a: False, log=lambda m: None, dormir=lambda s: None,
        ajustes={"janela_conversa_s": 0, "espera_conta_max_s": 100}, **kw)


class WorkerNaoEscreveOEstado(_Base):
    def test_carteiro_json_do_servico_fica_intacto(self):
        correio.gravar_estado_do_carteiro({"situacao": "ocioso", "nota": "o do serviço"})
        arquivo = correio.raiz() / "carteiro.json"
        antes = arquivo.read_bytes()
        gravados = []
        c = _carteiro()                                 # como os workers o criam
        c._diario = lambda *a: None
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1", dono=os.getpid())
        with mock.patch.object(correio, "gravar_estado_do_carteiro", gravados.append):
            fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(gravados, [])
        self.assertEqual(arquivo.read_bytes(), antes)
        self.assertEqual(correio.estado_do_carteiro()["nota"], "o do serviço")

    def test_diario_do_worker_sai_no_canal_pipeline(self):
        linhas = []

        def registrar(fabrica, status, detalhe="", canal="builds", **kw):
            linhas.append(canal)
        with mock.patch("builds.atividade.registrar", registrar):
            _carteiro()._diario("gemini", "ok", "x", "abc")
            _carteiro(de_servico=True)._diario("gemini", "ok", "x", "abc")
        self.assertEqual(linhas, ["pipeline", "adrian"])


class EntregandoSoComAConta(_Base):
    def test_primeiro_estado_e_esperando_trava(self):
        estados = []
        voltas = []

        @contextmanager
        def trava(nome, esperar=0.0):
            voltas.append(nome)
            yield len(voltas) > 2                       # ocupada nas 2 primeiras
        c = _carteiro(trava=trava, de_servico=True)
        c._diario = lambda *a: None
        m = correio.enviar("gemini", "pergunta")
        with mock.patch.object(correio, "gravar_estado_do_carteiro",
                               lambda dados: estados.append(dados["situacao"])):
            fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(estados[0], "esperando_trava")
        primeira_entrega = estados.index("entregando")
        self.assertTrue(all(e == "esperando_trava" for e in estados[:primeira_entrega]),
                        estados)


if __name__ == "__main__":
    unittest.main()
