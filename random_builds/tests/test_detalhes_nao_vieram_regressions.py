# -*- coding: utf-8 -*-
"""A tela de detalhes que nao veio depois do arquivo entregue (21/10/2026).

O caso medido: na rodada das 09:37 de 21/10 o YouTube dos builds
(duelo_00132, "Throwing Axes VS Tactical Knives — who wins?") fez

    09:41:01  inicio (atividade.jsonl, 12:41:01Z)
    09:41:17  arquivo entregue (final_celular.mp4)
    09:45:19  YouTubeWebFalhou: a tela de detalhes nao apareceu   (dur_s 257,5)

240 s calados entre o arquivo e a falha: `_primeiro(page, CAMPO_TITULO,
timeout=60)` espera 60 s POR SELETOR, e os 4 estavam ausentes. Nenhuma foto,
nenhum texto do dialogo, e a cota so era perguntada no instante do envio.
Nos 20 envios de 19 a 21/10 o titulo apareceu de 3 a 17 s depois do arquivo.
A Data API (playlist de envios e search forMine dos dois canais, 21/10
~10:45) nao tinha video nenhum depois de 21:44 de 20/10: o upload nao
comecou do lado do YouTube.

Agora: um prazo so (`ESPERA_DETALHES_S` = 90 s) para os 4 seletores, a cota
perguntada de novo, e a falha sai com a foto e o texto do dialogo.

Rode de dentro de random_builds/:
    python -m unittest tests.test_detalhes_nao_vieram_regressions -v
"""
from __future__ import annotations

import contextlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

from builds.publicar import youtube_web

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


class Relogio:
    """`time` do youtube_web: dormir faz o relogio andar."""

    def __init__(self):
        self.agora = 1000.0

    def monotonic(self):
        return self.agora

    def time(self):
        return self.agora

    def sleep(self, s):
        self.agora += s


class Alvo:
    def __init__(self, pagina, seletor):
        self.pagina, self.seletor = pagina, seletor

    @property
    def first(self):
        return self

    def nth(self, _i):
        return self

    def _existe(self):
        return self.pagina.existe(self.seletor)

    def count(self):
        return 1 if self._existe() else 0

    def is_visible(self):
        return self._existe()

    def inner_text(self, timeout=None):
        return self.pagina.texto(self.seletor)

    def set_input_files(self, _caminho):
        self.pagina.entregue_em = self.pagina.relogio.agora


class Pagina:
    """O Studio depois do arquivo entregue.

    `titulo_em`: segundos depois do envio em que o campo aparece (None =
    nunca). `cota_em`: idem para o aviso de limite diario.
    """
    url = "https://studio.youtube.com/channel/UCteste/videos/upload?d=ud"

    def __init__(self, relogio, *, titulo_em=None, cota_em=None):
        self.relogio = relogio
        self.titulo_em, self.cota_em = titulo_em, cota_em
        self.entregue_em = None

    def _passou(self, segundos):
        return (segundos is not None and self.entregue_em is not None
                and self.relogio.agora - self.entregue_em >= segundos)

    def existe(self, seletor):
        if seletor == youtube_web.ENTRADA_ARQUIVO:
            return True
        if seletor in youtube_web.CAMPO_TITULO:
            return self._passou(self.titulo_em)
        if "error-short" in seletor:
            return self._passou(self.cota_em)
        if seletor == youtube_web.DIALOGO_DE_ENVIO:
            return True
        return False

    def texto(self, seletor):
        if "error-short" in seletor:
            return "Daily upload limit reached"
        if seletor == youtube_web.DIALOGO_DE_ENVIO:
            return "Enviar videos\n  Arraste e solte os arquivos"
        return ""

    def locator(self, seletor):
        return Alvo(self, seletor)


class Passou(Exception):
    """O titulo foi achado: o fluxo seguiu para a escrita."""


