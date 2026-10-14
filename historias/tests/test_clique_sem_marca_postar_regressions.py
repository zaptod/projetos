# -*- coding: utf-8 -*-
"""PUB-1 no `postar.py`: o clique que saiu nao pode voltar a fila.

Auditoria de 11/10/2026 (`publicar-builds.md` #4), verificada em 14/10. O
clique no YouTube foi dado, algo falhou depois, e a marca "a conferir"
TAMBEM falhou (trava ocupada, disco) e foi engolida:

  (a) builds: `youtube_clicou` so impedia a reposicao do MESMO horario; a
      rodada seguinte escolhia o mesmo `generation_*` de novo;
  (b) historias: o laudo do pedaco que caiu nunca entrava em `provas` (o
      catalogo so anexava depois do sucesso), a ficha nao ganhava
      `youtube_clicou` e, com a mensagem com cara de rede ("timed out"),
      `_derrubados_pela_rede(ficha)` dava `["youtube"]` — a parte era reposta
      NA HORA.

Medido contra o HEAD d6aedb45: (a) a rodada seguinte escolhia
`generation_00101` de novo; (b) `_derrubados_pela_rede(ficha) == ["youtube"]`
e a ficha sem `youtube_clicou`. Agora: (a) a mesma execucao nao o escolhe
(memoria do `desfecho`), a ficha da trava leva `sem_marca`, e a rodada
seguinte grava a marca ANTES de escolher — ou nao publica; (b) `[]`.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"

A = "generation_00101:duelo:celular"
B = "generation_00102:duelo:celular"
PARTE = "historia_00090:celular:p02"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_clique_sem_marca",
                                                  POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


class _Video:
    def __init__(self, vid, **extra):
        self.id = vid
        self.titulo = f"titulo de {vid}"
        self.pendencias = []
        self.__dict__.update(extra)


class _Base(unittest.TestCase):
    def setUp(self):
        from builds import atividade
        from builds.publicar import desfecho
        self.desfecho = desfecho
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)
        _trocar(self, desfecho, "arquivo_a_conferir",
                lambda canal, p="tiktok":
                self.pasta / f"{canal}_{p}_a_conferir.json")
        _trocar(self, desfecho, "PAUSA_ENTRE_TENTATIVAS_S", 0.0)
        self.addCleanup(desfecho._SEM_MARCA.clear)
        desfecho._SEM_MARCA.clear()
        self.diario = []
        _trocar(self, atividade, "registrar",
                lambda *a, **k: self.diario.append(a))
        self.m = m = _postar()
        self.telegram = []
        m._mandar_no_telegram = lambda texto: self.telegram.append(texto)
        m._linha = lambda *a, **k: None
        m._arquivo_da_dona = lambda: self.pasta / "postar__rodada.dona.json"
        m.publicou_neste_horario = lambda *a, **k: None
        m._tiktok_neste_horario = lambda agora=None: True
        m._registrar_valvula = lambda ficha: None
        m.titulo_repetido = lambda *a, **k: False

    def _marca_falha(self):
        """A marca "a conferir" nao grava (trava ocupada), como na auditoria."""
        self.gravar_real = self.desfecho._gravar_marca

        def ocupada(*a, **k):
            raise self.desfecho._MarcaNaoGravou("a trava esta ocupada")
        _trocar(self, self.desfecho, "_gravar_marca", ocupada)

    def _no_disco(self, canal, destino):
        caminho = self.desfecho.arquivo_a_conferir(canal, destino)
        return set(self.desfecho._ler(caminho)) if caminho.is_file() else set()


class BuildsTests(_Base):
    def setUp(self):
        super().setUp()
        m = self.m
        m._divida_do_youtube_dos_builds = lambda: (None, "", [])
        # A fila de verdade (`proximo_build`), com o catalogo e a cota dublados.
        m._builds_prontos = lambda *a, **k: [_Video(B), _Video(A)]
        m._sem_fonte_cheia = lambda fila, canal, agora=None: fila
        m._servidos_recentes = lambda: {}
        m.cota_da_grade = lambda config=None: {}
        m.escolher_por_cota = lambda pendentes, servidos, cota: pendentes[0]
        m._audio_mudo = lambda v: ""
        from builds.publicar import audio
        _trocar(self, audio, "revisar_marcas", lambda *a, **k: None)
        self.youtube = []

        def youtube_clica_e_cai(alvo, laudo=None):
            self.youtube.append(alvo.id)
            laudo["clicou"] = True
            raise TimeoutError("timed out")
        m._youtube_dos_builds = youtube_clica_e_cai
        m._tiktok_dos_builds = lambda alvo, falha=None: "publicado no TikTok"
        from builds.publicar import tiktok
        _trocar(self, tiktok, "confirmado",
                lambda e: str(e).startswith("publicado no TikTok"))

    def test_a_mesma_execucao_nao_escolhe_de_novo(self):
        self._marca_falha()
        self.m._gravar_dona("rodada")
        ficha = self.m.postar_build()
        self.assertEqual(A, ficha["alvo"])
        self.assertTrue(ficha["youtube_clicou"])
        self.assertNotIn("youtube", self.m._derrubados_pela_rede(ficha))
        # A reposicao/volta final desta mesma execucao nao leva o A:
        self.assertEqual(B, self.m.proximo_build().id)
        self.assertTrue(self.telegram, "avisa que o clique ficou sem marca")

    def test_a_ficha_da_trava_leva_o_clique_e_a_rodada_seguinte_marca(self):
        self._marca_falha()
        self.m._gravar_dona("rodada")
        self.m.postar_build()
        ficha = json.loads(self.m._arquivo_da_dona().read_text("utf-8"))
        self.assertEqual([A], [i["alvo"] for i in ficha["sem_marca"]])
        self.assertEqual("youtube", ficha["sem_marca"][0]["destino"])

        # RODADA SEGUINTE = outro processo: memoria vazia, disco de volta.
        self.desfecho._SEM_MARCA.clear()
        self.m._DONA.clear()
        self.desfecho._gravar_marca = self.gravar_real
        with self.m._trava_da_rodada(esperar=0.0) as vez:
            self.assertTrue(vez["minha"])
            self.assertIn(A, self._no_disco("builds", "youtube"),
                          "a marca e gravada ANTES de qualquer escolha")
            self.assertEqual(B, self.m.proximo_build().id)

    def test_se_a_marca_nao_grava_de_novo_a_rodada_seguinte_nao_publica(self):
        self._marca_falha()
        self.m._gravar_dona("rodada")
        self.m.postar_build()
        self.desfecho._SEM_MARCA.clear()
        self.m._DONA.clear()
        with self.m._trava_da_rodada(esperar=0.0) as vez:
            self.assertFalse(vez["minha"], "repetir e pior que nao postar")
            self.assertTrue(vez.get("voo_preso"))
        ficha = json.loads(self.m._arquivo_da_dona().read_text("utf-8"))
        self.assertEqual([A], [i["alvo"] for i in ficha["sem_marca"]],
                         "a ficha velha fica para a proxima tentar")

    def test_caso_zero_marca_que_grava_nao_suja_a_ficha(self):
        """A marca grava (o caso comum): nada na ficha, nada a pousar."""
        self.m._gravar_dona("rodada")
        self.m.postar_build()
        self.assertIn(A, self._no_disco("builds", "youtube"))
        ficha = json.loads(self.m._arquivo_da_dona().read_text("utf-8"))
        self.assertFalse(ficha.get("sem_marca"))
        self.assertEqual([], self.telegram)


class HistoriasTests(_Base):
    """(b) da auditoria, pelo catalogo DE VERDADE: o publicador do YouTube
    escreve `clicou` no laudo e levanta "timed out"."""

    def setUp(self):
        super().setUp()
        m = self.m
        from contos.publicar import catalogo, serie
        mp4 = self.pasta / "p02.mp4"
        mp4.write_bytes(b"x" * 1000)
        self.alvo = _Video(PARTE, fonte_id="historia_00090", parte=2,
                           partes=6, caminho=mp4)
        m._divida_do_youtube = lambda: (None, "", [])
        m.proxima_historia = lambda **k: (self.alvo, [])
        m._valvula_da_parte = lambda ficha, alvo: ""
        m._visibilidade_das_historias = lambda: "public"
        m._tiktok_das_historias = lambda alvo, falha=None: "publicado no TikTok"
        from builds.publicar import tiktok
        _trocar(self, tiktok, "confirmado",
                lambda e: str(e).startswith("publicado no TikTok"))
        _trocar(self, serie, "registrar", lambda *a, **k: None)
        _trocar(self, catalogo, "barrar_pausa", lambda: None)
        _trocar(self, catalogo, "barrar_recusa", lambda v: None)
        _trocar(self, catalogo, "carregar_config", lambda: {})
        _trocar(self, catalogo._rb_publicar_cortes, "preparar",
                lambda v, limite=0, log=print: [v])
        self.envios = []

        def clica_e_cai(pedaco, **kw):
            self.envios.append(pedaco.id)
            kw["prova"]["clicou"] = True
            raise TimeoutError("timed out")
        _trocar(self, catalogo._rb_publicar_youtube,
                "publicar_como_configurado", clica_e_cai)

    def test_clique_dado_nao_e_reposto_como_rede(self):
        ficha = self.m.postar_historia()
        self.assertEqual([PARTE], self.envios)
        self.assertTrue(ficha["youtube_falhou"])
        self.assertIn("timed out", ficha["motivo"], "a frase tem cara de rede")
        self.assertTrue(ficha["youtube_clicou"])
        self.assertEqual([], self.m._derrubados_pela_rede(ficha))
        self.assertIn(PARTE, self._no_disco("historias", "youtube"))

    def test_com_a_marca_falhando_a_execucao_nao_escolhe_de_novo(self):
        self._marca_falha()
        ficha = self.m.postar_historia()
        self.assertEqual([], self.m._derrubados_pela_rede(ficha))
        self.assertEqual([], self.m._sem_a_conferir([self.alvo], "historias"))

    def test_caso_zero_falha_sem_clique_continua_sendo_rede(self):
        """Sem clique (a pagina nem abriu), repor no horario segue valendo."""
        from contos.publicar import catalogo

        def nem_abriu(pedaco, **kw):
            raise TimeoutError("timed out")
        _trocar(self, catalogo._rb_publicar_youtube,
                "publicar_como_configurado", nem_abriu)
        ficha = self.m.postar_historia()
        self.assertFalse(ficha.get("youtube_clicou"))
        self.assertEqual(["youtube"], self.m._derrubados_pela_rede(ficha))
        self.assertEqual(set(), self._no_disco("historias", "youtube"))


if __name__ == "__main__":
    unittest.main()
