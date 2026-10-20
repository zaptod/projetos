# -*- coding: utf-8 -*-
"""Semana 1 do plano unico (docs/PLANO.md, 20/10/2026): o duelo se apresenta
pelo CONFRONTO, nao pelo nome inventado.

- titulo "Arma VS Arma — who wins?" (YouTube) e a descricao, que e a
  legenda do TikTok, abrindo com o mesmo confronto e a pergunta — em ingles
  (decisao geral/canal-em-ingles; o mapa e o de `ingles.py`, testado em
  `test_ingles_do_duelo_regressions.py`);
- a arma e o ESTILO que o personagem tem no banco; mesma arma desempata pela
  classe, depois pelo elemento, depois pelo primeiro nome;
- o rodizio enxerga o titulo NOVO: par com confronto ja ocupado nao sai;
- faixa fixa no topo do video com os dois rotulos, cada um na cor do seu
  lutador, dentro da zona segura e sem crescer o HUD;
- "WHO WINS?" escrito desde o quadro 0.

Cada guarda tem o seu caso zero.
"""
from __future__ import annotations

import inspect
import json
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from PIL import Image  # noqa: E402

from builds.arena import rodizio  # noqa: E402
from builds.content.caption_generator import CaptionGenerator  # noqa: E402
from builds.generation.session_generator import load_config  # noqa: E402
from builds.publicar import catalogo, confronto, titulos  # noqa: E402
from builds.tournament.duelo import DueloTimelineBuilder  # noqa: E402
from builds.video.renderer import (FAIXA_FOLGA_HUD, PILULA,  # noqa: E402
                                   ZONA_DAS_PLATAFORMAS, VideoRenderer, caixa_do_hud,
                                   contraste, cor_legivel, fundo_da_pilula)

ARMAS = {
    "Dharduen": {"nome": "Dharduen", "estilo": "Facas Táticas", "afinidade_elemento": "Trevas"},
    "Thargald": {"nome": "Thargald", "estilo": "Espada Longa", "afinidade_elemento": "Chamas"},
    "Iskimantr": {"nome": "Iskimantr", "estilo": "Espada Longa", "afinidade_elemento": "Gelo"},
    "Vorn": {"nome": "Vorn", "estilo": "Espada Longa", "afinidade_elemento": "Chamas"},
    "Kesh": {"nome": "Kesh", "estilo": "Kusarigama", "afinidade_elemento": "Relâmpago"},
}


def _ficha(nome, arma, classe="Ninja (Velocidade)", cor=(51, 99, 221)):
    return {"nome": nome, "nome_arma": arma, "classe": classe,
            "cor_r": cor[0], "cor_g": cor[1], "cor_b": cor[2]}


class _ComArmasFalsas(unittest.TestCase):
    """O banco de armas do teste: nada le o banco vivo."""

    def setUp(self):
        confronto.esquecer_armas()
        self._p = mock.patch.object(confronto, "_carregar_armas", return_value=dict(ARMAS))
        self._p.start()

    def tearDown(self):
        self._p.stop()
        confronto.esquecer_armas()


