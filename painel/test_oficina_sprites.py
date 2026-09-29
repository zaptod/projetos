# -*- coding: utf-8 -*-
"""A Oficina de sprites: a limpeza MEDIDA nas folhas do Adrian, a
exportacao no formato do palco e a pagina montada na tela dele.

O que este arquivo trava:

1. AS CONTAS BASICAS. Componentes conectados e a soma em janela batem com a
   conta feita pixel a pixel.
2. A FOLHA DO CHATGPT (`fixtures/folha_acida_chatgpt.png`, a 11243): 26
   quadros, nenhuma linha de grade, nenhuma franja verde forte (nem visivel
   nem escondida em pixel transparente), nenhum pontinho, nenhum buraco no
   desenho e as ancoras iguais (ate 0,5 px). E o `piriri.py` medido do
   mesmo jeito, para o "antes" nao depender de memoria.
3. OUTRAS FOLHAS: a de fogo (sem grade, fatiada pelos vaos), fundo branco
   opaco com brilho branco DENTRO do desenho (nao pode furar) e tela verde
   com franja.
4. A EXPORTACAO no formato de `docs/palco/COMO-EDITAR.md`: folha em px
   inteiros, cena com o `folha_animada.gd` no caminho que a biblioteca
   procura, metadados, a linha de LICENCAS (sem duplicar), e a recusa sem
   prova de origem.
5. A PAGINA: abre, processa fora da interface, desfaz, soltar arquivo
   funciona, e na tela de 1366x768 o botao de exportar aparece sem rolar.

Rode da raiz:  python -m pytest painel/test_oficina_sprites.py -q
"""
from __future__ import annotations

import gc
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path

import numpy as np

from painel.sprites import alinhar, exportar, limpeza, medidas
from painel.sprites.receita import Receita, processar
from painel.sprites.rotulos import rotular

FIXTURES = Path(__file__).resolve().parent / "sprites" / "fixtures"
ACIDA = FIXTURES / "folha_acida_chatgpt.png"
PIRIRI = FIXTURES / "folha_acida_piriri.png"
FOGO = FIXTURES / "folha_fogo_removebg.png"


def _bfs(mascara):
    h, w = mascara.shape
    rot = np.zeros((h, w), int)
    n = 0
    for y in range(h):
        for x in range(w):
            if mascara[y, x] and not rot[y, x]:
                n += 1
                pilha = [(y, x)]
                rot[y, x] = n
                while pilha:
                    cy, cx = pilha.pop()
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            yy, xx = cy + dy, cx + dx
                            if 0 <= yy < h and 0 <= xx < w and \
                                    mascara[yy, xx] and not rot[yy, xx]:
                                rot[yy, xx] = n
                                pilha.append((yy, xx))
    return rot, n


class ContasBasicas(unittest.TestCase):
    def test_componentes_batem_com_a_busca_pixel_a_pixel(self):
        gerador = np.random.default_rng(7)
        for chance in (0.3, 0.5, 0.7):
            m = gerador.random((40, 57)) < chance
            esperado, n = _bfs(m)
            comps = rotular(m)
            self.assertEqual(comps.n, n)
            pares = set(zip(esperado[m].tolist(), comps.rotulos[m].tolist()))
            self.assertEqual(len(pares), n)
            self.assertEqual(int(comps.areas.sum()), int(m.sum()))

    def test_diagonal_e_do_mesmo_componente(self):
        m = np.eye(6, dtype=bool)
        self.assertEqual(rotular(m).n, 1)

    def test_soma_em_janela(self):
        v = np.random.default_rng(1).random((11, 14))
        for raio in (1, 3):
            esperado = np.array([[v[max(0, y - raio):y + raio + 1,
                                    max(0, x - raio):x + raio + 1].sum()
                                  for x in range(14)] for y in range(11)])
            self.assertTrue(np.allclose(limpeza.caixa(v, raio), esperado))

    def test_slug_igual_ao_do_palco(self):
        self.assertEqual(exportar.slug("Mágica"), "magica")
        self.assertEqual(exportar.slug("Bola Ácida"), "bola_acida")
        self.assertEqual(exportar.slug("Machado-Martelo"), "machado_martelo")
        self.assertEqual(exportar.slug("  Piromante (Fogo) "), "piromante_fogo")


