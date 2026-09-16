"""Builds tambem podem ficar atrasados no TikTok — e agora sao recuperados.

16/09/2026. O Adrian achou que a parte 4 da "Panela da Discordia" nao tinha ido
ao TikTok, e a recuperacao de atrasados foi feita — **so para historias**.
Builds ficaram de fora, e do lado deles o buraco era pior: `proximo_build`
descarta todo video que ja tem `url` em QUALQUER plataforma, entao um build
que falhasse no TikTok saia da fila para sempre. Medido no ledger: 8 builds no
periodo em que o TikTok ja funcionava, ~1 por dia de postagem, invisiveis.

E o conserto da legenda do mesmo dia (`fe1c7f4`) acrescentou um jeito NOVO de
cair nesse buraco: antes o build saia sem legenda, agora ele nao sai.

Quatro armadilhas que este arquivo tranca, todas achadas medindo a lista antes
de escrever a funcao:

1. **Nao reusar `titulo_repetido`.** Ela conta `url` de qualquer plataforma e
   nao exclui o proprio `video_id` — e todo candidato a recuperacao ja esta no
   ar no YouTube com o proprio titulo. Reusada aqui, ela recusaria TODOS, a
   fila viveria vazia e os testes ficariam VERDES, porque fila vazia e um
   estado legitimo. A pergunta certa e outra: ja existe OUTRO video com esta
   chave de titulo NO TIKTOK?
2. **Data de corte so nos builds.** Antes de 10/09 nada ia ao TikTok, mas a
   fila de historias ja vinha drenando sob politica aceita e tem partes de
   09/09 nela. Cortar os dois canais tiraria video de uma fila que funciona.
3. **Desistidos saem ANTES da deduplicacao**, senao desistir de um VIDEO
   viraria desistir do TITULO: com o A abandonado, o B tem de poder assumir.
4. **A ordem e a do ledger.** "Principal antes da variante" e desempate dentro
   do mesmo titulo; ordenar por id jogaria a cronologia fora.
"""
import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

# Carrega o `ferramentas/postar.py` sem cirurgia de `sys.path`: a catraca de
# arquitetura conta essas cirurgias e recusa qualquer aumento. E o mesmo
# carregador de `test_tiktok_na_grade_regressions.py`.
POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_atrasados", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


postar = _postar()


class _Video:
    def __init__(self, vid, titulo):
        self.id, self.titulo, self.perfil = vid, titulo, "celular"


def _linha(vid, plataforma, quando, titulo, url="http://x"):
    return {"video_id": vid, "plataforma": plataforma, "quando": quando,
            "titulo": titulo, "url": url}


