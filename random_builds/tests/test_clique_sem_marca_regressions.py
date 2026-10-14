# -*- coding: utf-8 -*-
"""PUB-1: o clique saiu, algo falhou depois, e a marca "a conferir" tambem.

Auditoria de 11/10/2026, verificada em 14/10: o `a34b355` grava
`laudo["clicou"]` e marca "a conferir" quando algo levanta depois do clique,
mas se a propria marca falha (`NaoConsegviMarcar`: trava `<destino>_a_conferir`
ocupada por 20 s, disco) a falha era engolida e NADA duravel guardava o
clique — o video voltava a fila no horario seguinte e subia de novo.

Medido no codigo de antes (estes testes contra o HEAD d6aedb45):
  - `marcar_para_conferir` com a trava ocupada: 1 tentativa, levanta, e
    `a_conferir` devolve `set()` logo depois — o video estava livre;
  - `tiktok.publicar` com excecao DEPOIS do clique: `desfecho.resolver` nao
    era chamado (0 marcas), so a ficha da rodada sabia do clique.

Agora: 2 tentativas; a que nao grava fica na memoria desta execucao, que
`marcas`/`a_conferir` somam (o funil de toda escolha); e o publicador do
TikTok marca na excecao depois do clique, como o do YouTube.
"""
from __future__ import annotations

import contextlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from builds.publicar import desfecho

VIDEO = "generation_00101:duelo:celular"


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)
        _trocar(self, desfecho, "arquivo_a_conferir",
                lambda _c, p="tiktok": self.pasta / f"_{p}_a_conferir.json")
        from builds import atividade
        self.diario = []
        _trocar(self, atividade, "registrar",
                lambda *a, **k: self.diario.append(a))
        _trocar(self, desfecho, "PAUSA_ENTRE_TENTATIVAS_S", 0.0)
        self.addCleanup(desfecho._SEM_MARCA.clear)
        desfecho._SEM_MARCA.clear()


class MarcaComNovaTentativaTests(_Base):
    def test_trava_ocupada_tenta_de_novo_e_grava(self):
        """1a tentativa: trava ocupada; 2a: grava. Nada fica na memoria."""
        real = desfecho._gravar_marca
        chamadas = []

        def uma_falha(*a, **k):
            chamadas.append(1)
            if len(chamadas) == 1:
                raise desfecho._MarcaNaoGravou("a trava esta ocupada")
            return real(*a, **k)
        _trocar(self, desfecho, "_gravar_marca", uma_falha)
        self.assertTrue(desfecho.marcar_para_conferir(
            "builds", VIDEO, "cliquei em publicar", "youtube"))
        self.assertEqual(2, len(chamadas))
        self.assertIn(VIDEO, desfecho._ler(
            self.pasta / "_youtube_a_conferir.json"))
        self.assertEqual([], desfecho.sem_marca_no_disco())

    def test_nada_grava_LEVANTA_e_a_execucao_nao_esquece(self):
        """O caso da auditoria: as duas tentativas falham. Levanta como antes
        (quem chama sabe que o disco nao tem a marca), mas `a_conferir` — o
        funil de toda escolha — passa a ter o video. No HEAD: `set()`."""
        chamadas = []

        def sempre_ocupada(*a, **k):
            chamadas.append(1)
            raise desfecho._MarcaNaoGravou("a trava esta ocupada")
        _trocar(self, desfecho, "_gravar_marca", sempre_ocupada)
        with self.assertRaises(desfecho.NaoConsegviMarcar):
            desfecho.marcar_para_conferir("builds", VIDEO,
                                          "cliquei em publicar", "youtube")
        self.assertEqual(desfecho.TENTATIVAS_DA_MARCA, len(chamadas))
        self.assertEqual(2, desfecho.TENTATIVAS_DA_MARCA)
        self.assertEqual({VIDEO}, desfecho.a_conferir("builds", "youtube"))
        self.assertEqual(set(), desfecho.a_conferir("builds", "tiktok"),
                         "a memoria e por destino, como a lista")
        self.assertEqual([{"canal": "builds", "alvo": VIDEO,
                           "destino": "youtube",
                           "estado": "cliquei em publicar"}],
                         desfecho.sem_marca_no_disco())
        texto = " ".join(str(a) for a in self.diario)
        self.assertIn("NAO esta bloqueado no disco", texto)

    def test_oserror_da_propria_trava_tambem_vira_NaoConsegviMarcar(self):
        """Pasta das travas inacessivel: antes subia um OSError cru."""
        from builds import travas

        @contextlib.contextmanager
        def quebrada(nome, esperar=0.0):
            raise PermissionError("pasta de travas inacessivel")
            yield  # pragma: no cover
        _trocar(self, travas, "trava", quebrada)
        with self.assertRaises(desfecho.NaoConsegviMarcar):
            desfecho.marcar_para_conferir("builds", VIDEO, "x", "youtube")

    def test_a_marca_que_grava_depois_sai_da_memoria(self):
        real = desfecho._gravar_marca
        _trocar(self, desfecho, "_gravar_marca",
                lambda *a, **k: (_ for _ in ()).throw(
                    desfecho._MarcaNaoGravou("ocupada")))
        with self.assertRaises(desfecho.NaoConsegviMarcar):
            desfecho.marcar_para_conferir("builds", VIDEO, "x", "youtube")
        self.assertEqual(1, len(desfecho.sem_marca_no_disco()))
        desfecho._gravar_marca = real
        self.assertTrue(desfecho.marcar_para_conferir("builds", VIDEO, "x",
                                                      "youtube"))
        self.assertEqual([], desfecho.sem_marca_no_disco())

    def test_caso_zero_sem_marca_nenhuma(self):
        """ZERO eventos: lista ausente e memoria vazia = ninguem bloqueado."""
        self.assertEqual(set(), desfecho.a_conferir("builds", "youtube"))
        self.assertEqual([], desfecho.sem_marca_no_disco())

    def test_marca_de_audio_na_memoria_tambem_sai_sozinha(self):
        desfecho.lembrar_sem_marca("builds", VIDEO, "[audio] luta muda",
                                   "youtube")
        self.assertEqual({VIDEO}, desfecho.a_conferir("builds", "youtube"))
        desfecho.soltar_marca("builds", VIDEO, "youtube", prefixo="[audio] ")
        self.assertEqual(set(), desfecho.a_conferir("builds", "youtube"))

    def test_a_de_clique_na_memoria_NAO_sai_pelo_prefixo_de_audio(self):
        desfecho.lembrar_sem_marca("builds", VIDEO, "cliquei", "youtube")
        desfecho.soltar_marca("builds", VIDEO, "youtube", prefixo="[audio] ")
        self.assertEqual({VIDEO}, desfecho.a_conferir("builds", "youtube"))