class FolhaDoChatGPT(unittest.TestCase):
    """A 11243, medida -- nao so olhada."""

    @classmethod
    def setUpClass(cls):
        cls.receita = Receita()
        inicio = time.perf_counter()
        cls.res = processar(limpeza.abrir(ACIDA), cls.receita)
        cls.segundos = time.perf_counter() - inicio
        cls.m = medidas.medir(cls.res, cls.receita)

    def test_26_quadros_pela_grade_desenhada(self):
        self.assertEqual(self.m["quadros"], 26)
        self.assertEqual(self.res.modo_fatiar, "linhas")
        self.assertEqual((self.res.grade.colunas, self.res.grade.linhas),
                         (6, 5))

    def test_a_grade_desenhada_some(self):
        self.assertGreaterEqual(self.m["linhas_de_grade"]["antes"], 8)
        self.assertEqual(self.m["linhas_de_grade"]["folha"], 0)
        self.assertGreater(self.m["px_nas_faixas"]["antes"], 10000)
        self.assertEqual(self.m["px_nas_faixas"]["depois"], 0)

    def test_sem_franja_verde_forte(self):
        self.assertEqual(self.res.franja, (0, 255, 0))
        self.assertGreater(self.m["franja"]["antes"]["visivel"], 100000)
        self.assertEqual(self.m["franja"]["folha"],
                         {"visivel": 0, "oculta": 0})
        # nem escondida: quem ignora o alfa tambem nao ve verde vivo
        verde = limpeza.distancia(self.res.folha[..., :3], (0, 255, 0)) \
            <= medidas.FRANJA_FORTE
        self.assertEqual(int(verde.sum()), 0)

    def test_sem_pontinhos_e_sem_buracos(self):
        self.assertGreater(self.m["pontinhos"]["antes"], 1000)
        self.assertEqual(self.m["pontinhos"]["folha"], 0)
        self.assertEqual(self.m["buracos"], 0)

    def test_ancoras_iguais_e_celula_unica(self):
        self.assertLessEqual(self.m["ancoras_desvio_px"], 0.5)
        tamanhos = {q.shape for q in self.res.alinhado.quadros}
        self.assertEqual(len(tamanhos), 1)
        cw, ch = self.res.alinhado.celula
        self.assertEqual(self.res.folha.shape[1], self.res.colunas * cw)
        self.assertEqual(self.res.folha.shape[0], self.res.linhas * ch)
        self.assertEqual(self.res.colunas * self.res.linhas - 26,
                         self.res.colunas * self.res.linhas - len(
                             self.res.alinhado.quadros))

    def test_nenhum_quadro_encosta_na_borda_da_celula(self):
        """Margem de seguranca: nada cortado na hora de tocar."""
        margem = self.receita.margem
        for q in self.res.alinhado.quadros:
            caixa = alinhar.caixa_do_desenho(q[..., 3], 1)
            self.assertGreaterEqual(min(caixa[0], caixa[1]), margem - 1)
            self.assertLessEqual(caixa[2], q.shape[1] - margem + 1)
            self.assertLessEqual(caixa[3], q.shape[0] - margem + 1)

    def test_rapida_o_bastante_para_previa_ao_vivo(self):
        self.assertLess(self.segundos, 3.0)

    def test_deterministica(self):
        outra = processar(limpeza.abrir(ACIDA), self.receita)
        self.assertEqual(outra.folha.tobytes(), self.res.folha.tobytes())

    def test_o_piriri_medido_do_mesmo_jeito(self):
        """O "antes" do Adrian, em numero: a grade e a franja ficam, e o
        limiar fura o brilho branco da bola."""
        original = limpeza.para_array(limpeza.abrir(ACIDA))
        dele = limpeza.para_array(limpeza.abrir(PIRIRI))
        self.assertGreater(medidas.linhas_de_grade(dele), 5)
        self.assertGreater(medidas.franja(dele, (0, 255, 0))["visivel"],
                           100000)
        self.assertGreater(medidas.buracos(original, dele), 100)
        self.assertGreater(medidas.pontinhos(dele), 1000)

    def test_a_origem_nao_muda(self):
        antes = limpeza.para_array(limpeza.abrir(ACIDA)).copy()
        self.assertEqual(self.res.original.tobytes(), antes.tobytes())


