# -*- coding: utf-8 -*-
"""O CARD "ALTA PROCURA" DO GROK NO LUGAR DA RESPOSTA (29/09/2026).

17:30 e 17:44, dois pedidos de imagem ao Grok pelo carteiro da Vila: no lugar
da resposta veio o card "Alta procura — Por favor, tente novamente em breve,
ou atualize para um acesso com maior prioridade" (botao "Aprimorar") e, no
topo, "Grok is experiencing issues...". A espera leu "0 chars" por 420 s,
duas vezes (outputs/carteiro.txt; tela em
historias/outputs/_logs/llm_calado/grok_20260929_174936.png), e so no fim o
texto da pagina inteira virou o motivo.

Agora `ClienteLLM.esperar_resposta` le o turno do assistente que responde ao
nosso MENOS a resposta de verdade e o raciocinio (`aviso_do_site`), casa os
textos de `seletores.GROK["indisponivel"]` com borda de palavra e sai em
segundos com `SiteIndisponivel` (categoria `indisponivel`), sem clicar em
nada. Uma resposta que so CITA "alta procura" nao sobra do turno — e se o DOM
mudar e sobrar, o teto de `AVISO_MAXIMO` (400) segura: card e curto.

O JS em si foi rodado num Chrome de verdade sobre a estrutura real das bolhas
do Grok (user-message / assistant-message / thinking-container, medida em
29/09): card -> casa; resposta longa ou curta citando "alta procura" -> nao.

Dubles: a pagina responde ao script pelo que ele e; nenhum navegador.
"""
from __future__ import annotations

import types
import unittest

from contos.llm import cliente as llm_cliente                      # noqa: E402
from contos.llm import seletores                                   # noqa: E402

CARD = ("Alta procura\nPor favor, tente novamente em breve, ou atualize para um "
        "acesso com maior prioridade\nAprimorar")
LONGA = ("Gatos laranja estão em alta procura nas redes, e isso vale para fotos "
         "realistas de manhã. " * 12)


def _aviso(resto="", pagina=False, turno=True):
    return {"ancorado": True, "turno": turno, "resto": resto, "pagina": pagina}


class _Pagina:
    """`evaluate` responde pelo script: o aviso (um estado por volta), as
    imagens da resposta (nenhuma), a foto de antes do envio e o texto."""

    def __init__(self, avisos, texto=""):
        self.avisos = iter(avisos)
        self.ultimo = _aviso()
        self.texto = texto
        self.voltas_aviso = 0
        self.cliques = 0

    def evaluate(self, script, argumento=None):
        script = str(script)
        if "resto" in script:
            self.voltas_aviso += 1
            self.ultimo = next(self.avisos, self.ultimo)
            return self.ultimo
        if "out.push(im.currentSrc)" in script:
            return []
        if "naturalWidth" in script:
            return {"ancorado": True, "turno": "gato", "resposta": True, "gerando": False,
                    "fora": 0, "imagens": []}
        if argumento is not None:
            return {"texto": self.texto, "ancorado": True}
        return None

    def click(self, *_a, **_k):                                # nunca: "Aprimorar"
        self.cliques += 1


class _Base(unittest.TestCase):
    provedor = "grok"

    def setUp(self):
        self.agora = [0.0]

        def monotonic():
            self.agora[0] += 1.0
            return self.agora[0]

        falso = types.SimpleNamespace(monotonic=monotonic, sleep=lambda _s: None,
                                      strftime=__import__("time").strftime)
        self.addCleanup(setattr, llm_cliente, "time", llm_cliente.time)
        llm_cliente.time = falso
        # o botao de parar LIGADO, como a ficha anotou no card de 17:30
        self.parar = [True]
        self.addCleanup(setattr, seletores, "encontrar", seletores.encontrar)
        seletores.encontrar = (lambda *a, **k: object() if self.parar[0] else None)
        self.logs = []
        self.diagnosticos = []

    def _cliente(self, pagina, provedor=None):
        c = llm_cliente.ClienteLLM(provedor or self.provedor, None, pagina,
                                   log=self.logs.append)
        c._envio_devolvido = lambda: False
        c._envio_truncado = lambda: False
        c._responder_agora = lambda: False
        c._diagnosticar_calado = lambda: self.diagnosticos.append(1)
        c._srcs_antes_do_envio = set()
        return c


