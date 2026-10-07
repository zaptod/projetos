# -*- coding: utf-8 -*-
"""A parte que caiu so no YouTube: o YouTube sobe a MESMA parte (06/10/2026).

Decisao do Adrian (Grimorio `publicacao/youtube-caiu-depois-do-tiktok`):
"subir a MESMA parte no YouTube — a serie fica completa e em ordem nos dois
lugares; o YouTube pode ficar um horario atras do TikTok."

O caso medido: as 00:37 de 06/10 a `historia_00054:celular:p02` saiu so no
TikTok (o Studio levou 126 s para abrir). A fila conta qualquer destino como
publicado, entao a reposicao por rede e as rodadas seguintes levavam ao
YouTube a p03 — no canal, Parte 1 e Parte 3, sem a 2, para sempre.

Conta de mao, com a h54 p01 nos dois destinos e a p02 so no TikTok:
  - reposicao no mesmo horario: antes, YouTube = p03 (e duas fichas, p02 no
    TikTok e p03 no YouTube); agora, YouTube = p02 e UMA ficha feita;
  - horario seguinte: antes, YouTube = TikTok = p03; agora, YouTube = p02 e
    TikTok = p03 (o YouTube um horario atras);
  - p02 com pedaco no ar (lista "a conferir" do YouTube) ou TikTok antes do
    corte: nao e divida, YouTube = TikTok = p03, como antes.

Dubla `serie`, `catalogo`, a fila, o TikTok e o YouTube: nada de rede nem do
ledger real.

Rode de dentro de historias/:
    python -m unittest tests.test_divida_do_youtube_regressions -v
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_divida_youtube",
                                                  POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


class _Parte:
    def __init__(self, n: int):
        self.id = f"historia_00054:celular:p{n:02d}"
        self.fonte_id, self.parte, self.partes = "historia_00054", n, 6
        self.titulo = f"A Conta Dividida (Parte {n}/6)"
        self.caminho = f"p{n:02d}.mp4"
        self.perfil = "celular"


P1, P2, P3, P4 = (_Parte(n) for n in (1, 2, 3, 4))
CATALOGO = [P1, P2, P3, P4]

QUEDA = ("infraestrutura: nao consegui abrir o envio de video (o clique no "
         "Criar nao passou (TimeoutError)). A pagina levou 126 s para abrir "
         "(o normal e 8-30 s).")


def _linha_do_ledger(parte, plataforma, quando, neste=False):
    return {"quando": quando, "plataforma": plataforma, "video_id": parte.id,
            "fonte_id": parte.fonte_id, "parte": parte.parte,
            "partes": parte.partes, "titulo": parte.titulo,
            "url": f"publicado no {plataforma}", "publicado": True,
            "neste": neste}


class DividaDoYoutubeTests(unittest.TestCase):
    def setUp(self):
        from builds import travas
        from builds.publicar import tiktok
        from contos.publicar import catalogo, qualidade, serie
        self.m = _postar()
        self.log = []
        self.m._linha = lambda *a, **_k: self.log.append(" ".join(map(str, a)))
        self.m._dormir = lambda _s: None
        self.m.esperar_a_rede = lambda **k: True
        self.m._ainda_no_horario = lambda comeco, slot, **k: True
        self.m._tiktok_neste_horario = lambda agora=None: True
        self.m.titulo_repetido = lambda *a, **k: False
        self.m._registrar_valvula = lambda ficha: None
        self.m._valvula_da_parte = lambda ficha, alvo: ""
        self.m._retida_chegou_ao_tiktok = lambda alvo, ficha: None
        self.m._visibilidade_das_historias = lambda: "public"
        self.m._fontes_cheias_hoje = lambda *a, **k: set()
        self.a_conferir: dict = {}
        self.m.a_conferir_no_tiktok = (
            lambda canal="historias", plataforma="tiktok":
            set(self.a_conferir.get(plataforma, ())))

        # O ledger: a p01 saiu nos dois destinos no 23:37 de 05/10.
        self.ledger = [
            _linha_do_ledger(P1, "youtube", "2026-10-05T23:40:00"),
            _linha_do_ledger(P1, "tiktok", "2026-10-05T23:43:00")]

        def neste_horario(canal, plataforma="youtube", agora=None):
            return next((l for l in reversed(self.ledger)
                         if l["plataforma"] == plataforma and l["neste"]),
                        None)
        self.m.publicou_neste_horario = neste_horario

        def ja_publicado(video_id, plataforma="youtube"):
            return next((l for l in reversed(self.ledger)
                         if l["video_id"] == video_id
                         and l["plataforma"] == plataforma), None)

        def registrar(video, url, plataforma, quando_publica=None, extra=None):
            linha = _linha_do_ledger(video, plataforma, "2026-10-06T00:45:00",
                                     neste=True)
            self.ledger.append(linha)
            return linha
        _trocar(self, serie, "publicados", lambda: list(self.ledger))
        _trocar(self, serie, "ja_publicado", ja_publicado)
        _trocar(self, serie, "registrar", registrar)
        _trocar(self, catalogo, "listar", lambda *a, **k: list(CATALOGO))
        _trocar(self, qualidade, "vistoriar_parte",
                lambda *a, **k: {"ok": True, "erros": [], "avisos": []})
        _trocar(self, travas, "ocupada", lambda *a, **k: False)
        roteiro = sys.modules.get("contos.roteiro.roteiro")
        if roteiro is None:
            import contos.roteiro.roteiro as roteiro
        _trocar(self, roteiro, "carregar", lambda *a, **k: {})
        _trocar(self, tiktok, "confirmado",
                lambda estado: estado == "publicado no TikTok")

        # A fila: como `fila_de_historias`, QUALQUER destino conta.
        def proxima(**_k):
            ja = {l["video_id"] for l in self.ledger}
            livres = [v for v in CATALOGO if v.id not in ja]
            return (livres[0] if livres else None), []
        self.m.proxima_historia = proxima

        self.no_youtube, self.no_tiktok = [], []
        self.quedas_do_youtube = 0

        def publicar_youtube(alvo, visibilidade=None, *, provas=None, **_k):
            self.no_youtube.append(alvo.id)
            if self.quedas_do_youtube:
                self.quedas_do_youtube -= 1
                raise RuntimeError(QUEDA)
            provas.append({"youtube_id": f"YT_{alvo.parte}",
                           "estado": "publicado"})
            return "publicado no YouTube"
        _trocar(self, catalogo, "publicar_youtube", publicar_youtube)

        def tiktok_posta(alvo, falha=None):
            self.no_tiktok.append(alvo.id)
            self.ledger.append(_linha_do_ledger(alvo, "tiktok",
                                                "2026-10-06T00:44:00",
                                                neste=True))
            return "publicado no TikTok"
        self.m._tiktok_das_historias = tiktok_posta

    def _no_youtube_do_ledger(self):
        return [l["video_id"] for l in self.ledger
                if l["plataforma"] == "youtube"]

    def test_reposicao_sobe_a_mesma_parte_numa_ficha_so(self):
        """O 00:37 de 06/10: YouTube caiu por rede, TikTok levou a p02. Antes
        a reposicao subia a p03 no YouTube; agora sobe a p02."""
        self.quedas_do_youtube = 1
        fichas = self.m._publicar_canal("historias", self.m.postar_historia,
                                        so_ver=False, comeco=0.0, slot=0)
        self.assertEqual([P2.id, P2.id], self.no_youtube)
        self.assertEqual([P2.id], self.no_tiktok)
        self.assertEqual(1, len(fichas), fichas)
        ficha = fichas[0]
        self.assertEqual(P2.id, ficha["alvo"])
        self.assertTrue(ficha["feito"])
        self.assertTrue(ficha["reposto"])
        self.assertEqual("publicado no YouTube", ficha["url"])
        self.assertNotIn("youtube_falhou", ficha)
        self.assertNotIn("motivo", ficha)
        self.assertEqual("publicado no TikTok", ficha["tiktok"])
        self.assertEqual([], self.m._derrubados_pela_rede(ficha))
        self.assertEqual([P1.id, P2.id], self._no_youtube_do_ledger())

    def test_juntar_reposicao_so_youtube(self):
        r = {"canal": "historias", "feito": True, "alvo": P2.id, "url": "",
             "tiktok": "publicado no TikTok", "youtube_falhou": True,
             "motivo": "YouTube falhou: RuntimeError: " + QUEDA}
        nova = {"canal": "historias", "feito": True, "alvo": P2.id,
                "url": "publicado no YouTube", "tiktok": "",
                "so_youtube": True, "youtube_devido": "2026-10-06T00:39:00"}
        junta, extra = self.m._juntar_reposicao(r, nova)
        self.assertIsNone(extra)
        self.assertEqual("publicado no YouTube", junta["url"])
        self.assertEqual("publicado no TikTok", junta["tiktok"])
        self.assertNotIn("youtube_falhou", junta)
        self.assertNotIn("motivo", junta)
        self.assertTrue(junta["reposto"] and junta["feito"])

    def test_horario_seguinte_youtube_p02_e_tiktok_p03(self):
        self.ledger.append(_linha_do_ledger(P2, "tiktok",
                                            "2026-10-06T00:39:00"))
        ficha = self.m.postar_historia()
        self.assertEqual([P2.id], self.no_youtube)
        self.assertEqual([P3.id], self.no_tiktok)
        self.assertEqual(P2.id, ficha["alvo"])
        self.assertEqual(P3.id, ficha["tiktok_alvo"])
        self.assertEqual("2026-10-06T00:39:00", ficha["youtube_devido"])
        self.assertTrue(ficha["feito"])
        # Ledger certo por destino.
        self.assertEqual([P1.id, P2.id], self._no_youtube_do_ledger())
        self.assertIn(P3.id, [l["video_id"] for l in self.ledger
                              if l["plataforma"] == "tiktok"])

    def test_ver_mostra_o_que_o_youtube_levaria(self):
        self.ledger.append(_linha_do_ledger(P2, "tiktok",
                                            "2026-10-06T00:39:00"))
        r = self.m.postar_historia(so_ver=True)
        self.assertEqual(P2.id, r["veria"])
        self.assertEqual(P3.id, r["veria_tiktok"])
        self.assertEqual([], self.no_youtube)
        self.assertEqual([], self.no_tiktok)

    def test_youtube_ja_saiu_com_a_divida_tiktok_leva_a_proxima(self):
        """Reposicao do TikTok depois de o YouTube ter levado a divida: o
        TikTok nao fica vazio tentando a p02 (que ja e dele)."""
        self.ledger.append(_linha_do_ledger(P2, "tiktok",
                                            "2026-10-06T00:39:00"))
        self.ledger.append(_linha_do_ledger(P2, "youtube",
                                            "2026-10-06T09:40:00", neste=True))
        ficha = self.m.postar_historia()
        self.assertEqual([], self.no_youtube)
        self.assertEqual([P3.id], self.no_tiktok)
        self.assertTrue(ficha["so_tiktok"])
        self.assertEqual(P3.id, ficha["tiktok_alvo"])

    def test_pedaco_no_ar_nao_e_divida(self):
        """A p02 esta na lista "a conferir" do YouTube (`ParteMeioNoAr`):
        subir de novo duplicaria o pedaco no ar. O YouTube segue a fila."""
        self.ledger.append(_linha_do_ledger(P2, "tiktok",
                                            "2026-10-06T00:39:00"))
        self.a_conferir = {"youtube": {P2.id + ":corte01"}}
        ficha = self.m.postar_historia()
        self.assertNotIn(P2.id, self.no_youtube)
        self.assertEqual([P3.id], self.no_youtube)
        self.assertEqual([P3.id], self.no_tiktok)
        self.assertNotIn("youtube_devido", ficha)
        self.assertTrue(any("a conferir" in l and P2.id in l
                            for l in self.log), self.log)

    def test_tiktok_antes_do_corte_nao_e_divida(self):
        self.ledger.append(_linha_do_ledger(P2, "tiktok",
                                            "2026-10-04T23:59:00"))
        ficha = self.m.postar_historia()
        self.assertEqual([P3.id], self.no_youtube)
        self.assertEqual([P3.id], self.no_tiktok)
        self.assertNotIn("youtube_devido", ficha)
        self.assertNotIn("tiktok_alvo", ficha)

    def test_divida_respeita_a_ordem_no_youtube(self):
        """p03 so no TikTok, mas a p02 (antes do corte) nao esta no YouTube:
        subir a p03 abriria o buraco que a regra existe para fechar."""
        self.ledger.append(_linha_do_ledger(P2, "tiktok",
                                            "2026-10-04T23:59:00"))
        self.ledger.append(_linha_do_ledger(P3, "tiktok",
                                            "2026-10-06T00:39:00"))
        self.assertIsNone(self.m._divida_do_youtube()[0])

    def test_o_caso_real_p01_e_p02_so_no_tiktok(self):
        """O ledger de 06/10, 23:59: a h54 p01 saiu so no TikTok as 23:50 de
        05/10 e a p02 as 00:49 de 06/10. Com o corte em 06/10 a p01 ficava
        de fora e a p02 nunca saia (a ordem pede a p01): o YouTube deve as
        DUAS, a p01 primeiro, e o TikTok segue com a p03."""
        self.ledger[:] = [
            _linha_do_ledger(P1, "tiktok", "2026-10-05T23:50:02"),
            _linha_do_ledger(P2, "tiktok", "2026-10-06T00:49:43")]
        alvo, quando, _motivos = self.m._divida_do_youtube()
        self.assertEqual((P1.id, "2026-10-05T23:50:02"), (alvo.id, quando))
        ficha = self.m.postar_historia()
        self.assertEqual(([P1.id], [P3.id]), (self.no_youtube, self.no_tiktok))
        self.assertEqual(P3.id, ficha["tiktok_alvo"])
        # Horario seguinte: agora a p02 e a divida (a p01 ja esta no YouTube).
        for linha in self.ledger:
            linha["neste"] = False
        self.assertEqual(P2.id, self.m._divida_do_youtube()[0].id)

    def test_teto_do_youtube_vale_para_a_divida(self):
        self.ledger.append(_linha_do_ledger(P2, "tiktok",
                                            "2026-10-06T00:39:00"))
        self.m._fontes_cheias_hoje = (
            lambda pub, plataforma="tiktok", agora=None:
            {"historia_00054"} if plataforma == "youtube" else set())
        alvo, _quando, motivos = self.m._divida_do_youtube()
        self.assertIsNone(alvo)
        self.assertIn("hoje no YouTube", motivos[0])

    def test_sem_divida_tudo_como_antes(self):
        """Caso zero: nada so no TikTok. Mesmo alvo nos dois destinos."""
        self.assertEqual((None, "", []), self.m._divida_do_youtube())
        ficha = self.m.postar_historia()
        self.assertEqual([P2.id], self.no_youtube)
        self.assertEqual([P2.id], self.no_tiktok)
        self.assertEqual(P2.id, ficha["alvo"])
        self.assertNotIn("tiktok_alvo", ficha)
        self.assertNotIn("youtube_devido", ficha)
        self.assertNotIn("so_youtube", ficha)


if __name__ == "__main__":
    unittest.main()