class OutrasFolhas(unittest.TestCase):
    def test_fogo_sem_grade_sai_pelos_vaos(self):
        res = processar(limpeza.abrir(FOGO))
        self.assertEqual(res.modo_fatiar, "vaos")
        self.assertEqual(len(res.caixas), 26)
        self.assertEqual((res.grade.colunas, res.grade.linhas), (6, 5))

    def test_fogo_por_desenho_tambem_da_26(self):
        res = processar(limpeza.abrir(FOGO), Receita(fatiar="componentes"))
        self.assertEqual(len(res.caixas), 26)

    def test_uniforme_com_celula_vazia_ignorada(self):
        res = processar(limpeza.abrir(FOGO),
                        Receita(fatiar="uniforme", colunas=6, linhas=5))
        self.assertEqual(len(res.caixas), 26)
        res = processar(limpeza.abrir(FOGO),
                        Receita(fatiar="uniforme", colunas=6, linhas=5,
                                ignorar_vazias=False))
        self.assertEqual(len(res.caixas), 30)

    @staticmethod
    def _folha_branca():
        """3x2 bolas vermelhas com BRILHO BRANCO no meio, fundo branco e
        grade cinza desenhada."""
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (300, 200), (255, 255, 255))
        d = ImageDraw.Draw(img)
        for j in range(2):
            for i in range(3):
                cx, cy = 50 + i * 100, 50 + j * 100
                d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30],
                          fill=(200, 30, 30))
                d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8],
                          fill=(255, 255, 255))
        for x in (100, 200):
            d.line([(x, 0), (x, 199)], fill=(150, 150, 150), width=2)
        d.line([(0, 100), (299, 100)], fill=(150, 150, 150), width=2)
        return img

    def test_fundo_branco_pelas_bordas_nao_fura_o_brilho(self):
        img = self._folha_branca()
        res = processar(img, Receita())
        self.assertEqual(res.fundo["metodo"], "bordas")
        self.assertEqual(len(res.caixas), 6)
        m = medidas.medir(res, Receita())
        self.assertEqual(m["linhas_de_grade"]["folha"], 0)
        for q in res.alinhado.quadros:
            ay, ax = int(round(res.alinhado.ancora[1])), \
                int(round(res.alinhado.ancora[0]))
            self.assertEqual(int(q[ay, ax, 3]), 255, "o brilho furou")
        # o limiar global (o jeito do piriri) fura
        global_ = processar(img, Receita(fundo="cor", cor_fundo=[255, 255, 255],
                                         apagar_linhas=False))
        q = global_.alinhado.quadros[0]
        ax, ay = (int(round(v)) for v in global_.alinhado.ancora)
        self.assertEqual(int(q[ay, ax, 3]), 0)

    def test_tela_verde_com_franja(self):
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (240, 120), (0, 255, 0))
        d = ImageDraw.Draw(img)
        for i in range(2):
            cx = 60 + i * 120
            d.ellipse([cx - 34, 26, cx + 34, 94], fill=(90, 200, 60))
            d.ellipse([cx - 30, 30, cx + 30, 90], fill=(220, 60, 200))
        res = processar(img, Receita(tolerancia=30, suavidade=20))
        self.assertEqual(len(res.caixas), 2)
        m = medidas.medir(res, Receita())
        self.assertEqual(m["franja"]["folha"]["oculta"], 0)
        self.assertEqual(m["franja"]["folha"]["visivel"], 0)

    def test_grade_a_mao_e_celula_ignorada(self):
        base = processar(limpeza.abrir(FOGO))
        xs, ys = list(base.grade.xs), list(base.grade.ys)
        res = processar(limpeza.abrir(FOGO),
                        Receita(xs=xs, ys=ys, excluidas=[0, 3]))
        self.assertEqual(res.modo_fatiar, "manual")
        self.assertEqual(len(res.caixas), 24)

    def test_espelhar(self):
        res = processar(limpeza.abrir(FOGO), Receita(espelhar=True))
        normal = processar(limpeza.abrir(FOGO))
        self.assertEqual(len(res.alinhado.quadros), 26)
        a = res.alinhado.quadros[0][..., 3].sum(0)
        b = normal.alinhado.quadros[0][..., 3].sum(0)
        # a massa do fogo troca de lado
        meio = len(a) // 2
        self.assertEqual(a[:meio].sum() > a[meio:].sum(),
                         b[:meio].sum() < b[meio:].sum())

    def test_largura_maxima_reduz(self):
        res = processar(limpeza.abrir(ACIDA), Receita(largura_max=128))
        self.assertLessEqual(res.alinhado.celula[0], 128)
        self.assertEqual(res.folha.shape[1],
                         res.colunas * res.alinhado.celula[0])


