"""A capa do video (Onda 15D) — que ate agora nao existia.

Nenhum dos 32 videos publicados tem miniatura propria: `youtube.py` nunca
chamou `thumbnails/set` e `youtube_web.py` nao tinha campo de capa. O
YouTube escolhe um frame qualquer.

A capa cumpre a decisao 2 da onda: a arte de IA sai do CORPO do video —
ocupava 12 s dos 62 e criava o contraste entre uma guerreira cinematografica
e duas bolinhas lisas — e passa a trabalhar onde funciona, vendendo o
clique fora do feed.

O que estes testes travam, alem do formato: que a capa seja ENFEITE. Ela
nao pode derrubar uma publicacao bem-sucedida, nao pode depender de rede, e
nao pode sumir quando os dois caminhos de upload falham.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from builds.generation.session_generator import load_config
from builds.publicar import capa as capa_mod
from builds.publicar import catalogo, youtube

RENDER = load_config("render.json")


def _fight(titulo=False, revanche=False) -> dict:
    return {"seed": 7, "luta": {
        "p1": "Kael", "p2": "Lyra",
        "p1_ficha": {"cor_r": 50, "cor_g": 200, "cor_b": 255,
                     "arma_tipo": "Reta", "nome_arma": "Vurdak"},
        "p2_ficha": {"cor_r": 255, "cor_g": 90, "cor_b": 60,
                     "arma_tipo": "Arco", "nome_arma": "Iskimantr"},
        "vencedor": "Kael", "ko_type": "KO",
        "titulo": titulo, "revanche": revanche}}


class FormatoDaCapaTests(unittest.TestCase):
    def test_sai_na_dimensao_e_no_peso_que_o_youtube_aceita(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = capa_mod.gerar(_fight(), Path(tmp), RENDER)
            self.assertTrue(caminho.is_file())
            self.assertEqual((1280, 720), Image.open(caminho).size)
            self.assertLessEqual(caminho.stat().st_size, capa_mod.PESO_MAXIMO)

    def test_nao_depende_de_rede_nem_de_arte_de_ia(self):
        """Lutador do banco que nunca passou pela roleta nao tem arte.

        A capa cai no glifo da arma na cor dele, em vez de nao existir.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(capa_mod, "arte_do_personagem", return_value=None):
                caminho = capa_mod.gerar(_fight(), Path(tmp), RENDER)
            self.assertTrue(caminho.is_file())

    def test_usa_a_arte_de_ia_quando_ela_existe(self):
        """E a decisao 2 da onda: a arte sai do video e vira capa."""
        with tempfile.TemporaryDirectory() as tmp:
            arte = Path(tmp) / "arte.png"
            Image.new("RGB", (512, 768), (10, 200, 30)).save(arte)
            with patch.object(capa_mod, "arte_do_personagem",
                              side_effect=lambda n: arte if n == "Kael" else None):
                com = capa_mod.gerar(_fight(), Path(tmp), RENDER,
                                     destino=Path(tmp) / "com.png")
            with patch.object(capa_mod, "arte_do_personagem", return_value=None):
                sem = capa_mod.gerar(_fight(), Path(tmp), RENDER,
                                     destino=Path(tmp) / "sem.png")
            self.assertNotEqual(com.read_bytes(), sem.read_bytes())

    def test_arte_ilegivel_cai_no_glifo_em_vez_de_explodir(self):
        with tempfile.TemporaryDirectory() as tmp:
            quebrada = Path(tmp) / "quebrada.png"
            quebrada.write_bytes(b"isto nao e uma imagem")
            with patch.object(capa_mod, "arte_do_personagem",
                              return_value=quebrada):
                self.assertTrue(capa_mod.gerar(_fight(), Path(tmp), RENDER).is_file())

    def test_o_selo_do_confronto_entra_na_capa(self):
        """Titulo e revanche sao o unico texto que diz por que ESTE
        confronto importa. Sao os mesmos do video, vindos do ledger."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(capa_mod, "arte_do_personagem", return_value=None):
                com = capa_mod.gerar(_fight(titulo=True), Path(tmp), RENDER,
                                     destino=Path(tmp) / "com.png")
                sem = capa_mod.gerar(_fight(), Path(tmp), RENDER,
                                     destino=Path(tmp) / "sem.png")
            self.assertNotEqual(com.read_bytes(), sem.read_bytes())

    def test_a_arte_e_procurada_pelo_nome_do_personagem(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp) / "generation_00001"
            pasta.mkdir()
            (pasta / "insercao.json").write_text(
                json.dumps({"personagem": "Kael"}), encoding="utf-8")
            Image.new("RGB", (64, 64)).save(pasta / "character_image.png")
            with patch.object(capa_mod, "OUTPUTS", Path(tmp)):
                self.assertIsNotNone(capa_mod.arte_do_personagem("Kael"))
                self.assertIsNone(capa_mod.arte_do_personagem("Lyra"))
                self.assertIsNone(capa_mod.arte_do_personagem(""))


class CapaNoCatalogoTests(unittest.TestCase):
    def test_a_capa_da_pasta_entra_no_video_e_no_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp) / "duelo_00001"
            pasta.mkdir()
            (pasta / "capa.png").write_bytes(b"x")
            video = catalogo.Video(
                id="d:duelo:celular", origem="duelo", perfil="celular",
                caminho=pasta / "final_celular.mp4", titulo="Kael x Lyra",
                descricao="", capa=pasta / "capa.png")
            video.caminho.write_bytes(b"mp4")
            alvo = catalogo.exportar(video, destino=Path(tmp) / "export")
            self.assertTrue(alvo.with_suffix(".png").is_file(),
                            "a capa tem que viajar junto com o mp4")

    def test_video_sem_capa_continua_exportando(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp) / "duelo_00002"
            pasta.mkdir()
            video = catalogo.Video(
                id="d:duelo:celular", origem="duelo", perfil="celular",
                caminho=pasta / "final_celular.mp4", titulo="Kael x Lyra",
                descricao="")
            video.caminho.write_bytes(b"mp4")
            self.assertTrue(catalogo.exportar(
                video, destino=Path(tmp) / "export").is_file())

    def test_o_campo_novo_entrou_no_fim_do_to_dict(self):
        """Chaves antigas intactas: quem compara o dicionario nao quebra."""
        dados = catalogo.Video(id="x", origem="duelo", perfil="celular",
                               caminho=Path("x.mp4"), titulo="t",
                               descricao="d").to_dict()
        self.assertIsNone(dados["capa"])
        for chave in ("id", "origem", "perfil", "caminho", "titulo",
                      "descricao", "hashtags", "fonte_id", "rotulo", "bytes",
                      "quando", "variante", "pendencias"):
            self.assertIn(chave, dados)


class UploadDaCapaTests(unittest.TestCase):
    """A capa e enfeite: falhar nela nao pode custar a publicacao."""

    class _Resposta:
        def __init__(self, ok=True, status=200, texto=""):
            self.ok, self.status_code, self.text = ok, status, texto

    def _capa(self, tmp) -> Path:
        caminho = Path(tmp) / "capa.png"
        Image.new("RGB", (1280, 720)).save(caminho)
        return caminho

    def test_a_api_chama_o_endpoint_de_miniatura(self):
        with tempfile.TemporaryDirectory() as tmp:
            chamadas = {}

            def falso_post(url, **kw):
                chamadas["url"] = url
                chamadas["params"] = kw.get("params")
                return self._Resposta()

            with patch.object(youtube, "carregar_credenciais",
                              return_value=object()), \
                 patch.object(youtube, "token_de_acesso", return_value="t"), \
                 patch.dict("sys.modules", {"requests": type(
                     "M", (), {"post": staticmethod(falso_post)})}):
                self.assertTrue(youtube.definir_capa("abc123", self._capa(tmp)))
            self.assertEqual(youtube.API_THUMBNAIL, chamadas["url"])
            self.assertEqual({"videoId": "abc123"}, chamadas["params"])

    def test_recusa_do_google_nao_levanta(self):
        """403 de canal sem verificacao e comum e nao e falha do upload."""
        with tempfile.TemporaryDirectory() as tmp:
            def falso_post(url, **kw):
                return self._Resposta(ok=False, status=403, texto="sem verificacao")

            with patch.object(youtube, "carregar_credenciais",
                              return_value=object()), \
                 patch.object(youtube, "token_de_acesso", return_value="t"), \
                 patch.dict("sys.modules", {"requests": type(
                     "M", (), {"post": staticmethod(falso_post)})}):
                self.assertFalse(youtube.definir_capa("abc123", self._capa(tmp)))

    def test_sem_credencial_nao_levanta(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(youtube, "carregar_credenciais", return_value=None):
                self.assertFalse(youtube.definir_capa("abc", self._capa(tmp)))

    def test_capa_inexistente_e_id_vazio_sao_ignorados(self):
        self.assertFalse(youtube.definir_capa("abc", Path("nao_existe.png")))
        self.assertFalse(youtube.definir_capa("", None))

    def test_o_id_sai_das_duas_formas_de_url(self):
        for url, esperado in (("https://youtu.be/Qx0ybHmoHJM", "Qx0ybHmoHJM"),
                              ("https://youtube.com/shorts/AbC123xyz", "AbC123xyz"),
                              ("https://www.youtube.com/watch?v=ZZ99zz88", "ZZ99zz88")):
            with self.subTest(url=url):
                achado = youtube._ID_NA_URL.search(url)
                self.assertIsNotNone(achado)
                self.assertEqual(esperado, achado.group(1))

    def test_o_navegador_tem_seletor_proprio_para_a_miniatura(self):
        """O Studio tem DOIS inputs de arquivo; o generico pegaria o video."""
        from builds.publicar import youtube_web

        self.assertTrue(youtube_web.ENTRADA_MINIATURA)
        for seletor in youtube_web.ENTRADA_MINIATURA:
            with self.subTest(seletor=seletor):
                self.assertNotEqual(youtube_web.ENTRADA_ARQUIVO, seletor)


if __name__ == "__main__":
    unittest.main()
