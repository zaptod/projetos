"""A marca da serie no MEIO do titulo da parte sai da frente.

Decisao do Adrian no Grimorio (`historias/titulo-marca-no-meio`, 06/10/2026):
"Tirar a marca da frente". Depois do conserto de 05/10 (a marca no COMECO do
titulo da parte, `_sem_a_marca`), sobraram 5 de 312 partes de serie com o nome
da serie repetido no meio:

    TÚMULO 214 — A Mulher do Túmulo 214 (Parte 1/5)          h41 p01
    O Quarto 12 — A Mulher do Quarto 12 (Parte 1/6)          h39 p01
    Rua Sete — A Noite em que a Rua Sete Entendeu (Parte 5/6) h47 p05
    Última Hora — O Passageiro da Última Hora (Parte 1/2)    h45 p01
    Rua do Meio — A Rainha da Rua do Meio (Parte 6/6)        h36 p06

Fica so o titulo da parte e o "(Parte n/N)": `A Mulher do Túmulo 214 (Parte
1/5)`. Medido no acervo em 06/10 (HEAD contra a arvore): esses 5 mudaram, os
outros 307 titulos ficaram iguais.
"""
from __future__ import annotations

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from contos.roteiro.roteiro import titulo_da_parte  # noqa: E402


def _roteiro(marca: str, titulos: list[str]) -> dict:
    return {"serie": True, "titulo": marca, "serie_nome": marca,
            "partes": [{"n": n, "titulo": t}
                       for n, t in enumerate(titulos, 1)]}


class MarcaNoMeio(unittest.TestCase):

    def test_os_cinco_do_acervo(self):
        casos = [
            ("TÚMULO 214", "A Mulher do Túmulo 214", 1, 5,
             "A Mulher do Túmulo 214 (Parte 1/5)"),
            ("O Quarto 12", "A Mulher do Quarto 12", 1, 6,
             "A Mulher do Quarto 12 (Parte 1/6)"),
            ("Rua Sete", "A Noite em que a Rua Sete Entendeu", 5, 6,
             "A Noite em que a Rua Sete Entendeu (Parte 5/6)"),
            ("Última Hora", "O Passageiro da Última Hora", 1, 2,
             "O Passageiro da Última Hora (Parte 1/2)"),
            ("Rua do Meio", "A Rainha da Rua do Meio", 6, 6,
             "A Rainha da Rua do Meio (Parte 6/6)"),
        ]
        for marca, proprio, n, total, esperado in casos:
            titulos = ["x"] * total
            titulos[n - 1] = proprio
            with self.subTest(marca=marca):
                self.assertEqual(esperado,
                                 titulo_da_parte(_roteiro(marca, titulos), n))

    def test_as_outras_partes_da_mesma_serie_seguem_com_a_marca(self):
        r = _roteiro("TÚMULO 214", ["A Mulher do Túmulo 214", "A Lápide",
                                    "x", "y", "z"])
        self.assertEqual("TÚMULO 214 — A Lápide (Parte 2/5)",
                         titulo_da_parte(r, 2))

    def test_marca_no_comeco_continua_com_o_corte_de_05_10(self):
        r = _roteiro("As Três Comportas", [
            "As Três Comportas — Parte 1: A Represa Aguenta"] + ["x"] * 5)
        self.assertEqual("As Três Comportas — A Represa Aguenta (Parte 1/6)",
                         titulo_da_parte(r, 1))

    def test_borda_de_palavra(self):
        """`Rua Sete` nao esta em `Rua Setembro`: a marca fica na frente."""
        r = _roteiro("Rua Sete", ["O Baile da Rua Setembro"])
        self.assertEqual("Rua Sete — O Baile da Rua Setembro (Parte 1/1)",
                         titulo_da_parte(r, 1))

    def test_sem_acento_caixa_nem_artigo(self):
        r = _roteiro("O QUARTO 12", ["a mulher do quarto 12", "b"])
        self.assertEqual("a mulher do quarto 12 (Parte 1/2)",
                         titulo_da_parte(r, 1))

    def test_titulo_comprido_corta_o_titulo_e_guarda_a_ordem(self):
        longo = "A Mulher do Túmulo 214 " + "e a noite sem fim " * 8
        r = _roteiro("TÚMULO 214", [longo.strip()])
        titulo = titulo_da_parte(r, 1)
        self.assertLessEqual(len(titulo), 100)
        self.assertTrue(titulo.startswith("A Mulher do Túmulo 214"))
        self.assertTrue(titulo.endswith("(Parte 1/1)"))

    def test_historia_que_nao_e_serie_nao_muda(self):
        r = {"serie": False, "titulo": "O Quarto 12", "serie_nome": "",
             "partes": [{"n": 1, "titulo": "A Mulher do Quarto 12"}]}
        self.assertEqual("A Mulher do Quarto 12", titulo_da_parte(r, 1))


if __name__ == "__main__":
    unittest.main()