class AtrasadosPorCanalTests(unittest.TestCase):
    def _fila(self, linhas, videos, canal="builds", desistidos=()):
        cat = {v.id: v for v in videos}
        with patch.object(postar, "_fontes_de_atraso",
                          return_value=(linhas, cat)), \
             patch.object(postar, "desistencias_do_tiktok",
                          return_value=set(desistidos)):
            return [v.id for v in postar.atrasados_no_tiktok(canal=canal)]

    # ---------------------------------------------------- 1 e 4 (o no-op)
    def test_so_no_youtube_entra(self):
        fila = self._fila(
            [_linha("g1:build:celular", "youtube", "2026-09-14T10:00", "Um")],
            [_Video("g1:build:celular", "Um")])
        self.assertEqual(["g1:build:celular"], fila)

    def test_o_proprio_video_no_youtube_nao_barra_a_si_mesmo(self):
        """O teste que pega o no-op silencioso.

        Se o filtro de titulo olhar o YouTube, ou nao excluir o proprio id,
        a fila vem VAZIA e nada acusa.
        """
        linhas = [_linha("g1:build:celular", "youtube", "2026-09-14T10:00",
                         "Erik, Guerreiro — build 87/100")]
        fila = self._fila(linhas,
                          [_Video("g1:build:celular",
                                  "Erik, Guerreiro — build 87/100")])
        self.assertEqual(["g1:build:celular"], fila,
                         "o proprio titulo no YouTube nao pode barrar")

    def test_titulo_ja_no_tiktok_por_outro_id_nao_entra(self):
        linhas = [
            _linha("gA:build:celular", "tiktok", "2026-09-14T09:00", "Erik"),
            _linha("gB:build:celular", "youtube", "2026-09-14T10:00", "Erik"),
        ]
        fila = self._fila(linhas, [_Video("gB:build:celular", "Erik")])
        self.assertEqual([], fila)

    # ---------------------------------------------------- variante A/B
    def test_entre_A_e_B_pendentes_vai_o_A(self):
        linhas = [
            _linha("g67:build:celular:B", "youtube", "2026-09-15T10:00", "Erik"),
            _linha("g67:build:celular", "youtube", "2026-09-15T11:00", "Erik"),
        ]
        videos = [_Video("g67:build:celular:B", "Erik"),
                  _Video("g67:build:celular", "Erik")]
        # O :B vem ANTES no ledger de proposito: se a regra dependesse da
        # ordem cronologica, este teste falharia.
        self.assertEqual(["g67:build:celular"], self._fila(linhas, videos))

    def test_A_desistido_libera_o_B(self):
        """Desistir de um VIDEO nao pode virar desistir do TITULO."""
        linhas = [
            _linha("g67:build:celular", "youtube", "2026-09-15T10:00", "Erik"),
            _linha("g67:build:celular:B", "youtube", "2026-09-15T11:00", "Erik"),
        ]
        videos = [_Video("g67:build:celular", "Erik"),
                  _Video("g67:build:celular:B", "Erik")]
        fila = self._fila(linhas, videos, desistidos=["g67:build:celular"])
        self.assertEqual(["g67:build:celular:B"], fila)

    # ---------------------------------------------------- data de corte
    def test_build_anterior_ao_corte_fica_de_fora(self):
        linhas = [_linha("g5:build:celular", "youtube", "2026-08-30T10:00", "Velho")]
        fila = self._fila(linhas, [_Video("g5:build:celular", "Velho")])
        self.assertEqual([], fila, "agosto nunca teve chance de ir ao TikTok")

    def test_build_depois_do_corte_entra(self):
        linhas = [_linha("g6:build:celular", "youtube", "2026-09-14T10:00", "Novo")]
        fila = self._fila(linhas, [_Video("g6:build:celular", "Novo")])
        self.assertEqual(["g6:build:celular"], fila)

    def test_historias_NAO_tem_corte(self):
        """A fila de historias ja drenava com partes de 09/09 nela."""
        linhas = [_linha("h3:celular:p03", "youtube", "2026-09-09T10:00", "P3")]
        fila = self._fila(linhas, [_Video("h3:celular:p03", "P3")],
                          canal="historias")
        self.assertEqual(["h3:celular:p03"], fila)

    # ---------------------------------------------------- ordem e catalogo
    def test_a_ordem_e_a_do_ledger(self):
        linhas = [
            _linha("z:build:celular", "youtube", "2026-09-11T10:00", "Zebra"),
            _linha("a:build:celular", "youtube", "2026-09-12T10:00", "Abacate"),
        ]
        videos = [_Video("z:build:celular", "Zebra"),
                  _Video("a:build:celular", "Abacate")]
        self.assertEqual(["z:build:celular", "a:build:celular"],
                         self._fila(linhas, videos),
                         "ordenar por id jogaria a cronologia fora")

    def test_fora_do_catalogo_nao_trava_a_fila(self):
        linhas = [
            _linha("sumiu:build:celular", "youtube", "2026-09-11T10:00", "Sumiu"),
            _linha("ok:build:celular", "youtube", "2026-09-12T10:00", "Ok"),
        ]
        self.assertEqual(["ok:build:celular"],
                         self._fila(linhas, [_Video("ok:build:celular", "Ok")]))


class DesistenciasTests(unittest.TestCase):
    def test_arquivo_ausente_e_ninguem_desistiu(self):
        with TemporaryDirectory() as tmp:
            with patch.object(postar, "_arquivo_de_desistencias",
                              return_value=Path(tmp) / "nao_existe.json"):
                self.assertEqual(set(), postar.desistencias_do_tiktok("builds"))

    def test_so_conta_quem_bateu_o_limite(self):
        with TemporaryDirectory() as tmp:
            arq = Path(tmp) / "d.json"
            arq.write_text(json.dumps({"a": 3, "b": 2, "c": 9}),
                           encoding="utf-8")
            with patch.object(postar, "_arquivo_de_desistencias",
                              return_value=arq):
                self.assertEqual({"a", "c"},
                                 postar.desistencias_do_tiktok("builds"))

    def test_estado_ilegivel_nao_barra_ninguem(self):
        """"Nao sei" deixa passar: barrar por arquivo corrompido seria
        perder video por causa de um byte."""
        with TemporaryDirectory() as tmp:
            arq = Path(tmp) / "d.json"
            arq.write_text("{isto nao e json", encoding="utf-8")
            with patch.object(postar, "_arquivo_de_desistencias",
                              return_value=arq):
                self.assertEqual(set(), postar.desistencias_do_tiktok("builds"))


class VarianteTests(unittest.TestCase):
    def test_reconhece_a_variante_sem_depender_do_alfabeto(self):
        self.assertTrue(postar._e_variante("g1:build:celular:B"))
        self.assertFalse(postar._e_variante("g1:build:celular"))


if __name__ == "__main__":
    unittest.main()
