"""O nome da serie aparecia DUAS vezes no titulo publicado.

Medido em 05/10/2026 (`catalogo.listar()`, 294 titulos): 30 com repeticao,
em 15 historias. O LLM escreve o titulo da parte ja com a marca da serie (e
as vezes com "Parte N:"), e `titulo_da_parte` juntava marca + " — " + titulo
da parte + " (Parte n/N)" sem olhar. Foi ao ar em 18 linhas do ledger:

    Rua das Acácias — Rua das Acácias — O Galho da Discórdia (Parte 1/6)
    Bom Dia, Vizinhos — Bom Dia, Vizinhos (Parte 6/6)
    A Porta das Três — A Porta das Três (Parte 1/2)

e a rodada das 23:37 de 05/10 levaria a `historia_00054` p01 como
`As Três Comportas — As Três Comportas — Parte 1: A Represa Aguenta (Parte 1/6)`.

O formato que fica e UM so: `Marca — Titulo da parte (Parte n/N)`; sem
titulo proprio (igual a marca), `Marca (Parte n/N)`. O "(Parte n/N)" do fim
e o unico marcador de parte — e dele que `titulos.chave` e `capa.sem_o_selo`
dependem —, e o "Parte N:" que o modelo escreveu sai.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from contos.roteiro.roteiro import titulo_da_parte  # noqa: E402


def _roteiro(marca: str, titulos: list[str]) -> dict:
    return {"serie": True, "titulo": marca, "serie_nome": marca,
            "partes": [{"n": n, "titulo": t}
                       for n, t in enumerate(titulos, 1)]}


class TituloSemSerieRepetida(unittest.TestCase):

    def test_tres_comportas_serie_e_parte_n_escritas_pelo_modelo(self):
        r = _roteiro("As Três Comportas", [
            "As Três Comportas — Parte 1: A Represa Aguenta (Parte 1)",
            "As Três Comportas — Parte 2: A Noite do Centenário (Parte 2)",
            "As Três Comportas — Parte 3: 1h40 (Parte 3)",
            "As Três Comportas — Parte 4: A Várzea Seca (Parte 4)",
            "As Três Comportas — Parte 5: O Alto-Falante (Parte 5)",
            "As Três Comportas — Parte 6: O Barco do Adão (Parte 6)"])
        self.assertEqual("As Três Comportas — A Represa Aguenta (Parte 1/6)",
                         titulo_da_parte(r, 1))
        self.assertEqual("As Três Comportas — 1h40 (Parte 3/6)",
                         titulo_da_parte(r, 3))
        # O hifen DENTRO de uma palavra nao e separador da marca.
        self.assertEqual("As Três Comportas — O Alto-Falante (Parte 5/6)",
                         titulo_da_parte(r, 5))

    def test_rua_das_acacias(self):
        r = _roteiro("Rua das Acácias", [
            "Rua das Acácias — O Galho da Discórdia"] + ["x"] * 5)
        self.assertEqual("Rua das Acácias — O Galho da Discórdia (Parte 1/6)",
                         titulo_da_parte(r, 1))

    def test_bom_dia_vizinhos_parte_igual_a_serie(self):
        r = _roteiro("Bom Dia, Vizinhos", ["a"] * 5 + ["Bom Dia, Vizinhos"])
        self.assertEqual("Bom Dia, Vizinhos (Parte 6/6)",
                         titulo_da_parte(r, 6))

    def test_porta_das_tres_parte_igual_a_serie(self):
        r = _roteiro("A Porta das Três", ["A Porta das Três", "O Fim"])
        self.assertEqual("A Porta das Três (Parte 1/2)", titulo_da_parte(r, 1))

    def test_sem_repeticao_nao_muda(self):
        r = _roteiro("Pensão da Lourdes", [
            "A ligação das sete da manhã", "O Fim", "x", "y"])
        self.assertEqual(
            "Pensão da Lourdes — A ligação das sete da manhã (Parte 1/4)",
            titulo_da_parte(r, 1))

    def test_comparacao_sem_acento_caixa_nem_artigo(self):
        r = _roteiro("ONZE MINUTOS", ["Onze Minutos"])
        self.assertEqual("ONZE MINUTOS (Parte 1/1)", titulo_da_parte(r, 1))
        r = _roteiro("Caderno Azul", ["O Caderno Azul", "b", "c"])
        self.assertEqual("Caderno Azul (Parte 1/3)", titulo_da_parte(r, 1))
        r = _roteiro("As Tres Comportas", ["as três comportas - A Cheia"])
        self.assertEqual("As Tres Comportas — A Cheia (Parte 1/1)",
                         titulo_da_parte(r, 1))
        r = _roteiro("Vila Bela", ["Vila Bela: O Forasteiro"])
        self.assertEqual("Vila Bela — O Forasteiro (Parte 1/1)",
                         titulo_da_parte(r, 1))

    def test_so_marca_e_parte_n_vira_so_a_marca(self):
        r = _roteiro("O Reboque", ["O Reboque — Parte 1", "O Reboque"])
        self.assertEqual("O Reboque (Parte 1/2)", titulo_da_parte(r, 1))
        self.assertEqual("O Reboque (Parte 2/2)", titulo_da_parte(r, 2))

    def test_marca_dentro_de_uma_palavra_nao_e_cortada(self):
        """"Rua Sete" e prefixo de "Rua Setembro", mas nao e a marca."""
        r = _roteiro("Rua Sete", ["Rua Setembro — A Festa"])
        self.assertEqual("Rua Sete — Rua Setembro — A Festa (Parte 1/1)",
                         titulo_da_parte(r, 1))

    def test_capa_tira_o_parte_n_de_N_que_o_selo_ja_diz(self):
        """A capa da h54 p01 saiu com o selo "PARTE 1" e "(PARTE 1/6)"."""
        from contos.video import capa
        self.assertEqual("As Três Comportas — A Represa Aguenta",
                         capa.sem_o_selo(
                             "As Três Comportas — A Represa Aguenta (Parte 1/6)"))
        self.assertEqual("A Porta", capa.sem_o_selo("A Porta (Parte 1 de 2)"))

    def test_titulo_nunca_vazio(self):
        r = _roteiro("Bom Dia, Vizinhos", ["Bom Dia, Vizinhos — Parte 1"])
        self.assertEqual("Bom Dia, Vizinhos (Parte 1/1)", titulo_da_parte(r, 1))
        r = _roteiro("", [""])
        r["serie_nome"] = ""
        r["titulo"] = "A Porta"
        self.assertEqual("A Porta (Parte 1/1)", titulo_da_parte(r, 1))


if __name__ == "__main__":
    unittest.main()
