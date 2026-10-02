# -*- coding: utf-8 -*-
"""Contratos da Vila FOFA: arte lisa, habitantes vivos, estado real primeiro.

1. ARTE deterministica: gerar duas vezes da os mesmos bytes; nome
   desconhecido cai num desenho de reserva, nunca some.
2. CAMINHOS: nenhum segmento atravessa predio; tudo alcanca tudo.
3. VIDA: passeio, papo quando dois se cruzam, comemoracao ao terminar,
   tristeza e consolo no erro, festa na publicacao, clique.
4. ESTADO REAL VENCE: trabalho leva ao predio certo com o balao certo,
   mesmo no meio de um papo ou sentado no banco.
5. COLECAO: um enfeite a cada 3 publicacoes do dia, sem descer no dia.
6. CENA monta, reage a erro/publicacao e resolve o clique.
"""
from __future__ import annotations

import gc
import hashlib
import json
import queue
import re
import shutil
import subprocess
import tkinter as tk
import unittest
from pathlib import Path

from painel import estilo
from painel.flutuante import arte, arte_pronta, dados, preferencias, vida
from painel.flutuante.cena import CenaFofa, e_noite

TODOS = list(dados.PREDIOS)
_SEM_ARTE: str | None = None


def setUpModule():
    """Estes contratos sao do DESENHO DE CODIGO (bytes e hashes medidos
    antes da arte da esteira): a arte aprovada em `painel/flutuante/
    arte_vila` fica de fora. O carregador tem os testes dele em
    `test_arte_pronta.py`."""
    global _SEM_ARTE
    import tempfile
    _SEM_ARTE = tempfile.mkdtemp(prefix="vila_sem_arte_")
    arte_pronta.usar(_SEM_ARTE)


def tearDownModule():
    arte_pronta.usar(None)
    shutil.rmtree(_SEM_ARTE or "", ignore_errors=True)


def _hash(img) -> str:
    return hashlib.sha1(img.tobytes()).hexdigest()


def _ocioso() -> dict:
    return {n: {"status": "ocioso", "balao": "💤"} for n in TODOS}


def _rodar(v: vida.Vida, segundos: float, t: float, passo: float = .05):
    eventos = []
    fim = t + segundos
    while t < fim:
        t += passo
        eventos += v.tick(passo, t)
    return t, eventos


class Arte(unittest.TestCase):
    def test_mundo_deterministico_dia_e_noite(self):
        self.assertEqual(_hash(arte.compor_mundo(False)),
                         _hash(arte.compor_mundo(False)))
        noite = arte.compor_mundo(True)
        self.assertEqual(noite.size, (arte.LARGURA, arte.ALTURA))
        self.assertNotEqual(_hash(noite), _hash(arte.compor_mundo(False)))

    def test_sprites_deterministicos_e_com_transparencia(self):
        for nome in TODOS:
            a = arte.desenhar_personagem(nome, "passo1", "abertos", "esq")
            b = arte.desenhar_personagem(nome, "passo1", "abertos", "esq")
            self.assertEqual(_hash(a), _hash(b), nome)
            self.assertEqual(a.size, (arte.PERSONAGEM_W, arte.PERSONAGEM_H))
            self.assertEqual(a.getpixel((0, 0))[3], 0, "fundo transparente")
            predio = arte.desenhar_predio(nome)
            self.assertEqual(predio.size, (arte.PREDIO_W, arte.PREDIO_H))
            self.assertEqual(predio.getpixel((0, 0))[3], 0)

    def test_cada_predio_tem_cara_propria(self):
        caras = {_hash(arte.desenhar_predio(n)) for n in TODOS}
        self.assertEqual(len(caras), len(TODOS))

    def test_nome_desconhecido_nao_some(self):
        img = arte.desenhar_predio("fabrica_que_nao_existe")
        self.assertEqual(img.size, (arte.PREDIO_W, arte.PREDIO_H))
        self.assertGreater(img.getchannel("A").getextrema()[1], 0)
        boneco = arte.desenhar_personagem("fabrica_que_nao_existe")
        self.assertGreater(boneco.getchannel("A").getextrema()[1], 0)

    def test_escala_desenha_de_verdade_e_e_o_mesmo_desenho(self):
        """O celular pede 3x: tamanho 3x, sem ampliar a de 1x, mesma arte."""
        from PIL import Image, ImageChops, ImageStat
        for fazer in (lambda e: arte.desenhar_predio("youtube", False, e),
                      lambda e: arte.desenhar_personagem(
                          "chatgpt", "parado", "abertos", "dir", e)):
            um, tres = fazer(1), fazer(3)
            self.assertEqual(tres.size, (um.width * 3, um.height * 3))
            self.assertEqual(_hash(tres), _hash(fazer(3)))
            # reduzida, a de 3x e a de 1x (media < 10 de 255 por canal)
            reduzida = tres.resize(um.size, Image.LANCZOS)
            media = ImageStat.Stat(ImageChops.difference(um, reduzida)).mean
            self.assertLess(max(media), 10, media)
            # e tem detalhe que a de 1x ampliada nao tem (nao e so ampliar)
            ampliada = um.resize(tres.size, Image.LANCZOS)
            self.assertNotEqual(_hash(ampliada), _hash(tres))
        self.assertEqual(arte.compor_mundo(False, 2).size,
                         (arte.LARGURA * 2, arte.ALTURA * 2))

    def test_sem_pixel_duro_ha_antialias(self):
        """Arte lisa: a borda do telhado tem tons intermediarios."""
        img = arte.desenhar_predio("youtube")
        alfas = set(img.getchannel("A").getdata())
        self.assertGreater(len(alfas - {0, 255}), 20)

    def test_emotes_e_decoracoes(self):
        for simbolo in ("☕", "💬", "🎉", "💧", "🤗"):
            self.assertEqual(arte.emote(simbolo).size, (22, 26))
        for nome in arte.DECORACOES:
            self.assertGreater(arte.desenhar_decoracao(nome).width, 0)
        self.assertEqual(set(arte.LUGAR_DAS_DECORACOES),
                         set(arte.DECORACOES))


