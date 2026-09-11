# -*- coding: utf-8 -*-
"""O modelo forte: tentar de novo, e nunca gravar vazio quando falhou.

Em 09/09/2026 as 22:59 a troca de modelo do Gemini estourou por `TimeoutError`
na PRIMEIRA tentativa, e a `historia_00004` inteira saiu no Flash-Lite:

    resposta do modelo    14-17 s   (contra 42-52 s no 3.1 Pro)
    palavras por parte    186-276   (contra 380-490)
    video por parte       73-102 s  (contra 140-175 s)

E `modelo_llm` gravou VAZIO — entao no dia seguinte nao havia como distinguir
essa historia de uma boa sem reabrir o log da noite. Custou 84 imagens do
PicassoIA e seis renders em cima de um texto do modelo fraco.

E a segunda vez que isto acontece. Em 08/09 o Gemini estava presa no "3.6
Flash" e as historias 3 a 10 sairam inteiras dele; a correcao de la foi criar
a troca de modelo. Faltava a troca ser confiavel.

O que este arquivo trava:

1. TENTA DE NOVO. O timeout e transitorio — a pagina esta hidratando, e na
   segunda tentativa ela responde.
2. NAO TENTA DE NOVO A TOA. Se a conta simplesmente NAO TEM o modelo forte,
   insistir nao muda nada e so gasta tempo.
3. VAZIO NAO E ausencia de informacao, e a informacao mais importante. Quando
   o alvo nao foi confirmado, o roteiro grava "NAO CONFIRMADO (...)".
"""
from __future__ import annotations

import unittest
from pathlib import Path

from contos.llm.cliente import ClienteLLM

RAIZ = Path(__file__).resolve().parents[1]


def _cliente(respostas):
    """Um cliente com `_tentar_modelo` roteirizado, uma resposta por volta."""
    cli = ClienteLLM.__new__(ClienteLLM)
    cli.provedor = "gemini"
    cli.sel = {"modelo_preferido": ["pro", "flash"], "modelo_botao": ["#m"]}
    cli.log = lambda *_a: None
    cli.modelo_atual = ""
    cli.modelo_confirmado = False
    fila = list(respostas)
    cli.tentativas = []

    def falso(ordem):
        cli.tentativas.append(ordem)
        return fila.pop(0) if fila else ("", False)
    cli._tentar_modelo = falso
    return cli


class RetentativaTests(unittest.TestCase):
    def test_de_primeira_nao_tenta_de_novo(self):
        cli = _cliente([("3.1 Pro", True)])
        self.assertEqual("3.1 Pro", cli.escolher_modelo())
        self.assertTrue(cli.modelo_confirmado)
        self.assertEqual(1, len(cli.tentativas))

    def test_timeout_na_primeira_e_recuperado_na_segunda(self):
        """Era exatamente este caso, e custou uma historia inteira."""
        cli = _cliente([("", False), ("3.1 Pro", True)])
        self.assertEqual("3.1 Pro", cli.escolher_modelo())
        self.assertTrue(cli.modelo_confirmado)
        self.assertEqual(2, len(cli.tentativas))

    def test_esgotadas_as_tentativas_a_geracao_SEGUE(self):
        """Seletor quebrado nao pode impedir a historia de nascer."""
        cli = _cliente([("Flash-Lite", False)] * 5)
        self.assertEqual("Flash-Lite", cli.escolher_modelo())
        self.assertFalse(cli.modelo_confirmado)
        self.assertEqual(cli.TENTATIVAS_DE_MODELO, len(cli.tentativas))

    def test_sem_catalogo_de_modelo_nao_tenta_nada(self):
        cli = _cliente([("x", True)])
        cli.sel = {}
        self.assertEqual("", cli.escolher_modelo())
        self.assertEqual([], cli.tentativas)


class RastroTests(unittest.TestCase):
    def test_o_estado_inicial_e_NAO_confirmado(self):
        """Enquanto ninguem confirmou, a resposta honesta e 'nao sei'."""
        cli = _cliente([])
        self.assertFalse(cli.modelo_confirmado)

    def test_o_roteiro_grava_que_o_modelo_nao_foi_confirmado(self):
        fonte = (RAIZ / "contos" / "roteiro" / "gerar.py").read_text(
            encoding="utf-8")
        trecho = fonte[fonte.index("def gerar_serie("):]
        self.assertIn("modelo_confirmado", trecho)
        self.assertIn("NAO CONFIRMADO", trecho)
        # e o aviso tem que sair no log da rodada, nao so no arquivo.
        # A frase e procurada em pedaco: ela vive quebrada entre duas linhas
        # da f-string, e cobrar o texto contiguo seria cobrar a formatacao.
        self.assertIn("ATENCAO", trecho)
        self.assertIn("confirmar o modelo forte", trecho)

    def test_conta_sem_o_modelo_forte_NAO_vira_retentativa(self):
        """Insistir contra uma conta que nao tem o modelo so gasta tempo."""
        fonte = (RAIZ / "contos" / "llm" / "cliente.py").read_text(
            encoding="utf-8")
        trecho = fonte[fonte.index("def _tentar_modelo("):]
        alvo = trecho[trecho.index("nenhum modelo de"):]
        self.assertIn("return atual, True", alvo[:200])


if __name__ == "__main__":
    unittest.main()
