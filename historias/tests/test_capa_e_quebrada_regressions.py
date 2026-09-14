# -*- coding: utf-8 -*-
"""A capa das historias e a categoria caricata (11/09/2026).

DUAS COISAS QUE NASCERAM DO MESMO PRINT. Na prateleira de Shorts da casa do
YouTube, nosso video aparecia como um frame cru sem uma letra na tela, ao
lado de concorrentes com titulo em corpo 120 e arte desenhada. O video JA
desenhava o titulo, mas por 2,2 s com fade — e a miniatura que o YouTube
escolhe sozinho quase nunca cai nesses 2,2 s.

O que este arquivo trava:

1. A capa sai vertical (1080x1920), cabe no teto de 2 MB do YouTube e nunca
   derruba o render quando falha.
2. `(Parte 6)` nao aparece DUAS vezes: o selo amarelo ja diz a parte.
3. Nenhuma linha do titulo e uma palavra curta sozinha — "A VERDADEIRA FACE"
   saia como "A" / "VERDADEIRA" / "FACE", com uma letra ocupando 150 px.
4. O molde `quebrada` troca pessoa, regras e estilo de imagem; os tres moldes
   confessionais continuam intactos.
5. `_comment_*` dentro de `modelos` nao vira molde sorteavel.

    cd e:\\projetos\\historias
    python -m pytest tests/test_capa_e_quebrada_regressions.py -q
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from contos.imagens import fila
from contos.roteiro import serie
from contos.video import capa


class CapaTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.cfg = {"colors": {"accent": "#ffb703", "text": "#f7f3ea",
                               "bg_top": "#0d0b12", "bg_bottom": "#191320"},
                    "fonts": {"black": "C:/Windows/Fonts/ariblk.ttf"}}

    def _cena(self, largura=1080, altura=1920) -> Path:
        alvo = self.pasta / "cena.png"
        Image.new("RGB", (largura, altura), (90, 120, 150)).save(alvo)
        return alvo

    def test_sai_vertical_no_tamanho_do_shorts(self):
        """16:9 chegaria recortada pelas beiradas na prateleira de Shorts, e
        o titulo e justamente a parte que precisa sobreviver ao recorte."""
        destino = capa.montar("Um titulo qualquer", self._cena(),
                              self.pasta / "capa.jpg", config_render=self.cfg)
        with Image.open(destino) as img:
            self.assertEqual((capa.LARGURA, capa.ALTURA), img.size)
            self.assertEqual((1080, 1920), img.size)

    def test_cabe_no_teto_do_youtube(self):
        destino = capa.montar("Titulo", self._cena(2160, 3840),
                              self.pasta / "capa.jpg", config_render=self.cfg)
        self.assertLessEqual(destino.stat().st_size, capa.PESO_MAXIMO)

    def test_sem_imagem_a_capa_ainda_sai(self):
        """Uma capa feia ganha de nenhuma capa — 'nenhuma' e o frame que o
        YouTube escolher sozinho, que e o estado que estamos consertando."""
        destino = capa.montar("Titulo sem cena", None,
                              self.pasta / "capa.jpg", config_render=self.cfg)
        self.assertTrue(destino.is_file())

    def test_cena_horizontal_nao_e_espremida(self):
        destino = capa.montar("Titulo", self._cena(1920, 1080),
                              self.pasta / "capa.jpg", config_render=self.cfg)
        with Image.open(destino) as img:
            self.assertEqual((capa.LARGURA, capa.ALTURA), img.size)

    def test_o_selo_da_parte_nao_repete_no_titulo(self):
        self.assertEqual("A verdadeira face",
                         capa.sem_o_selo("A verdadeira face (Parte 6)"))
        self.assertEqual("A verdadeira face",
                         capa.sem_o_selo("A verdadeira face [parte 12]"))

    def test_titulo_sem_selo_fica_como_esta(self):
        self.assertEqual("O troféu de aluguel",
                         capa.sem_o_selo("O troféu de aluguel"))

    def test_parte_no_meio_do_titulo_nao_e_cortada(self):
        """So o sufixo. 'A parte 2 do contrato' e o titulo, nao um selo."""
        self.assertEqual("A parte 2 do contrato",
                         capa.sem_o_selo("A parte 2 do contrato"))

    def test_nenhuma_linha_e_uma_palavra_curta_sozinha(self):
        fonte, linhas = capa._fonte_e_linhas(
            "A VERDADEIRA FACE", self.cfg["fonts"]["black"], 972)
        self.assertFalse(capa._tem_orfa(linhas), f"saiu orfa: {linhas}")
        self.assertEqual(["A VERDADEIRA", "FACE"], linhas)

    def test_o_corpo_escolhido_cabe_na_largura(self):
        largura = 972
        fonte, linhas = capa._fonte_e_linhas(
            "O SEGREDO QUE A VIZINHANCA INTEIRA GUARDOU POR ANOS",
            self.cfg["fonts"]["black"], largura)
        for linha in linhas:
            self.assertLessEqual(fonte.getlength(linha), largura)
        self.assertLessEqual(len(linhas), capa.MAX_LINHAS)

    def test_uma_palavra_so_nao_trava_a_busca(self):
        fonte, linhas = capa._fonte_e_linhas("OI", self.cfg["fonts"]["black"],
                                             972)
        self.assertEqual(["OI"], linhas)

    def test_o_caminho_segue_a_regra_do_catalogo(self):
        """Sem sufixo quando ha uma parte so — a mesma regra do id do video."""
        self.assertEqual("capa_p04.jpg", capa.caminho(self.pasta, 4, 6).name)
        self.assertEqual("capa.jpg", capa.caminho(self.pasta, 1, 1).name)


class ImagemVerticalTests(unittest.TestCase):
    """Nao basta o arquivo existir: ele precisa ser o que foi PEDIDO.

    Medido em 11/09/2026, na primeira historia do genero caricato: 18 cenas
    voltaram 1088x1920 e uma voltou 1024x1024, com o PicassoIA ignorando o
    seletor de 9:16. `utilizavel` so olhava bytes, entao a quadrada passou
    como pronta, o worker nunca refez, e ela entrou no video — preenchida com
    fundo borrado, com cara de outra producao no meio da historia.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _png(self, nome: str, tamanho: tuple) -> Path:
        alvo = self.pasta / nome
        # Ruido, e nao cor chapada: PNG de cor unica comprime a quase nada e
        # cairia no piso de bytes, testando a guarda errada.
        imagem = Image.effect_noise(tamanho, 64).convert("RGB")
        imagem.save(alvo)
        return alvo

    def test_a_quadrada_nao_conta_como_pronta(self):
        self.assertFalse(fila.vertical(self._png("q.png", (1024, 1024))))

    def test_a_paisagem_nao_conta_como_pronta(self):
        self.assertFalse(fila.vertical(self._png("p.png", (1920, 1080))))

    def test_o_que_o_picasso_devolve_certo_passa(self):
        self.assertTrue(fila.vertical(self._png("v.png", (1088, 1920))))

    def test_retrato_3x4_ainda_cabe(self):
        """3:4 nao e 9:16, mas e retrato e cabe com um corte suave. O teto e
        folgado de proposito: refazer imagem custa minuto e conta compartilhada."""
        self.assertTrue(fila.vertical(self._png("r.png", (1080, 1440))))

    def test_arquivo_ilegivel_nao_e_recusado_aqui(self):
        """Quem recusa por tamanho e `utilizavel`. Recusar de novo aqui
        esconderia a causa real atras de 'nao e vertical'."""
        quebrado = self.pasta / "quebrado.png"
        quebrado.write_bytes(b"nao sou png")
        self.assertTrue(fila.vertical(quebrado))

    def test_utilizavel_junta_as_duas_guardas(self):
        self.assertTrue(fila.utilizavel(self._png("ok.png", (1088, 1920))))
        self.assertFalse(fila.utilizavel(self._png("nao.png", (1024, 1024))))
        self.assertFalse(fila.utilizavel(self.pasta / "nem_existe.png"))


