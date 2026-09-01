# -*- coding: utf-8 -*-
"""Um login, varios canais: quem decide o destino e o ID do canal.

O caso real (medido em 01/09/2026): os canais do Adrian sao TODOS da mesma
conta Google. Uma sessao ja enxerga os tres — Adrian Oliveira, historinhas e
Neural fights. Duas consequencias:

1. Dar uma pasta de Chrome por conta o obrigaria a logar tres vezes para
   trocar de destino, sendo que o destino nem depende do login. Por isso
   `youtube_web` tem `sessao_unica`: todas as contas dividem o mesmo perfil.
2. Como o login nao separa nada, o que separa e o ID. E se o id nao for
   conferido, o Studio abre no ULTIMO canal usado — foi assim que `builds` e
   `historias` acabaram os dois apontando para o canal PESSOAL dele. Subir
   uma historia no canal de builds nao tem desfazer.

Rode de dentro de random_builds/:
    python -m unittest tests.test_escolher_canal_regressions -v
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from builds import contas                                          # noqa: E402
from builds.publicar import youtube_web                            # noqa: E402


class RegistroTemporario(unittest.TestCase):
    """Cada teste com o seu proprio contas.json — o de verdade fica quieto."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        anterior = contas.ARQUIVO
        contas.ARQUIVO = str(Path(self.pasta.name) / "contas.json")
        self.addCleanup(lambda: setattr(contas, "ARQUIVO", anterior))


class SessaoUnicaTests(RegistroTemporario):
    def test_um_login_serve_todos_os_canais(self):
        contas.escolher("youtube_web", "builds", "neural_fights")
        contas.escolher("youtube_web", "historias", "historinhas")
        self.assertEqual(contas.perfil("youtube_web", "builds"),
                         contas.perfil("youtube_web", "historias"))

    def test_o_tiktok_continua_com_perfil_por_conta(self):
        """`sessao_unica` e do YouTube; o TikTok e login por conta mesmo."""
        contas.escolher("tiktok", "builds", "uma")
        contas.escolher("tiktok", "historias", "outra")
        self.assertNotEqual(contas.perfil("tiktok", "builds"),
                            contas.perfil("tiktok", "historias"))


class IdDoCanalTests(unittest.TestCase):
    def test_le_o_id_da_url(self):
        self.assertEqual(
            "UCA3Y1SaahhDsMj4JKGLbQ-Q",
            youtube_web.id_do_canal(
                "https://studio.youtube.com/channel/UCA3Y1SaahhDsMj4JKGLbQ-Q"
                "/videos/upload"))

    def test_sem_canal_devolve_vazio(self):
        for url in ("https://studio.youtube.com/", "", None):
            self.assertEqual("", youtube_web.id_do_canal(url))

    def test_nao_aceita_id_de_tamanho_errado(self):
        """A varredura solta ja devolveu 11 'canais' que eram base64."""
        self.assertEqual("", youtube_web.id_do_canal(
            "https://x/channel/UCJ7qibHHW3pdvGdCe2yE4pu7a"))


class UsarCanalTests(RegistroTemporario):
    BUILDS = {"nome": "Neural fights", "arroba": "Neural_fights",
              "id": "UCA3Y1SaahhDsMj4JKGLbQ-Q"}
    HIST = {"nome": "historinhas", "arroba": "BemfacilDverdade",
            "id": "UC2S8Z85XCotBNFdstIXpeJw"}

    def test_amarrar_separa_os_destinos(self):
        youtube_web.usar_canal("builds", self.BUILDS)
        youtube_web.usar_canal("historias", self.HIST)

        b = contas.destino("youtube_web", "builds")
        h = contas.destino("youtube_web", "historias")
        self.assertEqual(self.BUILDS["id"], b["id"])
        self.assertEqual(self.HIST["id"], h["id"])
        self.assertNotEqual(b["id"], h["id"])

    def test_amarrar_torna_a_escolha_EXPLICITA(self):
        """Sem isto o painel barra a publicacao — e barra com razao."""
        self.assertFalse(contas.explicita("youtube_web", "historias"))
        youtube_web.usar_canal("historias", self.HIST)
        self.assertTrue(contas.explicita("youtube_web", "historias"))

    def test_a_url_de_upload_mira_o_canal_certo(self):
        youtube_web.usar_canal("builds", self.BUILDS)
        youtube_web.usar_canal("historias", self.HIST)
        self.assertIn(self.BUILDS["id"], youtube_web.url_de_upload("builds"))
        self.assertIn(self.HIST["id"], youtube_web.url_de_upload("historias"))

    def test_guarda_a_arroba_para_o_humano_conferir(self):
        registro = youtube_web.usar_canal("historias", self.HIST)
        self.assertEqual("BemfacilDverdade", registro.get("arroba"))

    def test_dois_canais_no_mesmo_destino_ficam_visiveis(self):
        """O estado REAL de 01/09: builds e historias no mesmo canal."""
        youtube_web.usar_canal("builds", self.HIST)
        youtube_web.usar_canal("historias", self.HIST)
        repetidos = contas.destinos_repetidos("youtube_web")
        self.assertIn(self.HIST["id"], repetidos)
        self.assertEqual({"builds", "historias"},
                         set(repetidos[self.HIST["id"]]))

    def test_destinos_diferentes_nao_acusam_nada(self):
        youtube_web.usar_canal("builds", self.BUILDS)
        youtube_web.usar_canal("historias", self.HIST)
        self.assertEqual({}, contas.destinos_repetidos("youtube_web"))


class ConfereAntesDeEnviarTests(unittest.TestCase):
    """A trava que faltava: conferir onde o Studio ABRIU, nao onde pedi."""

    def setUp(self):
        self.fonte = Path(youtube_web.__file__).read_text(encoding="utf-8")

    def test_publicar_compara_o_id_pedido_com_o_que_abriu(self):
        i = self.fonte.index("def publicar(")
        trecho = self.fonte[i:i + 4000]
        self.assertIn("id_do_canal(page.url)", trecho)
        self.assertIn("raise YouTubeWebFalhou", trecho)
        self.assertIn("nao tem desfazer", trecho)

    def test_sem_id_gravado_ele_avisa_em_vez_de_calar(self):
        i = self.fonte.index("def publicar(")
        trecho = self.fonte[i:i + 4000]
        self.assertIn("nao tem id gravado", trecho)


class ListaDaSessaoTests(unittest.TestCase):
    def test_a_lista_existe_e_o_cli_expoe(self):
        self.assertTrue(callable(youtube_web.canais_da_sessao))
        self.assertTrue(callable(youtube_web.usar_canal))
        fonte = Path(youtube_web.__file__).read_text(encoding="utf-8")
        self.assertIn('"--canais"', fonte)
        self.assertIn('"--usar-canal"', fonte)


if __name__ == "__main__":
    unittest.main()