class RotulosTests(_ComArmasFalsas):

    def test_o_rotulo_e_o_estilo_da_arma_nao_o_nome_proprio(self):
        l1, l2 = confronto.rotulos(_ficha("Serena Skathyumi", "Dharduen"),
                                   _ficha("Valerio Cyraragrond", "Thargald"))
        self.assertEqual(("Tactical Knives", "Longsword"), (l1, l2))

    def test_mesma_arma_desempata_pela_classe(self):
        l1, l2 = confronto.rotulos(_ficha("A", "Thargald", "Ninja (Velocidade)"),
                                   _ficha("B", "Iskimantr", "Monge (Chi)"))
        self.assertEqual(("Longsword Ninja", "Longsword Monk"), (l1, l2))

    def test_mesma_arma_e_classe_desempata_pelo_elemento(self):
        l1, l2 = confronto.rotulos(_ficha("A", "Thargald"), _ficha("B", "Iskimantr"))
        self.assertEqual(("Flame Longsword", "Frost Longsword"), (l1, l2))

    def test_tudo_igual_desempata_pelo_primeiro_nome(self):
        l1, l2 = confronto.rotulos(_ficha("Aldric Solulacern", "Thargald"),
                                   _ficha("Elowen Emberdoen", "Vorn"))
        self.assertEqual(("Aldric's Longsword", "Elowen's Longsword"), (l1, l2))

    def test_arma_fora_do_banco_cai_na_classe_e_depois_no_nome(self):
        l1, l2 = confronto.rotulos(_ficha("A", "Sumiu", "Berserker (Furia)"),
                                   {"nome": "Kuro #2"}, nome2="Kuro #2")
        self.assertEqual(("Berserker", "Kuro #2"), (l1, l2))

    def test_o_carimbo_vale_sobre_o_banco(self):
        luta = {"p1": "A", "p2": "B", "p1_ficha": _ficha("A", "Dharduen"),
                "p2_ficha": _ficha("B", "Thargald"),
                "confronto": {"p1": "Katana", "p2": "Sai"}}
        self.assertEqual(("Katana", "Sai"), confronto.da_luta(luta))

    def test_carimbar_grava_na_luta_e_nos_rounds(self):
        luta = {"p1": "A", "p2": "B", "p1_ficha": _ficha("A", "Dharduen"),
                "p2_ficha": _ficha("B", "Kesh")}
        fight = {"luta": luta, "lutas": [json.loads(json.dumps(luta))]}
        confronto.carimbar(fight)
        esperado = {"p1": "Tactical Knives", "p2": "Kusarigama"}
        self.assertEqual(esperado, fight["luta"]["confronto"])
        self.assertEqual(esperado, fight["lutas"][0]["confronto"])


class TituloDoCatalogoTests(_ComArmasFalsas):
    """Contra o `config/publicacao.json` REAL e um duelo num outputs falso."""

    def _duelo(self, tmp, luta):
        pasta = Path(tmp) / "duelo_00001"
        pasta.mkdir()
        (pasta / "fight.json").write_text(json.dumps({"luta": luta}), encoding="utf-8")
        (pasta / "final_celular.mp4").write_bytes(b"\0" * (catalogo.BYTES_MINIMOS + 1))
        return pasta

    def _luta(self):
        return {"p1": "Drusila Vyrhordan", "p2": "Sigrid Brasbalmirn", "cenario": "Duto",
                "p1_ficha": _ficha("Drusila Vyrhordan", "Dharduen"),
                "p2_ficha": _ficha("Sigrid Brasbalmirn", "Kesh")}

    def test_titulo_e_descricao_do_duelo_no_catalogo(self):
        config = catalogo.carregar_config()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(catalogo, "OUTPUTS", Path(tmp)):
            self._duelo(tmp, self._luta())
            config = dict(config, pasta_export=str(Path(tmp) / "_publicar"))
            video = next(v for v in catalogo.listar(config) if v.origem == catalogo.DUELO)
        self.assertEqual("Tactical Knives VS Kusarigama — who wins?", video.titulo)
        self.assertNotIn("Drusila", video.titulo)
        primeira = video.descricao.splitlines()[0]
        self.assertTrue(primeira.startswith("Tactical Knives VS Kusarigama: who wins?"),
                        primeira)
        # o nome continua na descricao, como detalhe
        self.assertIn("Drusila Vyrhordan vs Sigrid Brasbalmirn", video.descricao)
        # e a legenda do TikTok e a descricao + hashtags
        self.assertTrue(video.descricao_completa.startswith(primeira))
        self.assertLessEqual(len(video.titulo), 100)

    def test_caso_zero_o_modelo_antigo_dava_o_nome_inventado(self):
        antigo = {"titulos": {"duelo": "{p1} x {p2}"}}
        self.assertEqual("Drusila Vyrhordan x Sigrid Brasbalmirn",
                         catalogo.titulo_do_duelo(self._luta(), antigo))

    def test_o_titulo_cabe_no_youtube_no_pior_caso(self):
        config = catalogo.carregar_config()
        luta = {"p1": "A", "p2": "B",
                "p1_ficha": _ficha("A", "", "Guerreiro (Forca Bruta)"),
                "p2_ficha": _ficha("B", "", "Guerreiro (Forca Bruta)"),
                "confronto": {"p1": "Three-Section Staff Pyromancer",
                              "p2": "Three-Section Staff Necromancer"}}
        self.assertLessEqual(len(catalogo.titulo_do_duelo(luta, config)), 100)


