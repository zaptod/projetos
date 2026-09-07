# -*- coding: utf-8 -*-
"""Contratos do `espelho` — o que ja quebrou, ou o que quebraria caro.

Nenhum teste aqui encosta na rede, no YouTube ou num navegador. O que se
testa e a fronteira: o que fazemos com a resposta do yt-dlp, nao o yt-dlp.
As respostas cruas ficam literais no topo, como em
`historias/tests/test_serie_regressions.py` — quando o YouTube mudar o
formato, a diferenca aparece aqui em vez de aparecer no meio de uma coleta.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from espelho import (absorver, analise, baixar, biblia, canal, config, dossie,
                     estado, ffmpeg, ficha, medidas, preset, status,
                     transcrever, ytdlp)

# Uma resposta de `yt-dlp -J --flat-playlist` de uma aba de canal, reduzida
# ao que o codigo le. Os campos ausentes sao ausentes de proposito: no modo
# achatado, `description` e `upload_date` REALMENTE nao vem.
ABA_CRUA = {
    "id": "UCexemplo",
    "channel": "Canal de Teste",
    "channel_id": "UCexemplo",
    "channel_follower_count": 12345,
    "description": "um canal qualquer",
    "entries": [
        {"id": "aaa11111111", "title": "Como eu perdi tudo em 3 dias",
         "duration": 612.0, "view_count": 90000, "timestamp": 1756684800},
        {"id": "bbb22222222", "title": "A parte que ninguem conta",
         "duration": 480.5, "view_count": 12000, "upload_date": "20260815"},
        {"id": "ccc33333333", "title": "Sem duracao nem views"},
    ],
}


class _PastaTemporaria(unittest.TestCase):
    """Aponta o `outputs/` do pacote para uma pasta descartavel.

    Sem isto os testes escreveriam em `mimetizar/outputs/` — a pasta com as
    coletas de verdade — e `proximo_id()` passaria a contar as do usuario.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._antes = config.OUTPUTS
        config.OUTPUTS = Path(self._tmp.name) / "outputs"
        config.OUTPUTS.mkdir(parents=True)
        self.addCleanup(self._restaurar)

    def _restaurar(self) -> None:
        config.OUTPUTS = self._antes
        self._tmp.cleanup()


class UrlTests(unittest.TestCase):
    """A URL que a pessoa cola tem seis formatos, e cinco precisam de conserto."""

    def test_canal_pelado_ganha_a_aba_de_videos(self):
        # Sem isto o catalogo sai com quatro linhas ("Videos", "Shorts",
        # "Playlists"...) em vez dos videos: a URL pelada lista as ABAS.
        self.assertEqual(canal.normalizar_url("https://www.youtube.com/@nome"),
                         "https://www.youtube.com/@nome/videos")

    def test_arroba_cru_vira_url(self):
        self.assertEqual(canal.normalizar_url("@nome"),
                         "https://www.youtube.com/@nome/videos")
        self.assertEqual(canal.normalizar_url("nome"),
                         "https://www.youtube.com/@nome/videos")

    def test_barra_no_fim_nao_duplica(self):
        self.assertEqual(canal.normalizar_url("https://www.youtube.com/@nome/"),
                         "https://www.youtube.com/@nome/videos")

    def test_troca_a_aba_pedida(self):
        self.assertEqual(
            canal.normalizar_url("https://www.youtube.com/@nome", "shorts"),
            "https://www.youtube.com/@nome/shorts")
        # Ja veio com /videos, mas quero /shorts: troca, nao empilha.
        self.assertEqual(
            canal.normalizar_url("https://www.youtube.com/@nome/videos", "shorts"),
            "https://www.youtube.com/@nome/shorts")

    def test_channel_id_funciona(self):
        self.assertEqual(
            canal.normalizar_url("https://www.youtube.com/channel/UCabc"),
            "https://www.youtube.com/channel/UCabc/videos")

    def test_playlist_e_respeitada(self):
        url = "https://www.youtube.com/playlist?list=PLabc"
        self.assertEqual(canal.normalizar_url(url), url)

    def test_url_de_video_e_recusada_com_instrucao(self):
        # Colar a URL do video em vez da do canal e o erro mais provavel de
        # todos. A mensagem tem que dizer o que fazer, nao so "invalido".
        with self.assertRaises(canal.NaoColetou) as caso:
            canal.normalizar_url("https://www.youtube.com/watch?v=abc")
        self.assertIn("canal", str(caso.exception).lower())

    def test_url_vazia_e_recusada(self):
        with self.assertRaises(canal.NaoColetou):
            canal.normalizar_url("   ")


class EntradasTests(unittest.TestCase):
    """O que fazemos com a resposta achatada do yt-dlp."""

    def test_le_as_tres_entradas(self):
        entradas = canal._entradas(ABA_CRUA)
        self.assertEqual([e["id"] for e in entradas],
                         ["aaa11111111", "bbb22222222", "ccc33333333"])

    def test_entrada_sem_id_e_descartada(self):
        sujo = {"entries": [{"title": "fantasma"}, {"id": "ok1"}, None, "lixo"]}
        self.assertEqual([e["id"] for e in canal._entradas(sujo)], ["ok1"])

    def test_aba_aninhada_e_achatada(self):
        # Uma URL de canal pelada devolve UMA entrada cujas entries sao os
        # videos. Sem achatar, o catalogo teria um item chamado "Videos".
        aninhado = {"entries": [{"id": "tab", "entries": ABA_CRUA["entries"]}]}
        self.assertEqual(len(canal._entradas(aninhado)), 3)

    def test_upload_date_vence_o_timestamp(self):
        data, aproximada = canal._data({"upload_date": "20260815",
                                        "timestamp": 1700000000})
        self.assertEqual(data, "2026-08-15")
        self.assertFalse(aproximada, "upload_date e exata, nao aproximada")

    def test_timestamp_vira_data_aproximada(self):
        data, aproximada = canal._data({"timestamp": 1756684800})
        self.assertTrue(data)
        self.assertTrue(aproximada)

    def test_sem_data_nao_inventa(self):
        self.assertEqual(canal._data({}), ("", True))

    def test_campos_faltando_viram_zero_e_nao_None(self):
        # `duration: None` chega de verdade em video ao vivo agendado. Somar
        # None estoura a estimativa de espaco inteira.
        video = canal._video({"id": "x", "duration": None, "view_count": None},
                             "videos")
        self.assertEqual(video["duracao_s"], 0.0)
        self.assertEqual(video["views"], 0)
        self.assertEqual(video["url"], "https://www.youtube.com/watch?v=x")


class VideosJsonlTests(_PastaTemporaria):
    def test_grava_e_le_de_volta(self):
        pasta = config.OUTPUTS / "canal_00001"
        pasta.mkdir()
        originais = [canal._video(e, "videos") for e in ABA_CRUA["entries"]]
        canal.gravar_videos(pasta, originais)
        self.assertEqual(canal.videos(pasta), originais)

    def test_linha_corrompida_e_pulada_sem_derrubar(self):
        # Um Ctrl+C na hora da escrita deixa meia linha. Perder um video e
        # aceitavel; perder o catalogo inteiro nao e.
        pasta = config.OUTPUTS / "canal_00001"
        pasta.mkdir()
        (pasta / "videos.jsonl").write_text(
            '{"id": "bom1", "titulo": "ok"}\n'
            '{"id": "quebr\n'
            "\n"
            '{"id": "bom2", "titulo": "ok"}\n', encoding="utf-8")
        self.assertEqual([v["id"] for v in canal.videos(pasta)],
                         ["bom1", "bom2"])

    def test_sem_arquivo_devolve_lista_vazia(self):
        pasta = config.OUTPUTS / "canal_00001"
        pasta.mkdir()
        self.assertEqual(canal.videos(pasta), [])


class SelecionarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lista = [canal._video(e, "videos") for e in ABA_CRUA["entries"]]

    def test_sem_limite_devolve_tudo_na_ordem_do_canal(self):
        self.assertEqual(len(canal.selecionar(self.lista)), 3)
        self.assertEqual(canal.selecionar(self.lista)[0]["id"], "aaa11111111")

    def test_limite_corta(self):
        self.assertEqual(len(canal.selecionar(self.lista, limite=2)), 2)

    def test_criterio_views_pega_os_campeoes(self):
        # Com limite pequeno, o que interessa e o formato que FUNCIONOU, nao
        # o que foi publicado ontem.
        escolhidos = canal.selecionar(self.lista, limite=2, criterio="views")
        self.assertEqual([v["id"] for v in escolhidos],
                         ["aaa11111111", "bbb22222222"])

    def test_nao_mexe_na_lista_recebida(self):
        canal.selecionar(self.lista, criterio="views")
        self.assertEqual(self.lista[0]["id"], "aaa11111111")


