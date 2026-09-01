# -*- coding: utf-8 -*-
"""Contratos da sessao de triagem (janela "Categorizar assistindo" do painel).

O que este arquivo trava:

1. A fila so contem video, e aceita as extensoes ALEM do catalogo
   (EXTENSOES_TRIAGEM): um .avi do pack entra na fila e vira clipe valido —
   o importador nao filtra extensao de arquivo unico e o renderer normaliza
   tudo via FFmpeg.
2. Caminho colado com aspas ("Copiar como caminho" do Windows) funciona.
   Foi exatamente assim que a primeira versao (web) falhou na mao do usuario.
3. Recarregar a mesma pasta NAO importa duas vezes: arquivo cujo nome ja
   consta como `source` no catalogo nao volta para a fila.
4. Categorizar passa pelo importador OFICIAL: ID sequencial, entrada no
   catalog.json e arquivo na biblioteca — o mesmo contrato do
   `import-reactions`, nunca um caminho paralelo.
5. Desfazer desfaz de verdade nos dois modos: com mover o arquivo volta
   para a pasta de origem; com copia o original nunca saiu de la. Nos dois
   casos a entrada some do catalogo e o arquivo some da biblioteca.
6. Categoria invalida e recusada ANTES de mover qualquer coisa.
7. `resolver` nao deixa um caminho relativo escapar da pasta carregada.

Rode de dentro de random_builds/:
    python -m unittest tests.test_triagem_regressions -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from builds.assets.importer import list_reactions  # noqa: E402
from builds.assets.triagem import SessaoTriagem  # noqa: E402


class TriagemTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.assets = base / "assets"
        self.pack = base / "pack"
        self.pack.mkdir(parents=True)
        (self.pack / "clipe_a.mp4").write_bytes(b"video a")
        (self.pack / "clipe_b.mp4").write_bytes(b"video b")
        (self.pack / "clipe_c.avi").write_bytes(b"video c")
        (self.pack / "leiame.txt").write_bytes(b"nao sou video")
        self.sessao = SessaoTriagem(self.assets)

    def tearDown(self):
        self._tmp.cleanup()

    # ------------------------------------------------------------ contratos
    def test_fila_so_contem_video_e_aceita_avi(self):
        fila = self.sessao.carregar_pasta(str(self.pack))["fila"]
        self.assertEqual(fila, ["clipe_a.mp4", "clipe_b.mp4", "clipe_c.avi"])

    def test_caminho_colado_com_aspas_funciona(self):
        resultado = self.sessao.carregar_pasta(f'"{self.pack}"')
        self.assertEqual(len(resultado["fila"]), 3)

    def test_avi_vira_clipe_da_biblioteca(self):
        self.sessao.carregar_pasta(str(self.pack))
        entrada = self.sessao.categorizar("clipe_c.avi", "funny",
                                          mover=False)["entrada"]
        self.assertTrue((self.assets / "reactions" / entrada["file"]).is_file())
        self.assertEqual(entrada["file"], f"{entrada['id']}.avi")

    def test_recarregar_nao_reimporta(self):
        self.sessao.carregar_pasta(str(self.pack))
        self.sessao.categorizar("clipe_a.mp4", "insane", mover=False)
        # copia: o original continua na pasta, mas nao pode voltar a fila
        recarga = self.sessao.carregar_pasta(str(self.pack))
        self.assertEqual(recarga["fila"], ["clipe_b.mp4", "clipe_c.avi"])
        self.assertEqual(recarga["ja_importados"], 1)

    def test_categorizar_usa_o_importador_oficial(self):
        self.sessao.carregar_pasta(str(self.pack))
        resultado = self.sessao.categorizar("clipe_a.mp4", "funny", mover=False)
        entrada = resultado["entrada"]
        self.assertEqual(entrada["id"], "0001")
        self.assertEqual(entrada["category"], "funny")
        self.assertEqual(entrada["source"], "clipe_a.mp4")
        self.assertTrue((self.assets / "reactions" / entrada["file"]).is_file())
        self.assertEqual(resultado["contagens"]["funny"], 1)
        # e o catalog.json e a MESMA fonte que o list-reactions le
        self.assertEqual([e["id"] for e in list_reactions(self.assets)], ["0001"])

    def test_desfazer_com_mover_devolve_o_arquivo(self):
        self.sessao.carregar_pasta(str(self.pack))
        entrada = self.sessao.categorizar("clipe_a.mp4", "great",
                                          mover=True)["entrada"]
        self.assertFalse((self.pack / "clipe_a.mp4").exists())
        desfeito = self.sessao.desfazer()
        self.assertEqual(desfeito["arquivo"], "clipe_a.mp4")
        self.assertTrue((self.pack / "clipe_a.mp4").is_file())
        self.assertFalse((self.assets / "reactions" / entrada["file"]).exists())
        self.assertEqual(list_reactions(self.assets), [])

    def test_desfazer_com_copia_preserva_o_original(self):
        self.sessao.carregar_pasta(str(self.pack))
        entrada = self.sessao.categorizar("clipe_a.mp4", "bad",
                                          mover=False)["entrada"]
        self.sessao.desfazer()
        self.assertTrue((self.pack / "clipe_a.mp4").is_file())
        self.assertFalse((self.assets / "reactions" / entrada["file"]).exists())
        self.assertEqual(list_reactions(self.assets), [])

    def test_categoria_invalida_nao_move_nada(self):
        self.sessao.carregar_pasta(str(self.pack))
        with self.assertRaises(ValueError):
            self.sessao.categorizar("clipe_a.mp4", "epica", mover=True)
        self.assertTrue((self.pack / "clipe_a.mp4").is_file())
        self.assertEqual(list_reactions(self.assets), [])

    def test_resolver_barra_caminho_fora_da_pasta(self):
        self.sessao.carregar_pasta(str(self.pack))
        with self.assertRaises(ValueError):
            self.sessao.resolver("..\\fora.mp4")


if __name__ == "__main__":
    unittest.main()