class RodizioComOTituloNovoTests(_ComArmasFalsas):
    CONFIG = {"titulos": {"duelo": "{lado1} VS {lado2} — who wins?"}}

    def _fichas(self):
        return {"A": _ficha("A", "Dharduen"), "B": _ficha("B", "Kesh"),
                "C": _ficha("C", "Thargald", "Monge (Chi)")}

    def test_par_com_confronto_ja_no_ar_nunca_sai_mesmo_com_outros_nomes(self):
        # "Facas Taticas VS Kusarigama" ja foi ao ar com OUTRA dupla.
        ocupados = {titulos.chave("Tactical Knives VS Kusarigama — who wins?")}
        fichas = self._fichas()
        for semente in range(10):
            p2 = rodizio.escolher_p2("A", fichas, [], [], random.Random(semente),
                                     ocupados=ocupados, config=self.CONFIG)
            self.assertEqual("C", p2)

    def test_caso_zero_sem_fichas_o_titulo_nao_e_o_do_catalogo(self):
        # Sem a ficha, o rotulo cai no nome: a checagem nao veria o confronto.
        self.assertEqual("A VS B — who wins?",
                         rodizio.titulo_do_par("A", "B", self.CONFIG))
        self.assertEqual("Tactical Knives VS Kusarigama — who wins?",
                         rodizio.titulo_do_par("A", "B", self.CONFIG, self._fichas()))

    def test_titulos_do_disco_sao_os_do_catalogo(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp) / "duelo_00007"
            pasta.mkdir()
            luta = {"p1": "X", "p2": "Y", "p1_ficha": _ficha("X", "Dharduen"),
                    "p2_ficha": _ficha("Y", "Thargald")}
            (pasta / "fight.json").write_text(json.dumps({"luta": luta}), encoding="utf-8")
            self.assertEqual(["Tactical Knives VS Longsword — who wins?"],
                             rodizio.titulos_do_disco(Path(tmp), self.CONFIG))

    def test_a_geracao_passa_as_fichas_para_o_titulo(self):
        from builds.pipeline import noite
        fonte = inspect.getsource(noite._duelo_ensaiado)
        self.assertIn("titulo_do_par(p1, p2, config, fichas)", fonte)
        fonte = inspect.getsource(rodizio.escolher_p2) + inspect.getsource(rodizio.escolher_p1)
        self.assertEqual(2, fonte.count("ocupados, config, fichas)"))


