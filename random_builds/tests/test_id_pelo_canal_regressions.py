"""Sem `youtube_id` o video fica invisivel para tudo que nao seja o olho.

MEDIDO EM 17/09/2026: 16 linhas de YouTube sem `youtube_id` — 8 de builds e
8 de historias — e o `prova` delas igualmente vazio. A segunda fonte do id
(a URL da pagina do Studio, que entrou em 16/09) nao salvou NENHUMA.

O que se perde sem ele: a metrica nao tem a que se ligar, a conferencia por
API nao tem o que conferir, e a capa nao tem para onde ir. As 111 capas que
nunca subiram tem tres causas, e esta e a unica que e codigo — as outras duas
sao que o build nao gera arquivo de capa (4 de 305 itens tem) e que o canal
das historias nao e verificado por telefone (403 literal do YouTube).

O CANAL SABE. Casando por titulo e janela de tempo, as 8 de builds
resolveram com 0 minuto de diferenca, e as 3 de historias do dia tambem. (As
5 de historias de 09-10/09 nao tem titulo correspondente no canal — problema
diferente e mais feio, que nao e deste conserto.)

AMBIGUO DEVOLVE VAZIO, e e a regra que importa aqui: gravar o id errado e
pior que nao gravar nenhum, porque a metrica passaria a medir outro video em
silencio, para sempre.
"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from builds.publicar import recuperar


def _video(vid, titulo, quando):
    return {"id": vid, "titulo": titulo, "descricao": "x", "quando": quando,
            "privacidade": "public", "upload": "processed", "duracao": "PT1M"}


class IdNoCanalTests(unittest.TestCase):
    AGORA = datetime(2026, 9, 17, 15, 42, tzinfo=timezone(timedelta(hours=-3)))

    def _com(self, videos):
        return patch.object(recuperar, "videos_do_canal",
                            lambda _c=None, _t=None: videos)

    def test_acha_pelo_titulo_e_pela_hora(self):
        with self._com([_video("xm4R", "Nyxaris, Feiticeiro — build 60/100",
                               "2026-09-17T18:41:00Z")]):
            self.assertEqual("xm4R", recuperar.id_no_canal(
                "builds", "Nyxaris, Feiticeiro — build 60/100", self.AGORA))

    def test_o_LEDGER_e_local_e_o_YOUTUBE_e_UTC(self):
        """Comparar os dois como se fossem o mesmo relogio da 180 minutos de
        diferenca — bem dentro de uma janela generosa, e casando com o video
        errado."""
        certo = _video("certo", "mesmo titulo", "2026-09-17T18:41:00Z")
        # 15:42 UTC seria "o mesmo numero" lido errado: 3 h antes de verdade.
        engano = _video("engano", "mesmo titulo", "2026-09-17T15:42:00Z")
        with self._com([certo, engano]):
            self.assertEqual("certo", recuperar.id_no_canal(
                "builds", "mesmo titulo", self.AGORA, janela_min=60))

    def test_fora_da_janela_nao_conta(self):
        with self._com([_video("velho", "mesmo titulo",
                               "2026-09-15T18:41:00Z")]):
            self.assertEqual("", recuperar.id_no_canal(
                "builds", "mesmo titulo", self.AGORA))

    def test_titulo_diferente_nao_conta(self):
        with self._com([_video("outro", "outra coisa qualquer",
                               "2026-09-17T18:41:00Z")]):
            self.assertEqual("", recuperar.id_no_canal(
                "builds", "mesmo titulo", self.AGORA))

    def test_AMBIGUO_devolve_vazio(self):
        """Gravar o id errado e pior que nao gravar: a metrica mediria outro
        video, em silencio, para sempre."""
        with self._com([_video("a", "mesmo titulo", "2026-09-17T18:41:00Z"),
                        _video("b", "mesmo titulo", "2026-09-17T18:44:00Z")]):
            self.assertEqual("", recuperar.id_no_canal(
                "builds", "mesmo titulo", self.AGORA))

    # --------------------------------------------- a parte que virou dois
    def test_os_DOIS_pedacos_sao_a_resposta_certa(self):
        """Dois candidatos nem sempre e empate. Uma parte longa vira dois
        Shorts e o ledger guarda UMA linha para os dois."""
        with self._com([
                _video("b", "A parte (Parte 4) (2 de 2)",
                       "2026-09-17T18:44:00Z"),
                _video("a", "A parte (Parte 4) (1 de 2)",
                       "2026-09-17T18:41:00Z")]):
            self.assertEqual(["a", "b"], recuperar.ids_no_canal(
                "historias", "A parte (Parte 4)", self.AGORA),
                "na ordem do corte, e nao na de chegada")

    def test_o_campo_antigo_aponta_para_o_PRIMEIRO(self):
        """`youtube_id` guarda um id so e muita coisa o le assim."""
        with self._com([
                _video("a", "A parte (Parte 4) (1 de 2)",
                       "2026-09-17T18:41:00Z"),
                _video("b", "A parte (Parte 4) (2 de 2)",
                       "2026-09-17T18:44:00Z")]):
            self.assertEqual("a", recuperar.id_no_canal(
                "historias", "A parte (Parte 4)", self.AGORA))

    def test_o_MESMO_pedaco_duas_vezes_continua_ambiguo(self):
        """Duas copias de "(1 de 2)" sao duplicata no canal, nao as metades
        de uma parte — e ai nao da para escolher."""
        with self._com([
                _video("a", "A parte (Parte 4) (1 de 2)",
                       "2026-09-17T18:41:00Z"),
                _video("b", "A parte (Parte 4) (1 de 2)",
                       "2026-09-17T18:44:00Z")]):
            self.assertEqual([], recuperar.ids_no_canal(
                "historias", "A parte (Parte 4)", self.AGORA))

    def test_titulo_vazio_nem_pergunta(self):
        chamou = []
        with patch.object(recuperar, "videos_do_canal",
                          lambda *a, **k: chamou.append(1) or []):
            self.assertEqual("", recuperar.id_no_canal("builds", "",
                                                       self.AGORA))
        self.assertEqual([], chamou, "sem titulo nao ha o que casar")

    def test_aceita_a_hora_como_texto(self):
        with self._com([_video("x", "mesmo titulo", "2026-09-17T18:41:00Z")]):
            self.assertEqual("x", recuperar.id_no_canal(
                "builds", "mesmo titulo", "2026-09-17T15:42:00"))


class NoPublicadorTests(unittest.TestCase):
    """O id tem de chegar na LINHA do ledger, e nao so no laudo."""

    def _fonte(self):
        import inspect
        from builds.publicar import youtube
        return inspect.getsource(youtube.publicar_como_configurado)

    def test_pergunta_ao_canal_quando_falta_o_id(self):
        self.assertIn("id_do_video(", self._fonte())

    def test_o_id_vai_para_o_extra_do_registro(self):
        """`registrar_publicacao` extrai o id da URL; sem URL a linha nascia
        com `youtube_id: null` — invisivel para a metrica para sempre."""
        fonte = self._fonte()
        i_extra = fonte.find("extra={")
        self.assertNotEqual(-1, i_extra)
        self.assertIn('"youtube_id": video_id', fonte[i_extra:])

    def test_a_capa_usa_o_id_e_nao_so_a_URL(self):
        fonte = self._fonte()
        i_capa = fonte.find("definir_capa(")
        self.assertNotEqual(-1, i_capa)
        self.assertIn("definir_capa(video_id", fonte[i_capa - 20:])

    def test_perguntar_NAO_pode_derrubar_a_publicacao(self):
        """Publicacao feita nao vira falha porque a consulta de conferencia
        nao respondeu."""
        fonte = self._fonte()
        trecho = fonte[fonte.find("id_do_video("):]
        self.assertIn("except", trecho)



class IdDoPedacoTests(unittest.TestCase):
    """O id do ARQUIVO que acabou de subir, e nao o da linha do ledger.

    MEDIDO EM 28/09/2026: nenhuma linha do ledger tem dois laudos desde que o
    laudo existe (nenhuma parte passou de 180 s desde entao) — o defeito e
    latente. Mas toda parte longa passaria por ele: o pedaco 2 sobe minutos
    depois do pedaco 1, a busca por titulo acha os dois, e `id_no_canal`
    devolve o PRIMEIRO. O laudo do pedaco 2 ganhava o id do pedaco 1, e a capa
    do 2 ia parar no 1.
    """
    AGORA = datetime(2026, 9, 17, 15, 45, tzinfo=timezone(timedelta(hours=-3)))

    def _com(self, videos):
        return patch.object(recuperar, "videos_do_canal",
                            lambda _c=None, _t=None: videos)

    def _dois_pedacos(self):
        return self._com([
            _video("a", "A parte (Parte 4) (1 de 2)", "2026-09-17T18:41:00Z"),
            _video("b", "A parte (Parte 4) (2 de 2)", "2026-09-17T18:44:00Z")])

    def test_o_pedaco_2_ganha_o_id_do_pedaco_2(self):
        with self._dois_pedacos():
            self.assertEqual("b", recuperar.id_do_video(
                "historias", "A parte (Parte 4) (2 de 2)", self.AGORA))
            self.assertEqual("a", recuperar.id_no_canal(
                "historias", "A parte (Parte 4) (2 de 2)", self.AGORA),
                "o defeito: a resposta da LINHA para o arquivo do pedaco 2")

    def test_o_pedaco_1_ganha_o_id_do_pedaco_1(self):
        with self._dois_pedacos():
            self.assertEqual("a", recuperar.id_do_video(
                "historias", "A parte (Parte 4) (1 de 2)", self.AGORA))

    def test_video_inteiro_nao_casa_com_pedaco(self):
        with self._dois_pedacos():
            self.assertEqual("", recuperar.id_do_video(
                "historias", "A parte (Parte 4)", self.AGORA))

    def test_video_inteiro_sozinho_e_o_dele(self):
        with self._com([_video("x", "mesmo titulo", "2026-09-17T18:44:00Z")]):
            self.assertEqual("x", recuperar.id_do_video(
                "builds", "mesmo titulo", self.AGORA))

    def test_o_mesmo_pedaco_duas_vezes_e_ambiguo(self):
        with self._com([
                _video("a", "A parte (Parte 4) (2 de 2)", "2026-09-17T18:41:00Z"),
                _video("b", "A parte (Parte 4) (2 de 2)", "2026-09-17T18:44:00Z")]):
            self.assertEqual("", recuperar.id_do_video(
                "historias", "A parte (Parte 4) (2 de 2)", self.AGORA))


class LinhaDaHistoriaTests(unittest.TestCase):
    """A LINHA do ledger das historias guarda os ids de todos os pedacos.

    `serie.registrar` tira o `youtube_id` da URL — e pelo navegador a "URL" e
    a frase "publicado no YouTube", entao a linha nascia com `youtube_id:
    null` mesmo com o laudo sabendo o id (a linha de 27/09 20:43 da
    `historia_00035:celular:p01`: `null` na linha, `OAjbMHMCutk` no laudo).
    """

    def _postar(self):
        import importlib.util
        from pathlib import Path
        caminho = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"
        spec = importlib.util.spec_from_file_location("postar_ids", caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo

    def test_dois_pedacos_dois_ids_na_ordem(self):
        extra = self._postar()._ids_da_parte(
            [{"youtube_id": "a"}, {"youtube_id": "b"}])
        self.assertEqual({"youtube_id": "a", "youtube_ids": ["a", "b"]}, extra)

    def test_um_arquivo_so_o_id(self):
        extra = self._postar()._ids_da_parte([{"youtube_id": "OAjbMHMCutk"}])
        self.assertEqual({"youtube_id": "OAjbMHMCutk"}, extra)

    def test_pedaco_sem_id_nao_inventa_nem_desloca(self):
        """Com um pedaco sem id, a lista nao pode "subir" o outro para a
        posicao errada: sem os dois, nao ha `youtube_ids`."""
        extra = self._postar()._ids_da_parte([{}, {"youtube_id": "b"}])
        self.assertEqual({}, extra)

    def test_sem_laudo_nada(self):
        self.assertEqual({}, self._postar()._ids_da_parte([]))


if __name__ == "__main__":
    unittest.main()
