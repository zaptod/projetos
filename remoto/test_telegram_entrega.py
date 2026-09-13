# -*- coding: utf-8 -*-
"""O relatorio CHEGA, mesmo quando a formatacao nao vale (11/09/2026).

O DEFEITO, e ele calava o canal inteiro. O bot manda tudo com
`parse_mode=Markdown`, e o Markdown legado do Telegram trata `_` e `*` como
formatacao. Todo id deste projeto tem underscore — `historia_00004`,
`p04_cena_02`, `generation_00055` —, entao os TRES relatorios voltavam

    400 Bad Request: can't parse entities: Can't find end of the entity

e nada era entregue. Medido: metas, funcionamento e auditoria, os tres.

Nao havia como perceber. `chamar()` transformava qualquer erro em `{}`, entao
o motivo real que o Telegram poe no corpo do 400 era jogado fora, e quem
chamava seguia em frente sem checar. O canal que existe para avisar que algo
quebrou era o que estava quebrado.

    cd e:\\projetos
    python -m pytest remoto/test_telegram_entrega.py -q
"""
from __future__ import annotations

import io
import json
import unittest
import urllib.error

from remoto import api


class _Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _ok(**extra):
    return _Resposta(json.dumps({"ok": True, **extra}).encode("utf-8"))


def _erro_400(descricao: str):
    corpo = json.dumps({"ok": False, "error_code": 400,
                        "description": descricao}).encode("utf-8")
    return urllib.error.HTTPError("u", 400, "Bad Request", {},
                                  io.BytesIO(corpo))


class Espiao:
    """Guarda cada chamada e devolve o que o teste mandar, em ordem."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def __call__(self, url, data=None, timeout=None):
        corpo = (data or b"").decode("utf-8")
        self.chamadas.append(corpo)
        proxima = self.respostas.pop(0)
        if isinstance(proxima, Exception):
            raise proxima
        return proxima


class EntregaTests(unittest.TestCase):

    def _bot(self, respostas):
        self.espiao = Espiao(respostas)
        return api.Telegram("t", abrir=self.espiao)

    def test_markdown_quebrado_reenvia_sem_formatacao(self):
        bot = self._bot([_erro_400("Bad Request: can't parse entities: "
                                   "Can't find end of the entity at byte 481"),
                         _ok()])
        resposta = bot.mensagem(1, "veja historia_00004:celular:p04",
                                markdown=True)
        self.assertTrue(resposta.get("ok"))
        self.assertEqual(2, len(self.espiao.chamadas))
        self.assertIn("parse_mode", self.espiao.chamadas[0])
        self.assertNotIn("parse_mode", self.espiao.chamadas[1],
                         "o reenvio tem que ir SEM formatacao")

    def test_o_texto_do_reenvio_e_o_mesmo(self):
        """Conteudo e o que importa; negrito e enfeite."""
        bot = self._bot([_erro_400("can't parse entities"), _ok()])
        bot.mensagem(1, "historia_00004 barrada", markdown=True)
        self.assertIn("historia_00004", self.espiao.chamadas[1])

    def test_sucesso_de_primeira_nao_reenvia(self):
        bot = self._bot([_ok()])
        self.assertTrue(bot.mensagem(1, "tudo bem", markdown=True).get("ok"))
        self.assertEqual(1, len(self.espiao.chamadas))

    def test_erro_que_nao_e_de_formatacao_nao_reenvia(self):
        """Chat errado nao se conserta tirando o negrito — reenviar ali so
        gastaria uma segunda chamada para tomar o mesmo 400."""
        bot = self._bot([_erro_400("Bad Request: chat not found")])
        resposta = bot.mensagem(1, "oi", markdown=True)
        self.assertFalse(resposta.get("ok"))
        self.assertEqual(1, len(self.espiao.chamadas))

    def test_sem_markdown_nao_ha_o_que_reenviar(self):
        bot = self._bot([_erro_400("can't parse entities")])
        bot.mensagem(1, "oi")
        self.assertEqual(1, len(self.espiao.chamadas))

    def test_o_motivo_do_400_volta_em_vez_de_virar_vazio(self):
        """`chamar()` engolia o corpo do 400, e o motivo real do Telegram
        morria ali. Foi o que manteve o defeito invisivel."""
        bot = self._bot([_erro_400("Bad Request: chat not found")])
        resposta = bot.chamar("sendMessage", chat_id=1, text="x")
        self.assertIn("chat not found", str(resposta.get("description")))

    def test_falha_de_rede_continua_devolvendo_vazio(self):
        """Wi-Fi caido nao pode derrubar o bot — a regra antiga vale."""
        bot = self._bot([urllib.error.URLError("sem rede")])
        self.assertEqual({}, bot.chamar("sendMessage", chat_id=1, text="x"))


class RelatoriosCabemNoTelegramTests(unittest.TestCase):
    """Os textos de verdade, contra o parser de verdade — sem tocar a rede."""

    def _enviar(self, texto: str) -> list:
        espiao = Espiao([_erro_400("can't parse entities"), _ok()])
        api.Telegram("t", abrir=espiao).mensagem(1, texto, markdown=True)
        return espiao.chamadas

    def test_um_id_com_underscore_ainda_chega(self):
        chamadas = self._enviar("*Auditoria*\n  ✕ historia_00004:celular:p04")
        self.assertEqual(2, len(chamadas))
        self.assertIn("p04", chamadas[-1])

    def test_o_corte_de_4000_vale_para_os_dois_envios(self):
        espiao = Espiao([_erro_400("can't parse entities"), _ok()])
        # "Z" e nao "x": o corpo urlencoded traz `text=`, `chat_id=` e
        # `disable_web_page_preview=`, e contar "x" somava a letra do proprio
        # nome do campo — o teste falhou por 4001 na primeira versao.
        api.Telegram("t", abrir=espiao).mensagem(1, "Z" * 9000, markdown=True)
        for corpo in espiao.chamadas:
            self.assertLessEqual(corpo.count("Z"), 4000)


if __name__ == "__main__":
    unittest.main()