class EdicaoDoDueloTests(_ComArmasFalsas):

    def _fight(self):
        luta = {"p1": "Aldric Solulacern", "p2": "Elowen Emberdoen", "vencedor": "Elowen Emberdoen",
                "p1_ficha": _ficha("Aldric Solulacern", "Dharduen", "Necromante (Trevas)"),
                "p2_ficha": _ficha("Elowen Emberdoen", "Thargald", "Feiticeiro (Caos)"),
                "clipes": {"celular": {"path": "x.mp4", "duracao": 12.0}},
                "duracao": 10.0, "ko_type": "KO"}
        return {"seed": 7, "luta": luta, "lutas": [json.loads(json.dumps(luta))]}

    def test_o_evento_leva_o_confronto_e_a_pergunta(self):
        editing = load_config("editing.json")
        captions = CaptionGenerator(load_config("captions.json"), load_config("frases.json"))
        fight = self._fight()
        evento = DueloTimelineBuilder(editing, captions).build(random.Random(1), fight)["events"][0]
        self.assertEqual({"p1": "Tactical Knives", "p2": "Longsword"}, evento["confronto"])
        self.assertEqual("WHO WINS?", evento["identidade"]["pergunta"])
        self.assertEqual("nome", evento["identidade"]["primeiro"])
        # carimbado no fight que o controller regrava: titulo e faixa iguais
        self.assertEqual(evento["confronto"], fight["luta"]["confronto"])

    def test_o_duelo_novo_carimba_o_confronto(self):
        from builds.pipeline.controller import PipelineController
        self.assertIn("confronto.carimbar(fight)", inspect.getsource(PipelineController.duelo))


