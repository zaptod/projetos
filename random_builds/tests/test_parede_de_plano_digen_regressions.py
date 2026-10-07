# -*- coding: utf-8 -*-
"""A parede de PLANO do Digen: pede upgrade, nao e propaganda.

Por que existe (29/09/2026, 17:36). Numa prova ao vivo o `DigenClient` enviou
uma imagem num Space novo (Real Motion 3.5, 8 s, 480P, conta no plano Free,
chip "Free, Meme 149, Pro Meme 0"). O site respondeu "Creating Task..." e
depois o modal

    Upgrade your plan to unlock this model
    Meme 6,000 Meme / mo ... $4.99 Upgrade Now (Save $5)

com a MESMA estrutura da propaganda de 28/09 (`[role=dialog]
[data-slot=dialog-content]`). O guarda do cliente o FECHOU no ESC como se
fosse propaganda, e `ERRO_GERACAO` nao conhece o texto: o payoff das builds
ficaria olhando a espera (render_timeout 1800 s) de um video que nunca foi
criado — e, no fim, reenviaria o mesmo pedido para a mesma parede.

O que este arquivo trava:
1. O texto da parede de plano e reconhecido pela FRASE (deixis: "this
   model"), com borda de palavra; "Upgrade Now", preco e a promo "20% OFF"
   nao casam — sao iguais nas duas paredes.
2. `tirar_parede_da_frente` diante dela LEVANTA `SemPlano` com o texto lido,
   sem clicar no X e sem ESC; a propaganda continua sendo fechada.
3. O guarda do Playwright nao engole: anota no cliente (excecao levantada
   dentro do handler se perde numa task do driver).
4. A espera acusa na hora, e o envio confere antes de clicar em gerar.
5. O worker falha o job SEM nova tentativa, pausa o Digen com prazo, nao
   pega o proximo job e deixa `erro` no diario (painel e apuracao leem).
"""
from __future__ import annotations

import contextlib
import inspect
import os
import unittest
from pathlib import Path
from unittest import mock

import pytest

from builds.identity import client, selectors

# Decisao do Adrian no Grimorio (builds/digen-parede, 05/10/2026): deixar em
# espera. O conserto so vale quando o payoff em video do Digen for religado
# (random_builds/config/identity.json: payoff_video=false); ate la, pulados.
pytestmark = pytest.mark.skip(
    reason="em espera: builds/digen-parede (payoff_video do Digen desligado)")


def load_tests(loader, tests, pattern):
    # O testar.py roda por unittest discover, que ignora o pytestmark.
    return unittest.TestSuite()

# O texto lido na tela em 29/09/2026 17:36 (ias/fichas/digen.json).
PAREDE_REAL = (
    "Upgrade your plan to unlock this model Meme 6,000 Meme / mo Pro Meme "
    "2,200 Pro Meme / mo Up to 300 videos, industry-lowest pricing Daily "
    "login +200 Meme NEW Real Motion 3.5 Access Outstanding Generation "
    "Quality NEW MiniMax H3, Now Live Get access at the web's lowest price "
    "NEW Nano Banana 2 Lite Unlimited Unlimited Image Generation NEW Gemini "
    "Omni Flash Limited Offer Access to Seedance 2.0 · Veo 3.1 · Grok $4.99 "
    "Upgrade Now Save $5 View all plans & details")

# A propaganda de 28/09 (fecha pelo X) e o texto do duble antigo.
PROMO = ("20% OFF Real Motion 3.5 Fast Upgrade Now $4.99 Save $5 "
         "View all plans & details")