class CapaNoCatalogoTests(unittest.TestCase):

    def test_a_capa_chega_ao_upload_pelo_catalogo(self):
        """`youtube_web` le `video.capa`. Sem o campo no catalogo de
        historias, a capa ficava no disco e nunca subia."""
        from contos.publicar.catalogo import Video
        self.assertIn("capa", Video.__dataclass_fields__)


class MoldeQuebradaTests(unittest.TestCase):

    def setUp(self):
        self.cfg = serie.carregar_config()

    def test_comentario_nao_vira_molde_sorteavel(self):
        """O arquivo documenta cada bloco com um `_comment_` irmao. Dentro de
        `modelos` isso criava um molde fantasma que o rodizio escolheria."""
        moldes = serie.moldes_disponiveis(self.cfg)
        self.assertNotIn("_comment_quebrada", moldes)
        self.assertIn("quebrada", moldes)

    def test_a_quebrada_e_em_terceira_pessoa(self):
        prompt = serie.prompt_biblia(partes=3, cenas_por_parte=10,
                                     config=self.cfg, estrutura="quebrada",
                                     narrador="mulher")
        self.assertIn("narrador de fora", prompt)
        self.assertNotIn("na primeira pessoa", prompt)

    def test_a_quebrada_traz_as_regras_dela(self):
        prompt = serie.prompt_biblia(partes=3, cenas_por_parte=10,
                                     config=self.cfg, estrutura="quebrada")
        self.assertIn("APELIDO no lugar de nome", prompt)
        self.assertNotIn("DESABAFO que uma pessoa real", prompt,
                         "as regras do relato confessional pedem o oposto do "
                         "genero caricato; as duas juntas nao entregam nenhum")

    def test_o_limite_de_menor_continua_valendo_na_quebrada(self):
        """O guarda-corpo e incondicional desde 09/09. Genero novo nao o tira."""
        prompt = serie.prompt_biblia(partes=3, cenas_por_parte=10,
                                     config=self.cfg, estrutura="quebrada")
        self.assertIn("NINGUEM menor de 18 anos", prompt)

    def test_a_quebrada_nao_faz_piada_de_crime(self):
        """Nao e pudor: e o que derruba o video e faz a imagem ser recusada."""
        regras = " ".join(self.cfg["modelos"]["quebrada"]["regras"]).lower()
        self.assertIn("nunca crime", regras)
        self.assertIn("faccao", regras)

    def test_os_moldes_confessionais_seguem_iguais(self):
        prompt = serie.prompt_biblia(partes=3, cenas_por_parte=10,
                                     config=self.cfg, estrutura="reddit",
                                     narrador="mulher")
        self.assertIn("na primeira pessoa", prompt)
        self.assertIn("DESABAFO que uma pessoa real", prompt)

    def test_a_quebrada_usa_o_estilo_fotografico_de_todas(self):
        """Ate 14/09/2026 a quebrada tinha estilo proprio (render 3D estilo
        Pixar). Pedido dele: "abandone completamente essa ideia da pixar" —
        o personagem ia e voltava entre cenas. Agora ela cai no estilo
        fotografico do `imagens.json`, como os outros moldes. O mecanismo de
        estilo por molde continua (os dois testes abaixo)."""
        self.assertEqual("", fila.estilo_do_roteiro({"estrutura": "quebrada"}))
        self.assertEqual("", fila.estilo_do_roteiro({"estrutura": "reddit"}))
        self.assertEqual("", fila.estilo_do_roteiro({}))

    def test_o_estilo_do_molde_ganha_do_arquivo(self):
        prompt = fila.prompt_da_cena({"imagem": "a woman opens a door"},
                                     {"estilo": "photorealistic"},
                                     estilo="flat cartoon")
        self.assertIn("flat cartoon", prompt)
        self.assertNotIn("photorealistic", prompt)

    def test_sem_estilo_do_molde_vale_o_do_arquivo(self):
        prompt = fila.prompt_da_cena({"imagem": "a woman opens a door"},
                                     {"estilo": "photorealistic"})
        self.assertIn("photorealistic", prompt)


if __name__ == "__main__":
    unittest.main()