def _segmento_cruza(p0, p1, caixa, passos: int = 60) -> bool:
    x0, y0, x1, y1 = caixa
    for i in range(passos + 1):
        t = i / passos
        x = p0[0] + (p1[0] - p0[0]) * t
        y = p0[1] + (p1[1] - p0[1]) * t
        if x0 < x < x1 and y0 < y < y1:
            return True
    return False


class Retrato(unittest.TestCase):
    """A Vila dobrada do celular (retrato.py): as duas metades em fileiras."""

    def test_a_dobra_nao_corta_nada_ao_meio(self):
        from painel.flutuante import retrato
        d = retrato.DOBRA
        coisas = [(lx * arte.TILE - 4, arte.PREDIO_W, nome)
                  for nome, (lx, _ly) in list(arte.LOTES.items())
                  + [("casa", arte.CASA)]]
        coisas += [(tx * arte.TILE - 2, 36, "arvore")
                   for tx, _ty, _tom in arte.ARVORES]
        coisas += [(arte.BANCO[0] - 13, 26, "banco"),
                   (arte.FONTE[0] - 20, 40, "fonte"),
                   (arte.CANTEIRO[0] - 17, 34, "canteiro"),
                   (arte.LAGO[0] - 34, 68, "lago")]
        for x, largura, nome in coisas:
            self.assertFalse(x < d < x + largura, (nome, x, largura))
        # as travessas tambem (uma rua cortada no meio pareceria um toco)
        for tx in arte.TRAVESSAS_X:
            self.assertFalse(tx - 8 < d < tx + 8, tx)
        # e o campo extra fica todo depois do mundo e dentro da fileira 2
        for x, _y, _tom in retrato.ARVORES_EXTRA:
            self.assertTrue(arte.LARGURA <= x and x + 36 <= 2 * d, x)

    def test_ida_e_volta_do_mundo_para_o_retrato(self):
        from painel.flutuante import retrato
        pontos = list(arte.portas().values()) + [
            (0, 0), (retrato.DOBRA - 1, 239), (retrato.DOBRA, 0), (703, 239)]
        for x, y in pontos:
            rx, ry = retrato.para_retrato(x, y)
            self.assertTrue(0 <= rx < retrato.LARGURA, (x, y))
            self.assertEqual(retrato.para_mundo(rx, ry), (x, y))
        # ceu, sebe e pe nao sao mundo: o toque ali nao escolhe ninguem
        for ry in (0, retrato.CEU - 1, retrato.CEU + arte.ALTURA + 1,
                   retrato.ALTURA - 1):
            self.assertIsNone(retrato.para_mundo(10, ry))

    def test_retrato_deterministico_no_tamanho_certo(self):
        from painel.flutuante import retrato
        a = retrato.compor_retrato(False, 1)
        self.assertEqual(a.size, (retrato.LARGURA, retrato.ALTURA))
        self.assertEqual(_hash(a), _hash(retrato.compor_retrato(False, 1)))
        self.assertNotEqual(_hash(a), _hash(retrato.compor_retrato(True, 1)))
        # a fileira 1 e o mundo de verdade, pixel a pixel
        mundo = arte.compor_mundo(False)
        topo = (0, retrato.CEU, retrato.DOBRA, retrato.CEU + 100)
        self.assertEqual(_hash(a.crop(topo)),
                         _hash(mundo.crop((0, 0, retrato.DOBRA, 100))))