class OTextoDaParede(unittest.TestCase):

    def test_a_parede_real_e_de_plano(self):
        self.assertTrue(client.e_parede_de_plano(PAREDE_REAL))
        self.assertTrue(client.e_parede_de_plano(
            "Upgrade your plan to unlock this model"))
        self.assertTrue(client.e_parede_de_plano(
            "UPGRADE YOUR PLAN TO\nUNLOCK THIS MODEL"))

    def test_a_mesma_familia(self):
        for texto in ("This model requires a paid plan",
                      "Upgrade your plan to use Real Motion 3.5",
                      "Your current plan does not support this model",
                      "Subscribe to unlock this feature",
                      "This model is not available on the free plan"):
            with self.subTest(texto=texto):
                self.assertTrue(client.e_parede_de_plano(texto))

    def test_propaganda_e_preco_nao_casam(self):
        for texto in (PROMO, "Upgrade Now Close", "Upgrade", "$4.99",
                      "Upgrade your plan and save 20%",
                      "Available for Pro members",
                      "View all plans & details", "", None):
            with self.subTest(texto=texto):
                self.assertFalse(client.e_parede_de_plano(texto))

    def test_borda_de_palavra(self):
        self.assertFalse(client.e_parede_de_plano("Unlock this modeling pack"))
        self.assertFalse(client.e_parede_de_plano(
            "reupgrade your plan to unlock this modelo"))
        self.assertFalse(client.e_parede_de_plano("Upgrade your planet"))

    def test_sem_plano_nao_e_retomada(self):
        # `EsperaEstourou` e "retome o mesmo espaco depois"; a parede de plano
        # nao cria video nenhum, entao nao ha o que retomar.
        exc = client.SemPlano(PAREDE_REAL)
        self.assertIsInstance(exc, client.GeracaoFalhou)
        self.assertNotIsInstance(exc, client.EsperaEstourou)
        self.assertFalse(exc.retentavel)
        self.assertEqual(PAREDE_REAL, exc.texto)
        self.assertIn("Upgrade your plan to unlock this model", str(exc))


# ---------------------------------------------------------------- dubles
class _Nada:
    def count(self):
        return 0


class _Botao:
    def __init__(self, pagina):
        self.pagina, self.cliques = pagina, []

    def count(self):
        return 1

    @property
    def first(self):
        return self

    def is_visible(self):
        return True

    def click(self, **kw):
        self.cliques.append(kw)
        self.pagina.aberta = False


class _Parede:
    def __init__(self, pagina):
        self.pagina = pagina

    def count(self):
        return 1 if self.pagina.aberta else 0

    @property
    def first(self):
        return self

    def is_visible(self):
        return self.pagina.aberta

    def inner_text(self, timeout=None):
        return self.pagina.texto

    def locator(self, seletor):
        if seletor == "button[data-slot='dialog-close']":
            return self.pagina.x
        return _Nada()


class _Teclado:
    def __init__(self, pagina):
        self.pagina, self.teclas = pagina, []

    def press(self, tecla):
        self.teclas.append(tecla)
        if tecla == "Escape":
            self.pagina.aberta = False


class _Pagina:
    url = "https://digen.ai/en/space/2695372"

    def __init__(self, texto=PAREDE_REAL):
        self.aberta, self.texto = True, texto
        self.x = _Botao(self)
        self.parede = _Parede(self)
        self.keyboard = _Teclado(self)
        self.guardas = []

    def locator(self, seletor):
        return self.parede if seletor == selectors.PAREDE else _Nada()

    def add_locator_handler(self, locator, handler, **kw):
        self.guardas.append((locator, handler))

    def is_closed(self):
        return False

    def evaluate(self, _codigo):
        return 1


class _SemTempo(unittest.TestCase):
    def setUp(self):
        for alvo in ("sleep",):
            p = mock.patch.object(client.time, alvo)
            p.start()
            self.addCleanup(p.stop)
        # Os seletores de texto (get_by_text) nao existem no duble; o que se
        # testa aqui e o modal.
        p = mock.patch.object(client.selectors, "encontrar", return_value=None)
        p.start()
        self.addCleanup(p.stop)


