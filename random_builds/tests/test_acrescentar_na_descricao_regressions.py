# -*- coding: utf-8 -*-
"""`recuperar.acrescentar_na_descricao`: ligar a parte N a N+1 pela API.

Decisao `publicacao/historias-21h-e-parte-seguinte` (19/10/2026, TESTE). Fica
DESLIGADA em `postar.LIGAR_PELA_API`: medido em 19/10, a credencial do canal
de historias nao tem o escopo de edicao (`youtube`); a de builds tem. Quando o
Adrian autorizar, este e o caminho — e ele precisa de tres cuidados, que
estes testes prendem: `videos.update` SUBSTITUI o `snippet` inteiro (titulo e
categoria sao obrigatorios e nao podem sumir), o texto nao e posto duas vezes,
e o canal e relido depois (200 nao e prova).
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import builds.publicar.recuperar as R


class _Resposta:
    def __init__(self, status, texto=""):
        self.status_code = status
        self.text = texto
        self.ok = 200 <= status < 300


SNIPPET = {"title": "A Conta (Parte 1/6)", "description": "Parte 1 de 6.",
           "categoryId": "24", "tags": ["historia"], "channelId": "UCx",
           "thumbnails": {"default": {}}}


class AcrescentarNaDescricaoTests(unittest.TestCase):
    def _rodar(self, descricao_antes="Parte 1 de 6.", status_put=200,
               depois_tem=True):
        self.enviado = None
        texto = "Parte 2: https://youtube.com/shorts/ID2"
        antes = dict(SNIPPET, description=descricao_antes)
        depois = dict(SNIPPET, description=descricao_antes + "\n\n" + (
            texto if depois_tem else ""))
        leituras = [{"items": [{"snippet": antes}]},
                    {"items": [{"snippet": depois}]}]

        def get(_t, caminho, **_k):
            if caminho == "channels":
                return {"items": [{"id": "UCx"}]}
            return leituras.pop(0)

        def put(_url, **kw):
            self.enviado = json.loads(kw["data"].decode("utf-8"))
            return _Resposta(status_put, "recusado")
        with patch.object(R, "_get", get), \
             patch.object(R, "conferir_o_canal", lambda *a: None), \
             patch.object(R, "_token", lambda _c: "tok"), \
             patch("requests.put", put):
            return R.acrescentar_na_descricao("ID1", texto, "historias")

    def test_poe_no_fim_e_mantem_titulo_e_categoria(self):
        r = self._rodar()
        self.assertTrue(r["mudou"])
        snippet = self.enviado["snippet"]
        self.assertEqual("A Conta (Parte 1/6)", snippet["title"])
        self.assertEqual("24", snippet["categoryId"])
        self.assertEqual(["historia"], snippet["tags"])
        self.assertTrue(snippet["description"].endswith(
            "Parte 2: https://youtube.com/shorts/ID2"))
        self.assertTrue(snippet["description"].startswith("Parte 1 de 6."))
        self.assertNotIn("thumbnails", snippet, "campo que o PUT recusa")

    def test_ja_tem_o_texto_nao_manda_nada(self):
        r = self._rodar(descricao_antes="x\n\nParte 2: https://youtube.com/shorts/ID2")
        self.assertFalse(r["mudou"])
        self.assertIsNone(self.enviado)

    def test_sem_escopo_e_falta_escopo(self):
        with self.assertRaises(R.FaltaEscopo):
            self._rodar(status_put=403)

    def test_canal_que_nao_mostra_o_texto_nao_e_mudou(self):
        r = self._rodar(depois_tem=False)
        self.assertFalse(r["mudou"])
        self.assertTrue(r["motivo"])


if __name__ == "__main__":
    unittest.main()
