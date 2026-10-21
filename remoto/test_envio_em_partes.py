# -*- coding: utf-8 -*-
"""Mensagem longa em PARTES: a parte que ja chegou nao chega de novo (21/10/2026).

O conferente achou (`partes_bot.py`): `Telegram.mensagem` devolvia so a
resposta da parte que falhou, e todo chamador (relatorio, alerta, fila,
`remoto --avisar`) reenviava o texto INTEIRO na volta seguinte. Com a parte 2
recusada para sempre, a parte 1 chegava a cada volta do laco (~120 vezes por
hora), sem fim. E o teto contava caractere do Python, e o Telegram conta
unidade UTF-16 (110 linhas com 🟢 = 3.999 caracteres = 4.099 unidades).

Caminho real: `Bot._relatorios` -> `Telegram.mensagem` -> `chamar` -> `abrir`
(dublado: guarda o que CHEGOU). Nada toca a rede nem os arquivos de verdade.
"""
import io
import json
import tempfile
import types
import unittest
import urllib.parse
from pathlib import Path

from remoto import api, avisos, bot, config, relatorios


class _Abrir:
    """Responde como o Telegram; `regra(campos)` decide. Guarda o que chegou."""

    def __init__(self, regra):
        self.regra, self.chamadas, self.chegou = regra, [], []

    def __call__(self, url, data=None, timeout=None):
        campos = dict(urllib.parse.parse_qsl(data.decode()))
        self.chamadas.append(campos)
        resposta = self.regra(campos)
        if resposta.get("ok"):
            self.chegou.append(campos["text"])
        return _Resp(resposta)


