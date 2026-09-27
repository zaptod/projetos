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
import queue
import tkinter as tk
import unittest

from painel import estilo
from painel.flutuante import arte, dados, preferencias, vida
from painel.flutuante.cena import CenaFofa, e_noite

TODOS = list(dados.PREDIOS)


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


class JanelaEscolheArte(unittest.TestCase):
    def test_troca_entre_fofa_e_classica(self):
        import tempfile
        from pathlib import Path

        from painel.flutuante import janela, mundo
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
            app._arte_var.set("classico")
            app._trocar_arte()
            self.assertIsInstance(app._cena, mundo.CenaVila)
            app._arte_var.set("fofa")
            app._trocar_arte()
            self.assertIsInstance(app._cena, CenaFofa)
        finally:
            app.sair()
            del app
            gc.collect()


if __name__ == "__main__":
    unittest.main()
