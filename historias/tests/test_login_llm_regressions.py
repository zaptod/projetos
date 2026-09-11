# -*- coding: utf-8 -*-
"""Contratos do login do ChatGPT/Gemini: "logado" tem que ser verdade.

Em 09/09/2026, tentando trocar a conta do ChatGPT, a pergunta "esta logado?"
foi respondida errada DUAS VEZES, uma para cada lado — e cada erro custou uma
decisao:

  FALSO POSITIVO  `contas.tem_login` so olha se o arquivo de cookies do Chrome
                  existe em disco. Ele nasce na primeira vez que o navegador
                  abre, logado ou nao. Perfil recem-criado, zero sessao, e a
                  resposta foi "True" — e eu repassei isso como se fosse fato.

  FALSO NEGATIVO  a conferencia que escrevi para consertar aquilo abria a
                  pagina HEADLESS. O `chatgpt.com` serve o desafio do
                  Cloudflare ("Um momento...") para janela headless: o chat
                  nunca monta, e concluir "deslogado" dai declara morta uma
                  sessao viva.

O que este arquivo trava:

1. TRES ESTADOS, nao dois. `None` e "nao deu para perguntar", e ele nunca
   pode virar `False` — a diferenca entre "voce nao esta logado" e "eu nao
   consegui olhar" e a diferenca entre refazer o login e nao mexer em nada.
2. O DESAFIO ANTI-BOT E RECONHECIDO pelo titulo, nas duas linguas.
3. CHAT QUE MONTOU NA JANELA DE VERDADE E PROVA SUFICIENTE. Reconferir depois
   so acrescenta uma chance de errar, e foi exatamente o que aconteceu.
4. FECHAR A JANELA E FIM NORMAL, nao um traceback de trinta linhas.

Rode de dentro de historias/:
    python -m unittest tests.test_login_llm_regressions -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

from contos.llm import probe                                      # noqa: E402


class DesafioAntiBotTests(unittest.TestCase):
    def test_o_titulo_do_cloudflare_e_reconhecido_nas_duas_linguas(self):
        for titulo in ("Um momento…", "Just a moment...",
                       "Attention Required! | Cloudflare"):
            baixo = titulo.strip().lower()
            self.assertTrue(
                any(marca in baixo for marca in probe.BARRADO),
                f"{titulo!r} deveria ser reconhecido como desafio anti-bot")

    def test_o_titulo_normal_do_chat_NAO_e_desafio(self):
        for titulo in ("ChatGPT", "Gemini", "ChatGPT - Nova conversa"):
            baixo = titulo.strip().lower()
            self.assertFalse(
                any(marca in baixo for marca in probe.BARRADO),
                f"{titulo!r} nao pode ser confundido com desafio")


class TresEstadosTests(unittest.TestCase):
    """`None` nunca pode virar `False`: um refaz o login, o outro nao."""

    def test_sessao_valida_devolve_None_quando_nao_deu_para_perguntar(self):
        fonte = Path(probe.__file__).read_text(encoding="utf-8")
        trecho = fonte[fonte.index("def sessao_valida("):
                       fonte.index("def login(")]
        self.assertIn("bool | None", trecho)
        # o caminho do desafio e o do erro devolvem None, nunca False
        self.assertIn("return None", trecho)
        self.assertNotIn("return False\n    except", trecho)

    def test_o_padrao_NAO_e_headless(self):
        """Headless no chatgpt.com e o falso negativo inteiro."""
        import inspect
        assinatura = inspect.signature(probe.sessao_valida)
        self.assertIs(False, assinatura.parameters["headless"].default)

    def test_login_trata_None_diferente_de_deslogado(self):
        fonte = Path(probe.__file__).read_text(encoding="utf-8")
        trecho = fonte[fonte.index("def login("):]
        self.assertIn("valida is None", trecho)
        self.assertIn("NAO SEI", trecho)


class JanelaFechadaTests(unittest.TestCase):
    def test_fechar_a_janela_nao_e_erro(self):
        fonte = Path(probe.__file__).read_text(encoding="utf-8")
        trecho = fonte[fonte.index("def login("):]
        self.assertIn('"closed" not in str(exc).lower()', trecho)
        self.assertIn("janela fechada", trecho)

    def test_o_chat_montar_na_janela_ja_e_prova(self):
        """Reconferir depois foi o que sobrescreveu um login bem-sucedido."""
        fonte = Path(probe.__file__).read_text(encoding="utf-8")
        trecho = fonte[fonte.index("def login("):]
        self.assertLess(trecho.index("if visto:"),
                        trecho.index("valida = sessao_valida("))

    def test_login_devolve_bool(self):
        fonte = Path(probe.__file__).read_text(encoding="utf-8")
        self.assertIn("def login(provedor: str = \"chatgpt\", *, "
                      "espera: float = 300.0, log=print) -> bool:", fonte)

    def test_o_comando_sai_com_codigo_de_erro_quando_nao_loga(self):
        fonte = (Path(probe.__file__).resolve().parents[2]
                 / "main.py").read_text(encoding="utf-8")
        trecho = fonte[fonte.index("def cmd_llm("):]
        self.assertIn("return 0 if probe.login(args.provedor) else 1", trecho)


if __name__ == "__main__":
    unittest.main()
