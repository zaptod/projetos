# -*- coding: utf-8 -*-
"""Contratos do reescritor de prompt bloqueado (o LLM conserta a cena).

Pedido do Adrian em 31/08/2026, depois do segundo bloqueio: "quero que o
programa consiga pegar o que deu erro, re gerar o chat gpt ou algo assim e
colar o novo".

O que este arquivo trava:

1. LIMPEZA. A resposta de um chat vira PROMPT PURO. Qualquer "Claro! Aqui
   esta:" que passasse iria direto para o campo do PicassoIA e viraria texto
   desenhado dentro da imagem.
2. ORDEM DA ESCALADA. Original -> LLM -> LLM de novo -> mecanico. O LLM so
   entra DEPOIS de uma recusa de verdade, e o mecanico continua no fim como
   rede para quando o navegador nao abrir.
3. NUNCA DERRUBA. LLM sem login, sem resposta ou repetindo o mesmo texto nao
   pode interromper a geracao das outras cenas.

Rode de dentro de historias/:
    python -m unittest tests.test_reescritor_regressions -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from contos.imagens.reescritor import Reescritor, limpar          # noqa: E402
from contos.imagens.worker import _com_reescrita                  # noqa: E402

PROMPT = ("a woman standing in a dark kitchen, cinematic photography, "
          "shot on 35mm film, film grain")


class LimparTests(unittest.TestCase):
    def test_resposta_limpa_passa_inteira(self):
        self.assertEqual(PROMPT, limpar(PROMPT))

    def test_tira_o_preambulo_de_chat(self):
        for bruto in (f"Claro! Aqui esta: {PROMPT}",
                      f"Aqui vai o novo prompt:\n{PROMPT}",
                      f"Prompt: {PROMPT}",
                      f'"{PROMPT}"',
                      f"```\n{PROMPT}\n```"):
            self.assertEqual(PROMPT, limpar(bruto), bruto[:40])

    def test_varias_linhas_fica_com_a_que_parece_prompt(self):
        bruto = (f"Entendi o problema!\n\n{PROMPT}\n\n"
                 "Quer que eu ajuste mais alguma coisa?")
        self.assertEqual(PROMPT, limpar(bruto))

    def test_resposta_inutil_vira_vazio(self):
        for bruto in ("", "   ", "Claro!", "Nao posso ajudar com isso.",
                      "ok", "```\n```"):
            self.assertEqual("", limpar(bruto), repr(bruto))


class FalsoLLM:
    """Um `ClienteLLM` com o minimo que o reescritor usa."""

    def __init__(self, respostas=None, explode=False):
        self.respostas = list(respostas or [])
        self.explode = explode
        self.perguntas = []

    def abrir(self, novo_chat=True):
        pass

    def perguntar(self, pedido, timeout=None):
        self.perguntas.append(pedido)
        if self.explode:
            raise RuntimeError("o site nao respondeu")
        return self.respostas.pop(0) if self.respostas else ""


class ReescritorFalso(Reescritor):
    """Reescritor com a sessao ja resolvida: nenhum browser nos testes."""

    def __init__(self, llm, **kw):
        super().__init__(**kw)
        self._falso = llm

    def _garantir(self):
        if self._desistiu:
            return None
        self._cliente = self._falso
        return self._cliente

    def _fechar_pilha(self):
        self._cliente = None


def _reescritor(respostas=None, explode=False, **kw):
    return ReescritorFalso(FalsoLLM(respostas, explode), log=lambda *_a: None,
                           **kw)


class ReescreverTests(unittest.TestCase):
    def test_devolve_o_prompt_reescrito(self):
        novo = "an empty dark kitchen, a fallen glass, cinematic, 35mm"
        r = _reescritor([f"Aqui esta:\n{novo}"])
        self.assertEqual(novo, r.reescrever(PROMPT, "escudo", primeira=True))
        self.assertEqual(1, r.reescritas)

    def test_o_pedido_leva_o_prompt_e_o_motivo(self):
        r = _reescritor(["an empty kitchen at night, cinematic, 35mm, grain"])
        r.reescrever(PROMPT, "conteudo bloqueado")
        pedido = r._falso.perguntas[0]
        self.assertIn(PROMPT, pedido)
        self.assertIn("conteudo bloqueado", pedido)
        self.assertIn("APENAS", pedido, "sem isso a resposta vem com conversa")

    def test_a_segunda_volta_pede_mais_conservador(self):
        r = _reescritor(["an empty kitchen, wide shot, cinematic, 35mm grain"])
        r.reescrever(PROMPT, "escudo", primeira=False)
        self.assertIn("conservador", r._falso.perguntas[0])

    def test_resposta_igual_ao_original_nao_conta(self):
        r = _reescritor([PROMPT])
        self.assertIsNone(r.reescrever(PROMPT, "escudo"))
        self.assertEqual(0, r.reescritas)

    def test_resposta_vazia_nao_derruba(self):
        r = _reescritor(["Desculpe."])
        self.assertIsNone(r.reescrever(PROMPT, "escudo"))

    def test_llm_que_explode_desiste_de_vez(self):
        """Se o site caiu, nao adianta tentar a cada cena."""
        r = _reescritor(explode=True)
        self.assertIsNone(r.reescrever(PROMPT, "escudo"))
        self.assertTrue(r._desistiu)
        self.assertIsNone(r.reescrever(PROMPT, "escudo"))
        self.assertEqual(1, len(r._falso.perguntas), "tentou de novo a toa")


class EscaladaTests(unittest.TestCase):
    """A ordem importa: o LLM sabe o que a cena conta, o mecanico nao."""

    DEGRAUS = [(0, "original", []), (1, "suave1", ["sangue"]),
               (2, "suave2", ["faca"]), (3, "ambiente", ["so o ambiente"])]

    @staticmethod
    def _correr(degraus, reescritor, recusas):
        """Roda a escalada simulando recusa nas `recusas` primeiras voltas."""
        vistos, estado = [], {"motivo": None, "n": 0}
        for nivel, prompt, _m in _com_reescrita(
                degraus, reescritor, lambda: estado["motivo"], 2,
                lambda *_a: None, "p01_cena_01"):
            vistos.append((nivel, prompt))
            estado["n"] += 1
            estado["motivo"] = "escudo" if estado["n"] <= recusas else None
        return vistos

    def test_o_llm_entra_depois_da_recusa_e_antes_do_mecanico(self):
        r = _reescritor(["llm um, cinematic, 35mm, grain",
                         "llm dois, cinematic, 35mm, grain"])
        vistos = self._correr(self.DEGRAUS, r, recusas=9)
        self.assertEqual(
            [0, "llm 1", "llm 2", 1, 2, 3], [n for n, _p in vistos],
            "a ordem tem que ser original -> LLM -> mecanico")

    def test_sem_recusa_o_llm_nunca_e_chamado(self):
        """O primeiro prompt passou: abrir o Chrome ali seria custo puro."""
        r = _reescritor(["nao devia ser usado, cinematic, 35mm, grain"])
        vistos = self._correr(self.DEGRAUS, r, recusas=0)
        self.assertEqual([0], [n for n, _p in vistos][:1])
        self.assertEqual(0, r.reescritas)
        self.assertEqual([], r._falso.perguntas)

    def test_sem_reescritor_a_escalada_continua_mecanica(self):
        vistos = self._correr(self.DEGRAUS, None, recusas=9)
        self.assertEqual([0, 1, 2, 3], [n for n, _p in vistos])

    def test_llm_indisponivel_cai_no_mecanico(self):
        r = _reescritor(explode=True)
        vistos = self._correr(self.DEGRAUS, r, recusas=9)
        self.assertEqual([0, 1, 2, 3], [n for n, _p in vistos])

    def test_a_segunda_reescrita_parte_da_primeira(self):
        primeiro = "llm um, cinematic, 35mm, grain"
        r = _reescritor([primeiro, "llm dois, cinematic, 35mm, grain"])
        self._correr(self.DEGRAUS, r, recusas=9)
        self.assertIn(primeiro, r._falso.perguntas[1],
                      "a 2a volta tem que partir do que ja foi tentado")

    def test_escalada_vazia_nao_quebra(self):
        self.assertEqual([], self._correr([], _reescritor(), recusas=9))


if __name__ == "__main__":
    unittest.main()
