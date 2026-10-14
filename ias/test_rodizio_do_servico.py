# -*- coding: utf-8 -*-
"""IAS-7 (auditoria de 11/10/2026): o rodizio do carteiro de servico era
fixo (Gemini sempre primeiro) e o `config.json` so valia depois de reiniciar.

O `config.json` sempre tem `rodizio_imagem`; ele chegava em
`self.ajustes` e vencia o `or imagem.rodizio_ordem()`, entao no servico o
pedido `livre` ia sempre ao primeiro livre da lista e a divisao "vai quem
gerou ha mais tempo" (decidida em 03/10) nunca rodava. E `cota_pausa_h`
editado no config so valia depois de reiniciar o carteiro.

Com dublê: nenhum navegador, conta ou Telegram (`NF_IAS_PASTA`).
"""
from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from ias import carteiro as carteiro_mod, correio, imagem


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._antes = os.environ.get("NF_IAS_PASTA")
        os.environ["NF_IAS_PASTA"] = str(Path(self._tmp.name) / "ias")
        self.config = {"rodizio_imagem": ["gemini", "chatgpt"], "cota_pausa_h": 6}
        base = dict(carteiro_mod.PADRAO_CONFIG)
        self._patches = [
            mock.patch.object(carteiro_mod, "config", lambda: {**base, **self.config}),
            mock.patch.object(imagem, "_config", lambda: dict(self.config)),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        if self._antes is None:
            os.environ.pop("NF_IAS_PASTA", None)
        else:
            os.environ["NF_IAS_PASTA"] = self._antes
        self._tmp.cleanup()


@contextmanager
def _trava_livre(nome, esperar=0.0):
    yield True


def _servico(**ajustes):
    """O carteiro de servico: SEM `rodizio_imagem` nos ajustes (como o `main`)."""
    c = carteiro_mod.Carteiro(
        fabrica_de_sessao=carteiro_mod.fabrica_duble(),
        fabrica_imagem=imagem.fabrica_imagem_duble(), trava=_trava_livre,
        nome_da_trava=lambda ia: f"perfil__{ia}__teste", avisar=lambda _t: "entregue",
        avisar_arquivo=lambda *_a: True, log=lambda m: None, dormir=lambda s: None,
        ajustes={"janela_conversa_s": 0, **ajustes}, de_servico=True)
    c._diario = lambda *a: None
    return c


def _imagem_feita(gerador, ha_horas=0.0, situacao="respondida", categoria=None):
    quando = (datetime.now() - timedelta(hours=ha_horas)).isoformat(timespec="seconds")
    m = correio.pedir_imagem(gerador, "antiga", proporcao="1:1")
    campos = {"situacao": situacao, "gerador": gerador}
    if situacao == "respondida":
        campos["respondida_em"] = quando
    else:
        campos.update(falhou_em=quando, categoria=categoria, erro="limite atingido")
    correio.atualizar(gerador, m["id"], **campos)


class VaiQuemGerouHaMaisTempo(_Base):
    def test_gemini_acabou_de_gerar_o_pedido_vai_ao_chatgpt(self):
        _imagem_feita("gemini")
        self.assertEqual(imagem.rodizio_ordem(), ["chatgpt", "gemini"])
        c = _servico()
        livre = correio.pedir_imagem(correio.LIVRE, "um gato", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["id"], livre["id"])
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(fim["gerador"], "chatgpt")

    def test_lista_de_quem_chama_ainda_fixa_o_gerador(self):
        """O identity passa `rodizio_imagem: [gerador]`: so ele."""
        _imagem_feita("chatgpt")                        # o chatgpt gerou agora...
        c = _servico(rodizio_imagem=["chatgpt"])        # ...mas foi o escolhido
        correio.pedir_imagem(correio.LIVRE, "um gato", proporcao="1:1")
        self.assertEqual(c.uma_volta()["gerador"], "chatgpt")


class ConfigValeSemReiniciar(_Base):
    def test_cota_pausa_h_editada_vale_na_volta_seguinte(self):
        # o gemini bateu o limite ha 2 h; o chatgpt gerou agora (o gemini e o
        # mais antigo, entao vem primeiro se estiver em cota)
        _imagem_feita("gemini", ha_horas=2, situacao="falhou", categoria="limite")
        _imagem_feita("chatgpt")
        c = _servico()
        correio.pedir_imagem(correio.LIVRE, "pedido 1", proporcao="1:1")
        self.assertEqual(c.uma_volta()["gerador"], "chatgpt")   # 6 h: gemini fora
        self.config["cota_pausa_h"] = 1                  # editado com o carteiro no ar
        correio.pedir_imagem(correio.LIVRE, "pedido 2", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(c.ajustes["cota_pausa_h"], 1)
        self.assertEqual(fim["gerador"], "gemini")      # 1 h: o gemini voltou


if __name__ == "__main__":
    unittest.main()