class Paisagem(unittest.TestCase):
    """A Vila deitada do celular (paisagem.py): o mundo inteiro numa fileira."""

    def test_ida_e_volta_do_mundo_para_a_paisagem(self):
        from painel.flutuante import paisagem
        pontos = list(arte.portas().values()) + [(0, 0), (703, 239)]
        for x, y in pontos:
            px, py = paisagem.para_paisagem(x, y)
            self.assertTrue(0 <= px < paisagem.LARGURA, (x, y))
            self.assertEqual(paisagem.para_mundo(px, py), (x, y))
        for py in (0, paisagem.CEU - 1, paisagem.CEU + arte.ALTURA,
                   paisagem.ALTURA - 1):
            self.assertIsNone(paisagem.para_mundo(10, py))
        # as fileiras que o app usa dizem a mesma conta
        self.assertEqual(paisagem.geometria()["fileiras"], [[0, paisagem.CEU]])

    def test_paisagem_deterministica_e_a_fileira_e_o_mundo(self):
        from painel.flutuante import paisagem
        a = paisagem.compor_paisagem(False, 1)
        self.assertEqual(a.size, (arte.LARGURA, paisagem.ALTURA))
        self.assertEqual(_hash(a), _hash(paisagem.compor_paisagem(False, 1)))
        self.assertNotEqual(_hash(a), _hash(paisagem.compor_paisagem(True, 1)))
        # nenhuma casa muda de lugar: a fileira e o mundo, pixel a pixel
        faixa = (0, paisagem.CEU, arte.LARGURA, paisagem.CEU + arte.ALTURA)
        self.assertEqual(_hash(a.crop(faixa)), _hash(arte.compor_mundo(False)))