class ConfigTests(_PastaTemporaria):
    def test_proximo_id_conta_o_disco(self):
        self.assertEqual(config.proximo_id(), "canal_00001")
        (config.OUTPUTS / "canal_00001").mkdir()
        (config.OUTPUTS / "canal_00007").mkdir()
        # Conta o MAIOR, nao a quantidade: apagar uma pasta na mao nao pode
        # fazer a proxima coleta gravar por cima de uma que existe.
        self.assertEqual(config.proximo_id(), "canal_00008")

    def test_pasta_estranha_e_ignorada(self):
        (config.OUTPUTS / "_rascunho").mkdir()
        (config.OUTPUTS / "canal_1").mkdir()
        self.assertEqual(config.canais(), [])

    def test_id_invalido_explica_o_formato(self):
        with self.assertRaises(config.NaoAchou) as caso:
            config.pasta_do_canal("canal_1")
        self.assertIn("canal_00001", str(caso.exception))

    def test_canal_inexistente_diz_como_comecar(self):
        with self.assertRaises(config.NaoAchou) as caso:
            config.pasta_do_canal("canal_00042")
        self.assertIn("main.py canal", str(caso.exception))

    def test_criar_canal_reserva_a_pasta(self):
        canal_id, pasta = config.criar_canal()
        self.assertEqual(canal_id, "canal_00001")
        self.assertTrue(pasta.is_dir())
        segundo, _ = config.criar_canal()
        self.assertEqual(segundo, "canal_00002")

    def test_config_de_coleta_carrega(self):
        coleta = config.carregar("coleta")
        self.assertIn("formato", coleta)
        self.assertGreater(coleta["teto_gb"], 0)

    def test_config_ausente_diz_o_caminho(self):
        with self.assertRaises(config.NaoAchou) as caso:
            config.carregar("nao_existe")
        self.assertIn("nao_existe.json", str(caso.exception))


class EstadoTests(_PastaTemporaria):
    def setUp(self) -> None:
        super().setUp()
        self.pasta = config.OUTPUTS / "canal_00001"
        self.pasta.mkdir()

    def test_estado_ausente_nao_levanta(self):
        self.assertEqual(estado.ler(self.pasta), {"etapas": {}})

    def test_estado_corrompido_nao_levanta(self):
        # Processo morto no meio da escrita. Recomecar a contagem e barato;
        # a ferramenta se recusar a abrir nao e.
        estado.caminho(self.pasta).write_text('{"etapas": {"can',
                                              encoding="utf-8")
        self.assertEqual(estado.ler(self.pasta), {"etapas": {}})

    def test_marcar_acumula_sem_apagar_o_que_havia(self):
        estado.marcar(self.pasta, "canal", n_videos=10)
        estado.marcar(self.pasta, "baixar", baixados=3)
        estado.marcar(self.pasta, "baixar", baixados=7)
        etapas = estado.ler(self.pasta)["etapas"]
        self.assertEqual(etapas["canal"]["n_videos"], 10)
        self.assertEqual(etapas["baixar"]["baixados"], 7)
        self.assertIn("em", etapas["baixar"])

    def test_nao_deixa_temporario_para_tras(self):
        estado.marcar(self.pasta, "canal", n_videos=1)
        sobras = list(self.pasta.glob("*.tmp"))
        self.assertEqual(sobras, [], "a troca atomica deixou lixo")

    def test_etapa_desconhecida_devolve_vazio(self):
        self.assertEqual(estado.etapa(self.pasta, "biblia"), {})


class ProximoPassoTests(unittest.TestCase):
    """A unica pergunta que importa ao voltar no dia seguinte: e agora, o que?"""

    BASE = {"canal_id": "canal_00001", "n_videos": 10, "completos": 0,
            "biblia": False, "preset": False}

    def _passo(self, **mudancas) -> str:
        return status.proximo_passo({**self.BASE, **mudancas})

    def test_catalogo_vazio_pede_o_catalogo(self):
        self.assertIn("canal <url>", self._passo(n_videos=0))

    def test_ordem_completa_ate_o_fim(self):
        # O caminho normal e um comando so — `absorver` baixa, mede,
        # transcreve, poe os dois provedores para ler e apaga o video.
        self.assertIn("absorver", self._passo())
        self.assertIn("biblia", self._passo(completos=10))
        self.assertIn("preset", self._passo(completos=10, biblia=True))
        self.assertIn("pronto", self._passo(completos=10, biblia=True,
                                            preset=True))

    def test_parcial_continua_absorvendo_e_diz_quantos_faltam(self):
        # Retomada: 7 de 10 com as duas fichas nao pode pular para a biblia,
        # e o numero que falta e a informacao que importa.
        passo = self._passo(completos=7)
        self.assertIn("absorver", passo)
        self.assertIn("3", passo)


class YtdlpTests(unittest.TestCase):
    """As mensagens de erro. E o unico contato do usuario com o yt-dlp."""

    def test_url_invalida_sugere_os_formatos(self):
        texto = ytdlp._mensagem(1, "ERROR: 'xx' is not a valid URL")
        self.assertIn("youtube.com/@nome", texto)

    def test_pedido_de_sessao_manda_para_a_pagina_contas(self):
        texto = ytdlp._mensagem(1, "ERROR: Sign in to confirm your age")
        self.assertIn("Contas", texto)
        self.assertIn("youtube_web", texto)

    def test_estrangulamento_diz_para_retomar(self):
        texto = ytdlp._mensagem(1, "ERROR: HTTP Error 429: Too Many Requests")
        self.assertIn("retome", texto)

    def test_erro_desconhecido_mostra_o_original(self):
        texto = ytdlp._mensagem(2, "ERROR: alguma coisa nova e estranha")
        self.assertIn("alguma coisa nova e estranha", texto)

    def test_erro_mudo_ainda_diz_o_codigo(self):
        self.assertIn("77", ytdlp._mensagem(77, ""))

    def test_json_vazio_vira_Falhou_e_nao_JSONDecodeError(self):
        original = ytdlp.rodar
        ytdlp.rodar = lambda *a, **k: (1, "", "ERROR: HTTP Error 429")
        try:
            with self.assertRaises(ytdlp.Falhou) as caso:
                ytdlp.json_de(["-J", "x"])
        finally:
            ytdlp.rodar = original
        self.assertIn("retome", str(caso.exception))


class EstimativaTests(unittest.TestCase):
    """A conta que aparece ANTES de comprometer o disco e a madrugada."""

    def test_soma_as_duracoes(self):
        videos = [{"duracao_s": 3600.0}, {"duracao_s": 3600.0}]
        conta = baixar.estimativa(videos, {"bitrate_estimado_mbps": 2.5,
                                           "teto_gb": 50})
        self.assertEqual(conta["n_videos"], 2)
        self.assertAlmostEqual(conta["horas"], 2.0)
        # 2,5 Mbps por 2h: ~2,2 GB. A ordem de grandeza e o que importa.
        self.assertTrue(1.5 < conta["gb"] < 3.0, conta["gb"])

    def test_duracao_ausente_nao_estoura(self):
        # `duration: None` chega de verdade em live agendada. Somar None
        # derrubaria a estimativa inteira, que e justamente a protecao.
        conta = baixar.estimativa([{"duracao_s": None}, {}],
                                  {"bitrate_estimado_mbps": 2.5})
        self.assertEqual(conta["gb"], 0.0)


class BaixadosTests(_PastaTemporaria):
    """Quando um video conta como "esta em disco" — e quando NAO conta."""

    def setUp(self) -> None:
        super().setUp()
        self.pasta = config.OUTPUTS / "canal_00001"
        (self.pasta / "midia").mkdir(parents=True)

    def _criar(self, video_id: str, *arquivos) -> Path:
        alvo = self.pasta / "midia" / video_id
        alvo.mkdir(exist_ok=True)
        for nome in arquivos:
            (alvo / nome).write_bytes(b"conteudo")
        return alvo

    def test_video_inteiro_conta(self):
        self._criar("ok1", "video.mp4", "video.info.json", "video.webp")
        self.assertEqual(baixar.baixados(self.pasta), {"ok1"})

    def test_so_thumb_e_info_NAO_contam(self):
        # O defeito: a thumb e o info.json sao gravados ANTES do video e
        # casam com `video.*`. Contar isso como pronto e o jeito de nunca
        # mais baixar o video que faltou — e de "medir" reclamar depois.
        self._criar("meio", "video.info.json", "video.webp", "video.en.vtt")
        self.assertEqual(baixar.baixados(self.pasta), set())
        self.assertIsNone(baixar.video_de(self.pasta, "meio"))

    def test_arquivo_parcial_do_ytdlp_nao_conta(self):
        alvo = self._criar("parcial", "video.mp4")
        (alvo / "video.mp4.part").write_bytes(b"metade")
        self.assertEqual(baixar.baixados(self.pasta), set())

    def test_video_de_tamanho_zero_nao_conta(self):
        alvo = self.pasta / "midia" / "vazio"
        alvo.mkdir()
        (alvo / "video.mp4").write_bytes(b"")
        self.assertEqual(baixar.baixados(self.pasta), set())

    def test_legenda_respeita_a_ordem_dos_idiomas(self):
        self._criar("leg", "video.mp4", "video.en.vtt", "video.pt.vtt")
        achada = baixar.legenda_de(self.pasta, "leg", ["pt", "en"])
        self.assertIn(".pt.", achada.name)
        achada = baixar.legenda_de(self.pasta, "leg", ["en"])
        self.assertIn(".en.", achada.name)

    def test_sem_legenda_devolve_None(self):
        self._criar("nada", "video.mp4")
        self.assertIsNone(baixar.legenda_de(self.pasta, "nada", ["pt"]))


