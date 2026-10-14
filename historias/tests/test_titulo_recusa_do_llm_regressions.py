"""A recusa do LLM virou TITULO de parte e ia ao ar (05/10/2026).

O conferente achou a `historia_00059` p06 com o titulo

    Não consigo te ajudar com isso. Sou só um modelo de linguagem e não
    tenho capacidade de entender e responder a essa questão.

no `roteiro.json` (as 14 cenas eram normais). O catalogo a listava como
`Vila Bela — Não consigo te ajudar com isso... (Parte 6/6)`, a capa trazia a
frase e o mp4 a desenha nos primeiros ~2,2 s. Nenhuma guarda barrava: a
vistoria so olhava o arquivo, as imagens e a pertinencia das cenas.

Como nasceu: as 09:06 a retomada da parte 6 voltou com a recusa (antes de
`_perguntar_sem_recusa`, d0e2dfd), `R.parse` leu a frase como titulo, a
continuacao (`parte_06_cont1.txt`) trouxe as cenas e a revisao (outra
recusa) foi descartada por ter menos cenas — o titulo ficou.

Medido em 05/10/2026 com `llm.texto.e_recusa_enlatada` em todo o acervo
(57 historias, 294 partes, 4110 cenas): 1 titulo de parte (h59 p06) e
0 narracoes, 0 cliffhangers, 0 CTAs. Nenhum falso positivo.

Tres guardas, e e por isso que sao tres testes:
  - a VISTORIA barra a parte (ela e o funil de toda escolha do `postar.py`
    e do estoque) e o REPARO troca o titulo pelo do plano da biblia e
    re-renderiza (mp4 e capa saem com o titulo novo);
  - o CATALOGO (`publicar_youtube`/`publicar_tiktok`, por onde passa todo
    upload das historias) recusa subir;
  - a GERACAO nao aceita a recusa como titulo de parte.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]

from contos.roteiro import roteiro as R  # noqa: E402

RECUSA = ("Não consigo te ajudar com isso. Sou só um modelo de linguagem e "
          "não tenho capacidade de entender e responder a essa questão.")
ID = "historia_99059"


def _cenas(n=3):
    return [{"n": i, "narracao": f"Zeca abriu o bau numero {i} na praca.",
             "prompt": "A man opening a wooden chest in a square."}
            for i in range(1, n + 1)]


def _roteiro(titulo_p2=RECUSA, narracao_recusada=False):
    cenas = _cenas()
    if narracao_recusada:
        cenas[1]["narracao"] = RECUSA
    return {"historia_id": ID, "serie": True, "titulo": "Vila Bela",
            "serie_nome": "Vila Bela", "partes_esperadas": 2,
            "partes": [{"n": 1, "titulo": "Vila Bela — Parte 1: O Forasteiro",
                        "cta": "", "cenas": _cenas()},
                       {"n": 2, "titulo": titulo_p2, "cta": "",
                        "cenas": cenas}]}


class _OutputsTemporario(unittest.TestCase):
    """OUTPUTS desviado: nada aqui toca o acervo de producao."""

    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.outputs = Path(pasta.name)
        patcher = mock.patch.object(R, "OUTPUTS", self.outputs)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pasta = self.outputs / ID
        self.pasta.mkdir()

    def gravar(self, roteiro, biblia=None):
        (self.pasta / "roteiro.json").write_text(
            json.dumps(roteiro, ensure_ascii=False), encoding="utf-8")
        if biblia is not None:
            (self.pasta / "biblia.json").write_text(
                json.dumps(biblia, ensure_ascii=False), encoding="utf-8")


class AsPerguntasDoRoteiro(unittest.TestCase):
    def test_titulo_recusado_e_achado(self):
        self.assertEqual(RECUSA, R.recusa_no_titulo(_roteiro(), 2))

    def test_titulo_normal_nao_e_recusa(self):
        self.assertEqual("", R.recusa_no_titulo(_roteiro(), 1))
        self.assertEqual("", R.recusa_no_titulo(
            _roteiro(titulo_p2="Vila Bela — A Quermesse"), 2))

    def test_parte_que_nao_existe_nao_levanta(self):
        self.assertEqual("", R.recusa_no_titulo(_roteiro(), 9))
        self.assertEqual([], R.cenas_com_recusa(_roteiro(), 9))

    def test_narracao_recusada_diz_a_cena(self):
        self.assertEqual([2], R.cenas_com_recusa(
            _roteiro(narracao_recusada=True), 2))
        self.assertEqual([], R.cenas_com_recusa(_roteiro(), 2))


class AVistoriaBarra(unittest.TestCase):
    def _erros(self, roteiro, parte=2):
        from contos.publicar import qualidade as Q
        with mock.patch.object(Q, "_registrar_vistoria"):
            laudo = Q.vistoriar_parte(ID, parte, Path("nao_existe.mp4"),
                                      roteiro)
        return laudo["erros"]

    def test_titulo_recusado_e_erro(self):
        erros = self._erros(_roteiro())
        achados = [e for e in erros if R.TITULO_RECUSADO in e]
        self.assertEqual(1, len(achados), erros)
        self.assertIn("modelo de linguagem", achados[0])

    def test_narracao_recusada_e_erro_de_roteiro(self):
        erros = self._erros(_roteiro(titulo_p2="A Quermesse",
                                     narracao_recusada=True))
        achados = [e for e in erros if "recusa do LLM" in e]
        self.assertEqual(1, len(achados), erros)
        # "roteiro:" = o reparo nao tenta conserto de imagem nisso.
        self.assertTrue(achados[0].startswith("roteiro:"), achados[0])

    def test_parte_limpa_nao_ganha_erro_de_recusa(self):
        erros = self._erros(_roteiro(), parte=1)
        self.assertFalse([e for e in erros if "recusa do LLM" in e], erros)


class OCatalogoNaoSobe(_OutputsTemporario):
    def _video(self, parte=2):
        return SimpleNamespace(fonte_id=ID, parte=parte, partes=2,
                               id=f"{ID}:celular:p{parte:02d}",
                               titulo=R.titulo_da_parte(_roteiro(), parte))

    def test_youtube_recusa_antes_de_subir(self):
        from contos.publicar import catalogo
        self.gravar(_roteiro())
        with mock.patch.object(catalogo, "_rb_publicar_cortes") as cortes, \
                mock.patch.object(catalogo, "_rb_publicar_youtube") as yt:
            with self.assertRaises(catalogo.RecusaDoLLM):
                catalogo.publicar_youtube(self._video())
        cortes.preparar.assert_not_called()
        yt.publicar_como_configurado.assert_not_called()

    def test_tiktok_recusa_antes_de_subir(self):
        from contos.publicar import catalogo
        self.gravar(_roteiro(narracao_recusada=True,
                             titulo_p2="A Quermesse"))
        with mock.patch.object(catalogo, "_rb_publicar_tiktok") as tt:
            with self.assertRaises(catalogo.RecusaDoLLM):
                catalogo.publicar_tiktok(self._video(), postar=True)
        tt.publicar.assert_not_called()

    def test_parte_limpa_passa_pela_guarda(self):
        from contos.publicar import catalogo
        self.gravar(_roteiro())
        catalogo.barrar_recusa(self._video(parte=1))      # nao levanta

    def test_sem_roteiro_a_guarda_nao_inventa_recusa(self):
        from contos.publicar import catalogo
        catalogo.barrar_recusa(SimpleNamespace(fonte_id="historia_nenhuma",
                                               parte=1, titulo="X"))


class OReparoTrocaOTitulo(_OutputsTemporario):
    BIBLIA = {"partes": [{"n": 1, "titulo": "Vila Bela — Parte 1: O Forasteiro"},
                         {"n": 2, "titulo": "Vila Bela — Parte 2: A Quermesse"}]}

    def _pipeline(self):
        # O render de verdade redesenha a capa da parte; desde 06/10/2026 o
        # reparo do titulo confere que ela saiu (ver
        # test_recusa_no_trecho_regressions).
        pipeline = mock.Mock()
        capa = self.pasta / "capa_p02.jpg"
        pipeline.render.side_effect = (
            lambda *_a, **_k: capa.write_bytes(b"capa nova"))
        return pipeline

    def _fila_completa(self):
        from contos.imagens import fila
        return mock.patch.object(fila, "resumo", return_value={
            "total": 3, "prontas": 3, "faltam": 0, "completa": True})

    def _reparar(self, erros):
        from contos.pipeline import reparo
        pipeline = self._pipeline()
        video = SimpleNamespace(fonte_id=ID, parte=2, id=f"{ID}:celular:p02",
                                caminho=self.pasta / "final_celular_p02.mp4")
        with mock.patch.object(reparo, "insistente", return_value=False), \
                mock.patch.object(reparo, "_anotar", return_value=1), \
                self._fila_completa(), \
                mock.patch.object(reparo, "_so_vistoria",
                                  return_value={"aprovado": True,
                                                "motivos": []}):
            resultado = reparo.reparar(video, erros, pipeline=pipeline,
                                       log=lambda *_a: None)
        return resultado, pipeline

    def test_troca_pelo_titulo_do_plano_e_rerenderiza(self):
        self.gravar(_roteiro(), self.BIBLIA)
        erros = [f"{R.TITULO_RECUSADO}: \"{RECUSA[:60]}\""]
        resultado, pipeline = self._reparar(erros)
        self.assertTrue(resultado["ok"], resultado)
        pipeline.render.assert_called_once()
        gravado = R.carregar(ID)
        parte = R.parte_de(gravado, 2)
        self.assertEqual("Vila Bela — Parte 2: A Quermesse", parte["titulo"])
        self.assertEqual(RECUSA, parte["titulo_recusado"])
        self.assertEqual("Vila Bela — A Quermesse (Parte 2/2)",
                         R.titulo_da_parte(gravado, 2))
        # As cenas nao mudam: so o titulo era recusa.
        self.assertEqual(_roteiro()["partes"][1]["cenas"], parte["cenas"])

    def test_plano_tambem_recusado_fica_so_a_marca(self):
        biblia = {"partes": [{"n": 2, "titulo": RECUSA}]}
        self.gravar(_roteiro(), biblia)
        resultado, pipeline = self._reparar(
            [f"{R.TITULO_RECUSADO}: \"x\""])
        self.assertTrue(resultado["ok"], resultado)
        gravado = R.carregar(ID)
        self.assertEqual("Vila Bela (Parte 2/2)", R.titulo_da_parte(gravado, 2))

    def test_render_que_falha_devolve_o_titulo(self):
        # Roteiro limpo com o mp4 velho faria a vistoria aprovar o video que
        # ainda tem a recusa desenhada na primeira imagem e na capa.
        from contos.pipeline import reparo
        self.gravar(_roteiro(), self.BIBLIA)
        pipeline = mock.Mock()
        pipeline.render.side_effect = RuntimeError("ffmpeg caiu")
        video = SimpleNamespace(fonte_id=ID, parte=2, id=f"{ID}:celular:p02",
                                caminho=self.pasta / "final_celular_p02.mp4")
        with mock.patch.object(reparo, "insistente", return_value=False), \
                mock.patch.object(reparo, "_anotar", return_value=1), \
                self._fila_completa():
            resultado = reparo.reparar(
                video, [f"{R.TITULO_RECUSADO}: \"x\""], pipeline=pipeline,
                log=lambda *_a: None)
        self.assertFalse(resultado["ok"])
        self.assertEqual(RECUSA, R.recusa_no_titulo(R.carregar(ID), 2))

    def test_narracao_recusada_nao_e_conserto_automatico(self):
        self.gravar(_roteiro(narracao_recusada=True), self.BIBLIA)
        resultado, pipeline = self._reparar(
            ["roteiro: a narracao da cena 2 e recusa do LLM"])
        self.assertFalse(resultado["ok"])
        pipeline.render.assert_not_called()


class AGeracaoNaoAceita(unittest.TestCase):
    def test_titulo_recusado_vira_o_do_plano(self):
        from contos.roteiro import gerar
        titulo = gerar._titulo_aceito(RECUSA, {"titulo": "A Quermesse"}, 6,
                                      log=lambda *_a: None)
        self.assertEqual("A Quermesse", titulo)

    def test_titulo_e_plano_recusados_e_falha(self):
        from contos.roteiro import gerar
        with self.assertRaises(gerar.RecusaEnlatada):
            gerar._titulo_aceito(RECUSA, {"titulo": RECUSA}, 6,
                                 log=lambda *_a: None)

    def test_titulo_normal_passa_igual(self):
        from contos.roteiro import gerar
        self.assertEqual("O Forasteiro", gerar._titulo_aceito(
            "O Forasteiro", {"titulo": "X"}, 1, log=lambda *_a: None))
        self.assertEqual("X", gerar._titulo_aceito(
            "", {"titulo": "X"}, 1, log=lambda *_a: None))

    def test_narracao_recusada_e_falha(self):
        from contos.roteiro import gerar
        cenas = _cenas()
        cenas[2]["narracao"] = RECUSA
        with self.assertRaises(gerar.RecusaEnlatada):
            gerar._sem_recusa_nas_cenas(cenas, 6)
        gerar._sem_recusa_nas_cenas(_cenas(), 6)          # nao levanta

    def test_os_dois_caminhos_de_escrita_usam_a_guarda(self):
        import inspect

        from contos.roteiro import gerar
        for funcao in (gerar.gerar_serie, gerar.retomar_serie):
            fonte = inspect.getsource(funcao)
            self.assertIn("_titulo_aceito(", fonte, funcao.__name__)
            self.assertIn("_sem_recusa_nas_cenas(", fonte, funcao.__name__)
            self.assertNotIn('parcial["titulo"] or plano.get("titulo")',
                             fonte, funcao.__name__)


class OTituloDaParte(unittest.TestCase):
    """Bordas que o conferente achou em 05/10/2026 depois de 6184587."""

    def _t(self, marca, titulo):
        return R.titulo_da_parte(
            {"serie": True, "titulo": marca, "serie_nome": marca,
             "partes": [{"n": 1, "titulo": titulo}, {"n": 2, "titulo": "b"}]},
            1)

    def test_caixa_alta_e_normalizada_depois_do_corte(self):
        self.assertEqual("As Três Comportas — A cheia (Parte 1/2)",
                         self._t("As Três Comportas",
                                 "AS TRÊS COMPORTAS — A CHEIA"))

    def test_resto_minusculo_ganha_maiuscula(self):
        self.assertEqual("Vila Bela — O forasteiro (Parte 1/2)",
                         self._t("Vila Bela", "Vila Bela: o forasteiro"))

    def test_virgula_antes_do_parte_n(self):
        self.assertEqual("Vila Bela (Parte 1/2)",
                         self._t("Vila Bela", "Vila Bela, Parte 1"))

    def test_parte_por_extenso(self):
        self.assertEqual("Vila Bela — O Forasteiro (Parte 1/2)",
                         self._t("Vila Bela",
                                 "Vila Bela — Parte Um: O Forasteiro"))
        self.assertEqual("Vila Bela — O Forasteiro (Parte 1/2)",
                         self._t("Vila Bela", "Parte Um: O Forasteiro"))

    def test_marca_de_uma_letra(self):
        self.assertEqual("A — B (Parte 1/2)", self._t("A", "A — B"))

    def test_o_que_ja_funcionava_continua(self):
        self.assertEqual("Vila Bela — O Forasteiro (Parte 1/2)",
                         self._t("Vila Bela", "Vila Bela - Parte 1 - O Forasteiro"))
        self.assertEqual("Vila Bela (Parte 1/2)",
                         self._t("Vila Bela", "Vila Bela (Parte 1)"))
        self.assertEqual("Vila Bela — 23:37 — O Relógio (Parte 1/2)",
                         self._t("Vila Bela", "Vila Bela: 23:37 — O Relógio"))
        # Marca em CAPS fica como o LLM escreveu (outra questao).
        self.assertEqual("ONZE MINUTOS (Parte 1/2)",
                         self._t("ONZE MINUTOS", "ONZE MINUTOS"))

    def test_palavra_que_comeca_com_um_nao_e_numero(self):
        self.assertEqual("Parte Umbigo", R.limpar_titulo_de_parte(
            "Parte Umbigo"))

    def test_fora_de_serie_a_caixa_continua_normalizada(self):
        self.assertEqual("A passagem",
                         R.limpar_titulo_de_parte("PARTE 3 - A PASSAGEM"))
        self.assertEqual("O APAGÃO — O resgate", R.titulo_da_parte(
            {"titulo": "O APAGÃO — O resgate",
             "partes": [{"n": 1, "titulo": "O APAGÃO — O resgate"}]}, 1))


if __name__ == "__main__":
    unittest.main()
