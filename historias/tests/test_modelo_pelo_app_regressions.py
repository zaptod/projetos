# -*- coding: utf-8 -*-
"""O modelo do Gemini escolhido pelo app (01/10/2026, tarefa 52dc403c).

Pedido do Adrian: "suporte para mudar o modelo tanto do Claude quanto do Codex
e do Gemini". O Gemini e o do NAVEGADOR (decisao geral/gemini-sem-cli): o
`ClienteLLM` ja sabia escolher pelo menu do site, mas a ordem morava so nos
seletores (`modelo_preferido: ["pro", "flash"]`). A Mesa de comando grava a
escolha dele no bloco do provedor em `config/llm.json`, e o cliente a usa.

O que este arquivo trava:
1. com `modelo_preferido` no config, a troca procura essa ordem;
2. sem ele (ou torto), vale a dos seletores, como antes;
3. um `preferido` passado por quem chama ainda manda sobre os dois.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from contos.llm import papeis
from contos.llm.cliente import ClienteLLM


def _cliente():
    cli = ClienteLLM.__new__(ClienteLLM)
    cli.provedor = "gemini"
    cli.sel = {"modelo_preferido": ["pro", "flash"], "modelo_botao": ["#m"]}
    cli.log = lambda *_a: None
    cli.modelo_atual = ""
    cli.modelo_confirmado = False
    cli.tentativas = []

    def falso(ordem):
        cli.tentativas.append(list(ordem))
        return "3.6 Flash", True
    cli._tentar_modelo = falso
    return cli


class ModeloPeloAppTests(unittest.TestCase):
    def _com_config(self, dados):
        pasta = tempfile.mkdtemp()
        arquivo = Path(pasta) / "llm.json"
        arquivo.write_text(json.dumps(dados) if not isinstance(dados, str) else dados,
                           encoding="utf-8")
        return mock.patch.object(papeis, "ARQUIVO", arquivo)

    def test_config_manda_a_ordem(self):
        with self._com_config({"gemini": {"modelo_preferido": ["3.6 flash", "flash"]}}):
            cli = _cliente()
            cli.escolher_modelo()
        self.assertEqual([["3.6 flash", "flash"]], cli.tentativas)

    def test_sem_config_vale_a_dos_seletores(self):
        for dados in ({}, {"gemini": {}}, {"gemini": {"modelo_preferido": []}},
                      {"gemini": {"modelo_preferido": 7}}, "{ilegivel"):
            with self._com_config(dados):
                cli = _cliente()
                cli.escolher_modelo()
            self.assertEqual([["pro", "flash"]], cli.tentativas, dados)

    def test_quem_chama_ainda_manda(self):
        with self._com_config({"gemini": {"modelo_preferido": ["3.6 flash"]}}):
            cli = _cliente()
            cli.escolher_modelo(preferido=["pro"])
        self.assertEqual([["pro"]], cli.tentativas)

    def test_outro_provedor_nao_le_o_bloco_do_gemini(self):
        with self._com_config({"gemini": {"modelo_preferido": ["3.6 flash"]}}):
            cli = _cliente()
            cli.provedor = "chatgpt"
            cli.escolher_modelo()
        self.assertEqual([["pro", "flash"]], cli.tentativas)


if __name__ == "__main__":
    unittest.main()
