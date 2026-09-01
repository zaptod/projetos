# -*- coding: utf-8 -*-
"""Contratos do reparo de perfil de Chrome.

O caso real (31/08/2026): a tela de login do TikTok abria BRANCA — so o
esqueleto cinza, zero texto — e parecia bloqueio do site. Nao era: o perfil
de automacao tinha 1,1 GB de cache e service workers quebrados. Com o cache
limpo a mesma pagina montou; num perfil novo o QR aparecia de primeira.

O que este arquivo trava:

1. `limpar_cache` apaga CACHE e NUNCA o login. Apagar `Network/Cookies` ou
   `Login Data` transformaria um conserto de 15 segundos em "faz tudo de
   novo, incluindo o 2FA".
2. `montou` distingue pagina viva de esqueleto: o esqueleto tem centenas de
   nos e ZERO texto, que foi exatamente o sintoma fotografado.

Rode de dentro de random_builds/:
    python -m unittest tests.test_perfil_chrome_regressions -v
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from builds.identity import browser                                # noqa: E402

# O que NUNCA pode ser apagado: e aqui que mora a sessao.
SAGRADOS = ("Network/Cookies", "Login Data", "Preferences",
            "Local Storage/leveldb/000003.log", "Local State")


def _perfil_falso(raiz: Path) -> Path:
    perfil = raiz / "perfil"
    (perfil / "Default").mkdir(parents=True)
    for relativo in SAGRADOS:
        alvo = perfil / "Default" / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(b"sessao preciosa")
    for nome in ("Cache", "Code Cache", "GPUCache", "Service Worker"):
        pasta = perfil / "Default" / nome
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "lixo.bin").write_bytes(b"x" * 300_000)
    return perfil


class LimparCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.perfil = _perfil_falso(Path(self._tmp.name))

    def test_apaga_o_cache_e_diz_quanto(self):
        pastas, mb = browser.limpar_cache(self.perfil)
        self.assertIn("Cache", pastas)
        self.assertIn("Service Worker", pastas)
        self.assertFalse((self.perfil / "Default" / "Cache").exists())
        self.assertGreater(mb, 0)

    def test_o_login_sobrevive(self):
        """O ponto inteiro do conserto: nao custar um login novo."""
        browser.limpar_cache(self.perfil)
        for relativo in SAGRADOS:
            alvo = self.perfil / "Default" / relativo
            self.assertTrue(alvo.is_file(), f"apagou {relativo}!")
            self.assertEqual(b"sessao preciosa", alvo.read_bytes())

    def test_perfil_sem_cache_nao_quebra(self):
        with tempfile.TemporaryDirectory() as tmp:
            vazio = Path(tmp) / "novo"
            vazio.mkdir()
            self.assertEqual(([], 0.0), browser.limpar_cache(vazio))

    def test_nenhuma_pasta_da_lista_e_de_sessao(self):
        """Rede de seguranca para quem for acrescentar nomes em CACHES."""
        proibidos = ("cookie", "login data", "local state", "preferences",
                     "web data", "local storage", "session")
        for nome in browser.CACHES:
            for proibido in proibidos:
                self.assertNotIn(proibido, nome.lower(),
                                 f"{nome} nao e cache, e sessao")


class ResetarTests(unittest.TestCase):
    """Recomecar o perfil e o ultimo recurso — e nao pode APAGAR nada.

    Limpar o cache resolveu so metade: no perfil velho o texto saiu de 0 para
    159, mas o feed continuou quebrado. Num perfil novo, no mesmo minuto e na
    mesma rede, a tela de login apareceu inteira (texto=738, QR renderizado).
    Como isto custa o login, a pasta velha e GUARDADA, nunca removida.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.perfil = _perfil_falso(Path(self._tmp.name))

    def test_guarda_o_velho_e_libera_o_caminho(self):
        guardado = browser.resetar_perfil(self.perfil)
        self.assertIsNotNone(guardado)
        self.assertTrue(guardado.is_dir(), "apagou o perfil em vez de guardar")
        self.assertIn("quebrado", guardado.name)
        self.assertFalse(self.perfil.exists(),
                         "o caminho tem que ficar livre para o Chrome recriar")

    def test_o_conteudo_continua_recuperavel(self):
        guardado = browser.resetar_perfil(self.perfil)
        cookies = guardado / "Default" / "Network" / "Cookies"
        self.assertTrue(cookies.is_file())
        self.assertEqual(b"sessao preciosa", cookies.read_bytes())

    def test_perfil_inexistente_devolve_none(self):
        self.assertIsNone(
            browser.resetar_perfil(Path(self._tmp.name) / "nao_existe"))

    def test_dois_resets_nao_colidem(self):
        primeiro = browser.resetar_perfil(self.perfil)
        _perfil_falso(Path(self._tmp.name))
        segundo = browser.resetar_perfil(self.perfil)
        self.assertTrue(primeiro.is_dir())
        self.assertTrue(segundo.is_dir())


class PaginaFalsa:
    def __init__(self, texto):
        self._texto = texto

    def evaluate(self, _js):
        return len(self._texto.strip())


class MontouTests(unittest.TestCase):
    def test_esqueleto_branco_nao_montou(self):
        """O sintoma fotografado: muitos nos, zero texto."""
        self.assertFalse(browser.montou(PaginaFalsa("")))
        self.assertFalse(browser.montou(PaginaFalsa("   \\n  ")))

    def test_pagina_com_conteudo_montou(self):
        self.assertTrue(browser.montou(PaginaFalsa("Entrar no TikTok " * 40)))

    def test_limite_configuravel(self):
        texto = "x" * 150
        self.assertFalse(browser.montou(PaginaFalsa(texto), minimo=200))
        self.assertTrue(browser.montou(PaginaFalsa(texto), minimo=120))

    def test_pagina_que_explode_nao_derruba(self):
        class Morta:
            @staticmethod
            def evaluate(_js):
                raise RuntimeError("Execution context was destroyed")

        self.assertFalse(browser.montou(Morta()))


if __name__ == "__main__":
    unittest.main()
