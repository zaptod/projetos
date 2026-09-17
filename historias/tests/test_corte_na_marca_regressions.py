"""A marca fica com o id do PEDACO; a fila escolhe pelo id do INTEIRO.

Video longo demais e cortado antes de subir (`cortes._copia`), e cada pedaco
ganha `id` proprio: `X:corte01`, `X:corte02`. Quem sobe e o pedaco, entao a
marca de "a conferir" fica com o id dele. Mas `_sem_a_conferir` comparava
`v.id` com a lista crua: o `X` continuava livre, voltava no horario seguinte
e reenviava TODOS os pedacos — os que ja tinham saido inclusive.

E a fabrica de rascunhos gemeos pela ultima porta que ela tinha, e o achado
e da revisao do app.

Bloquear o inteiro por causa de um pedaco e de proposito: reenviar `X`
duplica os cortes que deram certo. Quem confere solta os dois juntos.
"""
import importlib.util
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "postar_corte", RAIZ / "ferramentas" / "postar.py")
postar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(postar)


class _Video:
    def __init__(self, vid, titulo=""):
        self.id = vid
        self.titulo = titulo


class RaizesTests(unittest.TestCase):
    def test_o_corte_traz_o_inteiro_junto(self):
        self.assertEqual({"h1:p01:corte01", "h1:p01"},
                         postar._com_as_raizes({"h1:p01:corte01"}))

    def test_varios_cortes_do_mesmo_video(self):
        raizes = postar._com_as_raizes({"h1:p01:corte01", "h1:p01:corte02"})
        self.assertIn("h1:p01", raizes)
        self.assertEqual(3, len(raizes))

    def test_id_sem_corte_fica_igual(self):
        self.assertEqual({"h1:p01"}, postar._com_as_raizes({"h1:p01"}))

    def test_a_VARIANTE_nao_e_corte(self):
        """`:B` e outro video, com outra arte e outro titulo. Bloquear o
        principal por causa dela seria o erro oposto — e ela existe
        justamente para assumir quando o principal cai."""
        self.assertEqual({"g67:build:celular:B"},
                         postar._com_as_raizes({"g67:build:celular:B"}))

    def test_vazio_nao_explode(self):
        self.assertEqual(set(), postar._com_as_raizes(set()))
        self.assertEqual(set(), postar._com_as_raizes(None))


class FilaTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, postar, "a_conferir_no_tiktok",
                        postar.a_conferir_no_tiktok)

    def _com_marcados(self, marcados):
        postar.a_conferir_no_tiktok = lambda _c, _p="tiktok": set(marcados)

    def test_o_inteiro_sai_da_fila_quando_um_corte_esta_marcado(self):
        self._com_marcados({"h1:p01:corte01"})
        fila = [_Video("h1:p01"), _Video("h1:p02")]
        livres = postar._sem_a_conferir(fila, "historias")
        self.assertEqual(["h1:p02"], [v.id for v in livres])

    def test_quem_nao_tem_marca_continua_na_fila(self):
        self._com_marcados({"outro:p09:corte01"})
        fila = [_Video("h1:p01")]
        self.assertEqual(["h1:p01"],
                         [v.id for v in postar._sem_a_conferir(fila, "h")])

    def test_sem_marca_nenhuma_a_fila_passa_inteira(self):
        self._com_marcados(set())
        fila = [_Video("h1:p01"), _Video("h1:p02")]
        self.assertEqual(2, len(postar._sem_a_conferir(fila, "historias")))

    def test_nao_conseguir_ler_esvazia_a_fila(self):
        """Falha fechada: o horario sem post custa um video, e reenviar custa
        um rascunho em cima dos que ja existem."""
        def explode(_c, _p="tiktok"):
            raise RuntimeError("lista ilegivel")
        postar.a_conferir_no_tiktok = explode
        self.assertEqual([], postar._sem_a_conferir([_Video("h1:p01")], "h"))


if __name__ == "__main__":
    unittest.main()