class DataExataTests(_PastaTemporaria):
    def test_info_json_corrige_a_data_aproximada(self):
        # O catalogo estima a data pela posicao na aba; cadencia de
        # publicacao lida em cima de estimativa e cadencia inventada.
        pasta = config.OUTPUTS / "canal_00001"
        alvo = pasta / "midia" / "vid1"
        alvo.mkdir(parents=True)
        (alvo / "video.mp4").write_bytes(b"x")
        (alvo / "video.info.json").write_text(
            json.dumps({"upload_date": "20260815", "duration": 612,
                        "view_count": 9999}), encoding="utf-8")
        todos = [{"id": "vid1", "titulo": "t", "data": "2026-09-01",
                  "data_aproximada": True, "duracao_s": 0, "views": 0,
                  "url": "u", "aba": "videos", "descricao": ""}]
        canal.gravar_videos(pasta, todos)

        corrigidos = baixar._registrar_datas(pasta, todos, {"vid1"},
                                             log=lambda *a: None)
        self.assertEqual(corrigidos, 1)
        gravado = canal.videos(pasta)[0]
        self.assertEqual(gravado["data"], "2026-08-15")
        self.assertFalse(gravado["data_aproximada"])
        self.assertEqual(gravado["duracao_s"], 612.0)

    def test_data_ja_exata_nao_e_mexida(self):
        pasta = config.OUTPUTS / "canal_00001"
        (pasta / "midia" / "vid1").mkdir(parents=True)
        todos = [{"id": "vid1", "data": "2026-01-01", "data_aproximada": False}]
        self.assertEqual(
            baixar._registrar_datas(pasta, todos, {"vid1"}, log=lambda *a: None),
            0)


class AmostraTests(unittest.TestCase):
    """A amostra cobre os formatos; os N mais vistos cobrem so um deles."""

    def _videos(self) -> list:
        lista = []
        for i in range(20):
            lista.append({"id": f"v{i}", "views": i * 100,
                          "duracao_s": 40 if i % 2 else 900,
                          "aba": "shorts" if i % 2 else "videos"})
        return lista

    def test_pega_dos_dois_formatos(self):
        escolhidos = baixar.amostra_por_formato(self._videos(), 6)
        self.assertEqual(len(escolhidos), 6)
        abas = {v["aba"] for v in escolhidos}
        self.assertEqual(abas, {"shorts", "videos"},
                         "a amostra ficou so com um formato")

    def test_e_reproduzivel(self):
        videos = self._videos()
        primeira = baixar.amostra_por_formato(videos, 6)
        segunda = baixar.amostra_por_formato(videos, 6)
        self.assertEqual([v["id"] for v in primeira],
                         [v["id"] for v in segunda])

    def test_pedir_mais_do_que_existe_devolve_tudo(self):
        videos = self._videos()
        self.assertEqual(len(baixar.amostra_por_formato(videos, 999)), 20)


# Legenda AUTOMATICA do YouTube: cada bloco repete a linha anterior inteira e
# acrescenta palavras, e vem salpicada de marcacao por palavra. Lida crua, a
# contagem de palavras por minuto sai varias vezes maior que a real.
VTT_ROLANTE = """WEBVTT
Kind: captions
Language: pt

00:00:00.030 --> 00:00:02.669 align:start position:0%

eu tinha<00:00:00.719><c> vinte</c><00:00:01.199><c> anos</c>

00:00:02.669 --> 00:00:02.679 align:start position:0%
eu tinha vinte anos


00:00:02.679 --> 00:00:05.310 align:start position:0%
eu tinha vinte anos
quando<00:00:03.199><c> tudo</c><00:00:03.919><c> mudou</c>

00:00:05.310 --> 00:00:05.320 align:start position:0%
eu tinha vinte anos quando tudo mudou

"""

VTT_LIMPO = """WEBVTT

00:00:01.000 --> 00:00:03.000
Primeira frase do video.

00:00:03.500 --> 00:00:07.000
Segunda frase, mais longa, que ninguem repetiu.
"""


class LegendaTests(unittest.TestCase):
    def test_rolante_nao_multiplica_palavras(self):
        falas = transcrever.ler_legenda(self._arquivo(VTT_ROLANTE))
        texto = transcrever.para_texto(falas)
        self.assertEqual(texto, "eu tinha vinte anos quando tudo mudou")
        self.assertEqual(len(texto.split()), 7,
                         "a repeticao rolante voltou a ser contada")

    def test_marcacao_por_palavra_some(self):
        falas = transcrever.ler_legenda(self._arquivo(VTT_ROLANTE))
        junto = transcrever.para_texto(falas)
        self.assertNotIn("<", junto)
        self.assertNotIn("00:00:00.719", junto)

    def test_legenda_humana_passa_inteira(self):
        falas = transcrever.ler_legenda(self._arquivo(VTT_LIMPO))
        self.assertEqual(len(falas), 2)
        self.assertIn("Primeira frase", falas[0]["texto"])
        self.assertAlmostEqual(falas[0]["inicio"], 1.0)
        self.assertAlmostEqual(falas[1]["fim"], 7.0)

    def test_ida_e_volta_pelo_srt(self):
        falas = transcrever.ler_legenda(self._arquivo(VTT_LIMPO))
        de_volta = transcrever.ler_legenda(
            self._arquivo(transcrever.para_srt(falas), ".srt"))
        self.assertEqual(transcrever.para_texto(de_volta),
                         transcrever.para_texto(falas))

    def test_arquivo_vazio_nao_levanta(self):
        self.assertEqual(transcrever.ler_legenda(self._arquivo("WEBVTT\n")), [])

    def _arquivo(self, conteudo: str, sufixo: str = ".vtt") -> Path:
        pasta = tempfile.mkdtemp()
        self.addCleanup(lambda: None)
        caminho = Path(pasta) / f"legenda{sufixo}"
        caminho.write_text(conteudo, encoding="utf-8")
        return caminho


class SobreposicaoTests(unittest.TestCase):
    def test_repeticao_exata_some(self):
        self.assertEqual(transcrever._so_o_que_e_novo("oi tudo", "oi tudo"), "")

    def test_prefixo_vira_so_o_sufixo(self):
        self.assertEqual(
            transcrever._so_o_que_e_novo("oi tudo bem", "oi tudo"), "bem")

    def test_bloco_contido_no_anterior_some(self):
        self.assertEqual(transcrever._so_o_que_e_novo("oi", "oi tudo bem"), "")

    def test_sobreposicao_parcial_no_meio(self):
        novo = transcrever._so_o_que_e_novo(
            "quando tudo mudou naquele dia", "eu tinha quando tudo mudou")
        self.assertEqual(novo, "naquele dia")

    def test_texto_sem_relacao_passa_inteiro(self):
        self.assertEqual(
            transcrever._so_o_que_e_novo("outra coisa", "eu tinha vinte"),
            "outra coisa")


class EstatisticaDeFalaTests(unittest.TestCase):
    def test_wpm_usa_o_tempo_FALADO(self):
        # Um video com 30s de musica no fim nao "fala mais devagar".
        falas = [{"inicio": 0.0, "fim": 60.0, "texto": " ".join(["pa"] * 150)}]
        stats = transcrever.estatisticas(falas, duracao_s=120.0)
        self.assertEqual(stats["wpm"], 150.0)
        self.assertEqual(stats["wpm_do_video"], 75.0)
        self.assertEqual(stats["densidade_pct"], 50.0)

    def test_sem_falas_nao_divide_por_zero(self):
        stats = transcrever.estatisticas([], duracao_s=60.0)
        self.assertEqual(stats["palavras"], 0)
        self.assertEqual(stats["densidade_pct"], 0.0)

    def test_sem_duracao_omite_a_densidade(self):
        stats = transcrever.estatisticas(
            [{"inicio": 0.0, "fim": 10.0, "texto": "uma frase"}])
        self.assertNotIn("densidade_pct", stats)


class MarcaDeTempoTests(unittest.TestCase):
    def test_formato_do_srt(self):
        self.assertEqual(transcrever._marca(0.0), "00:00:00,000")
        self.assertEqual(transcrever._marca(3661.5), "01:01:01,500")

    def test_arredondamento_nao_produz_1000_milissegundos(self):
        # 2.9999 arredondava para "00:00:02,1000" — um SRT que nenhum leitor
        # abre, gerado em silencio.
        self.assertEqual(transcrever._marca(2.9999), "00:00:03,000")

    def test_negativo_vira_zero(self):
        self.assertEqual(transcrever._marca(-5.0), "00:00:00,000")


class FfprobeTests(unittest.TestCase):
    def test_fracao_de_frame_rate(self):
        self.assertAlmostEqual(ffmpeg._fracao("30000/1001"), 29.97, places=2)
        self.assertAlmostEqual(ffmpeg._fracao("25/1"), 25.0)
        self.assertAlmostEqual(ffmpeg._fracao("24"), 24.0)

    def test_frame_rate_invalido_vira_zero(self):
        # `0/0` chega em stream de imagem. Sem isto, ZeroDivisionError no
        # meio da medicao de um acervo inteiro.
        self.assertEqual(ffmpeg._fracao("0/0"), 0.0)
        self.assertEqual(ffmpeg._fracao(None), 0.0)
        self.assertEqual(ffmpeg._fracao("nao e numero"), 0.0)


