# -*- coding: utf-8 -*-
"""PUB-2: build que saiu so no TikTok vai ao YouTube depois (a divida).

Decisao do Adrian `publicacao/build-so-no-tiktok` (13/10/2026, commit
d104da1): "Mesma regra das historias" — "o YouTube sobe o build devido no
proximo horario, junto com o novo, ate zerar".

O defeito (auditoria de 11/10, `postar.md` #3): quando o YouTube dos builds
caia e o TikTok confirmava, a reposicao subia OUTRO build no YouTube
(`_builds_prontos` conta qualquer destino como publicado) e o primeiro ficava
so no TikTok para sempre. Medido contra o HEAD d6aedb45 com o ledger deste
teste (00101 so no TikTok, hoje): o YouTube recebia `generation_00102` e o
00101 ficava orfao. Agora o YouTube recebe 00101 (a divida) e 00102 (o novo,
"junto"), e o TikTok o 00102.

No ledger real, em 14/10/2026 02:22: 3 builds so no TikTok, nenhum desde
13/10. Em 14/10 (decisao `duelo-00076-ao-youtube`) o corte
(`CORTE_DA_DIVIDA_DOS_BUILDS`) passou para 12/10: 1 devido, o duelo_00076.
"""
from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"

G101 = "generation_00101:duelo:celular"
G102 = "generation_00102:duelo:celular"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_divida_builds",
                                                  POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


class _Build:
    def __init__(self, vid):
        self.id = vid
        self.titulo = f"Duelo {vid[11:16]}"
        self.perfil = "celular"
        self.formato = self.origem = "duelo"
        self.pendencias = []
        self.quando = ""


def _linha(vid, plataforma, quando):
    return {"canal": "builds", "plataforma": plataforma, "video_id": vid,
            "url": ("publicado no TikTok" if plataforma == "tiktok"
                    else "https://youtu.be/x"),
            "publicado": True, "quando": quando}