class PredioDoGrok(unittest.TestCase):
    """O Grok entrou em 29/09/2026 (Vila das IAs, fase 2) na unica vaga do
    mundo: entre o DeepSeek e o ChatGPT, onde havia uma arvore. Regras: o
    predio existe nos dois arranjos do celular sem cortar, e NADA fora
    dele mudou (uma flor que muda de lugar e uma mudanca sem dono)."""

    # a imagem de 72 px do lote + o caminho da porta ate a rua, no mundo
    REGIAO = (84, 0, 156, 92)
    # md5 do mundo de dia (1x) com a regiao do Grok apagada, medido em
    # 29/09 ANTES de o Grok entrar. Se isto falhar, algo fora do lote dele
    # mudou (flores, arvores, ruas, vizinhos) — de proposito ou nao.
    FORA_DO_GROK_ANTES = "6ee17eb9e869ca66e1313ed051ff8cb6"

    def test_o_grok_e_predio_em_todo_lugar(self):
        self.assertIn("grok", dados.PREDIOS)
        self.assertEqual(dados.PREDIOS["grok"]["rotulo"], "Grok")
        self.assertEqual(dados.ler_trava("grok__principal")["predio"], "grok")
        self.assertIn("grok", arte.LOTES)
        self.assertIn("grok", arte.CORES)
        self.assertIn("grok", arte.ACESSORIOS)
        self.assertIn("grok", arte.ORDEM_DAS_PELES)
        self.assertEqual(set(arte.ORDEM_DAS_PELES), set(arte.CORES))

    def test_cabe_entre_os_vizinhos_e_nos_dois_arranjos(self):
        from painel.flutuante import paisagem, retrato
        lx, ly = arte.LOTES["grok"]
        x0 = lx * arte.TILE - 4
        # telhado a 8 px dos telhados vizinhos (o telhado e a imagem menos
        # 4 px de cada lado)
        vizinhos = [(n, arte.LOTES[n][0] * arte.TILE - 4)
                    for n in ("deepseek", "chatgpt")]
        for nome, vx in vizinhos:
            if vx < x0:
                self.assertGreaterEqual(x0 + 4 - (vx + 68), 8, nome)
            else:
                self.assertGreaterEqual(vx + 4 - (x0 + 68), 8, nome)
        # inteiro na fileira de cima do retrato e dentro da paisagem
        self.assertLessEqual(x0 + arte.PREDIO_W, retrato.DOBRA)
        self.assertLessEqual(x0 + arte.PREDIO_W, paisagem.LARGURA)
        self.assertEqual(ly, 1)
        # a porta e inteira (os nos do grafo e o app usam o numero)
        px, py = arte.portas()["grok"]
        self.assertIsInstance(px, int)
        self.assertIsInstance(py, int)
        # nenhuma arvore sobrou no lote, e o ponto "arvore" do passeio saiu
        for tx, ty, _tom in arte.ARVORES:
            self.assertFalse(x0 <= tx * arte.TILE - 2 < x0 + arte.PREDIO_W
                             and ty == ly, (tx, ty))
        self.assertNotIn("arvore", vida.PONTOS)

    def test_tem_cara_propria_e_aparece_de_dia_e_de_noite(self):
        caras = {_hash(arte.desenhar_predio(n)) for n in TODOS}
        self.assertEqual(len(caras), len(TODOS))
        lx, ly = arte.LOTES["grok"]
        caixa = (int(lx * arte.TILE - 4), ly * arte.TILE - 16,
                 int(lx * arte.TILE - 4) + arte.PREDIO_W,
                 ly * arte.TILE - 16 + arte.PREDIO_H)
        for noite in (False, True):
            mundo = arte.compor_mundo(noite)
            recorte = mundo.crop(caixa)
            self.assertEqual(_hash(recorte),
                             _hash(arte.compor_mundo(noite).crop(caixa)))
            # a placa clara com o emblema esta la (de noite ela e creme,
            # "#fff6e0", e nao escurece com a casa)
            claros = sum(1 for px in recorte.getdata()
                         if px[0] > 220 and px[1] > 220 and px[2] > 200)
            self.assertGreater(claros, 40, noite)

    def test_nada_fora_do_grok_mudou(self):
        mundo = arte.compor_mundo(False, 1).copy()
        mundo.paste((0, 0, 0, 0), self.REGIAO)
        self.assertEqual(hashlib.md5(mundo.tobytes()).hexdigest(),
                         self.FORA_DO_GROK_ANTES)
        # e os habitantes de antes tem a mesma pele (a ordem das peles nao
        # e mais a alfabetica: nome novo entra no fim)
        self.assertEqual(arte.ORDEM_DAS_PELES[-1], "grok")
        self.assertEqual(arte.ORDEM_DAS_PELES[:-1],
                         sorted(n for n in arte.CORES if n != "grok"))


def _funcoes_do_vila_js(*nomes) -> str:
    """O fonte das funcoes puras do `remoto/app/vila.js`, para rodar no node."""
    fonte = (Path(__file__).resolve().parents[1] / "remoto" / "app"
             / "vila.js").read_text(encoding="utf-8")
    partes = [m.group(0) for m in re.finditer(
        r"^const VILA_BALAO_[^\n]*(?:\n  [^\n]*)*;", fonte, re.M)]
    for nome in nomes:
        m = re.search(rf"^function {nome}\(.*?^}}", fonte, re.M | re.S)
        assert m, nome
        partes.append(m.group(0))
    return "\n".join(partes)