class ParserDeMedidaTests(unittest.TestCase):
    """As expressoes que leem a saida do ffmpeg. Formato mudou = teste vermelho."""

    EBUR128 = """[Parsed_ebur128_1 @ 000] Summary:

  Integrated loudness:
    I:         -14.8 LUFS
    Threshold: -25.3 LUFS

  Loudness range:
    LRA:         2.6 LU
    Threshold: -35.0 LUFS
"""

    def test_le_o_loudness_e_nao_o_threshold(self):
        # `Threshold: -25.3 LUFS` casa com um padrao frouxo e viraria o
        # loudness do canal inteiro, errado por 10 dB.
        self.assertEqual(medidas._LUFS.findall(self.EBUR128), ["-14.8"])
        self.assertEqual(medidas._LRA.findall(self.EBUR128), ["2.6"])

    def test_le_os_instantes_de_corte(self):
        saida = ("[Parsed_showinfo_2 @ 0] n:0 pts:252 pts_time:10.51 "
                 "duration:1\n"
                 "[Parsed_showinfo_2 @ 0] n:1 pts:326 pts_time:13.6 duration:1")
        self.assertEqual(medidas._TEMPO.findall(saida), ["10.51", "13.6"])

    def test_le_as_duracoes_de_silencio(self):
        saida = ("[silencedetect @ 0] silence_end: 15.6 | silence_duration: 3.3\n"
                 "[silencedetect @ 0] silence_end: 40.1 | silence_duration: 0.51")
        self.assertEqual(medidas._SILENCIO.findall(saida), ["3.3", "0.51"])


class TransicaoTests(unittest.TestCase):
    """Deteccoes coladas sao UM corte. Medido num video real: cinco
    "cortes" dentro do segundo 57 eram uma transicao so, e contar cru
    inflava `cortes_por_min` — o numero em que a biblia mais se apoia."""

    def test_transicao_vira_um_corte(self):
        cru = [57.0, 57.08, 57.16, 57.25, 57.33]
        self.assertEqual(medidas._juntar_transicoes(cru, 0.4), [57.0])

    def test_cortes_separados_sobrevivem(self):
        cru = [10.5, 13.6, 20.7]
        self.assertEqual(medidas._juntar_transicoes(cru, 0.4), cru)

    def test_ordena_antes_de_juntar(self):
        self.assertEqual(medidas._juntar_transicoes([13.6, 10.5, 10.6], 0.4),
                         [10.5, 13.6])

    def test_lista_vazia(self):
        self.assertEqual(medidas._juntar_transicoes([], 0.4), [])

    def test_minimo_zero_nao_junta_nada(self):
        cru = [57.0, 57.08]
        self.assertEqual(medidas._juntar_transicoes(cru, 0.0), cru)


class DossieTests(_PastaTemporaria):
    """O pacote de evidencia que sobe no chat."""

    def setUp(self) -> None:
        super().setUp()
        self.pasta = config.OUTPUTS / "canal_00001"
        (self.pasta / "medidas").mkdir(parents=True)
        (self.pasta / "transcricoes").mkdir(parents=True)
        (self.pasta / "medidas" / "v1.json").write_text(json.dumps({
            "video_id": "v1", "duracao_s": 300.0, "largura": 1080,
            "altura": 1920, "fps": 30.0, "vertical": True, "cortes": 40,
            "cortes_por_min": 8.0, "plano_medio_s": 7.3, "fala_pct": 82.0,
            "audio": {"lufs": -14.2, "faixa_lu": 5.1, "pausas": 12},
            "cor": {"rgb_medio": [30, 32, 40], "brilho": 32.0,
                    "saturacao": 0.2, "temperatura": -0.04, "escuro": True},
            "instantes_de_corte": [1.0, 9.0, 17.0],
        }), encoding="utf-8")
        self.video = {"id": "v1", "titulo": "Um titulo", "data": "2026-08-01",
                      "views": 120000, "aba": "videos", "duracao_s": 300.0}

    def _falas(self, quantas: int, palavras: int = 6) -> list:
        return [{"inicio": i * 5.0, "fim": i * 5.0 + 4.0,
                 "texto": " ".join(f"p{i}x{j}" for j in range(palavras))}
                for i in range(quantas)]

    def test_traz_os_numeros_medidos(self):
        (self.pasta / "transcricoes" / "v1.srt").write_text(
            transcrever.para_srt(self._falas(4)), encoding="utf-8")
        texto = dossie.montar(self.pasta, self.video, cfg={})
        self.assertIn("8.0 por minuto", texto)
        self.assertIn("-14.2 LUFS", texto)
        self.assertIn("vertical", texto)
        self.assertIn("escura", texto)

    def test_sem_transcricao_diz_que_nao_tem(self):
        # O contrario disso e o modelo analisar "a fala" de um video mudo e
        # devolver uma ficha inteira inventada.
        texto = dossie.montar(self.pasta, self.video, cfg={})
        self.assertIn("sem transcricao", texto)

    def test_sem_medida_diz_que_falta_medir(self):
        outro = {"id": "v9", "titulo": "sem medida", "views": 0}
        texto = dossie.montar(self.pasta, outro, cfg={})
        self.assertIn("nao foi medido", texto)

    def test_transcricao_longa_e_recortada_e_avisa(self):
        (self.pasta / "transcricoes" / "v1.srt").write_text(
            transcrever.para_srt(self._falas(400, palavras=10)),
            encoding="utf-8")
        texto = dossie.montar(self.pasta, self.video,
                              cfg={"transcricao_max_palavras": 200,
                                   "bloco_de_transcricao_s": 15})
        self.assertIn("RECORTADA", texto)
        self.assertIn("[...]", texto)
        self.assertLess(len(texto.split()), 1200)

    def test_transcricao_curta_passa_inteira(self):
        (self.pasta / "transcricoes" / "v1.srt").write_text(
            transcrever.para_srt(self._falas(4)), encoding="utf-8")
        texto = dossie.montar(self.pasta, self.video,
                              cfg={"transcricao_max_palavras": 1800,
                                   "bloco_de_transcricao_s": 15})
        self.assertNotIn("RECORTADA", texto)
        self.assertIn("p0x0", texto)
        self.assertIn("p3x0", texto)


# Uma resposta como o ChatGPT devolve: cerca de codigo, JSON dentro.
FICHA_CRUA = """Claro! Aqui esta a analise:

```json
{
  "gancho": {"primeiros_segundos": "pergunta direta na camera",
             "tecnica": "pergunta que a pessoa ja se fez",
             "promessa": "explicar em 3 minutos"},
  "estrutura": [
    {"de": "0:00", "ate": "0:12", "bloco": "gancho",
     "o_que_acontece": "a pergunta"},
    {"de": "0:12", "ate": "4:40", "bloco": "desenvolvimento",
     "o_que_acontece": "tres exemplos"}
  ],
  "fala": {"pessoa": "primeira", "tom": "didatico", "ritmo": "acelerado",
           "vocabulario": "coloquial", "bordoes": ["olha so"],
           "formalidade": "2"},
  "edicao": {"corte": "seco e frequente", "b_roll": "captura de tela",
             "texto_na_tela": "palavra-chave em caixa alta", "som": "musica baixa",
             "camera": "plano medio fixo"},
  "publico": {"quem": "quem esta comecando", "pressupoe": "nada",
              "dor": "medo de errar", "por_que_fica": "promessa de atalho"},
  "tema": {"assunto": "ferramentas", "angulo": "pratico"},
  "cta": {"pede": "inscricao", "onde": "4:10", "como": "explicito"},
  "promessa": {"titulo_formula": "COMO X sem Y", "thumb": "rosto e seta"},
  "reproduzivel": {"ja_automatizavel": ["roteiro", "legenda"],
                   "exige_pessoa": ["rosto na camera"], "dificil": ["b-roll"]},
  "evidencia": [{"em": "0:03", "cita": "voce ja tentou isso"},
                {"em": "4:10", "cita": "se inscreve ai"}]
}
```
"""