class ReceitaTests(unittest.TestCase):
    def test_ida_e_volta_em_json(self):
        r = Receita(tolerancia=33, xs=[0, 10, 20], cor_fundo=[1, 2, 3])
        caminho = Path(tempfile.mkdtemp()) / "r.json"
        r.salvar(caminho)
        self.assertEqual(Receita.ler(caminho), r)

    def test_lote_esquece_a_grade_feita_a_mao(self):
        r = Receita(xs=[0, 5], ys=[0, 5], excluidas=[1], tolerancia=40)
        lote = r.para_lote()
        self.assertIsNone(lote.xs)
        self.assertEqual(lote.excluidas, [])
        self.assertEqual(lote.tolerancia, 40)

    def test_lote_limpa_varias(self):
        from painel.sprites.lote import limpar_lote
        pasta = Path(tempfile.mkdtemp())
        linhas = limpar_lote([FOGO, ACIDA], Receita(), pasta)
        self.assertEqual([ln["medidas"]["quadros"] for ln in linhas], [26, 26])
        self.assertTrue((pasta / "folha_fogo_removebg_folha.png").exists())
        self.assertTrue((pasta / "folha_acida_chatgpt_folha.json").exists())


class Exportacao(unittest.TestCase):
    def setUp(self):
        self.bib = Path(tempfile.mkdtemp())
        (self.bib / "LICENCAS.md").write_text(
            "# Licenças\n\n<!-- efeitos_cc0:inicio -->\nx\n"
            "<!-- efeitos_cc0:fim -->\n", encoding="utf-8")
        self.res = processar(limpeza.abrir(FOGO))
        self.ident = exportar.Identidade(
            nome="Bola de Fogo Teste", tipo="projetil", elemento="FOGO",
            fps=18, escala_raio=3.2, prova="conversa do ChatGPT de 28/09",
            fonte=str(FOGO))

    def test_escreve_no_formato_do_palco(self):
        feito = exportar.exportar(self.res, self.ident, Receita(), None,
                                  self.bib)
        folha = self.bib / "efeitos/folhas/bola_de_fogo_teste.png"
        cena = self.bib / "efeitos/objetos/projetil/fogo.tscn"
        self.assertEqual(Path(feito["folha"]), folha)
        self.assertEqual(Path(feito["cena"]), cena)
        from PIL import Image
        with Image.open(folha) as img:
            self.assertEqual(img.mode, "RGBA")
            cw, ch = self.res.alinhado.celula
            self.assertEqual(img.size, (self.res.colunas * cw,
                                        self.res.linhas * ch))
        texto = cena.read_text(encoding="utf-8")
        for trecho in ('path="res://biblioteca/efeitos/folha_animada.gd"',
                       'path="res://biblioteca/efeitos/folhas/'
                       'bola_de_fogo_teste.png"',
                       f"colunas = {self.res.colunas}",
                       f"linhas = {self.res.linhas}", "quadros = 26",
                       "fps = 18.0", "laco = true", "escala_raio = 3.2",
                       'script = ExtResource("1_folha")',
                       'folha = ExtResource("2_folha")'):
            self.assertIn(trecho, texto)
        ax, ay = self.res.alinhado.ancora
        self.assertIn(f"ancora = Vector2({ax}, {ay})", texto)
        meta = (self.bib / "efeitos/folhas/bola_de_fogo_teste.json")
        self.assertIn('"prova": "conversa do ChatGPT de 28/09"',
                      meta.read_text(encoding="utf-8"))

    def test_o_script_do_palco_existe_onde_a_cena_aponta(self):
        from painel.janelas import RAIZ
        gd = RAIZ / "palco" / "biblioteca" / "efeitos" / "folha_animada.gd"
        self.assertTrue(gd.exists(), gd)
        texto = gd.read_text(encoding="utf-8")
        for campo in ("folha", "colunas", "linhas", "quadros", "fps", "laco",
                      "ancora", "girar", "tamanho_m", "escala_raio",
                      "aditivo", "tingir", "duracao_s"):
            self.assertIn(f"var {campo}", texto)

    def test_destinos_da_descoberta_por_nome(self):
        E = exportar.Identidade
        self.assertEqual(exportar.destino_da_cena(
            E(tipo="projetil", elemento="NATUREZA")), "objetos/projetil/natureza")
        self.assertEqual(exportar.destino_da_cena(
            E(tipo="projetil", skill="Bola Ácida")), "skills/bola_acida")
        self.assertEqual(exportar.destino_da_cena(
            E(tipo="acerto", tier="heavy")), "eventos/acerto_heavy")
        self.assertEqual(exportar.destino_da_cena(E(tipo="ko")), "eventos/ko")
        self.assertEqual(exportar.destino_da_cena(E(tipo="area")), "")

    def test_licenca_uma_linha_por_folha(self):
        exportar.exportar(self.res, self.ident, biblioteca=self.bib)
        exportar.exportar(self.res, self.ident, biblioteca=self.bib,
                          substituir=True)
        texto = (self.bib / "LICENCAS.md").read_text(encoding="utf-8")
        self.assertEqual(texto.count("`efeitos/folhas/bola_de_fogo_teste.png`"),
                         1)
        self.assertIn("<!-- efeitos_cc0:inicio -->\nx\n", texto)
        self.assertIn(exportar.INICIO_LICENCAS, texto)

    def test_ja_existe_pede_confirmacao(self):
        exportar.exportar(self.res, self.ident, biblioteca=self.bib)
        with self.assertRaises(FileExistsError):
            exportar.exportar(self.res, self.ident, biblioteca=self.bib)

    def test_sem_prova_nao_entra(self):
        self.ident.prova = ""
        with self.assertRaises(ValueError) as caso:
            exportar.exportar(self.res, self.ident, biblioteca=self.bib)
        self.assertIn("PROVA", str(caso.exception))
        self.assertFalse((self.bib / "efeitos").exists())

    def test_objeto_sem_elemento_nem_skill_e_beam_recusados(self):
        self.assertTrue(exportar.problemas(
            exportar.Identidade(nome="x", tipo="area", prova="p"), 3))
        self.assertTrue(exportar.problemas(
            exportar.Identidade(nome="x", tipo="beam", elemento="FOGO",
                                prova="p"), 3))
        self.assertNotIn("beam", exportar.TIPOS)

    def test_os_12_elementos(self):
        self.assertEqual(len(exportar.elementos()), 12)
        self.assertNotIn("DEFAULT", exportar.elementos())


