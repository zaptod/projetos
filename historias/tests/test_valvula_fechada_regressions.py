"""A valvula de titulo repetido FECHOU: repetir e pior que nao postar.

17/09/2026, por decisao do Adrian depois de ver conteudo repetido no perfil.

Ate ontem, fila inteira com titulo ja publicado liberava "o menos pior": o
video saia assim mesmo e a ficha ganhava uma marca. Foi assim que as
variantes A e B de cinco geracoes (00067, 00069, 00071, 00081, 00082) sairam
as duas, nos dois destinos, com titulo IDENTICO — para a deduplicacao por
`video_id` sao dois videos, para quem abre o perfil sao dois iguais.

A regra "nao ficar sem video" continua valendo, e nao e contradita aqui: ela
existe para estoque e para falha. Cobrir buraco com repeticao e outra coisa
— custa a confianca de quem ve a mesma coisa duas vezes, e um horario vazio
custa um post.

Nos builds ha uma saida melhor que o branco, e ela ja existe: a RESERVA leva
um build antigo ao TikTok quando a fila normal nao tem nada. O YouTube fica
sem, de proposito.

A marca `titulo_repetido` da ficha continua existindo, mas MUDOU DE SENTIDO:
era "saiu assim mesmo", virou DETECTOR. Pelo desenho novo ela deve ficar em
zero; se aparecer, algum caminho escapou da guarda.
"""
import importlib.util
import unittest
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_valvula", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _V:
    def __init__(self, vid, titulo):
        self.id, self.titulo, self.perfil = vid, titulo, "celular"
        self.pendencias = []


class ValvulaFechadaTests(unittest.TestCase):
    def setUp(self):
        self.postar = _postar()
        self.postar._linha = lambda *_a, **_k: None
        self.postar.repetir_titulo = lambda *_a, **_k: False

    # -------------------------------------------------- historias
    def _fila_real(self, titulos_das_partes, ja_no_ar):
        """Chama `fila_de_historias` DE VERDADE, com catalogo e ledger
        dublados. Reproduzir o trecho da valvula aqui passaria com a producao
        quebrada, que e o que o teste existe para pegar."""
        from contos.publicar import catalogo, serie

        class _P:
            def __init__(self, vid, titulo, parte):
                self.id, self.titulo, self.perfil = vid, titulo, "celular"
                self.parte, self.partes = parte, len(titulos_das_partes)
                self.fonte_id = "historia_00001"

        videos = [_P(f"historia_00001:celular:p{n:02d}", t, n)
                  for n, t in enumerate(titulos_das_partes, 1)]
        self.addCleanup(setattr, catalogo, "listar", catalogo.listar)
        self.addCleanup(setattr, serie, "publicados", serie.publicados)
        catalogo.listar = lambda *_a, **_k: videos
        serie.publicados = lambda *_a, **_k: [
            {"video_id": "outro", "plataforma": "youtube", "titulo": t,
             "url": "http://x"} for t in ja_no_ar]
        self.postar._publicados_do_canal = lambda _c: serie.publicados()
        return [v.id for v in self.postar.fila_de_historias()]

    def test_historias_todas_repetidas_devolve_VAZIO(self):
        """Antes devolvia a fila inteira ("sigo com a fila como estava")."""
        self.assertEqual(
            [], self._fila_real(["Igual", "Igual"], ja_no_ar=["Igual"]))

    def test_historias_com_inedito_devolve_so_o_inedito(self):
        fila = self._fila_real(["Igual", "Novo"], ja_no_ar=["Igual"])
        self.assertEqual(["historia_00001:celular:p02"], fila)

    def test_historias_sem_nada_no_ar_devolve_tudo(self):
        fila = self._fila_real(["Um", "Dois"], ja_no_ar=[])
        self.assertEqual(2, len(fila))

    # -------------------------------------------------- builds
    def test_builds_todos_repetidos_NAO_publica(self):
        p = self.postar
        p._sem_titulo_repetido = lambda f, *_a, **_k: ([], list(f))
        p._publicados_do_canal = lambda _c: []
        pend = [_V("g1:build:celular", "Igual")]
        import builds.publicar.catalogo as C
        self.addCleanup(setattr, C, "listar", C.listar)
        C.listar = lambda *_a, **_k: pend
        self.addCleanup(setattr, p, "_fontes_de_atraso", p._fontes_de_atraso)
        from builds.publicar import metricas
        self.addCleanup(setattr, metricas, "publicados", metricas.publicados)
        metricas.publicados = lambda *_a, **_k: []
        self.assertIsNone(p.proximo_build())

    # -------------------------------------------------- o rotulo
    def test_a_marca_virou_DETECTOR(self):
        """Se ela aparecer no relatorio, alguem escapou da guarda."""
        texto = self.postar.VALVULAS["titulo_repetido"]
        self.assertIn("ESCAPOU", texto)
        self.assertNotIn("nao havia outro na fila", texto)


if __name__ == "__main__":
    unittest.main()
