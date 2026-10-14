# -*- coding: utf-8 -*-
"""PUB-3: `renomear` nunca deixa so um dos dois mudado (registro ou pasta).

Auditoria de 11/10/2026 (`publicar-historias.md` #7), verificada em 14/10:
o `a34b355` so inverteu a ordem — gravava o registro e DEPOIS movia a pasta,
sem desfazer. No Windows o `rename` falha justamente com o Chrome aberto
naquele perfil. Medido no HEAD com um arquivo aberto dentro da pasta:
`PermissionError` no rename, o registro ja dizia `historinhas`, a pasta
continuava `tiktok__canal2`, e `perfil()` apontava (e criava, vazia)
`tiktok__historinhas` — o proximo upload pedia login no meio da fila.

Agora a pasta move PRIMEIRO; o registro so grava se ela moveu; e se o
registro nao grava, a pasta volta.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from builds import contas


class RenomearComPastaPresaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)
        antes = (contas.ARQUIVO, contas.runtime_dir)
        contas.ARQUIVO = self.pasta / "contas.json"
        contas.runtime_dir = lambda: self.pasta

        def restaurar():
            contas.ARQUIVO, contas.runtime_dir = antes
        self.addCleanup(restaurar)
        contas.escolher("tiktok", "historias", "canal2")
        self.perfil = self.pasta / "browser_profiles" / "tiktok__canal2"
        self.perfil.mkdir(parents=True)
        (self.perfil / "Cookies").write_bytes(b"login")

    @unittest.skipUnless(os.name == "nt", "o rename so e recusado no Windows")
    def test_chrome_aberto_nada_muda_e_diz_por_que(self):
        """O caso medido: um arquivo ABERTO na pasta (o Chrome no perfil)."""
        with open(self.perfil / "Cookies", "rb"):
            with self.assertRaises(RuntimeError) as caso:
                contas.renomear("tiktok", "canal2", "historinhas")
        self.assertIn("feche o Chrome", str(caso.exception))
        self.assertIn("canal2", contas.contas("tiktok"))
        self.assertNotIn("historinhas", contas.contas("tiktok"))
        self.assertEqual("canal2", contas.ativa("tiktok", "historias"))
        self.assertEqual(self.perfil, contas.perfil("tiktok", "historias"))
        self.assertTrue((self.perfil / "Cookies").is_file())
        self.assertFalse(
            (self.pasta / "browser_profiles" / "tiktok__historinhas").exists())

    def test_rename_recusado_em_qualquer_sistema(self):
        """O mesmo, sem depender do Windows: o `rename` levanta."""
        original = Path.rename

        def recusa(self_, alvo):
            if self_.name == "tiktok__canal2":
                raise PermissionError("[WinError 5] Acesso negado")
            return original(self_, alvo)
        Path.rename = recusa
        self.addCleanup(setattr, Path, "rename", original)
        with self.assertRaises(RuntimeError):
            contas.renomear("tiktok", "canal2", "historinhas")
        self.assertEqual("canal2", contas.ativa("tiktok", "historias"))
        self.assertTrue(self.perfil.is_dir())

    def test_registro_que_nao_grava_devolve_a_pasta(self):
        real = contas._gravar

        def recusa(_dados):
            raise PermissionError("registro trancado")
        contas._gravar = recusa
        self.addCleanup(setattr, contas, "_gravar", real)
        with self.assertRaises(PermissionError):
            contas.renomear("tiktok", "canal2", "historinhas")
        contas._gravar = real
        self.assertTrue((self.perfil / "Cookies").is_file(), "a pasta voltou")
        self.assertFalse(
            (self.pasta / "browser_profiles" / "tiktok__historinhas").exists())
        self.assertEqual("canal2", contas.ativa("tiktok", "historias"))

    def test_caso_zero_tudo_livre_move_e_grava(self):
        r = contas.renomear("tiktok", "canal2", "historinhas")
        nova = self.pasta / "browser_profiles" / "tiktok__historinhas"
        self.assertEqual([str(nova)], r["movidos"])
        self.assertTrue((nova / "Cookies").is_file())
        self.assertEqual("historinhas", contas.ativa("tiktok", "historias"))
        self.assertEqual(nova, contas.perfil("tiktok", "historias"))


if __name__ == "__main__":
    unittest.main()