@unittest.skipUnless(shutil.which("node"), "sem node")
class BalaoDoCorreioNoApp(unittest.TestCase):
    """O balao da resposta no canvas do celular (`vila.js`). Medido em
    29/09: predio da fileira de cima com a camera no topo, o balao ficava
    atras do placar. Agora desvia para baixo do predio."""

    def _rodar(self, js: str):
        codigo = _funcoes_do_vila_js("vilaOndeFicaOBalao",
                                     "vilaDesenharCorreio") + "\n" + js
        saida = subprocess.run(["node", "-e", codigo], capture_output=True,
                               text=True, timeout=30)
        self.assertEqual(saida.returncode, 0, saida.stderr)
        return json.loads(saida.stdout)

    def test_em_cima_quando_cabe_e_embaixo_quando_o_placar_taparia(self):
        r = self._rodar("""
          const porta = [120, 64 + 160];       // o Grok, na fileira 1 do retrato
          const z = 2.85;
          // camera no topo: a fileira comeca logo abaixo do placar (topo 120)
          const topoFileira = 160 * z;
          const a = vilaOndeFicaOBalao(porta[0], porta[1], z, topoFileira - 120, 120);
          // camera mais embaixo: sobra ceu acima do predio
          const b = vilaOndeFicaOBalao(porta[0], porta[1], z, topoFileira - 400, 120);
          console.log(JSON.stringify({a, b}));
        """)
        self.assertTrue(r["a"]["paraCima"])
        self.assertGreater(r["a"]["y"], 64 + 160, "abaixo do predio")
        self.assertEqual(r["a"]["x"], 120, "no caminho da porta")
        self.assertFalse(r["b"]["paraCima"])
        self.assertLess(r["b"]["y"], 64 + 160, "em cima do predio")

    def test_caso_zero_sem_correio_nao_desenha_nada(self):
        r = self._rodar("""
          const chamadas = [];
          const ctx = new Proxy({}, {get: (_, k) => (...a) => { chamadas.push(k); return 0; }});
          global.vilaBalaoDeFala = (...a) => chamadas.push("balao");
          global.vilaDobrar = (x, y) => [x, y + 160];
          global.vilaRespostaNova = () => "oi";
          global.Vila = {correio: null, mundo: {portas: {grok: [120, 64]}},
                         zoom: 1, panY: 0, faixa: [0, 800]};
          vilaDesenharCorreio(ctx);
          const semCorreio = chamadas.length;
          Vila.correio = {ias: [{ia: "grok", nao_vistas: 1, ultima: {}}]};
          vilaDesenharCorreio(ctx);
          const comCorreio = chamadas.length;
          Vila.correio = {ias: [{ia: "sem_predio", nao_vistas: 1, ultima: {}}]};
          vilaDesenharCorreio(ctx);
          console.log(JSON.stringify({semCorreio, comCorreio, semPredio: chamadas.length}));
        """)
        self.assertEqual(r["semCorreio"], 0)
        self.assertEqual(r["comCorreio"], 1)
        self.assertEqual(r["semPredio"], 1, "IA sem predio nao desenha")


class Caminhos(unittest.TestCase):
    def setUp(self):
        self.g = vida.montar_grafo()

    def test_nenhum_segmento_atravessa_predio(self):
        for p0, p1 in self.g.segmentos():
            for caixa in vida.lotes_px():
                self.assertFalse(_segmento_cruza(p0, p1, caixa),
                                 (p0, p1, caixa))

    def test_tudo_alcanca_tudo_e_fica_no_mapa(self):
        nos = sorted(self.g.nos)
        for nome in nos:
            x, y = self.g.nos[nome]
            self.assertTrue(0 <= x <= arte.LARGURA and 0 <= y <= arte.ALTURA)
        origem = "B:8"
        for destino in nos:
            if destino == origem:
                continue
            rota = self.g.caminho(origem, destino)
            self.assertTrue(rota, destino)
            self.assertEqual(rota[-1], destino)

    def test_toda_porta_e_todo_ponto_existem(self):
        for nome in TODOS + ["casa"]:
            self.assertIn(f"porta:{nome}", self.g.nos)
        for ponto in vida.PONTOS:
            self.assertIn(vida.no_do_ponto(ponto), self.g.nos)