class FichaTests(unittest.TestCase):
    def test_le_dentro_da_cerca_de_codigo(self):
        lida = ficha.parse_ficha(FICHA_CRUA)
        self.assertFalse(lida.get("_ilegivel"))
        self.assertEqual(lida["gancho"]["tecnica"],
                         "pergunta que a pessoa ja se fez")
        self.assertEqual(len(lida["estrutura"]), 2)

    def test_le_json_cru_sem_cerca(self):
        cru = FICHA_CRUA.split("```json")[1].split("```")[0]
        self.assertFalse(ficha.parse_ficha(cru).get("_ilegivel"))

    def test_le_com_paragrafo_antes_e_depois(self):
        sujo = ("Analisei o video.\n"
                + FICHA_CRUA.split("```json")[1].split("```")[0]
                + "\nEspero ter ajudado!")
        self.assertFalse(ficha.parse_ficha(sujo).get("_ilegivel"))

    def test_resposta_sem_json_vira_ilegivel_e_nao_estoura(self):
        lida = ficha.parse_ficha("Nao consigo analisar este video.")
        self.assertTrue(lida["_ilegivel"])
        self.assertIn("a resposta nao continha JSON legivel",
                      ficha.problemas_da_ficha(lida))

    def test_chaves_traduzidas_sao_aceitas(self):
        # O modelo as vezes responde em ingles mesmo com o prompt em
        # portugues. Perder a ficha inteira por causa da chave e caro.
        lida = ficha.parse_ficha(
            '{"hook": {"tecnica": "x"}, "editing": {"corte": "seco"}, '
            '"audience": {"quem": "y"}, "speech": {"tom": "z"}}')
        for esperada in ("gancho", "edicao", "publico", "fala"):
            self.assertIn(esperada, lida)

    def test_ficha_boa_nao_tem_problema(self):
        lida = ficha.parse_ficha(FICHA_CRUA)
        self.assertEqual(ficha.problemas_da_ficha(lida), [])

    def test_secao_obrigatoria_vazia_e_pega(self):
        lida = ficha.parse_ficha(FICHA_CRUA)
        lida["publico"] = {"quem": "", "pressupoe": "", "dor": "",
                           "por_que_fica": ""}
        self.assertIn("a secao publico veio vazia ou ausente",
                      ficha.problemas_da_ficha(lida))

    def test_nao_sei_conta_como_vazio(self):
        # "N/A" preenchido em todo campo e o jeito de uma ficha passar no
        # validador sem dizer nada.
        lida = ficha.parse_ficha(FICHA_CRUA)
        lida["fala"] = {"tom": "N/A", "pessoa": "-", "ritmo": "nao sei"}
        self.assertTrue(any("fala" in p for p in ficha.problemas_da_ficha(lida)))

    def test_evidencia_sem_instante_e_pega(self):
        lida = ficha.parse_ficha(FICHA_CRUA)
        lida["evidencia"] = [{"em": "", "cita": "alguma coisa"}]
        self.assertTrue(any("sem o instante" in p
                            for p in ficha.problemas_da_ficha(lida)))

    def test_citacao_longa_demais_e_pega(self):
        # Evidencia e trecho curto que sustenta uma afirmacao. Devolver a
        # transcricao de volta nao e analise — e so recontar o video.
        lida = ficha.parse_ficha(FICHA_CRUA)
        lida["evidencia"] = [{"em": "0:03", "cita": " ".join(["pa"] * 60)}]
        self.assertTrue(any("longas demais" in p for p in
                            ficha.problemas_da_ficha(lida,
                                                     cfg={"citacao_max_palavras": 12})))

    def test_estrutura_curta_demais_e_pega(self):
        lida = ficha.parse_ficha(FICHA_CRUA)
        lida["estrutura"] = [{"de": "0:00", "ate": "1:00", "bloco": "tudo"}]
        self.assertTrue(any("estrutura" in p
                            for p in ficha.problemas_da_ficha(lida)))

    def test_resumo_nao_estoura_com_ficha_torta(self):
        self.assertIsInstance(ficha.resumo_da_ficha({}), str)
        self.assertIsInstance(
            ficha.resumo_da_ficha({"gancho": "texto solto"}), str)


class PromptTests(unittest.TestCase):
    def test_abertura_traz_o_canal_e_o_formato(self):
        texto = ficha.prompt_abertura("CANAL: Teste\n  10 videos", total=6,
                                      cfg={"citacao_max_palavras": 12,
                                           "citacoes_por_ficha": 5})
        self.assertIn("CANAL: Teste", texto)
        self.assertIn("6 videos", texto)
        for secao in ficha.SECOES:
            self.assertIn(secao, texto, f"{secao} nao esta no formato pedido")

    def test_abertura_proibe_reescrever_a_transcricao(self):
        texto = ficha.prompt_abertura("CANAL: x", total=3)
        self.assertIn("Nao reescreva a transcricao", texto)

    def test_abertura_manda_confiar_no_medido(self):
        texto = ficha.prompt_abertura("CANAL: x", total=3)
        self.assertIn("nao os re-estime", texto.lower().replace("ã", "a"))

    def test_conserto_lista_os_problemas_e_pede_so_o_json(self):
        texto = ficha.prompt_conserto(["evidencia vazia", "estrutura curta"])
        self.assertIn("evidencia vazia", texto)
        self.assertIn("Nao refaca a analise", texto)


class LotesTests(unittest.TestCase):
    def test_divide_certo(self):
        self.assertEqual(analise._lotes([1, 2, 3, 4, 5], 2),
                         [[1, 2], [3, 4], [5]])

    def test_lote_zero_nao_faz_laco_infinito(self):
        self.assertEqual(analise._lotes([1, 2], 0), [[1], [2]])

    def test_lista_vazia(self):
        self.assertEqual(analise._lotes([], 5), [])


class PendentesTests(_PastaTemporaria):
    def setUp(self) -> None:
        super().setUp()
        self.pasta = config.OUTPUTS / "canal_00001"
        # O que habilita a analise e a MEDIDA, nao o mp4: o que sobe no chat
        # e o dossie, e o video ja pode ter sido apagado pelo `absorver`.
        (self.pasta / "medidas").mkdir(parents=True)
        for video_id in ("v1", "v2", "v3"):
            (self.pasta / "medidas" / f"{video_id}.json").write_text(
                "{}", encoding="utf-8")
        canal.gravar_videos(self.pasta, [
            {"id": v, "titulo": v, "url": "u", "duracao_s": 1, "views": 0,
             "data": "", "data_aproximada": True, "aba": "videos",
             "descricao": ""} for v in ("v1", "v2", "v3")])

    def test_pula_quem_ja_tem_ficha(self):
        # A retomada e um arquivo em disco. Um acervo grande leva horas e o
        # navegador cai; reperguntar o que ja foi respondido custa a noite.
        destino = self.pasta / "fichas" / "chatgpt"
        destino.mkdir(parents=True)
        (destino / "v2.json").write_text("{}", encoding="utf-8")
        alvos = analise.pendentes(self.pasta, "chatgpt")
        self.assertEqual([v["id"] for v in alvos], ["v1", "v3"])

    def test_refazer_traz_todos_de_volta(self):
        destino = self.pasta / "fichas" / "chatgpt"
        destino.mkdir(parents=True)
        (destino / "v2.json").write_text("{}", encoding="utf-8")
        alvos = analise.pendentes(self.pasta, "chatgpt", refazer=True)
        self.assertEqual(len(alvos), 3)

    def test_video_sem_medida_nao_entra(self):
        # Sem medida nao ha dossie, e sem dossie nao ha o que mandar.
        (self.pasta / "medidas" / "v1.json").unlink()
        self.assertEqual([v["id"] for v in analise.pendentes(self.pasta, "gemini")],
                         ["v2", "v3"])

    def test_video_sem_mp4_MAS_com_medida_entra(self):
        # O contrato que o fluxo de passagem exige: o mp4 foi apagado depois
        # da primeira ficha, e o segundo provedor ainda precisa analisar.
        self.assertEqual(baixar.baixados(self.pasta), set())
        self.assertEqual(len(analise.pendentes(self.pasta, "gemini")), 3)

    def test_limite_corta(self):
        self.assertEqual(len(analise.pendentes(self.pasta, "gemini", limite=2)), 2)

    def test_provedor_desconhecido_e_recusado(self):
        with self.assertRaises(analise.NaoAnalisou):
            analise.analisar("canal_00001", provedor="claude")


def _ficha(video_id, **secoes) -> dict:
    base = {"video_id": video_id, "titulo": video_id}
    base.update(secoes)
    return base


class AgregacaoTests(unittest.TestCase):
    """A contagem e CODIGO. Pedir a um LLM quantas fichas dizem 'corte seco'
    troca um numero exato por uma impressao — e ainda paga o contexto."""

    def test_mediana_de_par_e_impar(self):
        self.assertEqual(biblia._mediana([1, 2, 3]), 2)
        self.assertEqual(biblia._mediana([1, 2, 3, 4]), 2.5)

    def test_mediana_ignora_None_e_texto(self):
        self.assertEqual(biblia._mediana([None, 4, "x", 2]), 3)
        self.assertIsNone(biblia._mediana([None, "x"]))

    def test_contagem_junta_variacoes_de_escrita(self):
        fichas = [_ficha("a", fala={"tom": "Didático"}),
                  _ficha("b", fala={"tom": "didatico"}),
                  _ficha("c", fala={"tom": "seco"})]
        contagem = biblia._contagem(fichas, "fala", "tom")
        self.assertEqual(contagem[0]["vezes"], 2)
        self.assertEqual(contagem[1]["vezes"], 1)

    def test_contagem_ignora_campo_ausente_ou_torto(self):
        fichas = [_ficha("a", fala={"tom": ""}), _ficha("b"),
                  _ficha("c", fala="texto solto")]
        self.assertEqual(biblia._contagem(fichas, "fala", "tom"), [])

    def test_bordoes_contam_por_item_da_lista(self):
        fichas = [_ficha("a", fala={"bordoes": ["olha so", "entao"]}),
                  _ficha("b", fala={"bordoes": ["Olha só"]})]
        frequentes = biblia._lista_frequente(fichas, "fala", "bordoes")
        self.assertEqual(frequentes[0]["valor"].lower(), "olha so")
        self.assertEqual(frequentes[0]["vezes"], 2)


class CadenciaTests(unittest.TestCase):
    def test_calcula_por_semana(self):
        videos = [{"data": "2026-01-01"}, {"data": "2026-01-08"},
                  {"data": "2026-01-15"}]
        cadencia = biblia._cadencia(videos)
        self.assertEqual(cadencia["primeiro"], "2026-01-01")
        self.assertAlmostEqual(cadencia["por_semana"], 1.5, places=1)
        self.assertAlmostEqual(cadencia["intervalo_medio_dias"], 7.0)

    def test_um_video_so_nao_divide_por_zero(self):
        self.assertEqual(biblia._cadencia([{"data": "2026-01-01"}]),
                         {"videos_com_data": 1})

    def test_sem_data_nao_estoura(self):
        self.assertEqual(biblia._cadencia([{}, {"data": ""}]),
                         {"videos_com_data": 0})


