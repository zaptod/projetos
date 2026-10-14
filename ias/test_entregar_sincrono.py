# -*- coding: utf-8 -*-
"""IAS-2 (auditoria de 11/10/2026): o `entregar()` sincrono dos workers
devolvia o pedido ainda PENDENTE e reservado quando a rede caia.

"Volta para a fila" so faz sentido no laco do carteiro de servico. O worker
(historias, identity) recebia `pendente`, tratava como falha e pedia outro;
o pedido velho ficava reservado e, passadas 4 h, o carteiro de servico o
entregava: gastava a conta e mandava ao Telegram uma imagem que ninguem lia
(629 assim em 09/10).

Com dublê: nenhum navegador, conta ou Telegram (`NF_IAS_PASTA`).
"""
from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from ias import carteiro as carteiro_mod, correio, imagem

ERRO_DE_REDE = "Page.goto: net::ERR_NAME_NOT_RESOLVED at https://gemini.google.com/app"


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


def _do_worker(fabrica, **kw):
    """O Carteiro como os workers o criam: sem `de_servico`, janela 0."""
    esperas = []
    c = carteiro_mod.Carteiro(
        fabrica_de_sessao=fabrica, fabrica_imagem=imagem.fabrica_imagem_duble(),
        trava=_trava_livre, nome_da_trava=lambda ia: f"perfil__{ia}__teste",
        avisar=lambda _t: False, avisar_arquivo=lambda _c, _l: False,
        log=lambda m: None, dormir=esperas.append,
        ajustes={"janela_conversa_s": 0, "espera_conta_max_s": 100}, **kw)
    c._diario = lambda *a: None
    c.esperas = esperas
    return c


class RedeCaidaNoWorker(_Base):
    def test_entregar_devolve_falhou_rede_e_nao_pendente(self):
        c = _do_worker(carteiro_mod.fabrica_duble(imagem_falhar=RuntimeError(ERRO_DE_REDE)))
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1", dono=os.getpid())
        fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "rede")
        self.assertIn("rede caiu", fim["erro"])
        self.assertEqual(c.esperas, [])                 # nao dorme esperando a rede
        self.assertEqual(correio.uma("gemini", m["id"])["situacao"], "falhou")
        # nada sobra para o carteiro de servico entregar depois
        self.assertIsNone(correio.proxima_pendente(correio.CAIXAS, so_livres=True))

    def test_rede_caida_no_texto_tambem_falha_com_rede(self):
        c = _do_worker(carteiro_mod.fabrica_duble(falhar=RuntimeError(ERRO_DE_REDE)))
        m = correio.enviar("gemini", "pergunta")
        fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual((fim["situacao"], fim["categoria"]), ("falhou", "rede"))

    def test_no_servico_a_rede_caida_ainda_volta_para_a_fila(self):
        c = _do_worker(carteiro_mod.fabrica_duble(imagem_falhar=RuntimeError(ERRO_DE_REDE)),
                       de_servico=True)
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
        c.entregar(correio.uma("gemini", m["id"]))
        atual = correio.uma("gemini", m["id"])
        self.assertEqual(atual["situacao"], "pendente")
        self.assertEqual(atual["rede_tentativas"], 1)
        self.assertEqual(c.esperas, [60])

    def test_classificar_erro_diz_rede(self):
        categoria, motivo = carteiro_mod.classificar_erro("gemini", RuntimeError(ERRO_DE_REDE))
        self.assertEqual(categoria, "rede")
        self.assertEqual(motivo, carteiro_mod.MOTIVO_REDE)


class NadaSobraPendente(_Base):
    def test_o_que_sobra_pendente_vira_interrompida(self):
        """A rede de seguranca: se a entrega devolveu sem resolver, o pedido
        do worker falha `interrompida` em vez de ficar pendente."""
        c = _do_worker(carteiro_mod.fabrica_duble())
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1", dono=os.getpid())
        c._entregar = lambda mensagem: correio.uma("gemini", m["id"])   # devolve sem entregar
        fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual((fim["situacao"], fim["categoria"]), ("falhou", "interrompida"))

    def test_o_que_sobra_entregue_por_mim_vira_interrompida(self):
        c = _do_worker(carteiro_mod.fabrica_duble())
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1", dono=os.getpid())

        def _so_reivindica(mensagem):
            return correio.reivindicar("gemini", m["id"])
        c._entregar = _so_reivindica
        fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual((fim["situacao"], fim["categoria"]), ("falhou", "interrompida"))

    def test_respondida_fica_respondida(self):
        c = _do_worker(carteiro_mod.fabrica_duble())
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1", dono=os.getpid())
        fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual(fim["situacao"], "respondida")


class ReservaVencidaNaoViraLivre(_Base):
    def test_reserva_de_mais_de_4h_falha_na_varredura(self):
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1", dono=os.getppid())
        velho = (datetime.now() - timedelta(hours=5)).isoformat(timespec="seconds")
        correio.atualizar("gemini", m["id"], reservado_em=velho)
        c = _do_worker(carteiro_mod.fabrica_duble(), de_servico=True)
        self.assertEqual(c._varrer_abandonadas(), 1)
        atual = correio.uma("gemini", m["id"])
        self.assertEqual((atual["situacao"], atual["categoria"]), ("falhou", "abandonado"))
        self.assertIn("passou de 4 h", atual["erro"])
        self.assertIsNone(correio.proxima_pendente(correio.CAIXAS, so_livres=True))

    def test_reserva_recente_de_processo_vivo_fica(self):
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1", dono=os.getppid())
        c = _do_worker(carteiro_mod.fabrica_duble(), de_servico=True)
        self.assertEqual(c._varrer_abandonadas(), 0)
        self.assertEqual(correio.uma("gemini", m["id"])["situacao"], "pendente")


class EsperaNaoLargaNoWorker(_Base):
    def test_worker_nao_larga_a_espera_pela_conta_por_outra_mensagem(self):
        """No servico, a espera pela conta ocupada larga a mensagem (pendente)
        para entregar a de uma conta livre; no worker isso devolvia pendente."""
        ocupadas = {"perfil__gemini__teste"}
        voltas = []

        @contextmanager
        def trava(nome, esperar=0.0):
            voltas.append(nome)
            if len(voltas) > 3:
                ocupadas.clear()
            yield nome not in ocupadas
        c = _do_worker(carteiro_mod.fabrica_duble(responder=lambda t: "OK"))
        c.trava = trava
        correio.enviar("chatgpt", "outra conta, livre")
        m = correio.enviar("gemini", "pergunta")
        fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(fim["id"], m["id"])


if __name__ == "__main__":
    unittest.main()