class Vida(unittest.TestCase):
    def setUp(self):
        self.v = vida.Vida(TODOS, semente=3)
        self.t = 0.0
        self.v.aplicar(_ocioso(), self.t)

    def test_de_folga_eles_passeiam_e_fazem_coisas(self):
        self.t, eventos = _rodar(self.v, 120, self.t)
        tipos = {e[0] for e in eventos}
        self.assertIn("atividade", tipos)
        feitas = {e[2] for e in eventos if e[0] == "atividade"}
        self.assertGreaterEqual(len(feitas), 3, feitas)
        andaram = {h.nome for h in self.v.habitantes.values()
                   if h.passo_t > 0}
        self.assertEqual(andaram, set(TODOS))

    def test_dois_que_se_cruzam_conversam(self):
        a, b = self.v.habitantes["gemini"], self.v.habitantes["chatgpt"]
        for h in (a, b):
            h.andando, h.conversa_livre, h.pausa_ate = True, 0.0, 0.0
        a.pos, b.pos = [100.0, 88.0], [108.0, 88.0]
        eventos = self.v._encontros(10.0)
        self.assertEqual([(e[0], {e[1], e[2]}) for e in eventos],
                         [("encontro", {"gemini", "chatgpt"})])
        self.assertIn(a.emote, vida.PAPO)
        self.assertEqual(a.direcao, "dir")
        self.assertEqual(b.direcao, "esq")
        self.assertGreater(a.pausa_ate, 10.0)
        # Logo depois nao conversam de novo (intervalo).
        self.assertEqual(self.v._encontros(11.0), [])

    def test_trabalho_leva_ao_predio_certo_mesmo_no_meio_do_papo(self):
        h = self.v.habitantes["estudio"]
        h.pausa_ate = self.t + 999          # "conversando" por muito tempo
        h.atividade, h.ate = "sentado", self.t + 999
        predios = _ocioso()
        predios["estudio"] = {"status": "trabalhando",
                              "balao": "render historia_00017"}
        self.v.aplicar(predios, self.t)
        self.t, _ = _rodar(self.v, 40, self.t)
        self.assertEqual(h.no, "porta:estudio")
        self.assertEqual(h.atividade, "trabalhar")
        self.assertEqual(h.balao, "render historia_00017")
        pose = self.v.pose(h, self.t)[0]
        self.assertEqual(pose, "trabalhar")

    def test_recente_aviso_e_no_ar_tambem_sao_trabalho(self):
        predios = _ocioso()
        predios["gemini"] = {"status": "aviso", "balao": "⚠ vídeo h13 p1"}
        predios["bot"] = {"status": "no_ar", "balao": "no ar"}
        predios["picasso"] = {"status": "recente", "balao": "imagens h9"}
        self.v.aplicar(predios, self.t)
        self.t, _ = _rodar(self.v, 40, self.t)
        for nome in ("gemini", "bot", "picasso"):
            self.assertEqual(self.v.habitantes[nome].no, f"porta:{nome}",
                             nome)
        self.assertEqual(self.v.habitantes["gemini"].balao, "⚠ vídeo h13 p1")

    def test_terminou_volta_comemorando_na_praca(self):
        predios = _ocioso()
        predios["digen"] = {"status": "trabalhando", "balao": "payoff g7"}
        self.v.aplicar(predios, self.t)
        self.t, _ = _rodar(self.v, 30, self.t)
        eventos = self.v.aplicar(_ocioso(), self.t)
        self.assertIn(("terminou", "digen"), eventos)
        h = self.v.habitantes["digen"]
        self.assertEqual(h.balao, "")
        comemorou = False
        for _ in range(600):
            self.t += .05
            if ("comemorou", "digen") in self.v.tick(.05, self.t):
                comemorou = True
                break
        self.assertTrue(comemorou)
        self.assertEqual(h.no, "poi:fonte")
        self.assertEqual(h.emote, "✨")
        self.assertEqual(self.v.pose(h, self.t)[0], "feliz")

    def test_erro_fica_triste_e_alguem_vai_consolar(self):
        self.t, _ = _rodar(self.v, 5, self.t)
        predios = _ocioso()
        predios["tiktok"] = {"status": "erro", "balao": "❗ upload falhou"}
        eventos = self.v.aplicar(predios, self.t)
        consolo = [e for e in eventos if e[0] == "consolar"]
        self.assertEqual(len(consolo), 1)
        amigo = consolo[0][1]
        self.assertNotEqual(amigo, "tiktok")
        self.t, eventos = _rodar(self.v, 40, self.t)
        triste = self.v.habitantes["tiktok"]
        self.assertEqual(triste.no, "porta:tiktok")
        self.assertEqual(triste.atividade, "triste")
        self.assertEqual(triste.emote, "💧")
        self.assertIn(("consolou", amigo, "tiktok"), eventos)
        # erro resolvido: o triste volta a passear
        self.v.aplicar(_ocioso(), self.t)
        self.t, _ = _rodar(self.v, 5, self.t)
        self.assertEqual(triste.modo, "passeio")

    def test_publicacao_faz_festa_so_para_quem_esta_de_folga(self):
        predios = _ocioso()
        predios["estudio"] = {"status": "trabalhando", "balao": "render"}
        self.v.aplicar(predios, self.t)
        nomes = self.v.publicou(self.t)
        self.assertNotIn("estudio", nomes)
        self.assertEqual(len(nomes), len(TODOS) - 1)
        self.assertTrue(all(self.v.habitantes[n].emote == "🎉"
                            for n in nomes))

    def test_clique_pula_e_conta_o_que_faz(self):
        texto = self.v.clique("chatgpt", self.t)
        self.assertIn("ChatGPT: de folga", texto)
        h = self.v.habitantes["chatgpt"]
        self.assertGreater(self.v.pose(h, self.t + .25)[3], 0)
        predios = _ocioso()
        predios["chatgpt"] = {"status": "trabalhando", "balao": "roteiro h2"}
        self.v.aplicar(predios, self.t)
        self.assertEqual(self.v.clique("chatgpt", self.t),
                         "ChatGPT: roteiro h2")

    def test_andar_alterna_os_passos_e_pisca(self):
        h = self.v.habitantes["arena"]
        h.andando, h.pausa_ate = True, 0.0
        poses = set()
        for i in range(10):
            h.passo_t = i * .16
            poses.add(self.v.pose(h, 50.0)[0])
        self.assertEqual(poses, {"passo1", "passo2"})
        olhos = {self.v.pose(h, t / 100)[1] for t in range(0, 800)}
        self.assertEqual(olhos, {"abertos", "fechados"})

    def test_mesma_semente_mesma_vida(self):
        outra = vida.Vida(TODOS, semente=3)
        outra.aplicar(_ocioso(), 0.0)
        _rodar(outra, 60, 0.0)
        mesma = vida.Vida(TODOS, semente=3)
        mesma.aplicar(_ocioso(), 0.0)
        _rodar(mesma, 60, 0.0)
        self.assertEqual({n: h.pos for n, h in outra.habitantes.items()},
                         {n: h.pos for n, h in mesma.habitantes.items()})