class ConsensoTests(unittest.TestCase):
    """Onde as duas IAs discordam vira hipotese marcada, nao ruido."""

    def test_concordancia_por_palavra_em_comum(self):
        por_provedor = {
            "chatgpt": [_ficha("v1", gancho={"tecnica": "pergunta direta"})],
            "gemini": [_ficha("v1", gancho={"tecnica": "uma pergunta ao espectador"})],
        }
        consenso = biblia._consenso(por_provedor)
        self.assertEqual(consenso["comparaveis"], 1)
        self.assertEqual(consenso["n_divergencias"], 0)

    def test_leitura_oposta_vira_divergencia(self):
        por_provedor = {
            "chatgpt": [_ficha("v1", fala={"tom": "didatico"})],
            "gemini": [_ficha("v1", fala={"tom": "indignado"})],
        }
        consenso = biblia._consenso(por_provedor)
        self.assertEqual(consenso["n_divergencias"], 1)
        self.assertEqual(consenso["divergencias"][0]["campo"], "fala.tom")

    def test_palavras_vazias_nao_fabricam_acordo(self):
        # Sem a lista de vazias, "o video de x" e "o video de y" concordariam
        # por causa de "o", "video" e "de" — e o consenso viraria 100%.
        por_provedor = {
            "chatgpt": [_ficha("v1", publico={"quem": "o pessoal de design"})],
            "gemini": [_ficha("v1", publico={"quem": "o pessoal de vendas"})],
        }
        self.assertEqual(biblia._consenso(por_provedor)["n_divergencias"], 0)
        por_provedor = {
            "chatgpt": [_ficha("v1", publico={"quem": "o video de design"})],
            "gemini": [_ficha("v1", publico={"quem": "um canal para cozinheiros"})],
        }
        self.assertEqual(biblia._consenso(por_provedor)["n_divergencias"], 1)

    def test_um_provedor_so_avisa_em_vez_de_mentir(self):
        consenso = biblia._consenso({"chatgpt": [_ficha("v1")], "gemini": []})
        self.assertEqual(consenso["comparaveis"], 0)
        self.assertIn("aviso", consenso)


ESQUELETO_CRU = """UMA FRASE: um canal que explica ferramenta nova em tres minutos.
PUBLICO: quem trabalha com isso e nao tem tempo de ler documentacao.
FORMULA: gancho de pergunta, tres exemplos, atalho pratico, CTA.
DURACAO ALVO: 180
APOSTA 1: abrir com a duvida do espectador | 8 de 10 videos abrem assim
APOSTA 2: nenhum video passa de 4 minutos | duracao mediana medida: 3:12
APOSTA 3: exemplo na tela, nunca so falado | b-roll em 9 fichas
APOSTA 4: CTA unico, no fim | cta.onde mediano em 3:40
APOSTA 5: sem musica sob a fala | -14 LUFS e 88% de fala
RISCO: copiar o tom sem ter o exemplo na tela.
"""


class EsqueletoTests(unittest.TestCase):
    def test_le_os_campos_e_as_apostas(self):
        lido = biblia.parse_esqueleto(ESQUELETO_CRU)
        self.assertIn("tres minutos", lido["frase"])
        self.assertEqual(len(lido["apostas"]), 5)
        self.assertEqual(lido["apostas"][0]["evidencia"],
                         "8 de 10 videos abrem assim")
        self.assertIn("copiar o tom", lido["risco"])

    def test_aceita_markdown_e_bullet(self):
        sujo = ("## **UMA FRASE:** um canal de teste\n"
                "- **FORMULA:** gancho e desfecho\n"
                "* PUBLICO: qualquer um\n"
                "APOSTA 1: uma decisao | uma evidencia\n")
        lido = biblia.parse_esqueleto(sujo)
        self.assertEqual(lido["frase"], "um canal de teste")
        self.assertEqual(lido["formula"], "gancho e desfecho")

    def test_apostas_fora_de_ordem_sao_ordenadas(self):
        lido = biblia.parse_esqueleto(
            "APOSTA 3: c | e3\nAPOSTA 1: a | e1\nAPOSTA 2: b | e2")
        self.assertEqual([a["n"] for a in lido["apostas"]], [1, 2, 3])

    def test_esqueleto_bom_nao_tem_problema(self):
        lido = biblia.parse_esqueleto(ESQUELETO_CRU)
        self.assertEqual(biblia.problemas_do_esqueleto(lido), [])

    def test_falta_de_formula_e_pega(self):
        # E da formula que sai o modelo de roteiro do preset.
        lido = biblia.parse_esqueleto(ESQUELETO_CRU)
        lido["formula"] = ""
        self.assertTrue(any("FORMULA" in p
                            for p in biblia.problemas_do_esqueleto(lido)))

    def test_aposta_sem_evidencia_e_pega(self):
        lido = biblia.parse_esqueleto(
            "UMA FRASE: x\nFORMULA: y\nPUBLICO: z\n"
            "APOSTA 1: a | e\nAPOSTA 2: b\nAPOSTA 3: c | e")
        self.assertTrue(any("sem evidencia" in p
                            for p in biblia.problemas_do_esqueleto(lido)))

    def test_resposta_vazia_nao_estoura(self):
        lido = biblia.parse_esqueleto("")
        self.assertEqual(lido["apostas"], [])
        self.assertTrue(biblia.problemas_do_esqueleto(lido))


class LastroTests(unittest.TestCase):
    """Secao sem numero nem instante e opiniao, nao biblia."""

    def test_reconhece_numero_com_unidade(self):
        for texto in ("dura 180s", "sao 4 cortes por minuto", "-14 LUFS",
                      "88% de fala", "12 palavras", "o CTA entra em 3:40"):
            with self.subTest(texto=texto):
                self.assertTrue(biblia._tem_lastro(texto), texto)

    def test_texto_generico_nao_passa(self):
        self.assertFalse(biblia._tem_lastro(
            "O canal usa uma linguagem envolvente e proxima do espectador, "
            "criando conexao."))

    def test_secao_curta_e_pega(self):
        dados = {"secoes": {"formula": "curta demais"},
                 "esqueleto": {"apostas": [{"n": 1}]}}
        self.assertTrue(any("curta demais" in p for p in
                            biblia.problemas_da_biblia(dados)))

    def test_secao_sem_lastro_e_pega_so_onde_se_exige(self):
        longa = " ".join(["palavra"] * 80)
        dados = {"secoes": {"formula": longa, "resumo": longa},
                 "esqueleto": {"apostas": [{"n": 1}]}}
        problemas = biblia.problemas_da_biblia(
            dados, {"exige_evidencia": ["formula"]})
        self.assertEqual(len(problemas), 1)
        self.assertIn("formula", problemas[0])

    def test_markdown_da_biblia_nao_estoura_com_dados_minimos(self):
        texto = biblia.para_markdown({"canal": {"nome": "X"}, "secoes": {},
                                      "esqueleto": {}})
        self.assertIn("Bíblia", texto)


class ClassificarTests(unittest.TestCase):
    """O diagnostico e codigo: um LLM nao conhece este repositorio."""

    CAPACIDADES = {
        "capacidades": [
            {"nome": "narracao sintetica", "onde": "random_builds/",
             "palavras": ["narracao", "voz em off"]},
            {"nome": "render de video", "onde": "random_builds/",
             "palavras": ["render", "montagem"]},
        ],
        "exige_pessoa": ["rosto", "voz propria"],
    }

    def test_casa_com_capacidade_existente(self):
        achado = preset.classificar("narracao do roteiro", self.CAPACIDADES)
        self.assertEqual(achado["onde"], "pronto")
        self.assertEqual(achado["capacidade"], "narracao sintetica")

    def test_rosto_na_camera_exige_pessoa(self):
        self.assertEqual(
            preset.classificar("rosto na camera", self.CAPACIDADES)["onde"],
            "pessoa")

    def test_pessoa_vence_capacidade(self):
        # "voz propria" e humano mesmo tendo "voz" numa capacidade. Fingir
        # que a pipeline resolve produz um canal que soa falso.
        self.assertEqual(
            preset.classificar("voz propria do apresentador",
                               self.CAPACIDADES)["onde"], "pessoa")

    def test_o_que_nao_casa_vai_para_construir(self):
        self.assertEqual(
            preset.classificar("grafico animado 3d", self.CAPACIDADES)["onde"],
            "construir")

    def test_acento_nao_atrapalha(self):
        self.assertEqual(
            preset.classificar("narração em off", self.CAPACIDADES)["onde"],
            "pronto")

    def test_fichas_mandam_mais_que_a_palavra_chave(self):
        # Quem viu o video sabe se o rosto e essencial; a lista de palavras
        # e so um atalho.
        mapa = preset.mapear_lacunas(
            {"exige_pessoa": [{"valor": "montagem no ritmo dele", "vezes": 4}]},
            self.CAPACIDADES)
        self.assertEqual(len(mapa["pessoa"]), 1)
        self.assertEqual(mapa["pronto"], [])

    def test_item_repetido_entra_uma_vez_so(self):
        mapa = preset.mapear_lacunas({
            "ja_automatizavel": [{"valor": "narracao", "vezes": 3}],
            "dificil": [{"valor": "Narração", "vezes": 1}],
        }, self.CAPACIDADES)
        self.assertEqual(len(mapa["pronto"]), 1)

    def test_lacunas_md_nao_estoura_vazio(self):
        vazio = {"pronto": [], "construir": [], "pessoa": []}
        texto = preset.lacunas_md("Canal", vazio, {})
        self.assertIn("Dá para automatizar já", texto)


