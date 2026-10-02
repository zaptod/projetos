# -*- coding: utf-8 -*-
"""O carregador da arte da esteira (`painel/flutuante/arte_pronta.py`).

Pedido do Adrian em 02/10/2026: "POR QUE A VILA AINDA ESTA DO MESMO
JEITO?" — a esteira aprovava arte e nada na Vila a lia. O que estes testes
seguram, item a item pelo `nome_arquivo` do inventario:

1. TEM ARTE -> USA: casa, grama e terra aprovadas aparecem no desenho;
2. NAO TEM -> RECAI: sem a peca, o desenho de codigo de sempre, byte a byte;
3. .JSON -> CICLO: a folha toca o ciclo da direcao (a linha), no fps e no
   laco do `.json`; pose sem folha propria cai na de ficar parado;
4. a rota do app so serve peca aprovada do inventario (nada de `..`);
5. uma peca aprovada depois de a Vila abrir entra sem reiniciar;
6. o celular escolhe o MESMO quadro que a janela (a conta do `vila.js`).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from painel.flutuante import arte, arte_pronta

GRAMA = (40, 190, 60, 255)
TERRA = (210, 120, 40, 255)
CASA = (220, 30, 30, 255)
CICLOS = [{"nome": n, "quadros": list(range(4 * i, 4 * i + 4)), "fps": 4,
           "loop": True} for i, n in enumerate(
               ("frente", "esquerda", "direita", "costas"))]


def _hash(img) -> str:
    return hashlib.sha1(img.tobytes()).hexdigest()


def _cor_da_celula(n: int) -> tuple:
    return (10 + n * 14, 250 - n * 12, 60 + n * 9, 255)


def _folha_de_teste(destino: Path, celula: int = 64) -> None:
    """4x4 celulas, cada uma com uma bolinha de cor propria na metade de
    baixo (o pe a 8 px do fim da celula: o carregador tem de descer o pe)."""
    img = Image.new("RGBA", (4 * celula, 4 * celula), (0, 0, 0, 0))
    for n in range(16):
        x0, y0 = (n % 4) * celula, (n // 4) * celula
        bolinha = Image.new("RGBA", (celula // 2, celula // 2), _cor_da_celula(n))
        img.paste(bolinha, (x0 + celula // 4, y0 + celula // 2 - 8))
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)


def _inventario(pasta: Path) -> Path:
    animacao = {"ciclo": True, "grade": [4, 4], "ancora": "pes",
                "ciclos": CICLOS}
    itens = [
        {"id": "predio_casa", "nome_arquivo": "predios/casa.png",
         "tipo": "peca", "tamanho": "1024x1024; no mundo 72x64 (x3 no celular)"},
        {"id": "predio_casa_noite", "nome_arquivo": "predios/casa_noite.png",
         "tipo": "peca", "tamanho": "1024x1024; no mundo 72x64 (x3 no celular)"},
        {"id": "chao_grama", "nome_arquivo": "cenario/chao_grama.png",
         "tipo": "peca", "tamanho": "512x512 que emenda nos 4 lados"},
        {"id": "caminho_terra", "nome_arquivo": "cenario/caminho_terra.png",
         "tipo": "peca", "tamanho": "512x512 que emenda nos 4 lados"},
        {"id": "habitante_chatgpt_andar",
         "nome_arquivo": "habitantes/chatgpt/andar.png", "tipo": "folha",
         "tamanho": "folha 1024x1024; no mundo 26x32", "animacao": animacao},
        {"id": "habitante_chatgpt_parado",
         "nome_arquivo": "habitantes/chatgpt/parado.png", "tipo": "folha",
         "tamanho": "folha 1024x1024; no mundo 26x32", "animacao": animacao},
    ]
    caminho = pasta / "inventario.json"
    caminho.write_text(json.dumps({"itens": itens}), encoding="utf-8")
    return caminho


class _ComPasta(unittest.TestCase):
    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="arte_pronta_"))
        self.pasta = self.raiz / "arte_vila"
        self.pasta.mkdir()
        self.inventario = _inventario(self.raiz)
        arte_pronta.usar(self.pasta, self.inventario)

    def tearDown(self):
        arte_pronta.usar(None)
        shutil.rmtree(self.raiz, ignore_errors=True)

    def _aprovar(self, nome_arquivo: str, img: Image.Image | None = None,
                 meta: dict | None = None) -> None:
        destino = self.pasta / nome_arquivo
        destino.parent.mkdir(parents=True, exist_ok=True)
        if img is not None:
            img.save(destino)
        if meta is not None:
            destino.with_suffix(".json").write_text(json.dumps(meta),
                                                    encoding="utf-8")
        arte_pronta.conferir()

    def _casa(self) -> Image.Image:
        img = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
        img.paste(Image.new("RGBA", (300, 200), CASA), (50, 60))
        return img


class SemArteRecai(_ComPasta):
    def test_pasta_vazia_e_o_desenho_de_codigo_byte_a_byte(self):
        antes = {"chao": _hash(arte.desenhar_chao()),
                 "casa": _hash(arte.desenhar_predio("casa")),
                 "noite": _hash(arte.desenhar_predio("casa", True)),
                 "gente": _hash(arte.desenhar_personagem("chatgpt", "passo1"))}
        self.assertIsNone(arte_pronta.peca("predios/casa.png"))
        self.assertIsNone(arte_pronta.habitante("chatgpt", "parado", "dir"))
        self.assertEqual(arte.quadro_do_habitante("chatgpt", "parado", "dir",
                                                  5.0), 0)
        # aprova e tira: volta exatamente ao de antes
        self._aprovar("predios/casa.png", self._casa())
        self.assertNotEqual(_hash(arte.desenhar_predio("casa")), antes["casa"])
        (self.pasta / "predios" / "casa.png").unlink()
        arte_pronta.conferir()
        self.assertEqual(_hash(arte.desenhar_chao()), antes["chao"])
        self.assertEqual(_hash(arte.desenhar_predio("casa")), antes["casa"])
        self.assertEqual(_hash(arte.desenhar_predio("casa", True)),
                         antes["noite"])
        self.assertEqual(_hash(arte.desenhar_personagem("chatgpt", "passo1")),
                         antes["gente"])

    def test_so_a_peca_aprovada_muda_os_vizinhos_ficam_de_codigo(self):
        codigo = _hash(arte.desenhar_predio("gemini"))
        self._aprovar("predios/casa.png", self._casa())
        self.assertEqual(_hash(arte.desenhar_predio("gemini")), codigo)

    def test_png_fora_do_inventario_nao_entra(self):
        self._aprovar("predios/inventado.png", self._casa())
        self.assertNotIn("predios/inventado.png", arte_pronta.indice())
        self.assertIsNone(arte_pronta.peca("predios/inventado.png"))

    def test_inventario_ilegivel_e_nenhuma_arte(self):
        self._aprovar("predios/casa.png", self._casa())
        self.inventario.write_text("{quebrado", encoding="utf-8")
        arte_pronta.usar(self.pasta, self.inventario)
        self.assertEqual(arte_pronta.indice(), {})


class TemArteUsa(_ComPasta):
    def test_casa_aprovada_encaixa_nos_72x64_com_a_base_no_chao(self):
        self._aprovar("predios/casa.png", self._casa())
        for escala in (1, 3):
            img = arte.desenhar_predio("casa", escala=escala)
            self.assertEqual(img.size, (arte.PREDIO_W * escala,
                                        arte.PREDIO_H * escala))
            caixa = img.getchannel("A").getbbox()
            # 300x200 cabe pela largura: 72 de largura, base na ultima linha
            self.assertEqual(caixa[2] - caixa[0], arte.PREDIO_W * escala)
            self.assertEqual(caixa[3], arte.PREDIO_H * escala)
            meio = img.getpixel((img.width // 2, img.height - 4 * escala))
            self.assertEqual(meio[:3], CASA[:3])
        # de noite escurece (sem versao _noite aprovada) e nao some
        noite = arte.desenhar_predio("casa", noite=True)
        px = noite.getpixel((36, 60))
        self.assertEqual(px[3], 255)
        self.assertLess(px[0], CASA[0])
        # com a versao de noite aprovada, e ela que vale
        azul = Image.new("RGBA", (300, 200), (20, 20, 200, 255))
        self._aprovar("predios/casa_noite.png", azul)
        self.assertEqual(arte.desenhar_predio("casa", noite=True)
                         .getpixel((36, 60))[:3], (20, 20, 200))

    def test_casa_aprovada_aparece_no_mundo_inteiro(self):
        codigo = arte.compor_mundo(False)
        self._aprovar("predios/casa.png", self._casa())
        mundo = arte.compor_mundo(False)
        lx, ly = arte.CASA
        x = lx * arte.TILE - 4 + arte.PREDIO_W // 2
        y = ly * arte.TILE - 16 + arte.PREDIO_H - 6
        self.assertEqual(mundo.getpixel((x, y))[:3], CASA[:3])
        self.assertNotEqual(codigo.getpixel((x, y))[:3], CASA[:3])

    def test_grama_e_terra_ladrilham_o_chao(self):
        self._aprovar("cenario/chao_grama.png", Image.new("RGBA", (300, 300), GRAMA))
        chao = arte.desenhar_chao()
        # longe de rua, lago e lote: a grama da textura
        self.assertEqual(chao.getpixel((40, 150))[:3], GRAMA[:3])
        self._aprovar("cenario/caminho_terra.png", Image.new("RGBA", (300, 300), TERRA))
        chao = arte.desenhar_chao()
        # no meio da rua de baixo (y=216): a terra da textura
        self.assertEqual(chao.getpixel((40, arte.RUA_Y[1]))[:3], TERRA[:3])
        self.assertEqual(chao.getpixel((40, 150))[:3], GRAMA[:3])
        # a borda da rua continua de codigo (nem grama nem terra)
        borda = chao.getpixel((40, arte.RUA_Y[1] - 8))[:3]
        self.assertNotIn(borda, (GRAMA[:3], TERRA[:3]))

    def test_ladrilho_no_tamanho_do_mundo_e_deterministico(self):
        xadrez = Image.new("RGBA", (256, 256), GRAMA)
        xadrez.paste(Image.new("RGBA", (128, 128), TERRA), (0, 0))
        self._aprovar("cenario/chao_grama.png", xadrez)
        lado = arte_pronta.lado_do_ladrilho("cenario/chao_grama.png")
        self.assertEqual(lado, arte_pronta.LADO_DO_LADRILHO["cenario/chao_grama.png"])
        a = arte.desenhar_chao()
        # o ladrilho repete a cada `lado` pixels do mundo
        self.assertEqual(a.getpixel((10, 140))[:3], a.getpixel((10 + lado, 140))[:3])
        self.assertEqual(_hash(a), _hash(arte.desenhar_chao()))

    def test_peca_aprovada_depois_entra_sem_reiniciar(self):
        antes = arte_pronta.conferir()
        self.assertEqual(arte_pronta.conferir(), antes)      # nada mudou
        (self.pasta / "predios").mkdir()
        self._casa().save(self.pasta / "predios" / "casa.png")
        self.assertNotEqual(arte_pronta.conferir(), antes)
        self.assertIsNotNone(arte_pronta.peca("predios/casa.png"))


class FolhaTocaOCiclo(_ComPasta):
    def setUp(self):
        super().setUp()
        _folha_de_teste(self.pasta / "habitantes" / "chatgpt" / "andar.png")
        arte_pronta.conferir()

    def test_direcao_escolhe_a_linha_e_o_tempo_escolhe_o_quadro(self):
        folha, ciclo = arte_pronta.habitante("chatgpt", "passo1", "dir")
        self.assertEqual(ciclo, "direita")
        self.assertEqual(arte_pronta.habitante("chatgpt", "passo2", "esq")[1],
                         "esquerda")
        # 4 fps, laco: 0,25 s por quadro e volta ao primeiro depois de 1 s
        self.assertEqual([folha.indice(ciclo, t) for t in (0, .24, .25, .5, .99, 1.0)],
                         [0, 0, 1, 2, 3, 0])
        self.assertEqual(folha.quadro(ciclo, 1), 9)
        self.assertEqual(arte.quadro_do_habitante("chatgpt", "passo1", "dir", .5), 2)

    def test_o_json_da_esteira_manda_no_fps_e_no_laco(self):
        meta = {"animacao": {"grade": [4, 4], "ciclos": [
            {"nome": "direita", "quadros": [8, 9, 10, 11], "fps": 8, "loop": False}]}}
        self._aprovar("habitantes/chatgpt/andar.png", meta=meta)
        folha, ciclo = arte_pronta.habitante("chatgpt", "passo1", "dir")
        self.assertEqual(folha.ciclos[ciclo]["fps"], 8.0)
        # sem laco: para no ultimo quadro
        self.assertEqual([folha.indice(ciclo, t) for t in (0, .125, .4, 9)],
                         [0, 1, 3, 3])
        # direcao sem linha propria cai no primeiro ciclo da folha
        self.assertEqual(folha.ciclo("cima"), "direita")

    def test_o_quadro_desenhado_e_a_celula_certa_com_o_pe_no_chao(self):
        for direcao, linha in (("dir", 2), ("esq", 1)):
            for i in range(4):
                img = arte.desenhar_personagem("chatgpt", "passo1", "abertos",
                                               direcao, quadro=i)
                # o contrato de 26x32: o atlas do app empilha sprites lado a
                # lado, e a sobra da celula nao pode cair no vizinho
                self.assertEqual(img.size, (arte.PERSONAGEM_W, arte.PERSONAGEM_H))
                cor = img.getpixel((img.width // 2, img.height - 6))
                esperada = _cor_da_celula(linha * 4 + i)
                for a, b in zip(cor[:3], esperada[:3]):
                    self.assertLessEqual(abs(a - b), 3, (direcao, i, cor))
        # o pe (o fundo da bolinha, 8 px acima do fim da celula) desce para
        # a ultima linha do sprite: nada de habitante flutuando
        img = arte.desenhar_personagem("chatgpt", "passo1", quadro=0, escala=3)
        alfa = img.getchannel("A")
        opacos = [y for y in range(img.height)
                  if any(alfa.getpixel((x, y)) > 200 for x in range(img.width))]
        self.assertGreaterEqual(max(opacos), img.height - 4)

    def test_pose_sem_folha_cai_no_parado_e_depois_no_andar(self):
        self.assertEqual(arte_pronta.animacao_do_habitante("chatgpt", "triste"),
                         "andar")
        _folha_de_teste(self.pasta / "habitantes" / "chatgpt" / "parado.png")
        arte_pronta.conferir()
        self.assertEqual(arte_pronta.animacao_do_habitante("chatgpt", "triste"),
                         "parado")
        self.assertEqual(arte_pronta.animacao_do_habitante("chatgpt", "passo2"),
                         "andar")
        # quem nao tem folha nenhuma continua de codigo
        self.assertIsNone(arte_pronta.animacao_do_habitante("gemini", "parado"))

    def test_o_app_recebe_url_grade_ciclos_e_pe(self):
        app = arte_pronta.para_o_app()
        andar = app["habitantes"]["chatgpt"]["andar"]
        self.assertTrue(andar["url"].startswith("/arte-vila/habitantes/chatgpt/andar.png?v="))
        self.assertEqual(andar["grade"], [4, 4])
        self.assertEqual(andar["tamanho"], [256, 256])
        self.assertEqual(andar["mundo"], [26, 32])
        self.assertEqual(andar["ciclos"]["direita"]["quadros"], [8, 9, 10, 11])
        self.assertAlmostEqual(andar["pe"], 56 / 64, places=3)


class RotaDoApp(_ComPasta):
    def test_so_serve_peca_aprovada_do_inventario(self):
        self._aprovar("predios/casa.png", self._casa())
        self._aprovar("predios/inventado.png", self._casa())
        self.assertEqual(arte_pronta.arquivo_publico("/arte-vila/predios/casa.png"),
                         self.pasta / "predios" / "casa.png")
        for rota in ("/arte-vila/predios/inventado.png",
                     "/arte-vila/../inventario.json",
                     "/arte-vila/predios/../predios/casa.png",
                     "/arte-vila/predios\\casa.png",
                     "/arte-vila/predios/casa.json",
                     "/outra/predios/casa.png", "/arte-vila/"):
            self.assertIsNone(arte_pronta.arquivo_publico(rota), rota)

    def test_a_rota_do_servidor_entrega_os_bytes_e_404_no_resto(self):
        from remoto import api_http
        self._aprovar("predios/casa.png", self._casa())
        corpo, erros = [], []

        class Falso:
            send_response = send_header = end_headers = (lambda self, *a: None)
            wfile = type("W", (), {"write": lambda self, b: corpo.append(b)})()
            _erro = (lambda self, *a: erros.append(a))

        api_http.Manipulador._arte_da_vila(Falso(), "/arte-vila/predios/casa.png")
        self.assertEqual(corpo, [(self.pasta / "predios" / "casa.png").read_bytes()])
        api_http.Manipulador._arte_da_vila(Falso(), "/arte-vila/../inventario.json")
        self.assertEqual(erros[0][0], 404)


def _funcao_do_vila_js(nome: str) -> str:
    fonte = (Path(__file__).resolve().parents[1] / "remoto" / "app"
             / "vila.js").read_text(encoding="utf-8")
    m = re.search(rf"^function {nome}\(.*?^}}", fonte, re.M | re.S)
    assert m, nome
    return m.group(0)


@unittest.skipUnless(shutil.which("node"), "sem node")
class CelularEscolheOMesmoQuadro(unittest.TestCase):
    def test_vila_js_e_arte_pronta_dao_o_mesmo_quadro(self):
        ciclos = [{"quadros": [8, 9, 10, 11], "fps": 4, "loop": True},
                  {"quadros": [0, 1, 2], "fps": 8, "loop": False}]
        tempos = [0, .1, .25, .3, .74, 1.0, 2.6, 7.9]
        codigo = (_funcao_do_vila_js("vilaQuadroDaFolha") + "\nconst c = "
                  + json.dumps(ciclos) + "; const t = " + json.dumps(tempos)
                  + ";\nconsole.log(JSON.stringify(c.map((x) => t.map("
                  "(s) => vilaQuadroDaFolha(x, s)))));")
        saida = subprocess.run(["node", "-e", codigo], capture_output=True,
                               text=True, timeout=30)
        self.assertEqual(saida.returncode, 0, saida.stderr)
        no_celular = json.loads(saida.stdout)
        for ciclo, linha in zip(ciclos, no_celular):
            folha = arte_pronta.Folha("x", Image.new("RGBA", (4, 4)), 4, 4,
                                      {"c": ciclo}, ["c"])
            self.assertEqual(linha, [folha.quadro("c", folha.indice("c", s))
                                     for s in tempos])


if __name__ == "__main__":
    unittest.main()
