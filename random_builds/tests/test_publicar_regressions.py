# -*- coding: utf-8 -*-
"""Regressões da publicação (catálogo, textos e envio ao YouTube).

O que estes testes protegem:

1. Os três lugares onde nascem mp4 (build, estreia, torneio) aparecem no
   MESMO índice — era isso que obrigava a caçar arquivo em pasta.
2. Um dado que falta some da frase em vez de virar "None" ou quebrar o
   título — o texto vai para a plataforma, não para o log.
3. O texto EDITADO vale sobre o gerado, e vale nos dois envios.
4. Exportar produz nome legível + o .txt ao lado (é o que substitui
   "entrar na pasta e renomear na mão").
5. O YouTube recusa cedo e com frase clara quando o token não autoriza
   upload — em vez de 403 no fim de 30 MB enviados.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.publicar import catalogo, youtube                    # noqa: E402

CONFIG = {
    "titulos": {"build": "{personagem}, {classe} — build {nota}/100",
                "estreia": "{personagem} estreia contra {adversario}",
                "torneio": "Torneio de {participantes} — campeão: {campeao}"},
    "descricoes": {"build": "Arma: {arma}\nForça {forca}",
                   "estreia": "{personagem} x {adversario}: {desfecho}",
                   "torneio": "Campeão: {campeao}"},
    "hashtags": {"build": ["#shorts", "#rpg"], "estreia": ["#luta"],
                 "torneio": ["#torneio"]},
    "youtube": {"visibilidade": "private", "categoria": "20"},
}
CONTEUDO = b"v" * (catalogo.BYTES_MINIMOS + 1)


class CatalogoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.outputs = Path(self._tmp.name) / "outputs"
        self.build = self.outputs / "generation_00001"
        self.build.mkdir(parents=True)
        (self.build / "character.json").write_text(json.dumps({
            "nome": "Cobaia", "classe": "Ninja (Velocidade)",
            "nome_arma": "Katana", "forca": 7.0}), encoding="utf-8")
        (self.build / "build.json").write_text(
            json.dumps({"final_score": 80, "verdict_label": "BOA"}),
            encoding="utf-8")
        self._mp4(self.build)

        estreia = self.build / "estreia"
        estreia.mkdir()
        self._mp4(estreia)
        (self.build / "estreia.json").write_text(json.dumps({
            "personagem": "Cobaia", "adversario": "Rival",
            "vencedor": "Cobaia", "ko_type": "KO", "duracao": 30.2}),
            encoding="utf-8")

        torneio = self.outputs / "tournament_00001"
        torneio.mkdir()
        self._mp4(torneio)
        (torneio / "tournament.json").write_text(
            json.dumps({"campeao": "Rival", "participantes": ["a", "b", "c", "d"]}),
            encoding="utf-8")

        self.export = Path(self._tmp.name) / "publicar"
        self._patches = [
            patch.object(catalogo, "OUTPUTS", self.outputs),
            patch.object(catalogo, "pasta_export", lambda config=None: self.export),
        ]
        for p in self._patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._patches])
        self.addCleanup(self._tmp.cleanup)

    def _mp4(self, pasta: Path):
        for perfil in catalogo.PERFIS:
            (pasta / f"final_{perfil}.mp4").write_bytes(CONTEUDO)

    def _listar(self):
        return catalogo.listar(CONFIG)

    # ---------------------------------------------------------------- testes
    def test_os_tres_lugares_entram_no_mesmo_indice(self):
        videos = self._listar()
        origens = {v.origem for v in videos}
        self.assertEqual({catalogo.BUILD, catalogo.ESTREIA, catalogo.TORNEIO},
                         origens)
        # dois perfis por vídeo (celular e normal)
        self.assertEqual(6, len(videos))
        self.assertTrue(all(v.caminho.is_file() for v in videos))

    def test_titulo_usa_os_dados_da_build(self):
        build = next(v for v in self._listar() if v.origem == catalogo.BUILD)
        self.assertEqual("Cobaia, Ninja (Velocidade) — build 80/100",
                         build.titulo)
        estreia = next(v for v in self._listar() if v.origem == catalogo.ESTREIA)
        self.assertIn("estreia contra Rival", estreia.titulo)
        self.assertIn("venceu por KO", estreia.descricao)

    def _generation(self, dados: dict):
        (self.build / "generation.json").write_text(json.dumps(dados),
                                                    encoding="utf-8")

    def _descricao_real(self) -> str:
        """Contra o texto QUE VAI AO AR (config/publicacao.json), nao o dublê.

        A afirmacao de aleatoriedade mora no arquivo de verdade; testar contra
        o template do teste mediria uma frase que ninguem publica.
        """
        with open(ROOT / "config" / "publicacao.json", encoding="utf-8") as fh:
            real = json.load(fh)
        video = next(v for v in catalogo.listar(real)
                     if v.origem == catalogo.BUILD)
        return video.descricao

    def test_sem_escolha_a_descricao_afirma_o_sorteio(self):
        self.assertIn("100% aleatório", self._descricao_real())

    def test_com_atributo_escolhido_a_descricao_para_de_dizer_100_por_cento(self):
        """A descricao vai para a plataforma: nao pode afirmar o que o video nega."""
        self._generation({"escolhas": {"tela": {"classe": "Mago (Arcano)",
                                                "genero": "feminino"}}})
        descricao = self._descricao_real()
        self.assertNotIn("100% aleatório", descricao)
        self.assertIn("Escolhido a dedo", descricao)
        self.assertIn("classe Mago (Arcano)", descricao)

    def test_com_nome_pedido_a_descricao_credita_em_vez_de_afirmar(self):
        self._generation({"nome_pedido": {"nome": "Kaelen", "autor": "@zeca"}})
        descricao = self._descricao_real()
        self.assertNotIn("100% aleatório", descricao)
        self.assertIn("nome veio de vocês", descricao)

    def test_estreia_em_serie_conta_o_placar_e_nao_o_ultimo_round(self):
        """"venceu por KO" descreveria so o round que fechou a melhor de 3."""
        (self.build / "estreia.json").write_text(json.dumps({
            "personagem": "Cobaia", "adversario": "Rival",
            "vencedor": "Cobaia", "ko_type": "KO", "duracao": 30.2,
            "melhor_de": 3, "placar": [2, 1]}), encoding="utf-8")
        estreia = next(v for v in self._listar() if v.origem == catalogo.ESTREIA)
        self.assertIn("venceu por 2 x 1", estreia.descricao)
        self.assertNotIn("venceu por KO", estreia.descricao)

    def test_campo_que_falta_some_em_vez_de_virar_None(self):
        """Título vai para a plataforma: 'None' ali é pior que frase curta."""
        (self.build / "build.json").write_text("{}", encoding="utf-8")
        build = next(v for v in self._listar() if v.origem == catalogo.BUILD)
        self.assertNotIn("None", build.titulo)
        self.assertNotIn("{", build.titulo)
        self.assertTrue(build.titulo.startswith("Cobaia"))

    def test_hashtags_entram_na_descricao_completa(self):
        build = next(v for v in self._listar() if v.origem == catalogo.BUILD)
        self.assertIn("#shorts #rpg", build.descricao_completa)
        self.assertNotIn("#shorts", build.descricao)

    def test_texto_editado_vale_sobre_o_gerado(self):
        build = next(v for v in self._listar() if v.origem == catalogo.BUILD)
        catalogo.salvar_texto(build.id, "Meu título", "Minha descrição",
                              hashtags=["#meu"])
        editado = catalogo.por_id(build.id, CONFIG)
        self.assertEqual("Meu título", editado.titulo)
        self.assertEqual("Minha descrição", editado.descricao)
        self.assertIn("#meu", editado.descricao_completa)

    def test_exportar_da_nome_legivel_e_escreve_o_texto(self):
        build = next(v for v in self._listar() if v.origem == catalogo.BUILD)
        destino = catalogo.exportar(build, config=CONFIG)
        self.assertTrue(destino.is_file())
        self.assertIn("generation_00001", destino.name)
        self.assertIn("Cobaia", destino.name)
        self.assertTrue(destino.name.endswith(".mp4"))
        texto = destino.with_suffix(".txt").read_text(encoding="utf-8")
        self.assertIn(build.titulo, texto)
        self.assertIn("#shorts", texto)

    def test_vertical_identifica_o_corte_de_celular(self):
        videos = self._listar()
        celular = [v for v in videos if v.perfil == "celular"]
        self.assertTrue(all(v.vertical for v in celular))
        self.assertTrue(all(not v.vertical for v in videos if v.perfil == "normal"))


class YouTubeTests(unittest.TestCase):
    def _video(self):
        return catalogo.Video(
            id="x:build:celular", origem=catalogo.BUILD, perfil="celular",
            caminho=Path("nao-existe.mp4"), titulo="T" * 150,
            descricao="descrição", hashtags=["#um", "#dois"],
            fonte_id="generation_00001")

    def test_credencial_sem_upload_recusa_antes_de_enviar(self):
        credencial = youtube.Credenciais("id", "secret", "refresh",
                                         escopo=youtube.ESCOPO_UPLOAD.replace(
                                             "upload", "readonly"))
        self.assertFalse(credencial.tem_upload)
        with patch.object(youtube, "carregar_credenciais",
                          lambda *a, **k: credencial):
            with self.assertRaises(youtube.PublicacaoFalhou) as erro:
                youtube.publicar(self._video(), config=CONFIG)
        self.assertIn("--com-upload", str(erro.exception))

    def test_sem_credencial_diz_o_que_fazer(self):
        with patch.object(youtube, "carregar_credenciais", lambda *a, **k: None):
            with self.assertRaises(youtube.PublicacaoFalhou) as erro:
                youtube.publicar(self._video(), config=CONFIG)
        self.assertIn("OAuth", str(erro.exception))

    def test_visibilidade_invalida_nao_chega_na_rede(self):
        with self.assertRaises(youtube.PublicacaoFalhou):
            youtube.publicar(self._video(), visibilidade="amigos",
                             config=CONFIG)

    def test_corpo_respeita_os_limites_da_api(self):
        corpo = youtube._corpo(self._video(), CONFIG, "private")
        self.assertEqual(100, len(corpo["snippet"]["title"]))
        self.assertEqual(["um", "dois"], corpo["snippet"]["tags"])
        self.assertEqual("private", corpo["status"]["privacyStatus"])
        self.assertEqual("20", corpo["snippet"]["categoryId"])


if __name__ == "__main__":
    unittest.main()
