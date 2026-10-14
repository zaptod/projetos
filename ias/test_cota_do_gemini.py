# -*- coding: utf-8 -*-
"""IAS-1 (auditoria de 11/10/2026): a cota de IMAGEM do Gemini nao era
reconhecida como limite.

Sem cota, o Gemini responde «Poderei criar mais imagens assim que seu limite
for redefinido». `imagem.classificar` devolvia `sem_imagem` (a categoria da
excecao) antes de olhar o texto, o regex de `limite` nao casava a frase e o
carteiro ainda repetia o pedido com `REFORCO_IMAGEM` numa conversa nova:
2 turnos por pedido, `fora_de_cota("gemini")` sempre vazio e o Gemini nunca
saia do rodizio.

Com dublê: nenhum navegador, conta, cota ou Telegram (`NF_IAS_PASTA`).
"""
from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from ias import carteiro as carteiro_mod, catalogo, correio, imagem

FRASE = "Poderei criar mais imagens assim que seu limite for redefinido."


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._antes = os.environ.get("NF_IAS_PASTA")
        os.environ["NF_IAS_PASTA"] = str(Path(self._tmp.name) / "ias")

    def tearDown(self):
        if self._antes is None:
            os.environ.pop("NF_IAS_PASTA", None)
        else:
            os.environ["NF_IAS_PASTA"] = self._antes
        self._tmp.cleanup()


@contextmanager
def _trava_livre(nome, esperar=0.0):
    yield True


def _carteiro(fabrica, **ajustes):
    base = {"janela_conversa_s": 0, "resumo_a_cada": 50, "espera_conta_max_s": 100,
            "rodizio_imagem": ["gemini", "chatgpt"], "cota_pausa_h": 6}
    base.update(ajustes)
    return carteiro_mod.Carteiro(
        fabrica_de_sessao=fabrica, fabrica_imagem=imagem.fabrica_imagem_duble(),
        trava=_trava_livre, nome_da_trava=lambda ia: f"perfil__{ia}__teste",
        avisar=lambda *_a, **_k: "entregue", avisar_arquivo=lambda *_a, **_k: True,
        log=lambda m: None, dormir=lambda s: None, ajustes=base, de_servico=True)


class AFraseEhLimite(unittest.TestCase):
    def test_catalogo_geral_reconhece_a_frase(self):
        self.assertEqual(catalogo.classificar(FRASE), "limite")
        self.assertEqual(catalogo.classificar(
            "o Gemini respondeu sem imagem: «Poderei criar mais imagens assim que seu "
            "limite for redefinido»"), "limite")

    def test_a_ficha_do_gemini_traz_a_frase(self):
        achado = carteiro_mod.motivo_da_tela("gemini", f"blá\n{FRASE}\n")
        self.assertIsNotNone(achado)
        self.assertEqual(achado[0], "limite")

    def test_classificar_le_o_texto_da_semimagem(self):
        exc = imagem.SemImagem(f"o Gemini respondeu sem imagem: «{FRASE}»")
        self.assertEqual(imagem.classificar("gemini", exc, "")[0], "limite")
        self.assertEqual(imagem.classificar("gemini", exc, FRASE)[0], "limite")
        # a recusa de modelo de linguagem continua `sem_imagem`
        recusa = imagem.SemImagem("o Gemini respondeu sem imagem: «sou um modelo de linguagem»")
        self.assertEqual(imagem.classificar("gemini", recusa, "")[0], "sem_imagem")


class OCarteiroTiraOGeminiDoRodizio(_Base):
    def test_cota_falha_em_um_turno_e_tira_o_gemini_do_rodizio(self):
        fabrica = carteiro_mod.fabrica_duble(
            imagem_falhar=imagem.SemImagem(f"o Gemini respondeu sem imagem: «{FRASE}»"),
            tela=FRASE)
        c = _carteiro(fabrica)
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
        fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "limite")
        # UM pedido ao dublê, nao dois (sem o reforco em conversa nova)
        self.assertEqual(len(fabrica.criadas[0]._imagem.pedidos), 1)
        self.assertNotIn(carteiro_mod.REFORCO_IMAGEM,
                         " ".join(t["texto"] for t in fabrica.criadas[0].turnos))
        self.assertNotEqual(imagem.fora_de_cota("gemini"), "")
        # o pedido LIVRE seguinte vai ao chatgpt
        outro = _carteiro(carteiro_mod.fabrica_duble())
        livre = correio.pedir_imagem(correio.LIVRE, "um cachorro", proporcao="1:1")
        with mock.patch.object(imagem, "_config",
                               lambda: {"rodizio_imagem": ["gemini", "chatgpt"],
                                        "cota_pausa_h": 6}):
            saida = outro.entregar(correio.uma(correio.LIVRE, livre["id"]))
        self.assertEqual(saida["situacao"], "respondida")
        self.assertEqual(saida["gerador"], "chatgpt")

    def test_recusa_de_verdade_ainda_ganha_o_reforco(self):
        """O reforco continua para o "sou um modelo de linguagem" (02/10)."""
        tentativas = []

        def gerar(prompt):
            tentativas.append(prompt)
            if len(tentativas) == 1:
                raise imagem.SemImagem("o Gemini respondeu sem imagem: «sou um modelo de "
                                       "linguagem, não gero imagens»")
        c = _carteiro(carteiro_mod.fabrica_duble(antes_de_gerar=gerar))
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
        fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(len(tentativas), 2)
        self.assertTrue(tentativas[1].startswith(carteiro_mod.REFORCO_IMAGEM))


if __name__ == "__main__":
    unittest.main()
