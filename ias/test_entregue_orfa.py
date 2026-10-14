# -*- coding: utf-8 -*-
"""IAS-4 (auditoria de 11/10/2026): a mensagem "entregue" por um carteiro
que morreu ficava orfa para sempre.

`reivindicar` so retoma a `entregue` do MESMO pid, e a varredura so olhava
as pendentes: se o processo morria depois do `pendente -> entregue`, nenhum
carteiro novo a retomava e ninguem a marcava falhou. O app mostrava "em
andamento" para sempre, sem aviso.

Com dublê: nenhum navegador, conta ou Telegram (`NF_IAS_PASTA`).
"""
from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from ias import carteiro as carteiro_mod, correio, imagem

MORTO = 999999


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._antes = os.environ.get("NF_IAS_PASTA")
        os.environ["NF_IAS_PASTA"] = str(Path(self._tmp.name) / "ias")
        vivo = correio._pid_vivo
        # so o 999999 esta morto; o resto pergunta ao sistema
        self._pid = mock.patch.object(
            correio, "_pid_vivo", lambda pid: False if int(pid or 0) == MORTO else vivo(pid))
        self._pid.start()

    def tearDown(self):
        self._pid.stop()
        if self._antes is None:
            os.environ.pop("NF_IAS_PASTA", None)
        else:
            os.environ["NF_IAS_PASTA"] = self._antes
        self._tmp.cleanup()


@contextmanager
def _trava_livre(nome, esperar=0.0):
    yield True


def _servico(fabrica=None):
    logs = []
    c = carteiro_mod.Carteiro(
        fabrica_de_sessao=fabrica or carteiro_mod.fabrica_duble(responder=lambda t: "OK"),
        fabrica_imagem=imagem.fabrica_imagem_duble(), trava=_trava_livre,
        nome_da_trava=lambda ia: f"perfil__{ia}__teste", avisar=lambda _t: "entregue",
        avisar_arquivo=lambda *_a: True, log=logs.append, dormir=lambda s: None,
        ajustes={"janela_conversa_s": 0, "espera_conta_max_s": 100}, de_servico=True)
    c._diario = lambda *a: None
    c.logs = logs
    return c


def _entregue_por(caixa, mid, pid, ha_horas=0.0):
    quando = (datetime.now() - timedelta(hours=ha_horas)).isoformat(timespec="seconds")
    correio.atualizar(caixa, mid, situacao="entregue", entregador=pid, entregue_em=quando)


class OrfaVoltaParaAFila(_Base):
    def test_texto_entregue_por_carteiro_morto_volta_pendente(self):
        m = correio.enviar("chatgpt", "pergunta do Adrian")
        _entregue_por("chatgpt", m["id"], MORTO)
        c = _servico()
        self.assertEqual(c._varrer_abandonadas(), 1)
        atual = correio.uma("chatgpt", m["id"])
        self.assertEqual(atual["situacao"], "pendente")
        self.assertIsNone(atual["entregador"])
        self.assertIn("caiu no meio", atual["nota"])
        self.assertEqual(correio.proxima_pendente(so_livres=True)["id"], m["id"])
        # e o servico a entrega de verdade
        c._ultima_varredura = None
        self.assertEqual(c.uma_volta()["situacao"], "respondida")

    def test_imagem_sem_a_conversa_falha_interrompida(self):
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
        _entregue_por("gemini", m["id"], MORTO)
        _servico()._varrer_abandonadas()
        atual = correio.uma("gemini", m["id"])
        self.assertEqual((atual["situacao"], atual["categoria"]), ("falhou", "interrompida"))
        self.assertIn(str(MORTO), atual["erro"])

    def test_imagem_com_a_conversa_volta_e_e_recuperada_sem_novo_pedido(self):
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
        correio.atualizar("gemini", m["id"],
                          chat_imagem_url="https://duble.local/gemini/c/da-imagem")
        _entregue_por("gemini", m["id"], MORTO)
        recuperadas = []

        class _Sessao(carteiro_mod.SessaoDuble):
            def recuperar_imagem(self, prompt, proporcao):
                recuperadas.append(prompt)
                return {"bytes": imagem.png_de_teste(),
                        "prova": {"comprovada": True, "metodo": "duble", "forca": "teste"}}

        sessoes = []

        @contextmanager
        def fabrica(ia):
            sessao = _Sessao(ia)
            sessoes.append(sessao)
            yield sessao
        c = _servico(fabrica)
        c._varrer_abandonadas()
        atual = correio.uma("gemini", m["id"])
        self.assertEqual(atual["situacao"], "pendente")
        self.assertTrue(atual["recuperar"])
        c._ultima_varredura = None
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(recuperadas, ["um gato"])
        self.assertEqual(sessoes[0]._imagem.pedidos, [])    # nenhuma imagem nova pedida

    def test_orfa_velha_so_falha(self):
        m = correio.enviar("chatgpt", "pergunta de dias atrás")
        _entregue_por("chatgpt", m["id"], MORTO, ha_horas=30)
        _servico()._varrer_abandonadas()
        atual = correio.uma("chatgpt", m["id"])
        self.assertEqual((atual["situacao"], atual["categoria"]), ("falhou", "interrompida"))

    def test_entregue_por_processo_vivo_fica(self):
        m = correio.enviar("chatgpt", "pergunta")
        _entregue_por("chatgpt", m["id"], os.getppid())
        self.assertEqual(_servico()._varrer_abandonadas(), 0)
        self.assertEqual(correio.uma("chatgpt", m["id"])["situacao"], "entregue")

    def test_entregue_por_mim_fica(self):
        m = correio.enviar("chatgpt", "pergunta")
        _entregue_por("chatgpt", m["id"], os.getpid())
        self.assertEqual(_servico()._varrer_abandonadas(), 0)
        self.assertEqual(correio.uma("chatgpt", m["id"])["situacao"], "entregue")


if __name__ == "__main__":
    unittest.main()
