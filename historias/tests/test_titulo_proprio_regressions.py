"""O video nao pode se acusar de repetir a si mesmo.

16/09/2026. A valvula "titulo ja publicado (nao havia outro na fila)" abriu
quatro vezes no dia, e em NENHUMA havia titulo repetido de verdade.

A causa e a ordem. `titulo_repetido(alvo, canal)` e avaliada ao montar a
ficha, DEPOIS de o YouTube ter publicado e gravado no ledger na mesma
rodada. Entao a chave do proprio video ja estava em `_titulos_no_ar` — posta
por ele mesmo, segundos antes — e ele batia consigo.

Conferido nas seis partes da `historia_00016`: todas com chaves distintas e
dentro dos 60 caracteres. Nao havia nada repetido.

Duas correcoes, e as duas importam:

1. **`menos`**: o proprio `video_id` sai da conta. "Repetido" quer dizer
   OUTRO video com o mesmo titulo.
2. **`plataforma`**: a pergunta util e "ja esta no ar NAQUELE destino". Um
   video que saiu no YouTube e nao no TikTok tem de poder ir ao TikTok —
   sem isso, fechar a valvula mataria o segundo destino de toda rodada, que
   e muito pior que o defeito que ela conserta.

O que este arquivo NAO pode deixar passar: a duplicata de verdade. As
variantes A e B da mesma geracao tem titulo identico, e o Adrian viu as duas
no ar. Elas continuam sendo barradas.
"""
import importlib.util
import unittest
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_titulo", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


postar = _postar()


class _V:
    def __init__(self, vid, titulo):
        self.id, self.titulo = vid, titulo


def _linha(vid, plataforma, titulo):
    return {"video_id": vid, "plataforma": plataforma, "titulo": titulo,
            "url": "http://x"}


class TituloProprioTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, postar, "_publicados_do_canal",
                        postar._publicados_do_canal)
        self.addCleanup(setattr, postar, "repetir_titulo",
                        postar.repetir_titulo)
        postar.repetir_titulo = lambda *_a, **_k: False

    def _ledger(self, linhas):
        postar._publicados_do_canal = lambda _c: list(linhas)

    # ------------------------------------------------ o falso positivo
    def test_o_proprio_video_no_youtube_nao_o_barra(self):
        """O caso exato que abriu a valvula 4x em 16/09."""
        self._ledger([_linha("h16:p03", "youtube", "Parte 3 de 6")])
        self.assertFalse(
            postar.titulo_repetido(_V("h16:p03", "Parte 3 de 6"), "historias"))

    def test_outro_video_com_o_mesmo_titulo_barra(self):
        self._ledger([_linha("outro", "youtube", "Parte 3 de 6")])
        self.assertTrue(
            postar.titulo_repetido(_V("h16:p03", "Parte 3 de 6"), "historias"))

    # ------------------------------------------------ por destino
    def test_ja_no_youtube_nao_barra_o_TIKTOK(self):
        """Barrar aqui mataria o segundo destino de toda rodada — pior que o
        defeito que a valvula conserta."""
        self._ledger([_linha("outro", "youtube", "Igual")])
        self.assertFalse(postar.titulo_repetido(
            _V("novo", "Igual"), "historias", "tiktok"))

    def test_ja_no_tiktok_barra_o_tiktok(self):
        self._ledger([_linha("outro", "tiktok", "Igual")])
        self.assertTrue(postar.titulo_repetido(
            _V("novo", "Igual"), "historias", "tiktok"))

    def test_sem_plataforma_olha_todos_os_destinos(self):
        self._ledger([_linha("outro", "tiktok", "Igual")])
        self.assertTrue(
            postar.titulo_repetido(_V("novo", "Igual"), "historias"))

    # ------------------------------------------------ a duplicata REAL
    def test_a_variante_B_continua_barrada(self):
        """O que o Adrian viu: A e B da mesma geracao, titulo identico."""
        self._ledger([_linha("g84:build:celular", "youtube", "Ylva 56/100")])
        self.assertTrue(postar.titulo_repetido(
            _V("g84:build:celular:B", "Ylva 56/100"), "builds"))

    def test_ledger_ilegivel_deixa_passar(self):
        """"Nao sei" nao pode barrar: ficar sem video e pior."""
        def explode(_c):
            raise OSError("ledger ilegivel")
        postar._publicados_do_canal = explode
        self.assertFalse(
            postar.titulo_repetido(_V("x", "Qualquer"), "historias"))


if __name__ == "__main__":
    unittest.main()
