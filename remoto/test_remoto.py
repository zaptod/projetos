# -*- coding: utf-8 -*-
"""Contratos do controle pelo celular.

Este bot controla uma maquina com YouTube, TikTok, ChatGPT e PicassoIA
logados. Por isso os testes aqui sao menos sobre "funciona" e mais sobre
"nao faz o que nao devia":

1. LISTA BRANCA. Quem nao esta na lista nao executa NADA e nao descobre nada
   — nem a lista de comandos, que ja e informacao sobre a maquina.
2. TABELA FECHADA. Nao existe caminho de "texto do celular" para "comando do
   sistema". Um `/rodar rm -rf` tem que morrer como comando desconhecido.
3. NADA DERRUBA O BOT. Comando que explode, rede que cai e mensagem torta
   viram resposta, nao stack trace — um bot morto as 3 da manha e pior que
   um bot que erra.
4. ALERTA SO DO QUE E NOVO. Ligar o bot nao pode despejar o historico de
   erros do dia no celular.

Rode da raiz do repo:
    python -m unittest remoto.test_remoto -v
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from remoto import bot as bot_mod
from remoto import comandos, config
from remoto.api import Telegram


def _ts(minutos_atras: float = 0) -> str:
    return (datetime.now(timezone.utc)
            - timedelta(minutes=minutos_atras)).isoformat(timespec="seconds")


class TelegramFalso:
    """Guarda o que seria enviado, em vez de falar com a rede."""

    def __init__(self, novidades=None, nome="meubot"):
        self._novidades = list(novidades or [])
        self.enviadas = []
        self.arquivos = []
        self.nome = nome

    def eu(self):
        return {"username": self.nome}

    def novidades(self, desde=None, timeout=30):
        saida, self._novidades = self._novidades, []
        return saida

    def mensagem(self, chat_id, texto, markdown=False):
        self.enviadas.append((chat_id, texto))
        return {"ok": True}

    def arquivo(self, chat_id, caminho, legenda="", como_video=True):
        self.arquivos.append((chat_id, str(caminho), legenda))
        return {"ok": True}

    # atalhos de leitura para os testes
    def textos(self, chat=None):
        return [t for c, t in self.enviadas if chat is None or c == chat]


def _mensagem(texto, chat=42, update_id=1):
    return {"update_id": update_id,
            "message": {"chat": {"id": chat}, "text": texto}}


class BaseTemp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        config.ARQUIVO = str(self.pasta / "remoto.json")
        self.addCleanup(lambda: setattr(config, "ARQUIVO", None))
        # o diario tambem vai para a pasta temporaria
        self._arquivo_diario = comandos.atividade._arquivo
        comandos.atividade._arquivo = lambda: self.pasta / "atividade.jsonl"
        self.addCleanup(lambda: setattr(comandos.atividade, "_arquivo",
                                        self._arquivo_diario))


class ListaBrancaTests(BaseTemp):
    def test_desconhecido_nao_executa_nada(self):
        tg = TelegramFalso([_mensagem("/parar", chat=999)])
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        robo.uma_volta(timeout=0)
        self.assertEqual(["não autorizado."], tg.textos())

    def test_desconhecido_nao_recebe_a_lista_de_comandos(self):
        tg = TelegramFalso([_mensagem("/ajuda", chat=999)])
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        robo.uma_volta(timeout=0)
        junto = " ".join(tg.textos())
        self.assertNotIn("/publicar", junto)
        self.assertNotIn("/gerar", junto)

    def test_codigo_certo_autoriza_uma_vez_so(self):
        tg = TelegramFalso()
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        tg._novidades = [_mensagem(f"/parear {robo.codigo}", chat=7)]
        robo.uma_volta(timeout=0)
        self.assertTrue(config.autorizado(7))
        # um segundo desconhecido com o MESMO codigo nao entra
        tg._novidades = [_mensagem(f"/parear {robo.codigo}", chat=8, update_id=2)]
        robo.uma_volta(timeout=0)
        self.assertFalse(config.autorizado(8))

    def test_codigo_errado_nao_autoriza(self):
        tg = TelegramFalso([_mensagem("/parear 000000", chat=7)])
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        robo.codigo = "123456"
        robo.uma_volta(timeout=0)
        self.assertFalse(config.autorizado(7))

    def test_autorizado_executa(self):
        config.autorizar(42)
        tg = TelegramFalso([_mensagem("/vila")])
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        robo.uma_volta(timeout=0)
        self.assertTrue(tg.textos(), "não respondeu a quem tem permissão")

    def test_esquecer_revoga(self):
        config.autorizar(42)
        config.esquecer(42)
        self.assertFalse(config.autorizado(42))


class TabelaFechadaTests(BaseTemp):
    """Nao existe caminho de texto do celular para comando do sistema."""

    def test_comando_desconhecido_morre(self):
        for texto in ("/rodar rm -rf /", "/exec import os", "/shell dir",
                      "/eval 2+2", "/sh"):
            resposta, arquivo = comandos.executar(texto)
            self.assertIn("não conheço", resposta, texto)
            self.assertIsNone(arquivo)

    def test_texto_solto_nao_e_comando(self):
        resposta, _ = comandos.executar("apaga tudo por favor")
        self.assertIn("/ajuda", resposta)

    def test_a_tabela_nao_tem_nada_de_shell(self):
        proibidos = ("rodar", "exec", "shell", "sh", "cmd", "eval", "python")
        for nome in comandos.TABELA:
            self.assertNotIn(nome, proibidos, f"/{nome} não devia existir")

    def test_comando_que_explode_vira_resposta(self):
        def bomba(_args):
            raise RuntimeError("boom")

        comandos.TABELA["testebomba"] = bomba
        self.addCleanup(lambda: comandos.TABELA.pop("testebomba", None))
        resposta, _ = comandos.executar("/testebomba")
        self.assertIn("falhou", resposta)
        self.assertIn("boom", resposta)

    def test_publicar_exige_id_que_existe(self):
        self.assertIn("diga o id", comandos.publicar(""))
        self.assertIn("não achei", comandos.publicar("id_que_nao_existe_xyz"))

    def test_publicar_recusa_destino_invalido(self):
        original = comandos.procurar_video
        comandos.procurar_video = lambda _p: type(
            "V", (), {"id": "x", "titulo": "t"})()
        self.addCleanup(lambda: setattr(comandos, "procurar_video", original))
        self.assertIn("onde?", comandos.publicar("x instagram"))


class AlertaTests(BaseTemp):
    def test_so_avisa_o_que_e_novo(self):
        """Ligar o bot nao pode despejar o historico do dia no celular."""
        comandos.atividade.registrar("picasso", "erro", "erro velho")
        config.autorizar(42)
        tg = TelegramFalso()
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        robo.uma_volta(timeout=0)
        self.assertEqual([], tg.textos(), "avisou de erro anterior ao bot")

        comandos.atividade.registrar("digen", "erro", "quebrou agora")
        robo.uma_volta(timeout=0)
        self.assertTrue(any("quebrou agora" in t for t in tg.textos()))

    def test_nao_repete_o_mesmo_alerta(self):
        config.autorizar(42)
        tg = TelegramFalso()
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        comandos.atividade.registrar("digen", "erro", "quebrou")
        robo.uma_volta(timeout=0)
        antes = len(tg.textos())
        robo.uma_volta(timeout=0)
        self.assertEqual(antes, len(tg.textos()), "mandou o mesmo erro 2x")

    def test_sucesso_nao_vira_alerta(self):
        config.autorizar(42)
        tg = TelegramFalso()
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        comandos.atividade.registrar("estudio", "ok", "video pronto")
        robo.uma_volta(timeout=0)
        self.assertEqual([], tg.textos())

    def test_alerta_vai_para_todos_os_autorizados(self):
        config.autorizar(1)
        config.autorizar(2)
        tg = TelegramFalso()
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        comandos.atividade.registrar("arena", "erro", "caiu")
        robo.uma_volta(timeout=0)
        self.assertEqual({1, 2}, {c for c, _t in tg.enviadas})


class ResistenciaTests(BaseTemp):
    def test_mensagem_sem_texto_nao_quebra(self):
        config.autorizar(42)
        tg = TelegramFalso([{"update_id": 1,
                             "message": {"chat": {"id": 42}}}])
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        robo.uma_volta(timeout=0)          # nao pode levantar

    def test_rede_caida_devolve_vazio(self):
        def cair(*_a, **_k):
            raise OSError("sem rede")

        tg = Telegram("token-falso", abrir=cair)
        self.assertEqual([], tg.novidades())
        self.assertEqual({}, tg.chamar("getMe"))

    def test_arquivo_grande_demais_e_recusado_com_motivo(self):
        grande = self.pasta / "grande.mp4"
        grande.write_bytes(b"0" * 1024)
        from remoto import api
        limite = api.LIMITE_ARQUIVO_MB
        api.LIMITE_ARQUIVO_MB = 0.0001
        self.addCleanup(lambda: setattr(api, "LIMITE_ARQUIVO_MB", limite))
        resposta = Telegram("t").arquivo(1, grande)
        self.assertFalse(resposta["ok"])
        self.assertIn("limite", resposta["description"])

    def test_arquivo_que_nao_existe_nao_levanta(self):
        resposta = Telegram("t").arquivo(1, self.pasta / "fantasma.mp4")
        self.assertFalse(resposta["ok"])


class ConfigTests(BaseTemp):
    def test_token_do_ambiente_quando_nao_ha_arquivo(self):
        import os
        os.environ["TELEGRAM_BOT_TOKEN"] = "do-ambiente"
        self.addCleanup(lambda: os.environ.pop("TELEGRAM_BOT_TOKEN", None))
        self.assertEqual("do-ambiente", config.token())

    def test_arquivo_vence_o_ambiente(self):
        import os
        os.environ["TELEGRAM_BOT_TOKEN"] = "do-ambiente"
        self.addCleanup(lambda: os.environ.pop("TELEGRAM_BOT_TOKEN", None))
        config.salvar({**config.carregar(), "token": "do-arquivo"})
        self.assertEqual("do-arquivo", config.token())

    def test_config_torta_nao_derruba(self):
        Path(config.caminho()).write_text("{isto nao e json",
                                          encoding="utf-8")
        self.assertEqual([], config.carregar()["autorizados"])

    def test_o_token_nunca_aparece_na_ajuda(self):
        config.salvar({**config.carregar(), "token": "segredo123"})
        self.assertNotIn("segredo123", comandos.ajuda())


class RespostasTests(BaseTemp):
    def test_status_responde_sem_nada_rodando(self):
        self.assertIn("nada rodando", comandos.status())

    def test_vila_lista_as_sete_fabricas(self):
        linhas = comandos.vila().splitlines()
        self.assertEqual(len(comandos.atividade.FABRICAS), len(linhas))

    def test_erros_diz_quando_esta_limpo(self):
        self.assertIn("nenhum erro", comandos.erros())

    def test_erros_mostra_o_que_aconteceu(self):
        comandos.atividade.registrar("picasso", "erro", "cena bloqueada")
        self.assertIn("cena bloqueada", comandos.erros())

    def test_ajuda_lista_os_comandos_de_verdade(self):
        texto = comandos.ajuda()
        for nome in ("status", "vila", "erros", "publicar", "pausar"):
            self.assertIn(f"/{nome}", texto)


if __name__ == "__main__":
    unittest.main()