class ADiantedaParede(_SemTempo):

    def test_parede_de_plano_levanta_e_nao_fecha(self):
        pagina = _Pagina()
        with self.assertRaises(client.SemPlano) as erro:
            client.tirar_parede_da_frente(pagina, espera=0.1)
        self.assertIn("unlock this model", erro.exception.texto)
        self.assertTrue(pagina.aberta, "a parede de plano foi fechada")
        self.assertEqual([], pagina.x.cliques)
        self.assertEqual([], pagina.keyboard.teclas, "ESC usado na parede de plano")

    def test_propaganda_continua_sendo_fechada(self):
        pagina = _Pagina(texto=PROMO)
        self.assertEqual(PROMO, client.tirar_parede_da_frente(pagina, espera=0.1))
        self.assertFalse(pagina.aberta)
        self.assertEqual(1, len(pagina.x.cliques))

    def test_o_guarda_anota_no_cliente_e_nao_fecha(self):
        pagina = _Pagina()
        cliente = client.DigenClient(None, pagina, {})
        self.assertIsNone(cliente.sem_plano)
        _locator, guarda = pagina.guardas[0]
        guarda(_locator)             # nao levanta: dentro do driver se perderia
        self.assertIsInstance(cliente.sem_plano, client.SemPlano)
        self.assertTrue(pagina.aberta)
        self.assertEqual([], pagina.keyboard.teclas)
        with self.assertRaises(client.SemPlano):
            cliente._conferir_plano()

    def test_a_espera_acusa_na_hora(self):
        pagina = _Pagina()
        cliente = client.DigenClient(None, pagina, {"render_timeout": 1800,
                                                    "poll_interval": 5})
        with self.assertRaises(client.SemPlano):
            cliente.wait_for_render(antes=[])
        self.assertTrue(pagina.aberta)
        self.assertEqual([], pagina.keyboard.teclas)
        client.selectors.encontrar.assert_not_called()   # nem olhou o GERANDO

    def test_aviso_de_plano_fora_do_modal(self):
        # Um toast/cartao com a frase, sem o modal: o texto decide.
        pagina = _Pagina()
        pagina.aberta = False
        cliente = client.DigenClient(None, pagina, {})
        aviso = mock.Mock()
        aviso.inner_text.return_value = "Upgrade your plan to unlock this model"
        client.selectors.encontrar.return_value = aviso
        with self.assertRaises(client.SemPlano):
            cliente._conferir_plano()
        aviso.inner_text.return_value = "Upgrade your plan and save 20%"
        cliente.sem_plano = None
        cliente._conferir_plano()          # propaganda: nao levanta

    def test_o_envio_confere_antes_de_clicar_e_depois(self):
        fonte = inspect.getsource(client.DigenClient.submit_prompt)
        clique = fonte.index("botao.click()")
        self.assertLess(fonte.index("self._conferir_plano()"), clique)
        # E no laco que espera a URL do espaco (a parede veio depois do
        # "Creating Task...").
        self.assertIn("self._conferir_plano()", fonte[clique:])


