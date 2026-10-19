# -*- coding: utf-8 -*-
"""O HUD do topo do celular fora do que o TikTok e o Shorts cobrem (18/10/2026).

Decisao ``builds/hud-do-topo-zona-segura``: as barras de vida e os nomes do
duelo ficavam em y 56-168 de 1920 (2,9-8,8% da altura), sob as abas
"Seguindo | Para voce" e o LIVE do TikTok e a linha de icones do Shorts, e o
HUD do p2 ia a 96,5% da largura, sob a coluna de botoes. Agora:

- HUD, identidade e callouts do celular ficam abaixo do topo de
  ``ZONA_DAS_PLATAFORMAS`` (10%) e a esquerda da coluna (88%), o p2
  espelhado do p1 dentro dessa faixa;
- nada se cruza: HUD, identidade, callouts (com o pop-in de 1,35x), o
  letreiro do K.O. e o veredito;
- a camera da cauda reserva o HUD (``reserva_do_letreiro()["hud"]``) e o
  letreiro, os dois lidos da caixa REAL que o renderer pinta.

O caso ZERO (o HUD na posicao antiga) tem de acusar.
"""
from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from PIL import Image  # noqa: E402

from builds.generation.session_generator import load_config  # noqa: E402
from builds.tournament.runner import reserva_do_letreiro  # noqa: E402
from builds.video.renderer import (POP_IN_CALLOUT, VEREDITO_ZONA,  # noqa: E402
                                   ZONA_DAS_PLATAFORMAS, VideoRenderer,
                                   caixa_do_hud, caixa_do_letreiro)

NOMES = [("Gunnar Vexevok", "Aurelia Argalacern"), ("Kuro", "Ana"),
         ("Genevieve o Destruidor #2", "Ícaro Ângelo Çavuşoğlu"),
         ("Wren Telgyll", "Emi Ossarhamar")]


# As cenas do teste do letreiro (test_letreiro_do_ko_regressions): vencedor e
# perdedor (x, y em m) longe, perto e com o vencedor encostado na parede; mais
# o vencedor no alto da arena, que e onde ele sobe para baixo do HUD.
CENAS_DA_CAUDA = {
    "Vulcao": [((20.0, 8.0), (6.0, 20.0)), ((13.0, 10.0), (14.0, 10.5)),
               ((24.6, 13.0), (12.0, 13.0)), ((12.0, 1.5), (12.0, 12.0))],
    "Torre": [((5.0, 4.0), (5.0, 14.0)), ((5.0, 9.0), (6.0, 9.3)),
              ((9.6, 9.0), (3.0, 14.0)), ((5.0, 1.2), (5.0, 9.0))],
}


def _lutador(x, y, morto=False, tamanho=1.0):
    return SimpleNamespace(pos=[x, y], z=0.0, morto=morto, raio_fisico=tamanho / 4.0,
                           dados=SimpleNamespace(tamanho=tamanho))


def _cruza(a, b) -> bool:
    return bool(a and b and a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3])


def _dentro_da_zona(caixa, largura, altura) -> bool:
    """Inteira abaixo do topo coberto e a esquerda da coluna de botoes."""
    return (caixa[1] >= ZONA_DAS_PLATAFORMAS["topo"] * altura
            and caixa[2] <= (1.0 - ZONA_DAS_PLATAFORMAS["direita"]) * largura
            and caixa[3] <= (1.0 - ZONA_DAS_PLATAFORMAS["baixo"]) * altura)


