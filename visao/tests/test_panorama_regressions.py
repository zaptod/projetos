# -*- coding: utf-8 -*-
"""Contratos do agregador: le tudo, escreve nada, e nunca derruba a tela.

Rode da raiz do monorepo:
    python -m unittest discover -s visao/tests -p "test_*.py" -v
"""
from __future__ import annotations

import time
import unittest
from pathlib import Path

import panorama


class NaoEscreveTests(unittest.TestCase):
    """Um agregador que escreve corrompe estado quando alguem abre a tela."""

    def test_resumo_nao_mexe_em_nada_no_runtime(self):
        antes = self._retrato()
        panorama.esquecer()
        panorama.resumo()
        self.assertEqual(antes, self._retrato(),
                         "o resumo alterou arquivos do runtime")

    @staticmethod
    def _retrato() -> dict:
        """(caminho, tamanho, mtime) de cada arquivo de estado do runtime."""
        try:
            from builds.contas import runtime_dir
            base = Path(runtime_dir())
        except Exception:
            return {}
        retrato = {}
        for caminho in base.iterdir():
            # As pastas de perfil do Chrome e de travas mudam por conta
            # propria (a leitura de `ocupada` toca os .lock); o que importa
            # aqui e o ESTADO: banco, contas, diario.
            if caminho.is_file():
                info = caminho.stat()
                retrato[caminho.name] = (info.st_size, info.st_mtime_ns)
        return retrato


class NaoDerrubaTests(unittest.TestCase):
    """Uma familia que falha nao pode levar as outras tres junto."""

    def test_familia_quebrada_vira_campo_de_erro(self):
        original = panorama.saude.agora

        def explode():
            raise RuntimeError("disco pegou fogo")

        panorama.saude.agora = explode
        self.addCleanup(lambda: setattr(panorama.saude, "agora", original))
        panorama.esquecer()

        dados = panorama.resumo()
        self.assertIn("erro", dados["saude"])
        self.assertIn("disco pegou fogo", dados["saude"]["erro"])
        # As outras tres continuam de pe.
        for familia in ("desempenho", "inventario", "qualidade"):
            self.assertNotIn("erro", dados[familia], familia)

    def test_sem_o_projeto_de_historias_ainda_responde(self):
        """`contos` e opcional: ausente e vazio, nao excecao."""
        import sys
        salvos = {n: m for n, m in sys.modules.items()
                  if n == "contos" or n.startswith("contos.")}
        for nome in salvos:
            sys.modules[nome] = None          # import passa a falhar
        self.addCleanup(lambda: sys.modules.update(salvos))
        panorama.esquecer()

        dados = panorama.resumo()
        self.assertNotIn("erro", dados["inventario"])
        self.assertEqual(0, dados["inventario"]["videos_prontos"]["historias"])


class QuatroFamiliasTests(unittest.TestCase):
    def setUp(self):
        panorama.esquecer()
        self.dados = panorama.resumo()

    def test_as_quatro_estao_la(self):
        self.assertEqual({"saude", "desempenho", "inventario", "qualidade"},
                         set(self.dados))

    def test_saude_separa_por_canal(self):
        """Dois canais no mesmo provedor sao dois trabalhos."""
        self.assertIn("por_canal", self.dados["saude"])

    def test_saude_mostra_quem_divide_pasta(self):
        paralelo = self.dados["saude"]["paralelismo"]
        self.assertIn("divididas", paralelo)
        for linha in paralelo["divididas"]:
            self.assertGreater(len(linha["canais"]), 1)

    def test_desempenho_conta_os_dois_registros(self):
        """Ate aqui nenhum leitor de metrica olhava o das historias."""
        d = self.dados["desempenho"]
        self.assertIn("builds", d)
        self.assertIn("historias", d)
        self.assertEqual(d["total"],
                         d["builds"]["total"] + d["historias"]["total"])

    def test_desempenho_diz_QUANDO_o_numero_foi_baixado(self):
        """Numero velho apresentado como novo e pior que numero nenhum."""
        self.assertIn("atualizado_em", self.dados["desempenho"])


class CacheTests(unittest.TestCase):
    def test_a_segunda_leitura_vem_do_cache(self):
        panorama.esquecer()
        inicio = time.monotonic()
        panorama.resumo()
        primeira = time.monotonic() - inicio

        inicio = time.monotonic()
        panorama.resumo()
        segunda = time.monotonic() - inicio
        self.assertLess(segunda, max(primeira / 4, 0.02),
                        "sem cache, um poller de 3s vira I/O continuo")

    def test_forcar_ignora_o_cache(self):
        panorama.esquecer()
        primeiro = panorama.resumo()
        self.assertIs(primeiro, panorama.resumo())
        self.assertIsNot(primeiro, panorama.resumo(forcar=True))


class SemRedeTests(unittest.TestCase):
    """A tela nao pode travar porque a internet caiu."""

    def test_nenhuma_familia_abre_conexao(self):
        import socket
        original = socket.socket

        class Proibido(Exception):
            pass

        def recusar(*a, **k):
            raise Proibido("o agregador tentou usar a rede")

        socket.socket = recusar
        self.addCleanup(lambda: setattr(socket, "socket", original))
        panorama.esquecer()
        dados = panorama.resumo()          # nao pode levantar Proibido
        for familia, conteudo in dados.items():
            self.assertNotIn("Proibido", str(conteudo.get("erro", "")), familia)


if __name__ == "__main__":
    unittest.main()
