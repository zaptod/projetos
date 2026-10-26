# -*- coding: utf-8 -*-
"""A medicao da serie "Como eu criei um Blue Lock" (canal `bluelock`), 26/10/2026.

Em 26/10 a serie estreou (YouTube Egoistsoccer, TikTok zombie_surviv0rs) e
nenhuma coleta lia um numero dela. As tres perguntas da lei desta parte, uma a
uma, com o caso VAZIO ao lado do cheio:

- zero episodio / zero comentario / zero leitura NAO e nota boa;
- "views 24 h" sem leitura perto das 24 h e "ainda nao", nunca 0;
- leitura que falha (token, rede, Studio) aparece como "NAO consegui ler".

Nada aqui toca rede, navegador nem o disco de verdade.
"""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from builds.publicar import metricas, serie_comentarios as C, serie_metricas as S


class _NaPasta(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        outputs = Path(self.tmp.name)
        patch = mock.patch.object(metricas, "OUTPUTS", outputs)
        patch.start()
        self.addCleanup(patch.stop)
        self.pasta = outputs / "_serie_bluelock"
        self.pasta.mkdir(parents=True)

    def ledger(self, *linhas):
        with open(self.pasta / "publicados.jsonl", "w", encoding="utf-8") as fh:
            for linha in linhas:
                fh.write(json.dumps(linha) + "\n")

    def salvar_youtube(self, yid, **campos):
        pasta = self.pasta / "_metricas"
        pasta.mkdir(exist_ok=True)
        (pasta / f"{yid}.json").write_text(json.dumps(
            {"youtube_id": yid, "canal": "bluelock", **campos}), encoding="utf-8")


EP1_YT = {"quando": "2026-10-26T10:22:49", "plataforma": "youtube",
          "youtube_id": "8RFvQp9VogE", "episodio": 1, "publicado": True,
          "video_id": "bluelock_ep01", "titulo": "Ep 1"}
EP1_TT = {"quando": "2026-10-26T11:00:34", "plataforma": "tiktok",
          "youtube_id": None, "episodio": 1, "publicado": True,
          "video_id": "bluelock_ep01", "titulo": "Ep 1"}


class AColetaConheceASerie(unittest.TestCase):

    def test_a_serie_e_parte_da_coleta_e_da_marca(self):
        nomes = [metricas.nome_da_parte(c, p) for c, p in metricas.partes()]
        self.assertIn("bluelock", nomes)
        self.assertIn("bluelock_tiktok", nomes)
        # ...mas fora de CANAIS, que e o que a analise dos duelos compara.
        self.assertNotIn("bluelock", metricas.CANAIS)

    def test_marca_sem_a_serie_acende_atraso(self):
        # A coleta que nunca mediu a serie nao pode passar por "em dia".
        marca = {"dia": "dia-2026-10-26", "partes": {
            n: {"estado": "ok", "quando": "2026-10-26T07:20:00",
                "ultimo_ok": "2026-10-26T07:20:00"}
            for n in ("builds", "builds_tiktok", "historias", "historias_tiktok")}}
        atraso = metricas.coleta_atrasada(marca, datetime(2026, 10, 26, 10, 30))
        self.assertEqual(["bluelock", "bluelock_tiktok"], atraso["partes"])


class ContagensDoVideo(unittest.TestCase):

    def _resposta(self, ok=True, corpo=None, status=200):
        return mock.Mock(ok=ok, status_code=status, text="x",
                         json=lambda: corpo)

    def test_sem_linha_nao_e_zero(self):
        with mock.patch.object(metricas, "_get", return_value=self._resposta(
                corpo={"rows": [], "columnHeaders": []})):
            saida = metricas.contagens_do_video("abc", "t", "2026-10-26")
        self.assertIn("extras_erro", saida)
        self.assertNotIn("inscritos_ganhos", saida)

    def test_coluna_que_nao_veio_nao_vira_zero(self):
        corpo = {"columnHeaders": [{"name": "shares"}], "rows": [[3]]}
        with mock.patch.object(metricas, "_get",
                               return_value=self._resposta(corpo=corpo)):
            saida = metricas.contagens_do_video("abc", "t", "2026-10-26")
        self.assertEqual(3, saida["compartilhamentos"])
        self.assertNotIn("inscritos_ganhos", saida)

    def test_recusa_da_api_vira_erro_e_nao_levanta(self):
        with mock.patch.object(metricas, "_get", return_value=self._resposta(
                ok=False, status=403)):
            self.assertIn("403", metricas.contagens_do_video("a", "t", "d")["extras_erro"])

    def test_queda_de_rede_vira_erro_e_nao_levanta(self):
        with mock.patch.object(metricas, "_get", side_effect=OSError("sem rede")):
            self.assertIn("sem rede", metricas.contagens_do_video("a", "t", "d")["extras_erro"])

    def test_ficou_para_ver_e_derivado_e_sem_dado_e_none(self):
        self.assertEqual(0.5, metricas.ficou_para_ver(
            {"engaged_views": 5, "views_analytics": 10}))
        self.assertIsNone(metricas.ficou_para_ver({"views_analytics": 10}))
        self.assertIsNone(metricas.ficou_para_ver({"engaged_views": 5}))


class DepoisDaColetaDaSerie(_NaPasta):

    def test_falha_de_comentario_vira_linha_de_erro_e_nao_derruba(self):
        from builds import atividade
        diario = []
        with mock.patch.object(atividade, "registrar",
                               lambda *a, **k: diario.append((a, k))), \
                mock.patch.object(C, "ler_youtube", return_value={
                    "lidos": [], "novos": 0, "falhas": ["v: token morto"]}):
            metricas._depois_da_coleta_da_serie(
                [{"youtube_id": "v", "views": 3}], log=lambda *_a: None)
        (args, kw), = diario
        self.assertEqual("metricas", args[0])
        self.assertEqual(atividade.ERRO, args[1])
        self.assertIn("token morto", args[2])
        self.assertEqual("bluelock", kw["canal"])
        # ...e o historico gravou a leitura mesmo assim.
        self.assertEqual(1, len(S.carregar_leituras()))

    def test_excecao_inesperada_tambem_e_dita(self):
        from builds import atividade
        diario = []
        with mock.patch.object(atividade, "registrar",
                               lambda *a, **k: diario.append(a)), \
                mock.patch.object(C, "ler_youtube", side_effect=RuntimeError("x")):
            metricas._depois_da_coleta_da_serie([], log=lambda *_a: None)
        self.assertTrue(diario and "RuntimeError" in diario[0][2])


class ViewsNaIdade(unittest.TestCase):
    PUBLICADO = datetime(2026, 10, 26, 10, 22)

    def leitura(self, quando, views, plataforma="youtube", vid="v"):
        return {"quando": quando, "plataforma": plataforma,
                "videos": {vid: {"views": views, "medido_em": quando}}}

    def test_a_leitura_perto_das_24h_vale(self):
        leituras = [self.leitura("2026-10-26T21:00:00", 300),
                    self.leitura("2026-10-27T07:02:00", 410)]
        # 20,7 h depois do post: dentro de 24 +- 5.
        self.assertEqual((410, 20.7), S.views_na_idade(
            leituras, "youtube", "v", self.PUBLICADO))

    def test_sem_leitura_perto_e_ainda_nao_e_nao_zero(self):
        leituras = [self.leitura("2026-10-26T21:00:00", 300)]    # 10,6 h
        self.assertIsNone(S.views_na_idade(leituras, "youtube", "v", self.PUBLICADO))
        self.assertIsNone(S.views_na_idade([], "youtube", "v", self.PUBLICADO))

    def test_outra_plataforma_nao_conta(self):
        leituras = [self.leitura("2026-10-27T10:00:00", 99, plataforma="tiktok")]
        self.assertIsNone(S.views_na_idade(leituras, "youtube", "v", self.PUBLICADO))

    def test_sem_hora_de_publicacao_nao_chuta(self):
        leituras = [self.leitura("2026-10-27T10:00:00", 99)]
        self.assertIsNone(S.views_na_idade(leituras, "youtube", "v", None))


class OHistorico(_NaPasta):

    def test_lista_vazia_nao_grava_linha_nenhuma(self):
        self.assertIsNone(S.registrar_leitura("youtube", []))
        self.assertFalse(S.arquivo_das_leituras().exists())

    def test_campo_ausente_nao_vira_zero(self):
        S.registrar_leitura("youtube", [{"youtube_id": "v", "views": 5}],
                            datetime(2026, 10, 26, 21, 0))
        item = S.carregar_leituras()[0]["videos"]["v"]
        self.assertEqual(5, item["views"])
        self.assertNotIn("media_percentual", item)
        self.assertNotIn("inscritos_ganhos", item)


class OBlocoDoRelatorio(_NaPasta):
    AGORA = datetime(2026, 10, 27, 7, 30)

    def test_zero_episodio_nao_e_nota_boa(self):
        texto = "\n".join(S.linhas_do_relatorio(self.AGORA))
        self.assertIn("nenhum episódio publicado", texto)
        self.assertIn("NÃO é nota boa", texto)

    def test_episodio_sem_medida_diz_sem_medida(self):
        self.ledger(EP1_YT, EP1_TT)
        texto = "\n".join(S.linhas_do_relatorio(self.AGORA))
        self.assertIn("sem medida", texto)
        self.assertNotIn("0 views", texto)

    def test_youtube_sem_id_e_dito(self):
        self.ledger({**EP1_YT, "youtube_id": None})
        self.assertIn("SEM youtube_id",
                      "\n".join(S.linhas_do_relatorio(self.AGORA)))

    def test_rascunho_nao_e_episodio_no_ar(self):
        self.ledger({**EP1_YT, "publicado": False, "estado": "rascunho"})
        self.assertIn("nenhum episódio publicado",
                      "\n".join(S.linhas_do_relatorio(self.AGORA)))

    def test_episodio_cheio_traz_views_24h_e_assistido(self):
        self.ledger(EP1_YT)
        self.salvar_youtube("8RFvQp9VogE", views=410, likes=12, comentarios=2,
                            media_percentual=61.4, ficou_para_ver=0.7,
                            inscritos_ganhos=3, publicado_em="2026-10-26T13:22:00Z",
                            views_medidas_em="2026-10-27T07:20:00")
        S.registrar_leitura("youtube", [{"youtube_id": "8RFvQp9VogE", "views": 400,
                                         "views_medidas_em": "2026-10-27T07:05:00"}],
                            datetime(2026, 10, 27, 7, 5))
        texto = "\n".join(S.linhas_do_relatorio(self.AGORA))
        for trecho in ("410 views", "24 h: 400", "assistido 61%", "+3 inscr.",
                       "2 coment."):
            self.assertIn(trecho, texto)

    def test_numero_velho_vem_com_aviso(self):
        self.ledger(EP1_YT)
        self.salvar_youtube("8RFvQp9VogE", views=10, likes=0, comentarios=0,
                            views_medidas_em="2026-10-25T07:00:00")
        self.assertIn("número de há", "\n".join(S.linhas_do_relatorio(self.AGORA)))

    def test_ledger_ilegivel_nao_derruba_o_relatorio(self):
        with mock.patch.object(S, "episodios", side_effect=OSError("preso")):
            texto = "\n".join(S.linhas_do_relatorio(self.AGORA))
        self.assertIn("não consegui", texto)


class OsComentarios(_NaPasta):
    AGORA = datetime(2026, 10, 27, 21, 10)

    def test_guardar_conta_so_o_novo_e_ignora_vazio(self):
        dado = {"comentarios": {}, "leituras": {}}
        lista = [{"id": "a", "texto": "boa"}, {"id": "b", "texto": "  "},
                 {"id": None, "texto": "x"}]
        self.assertEqual(1, C.guardar(dado, "youtube", "v", lista, self.AGORA))
        self.assertEqual(0, C.guardar(dado, "youtube", "v", lista, self.AGORA))

    def test_resumo_sem_nenhuma_leitura_nao_diz_que_esta_tudo_bem(self):
        texto = C.resumo(self.AGORA)
        self.assertIn("nenhuma leitura", texto)
        self.assertNotIn("nenhum comentário novo", texto)

    def test_resumo_com_leitura_feita_e_zero_comentario(self):
        dado = C.carregar()
        C.registrar_leitura(dado, "youtube", "v", estado="ok", lidos=0, total=0,
                            via="contagem", agora=self.AGORA)
        C.gravar(dado)
        self.assertIn("nenhum comentário novo", C.resumo(self.AGORA))

    def test_contador_maior_que_o_lido_nao_e_leitura_completa(self):
        # O caso real de 26/10: o contador do YouTube dizia 1 e a pagina
        # publica mostrava 0 (retido para revisao, ou do proprio canal).
        dado = C.carregar()
        C.registrar_leitura(dado, "youtube", "v", estado="ok", lidos=0, total=1,
                            via="pagina", agora=self.AGORA)
        C.gravar(dado)
        texto = C.resumo(self.AGORA)
        self.assertIn("o contador do YouTube diz 1", texto)
        self.assertIn("nenhum comentário novo que eu consiga ler", texto)

    def test_leitura_que_falhou_diz_nao_consegui_ler(self):
        dado = C.carregar()
        C.registrar_leitura(dado, "youtube", "v", estado="erro", erro="token",
                            agora=self.AGORA)
        C.gravar(dado)
        texto = C.resumo(self.AGORA)
        self.assertIn("NÃO consegui ler", texto)
        self.assertNotIn("nenhum comentário novo", texto)

    def test_arquivo_ilegivel_nao_vira_sem_comentarios(self):
        (self.pasta / "_comentarios.json").write_text("{quebrado", encoding="utf-8")
        self.assertIn("NÃO consegui ler", C.resumo(self.AGORA))

    def test_novo_aparece_uma_vez_no_dia_e_some_no_dia_seguinte(self):
        dado = C.carregar()
        C.guardar(dado, "youtube", "v", [{"id": "c1", "autor": "@ana",
                                           "texto": "Ep. 2 quando?"}], self.AGORA)
        C.registrar_leitura(dado, "youtube", "v", estado="ok", lidos=1, total=1,
                            agora=self.AGORA)
        C.gravar(dado)
        primeiro = C.resumo(self.AGORA)
        self.assertIn("Ep. 2 quando?", primeiro)
        self.assertIn("@ana", primeiro)
        # Reenvio no mesmo dia (o envio falhou, ou o /comentarios): repete.
        self.assertIn("Ep. 2 quando?", C.resumo(self.AGORA.replace(minute=40)))
        # Dia seguinte: ja foi avisado ontem.
        amanha = C.resumo(datetime(2026, 10, 28, 21, 10))
        self.assertNotIn("Ep. 2 quando?", amanha)
        self.assertIn("nenhum comentário novo", amanha)


class LerOYoutube(_NaPasta):
    AGORA = datetime(2026, 10, 27, 7, 5)

    def _ler(self, comentarios, api, pagina):
        self.ledger(EP1_YT)
        with mock.patch.object(metricas, "estatisticas",
                               return_value={"8RFvQp9VogE": {"comentarios": comentarios}}):
            return C.ler_youtube("tok", agora=self.AGORA, log=lambda *_a: None,
                                 api=api, pagina_do_video=pagina)

    def test_contagem_zero_nao_abre_a_pagina(self):
        def pagina(_v):
            raise AssertionError("nao deveria abrir o Chrome")
        saida = self._ler(0, lambda *_a: (None, "x"), pagina)
        self.assertEqual(["8RFvQp9VogE"], saida["lidos"])
        self.assertEqual([], saida["falhas"])

    def test_sem_escopo_na_api_cai_na_pagina_publica(self):
        lista = [{"id": "lc1", "autor": "@x", "texto": "oi"}]
        saida = self._ler(1, lambda *_a: (None, "API 403: escopo"),
                          lambda _v: lista)
        self.assertEqual(1, saida["novos"])
        self.assertEqual("pagina", C.carregar()["leituras"]["youtube:8RFvQp9VogE"]["via"])

    def test_as_duas_vias_falham_e_isso_e_dito(self):
        def pagina(_v):
            raise RuntimeError("chrome")
        saida = self._ler(2, lambda *_a: (None, "API 403"), pagina)
        self.assertEqual(0, saida["novos"])
        self.assertTrue(saida["falhas"])
        self.assertIn("NÃO consegui ler", C.resumo(self.AGORA))

    def test_token_que_falha_vira_falha_e_nao_levanta(self):
        self.ledger(EP1_YT)
        with mock.patch.object(metricas, "_token", side_effect=RuntimeError("401")):
            saida = C.ler_youtube(agora=self.AGORA, log=lambda *_a: None)
        self.assertTrue(saida["falhas"])

    def test_sem_episodio_no_ledger_nao_chama_ninguem(self):
        saida = C.ler_youtube("tok", agora=self.AGORA, log=lambda *_a: None)
        self.assertEqual({"lidos": [], "novos": 0, "falhas": []}, saida)


class OTikTokComentarios(_NaPasta):
    AGORA = datetime(2026, 10, 27, 7, 5)

    def test_studio_que_nao_respondeu_e_erro_e_nao_zero(self):
        saida = C.guardar_do_tiktok([], agora=self.AGORA)
        self.assertTrue(saida["falhas"])
        self.assertIn("NÃO consegui ler", C.resumo(self.AGORA))

    def test_resposta_vazia_do_studio_e_leitura_boa_com_zero(self):
        # O corpo medido em 26/10: a conta ainda nao tinha comentario.
        saida = C.guardar_do_tiktok(
            [{"hasMore": False, "comments": [], "cursor": ""}], agora=self.AGORA)
        self.assertEqual({"novos": 0, "falhas": []}, saida)
        self.assertIn("nenhum comentário novo", C.resumo(self.AGORA))

    def test_comentario_com_nomes_provaveis_entra(self):
        corpo = {"comments": [{"cid": "9", "text": "foda", "aweme_id": "77",
                               "user": {"nickname": "bia"}, "digg_count": 2}]}
        self.assertEqual(1, C.guardar_do_tiktok([corpo], agora=self.AGORA)["novos"])
        self.assertIn("foda", C.resumo(self.AGORA))

    def test_comentario_sem_id_ou_texto_nao_entra(self):
        corpo = {"comments": [{"foo": 1}, {"cid": "1"}]}
        self.assertEqual(0, C.guardar_do_tiktok([corpo], agora=self.AGORA)["novos"])


if __name__ == "__main__":
    unittest.main()