class HudNaZonaSeguraTests(unittest.TestCase):
    PERFIL = "celular"

    @classmethod
    def setUpClass(cls):
        cls.render = load_config("render.json")
        cls.callouts_cfg = load_config("editing.json").get("fight_callouts") or {}

    def _renderer(self):
        return VideoRenderer(self.render, self.PERFIL)

    def _hud(self, renderer, p1, p2, hp=(20.0, 20.0), plano=True, nomes=True):
        hud = {"p1": p1, "p2": p2, "nomes": nomes,
               "serie_hp": [[0.0, hp[0], hp[1]]]}
        if plano:
            hud["serie_plano"] = [[0.0, "QUEBRAR GUARDA", 1.0, "TROCAÇÃO", 1.0]]
        preparado = renderer._hud_preparado({"hud": hud})
        img = Image.new("RGBA", (renderer.width, renderer.height), (0, 0, 0, 0))
        renderer._desenhar_hud(img, preparado, 0.0)       # t=0: o contorno da vida critica
        return img

    def _identidade(self, renderer, selo="TITULO EM JOGO"):
        evento = {"identidade": {
            "ate": 1.5, "selo": selo,
            "p1": {"arma": "Machado de Guerra Ancestral", "classe": "Berserker (Furia)",
                   "cartel": "12V-3D"},
            "p2": {"arma": "Agulhas Envenenadas", "classe": "Assassino", "cartel": "1V-0D"}}}
        ident = renderer._identidade_preparada(evento)
        img = Image.new("RGBA", (renderer.width, renderer.height), (0, 0, 0, 0))
        renderer._desenhar_identidade(img, ident, 0.0)
        return img.getchannel("A").getbbox(), evento

    def _textos_de_callout(self):
        textos = []
        for lista in (self.callouts_cfg.get("textos") or {}).values():
            for texto in lista:
                textos.append(texto.replace("{N}", "10").replace("{ROTULO}", "QUEBRAR GUARDA"))
        self.assertGreater(len(textos), 20)
        return textos

    def _caixas_de_callout(self, renderer, evento_base, t):
        """Cada texto de callout do config, nascendo em ``t``, no pico do pop-in
        (idade 0 = 1,35x, o maior) e depois dele."""
        caixas = []
        for texto in sorted(set(self._textos_de_callout())):
            evento = dict(evento_base, callouts=[{"t": t, "texto": texto, "duracao": 0.9}])
            preparado = renderer._callouts_preparados(evento)[0]
            for idade in (0.0, 0.5):
                img = Image.new("RGBA", (renderer.width, renderer.height), (0, 0, 0, 0))
                renderer._desenhar_callout(img, preparado, t + idade)
                caixa = img.getchannel("A").getbbox()
                if caixa:
                    caixas.append((texto, idade, caixa))
        return caixas

    # ------------------------------------------------------------------ HUD
    def test_o_hud_inteiro_fica_dentro_da_zona_segura(self):
        renderer = self._renderer()
        for p1, p2 in NOMES:
            for hp in ((100.0, 100.0), (20.0, 20.0), (0.0, 0.0)):
                with self.subTest(p1=p1, p2=p2, hp=hp):
                    caixa = self._hud(renderer, p1, p2, hp).getchannel("A").getbbox()
                    self.assertTrue(_dentro_da_zona(caixa, renderer.width, renderer.height),
                                    caixa)
                    # e longe do veredito
                    self.assertLess(caixa[3], VEREDITO_ZONA[0] * renderer.height)

    def test_o_p2_e_o_espelho_do_p1_dentro_da_faixa_segura(self):
        renderer = self._renderer()
        faixa = int(renderer.width * (1.0 - ZONA_DAS_PLATAFORMAS["direita"]))
        # sem nomes nem plano (cada texto tem a sua largura): molduras e barras
        img = self._hud(renderer, "", "", hp=(100.0, 100.0), plano=False, nomes=False)
        meio = faixa // 2
        esq = img.crop((0, 0, meio, renderer.height)).getchannel("A").getbbox()
        dir_ = img.crop((meio, 0, renderer.width, renderer.height)).getchannel("A").getbbox()
        self.assertLessEqual(abs(esq[0] - (faixa - (dir_[2] + meio))), 2, (esq, dir_))
        self.assertEqual((esq[1], esq[3]), (dir_[1], dir_[3]))
        # as barras: mesma largura, mesma altura, distancias iguais das bordas
        hud = renderer._hud_preparado({"hud": {"p1": "a", "p2": "b",
                                               "serie_hp": [[0.0, 1.0, 1.0]]}})
        (x1, y1, l1, a1, _c1, _l1), (x2, y2, l2, a2, _c2, _l2) = hud["barras"]
        self.assertEqual((y1, l1, a1), (y2, l2, a2))
        self.assertLessEqual(abs(x1 - (faixa - (x2 + l2))), 1)

    def test_caso_zero_o_hud_na_posicao_antiga_acusa(self):
        """A geometria de antes de 18/10 (y = 5,2% da altura, barra de 43% da
        largura, p2 encostado na borda direita) sai da zona pelos dois lados."""
        renderer = self._renderer()
        w, h = renderer.width, renderer.height
        largura, x1 = int(w * 0.43), int(w * 0.04)
        antigo = dict(renderer._layout_do_topo(), y=int(h * 0.052), x1=x1,
                      largura=largura, x2=w - x1 - largura)
        with mock.patch.object(VideoRenderer, "_layout_do_topo", return_value=antigo):
            caixa = self._hud(renderer, "Gunnar Vexevok", "Aurelia Argalacern") \
                .getchannel("A").getbbox()
        self.assertFalse(_dentro_da_zona(caixa, w, h), caixa)
        self.assertLess(caixa[1], ZONA_DAS_PLATAFORMAS["topo"] * h)          # sob as abas
        self.assertGreater(caixa[2], (1 - ZONA_DAS_PLATAFORMAS["direita"]) * w)  # sob os botoes

    def test_o_16x9_que_nao_vai_ao_shorts_nao_mudou(self):
        """O ``final_normal`` nao e publicado (so o celular vai ao TikTok e ao
        Shorts): o HUD, a identidade e os callouts dele seguem onde estavam
        (no PC, a caixa do HUD medida antes e depois e (63, 16, 1858, 128))."""
        renderer = VideoRenderer(self.render, "normal")
        w, h = renderer.width, renderer.height
        self.assertIsNone(renderer._layout_do_topo())
        hud = renderer._hud_preparado({"hud": {"p1": "a", "p2": "b",
                                               "serie_hp": [[0.0, 1.0, 1.0]]}})
        largura, x1 = int(w * 0.30), int(w * 0.035)
        self.assertEqual([b[:3] for b in hud["barras"]],
                         [(x1, int(h * 0.055), largura),
                          (w - x1 - largura, int(h * 0.055), largura)])
        callout = renderer._callouts_preparados({"callouts": [{"t": 0.0, "texto": "K.O."}]})[0]
        self.assertEqual(callout["cy"], int(h * 0.20))

    # ---------------------------------------------------- identidade e selo
    def test_identidade_e_selo_dentro_da_zona_e_abaixo_do_hud(self):
        renderer = self._renderer()
        hud = caixa_do_hud(self.render, self.PERFIL)
        for selo in ("TITULO EM JOGO", "Genevieve o Destruidor #2 VEM DE 12 SEGUIDAS", ""):
            with self.subTest(selo=selo):
                caixa, _evento = self._identidade(renderer, selo)
                self.assertTrue(_dentro_da_zona(caixa, renderer.width, renderer.height), caixa)
                self.assertGreater(caixa[1], hud[3])        # nada encosta no HUD

    # --------------------------------------------------------------- callouts
    def test_nenhum_callout_cruza_o_hud_nem_a_identidade(self):
        renderer = self._renderer()
        hud = caixa_do_hud(self.render, self.PERFIL)
        ident, evento = self._identidade(renderer)
        ate = evento["identidade"]["ate"]
        # o que nasce com a identidade na tela fica abaixo dela ...
        for texto, idade, caixa in self._caixas_de_callout(renderer, evento, 0.2):
            with self.subTest(texto=texto, idade=idade, com_identidade=True):
                self.assertFalse(_cruza(caixa, hud), (caixa, hud))
                self.assertFalse(_cruza(caixa, ident), (caixa, ident))
                self.assertLess(caixa[3], VEREDITO_ZONA[0] * renderer.height)
        # ... e o resto logo abaixo do HUD (o build e a estreia, sem
        # identidade, no mesmo lugar)
        for texto, idade, caixa in self._caixas_de_callout(renderer, evento, ate):
            with self.subTest(texto=texto, idade=idade, com_identidade=False):
                self.assertFalse(_cruza(caixa, hud), (caixa, hud))
                self.assertGreaterEqual(caixa[1], ZONA_DAS_PLATAFORMAS["topo"] * renderer.height)
                self.assertLess(caixa[3], VEREDITO_ZONA[0] * renderer.height)
        sem_identidade = renderer._callouts_preparados(
            {"callouts": [{"t": 0.2, "texto": "K.O."}]})[0]
        self.assertEqual(sem_identidade["cy"], renderer._layout_do_topo()["callout_cy"])

    def test_o_callout_nao_pula_quando_a_identidade_some(self):
        renderer = self._renderer()
        _ident, evento = self._identidade(renderer)
        evento = dict(evento, callouts=[{"t": 1.2, "texto": "CASTIGO", "duracao": 0.9},
                                        {"t": 2.0, "texto": "CASTIGO", "duracao": 0.9}])
        cedo, tarde = renderer._callouts_preparados(evento)
        topo = renderer._layout_do_topo()
        self.assertEqual(cedo["cy"], topo["callout_cy_identidade"])   # a vida toda
        self.assertEqual(tarde["cy"], topo["callout_cy"])
        self.assertGreater(cedo["cy"], tarde["cy"])

    # ------------------------------------------------- letreiro e a camera
    def test_a_reserva_le_o_hud_e_o_letreiro_reais_e_eles_nao_se_cruzam(self):
        reserva = reserva_do_letreiro(self.PERFIL)
        self.assertIsNotNone(reserva)
        altura = VideoRenderer(self.render, self.PERFIL).height
        hud = caixa_do_hud(self.render, self.PERFIL)
        self.assertAlmostEqual(reserva["hud"], hud[3] / altura, places=3)
        textos = (self.callouts_cfg.get("textos") or {}).get("ko") or ["K.O."]
        letreiros = [caixa_do_letreiro(self.render, self.PERFIL, t, 0.0) for t in textos]
        self.assertAlmostEqual(reserva["topo"], max(c[3] for c in letreiros) / altura, places=3)
        for caixa in letreiros:                          # no pico do pop-in
            self.assertFalse(_cruza(caixa, hud), (caixa, hud))
        self.assertGreater(reserva["topo"], reserva["hud"])
        self.assertAlmostEqual(POP_IN_CALLOUT, 1.35)

    def test_o_rosto_do_vencedor_nunca_sobe_para_baixo_do_hud_na_cauda(self):
        """A cauda inteira (slow-mo + festa) das cenas do teste do letreiro:
        o rosto e o nome do vencedor ficam abaixo do HUD em todo passo. Caso
        zero: sem o ``hud`` na reserva, alguma cena sobe para baixo dele."""
        reserva = reserva_do_letreiro(self.PERFIL)
        sem_hud = {k: v for k, v in reserva.items() if k != "hud"}
        limite = reserva["hud"] * 1920

        def subidas(res):
            achou = []
            for arena, cenas in CENAS_DA_CAUDA.items():
                for v, p in cenas:
                    vencedor, perdedor = _lutador(*v), _lutador(*p, morto=True)
                    for topo_tela in self._cauda(arena, vencedor, perdedor, res):
                        if topo_tela < limite:
                            achou.append((arena, v, round(topo_tela)))
                            break
            return achou

        self.assertEqual(subidas(reserva), [])
        self.assertGreater(len(subidas(sem_hud)), 0)

    def _cauda(self, arena, vencedor, perdedor, reserva):
        """O topo (px) do rosto+nome do vencedor em cada passo da cauda."""
        from neural_fights.core.arena import ARENAS
        from neural_fights.effects.camera import Câmera

        cfg = ARENAS[arena]
        cam = Câmera(1080, 1920)
        cam.set_arena_bounds(cfg.largura / 2, cfg.altura / 2, cfg.largura, cfg.altura)
        cam.modo = "DIRETOR"
        cam.diretor_largura_min_m = 5.5
        cam.reserva_pos_ko = reserva
        cam.zoom = cam._calcular_zoom_necessario(vencedor, perdedor,
                                                  zoom_max=cam._diretor_teto_zoom())
        cam.x, cam.y = cam._limitar_centro_a_arena(*cam._calcular_centro_ideal(vencedor, perdedor))
        topos = []
        for k, dt in enumerate([0.25 / 60] * 72 + [1 / 60] * 91):
            t = (k + 1) / 60
            cam.t_pos_ko = t
            # o pulo da festa comeca com a fanfarra (1,2 s) e vai ao maximo
            cam.pulo_pos_ko = 0.0 if t < 1.2 else 1.0
            vencedor.z = 0.0
            cam.atualizar(dt, vencedor, perdedor)
            if k < 2:
                continue                    # o 1o quadro e o do K.O. (o letreiro empurra)
            _x0, y0, _x1, _y1 = cam.caixa_do_rosto(vencedor, cam.zoom, cam.pulo_pos_ko)
            topos.append(cam.converter(0, y0)[1])
        return topos

    # ------------------------------------------------------ gravador (CLI)
    def test_o_gravador_recebe_o_hud_pela_linha_de_comando(self):
        from builds.tournament import capture
        from neural_fights.recording import fight_recorder

        vistos = []

        def rodar(comando, **_kw):
            vistos.append(comando)
            return SimpleNamespace(stdout='{"sucesso": true}', stderr="", returncode=0)

        with mock.patch.object(capture.subprocess, "run", side_effect=rodar):
            capture.gravar_uma(p1="a", p2="b", seed=1, saida=None, cenario="Arena",
                               reserva_pos_ko={"topo": 0.2656, "ate_s": 0.95, "hud": 0.1672})
            capture.gravar_uma(p1="a", p2="b", seed=1, saida=None, cenario="Arena",
                               reserva_pos_ko={"topo": 0.26, "ate_s": 0.95})
        com, sem = (c[c.index("--reserva-pos-ko") + 1] for c in vistos)
        self.assertEqual(com, "0.2656,0.950,0.1672")
        self.assertEqual(sem, "0.2600,0.950")
        self.assertEqual(fight_recorder.tipo_reserva_pos_ko(com),
                         {"topo": 0.2656, "ate_s": 0.95, "hud": 0.1672})
        self.assertEqual(fight_recorder.tipo_reserva_pos_ko(sem), {"topo": 0.26, "ate_s": 0.95})
        import argparse
        for ruim in ("0.2", "0.2,0.9,1.5", "a,b", "0.2,0.9,0.1,0.3"):
            with self.subTest(ruim=ruim), self.assertRaises(argparse.ArgumentTypeError):
                fight_recorder.tipo_reserva_pos_ko(ruim)


if __name__ == "__main__":
    unittest.main()
