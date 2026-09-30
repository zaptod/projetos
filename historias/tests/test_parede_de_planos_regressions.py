# -*- coding: utf-8 -*-
"""A parede de planos do PicassoIA reabre o perfil uma vez (17/09/2026).

Na madrugada, uma conta ilimitada abriu como "FREE -> PRO+", o botao de gerar
virou "Assine para Gerar", e o cliente fechava o aviso e esperava uma imagem
que nunca saia. Reabrir o perfil resolveu. Nada aqui abre navegador.

Rode de dentro de historias/:
    python -m unittest tests.test_parede_de_planos_regressions -v
"""
from __future__ import annotations

import unittest

from builds.identity import picasso_client as PC                   # noqa: E402
from contos.imagens import worker                                  # noqa: E402


class OCliente(unittest.TestCase):

    def _cliente(self, assine_visivel):
        class Alvo:
            def count(self):
                return 1 if assine_visivel is not None else 0

            @property
            def first(self):
                return self

            def is_visible(self):
                return bool(assine_visivel)

        class Pagina:
            def locator(self, seletor):
                assert seletor == PC.SEM_PLANO
                return Alvo()

        cliente = PC.PicassoClient.__new__(PC.PicassoClient)
        cliente.page = Pagina()
        return cliente

    def test_assine_para_gerar_visivel_levanta(self):
        with self.assertRaises(PC.ParedeDePlanos) as erro:
            self._cliente(True)._conferir_plano("Planos e Creditos ...")
        self.assertIn("sessao FREE", str(erro.exception))
        self.assertIn("Planos e Creditos", str(erro.exception))

    def test_sem_o_botao_segue(self):
        self._cliente(None)._conferir_plano("promocao qualquer")
        self._cliente(False)._conferir_plano("")

    def test_e_uma_falha_de_geracao(self):
        # Quem ainda nao conhece a excecao nova a trata como falha comum.
        self.assertTrue(issubclass(PC.ParedeDePlanos, PC.GeracaoFalhou))


class OFechador(unittest.TestCase):
    """Pop-up de paywall de 17/09/2026: o X e
    `<svg class="lucide lucide-x size-5" aria-hidden="true">`. Conferido num
    Chromium headless (sem perfil, sem rede): os seletores pegam o BOTAO do
    dialogo em tres formatos, e nunca o X de limpar o prompt."""

    def test_especificos_antes_do_generico(self):
        generico = PC.FECHAR_MODAL.index("button:has(svg.lucide-x)")
        self.assertEqual(len(PC.FECHAR_MODAL) - 1, generico)
        for seletor in ("[role='dialog'] [role='button']:has(svg.lucide-x)",
                        "[data-slot='dialog-content'] button:has(svg.lucide-x)"):
            self.assertLess(PC.FECHAR_MODAL.index(seletor), generico)

    def test_o_clique_vai_no_botao_e_nao_no_svg(self):
        for seletor in PC.FECHAR_MODAL:
            if "lucide-x" in seletor:
                self.assertIn(":has(svg.lucide-x)", seletor)


class OWorker(unittest.TestCase):

    def setUp(self):
        self.chamadas = []
        self.registros = []
        reais = (worker._gerar, worker._registrar_parede)
        self.addCleanup(setattr, worker, "_gerar", reais[0])
        self.addCleanup(setattr, worker, "_registrar_parede", reais[1])
        worker._registrar_parede = (
            lambda hid, exc: self.registros.append((hid, str(exc))))
        # UMA reabertura, como era ate 30/09/2026: desde o lote o numero vem
        # do config (`reaberturas_na_parede`), e o que estes testes guardam e
        # a regra "reabre e, se voltar, para como infraestrutura" — o numero
        # do config tem teste proprio (test_lote_semanal_regressions).
        from contos.imagens import fila as _fila
        self.addCleanup(setattr, _fila, "carregar_config",
                        _fila.carregar_config)
        _fila.carregar_config = lambda: {"reaberturas_na_parede": 1}

    def _roteiro(self, *respostas):
        fila = list(respostas)

        def falso(historia_id, **k):
            self.chamadas.append(historia_id)
            resposta = fila.pop(0)
            if isinstance(resposta, Exception):
                raise resposta
            return resposta

        worker._gerar = falso

    def test_parede_uma_vez_reabre_e_segue(self):
        feito = {"geradas": 14, "faltam": 0, "erros": [], "recusadas": []}
        self._roteiro(PC.ParedeDePlanos("parede"), feito)
        self.assertEqual(feito, worker.gerar("historia_00001",
                                             log=lambda *_a: None))
        self.assertEqual(2, len(self.chamadas))
        self.assertEqual([], self.registros)

    def test_parede_duas_vezes_para_como_infraestrutura(self):
        self._roteiro(PC.ParedeDePlanos("parede 1"),
                      PC.ParedeDePlanos("parede 2"))
        with self.assertRaises(worker.NaoRodou) as erro:
            worker.gerar("historia_00001", log=lambda *_a: None)
        self.assertIn("de novo", str(erro.exception))
        self.assertEqual(2, len(self.chamadas))
        self.assertEqual([("historia_00001", "parede 2")], self.registros)

    def test_sem_parede_uma_passada_so(self):
        self._roteiro({"geradas": 1, "faltam": 0, "erros": [],
                       "recusadas": []})
        worker.gerar("historia_00001", log=lambda *_a: None)
        self.assertEqual(1, len(self.chamadas))

    def test_outra_falha_nao_reabre(self):
        self._roteiro(RuntimeError("outra coisa"))
        with self.assertRaises(RuntimeError):
            worker.gerar("historia_00001", log=lambda *_a: None)
        self.assertEqual(1, len(self.chamadas))


if __name__ == "__main__":
    unittest.main()