class _Pagina:
    url = "https://www.tiktok.com/tiktokstudio/upload"

    class _Loc:
        first = None

        def count(self):
            return 1

        def set_input_files(self, _caminho):
            pass

    def locator(self, _sel):
        loc = self._Loc()
        loc.first = loc
        return loc


class _Botao:
    def click(self, timeout=None):
        pass


class TikTokExcecaoDepoisDoCliqueTests(_Base):
    """`tiktok.publicar` com o navegador de mentira: o clique sai e a
    confirmacao levanta (Chrome fechando). No HEAD nenhuma marca era gravada."""

    def setUp(self):
        super().setUp()
        from builds.publicar import audio, tiktok
        self.tiktok = tiktok
        mp4 = self.pasta / "v.mp4"
        mp4.write_bytes(b"x" * 1000)
        self.video = type("V", (), {"id": VIDEO, "caminho": mp4,
                                    "vertical": True,
                                    "descricao_completa": "legenda #tag"})()

        @contextlib.contextmanager
        def nada(*a, **k):
            yield object()
        _trocar(self, tiktok.atividade, "fabrica", nada)
        _trocar(self, tiktok, "contexto_persistente", nada)
        _trocar(self, tiktok, "perfil_da_conta", lambda canal="builds": "p")
        _trocar(self, tiktok, "_conta_ativa", lambda canal: "c")
        _trocar(self, tiktok, "_abrir", lambda ctx, url: _Pagina())
        _trocar(self, tiktok, "_primeiro",
                lambda page, sel, timeout=0: _Botao())
        _trocar(self, tiktok, "_esperar_envio", lambda page, passo: True)
        _trocar(self, tiktok, "_escrever_legenda",
                lambda page, texto, passo, laudo: None)
        _trocar(self, tiktok, "_deve_barrar", lambda postar, texto, laudo: False)
        _trocar(self, audio, "barrar_luta_muda", lambda *a, **k: None)
        _trocar(self, tiktok.time, "sleep", lambda s: None)

        def chrome_fechou(page, passo):
            raise RuntimeError("Target page, context or browser has been closed")
        _trocar(self, tiktok, "_confirmar_publicacao", chrome_fechou)

    def test_excecao_depois_do_clique_vai_para_a_lista(self):
        laudo = {}
        with self.assertRaises(RuntimeError):
            self.tiktok.publicar(self.video, postar=True, canal="builds",
                                 config={}, prova=laudo)
        self.assertTrue(laudo["clicou"])
        self.assertEqual("sem_confirmacao", laudo["estado"])
        self.assertEqual({VIDEO}, desfecho.a_conferir("builds", "tiktok"))
        self.assertEqual(set(), desfecho.a_conferir("builds", "youtube"))

    def test_e_se_a_marca_tambem_falha_a_execucao_lembra(self):
        _trocar(self, desfecho, "_gravar_marca",
                lambda *a, **k: (_ for _ in ()).throw(
                    desfecho._MarcaNaoGravou("ocupada")))
        with self.assertRaises(RuntimeError) as caso:
            self.tiktok.publicar(self.video, postar=True, canal="builds",
                                 config={}, prova={})
        self.assertIn("browser has been closed", str(caso.exception),
                      "sobe a excecao ORIGINAL, que diz o que quebrou")
        self.assertEqual({VIDEO}, desfecho.a_conferir("builds", "tiktok"))

    def test_caso_zero_clique_confirmado_nao_marca(self):
        _trocar(self, self.tiktok, "_confirmar_publicacao",
                lambda page, passo: self.tiktok.SUCESSO + " (teste)")
        from builds.publicar import metricas
        _trocar(self, metricas, "registrar_publicado", lambda *a, **k: None)
        self.tiktok.publicar(self.video, postar=True, canal="builds",
                             config={}, prova={})
        self.assertEqual(set(), desfecho.a_conferir("builds", "tiktok"))


if __name__ == "__main__":
    unittest.main()