class FaixaDoTopoTests(unittest.TestCase):
    PIOR = ("Three-Section Staff Pyromancer", "Three-Section Staff Necromancer")
    COR1, COR2 = (61, 214, 160), (232, 22, 232)

    @classmethod
    def setUpClass(cls):
        cls.render = load_config("render.json")

    def _evento(self, confronto_=None, pergunta="WHO WINS?", selo="TITLE ON THE LINE"):
        luta = {"p1": "Aldric Solulacern", "p2": "Elowen Emberdoen",
                "p1_ficha": {"cor_r": self.COR1[0], "cor_g": self.COR1[1], "cor_b": self.COR1[2]},
                "p2_ficha": {"cor_r": self.COR2[0], "cor_g": self.COR2[1], "cor_b": self.COR2[2]}}
        evento = {"luta": luta,
                  "hud": {"p1": luta["p1"], "p2": luta["p2"],
                          "serie_hp": [[0.0, 100.0, 100.0]],
                          "serie_plano": [[0.0, "QUEBRAR GUARDA", 1.0, "TROCAÇÃO", 1.0]]},
                  "identidade": {"ate": 1.5, "primeiro": "nome", "pergunta": pergunta,
                                 "selo": selo,
                                 "p1": {"nome": luta["p1"], "classe": "Necromancer",
                                        "cartel": "12W-3L"},
                                 "p2": {"nome": luta["p2"], "classe": "Sorcerer",
                                        "cartel": "4W-0L"}}}
        if confronto_:
            evento["confronto"] = {"p1": confronto_[0], "p2": confronto_[1]}
        return evento

    def _hud(self, renderer, evento):
        img = Image.new("RGBA", (renderer.width, renderer.height), (0, 0, 0, 0))
        renderer._desenhar_hud(img, renderer._hud_preparado(evento), 0.0)
        return img

    def _identidade(self, renderer, evento, t=0.0):
        img = Image.new("RGBA", (renderer.width, renderer.height), (0, 0, 0, 0))
        renderer._desenhar_identidade(img, renderer._identidade_preparada(evento), t)
        return img

    @staticmethod
    def _cor_em(img, cor, caixa, tol=6):
        x0, y0, x1, y1 = caixa
        rgb = img.convert("RGB")
        alfa = img.getchannel("A")
        for y in range(y0, y1, 2):
            for x in range(x0, x1, 2):
                if alfa.getpixel((x, y)) > 200:
                    p = rgb.getpixel((x, y))
                    if all(abs(a - b) <= tol for a, b in zip(p, cor)):
                        return True
        return False

    def test_a_faixa_fica_na_zona_segura_e_nao_cresce_o_hud(self):
        r = VideoRenderer(self.render, "celular")
        topo = r._layout_do_topo()
        for par in (("Katana", "Sai"), ("Tactical Knives", "Longsword"), self.PIOR):
            with self.subTest(par=par):
                caixa = self._hud(r, self._evento(par)).getchannel("A").getbbox()
                self.assertGreaterEqual(caixa[1], ZONA_DAS_PLATAFORMAS["topo"] * r.height)
                self.assertLessEqual(caixa[2], (1 - ZONA_DAS_PLATAFORMAS["direita"]) * r.width)
                self.assertLessEqual(caixa[3], topo["hud_baixo"])
        # a camera da cauda le a caixa do HUD: com a faixa ela nao desce
        sem = self._hud(r, self._evento()).getchannel("A").getbbox()
        self.assertEqual(sem[3], caixa_do_hud(self.render, "celular")[3])

    def test_cada_lado_na_cor_do_seu_lutador(self):
        r = VideoRenderer(self.render, "celular")
        topo = r._layout_do_topo()
        img = self._hud(r, self._evento(("Tactical Knives", "Longsword")))
        meio = topo["direita"] // 2
        linha = (0, topo["hud_topo"], topo["direita"], topo["y"] - 2)
        esquerda = (linha[0], linha[1], meio, linha[3])
        direita = (meio, linha[1], linha[2], linha[3])
        c1, c2 = cor_legivel(self.COR1), cor_legivel(self.COR2)
        self.assertTrue(self._cor_em(img, c1, esquerda))
        self.assertTrue(self._cor_em(img, c2, direita))
        self.assertFalse(self._cor_em(img, c2, (0, linha[1], meio - 60, linha[3])))

    def test_a_faixa_tem_pilula_contraste_e_folga_do_hud(self):
        """Conferente, 20/10: o azul (36,81,243) dava 2,6-3,0:1 sobre a arena
        e a faixa ficava a 1-2 px das barras."""
        r = VideoRenderer(self.render, "celular")
        topo = r._layout_do_topo()
        azul = (36, 81, 243)
        self.assertLess(contraste(azul, fundo_da_pilula()), 4.5)        # caso zero
        self.assertGreaterEqual(contraste(cor_legivel(azul), fundo_da_pilula()), 4.5)
        evento = self._evento(("Tactical Knives", "Longsword"))
        evento["hud"] = dict(evento["hud"], serie_plano=[])
        hud = r._hud_preparado(evento)
        alfa = hud["camada"].getchannel("A")
        moldura_das_barras = topo["y"] - 4
        faixa = alfa.crop((0, 0, r.width, moldura_das_barras)).getbbox()
        self.assertIsNotNone(faixa)
        self.assertGreaterEqual(moldura_das_barras - faixa[3], FAIXA_FOLGA_HUD)
        self.assertGreaterEqual(faixa[1], ZONA_DAS_PLATAFORMAS["topo"] * r.height)
        # a pilula: o fundo atras do texto e escuro e semitransparente
        meio_x = (faixa[0] + faixa[2]) // 2
        self.assertEqual(PILULA[3], alfa.getpixel((faixa[0] + 3, (faixa[1] + faixa[3]) // 2)))
        self.assertGreater(faixa[2] - faixa[0], 200)
        self.assertLess(abs(meio_x - topo["direita"] // 2), 3)

    def test_com_a_faixa_o_nome_inventado_sai_do_hud(self):
        r = VideoRenderer(self.render, "celular")
        topo = r._layout_do_topo()
        linha = (topo["x1"], topo["hud_topo"], topo["x1"] + 120, topo["y"] - 2)
        # "Facas..." centrado nao chega a 120 px da margem; "Aldric Solulacern" sim
        com_faixa = self._hud(r, self._evento(("Katana", "Sai")))
        self.assertFalse(self._cor_em(com_faixa, self.COR1, linha))
        # caso zero: sem confronto (build, estreia, plano antigo) o nome segue la
        self.assertTrue(self._cor_em(self._hud(r, self._evento()), self.COR1, linha))

    def test_a_pergunta_aparece_no_quadro_0_na_zona_segura(self):
        r = VideoRenderer(self.render, "celular")
        topo = r._layout_do_topo()
        com = self._identidade(r, self._evento(("Katana", "Sai"))).getchannel("A")
        sem = self._identidade(r, self._evento(("Katana", "Sai"), pergunta="")).getchannel("A")
        faixa = (0, topo["pergunta_y"], r.width, topo["selo_y"] - 1)
        self.assertIsNotNone(com.crop(faixa).getbbox(), "a pergunta nao foi desenhada")
        self.assertIsNone(sem.crop(faixa).getbbox(), "caso zero: sem pergunta, nada ali")
        caixa = com.getbbox()
        self.assertGreater(caixa[1], topo["hud_baixo"])
        self.assertLessEqual(caixa[2], (1 - ZONA_DAS_PLATAFORMAS["direita"]) * r.width)
        self.assertLessEqual(caixa[3], topo["ident_baixo"])
        # e some com a identidade
        self.assertIsNone(self._identidade(r, self._evento(("Katana", "Sai")), 1.6)
                          .getchannel("A").getbbox())

    def test_a_identidade_com_a_faixa_diz_o_nome(self):
        r = VideoRenderer(self.render, "celular")
        ident = r._identidade_preparada(self._evento(("Katana", "Sai")))
        self.assertTrue(ident["lados"][0]["texto"].startswith("Aldric Solulacern · Necromancer"))

    def test_o_callout_que_nasce_com_a_identidade_fica_abaixo_da_pergunta(self):
        r = VideoRenderer(self.render, "celular")
        evento = dict(self._evento(("Katana", "Sai")),
                      callouts=[{"t": 0.0, "texto": "FIRST BLOOD", "duracao": 0.9}])
        callout = r._callouts_preparados(evento)[0]
        img = Image.new("RGBA", (r.width, r.height), (0, 0, 0, 0))
        r._desenhar_callout(img, callout, 0.0)          # pico do pop-in
        caixa_c = img.getchannel("A").getbbox()
        caixa_i = self._identidade(r, evento).getchannel("A").getbbox()
        self.assertGreater(caixa_c[1], caixa_i[3])

    def test_16x9_tambem_leva_a_faixa(self):
        r = VideoRenderer(self.render, "normal")
        img = self._hud(r, self._evento(("Tactical Knives", "Longsword")))
        self.assertTrue(self._cor_em(img, cor_legivel(self.COR1),
                                     (0, 0, r.width // 2, r.height // 4)))
        self.assertTrue(self._cor_em(img, cor_legivel(self.COR2),
                                     (r.width // 2, 0, r.width, r.height // 4)))

    def test_o_cartao_final_responde_a_pergunta_e_fica_na_faixa_segura(self):
        """Conferente, 20/10: "SHURIKEN WINS!" (o rotulo do vencedor), no
        centro da faixa (~475) e nada alem de x=900."""
        r = VideoRenderer(self.render, "celular")
        topo = r._layout_do_topo()
        for grande in ("SHURIKEN WINS!", "THREE-SECTION STAFF NECROMANCER WINS!"):
            with self.subTest(grande=grande):
                ver = r._veredito_preparado({"veredito": {
                    "de": 0.0, "vencedor": "Nyxaris Cinzamordaca", "titulo": grande,
                    "ko_type": "KO", "cartel_apos": "12W-3L"}})
                self.assertEqual(grande, ver["nome"].replace("\n", " "))
                self.assertTrue(ver["ko"].startswith("Nyxaris Cinzamordaca · KO"))
                img = Image.new("RGBA", (r.width, r.height), (0, 0, 0, 0))
                r._desenhar_veredito(img, ver, 1.0)
                caixa = img.getchannel("A").getbbox()
                self.assertLessEqual(caixa[2], 900)
                self.assertGreaterEqual(caixa[0], topo["margem"] - 1)
                self.assertLess(abs((caixa[0] + caixa[2]) / 2 - topo["direita"] / 2), 4)
        # caso zero: sem titulo, o nome do vencedor como antes
        sem = r._veredito_preparado({"veredito": {"de": 0.0, "vencedor": "Kael"}})
        self.assertEqual("Kael", sem["nome"])

    def test_rotulo_longo_quebra_em_duas_linhas_em_vez_de_encolher(self):
        """Conferente, 20/10: o rotulo longo encolhia a 31-47 px."""
        from builds.video.renderer import VEREDITO_CORPO_MIN, VEREDITO_ZONA
        r = VideoRenderer(self.render, "celular")
        minimo = int(r.ref * VEREDITO_CORPO_MIN)
        for grande in ("THREE-SECTION STAFF NECROMANCER WINS!",
                       "EXECUTIONER'S THREE-SECTION STAFF WINS!", "SHURIKEN WINS!"):
            with self.subTest(grande=grande):
                ver = r._veredito_preparado({"veredito": {
                    "de": 0.0, "vencedor": "Nyxaris Cinzamordaca", "titulo": grande,
                    "ko_type": "KO", "cartel_apos": "1W-0L"}})
                # ~70 px: o pior caso real ("THREE-SECTION STAFF NECROMANCER
                # WINS!", desempate pela classe na arma mais longa) fica em 67
                # em 3 linhas — "NECROMANCER WINS!" sozinho enche a largura
                self.assertGreaterEqual(ver["fonte"].size, minimo - 4)
                self.assertEqual(grande.replace(" ", "") , ver["nome"].replace("\n", "").replace(" ", ""))
                img = Image.new("RGBA", (r.width, r.height), (0, 0, 0, 0))
                r._desenhar_veredito(img, ver, 1.0)
                caixa = img.getchannel("A").getbbox()
                self.assertLessEqual(caixa[2], 900)
                self.assertGreaterEqual(caixa[1], VEREDITO_ZONA[0] * r.height - 1)
                # inteiro acima dos 20% de baixo que as plataformas cobrem
                self.assertLessEqual(caixa[3], (1 - ZONA_DAS_PLATAFORMAS["baixo"]) * r.height)
        # o curto fica numa linha so
        curto = r._veredito_preparado({"veredito": {"de": 0.0, "vencedor": "X",
                                                    "titulo": "SHURIKEN WINS!"}})
        self.assertNotIn("\n", curto["nome"])


class DueloCurtoTests(unittest.TestCase):
    """Conferente, 20/10: o duelo_00001 (5,8 s) sairia como um Short de 6 s."""

    def _duelo(self, tmp, duracao):
        pasta = Path(tmp) / f"duelo_{int(duracao * 10):05d}"
        pasta.mkdir()
        (pasta / "fight.json").write_text(json.dumps({"luta": {
            "p1": "A", "p2": "B", "confronto": {"p1": "Katana", "p2": "Sai"}}}),
            encoding="utf-8")
        (pasta / "edit_plan.json").write_text(json.dumps({"total_duration": duracao}),
                                              encoding="utf-8")
        (pasta / "final_celular.mp4").write_bytes(b"\0" * (catalogo.BYTES_MINIMOS + 1))

    def test_duelo_abaixo_de_15_s_nao_e_publicavel(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(catalogo, "OUTPUTS", Path(tmp)):
            self._duelo(tmp, 5.8)
            self._duelo(tmp, 15.0)
            config = dict(catalogo.carregar_config(), pasta_export=str(Path(tmp) / "_p"))
            videos = {v.fonte_id: v for v in catalogo.listar(config)
                      if v.origem == catalogo.DUELO}
        self.assertFalse(videos["duelo_00058"].pronto)
        self.assertIn("curto", videos["duelo_00058"].pendencias[0])
        self.assertTrue(videos["duelo_00150"].pronto)

    def test_a_descricao_nao_promete_o_que_nao_e(self):
        texto = catalogo.carregar_config()["descricoes"][catalogo.DUELO]
        self.assertNotIn("no edits", texto)
        self.assertIn("Computer-simulated duel. No script", texto)


if __name__ == "__main__":
    unittest.main()