class PublicarDetalhesTests(unittest.TestCase):
    """`publicar()` de verdade, com o navegador de mentira."""

    def setUp(self):
        from builds import contas
        self.relogio = Relogio()
        _trocar(self, youtube_web, "time", self.relogio)
        _trocar(self, youtube_web.atividade, "fabrica",
                lambda *a, **k: contextlib.nullcontext())
        _trocar(self, youtube_web, "contexto_persistente",
                lambda **k: contextlib.nullcontext(object()))
        _trocar(self, youtube_web, "perfil_da_conta", lambda canal: "perfil")
        _trocar(self, youtube_web, "_conta_ativa", lambda canal: "builds")
        _trocar(self, youtube_web, "url_de_upload", lambda canal: Pagina.url)
        self.fotos = []

        def fotografar(_p, rotulo, **_k):
            self.fotos.append(rotulo)
            return f"telas/{rotulo}.png"
        _trocar(self, youtube_web.escrita, "fotografar", fotografar)
        _trocar(self, contas, "ativa", lambda *a, **k: "builds")
        _trocar(self, contas, "identidade", lambda *a, **k: {})
        self.pagina = None

        def abrir(_ctx, _url):
            self.relogio.agora += 12.0      # 21/10: 16 s ate o arquivo
            return self.pagina
        _trocar(self, youtube_web, "_abrir", abrir)
        _trocar(self, youtube_web, "_esperar_montar", lambda *a, **k: True)
        _trocar(self, youtube_web, "_abrir_dialogo_de_upload",
                lambda *a, **k: True)

        def escrever(*_a, **_k):
            raise Passou()
        _trocar(self, youtube_web, "_escrever", escrever)
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        arquivo = Path(pasta.name) / "final_celular.mp4"
        arquivo.write_bytes(b"x")
        self.video = type("V", (), {
            "id": "duelo_00132:duelo:celular", "caminho": str(arquivo),
            "titulo": "Throwing Axes VS Tactical Knives — who wins?",
            "descricao_completa": "d"})()

    def _publicar(self, **pagina):
        self.pagina = Pagina(self.relogio, **pagina)
        laudo = {}
        youtube_web.publicar(self.video, config={}, canal="builds",
                             postar=True, progresso=lambda _t: None,
                             prova=laudo)
        return laudo

    def test_caso_de_21_10_espera_90_s_e_nao_240_e_sai_com_a_foto(self):
        laudo = {}
        self.pagina = Pagina(self.relogio)
        with self.assertRaises(youtube_web.YouTubeWebFalhou) as caso:
            youtube_web.publicar(self.video, config={}, canal="builds",
                                 postar=True, progresso=lambda _t: None,
                                 prova=laudo)
        frase = str(caso.exception)
        self.assertNotIsInstance(caso.exception,
                                 youtube_web.LimiteDiarioDoYouTube)
        self.assertTrue(frase.startswith(
            "a tela de detalhes nao apareceu em 90 s"), frase)
        self.assertFalse(frase.startswith("infraestrutura"), frase)
        self.assertIn("Tela: telas/youtube_sem_detalhes.png", frase)
        self.assertIn("Arraste e solte", frase)
        detalhes = laudo["detalhes_nao_vieram"]
        self.assertEqual(90.0, detalhes["espera_s"])
        self.assertEqual("telas/youtube_sem_detalhes.png", detalhes["tela"])
        self.assertEqual(["youtube_sem_detalhes"], self.fotos)

    def test_cota_que_aparece_depois_do_envio_e_limite_diario(self):
        """A pergunta logo apos o envio nao ve o aviso que chega 5 s depois."""
        with self.assertRaises(youtube_web.LimiteDiarioDoYouTube):
            self._publicar(cota_em=5.0)

    def test_titulo_aos_17_s_segue_para_a_escrita(self):
        """O mais lento medido (00:37 de 21/10): 17 s. Nao pode falhar."""
        def marcar(*_a, **_k):
            raise Passou(self.relogio.agora - self.pagina.entregue_em)
        _trocar(self, youtube_web, "_escrever", marcar)
        with self.assertRaises(Passou) as caso:
            self._publicar(titulo_em=17.0)
        self.assertLessEqual(17.0, caso.exception.args[0])
        self.assertLess(caso.exception.args[0], 19.0)
        self.assertEqual([], self.fotos)

    def test_titulo_na_hora_nao_dorme(self):
        with self.assertRaises(Passou):
            self._publicar(titulo_em=0.0)


