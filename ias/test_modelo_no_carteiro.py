# -*- coding: utf-8 -*-
"""O modelo no carteiro: imagem sem troca de modelo (HIS-11) e a nota do
modelo nao confirmado (IAS-9). Auditoria de 11/10/2026.

HIS-11: cada chat novo pagava a troca de modelo inteira (3 tentativas, os
`sleep` e os timeouts do menu), ~32 s de mediana por chat e ~1,9 h em 06-08/10
— quase tudo no carteiro, que abre um chat por IMAGEM. O pedido de imagem nao
precisa do Pro: o chat dele abre sem mexer no modelo.

IAS-9: o carteiro gravava a resposta com o modelo fraco (ou vazio) sem nota
nenhuma. Agora a resposta de um chat fora do modelo forte leva a nota
"modelo nao confirmado (saiu em X)", e o Telegram de uma pergunta do Adrian
tambem.

Com dublê: nenhum navegador, Telegram ou `%LOCALAPPDATA%` real (a raiz vai
para `NF_IAS_PASTA`).
"""
from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

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


def _fabrica(**atributos):
    """A fabrica dublê de sempre, com atributos extras em cada sessao."""
    criadas = []

    @contextmanager
    def _abrir(ia):
        sessao = carteiro_mod.SessaoDuble(ia, responder=lambda t: "OK")
        for nome, valor in atributos.items():
            setattr(sessao, nome, valor)
        criadas.append(sessao)
        yield sessao

    _abrir.criadas = criadas
    return _abrir


def _novo(fabrica):
    avisos = []
    c = carteiro_mod.Carteiro(
        fabrica_de_sessao=fabrica, fabrica_imagem=imagem.fabrica_imagem_duble(),
        trava=_trava_livre, nome_da_trava=lambda ia: f"perfil__{ia}__teste",
        avisar=avisos.append, avisar_arquivo=lambda caminho, legenda: True,
        log=lambda m: None, dormir=lambda s: None, de_servico=True,
        ajustes={"janela_conversa_s": 0, "resumo_a_cada": 50,
                 "espera_conta_max_s": 100,
                 "rodizio_imagem": ["gemini", "chatgpt"], "cota_pausa_h": 6})
    c._diario = lambda *a: None
    c.avisos = avisos
    return c


class ModeloNaoConfirmadoVaiNaNota(_Base):
    def test_resposta_fora_do_modelo_forte_leva_a_nota(self):
        fabrica = _fabrica(modelo="3.5 Flash", modelo_confirmado=False)
        c = _novo(fabrica)
        correio.enviar("gemini", "oi", de="adrian")
        fim = c.uma_volta()
        self.assertEqual("respondida", fim["situacao"])
        self.assertIn("não confirmado", fim.get("nota") or "")
        self.assertIn("3.5 Flash", fim["nota"])
        # a pergunta foi do Adrian: o Telegram diz o mesmo
        self.assertEqual(1, len(c.avisos))
        self.assertIn("modelo não confirmado (saiu em 3.5 Flash)", c.avisos[0])

    def test_modelo_forte_nao_ganha_nota(self):
        c = _novo(_fabrica(modelo="3.1 Pro", modelo_confirmado=True))
        correio.enviar("gemini", "oi", de="adrian")
        fim = c.uma_volta()
        self.assertFalse(fim.get("nota"))
        self.assertNotIn("não confirmado", c.avisos[0])

    def test_pergunta_de_outra_parte_nao_leva_a_frase_ao_telegram(self):
        c = _novo(_fabrica(modelo="", modelo_confirmado=False))
        correio.enviar("gemini", "oi", de="assembleia")
        fim = c.uma_volta()
        self.assertIn("saiu em desconhecido", fim["nota"])
        self.assertNotIn("não confirmado", c.avisos[0])


class ImagemNaoTrocaModelo(_Base):
    def test_chat_da_imagem_abre_sem_trocar_o_modelo(self):
        fabrica = _fabrica()
        c = _novo(fabrica)
        m = correio.pedir_imagem("chatgpt", "um gato", proporcao="1:1")
        self.assertEqual("respondida", c.uma_volta()["situacao"])
        s = fabrica.criadas[0]
        self.assertEqual(1, s.casas_novas)
        self.assertEqual(1, s.chats_de_imagem)
        self.assertTrue(correio.arquivo_da_imagem("chatgpt", m["id"]).is_file())

    def test_texto_continua_trocando(self):
        fabrica = _fabrica()
        c = _novo(fabrica)
        correio.enviar("gemini", "oi")
        c.uma_volta()
        self.assertEqual(0, fabrica.criadas[0].chats_de_imagem)

    def test_sessao_antiga_sem_o_parametro_continua_funcionando(self):
        chamadas = []

        class Velha:
            def novo_chat(self):
                chamadas.append("novo")

            def abrir_casa(self, url):
                chamadas.append(url)
                return True

        carteiro_mod._chat_de_imagem(Velha().novo_chat)
        self.assertTrue(carteiro_mod._reabrir_conversa_de_imagem(Velha(), "u"))
        self.assertEqual(["novo", "u"], chamadas)


class SessaoRealPassaAdiante(unittest.TestCase):
    """A sessao de verdade sobre um cliente dublado (sem navegador)."""

    class _Cliente:
        def __init__(self):
            self.aberturas = []
            self.modelo_atual = "3.5 Flash"
            self.modelo_forte = False
            self.modelo_confirmado = True

        def abrir(self, novo_chat=True, trocar_modelo=True):
            self.aberturas.append(trocar_modelo)

    def test_novo_chat_de_imagem_pede_para_nao_trocar(self):
        cliente = self._Cliente()
        sessao = carteiro_mod.SessaoReal(cliente, log=lambda m: None)
        sessao.novo_chat(imagem=True)
        sessao.novo_chat()
        self.assertEqual([False, True], cliente.aberturas)

    def test_modelo_confirmado_e_o_modelo_forte_do_cliente(self):
        cliente = self._Cliente()
        sessao = carteiro_mod.SessaoReal(cliente, log=lambda m: None)
        # confirmado (a escolha terminou), mas no 2o da lista: NAO e forte
        self.assertFalse(sessao.modelo_confirmado)
        cliente.modelo_forte = True
        self.assertTrue(sessao.modelo_confirmado)
        del cliente.modelo_forte                    # cliente antigo
        self.assertTrue(sessao.modelo_confirmado)


if __name__ == "__main__":
    unittest.main()