class _Resp(io.BytesIO):
    def __init__(self, r):
        super().__init__(json.dumps(r).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def texto_longo(linhas=160):
    cabeca = ["\U0001F6E1 *Confiabilidade* — o que saiu hoje"]
    return "\n".join(cabeca + [f"\U0001F7E2 historia {i:05d} ok — publicado às 21:37, prova "
                               f"em outputs/publicar/x{i}.json" for i in range(linhas)])


RECUSA = {"ok": False, "error_code": 400, "description": "Bad Request: message is too long"}


class _Ambiente(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        reais = (config.carregar, relatorios.devidos, relatorios.montar, relatorios.marcar,
                 avisos.ARQUIVO, avisos.PENDENTES)

        def volta():
            (config.carregar, relatorios.devidos, relatorios.montar, relatorios.marcar,
             avisos.ARQUIVO, avisos.PENDENTES) = reais
        self.addCleanup(volta)
        avisos.ARQUIVO = str(Path(tmp.name) / "avisos.json")
        avisos.PENDENTES = str(Path(tmp.name) / "pendentes.jsonl")
        config.carregar = lambda: {"autorizados": [111], "alertas": True,
                                   "relatorios": {"confiabilidade": "22:30"}}
        self.texto = texto_longo()
        self.partes = api.partes_da_mensagem(self.texto)
        self.assertGreaterEqual(len(self.partes), 3)
        self.marcados, self.logs = [], []
        relatorios.montar = lambda nome: self.texto
        relatorios.devidos = lambda horarios: [] if self.marcados else ["confiabilidade"]
        relatorios.marcar = lambda nome, dia: self.marcados.append(nome)

    def voltas(self, regra, n):
        abrir = _Abrir(regra)
        falso = types.SimpleNamespace(tg=api.Telegram("t", abrir=abrir),
                                      _relatorio_montado={}, log=self.logs.append)
        for _ in range(n):
            bot.Bot._relatorios(falso)
        return abrir


class RelatorioEmPartesTests(_Ambiente):

    def test_tudo_ok_chega_inteiro_uma_vez(self):
        a = self.voltas(lambda c: {"ok": True}, 3)
        self.assertEqual(self.texto, "\n".join(a.chegou))
        self.assertEqual(["confiabilidade"], self.marcados)

    def test_parte_2_falha_uma_vez_a_parte_1_chega_uma_vez(self):
        falhou = []

        def regra(c):
            if c["text"] == self.partes[1] and not falhou:
                falhou.append(1)
                return {}                         # sem rede
            return {"ok": True}
        a = self.voltas(regra, 3)
        self.assertEqual(1, a.chegou.count(self.partes[0]))
        self.assertEqual(self.texto, "\n".join(a.chegou), "nada perdido, nada repetido")
        self.assertEqual(["confiabilidade"], self.marcados)

    def test_parte_2_recusada_sempre_nao_repete_sem_fim(self):
        a = self.voltas(lambda c: RECUSA if c["text"] == self.partes[1] else {"ok": True}, 10)
        self.assertEqual(1, a.chegou.count(self.partes[0]), "a parte 1 chega UMA vez")
        self.assertEqual(api.TETO_DE_TENTATIVAS,
                         sum(1 for c in a.chamadas if c["text"] == self.partes[1]))
        for parte in self.partes[2:]:
            self.assertEqual(1, a.chegou.count(parte), "o resto segue depois do teto")
        self.assertEqual(["confiabilidade"], self.marcados)
        self.assertTrue(any("puladas" in str(x) for x in self.logs),
                        "a parte pulada e dita, nunca calada")

    def test_sem_rede_nao_gasta_o_teto_nem_repete(self):
        rede = {"fora": True}

        def regra(c):
            if c["text"] == self.partes[1] and rede["fora"]:
                return {}
            return {"ok": True}
        a = self.voltas(regra, 10)
        self.assertEqual(1, a.chegou.count(self.partes[0]))
        self.assertEqual([], self.marcados, "sem rede nao e entrega")
        self.assertEqual(10, sum(1 for c in a.chamadas if c["text"] == self.partes[1]),
                         "falta de rede tenta de novo a cada volta, sem pular")


class TetoEmUtf16Tests(unittest.TestCase):

    def test_110_linhas_com_emoji_cabem_em_unidades_utf16(self):
        texto = "\n".join("\U0001F7E2 " + "x" * 33 for _ in range(110))
        self.assertLessEqual(len(texto), 4000)
        self.assertGreater(api.unidades(texto), 4000, "o caso que passava do teto")
        partes = api.partes_da_mensagem(texto)
        self.assertGreater(len(partes), 1)
        self.assertTrue(all(api.unidades(p) <= api.LIMITE_DA_MENSAGEM for p in partes))
        self.assertEqual(texto, "\n".join(partes))

    def test_linha_gigante_de_emoji_nao_parte_o_emoji(self):
        partes = api.partes_da_mensagem("\U0001F7E2" * 3000)         # 6000 unidades
        self.assertTrue(all(api.unidades(p) <= 4000 for p in partes))
        self.assertEqual("\U0001F7E2" * 3000, "".join(partes))
        self.assertEqual(2000, len(partes[0]))

    def test_caso_zero(self):
        self.assertEqual([""], api.partes_da_mensagem(""))
        self.assertEqual(0, api.unidades(""))


class FilaSoComOResto(_Ambiente):

    def test_alerta_pela_metade_enfileira_so_o_que_faltou(self):
        abrir = _Abrir(lambda c: {} if c["text"] == self.partes[1] else {"ok": True})
        falso = types.SimpleNamespace(tg=api.Telegram("t", abrir=abrir), log=self.logs.append)
        self.assertTrue(bot.Bot._mandar_alerta(falso, self.texto, "teste", markdown=False))
        fila = [i["texto"] for i in avisos.pendentes()]
        self.assertEqual(["\n".join(self.partes[1:])], fila)
        self.assertNotIn(self.partes[0], fila[0])

    def test_remoto_avisar_pela_metade_enfileira_so_o_resto(self):
        from remoto import __main__ as principal
        abrir = _Abrir(lambda c: {} if c["text"] == self.partes[1] else {"ok": True})
        real = principal.config.token
        self.addCleanup(setattr, principal.config, "token", real)
        principal.config.token = lambda: "t"
        import remoto.api as modulo_api
        real_tg = modulo_api.Telegram
        self.addCleanup(setattr, modulo_api, "Telegram", real_tg)
        modulo_api.Telegram = lambda token: real_tg(token, abrir=abrir)
        self.assertTrue(principal.avisar(self.texto))
        fila = [i["texto"] for i in avisos.pendentes()]
        self.assertEqual(["\n".join(self.partes[1:])], fila)

    def test_entrega_inteira_nao_enfileira_nada(self):
        abrir = _Abrir(lambda c: {"ok": True})
        falso = types.SimpleNamespace(tg=api.Telegram("t", abrir=abrir), log=self.logs.append)
        self.assertTrue(bot.Bot._mandar_alerta(falso, self.texto, "teste2", markdown=False))
        self.assertEqual([], avisos.pendentes())


if __name__ == "__main__":
    unittest.main()
