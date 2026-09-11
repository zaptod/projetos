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

    def test_maximo_como_string_llm_numero_nao_quebra(self):
        """Robustez: se maximo vem como "llm 1" de estado corrupto, extrai o 1."""
        r = _reescritor(["llm um, cinematic, 35mm, grain"])
        vistos, estado = [], {"motivo": None, "n": 0}
        # Passar maximo como string "llm 1" (simulando estado corrupto)
        for nivel, prompt, _m in _com_reescrita(
                self.DEGRAUS, r, lambda: estado["motivo"], "llm 1",
                lambda *_a: None, "p01_cena_01"):
            vistos.append((nivel, prompt))
            estado["n"] += 1
            estado["motivo"] = "escudo" if estado["n"] <= 3 else None
        # Tem que ter extraido o numero 1 e rodado 1 volta do LLM
        self.assertIn("llm 1", [n for n, _p in vistos],
                      "maximo como 'llm 1' deveria rodar 1 volta do LLM")

    def test_maximo_como_string_numero_puro_funciona(self):
        """Se maximo e string "2", converte para int(2)."""
        r = _reescritor(["llm um, cinematic, 35mm, grain",
                         "llm dois, cinematic, 35mm, grain"])
        vistos, estado = [], {"motivo": None, "n": 0}
        # Passar maximo como string "2" (invés de int)
        for nivel, prompt, _m in _com_reescrita(
                self.DEGRAUS, r, lambda: estado["motivo"], "2",
                lambda *_a: None, "p01_cena_01"):
            vistos.append((nivel, prompt))
            estado["n"] += 1
            estado["motivo"] = "escudo" if estado["n"] <= 3 else None
        # Tem que ter rodado 2 voltas do LLM
        niveis = [n for n, _p in vistos]
        self.assertEqual(2, niveis.count("llm 1") + niveis.count("llm 2"),
                         "maximo como '2' deveria rodar 2 voltas")

    def test_escalada_vazia_nao_quebra(self):
        self.assertEqual([], self._correr([], _reescritor(), recusas=9))


class ThreadPropriaTests(unittest.TestCase):
    """O navegador do reescritor vive numa thread só dele (08/09/2026).

    O Playwright sync NÃO pode ser aninhado: a API sincrona roda sobre um loop
    asyncio POR THREAD, e só cabe um. O worker de imagens já está dentro do
    navegador do PicassoIA, então abrir o ChatGPT na mesma thread levantava
    `Playwright Sync API inside the asyncio loop` — e a reescrita por LLM
    nunca chegou a acontecer numa corrida de verdade. O sintoma era invisível
    porque a mensagem saía por `print`, que ninguém guardava; parecia que o
    reescritor estava trabalhando e ele caía direto no mecânico.

    Estes testes olham a THREAD, que é o que a correção mudou. Os outros deste
    arquivo usam `ReescritorFalso`, que troca `_garantir` inteiro — eles nunca
    passariam por aqui, e é por isso que passavam com o defeito no lugar.
    """

    def _preparar(self):
        import contextlib
        import threading
        from contos.llm import cliente as mod

        visto = {}

        class _Cliente:
            def abrir(self, novo_chat=True):
                visto["abriu"] = threading.get_ident()

            def perguntar(self, pedido, timeout=None):
                visto["perguntou"] = threading.get_ident()
                return "a woman in a kitchen, warm light, cinematic"

        @contextlib.contextmanager
        def _falso(provedor, headless=False, ajustes=None, log=None):
            visto["entrou"] = threading.get_ident()
            try:
                yield _Cliente()
            finally:
                visto["saiu"] = threading.get_ident()

        original = mod.abrir_cliente
        mod.abrir_cliente = _falso
        self.addCleanup(setattr, mod, "abrir_cliente", original)
        return visto, threading.get_ident()

    def test_o_navegador_nao_abre_na_thread_de_quem_chamou(self):
        visto, minha = self._preparar()
        r = Reescritor(log=lambda *_a: None)
        self.addCleanup(r.fechar)
        r.reescrever(PROMPT, "conteudo bloqueado")
        self.assertIn("entrou", visto, "o cliente nao chegou a abrir")
        self.assertNotEqual(visto["entrou"], minha,
                            "abriu na mesma thread: o Playwright quebraria")

    def test_abrir_e_perguntar_na_MESMA_thread(self):
        """Trocar de thread no meio quebraria igual a aninhar."""
        visto, _minha = self._preparar()
        r = Reescritor(log=lambda *_a: None)
        self.addCleanup(r.fechar)
        r.reescrever(PROMPT, "conteudo bloqueado")
        r.reescrever(PROMPT, "conteudo bloqueado", primeira=False)
        self.assertEqual(visto["abriu"], visto["entrou"])
        self.assertEqual(visto["perguntou"], visto["entrou"])

    def test_fechar_na_mesma_thread_e_sem_travar(self):
        # `_fechar_pilha` chamado de dentro da thread com um executor de UMA
        # vaga seria um deadlock — por isso existe `_fechar_na_thread`.
        visto, _minha = self._preparar()
        r = Reescritor(log=lambda *_a: None)
        r.reescrever(PROMPT, "conteudo bloqueado")
        r.fechar()
        self.assertEqual(visto["saiu"], visto["entrou"])
        self.assertIsNone(r._executor, "o executor tinha que ter sido desligado")
        self.assertIsNone(r._cliente)

    def test_llm_que_nao_abre_desiste_e_nao_tenta_de_novo(self):
        import contextlib
        from contos.llm import cliente as mod

        tentativas = []

        @contextlib.contextmanager
        def _explode(*_a, **_kw):
            tentativas.append(1)
            raise RuntimeError("Playwright Sync API inside the asyncio loop")
            yield  # pragma: no cover

        original = mod.abrir_cliente
        mod.abrir_cliente = _explode
        self.addCleanup(setattr, mod, "abrir_cliente", original)

        r = Reescritor(log=lambda *_a: None)
        self.addCleanup(r.fechar)
        self.assertIsNone(r.reescrever(PROMPT, "bloqueado"))
        self.assertIsNone(r.reescrever(PROMPT, "bloqueado"))
        self.assertEqual(len(tentativas), 1,
                         "navegador morto nao se tenta duas vezes por cena")


if __name__ == "__main__":
    unittest.main()
