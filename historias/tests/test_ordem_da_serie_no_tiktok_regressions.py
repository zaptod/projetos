"""Parte N so sai depois que a N-1 ja esta NAQUELE destino.

MEDIDO EM 17/09/2026, todas as series dos dois canais:

    YOUTUBE                       TIKTOK
    h03  1..10           ok       h03  7,8,9,10,1,2,3,4,5,6   FORA
    h04  3,4,5,1,2,6     FORA     h04  3,4,1,2,6,5            FORA
    h05  1..6            ok       h05  1,2,3,4,6,5            FORA
    h09  1..6            ok       h09  1,2,3,6,4              FORA
    h10  1,3,4,2,6,5     FORA     h10  3,6,5,1,4,2            FORA
    h11  2,1,3,4,5,6     FORA     h11  2,1,3,4,5,6            FORA
    h12  1..6            ok       h12  1,2,3,5,4,6            FORA
                  3 de 13                            7 de 13

No YouTube a garantia existe desde 14/09 (`proxima_historia`, `bloqueadas`,
pedida pelo Adrian depois de a h10 publicar a p06 antes da p05) e as tres
desordens sao anteriores a ela. No TikTok nao havia garantia nenhuma, e a
h03 saiu 7, 8, 9, 10 e SO ENTAO 1 a 6 — quem comecou a acompanhar recebeu o
fim primeiro.

Dois mecanismos produziam isso, e a guarda fecha os dois porque pergunta
pelo DESTINO em vez de pelo ledger:

1. a fila do TikTok e partida em duas por data (`CORTE_DO_TIKTOK`): "atraso"
   depois do corte e "reserva" antes dele. Serie que atravessa o corte saia
   com as partes novas primeiro, por construcao.
2. a fila segue a ordem do ledger, que e a ordem do YOUTUBE — uma desordem
   la era copiada para ca, para sempre, e mesmo depois de consertada la.

SEM ULTIMO RECURSO, ao contrario do YouTube: la o "fora de ordem" e escolha
consciente do Adrian para o horario nao ficar vazio; aqui a recuperacao e
sempre EXTRA, entao pular para outra serie nao custa nada.
"""
import importlib.util
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "postar_ordem", RAIZ / "ferramentas" / "postar.py")
postar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(postar)


class _Parte:
    def __init__(self, fonte, parte):
        self.fonte_id = fonte
        self.parte = parte
        self.id = f"{fonte}:celular:p{parte:02d}"
        self.titulo = f"serie (Parte {parte}/6)"


class _Build:
    def __init__(self, vid="generation_00006:build:celular"):
        self.id = vid
        self.fonte_id = vid.split(":")[0]
        self.parte = None
        self.titulo = "um build"