@unittest.skipUnless(sys.platform == "win32", "o soltar e do Windows")
class Soltar(unittest.TestCase):
    def test_arquivo_solto_chega(self):
        from painel import arrastar
        raiz = tk.Tk()
        raiz.withdraw()
        try:
            soltura = arrastar.aceitar(raiz)
            self.assertIsNotNone(soltura)
            self.assertTrue(arrastar.simular_soltura(
                soltura.hwnd, [str(FOGO), r"C:\ação\ç.png"]))
            for _ in range(20):
                raiz.update()
                if soltura.caminhos:
                    break
                time.sleep(0.01)
            self.assertEqual(soltura.pegar(), [str(FOGO), r"C:\ação\ç.png"])
            self.assertEqual(soltura.pegar(), [])
            soltura.soltar()
        finally:
            raiz.destroy()


class PaginaDaOficina(unittest.TestCase):
    """A janela montada de verdade, no tamanho da tela dele."""

    def setUp(self):
        from painel import janelas
        self.app = janelas.montar("oficina")
        self.app.withdraw()
        self.app.geometry("1366x705+0+0")
        self.pagina = self.app.paginas["oficina"]

    def tearDown(self):
        self.app.encerrar()
        self.app.supervisor.aguardar(20)
        if self.pagina._soltura is not None:
            self.pagina._soltura.soltar()
        self.app.destroy()
        del self.app, self.pagina
        gc.collect()

    def _esperar(self, limite=20.0):
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            self.app.update()
            if not self.pagina.ocupada():
                return True
            time.sleep(0.03)
        return False

    def test_abre_processa_e_desfaz(self):
        p = self.pagina
        self.assertTrue(p.abrir(FOGO))
        self.assertTrue(self._esperar())
        self.assertEqual(len(p.resultado.caixas), 26)
        self.assertEqual(p.medidas["quadros"], 26)
        receita_inicial = p.receita
        p._vars["tolerancia"].set(60)
        p._mudou("tolerancia")
        self.assertTrue(self._esperar())
        self.assertEqual(p.receita.tolerancia, 60)
        p.desfazer()
        self.assertTrue(self._esperar())
        self.assertEqual(p.receita, receita_inicial)
        self.assertEqual(float(p._vars["tolerancia"].get()),
                         receita_inicial.tolerancia)
        p.refazer()
        self.assertEqual(p.receita.tolerancia, 60)

    def test_celula_clicada_vira_ignorada(self):
        p = self.pagina
        p.abrir(FOGO)
        self.assertTrue(self._esperar())
        x0, y0, x1, y1 = p.resultado.caixas[0]
        p._alternar_celula((x0 + x1) / 2, (y0 + y1) / 2)
        self.assertTrue(self._esperar())
        self.assertEqual(len(p.resultado.caixas), 25)
        p.desfazer()
        self.assertTrue(self._esperar())
        self.assertEqual(len(p.resultado.caixas), 26)

    def test_identidade_e_destino(self):
        p = self.pagina
        p.abrir(FOGO)
        self.assertTrue(self._esperar())
        self.assertEqual(p._ident["nome"].get(), "folha_fogo_removebg")
        p._ident["elemento"].set("FOGO")
        p._ident["prova"].set("conversa")
        p._identidade_mudou()
        self.assertIn("objetos/projetil/fogo.tscn",
                      p.lbl_destino.cget("text"))
        self.assertEqual(p.lbl_problemas.cget("fg"), p.t.aviso)

    def test_cabe_na_tela_dele(self):
        """1366x768 maximizada: o botao de exportar aparece sem rolar, e o
        que nao cabe na coluna da esquerda rola (nao some)."""
        self.app.deiconify()
        from painel import prova
        prova.discreta(self.app, prova.janela_da_frente())
        for _ in range(10):
            self.app.update()
        p = self.pagina
        botao = p.btn_exportar
        topo = self.app.winfo_rooty()
        fundo_do_botao = botao.winfo_rooty() + botao.winfo_height() - topo
        area = self.app._area.winfo_height()
        self.assertTrue(botao.winfo_ismapped())
        self.assertLessEqual(fundo_do_botao, area + 2,
                             "o botao de exportar ficou abaixo da dobra")
        tela = p.canvas
        self.assertGreater(tela.winfo_width(), 400)
        self.assertGreater(tela.winfo_height(), 300)


class HubSemPixel(unittest.TestCase):
    def test_a_vila_em_pixel_saiu(self):
        import importlib.util
        for modulo in ("vila", "vila.motor", "vila.editor",
                       "painel.flutuante.mundo"):
            try:
                achou = importlib.util.find_spec(modulo)
            except ModuleNotFoundError:          # o pacote pai nem existe
                achou = None
            self.assertIsNone(achou, modulo)
        from painel.janelas import RAIZ
        fonte = (RAIZ / "painel" / "paginas" / "vila.py").read_text(
            encoding="utf-8")
        self.assertNotIn("from vila", fonte)
        self.assertNotIn("vila.editor", fonte)

    def test_a_oficina_tem_janela_propria(self):
        from painel.janelas import JANELAS
        self.assertIn("oficina", JANELAS)
        paginas = JANELAS["oficina"]["paginas"]()
        self.assertEqual([p.chave for p in paginas], ["oficina"])
        self.assertFalse(JANELAS["oficina"].get("pipeline"))


if __name__ == "__main__":
    unittest.main()