class OWorker(unittest.TestCase):
    """O job falha SEM nova tentativa e a passada para."""

    def _passada(self, erro_do_processar, cliente=None):
        from builds.identity import worker
        jobs = [{"job_id": "generation_00085#character_weapon",
                 "generation_id": "generation_00085",
                 "slot": "character_weapon", "attempts": 1},
                {"job_id": "generation_00090#character_weapon",
                 "generation_id": "generation_00090",
                 "slot": "character_weapon", "attempts": 0}]
        reivindicados, diario = [], []

        def claim(*a, **k):
            if not jobs:
                return None
            reivindicados.append(jobs[0]["job_id"])
            return jobs.pop(0)

        if cliente is None:
            cliente = mock.Mock()
            cliente.sem_plano = None
        cliente.creditos.return_value = 149
        ajustes = {"payoff_video": True, "max_attempts": 3, "min_interval": 0,
                   "modelo": "Real Motion 3.5"}
        with mock.patch.object(worker.queue, "claim", side_effect=claim), \
                mock.patch.object(worker.queue, "falhar") as falhar, \
                mock.patch.object(worker.queue, "concluir"), \
                mock.patch.object(worker.history, "registrar"), \
                mock.patch.object(worker.config, "settings",
                                  return_value=ajustes), \
                mock.patch.object(worker.time, "sleep"), \
                mock.patch.object(worker, "pausa_humana"), \
                mock.patch.object(worker, "processar",
                                  side_effect=erro_do_processar), \
                mock.patch.object(worker, "contexto_persistente",
                                  side_effect=lambda **k:
                                  contextlib.nullcontext(object())), \
                mock.patch.object(worker, "pagina", return_value=object()), \
                mock.patch.object(worker, "ensure_logged_in"), \
                mock.patch.object(worker.provedores, "cliente",
                                  return_value=cliente), \
                mock.patch.object(worker.provedores, "seletores",
                                  return_value=None), \
                mock.patch.object(worker.controle, "pausado_para",
                                  return_value=False), \
                mock.patch.object(worker.controle, "parada_pedida",
                                  return_value=False), \
                mock.patch.object(worker.controle, "pausar") as pausar, \
                mock.patch("builds.travas.do_perfil",
                           return_value=f"teste_plano_{os.getpid()}"), \
                mock.patch("builds.atividade.registrar",
                           side_effect=lambda *a, **k: diario.append((a, k))):
            try:
                resultado = worker._passada("digen", False, True, False, None)
                levantou = None
            except Exception as exc:          # noqa: BLE001
                resultado, levantou = None, exc
        return {"resultado": resultado, "levantou": levantou,
                "reivindicados": reivindicados, "falhar": falhar,
                "pausar": pausar, "diario": diario}

    def test_sem_plano_falha_sem_nova_tentativa_e_para(self):
        feito = self._passada(client.SemPlano(PAREDE_REAL))
        self.assertIsInstance(feito["levantou"], client.SemPlano)
        # Um job so: o proximo bateria na mesma parede.
        self.assertEqual(["generation_00085#character_weapon"],
                         feito["reivindicados"])
        feito["falhar"].assert_called_once()
        args, kwargs = feito["falhar"].call_args
        self.assertEqual("generation_00085#character_weapon", args[0])
        self.assertEqual(0, kwargs.get("max_attempts"))
        self.assertIn("unlock this model", args[1])
        # Pausa do Digen COM prazo (volta sozinha se a conta ganhar plano).
        feito["pausar"].assert_called_once()
        p_args, p_kwargs = feito["pausar"].call_args
        self.assertEqual("digen", p_args[0] if p_args else p_kwargs.get("alvo"))
        self.assertTrue(p_kwargs.get("minutos"))
        self.assertIn("plano", p_kwargs.get("motivo", ""))

    def test_o_diario_termina_em_erro_com_o_texto(self):
        feito = self._passada(client.SemPlano(PAREDE_REAL))
        ultimo_args, ultimo_kw = feito["diario"][-1]
        self.assertEqual("digen", ultimo_args[0])
        self.assertEqual("erro", ultimo_args[1])
        self.assertIn("SemPlano", ultimo_args[2])
        self.assertIn("unlock this model", ultimo_args[2])
        self.assertEqual("identity.sem_plano", ultimo_kw.get("etapa"))
        # Sem `ref`: a apuracao le e explica, mas nao abre CONSERTO de codigo
        # (a parede e da conta, nao do fonte).
        self.assertFalse(ultimo_kw.get("ref"))

    def test_timeout_do_driver_com_a_parede_anotada_vira_sem_plano(self):
        # O guarda viu a parede no meio de um clique; o clique estourou o
        # tempo do Playwright. O que vale e a parede, nao o timeout.
        cliente = mock.Mock()
        cliente.sem_plano = client.SemPlano(PAREDE_REAL)
        feito = self._passada(TimeoutError("Locator.click: Timeout 30000ms"),
                              cliente=cliente)
        self.assertIsInstance(feito["levantou"], client.SemPlano)
        self.assertEqual(0, feito["falhar"].call_args.kwargs.get("max_attempts"))
        self.assertEqual(1, len(feito["reivindicados"]))

    def test_erro_comum_continua_retentavel(self):
        feito = self._passada(client.GeracaoFalhou("Generation failed"))
        self.assertIsNone(feito["levantou"])
        self.assertEqual(2, len(feito["reivindicados"]))
        for chamada in feito["falhar"].call_args_list:
            self.assertEqual(3, chamada.args[2] if len(chamada.args) > 2
                             else chamada.kwargs.get("max_attempts"))
        feito["pausar"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