class Colecao(unittest.TestCase):
    def test_enfeite_a_cada_tres_e_nao_desce_no_dia(self):
        prefs = {}
        self.assertEqual(preferencias.atualizar_colecao(prefs, 2, "d1"), 0)
        self.assertEqual(preferencias.atualizar_colecao(prefs, 7, "d1"), 2)
        self.assertEqual(preferencias.atualizar_colecao(prefs, 1, "d1"), 2)
        self.assertEqual(preferencias.atualizar_colecao(prefs, 99, "d1"), 6)
        self.assertEqual(preferencias.atualizar_colecao(prefs, 0, "d2"), 0)
        self.assertEqual(prefs["colecao"]["recorde"], 6)

    def test_publicados_no_dia(self):
        por_canal = {"historias": [
            {"quando": "2026-09-17T00:40:00", "url": "x"},
            {"quando": "2026-09-17T06:40:00", "publicado": False},
            {"quando": "2026-09-16T23:40:00", "url": "x"}],
            "builds": [{"quando": "2026-09-17T09:00:00", "publicado": True}]}
        self.assertEqual(dados.publicados_no_dia(por_canal, "2026-09-17"), 2)

    def test_arte_padrao_e_fofa(self):
        self.assertEqual(preferencias.PADRAO["arte"], "fofa")