class CardNoLugarDaResposta(_Base):
    def test_card_sai_em_segundos_como_indisponivel(self):
        # 3 voltas sem nada, e o card para sempre (o de 29/09 nao sumia)
        pagina = _Pagina([_aviso()] * 3 + [_aviso(CARD, pagina=True)] * 500)
        c = self._cliente(pagina)
        with self.assertRaises(llm_cliente.SiteIndisponivel) as caso:
            c.esperar_resposta(timeout=420, estabilidade=2.5)
        self.assertLess(self.agora[0], 30, "gastou o prazo em vez de sair")
        exc = caso.exception
        self.assertIsInstance(exc, llm_cliente.LLMFalhou)
        self.assertEqual("indisponivel", exc.categoria)
        self.assertTrue(exc.pausa_rodizio)
        self.assertIn("Alta procura", str(exc))
        self.assertIn("aviso no topo", str(exc))
        self.assertEqual(0, pagina.cliques, "nunca clica em 'Aprimorar'")
        self.assertEqual([1], self.diagnosticos, "a tela vai para _logs/llm_calado")
        self.assertTrue(any("aviso no lugar da resposta" in m for m in self.logs), self.logs)

    def test_card_sem_o_toast_tambem_sai(self):
        pagina = _Pagina([_aviso(CARD)] * 500)
        c = self._cliente(pagina)
        with self.assertRaises(llm_cliente.SiteIndisponivel) as caso:
            c.esperar_resposta(timeout=420)
        self.assertNotIn("aviso no topo", str(caso.exception))
        self.assertLess(self.agora[0], 30)

    def test_um_quadro_so_nao_encerra(self):
        # o card piscou numa volta e a resposta veio: e resposta
        self.parar[0] = False
        pagina = _Pagina([_aviso(CARD), _aviso()] + [_aviso()] * 500,
                         texto="Aqui está o seu gato laranja, dormindo na almofada azul.")
        c = self._cliente(pagina)
        texto = c.esperar_resposta(timeout=420, estabilidade=2.5)
        self.assertIn("gato laranja", texto)

    def test_so_o_toast_no_topo_nao_encerra_e_avisa_uma_vez(self):
        pagina = _Pagina([_aviso(pagina=True)] * 500)
        c = self._cliente(pagina)
        with self.assertRaises(llm_cliente.LLMFalhou) as caso:
            c.esperar_resposta(timeout=60)
        self.assertNotIsInstance(caso.exception, llm_cliente.SiteIndisponivel)
        self.assertEqual(1, sum("avisa no topo" in m for m in self.logs), self.logs)


class RespostaQueCitaNaoDispara(_Base):
    def setUp(self):
        super().setUp()
        self.parar[0] = False

    def test_resposta_longa_que_cita_alta_procura(self):
        # se o DOM mudar e a resposta sobrar do turno, o teto de tamanho segura
        pagina = _Pagina([_aviso(LONGA)] * 500, texto=LONGA)
        c = self._cliente(pagina)
        texto = c.esperar_resposta(timeout=420, estabilidade=2.5)
        self.assertIn("alta procura", texto)
        self.assertGreater(len(" ".join(LONGA.split())), c.AVISO_MAXIMO)

    def test_resposta_curta_que_cita_e_subtraida_do_turno(self):
        # o JS tira a resposta de verdade do turno: sobra so o rotulo do raciocinio
        pagina = _Pagina([_aviso("")] * 500, texto="Sim, está em alta procura.")
        c = self._cliente(pagina)
        self.assertEqual("Sim, está em alta procura.", c.esperar_resposta(timeout=420))


class BordaDePalavra(_Base):
    def _casa(self, resto):
        return self._cliente(_Pagina([_aviso(resto)])).aviso_do_site()["texto"]

    def test_os_textos_medidos_casam(self):
        self.assertTrue(self._casa(CARD))
        self.assertTrue(self._casa("Por favor, tente novamente em breve, ou atualize "
                                   "para um acesso com maior prioridade"))
        self.assertTrue(self._casa("Grok is experiencing issues. We are working on "
                                   "restoring service as quickly as possible."))

    def test_sem_borda_nao_casa(self):
        self.assertFalse(self._casa("Produto de alta procurada"))
        self.assertFalse(self._casa("altaprocura"))
        self.assertFalse(self._casa("Trabalhou por 3s"))
        self.assertFalse(self._casa(""))


class CasoZero(_Base):
    def test_ia_sem_textos_medidos_nao_olha(self):
        # ChatGPT, Gemini e DeepSeek: nada muda neles
        for ia in ("chatgpt", "gemini", "deepseek"):
            self.assertFalse(seletores.do_provedor(ia).get("indisponivel"), ia)
            pagina = _Pagina([_aviso(CARD)] * 500, texto="Uma resposta comum e completa.")
            c = self._cliente(pagina, provedor=ia)
            self.parar[0] = False
            self.assertEqual({"texto": "", "pagina": False}, c.aviso_do_site())
            c.esperar_resposta(timeout=100, estabilidade=2)
            self.assertEqual(0, pagina.voltas_aviso, ia)

    def test_pagina_que_nao_responde_e_vazio(self):
        class _Quebrada:
            def evaluate(self, *_a):
                raise RuntimeError("pagina fechou")
        c = llm_cliente.ClienteLLM("grok", None, _Quebrada(), log=lambda *_a: None)
        self.assertEqual({"texto": "", "pagina": False}, c.aviso_do_site())

    def test_sem_turno_do_assistente_nao_ha_aviso(self):
        c = self._cliente(_Pagina([_aviso(CARD, turno=False) | {"resto": ""}]))
        self.assertEqual("", c.aviso_do_site()["texto"])

    def test_o_grok_tem_os_seletores(self):
        s = seletores.do_provedor("grok")
        self.assertIn("div[data-testid='assistant-message']", s["turno_assistente"])
        self.assertTrue(s["indisponivel_pagina"])
        # o raciocinio e a resposta saem do turno antes de casar
        self.assertIn("div.thinking-container", s["raciocinio"])


if __name__ == "__main__":
    unittest.main()
