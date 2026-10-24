# -*- coding: utf-8 -*-
"""YouTube de builds: duelo no lugar da estreia (decisao de 19/10/2026).

Medido na analise dos videos de 19/10 (28 dias, YouTube): duelo 111 views
por video (89 videos, 54% assistido), build 81, estreia 29 (27 videos, 13%).
A mistura do config (duelo 4, build 3, estreia 1) passa a valer inteira so
no TikTok; no YouTube vira duelo 5, build 3, estreia 0 — e cota zero e "so
quando ninguem mais quer": sem duelo sai o build; sem duelo nem build, a
estreia, para o horario nao ficar vazio.

Estoque medido em 19/10 13:55 (`_builds_prontos`, sem medir audio): 26
duelos, 10 builds, 52 estreias. Ritmo novo (`consumo_por_formato`): duelo
6,25/dia (era 5), build 3,75, estreia 0,75 (so o TikTok) — os duelos duram
~4 dias, os builds ~2,7; depois disso o YouTube leva estreia.
"""
from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timedelta
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"
MISTURA = {"grade": {"mistura": {"duelo": 4, "build": 3, "estreia": 1,
                                 "torneio": 0}}}


def _postar():
    spec = importlib.util.spec_from_file_location("postar_duelo", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    modulo._linha = lambda *a, **k: None
    return modulo


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


class _Build:
    def __init__(self, n, formato, quando=0.0):
        self.id = f"generation_{n:05d}:{formato}:celular"
        self.origem = formato
        self.titulo = f"{formato} {n}"
        self.perfil = "celular"
        self.pendencias = []
        self.quando = float(quando)


class CotaPorDestinoTests(unittest.TestCase):
    def test_conta_de_mao(self):
        m = _postar()
        cota = m.cota_da_grade(MISTURA)
        # Desde 20/10/2026 (docs/PLANO.md, canal de duelos) o build tambem
        # passa o peso ao duelo, e o TikTok troca igual.
        self.assertEqual({"duelo": 8, "build": 0, "estreia": 0, "torneio": 0},
                         m.cota_da_plataforma(cota, "youtube"))
        self.assertEqual(m.cota_da_plataforma(cota, "youtube"),
                         m.cota_da_plataforma(cota, "tiktok"),
                         "os dois destinos so com duelo")
        self.assertEqual({}, m.cota_da_plataforma({}, "youtube"), "zero")

    def test_estreia_pelo_formato_e_pelo_id(self):
        m = _postar()
        self.assertTrue(m._trocado_no_youtube("estreia"))
        self.assertTrue(m._trocado_no_youtube("generation_00066:estreia:celular"))
        self.assertFalse(m._trocado_no_youtube("duelo_00076:duelo:celular"))
        self.assertFalse(m._trocado_no_youtube(""))

    def test_ritmo_de_cada_formato(self):
        # O consumo le o RELOGIO da grade (3 duelos/dia ate 26/10, 8 desde
        # 27/10): fixa 21/10 para o teste nao quebrar sozinho no dia da troca.
        from datetime import date
        from builds import grade
        original = grade.tabela_do_canal
        self.addCleanup(setattr, grade, "tabela_do_canal", original)
        grade.tabela_do_canal = lambda quando=None: original(
            date(2026, 10, 21) if quando is None else quando)
        m = _postar()
        ritmo = m.consumo_por_formato(m.cota_da_grade(MISTURA))
        # 20/10/2026: 3 horarios dos builds no YouTube x 8/8 = 3 (era 6,25);
        # build e estreia de cota zero nao entram (eram 3,75 e 0,75).
        self.assertAlmostEqual(3.0, ritmo["duelo"])
        self.assertNotIn("build", ritmo)
        self.assertNotIn("estreia", ritmo)
        self.assertNotIn("torneio", ritmo)


class FilaDoYoutubeTests(unittest.TestCase):
    def setUp(self):
        from builds.publicar import metricas
        self.m = m = _postar()
        self.ledger = []
        _trocar(self, metricas, "publicados", lambda canal="builds": list(self.ledger))
        m._publicados_do_canal = lambda canal: list(self.ledger)
        m.a_conferir_no_tiktok = lambda canal="builds", p="youtube": set()
        m._audio_mudo = lambda v: ""
        self.pendentes = []
        # `_builds_prontos` devolve do mais NOVO para o mais velho
        m._builds_prontos = lambda config=None, **k: list(reversed(self.pendentes))

    def _servidos(self, *formatos):
        base = datetime.now() - timedelta(days=2)
        for i, f in enumerate(formatos):
            self.ledger.append({"video_id": f"generation_{900 + i:05d}:{f}:celular",
                                "origem": f, "plataforma": "youtube",
                                "quando": (base + timedelta(minutes=i)).isoformat(),
                                "url": "https://youtu.be/x", "publicado": True})

    def test_estreia_atrasada_nao_ganha_do_duelo(self):
        """Com a mistura antiga, 8 duelos e 0 estreia servidos davam a vez a
        estreia (0/1 < 8/4). Agora a estreia tem cota zero no YouTube."""
        self._servidos(*["duelo"] * 8)
        self.pendentes = [_Build(1, "estreia", 1), _Build(2, "duelo", 2)]
        self.assertEqual("duelo", self.m.proximo_build(MISTURA).origem)

    def test_sem_duelo_sai_o_build(self):
        self.pendentes = [_Build(1, "estreia", 1), _Build(2, "build", 2)]
        self.assertEqual("build", self.m.proximo_build(MISTURA).origem)

    def test_so_estreia_sai_a_estreia(self):
        """Cota zero nao e proibicao: o horario nao fica vazio."""
        self.pendentes = [_Build(1, "estreia", 1)]
        self.assertEqual("estreia", self.m.proximo_build(MISTURA).origem)

    def test_zero_estoque_vazio(self):
        self.pendentes = []
        self.assertIsNone(self.m.proximo_build(MISTURA))

    def test_servidos_contam_so_o_destino(self):
        self._servidos("duelo", "duelo")
        self.ledger.append({"video_id": "generation_00999:estreia:celular",
                            "origem": "estreia", "plataforma": "tiktok",
                            "quando": datetime.now().isoformat(),
                            "url": "publicado no TikTok", "publicado": True})
        self.assertEqual({"duelo": 2}, self.m._servidos_recentes(plataforma="youtube"))
        self.assertEqual({"estreia": 1}, self.m._servidos_recentes(plataforma="tiktok"))


class TiktokMantemAMisturaTests(unittest.TestCase):
    def setUp(self):
        from builds.publicar import metricas
        self.m = m = _postar()
        self.ledger = []
        _trocar(self, metricas, "publicados", lambda canal="builds": list(self.ledger))
        m.a_conferir_no_tiktok = lambda canal="builds", p="tiktok": set()
        m.desistencias_do_tiktok = lambda canal="builds": set()
        m._audio_mudo = lambda v: ""
        self.novos = []
        m._builds_prontos = lambda config=None, **k: list(self.novos)
        m._fontes_de_atraso = lambda canal: (list(self.ledger),
                                             {v.id: v for v in self.novos})

    def test_o_tiktok_tambem_so_leva_duelo(self):
        """Ate 19/10 o TikTok mantinha a mistura (8 duelos servidos davam a
        vez a estreia). Desde 20/10 (PLANO, canal de duelos) ele troca igual
        ao YouTube: com duelo na fila, sai o duelo; sem duelo, a estreia."""
        base = datetime.now() - timedelta(days=2)
        for i in range(8):
            self.ledger.append({"video_id": f"generation_{800 + i:05d}:duelo:celular",
                                "origem": "duelo", "plataforma": "tiktok",
                                "quando": (base + timedelta(minutes=i)).isoformat(),
                                "url": "publicado no TikTok", "publicado": True})
        self.novos = [_Build(1, "duelo", 1), _Build(2, "estreia", 2)]
        alvo, _motivo = self.m._vez_do_tiktok_builds(MISTURA)
        self.assertEqual("duelo", alvo.origem)
        self.novos = [_Build(2, "estreia", 2)]
        alvo, _motivo = self.m._vez_do_tiktok_builds(MISTURA)
        self.assertEqual("estreia", alvo.origem)

    def test_zero_sem_nada(self):
        alvo, motivo = self.m._vez_do_tiktok_builds(MISTURA)
        self.assertIsNone(alvo)
        self.assertTrue(motivo)


class EstreiaNaoEDividaTests(unittest.TestCase):
    def test_estreia_so_no_tiktok_nao_vai_ao_youtube(self):
        from builds.publicar import catalogo as C, metricas
        m = _postar()
        hoje = datetime.now().isoformat(timespec="seconds")
        e, d = _Build(1, "estreia"), _Build(2, "duelo")
        ledger = [{"video_id": e.id, "origem": "estreia", "plataforma": "tiktok",
                   "quando": hoje, "url": "publicado no TikTok", "publicado": True},
                  {"video_id": d.id, "origem": "duelo", "plataforma": "tiktok",
                   "quando": hoje, "url": "publicado no TikTok", "publicado": True}]
        _trocar(self, metricas, "publicados", lambda canal="builds": list(ledger))
        _trocar(self, C, "listar", lambda *a, **k: [e, d])
        m.titulo_repetido = lambda *a, **k: False
        m._sem_a_conferir = lambda fila, canal: fila
        m._audio_mudo = lambda v: ""
        divida, _quando, _motivos = m._divida_do_youtube_dos_builds()
        self.assertEqual(d.id, divida.id, "o duelo e divida; a estreia nao")
        ledger.pop()
        divida, _quando, _motivos = m._divida_do_youtube_dos_builds()
        self.assertIsNone(divida)

    def test_alcance_nao_leva_estreia(self):
        m = _postar()
        m._youtube_dos_builds = lambda *a, **k: self.fail("nao sobe estreia")
        ficha = {}
        m._alcance_do_youtube_dos_builds(ficha, _Build(1, "estreia"))
        self.assertIn("estreia", ficha["youtube_alcance"]["pulado"])


if __name__ == "__main__":
    unittest.main()
