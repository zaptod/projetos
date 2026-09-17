"""A recuperacao do TikTok esta DESLIGADA, e este arquivo garante que esta.

16/09/2026, a noite. A recuperacao de atrasados que eu escrevi hoje repostou
no ar: a `historia_00003` saiu duas vezes no TikTok, da p01 a p06, e
provavelmente a h10 p01 e a h16 p01 junto. O Adrian viu videos repetidos no
perfil dele.

A CAUSA, e ela e de metodo: `atrasados_no_tiktok` pergunta ao LEDGER quem ja
foi ao TikTok, e o ledger NAO TEM as publicacoes antigas de la — as feitas a
mao, as da grade propria de 13-15/09, os pedaços "1 de 2". O
`_metricas_tiktok` ja mostrava a h3 p08-p10 no TikTok desde 10/09. Entao a
fila leu "nunca foi" sobre partes que estavam no ar havia dias.

Eu conferi a lista com cuidado antes de escrever a funcao — e conferi contra
a fonte errada. A pergunta era sobre o CANAL, e eu medi o ledger.

Enquanto o ledger for cego para o passado do TikTok, QUALQUER coisa que
dependa dele para afirmar "nunca foi" vai repetir. Por isso as tres saem de
circulacao juntas — recuperacao das duas filas e reserva de builds — e nao
so a que foi pega.

Para religar: conferir a fila contra a lista COMPLETA do Studio (titulo,
parte e data), gravar no ledger o que ja estiver la, e so entao virar as
constantes. Este arquivo vai falhar nesse dia, de proposito: e o lembrete de
que religar exige decidir, nao esquecer.
"""
import importlib.util
import unittest
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_desligada", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


postar = _postar()


class DesligadasTests(unittest.TestCase):
    def test_as_constantes_estao_desligadas(self):
        self.assertFalse(postar.RECUPERACAO_LIGADA)
        self.assertFalse(postar.RESERVA_LIGADA)

    def test_recuperacao_nao_leva_ninguem_nos_dois_canais(self):
        """Nem sequer monta a fila: desligada e desligada."""
        for canal in ("historias", "builds"):
            with self.subTest(canal=canal):
                r = postar.recuperar_no_tiktok(canal=canal)
                self.assertFalse(r["feito"])
                self.assertEqual(0, r["fila"])
                self.assertIn("desligada", r.get("motivo", ""))

    def test_reserva_nao_leva_ninguem(self):
        r = postar.publicar_da_reserva()
        self.assertFalse(r["feito"])
        self.assertEqual(0, r["reserva"])
        self.assertIn("desligada", r.get("motivo", ""))

    def test_so_ver_tambem_nao_mostra_fila(self):
        """O `--ver` nao pode prometer o que a rodada nao vai fazer."""
        self.assertEqual(0, postar.recuperar_no_tiktok(so_ver=True)["fila"])
        self.assertEqual(0, postar.publicar_da_reserva(so_ver=True)["reserva"])

    def test_desligar_NAO_apaga_o_calculo_da_fila(self):
        """A lista continua sendo calculavel: e dela que sai o levantamento
        de quantos atrasados ja estao no TikTok. Desligar e parar de PUBLICAR,
        nao parar de saber."""
        self.assertIsInstance(postar.atrasados_no_tiktok(canal="builds"), list)
        self.assertIsInstance(postar.reserva_do_tiktok(), list)


if __name__ == "__main__":
    unittest.main()