class DividaDosBuildsTests(unittest.TestCase):
    def setUp(self):
        from builds import atividade
        from builds.publicar import audio, desfecho, metricas, tiktok
        from builds.publicar import catalogo as C
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        pasta = Path(self.tmp.name)
        _trocar(self, desfecho, "arquivo_a_conferir",
                lambda canal, p="tiktok": pasta / f"{canal}_{p}.json")
        self.addCleanup(desfecho._SEM_MARCA.clear)
        self.desfecho = desfecho
        _trocar(self, atividade, "registrar", lambda *a, **k: None)
        hoje = (datetime.now() - timedelta(minutes=30)).isoformat(
            timespec="seconds")
        self.ledger = [_linha(G101, "tiktok", hoje)]
        _trocar(self, metricas, "publicados",
                lambda canal="builds": list(self.ledger))
        _trocar(self, C, "listar",
                lambda *a, **k: [_Build(G102), _Build(G101)])
        _trocar(self, audio, "revisar_marcas", lambda *a, **k: None)
        _trocar(self, tiktok, "confirmado",
                lambda e: str(e).startswith("publicado no TikTok"))
        self.m = m = _postar()
        m._linha = lambda *a, **k: None
        m._mandar_no_telegram = lambda texto: None
        m.publicou_neste_horario = lambda *a, **k: None
        m._tiktok_neste_horario = lambda agora=None: True
        m._registrar_valvula = lambda ficha: None
        m._audio_mudo = lambda v: ""
        m.titulo_repetido = lambda *a, **k: False
        m._sem_titulo_repetido = lambda fila, canal, config=None: (fila, [])
        m._cabe_antes_do_proximo = lambda *a, **k: True
        self.youtube, self.tiktok = [], []

        def no_youtube(alvo, laudo=None):
            self.youtube.append(alvo.id)
            return f"https://youtu.be/{alvo.id[11:16]}"

        def no_tiktok(alvo, falha=None):
            self.tiktok.append(alvo.id)
            return "publicado no TikTok"
        m._youtube_dos_builds = no_youtube
        m._tiktok_dos_builds = no_tiktok

    def test_o_youtube_sobe_o_devido_e_o_tiktok_o_proximo(self):
        ficha = self.m.postar_build()
        self.assertEqual(G101, self.youtube[0], "a divida primeiro")
        self.assertEqual([G101, G102], self.youtube,
                         "junto com o novo (alcance)")
        self.assertEqual([G102], self.tiktok)
        self.assertEqual(G101, ficha["alvo"])
        self.assertTrue(ficha["youtube_devido"])
        self.assertEqual(G102, ficha["tiktok_alvo"])
        self.assertTrue(ficha["feito"])

    def test_linha_do_tiktok_antes_do_corte_nao_muda_nada(self):
        self.ledger[:] = [_linha(G101, "tiktok", "2026-10-11T23:59:00")]
        self.assertEqual("2026-10-12", self.m.CORTE_DA_DIVIDA_DOS_BUILDS)
        ficha = self.m.postar_build()
        self.assertEqual([G102], self.youtube)
        self.assertEqual([G102], self.tiktok)
        self.assertFalse(ficha.get("youtube_devido"))

    def test_duelo_de_12_10_entra_na_divida(self):
        """Decisao `duelo-00076-ao-youtube` (14/10): o de 12/10 16:31 e devido.

        Medido no ledger real em 14/10: corte 13/10 = 0 devidos, 12/10 = 1.
        """
        self.ledger[:] = [_linha(G101, "tiktok", "2026-10-12T16:31:22")]
        ficha = self.m.postar_build()
        self.assertEqual(G101, self.youtube[0])
        self.assertTrue(ficha["youtube_devido"])

    def test_caso_zero_ledger_vazio(self):
        self.ledger[:] = []
        self.assertEqual((None, "", []),
                         self.m._divida_do_youtube_dos_builds())
        self.m.postar_build()
        self.assertEqual([G101], self.youtube, "a fila normal: o mais antigo")
        self.assertEqual([G101], self.tiktok)

    def test_ja_no_youtube_nao_e_divida(self):
        quando = self.ledger[0]["quando"]
        self.ledger.append(_linha(G101, "youtube", quando))
        self.assertIsNone(self.m._divida_do_youtube_dos_builds()[0])

    def test_reposicao_no_mesmo_horario_junta_na_mesma_ficha(self):
        """O YouTube caiu por rede, o TikTok levou o 00101 NESTE horario: a
        reposicao sobe o MESMO 00101 so no YouTube, e as fichas se juntam.
        Antes subia o 00102 e o 00101 ficava orfao."""
        antes = {"canal": "builds", "feito": True, "alvo": G101, "url": "",
                 "youtube_falhou": True, "tiktok": "publicado no TikTok",
                 "motivo": "YouTube falhou: TimeoutError: timed out"}
        self.m.publicou_neste_horario = (
            lambda canal, plataforma="youtube":
            self.ledger[0] if plataforma == "tiktok" else None)
        nova = self.m.postar_build()
        self.assertEqual([G101], self.youtube)
        self.assertEqual([], self.tiktok)
        self.assertTrue(nova["so_youtube"])
        junta, extra = self.m._juntar_reposicao(antes, nova)
        self.assertIsNone(extra)
        self.assertEqual(G101, junta["alvo"])
        self.assertTrue(junta["url"])

    def test_devido_a_conferir_no_youtube_nao_sobe(self):
        self.desfecho.marcar_para_conferir("builds", G101, "cliquei",
                                           "youtube")
        alvo, _quando, motivos = self.m._divida_do_youtube_dos_builds()
        self.assertIsNone(alvo)
        self.assertIn("a conferir", motivos[0])
        self.m.postar_build()
        self.assertEqual([G102], self.youtube)

    def test_devido_mudo_nao_sobe(self):
        self.m._audio_mudo = lambda v: ("luta muda" if v.id == G101 else "")
        alvo, _q, motivos = self.m._divida_do_youtube_dos_builds()
        self.assertIsNone(alvo)
        self.assertIn("luta muda", motivos[0])

    def test_so_ver_mostra_a_divida_sem_subir(self):
        veria = self.m.postar_build(so_ver=True)
        self.assertEqual(G101, veria["veria"])
        self.assertEqual(G102, veria["veria_tiktok"])
        self.assertTrue(veria["youtube_devido"])
        self.assertEqual([], self.youtube + self.tiktok)

    def test_youtube_que_cai_na_divida_nao_faz_o_alcance(self):
        def cai(alvo, laudo=None):
            self.youtube.append(alvo.id)
            raise RuntimeError("Studio caiu")
        self.m._youtube_dos_builds = cai
        ficha = self.m.postar_build()
        self.assertEqual([G101], self.youtube)
        self.assertEqual([G102], self.tiktok)
        self.assertNotIn("youtube_alcance", ficha)


if __name__ == "__main__":
    unittest.main()