class OrdemTests(unittest.TestCase):
    def _filtrar(self, candidatos, no_destino):
        return postar._em_ordem_no_destino(candidatos, set(no_destino), "h")

    def test_a_parte_1_sempre_pode(self):
        self.assertEqual(
            ["h1:celular:p01"],
            [v.id for v in self._filtrar([_Parte("h1", 1)], set())])

    def test_a_parte_3_espera_a_2(self):
        fora = self._filtrar([_Parte("h1", 3)], {("h1", 1)})
        self.assertEqual([], fora, "a 2 nao esta no destino")

    def test_a_parte_3_sai_quando_1_e_2_estao_la(self):
        fora = self._filtrar([_Parte("h1", 3)], {("h1", 1), ("h1", 2)})
        self.assertEqual(["h1:celular:p03"], [v.id for v in fora])

    # ------------------------------------- o cuidado (2) do orquestrador
    def test_serie_JA_embaralhada_NAO_trava_para_sempre(self):
        """A h09 tem 1, 2, 3, 4 e 6 no TikTok. A parte 5 exige 1 a 4, que
        estao la — entao ela sai, e e exatamente o que conserta a serie.

        A pergunta e "a N-1 esta no destino?", e nunca "a ordem foi
        respeitada": esta seria irreparavel."""
        no_destino = {("h9", 1), ("h9", 2), ("h9", 3), ("h9", 4), ("h9", 6)}
        fora = self._filtrar([_Parte("h9", 5)], no_destino)
        self.assertEqual(["h9:celular:p05"], [v.id for v in fora])

    def test_a_que_depende_da_faltante_continua_presa(self):
        """Na h10 faltam a 2 e a 4 no destino; a 3 espera a 2."""
        fora = self._filtrar([_Parte("h10", 3), _Parte("h10", 2)],
                             {("h10", 1), ("h10", 5), ("h10", 6)})
        self.assertEqual(["h10:celular:p02"], [v.id for v in fora])

    # ------------------------------------- o cuidado (1) do orquestrador
    def test_a_reserva_nao_fura_a_ordem(self):
        """A fila partida por data foi o que fez a h03 sair 7,8,9,10,1..6. A
        guarda pergunta pelo destino, entao nao importa de que lado do corte
        o video veio."""
        no_destino = {("h3", n) for n in (7, 8, 9, 10)}
        fora = self._filtrar([_Parte("h3", 2)], no_destino)
        self.assertEqual([], fora, "a 1 nao esta no destino")
        fora = self._filtrar([_Parte("h3", 1)], no_destino)
        self.assertEqual(["h3:celular:p01"], [v.id for v in fora])

    # ------------------------------------- o que nao tem parte
    def test_build_passa_direto(self):
        fora = self._filtrar([_Build()], set())
        self.assertEqual(1, len(fora), "build nao tem parte nem serie")

    def test_a_ordem_relativa_e_preservada(self):
        cand = [_Parte("a", 1), _Parte("b", 1), _Parte("c", 1)]
        self.assertEqual(["a:celular:p01", "b:celular:p01", "c:celular:p01"],
                         [v.id for v in self._filtrar(cand, set())])

    # ------------------------------------- o travamento APARECE
    def test_o_que_trava_e_DITO(self):
        """Fila que para em silencio e o defeito que deixou 20 builds
        esperando duas semanas com o contador parecendo certo."""
        ditas = []
        original = postar._linha
        postar._linha = lambda t="": ditas.append(t)
        try:
            self._filtrar([_Parte("h1", 4)], {("h1", 1)})
        finally:
            postar._linha = original
        texto = " ".join(ditas)
        self.assertIn("ordem da serie", texto)
        self.assertIn("h1:celular:p04", texto)
        self.assertIn("2,3", texto, "diga QUAIS partes faltam")

    def test_nada_preso_nao_fala_nada(self):
        ditas = []
        original = postar._linha
        postar._linha = lambda t="": ditas.append(t)
        try:
            self._filtrar([_Parte("h1", 1)], set())
        finally:
            postar._linha = original
        self.assertEqual([], ditas)


class NaFilaDeVerdadeTests(unittest.TestCase):
    """A guarda tem de estar no caminho, e antes do rodizio e do teto."""

    def test_a_fila_do_tiktok_usa_a_guarda(self):
        import inspect
        fonte = inspect.getsource(postar._fila_do_tiktok)
        sem_comentario = "\n".join(
            l for l in fonte.splitlines() if not l.strip().startswith("#"))
        i_ordem = sem_comentario.find("_em_ordem_no_destino(")
        self.assertNotEqual(-1, i_ordem, "guarda que ninguem chama nao guarda")
        self.assertLess(i_ordem, sem_comentario.find("_em_rodizio("),
                        "a ordem e sobre o video; o rodizio e sobre o dia")

    def test_le_as_partes_do_TIKTOK_e_nao_do_ledger_inteiro(self):
        import inspect
        fonte = inspect.getsource(postar._fila_do_tiktok)
        self.assertIn("partes_no_tiktok", fonte)
        trecho = fonte[fonte.find("partes_no_tiktok = set()"):
                       fonte.find("_em_ordem_no_destino(")]
        self.assertIn('l.get("plataforma") != "tiktok"', trecho,
                      "as partes contadas tem de ser as do DESTINO")


if __name__ == "__main__":
    unittest.main()