PRESET_CRU = """ESTRUTURA
GANCHO (1 cena): a pergunta que o titulo promete, dita de uma vez.
CONTEXTO (2 cenas): so o que faz a duvida fazer sentido.
EXEMPLOS (6 cenas): um caso concreto por cena, com o resultado na tela.
ATALHO (2 cenas): o jeito rapido de fazer, passo a passo.
CTA (1 cena): uma pergunta direta sobre o que a pessoa faria.

NARRACAO
- Frases de no maximo 14 palavras.
- Primeira pessoa, sempre.
- Nenhuma cena sem um numero ou um nome concreto.
- Nada de introducao: a primeira frase ja e o gancho.
- Verbo no presente.
- Nunca prometer o que a cena seguinte nao entrega.
- Uma unica ideia por cena.
- Fechar com pergunta, nao com pedido.

IMAGEM
clean product photography, soft diffused light, muted desaturated palette, shallow depth of field, neutral background, photorealistic

NEGATIVO
text, watermark, logo, extra fingers, blurry
"""


class PresetTests(unittest.TestCase):
    def test_le_os_quatro_blocos(self):
        lido = preset.parse_preset(PRESET_CRU)
        self.assertEqual(len(lido["estrutura"]), 5)
        self.assertEqual(len(lido["narracao"]), 8)
        self.assertIn("desaturated", lido["imagem"])
        self.assertIn("watermark", lido["negativo"])

    def test_rotulo_com_acento_e_markdown_e_aceito(self):
        lido = preset.parse_preset(
            "## **NARRAÇÃO**\n- uma regra bem comprida aqui\n"
            "- outra regra bem comprida\n**IMAGEM:**\numa frase em ingles aqui")
        self.assertEqual(len(lido["narracao"]), 2)
        self.assertIn("frase em ingles", lido["imagem"])

    def test_preset_bom_nao_tem_problema(self):
        self.assertEqual(
            preset.problemas_do_preset(preset.parse_preset(PRESET_CRU)), [])

    def test_estrutura_curta_e_pega(self):
        lido = preset.parse_preset("ESTRUTURA\nGANCHO (1 cena): x\n"
                                   "NARRACAO\n- uma regra bem comprida\n")
        self.assertTrue(any("ESTRUTURA" in p
                            for p in preset.problemas_do_preset(lido)))

    def test_soma_as_cenas_da_estrutura(self):
        lido = preset.parse_preset(PRESET_CRU)
        self.assertEqual(preset._cenas_da_estrutura(lido["estrutura"]), 12)

    def test_cenas_alvo_respeita_os_limites(self):
        # Plano medido de 0,5s nao pode virar cena de imagem de 0,5s.
        self.assertEqual(
            preset._cenas_alvo({"duracao_mediana_s": 60, "plano_medio_s": 0.5}),
            round(60 / preset.CENA_MIN_S))
        self.assertLessEqual(
            preset._cenas_alvo({"duracao_mediana_s": 6000,
                                "plano_medio_s": 5}), 40)

    def test_roteiro_json_tem_a_forma_que_o_historias_le(self):
        lido = preset.parse_preset(PRESET_CRU)
        roteiro = preset.montar_roteiro_json(
            "Canal Teste", lido, {"duracao_mediana_s": 190,
                                  "plano_medio_s": 6})
        for chave in ("modelo_padrao", "modelos", "regras", "limites"):
            self.assertIn(chave, roteiro)
        modelo = roteiro["modelos"][roteiro["modelo_padrao"]]
        for chave in ("rotulo", "duracao_alvo", "cenas_alvo", "estrutura"):
            self.assertIn(chave, modelo)
        self.assertEqual(modelo["cenas_alvo"], 12)
        self.assertEqual(modelo["duracao_alvo"], 190)
        for chave in ("narracao", "imagem", "tempo"):
            self.assertIn(chave, roteiro["regras"])
        self.assertEqual(roteiro["regras"]["narracao"], lido["narracao"])

    def test_slug_do_canal_e_seguro_para_chave_json(self):
        roteiro = preset.montar_roteiro_json(
            "Canal do João! (2026)", preset.parse_preset(PRESET_CRU), {})
        chave = roteiro["modelo_padrao"]
        self.assertTrue(chave.replace("_", "").isalnum(), chave)
        self.assertIn(chave, roteiro["modelos"])


class MedirDeVerdadeTests(unittest.TestCase):
    """Mede um mp4 SINTETICO, gerado na hora pelo proprio ffmpeg.

    Os testes de regex acima provam que sabemos ler a saida do ffmpeg. Este
    prova que a passada inteira funciona — que os argumentos estao na ordem
    certa, que `-fps_mode passthrough` sobrevive, que o contato sai. Sem ele,
    um argumento invertido so apareceria no meio de um acervo de 300 videos.

    O video e gerado, nao versionado: binario em repositorio envelhece e
    ninguem lembra de por que ele esta la.
    """

    @classmethod
    def setUpClass(cls) -> None:
        if ffmpeg.faltando():
            raise unittest.SkipTest("ffmpeg/ffprobe nao estao no PATH")
        cls._tmp = tempfile.TemporaryDirectory()
        cls.video = Path(cls._tmp.name) / "sintetico.mp4"
        # 6s: 3s de barras coloridas com tom de 440 Hz, 3s de preto e
        # silencio. Da um corte de cena no meio e silencio mensuravel.
        codigo, _saida, erro = ffmpeg.ffmpeg([
            "-f", "lavfi", "-i", "testsrc=size=320x240:rate=15:duration=3",
            "-f", "lavfi", "-i", "color=black:size=320x240:rate=15:duration=3",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=3",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v];[2:a][3:a]concat=n=2:v=0:a=1[a]",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset",
            "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-y",
            str(cls.video)], timeout=180)
        if codigo != 0 or not cls.video.is_file():
            raise unittest.SkipTest(
                f"nao consegui gerar o mp4 de teste: {erro[-200:]}")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "_tmp"):
            cls._tmp.cleanup()

    def test_sondar_le_o_que_o_arquivo_e(self):
        sonda = ffmpeg.sondar(self.video)
        self.assertAlmostEqual(sonda["duracao_s"], 6.0, delta=0.6)
        self.assertEqual((sonda["largura"], sonda["altura"]), (320, 240))
        self.assertTrue(sonda["tem_audio"])
        self.assertFalse(sonda["vertical"])

    def test_arquivo_que_nao_e_video_levanta_com_instrucao(self):
        # Um mp4 truncado (download morto no meio) passa por varias
        # operacoes do ffmpeg sem erro e so falha depois. Tem que virar erro
        # alto aqui, com o conserto na mensagem.
        falso = Path(self._tmp.name) / "quebrado.mp4"
        falso.write_bytes(b"isto nao e um mp4")
        with self.assertRaises(ffmpeg.NaoMediu) as caso:
            ffmpeg.sondar(falso)
        self.assertIn("baixar", str(caso.exception))

    def test_a_medicao_inteira_devolve_numeros_coerentes(self):
        cfg = config.carregar("medidas")
        contato = Path(self._tmp.name) / "contato.jpg"
        medida = medidas.medir_video(self.video, cfg=cfg, contato_em=contato)

        self.assertGreaterEqual(medida["cortes"], 1,
                                "o corte entre as barras e o preto sumiu")
        self.assertGreater(medida["cortes_por_min"], 0)
        # Metade do video e silencio de verdade.
        self.assertGreater(medida["silencio_pct"], 25.0)
        self.assertLess(medida["silencio_pct"], 75.0)
        self.assertIsNotNone(medida["audio"]["lufs"])
        # As amostras de cor sao KEYFRAMES, nao todos os frames: um video de
        # 6s a 15fps tem 90 frames, e sem `-fps_mode passthrough` voltavam
        # todos eles.
        self.assertGreater(medida["cor"]["amostras"], 0)
        self.assertLess(medida["cor"]["amostras"], 60)
        self.assertTrue(contato.is_file(), "o mosaico de contato nao saiu")
        self.assertGreater(contato.stat().st_size, 500)

    def test_amostra_parcial_e_marcada(self):
        medida = medidas.medir_video(
            self.video, cfg={**config.carregar("medidas"), "amostra_s": 2})
        self.assertTrue(medida["amostra_parcial"])
        self.assertAlmostEqual(medida["analisado_s"], 2.0, delta=0.5)