class EsperaTests(unittest.TestCase):
    def test_prazo_e_um_so_para_os_quatro_seletores(self):
        relogio = Relogio()
        _trocar(self, youtube_web, "time", relogio)
        pagina = Pagina(relogio)
        pagina.entregue_em = relogio.agora
        self.assertIsNone(youtube_web._esperar_detalhes(pagina))
        self.assertEqual(4, len(youtube_web.CAMPO_TITULO))
        self.assertEqual(youtube_web.ESPERA_DETALHES_S, relogio.agora - 1000.0)

    def test_relogio_parado_nao_prende_para_sempre(self):
        """Se o relogio nao andar, o teto de voltas encerra a espera."""
        class Parado(Relogio):
            def sleep(self, _s):
                pass
        relogio = Parado()
        _trocar(self, youtube_web, "time", relogio)
        pagina = Pagina(relogio)
        self.assertIsNone(youtube_web._esperar_detalhes(pagina, prazo_s=5))


class FraseCortadaTests(unittest.TestCase):
    """O postar.txt, o Telegram e o diario cortam o erro em 200 caracteres.

    Medido na 1a versao deste conserto (21/10): "YouTubeWebFalhou: " + a
    frase com "O dialogo dizia: <200>" e o caminho absoluto da foto NO FIM
    (`E:\\projetos\\random_builds\\outputs\\_publicar\\telas\\2026..png`, ~95
    caracteres) dava ~410; no corte de 200 a foto sumia inteira — e a foto e
    o motivo do conserto.
    """

    TELA = ("E:\\projetos\\random_builds\\outputs\\_publicar\\telas\\"
            "20261021_094519_youtube_sem_detalhes.png")

    def test_a_foto_sobrevive_ao_corte_de_200(self):
        frase = youtube_web.falha_dos_detalhes(90.0, "x" * 300, self.TELA)
        cortada = f"YouTubeWebFalhou: {frase}"[:200]
        self.assertIn("Tela: telas/20261021_094519_youtube_sem_detalhes.png",
                      cortada)
        self.assertTrue(cortada.startswith(
            "YouTubeWebFalhou: a tela de detalhes nao apareceu em 90 s"))

    def test_sem_foto_nem_texto(self):
        """Caso zero: a camera falhou e o dialogo nao existe."""
        self.assertEqual(
            "a tela de detalhes nao apareceu em 90 s (o upload nao comecou?).",
            youtube_web.falha_dos_detalhes(90.0))


class RodadaNaoRepoeTests(unittest.TestCase):
    """Como antes de 21/10: sem medida de rede, a rodada NAO repoe o horario
    (repor e decisao de quem publica, e sem a foto nao ha causa)."""

    def test_frase_nova_nao_conta_como_rede(self):
        spec = importlib.util.spec_from_file_location("postar_detalhes",
                                                      POSTAR)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        frase = youtube_web.falha_dos_detalhes(
            90.0, "Enviar videos", "telas/youtube_sem_detalhes.png")
        falha_yt = f"YouTubeWebFalhou: {frase}"[:200]
        ficha = {"canal": "builds", "feito": False, "youtube_falhou": True,
                 "motivo": f"YouTube falhou: {falha_yt}"[:200],
                 "tiktok": "fora da grade do TikTok neste horario"}
        self.assertEqual([], m._derrubados_pela_rede(ficha))


if __name__ == "__main__":
    unittest.main()