class _Relogio:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class Cena(unittest.TestCase):
    def setUp(self):
        self.raiz = tk.Tk()
        self.raiz.withdraw()
        # O lixo com imagens do Tk precisa ser coletado NESTA thread: coletado
        # por uma thread de fundo, o Tcl aborta o processo inteiro.
        self.addCleanup(gc.collect)
        self.addCleanup(self.__dict__.pop, "cena", None)
        self.addCleanup(self.raiz.destroy)
        self.relogio = _Relogio()
        self.cena = CenaFofa(self.raiz, estilo.VILA, relogio=self.relogio,
                             hora=14)
        self.cena.canvas.pack()

    def _passos(self, segundos):
        for _ in range(int(segundos / .05)):
            self.relogio.t += .05
            self.cena.passo()

    def test_erro_mostra_o_alerta_no_predio(self):
        predios = _ocioso()
        predios["youtube"] = {"status": "erro", "balao": "❗ cota",
                              "contas": []}
        self.cena.aplicar(predios)
        alerta = self.cena._rotulos["youtube"][3]
        self.assertEqual(self.cena.canvas.itemcget(alerta, "state"), "normal")
        self.cena.aplicar(_ocioso())
        self.assertEqual(self.cena.canvas.itemcget(alerta, "state"), "hidden")

    def test_balao_do_trabalho_aparece_embaixo_do_habitante(self):
        predios = _ocioso()
        predios["gemini"] = {"status": "trabalhando",
                             "balao": "vídeo historia_00013 p1",
                             "contas": ["principal"]}
        self.cena.aplicar(predios)
        self._passos(30)
        itens = self.cena._itens["gemini"]
        self.assertEqual(self.cena.canvas.itemcget(itens["balao"], "text"),
                         "vídeo historia_00013 p1")
        bandeira = self.cena._rotulos["gemini"][2]
        self.assertEqual(self.cena.canvas.itemcget(bandeira, "text"), "⚑")

    def test_publicacao_nova_solta_confete_e_placar(self):
        from datetime import datetime
        estado = {"publicados": [{"quando": datetime(2026, 9, 17, 6, 0)}]}
        self.cena.aplicar_estado(estado, 1, 4)
        self.assertEqual(self.cena._particulas, [])
        estado = {"publicados": [{"quando": datetime(2026, 9, 17, 6, 40)}]}
        self.cena.aplicar_estado(estado, 1, 5)
        self.assertGreater(len(self.cena._particulas), 10)
        texto = self.cena.canvas.itemcget(self.cena._placar, "text")
        self.assertEqual(texto, "📤 5 hoje · 🎀 1/6")
        visiveis = [i for i in self.cena._decoracoes
                    if self.cena.canvas.itemcget(i, "state") == "normal"]
        self.assertEqual(len(visiveis), 1)
        self._passos(3)
        self.assertEqual(self.cena._particulas, [], "o confete acaba")

    def test_clique_no_personagem_e_no_predio(self):
        clicados = []
        self.cena.ao_clicar = clicados.append
        h = self.cena.vida.habitantes["arena"]
        x, y = self.cena.vida.posicao_de_desenho(h)
        evento = type("E", (), {"x": x, "y": y - 12})()
        self.cena._clique(evento)
        self.assertTrue(h.info.startswith("Arena"))
        lx, ly = arte.LOTES["picasso"]
        longe = {"x": lx * 16 + 20, "y": ly * 16 + 10}
        for outro in self.cena.vida.habitantes.values():
            outro.pos = [5.0, 230.0]
        self.cena._clique(type("E", (), longe)())
        self.assertEqual(clicados, ["picasso"])

    def test_noite_pelo_relogio(self):
        from datetime import datetime
        self.assertTrue(e_noite(datetime(2026, 9, 17, 22)))
        self.assertTrue(e_noite(datetime(2026, 9, 17, 3)))
        self.assertFalse(e_noite(datetime(2026, 9, 17, 12)))
        noite = CenaFofa(self.raiz, estilo.VILA, relogio=self.relogio,
                         hora=22)
        self.assertTrue(noite._noite)
        estado = noite.canvas.itemcget(noite._vagalumes[0], "state")
        self.assertEqual(estado, "normal")
        self.assertFalse(self.cena._noite)


class JanelaSoTemAFofa(unittest.TestCase):
    """A arte classica em pixel foi aposentada (28/09/2026): a janela monta
    a fofa, e o menu nao oferece mais a troca."""

    def test_monta_a_fofa(self):
        import tempfile
        from pathlib import Path

        from painel.flutuante import janela
        from painel.flutuante.caminhos import Caminhos

        class Parado:
            def __init__(self):
                self.fila = queue.Queue()

            def __getattr__(self, _nome):
                return lambda *a, **k: None

        pasta = Path(tempfile.mkdtemp())
        app = janela.Janela(caminhos=Caminhos(raiz=pasta, rt=pasta),
                            modo="medio", topo=False, coletor=Parado(),
                            iniciar=False, persistir=False)
        try:
            self.assertIsInstance(app._cena, CenaFofa)
            self.assertEqual(app._intervalo(), janela.ANIMACAO_FOFA_MS)
            self.assertFalse(hasattr(app, "_trocar_arte"))
        finally:
            app.sair()
            del app
            gc.collect()


if __name__ == "__main__":
    unittest.main()