class AbsorverTests(_PastaTemporaria):
    """O fluxo de passagem: o video entra, vira ficha, e sai.

    O acervo do canal que motivou isto tem 342 videos e passaria de 400 GB.
    O disco tem que ficar PLANO — sobe durante um lote, volta a quase zero
    quando ele fecha.
    """

    def setUp(self) -> None:
        super().setUp()
        self.pasta = config.OUTPUTS / "canal_00001"
        (self.pasta / "midia").mkdir(parents=True)
        canal.gravar_videos(self.pasta, [
            {"id": v, "titulo": v, "url": f"u/{v}", "duracao_s": 60,
             "views": 100 - i, "data": "", "data_aproximada": True,
             "aba": "videos", "descricao": ""}
            for i, v in enumerate(("v1", "v2", "v3"))])

    # Grande o bastante para sobreviver ao arredondamento em MB — o relatorio
    # mostra uma casa decimal, e um arquivo de 4 KB apareceria como "0.0 MB".
    TAMANHO_FALSO = 2_000_000

    def _midia(self, video_id: str, *, com_video: bool = True) -> Path:
        alvo = self.pasta / "midia" / video_id
        alvo.mkdir(exist_ok=True)
        (alvo / "video.info.json").write_text("{}", encoding="utf-8")
        (alvo / "video.webp").write_bytes(b"thumb")
        (alvo / "video.pt.vtt").write_text("WEBVTT\n", encoding="utf-8")
        if com_video:
            (alvo / "video.mp4").write_bytes(b"x" * self.TAMANHO_FALSO)
        return alvo

    def _ficha(self, video_id: str, provedor: str) -> None:
        destino = self.pasta / "fichas" / provedor
        destino.mkdir(parents=True, exist_ok=True)
        (destino / f"{video_id}.json").write_text("{}", encoding="utf-8")

    def test_apagar_tira_o_video_e_deixa_o_derivado(self):
        alvo = self._midia("v1")
        liberados = baixar.apagar_midia(self.pasta, "v1")
        self.assertEqual(liberados, self.TAMANHO_FALSO)
        self.assertFalse((alvo / "video.mp4").exists())
        # O derivado e o que a biblia usa depois; sao quilobytes.
        self.assertTrue((alvo / "video.info.json").exists())
        self.assertTrue((alvo / "video.webp").exists())
        self.assertTrue((alvo / "video.pt.vtt").exists())

    def test_apagar_leva_o_arquivo_parcial_junto(self):
        alvo = self._midia("v1")
        (alvo / "video.mp4.part").write_bytes(b"metade")
        baixar.apagar_midia(self.pasta, "v1")
        self.assertFalse((alvo / "video.mp4.part").exists())

    def test_apagar_de_novo_nao_estoura(self):
        self._midia("v1")
        baixar.apagar_midia(self.pasta, "v1")
        self.assertEqual(baixar.apagar_midia(self.pasta, "v1"), 0)
        self.assertEqual(baixar.apagar_midia(self.pasta, "nao_existe"), 0)

    def test_alvo_e_quem_falta_ficha_de_algum_provedor(self):
        self._ficha("v1", "chatgpt")
        self._ficha("v1", "gemini")
        self._ficha("v2", "chatgpt")          # falta o gemini
        restantes = [v["id"] for v in absorver.alvos("canal_00001")]
        self.assertEqual(restantes, ["v2", "v3"])

    def test_video_analisado_pelos_dois_sai_do_alvo_mesmo_sem_mp4(self):
        # E o ponto do fluxo: o mp4 vai embora e o video NAO volta para a
        # fila. Antes disto, `pendentes` exigia o arquivo em disco e a
        # segunda passada rebaixaria tudo.
        self._ficha("v3", "chatgpt")
        self._ficha("v3", "gemini")
        self.assertNotIn("v3", [v["id"] for v in absorver.alvos("canal_00001")])

    def test_analisavel_olha_a_medida_e_nao_o_mp4(self):
        (self.pasta / "medidas").mkdir(parents=True)
        (self.pasta / "medidas" / "v1.json").write_text("{}", encoding="utf-8")
        self.assertTrue(analise.analisavel(self.pasta, "v1"))
        self.assertFalse(analise.analisavel(self.pasta, "v2"))

    def test_dossie_ja_montado_tambem_basta(self):
        (self.pasta / "dossies").mkdir(parents=True)
        (self.pasta / "dossies" / "v2.md").write_text("x", encoding="utf-8")
        self.assertTrue(analise.analisavel(self.pasta, "v2"))

    def test_pendentes_nao_exige_mais_o_video_em_disco(self):
        (self.pasta / "medidas").mkdir(parents=True)
        for video_id in ("v1", "v2", "v3"):
            (self.pasta / "medidas" / f"{video_id}.json").write_text(
                "{}", encoding="utf-8")
        alvos = analise.pendentes(self.pasta, "chatgpt")
        self.assertEqual([v["id"] for v in alvos], ["v1", "v2", "v3"])

    def test_so_estes_limita_ao_que_o_subprocesso_recebeu(self):
        # E assim que o `absorver` fala com cada provedor: --video id id.
        (self.pasta / "medidas").mkdir(parents=True)
        for video_id in ("v1", "v2", "v3"):
            (self.pasta / "medidas" / f"{video_id}.json").write_text(
                "{}", encoding="utf-8")
        alvos = analise.pendentes(self.pasta, "gemini", so_estes=["v2"])
        self.assertEqual([v["id"] for v in alvos], ["v2"])

    def test_criterio_padrao_pega_os_mais_vistos(self):
        escolhidos = absorver.alvos("canal_00001", limite=2, criterio="views")
        self.assertEqual([v["id"] for v in escolhidos], ["v1", "v2"])

    def test_em_disco_conta_so_video(self):
        self._midia("v1")
        self._midia("v2", com_video=False)
        disco = absorver.em_disco("canal_00001")
        self.assertEqual(disco["videos_em_disco"], 1)
        self.assertGreater(disco["mb"], 0)

    def test_status_mostra_o_disco_e_os_completos(self):
        self._midia("v1")
        self._ficha("v2", "chatgpt")
        self._ficha("v2", "gemini")
        dados = status.do_canal("canal_00001")
        self.assertEqual(dados["completos"], 1)
        self.assertEqual(dados["em_disco"]["videos"], 1)
        self.assertIn("absorver", dados["proximo_passo"])

    def test_proximo_passo_vira_biblia_quando_todos_fecham(self):
        for video_id in ("v1", "v2", "v3"):
            self._ficha(video_id, "chatgpt")
            self._ficha(video_id, "gemini")
        dados = status.do_canal("canal_00001")
        self.assertEqual(dados["completos"], 3)
        self.assertIn("biblia", dados["proximo_passo"])

    def test_baixar_estes_nao_baixa_o_que_ja_esta_em_disco(self):
        self._midia("v1")
        videos = [v for v in canal.videos(self.pasta) if v["id"] == "v1"]
        # Sem rede: se ele tentasse baixar, `rodar_streaming` seria chamado.
        resultado = baixar.baixar_estes(self.pasta, videos,
                                        coleta=config.carregar("coleta"),
                                        log=lambda *_a: None)
        self.assertEqual(resultado["novos"], 0)
        self.assertEqual(resultado["faltaram"], [])

    def test_lotes_dividem_o_alvo(self):
        self.assertEqual(absorver._lotes([1, 2, 3, 4, 5], 2),
                         [[1, 2], [3, 4], [5]])
        self.assertEqual(absorver._lotes([1, 2], 0), [[1], [2]])

    def test_o_arquivo_de_retomada_fica_de_fora_no_fluxo_de_passagem(self):
        # Com a linha no arquivo de retomada, o yt-dlp se recusaria a
        # rebaixar um video que foi apagado DE PROPOSITO.
        coleta = config.carregar("coleta")
        lista = self.pasta / "midia" / "_alvo.txt"
        com = baixar._argumentos(self.pasta, lista, coleta, com_retomada=True)
        sem = baixar._argumentos(self.pasta, lista, coleta, com_retomada=False)
        self.assertIn("--download-archive", com)
        self.assertNotIn("--download-archive", sem)


class PonteTests(unittest.TestCase):
    """O `espelho` fala com os vizinhos, e nenhum pacote sombreia o outro."""

    def test_o_cliente_de_llm_dos_vizinhos_importa(self):
        from contos.llm import cliente
        self.assertTrue(hasattr(cliente, "abrir_cliente"))

    def test_o_contos_carregado_e_o_de_historias(self):
        # A regra inviolavel do repositorio: um diretorio da raiz com o nome
        # de um pacote vira namespace vazio e sombreia a instalacao. Se este
        # teste falhar, alguem renomeou uma pasta.
        import contos.llm.cliente as vizinho
        self.assertIn("historias", str(Path(vizinho.__file__)).lower())

    def test_o_espelho_carregado_e_o_daqui(self):
        import espelho
        self.assertIn("mimetizar", str(Path(espelho.__file__)).lower())

    def test_o_diario_e_as_travas_estao_ao_alcance(self):
        import builds.atividade as atividade
        import builds.travas as travas
        self.assertTrue(hasattr(atividade, "registrar"))
        self.assertTrue(hasattr(travas, "trava"))


class ConfiguracaoDoProjetoTests(unittest.TestCase):
    """O que o CI e a catraca cobram, cobrado aqui primeiro."""

    def test_o_pacote_nao_tem_nome_de_pasta_da_raiz(self):
        raiz = config.RAIZ.parent
        pastas = {p.name.lower() for p in raiz.iterdir() if p.is_dir()}
        self.assertNotIn("espelho", pastas,
                         "pacote com nome de pasta da raiz vira namespace "
                         "vazio e sombreia a instalacao em silencio")

    def test_config_json_todos_carregam(self):
        for arquivo in config.CONFIG.glob("*.json"):
            with self.subTest(arquivo=arquivo.name):
                json.loads(arquivo.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
