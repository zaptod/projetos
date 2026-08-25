# -*- coding: utf-8 -*-
# Codigo e comentarios em ASCII, como manda a convencao do projeto.
"""Bloqueio do nome ofensivo vindo do comentario.

O nome pedido e a UNICA entrada do sistema que um estranho controla, e ele
termina desenhado na placa de um video publico. Antes desta camada,
sanitizar_nome_pedido("puta que pariu") devolvia ("Puta Que Pariu", None).

O que este arquivo trava:

1. Xingamento e recusado, inclusive escrito com leet ("c4r4lh0") e com as
   letras separadas ("P U T A") - as duas evasoes obvias.
2. Nome legitimo NAO e recusado. Falso positivo aqui e pior que o buraco:
   derrubar "Escurinho" ou "Ana B Silva" quebra o produto para gente inocente.
   A varredura roda contra 12000 nomes GERADOS pelo proprio sistema.
3. A checagem acontece nas duas pontas: no texto bruto (antes da limpeza, que
   quebraria o termo em pedacos) e no nome final (o corte por palavras pode
   formar um termo que o bruto nao tinha).
4. Sem o arquivo de config o filtro nao finge que filtrou.

Rode de dentro de random_builds/:
    python -m pytest tests/test_moderacao_regressions.py -q
"""
import random
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.character import moderacao, nomes  # noqa: E402

OFENSIVOS = [
    "puta que pariu", "FDP caralho", "vai tomar no cu", "seu viado",
    "c4r4lh0", "P U T A", "v i a d o", "f u c k", "c a r a l h o",
    "Puuuta", "nazista", "hitler", "fuck you", "pqp", "vtnc",
]

LEGITIMOS = [
    "Kaelen Vortex", "Escurinho", "Ana B Silva", "J R R Tolkien",
    "Cunha", "Discurso", "Obscuro", "Percurso", "Anna Gassner",
    "Bartolomeu Aguiar", "Seraphina", "Curitiba", "Assis",
    "Nyxaris Fornalcorrente", "Maria Escura", "Pedro Curado",
]


class BloqueioTests(unittest.TestCase):
    def test_ofensivo_e_recusado(self):
        for texto in OFENSIVOS:
            with self.subTest(texto=texto):
                self.assertIsNotNone(
                    moderacao.ofensivo(texto),
                    "%r passou pelo filtro" % texto)

    def test_nome_legitimo_passa(self):
        for texto in LEGITIMOS:
            with self.subTest(texto=texto):
                self.assertIsNone(
                    moderacao.ofensivo(texto),
                    "%r foi bloqueado por engano" % texto)

    def test_sanitizador_recusa_com_motivo(self):
        for texto in OFENSIVOS:
            with self.subTest(texto=texto):
                nome, motivo = nomes.sanitizar_nome_pedido(texto)
                self.assertIsNone(nome)
                self.assertEqual(motivo, moderacao.MOTIVO)

    def test_sanitizador_aceita_legitimo(self):
        for texto in LEGITIMOS:
            with self.subTest(texto=texto):
                nome, motivo = nomes.sanitizar_nome_pedido(texto)
                self.assertIsNone(motivo)
                self.assertTrue(nome)


class FalsoPositivoTests(unittest.TestCase):
    """O sistema nao pode bloquear os nomes que ele mesmo gera."""

    def test_nomes_gerados_nunca_sao_bloqueados(self):
        rng = random.Random(9)
        pegos = []
        for _ in range(6000):
            nome = nomes.gerar_nome_personagem(rng)
            if moderacao.ofensivo(nome):
                pegos.append(nome)
        for _ in range(6000):
            nome = nomes.gerar_nome_arma(rng)
            if moderacao.ofensivo(nome):
                pegos.append(nome)
        self.assertEqual(pegos, [], "nomes gerados bloqueados: %s" % pegos[:10])


class EvasaoTests(unittest.TestCase):
    def test_letras_soltas_so_colam_em_corrida_longa(self):
        # "Ana B Silva" tem uma letra solta e precisa sobreviver.
        self.assertEqual(moderacao._juntar_letras_soltas("ana b silva"),
                         "ana b silva")
        self.assertEqual(moderacao._juntar_letras_soltas("p u t a"), "puta")

    def test_acento_nao_escapa(self):
        self.assertIsNotNone(moderacao.ofensivo("PUTA"))
        self.assertIsNotNone(moderacao.ofensivo("Viado"))

    def test_sem_config_nao_finge_que_filtrou(self):
        original = moderacao._CONFIG
        try:
            moderacao._CONFIG = RAIZ / "config" / "nao_existe.json"
            moderacao._regras.cache_clear()
            # Sem lista, nada e bloqueado - e isso e explicito, nao silencioso.
            self.assertIsNone(moderacao.ofensivo("puta que pariu"))
        finally:
            moderacao._CONFIG = original
            moderacao._regras.cache_clear()


class PontasTests(unittest.TestCase):
    def test_checa_o_texto_bruto(self):
        # Com @ e pontuacao a limpeza quebraria o termo; a checagem vem antes.
        nome, motivo = nomes.sanitizar_nome_pedido("@ c4r4lh0 !")
        self.assertIsNone(nome)
        self.assertEqual(motivo, moderacao.MOTIVO)

    def test_nome_pedido_ofensivo_nao_vira_personagem(self):
        rng = random.Random(3)
        info = nomes.resolver_nome_personagem(rng, nome_pedido="puta que pariu")
        self.assertNotIn("puta", str(info).lower())


if __name__ == "__main__":
    unittest.main()
