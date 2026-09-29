# -*- coding: utf-8 -*-
"""A conferencia via so a playlist de envios, e ela nao traz todos os Shorts.

MEDIDO EM 28/09/2026 as 21:55, com o codigo em uso, canal de builds:

    `statistics.videoCount` (publicos que o canal declara)   151
    a lista da conferencia (so a `UU`)   178 linhas, 143 ids, 125 publicos
    a uniao `UU` + `UUSH` (a da recuperacao, 6fa9ad6)   170 ids, 149 publicos

Vinte e seis publicos invisiveis para `metricas.enviados`, para a
conferencia ledger x canal e para a reconciliacao — e nenhum deles dizia
isso. Uma lista curta vira "fantasma" (o ledger afirma e o canal nao tem)
sem prova nenhuma, e um veredito calculado sobre ela e um palpite.

O conserto: `enviados` le a UNIAO pela mesma funcao da recuperacao
(`recuperar._ids_do_canal`), a lista leva quantos publicos o canal declara,
e `conferir_lista` diz se ela veio inteira. Lista curta PARA o veredito do
ledger (`incompleta`, que nao e `limpo`) e acende um alarme por noite.

A uniao ainda deu curta no canal de builds (149 de 151): V61uLqU_PfI,
publico desde 31/08, nao esta em nenhuma das duas listas. Por isso o alarme
nasce aceso — e o que ele tem de fazer.
"""
from __future__ import annotations

import unittest
from datetime import datetime

from builds.publicar import conferencia, metricas

AS_0520 = datetime(2026, 9, 28, 5, 20)


class _Resposta:
    def __init__(self, dados, status=200):
        self._dados, self.status_code = dados, status
        self.ok = status < 400
        self.text = str(dados)

    def json(self):
        return self._dados


class _Canal:
    """O YouTube falso, respondendo `requests.get` pelas URLs de verdade.

    `uu`/`uush`: ids de cada playlist (`uush=None` = 404, canal sem Shorts).
    `videos`: {id: privacidade}. `declarados`: `statistics.videoCount`
    (`None` = o canal nao mandou o campo). `sem_canal`: credencial sem canal.
    """

    def __init__(self, *, uu=(), uush=(), videos=None, declarados=0,
                 sem_canal=False):
        self.uu, self.uush = list(uu), None if uush is None else list(uush)
        self.videos = dict(videos or {})
        self.declarados, self.sem_canal = declarados, sem_canal
        self.pedidos = []

    def __call__(self, url, params=None, headers=None, timeout=None, **_k):
        params = dict(params or {})
        caminho = url.rstrip("/").rsplit("/", 1)[-1]
        self.pedidos.append(caminho)
        if caminho == "channels":
            if self.sem_canal:
                return _Resposta({"items": []})
            canal = {"id": "UCx", "snippet": {"title": "canal"},
                     "contentDetails": {"relatedPlaylists":
                                        {"uploads": "UUabc"}}}
            if self.declarados is not None:
                canal["statistics"] = {"videoCount": str(self.declarados)}
            return _Resposta({"items": [canal]})
        if caminho == "playlistItems":
            lista = params["playlistId"]
            if lista == "UUSHabc" and self.uush is None:
                return _Resposta({"error": "not found"}, status=404)
            ids = self.uu if lista == "UUabc" else self.uush
            return _Resposta({"items": [{"contentDetails": {"videoId": i}}
                                        for i in ids]})
        if caminho == "videos":
            return _Resposta({"items": [
                {"id": i, "snippet": {"title": f"titulo {i}",
                                      "publishedAt": "2026-09-27T12:00:00Z"},
                 "status": {"privacyStatus": self.videos[i]}}
                for i in params["id"].split(",") if i in self.videos]})
        raise AssertionError(caminho)


class _ComCanalFalso(unittest.TestCase):

    def _canal(self, **k) -> _Canal:
        import requests
        canal = _Canal(**k)
        real = requests.get
        requests.get = canal
        self.addCleanup(setattr, requests, "get", real)
        return canal


class AUniaoDasListas(_ComCanalFalso):

    def test_o_short_que_so_a_uush_tem_entra_na_lista(self):
        self._canal(uu=["priv", "pubA"], uush=["pubA", "pubB"],
                    videos={"priv": "private", "pubA": "public",
                            "pubB": "public"}, declarados=2)
        lista = metricas.enviados("tok")
        self.assertEqual(["priv", "pubA", "pubB"],
                         sorted(v["youtube_id"] for v in lista))
        self.assertEqual({"videos": 3, "publicos": 2, "declarados": 2,
                          "completa": True, "motivo": ""},
                         metricas.conferir_lista(lista))

    def test_cada_video_uma_vez_so(self):
        # A leitura antiga devolvia 178 linhas para 143 ids no canal real.
        self._canal(uu=["a", "b"], uush=["b", "a"],
                    videos={"a": "public", "b": "public"}, declarados=2)
        self.assertEqual(2, len(metricas.enviados("tok")))

    def test_os_campos_que_a_reconciliacao_usa(self):
        self._canal(uu=["a"], uush=[], videos={"a": "public"}, declarados=1)
        (video,) = metricas.enviados("tok")
        self.assertEqual({"youtube_id": "a", "titulo": "titulo a",
                          "publicado_em": "2026-09-27T12:00:00Z",
                          "privacidade": "public"}, video)

    def test_nao_ha_mais_teto_de_200(self):
        # O canal de historias ja tem 195: o teto antigo ia corta-lo calado.
        ids = [f"v{n:03d}" for n in range(230)]
        self._canal(uu=ids, uush=[], videos={i: "public" for i in ids},
                    declarados=230)
        lista = metricas.enviados("tok")
        self.assertEqual(230, len(lista))
        self.assertTrue(metricas.conferir_lista(lista)["completa"])

    def test_quantos_corta_e_a_lista_da_curta(self):
        ids = [f"v{n}" for n in range(5)]
        self._canal(uu=ids, uush=[], videos={i: "public" for i in ids},
                    declarados=5)
        conferida = metricas.conferir_lista(metricas.enviados("tok", 3))
        self.assertFalse(conferida["completa"])

    def test_as_chamadas_proprias_sao_contadas(self):
        self._canal(uu=["a"], uush=[], videos={"a": "public"}, declarados=1)
        antes = dict(metricas.CHAMADAS)
        metricas.enviados("tok")
        # `channels` + um lote de `videos` + as paginas da playlist, que
        # passam por `recuperar._get` e contam la desde 28/09/2026: a `UU`
        # le 2 passadas (a 2a nao acrescenta nada e para) e a `UUSH` vazia
        # tambem 2 — 1 + 1 + 4 = 6. Antes dava 2, e a cota ficava por baixo.
        self.assertEqual(6, metricas.CHAMADAS["data"] - antes["data"])


class AListaCurta(_ComCanalFalso):

    def test_lista_com_publico_faltando_e_curta(self):
        self._canal(uu=["pubA"], uush=None, videos={"pubA": "public"},
                    declarados=2)
        conferida = metricas.conferir_lista(metricas.enviados("tok"))
        self.assertFalse(conferida["completa"])
        self.assertEqual((1, 2), (conferida["publicos"],
                                  conferida["declarados"]))
        self.assertIn("1 publicos e o canal declara 2", conferida["motivo"])

    def test_privado_nao_completa_a_conta_de_publicos(self):
        self._canal(uu=["a", "b"], uush=[],
                    videos={"a": "public", "b": "private"}, declarados=2)
        self.assertFalse(
            metricas.conferir_lista(metricas.enviados("tok"))["completa"])

    def test_canal_que_nao_diz_quantos_nunca_e_inteiro(self):
        self._canal(uu=["a"], uush=[], videos={"a": "public"},
                    declarados=None)
        conferida = metricas.conferir_lista(metricas.enviados("tok"))
        self.assertFalse(conferida["completa"])
        self.assertEqual(-1, conferida["declarados"])

    def test_credencial_sem_canal_nao_e_lista_vazia_inteira(self):
        self._canal(sem_canal=True)
        lista = metricas.enviados("tok")
        self.assertEqual([], list(lista))
        self.assertFalse(metricas.conferir_lista(lista)["completa"])

    def test_duble_sem_declarados_nao_tem_o_que_conferir(self):
        self.assertIsNone(metricas.conferir_lista([{"youtube_id": "a"}]))


class OCasoZero(_ComCanalFalso):

    def test_canal_vazio_que_declara_zero_e_lista_inteira(self):
        self._canal(uu=[], uush=None, declarados=0)
        lista = metricas.enviados("tok")
        self.assertEqual([], list(lista))
        self.assertTrue(metricas.conferir_lista(lista)["completa"])

    def test_zero_na_conferencia_nao_e_nota_boa(self):
        """Canal vazio e ledger vazio: ledger coerente, grade toda em falta."""
        vazio = metricas.ListaDoCanal()
        vazio.declarados = 0
        ficha = conferencia.conferir("builds", publicados=[], no_canal=vazio,
                                     agora=AS_0520, aceitos={})
        self.assertEqual("limpo", ficha["veredito"])
        self.assertEqual(ficha["slots_da_grade"], ficha["deficit"])
        self.assertEqual("em falta", ficha["grade"])

    def test_zero_com_lista_curta_nao_e_limpo(self):
        vazio = metricas.ListaDoCanal()
        vazio.declarados = 3
        ficha = conferencia.conferir("builds", publicados=[], no_canal=vazio,
                                     agora=AS_0520, aceitos={})
        self.assertEqual("incompleta", ficha["veredito"])


def _linha(n, quando="2026-09-27T09:39:00"):
    return {"plataforma": "youtube", "video_id": f"v{n}",
            "titulo": f"titulo {n}", "youtube_id": f"y{n}", "quando": quando}


def _no_canal(videos, declarados):
    lista = metricas.ListaDoCanal()
    lista.declarados = declarados
    lista.extend({"id": vid, "titulo": f"titulo {vid[1:]}",
                  "publicado_em": "2026-09-27T12:41:00Z",
                  "privacidade": privacidade}
                 for vid, privacidade in videos)
    return lista


class OVereditoParaComAListaCurta(unittest.TestCase):

    def _conferir(self, publicados, no_canal):
        return conferencia.conferir("builds", publicados=publicados,
                                    no_canal=no_canal, agora=AS_0520,
                                    aceitos={})

    def test_fantasma_com_lista_curta_nao_suja_nem_limpa(self):
        # y2 nao veio na lista, mas o canal declara 2 publicos: o "fantasma"
        # pode ser so o video que a lista perdeu.
        ficha = self._conferir([_linha(1), _linha(2)],
                               _no_canal([("y1", "public")], declarados=2))
        self.assertEqual(1, len(ficha["fantasmas"]))
        self.assertEqual("incompleta", ficha["veredito"])
        self.assertFalse(ficha["lista"]["completa"])

    def test_o_mesmo_fantasma_com_lista_inteira_suja(self):
        ficha = self._conferir([_linha(1), _linha(2)],
                               _no_canal([("y1", "public")], declarados=1))
        self.assertEqual("sujo", ficha["veredito"])
        self.assertTrue(ficha["lista"]["completa"])

    def test_rascunho_achado_suja_mesmo_com_lista_curta(self):
        ficha = self._conferir([_linha(1)],
                               _no_canal([("y1", "private")], declarados=4))
        self.assertEqual(1, len(ficha["rascunhos"]))
        self.assertEqual("sujo", ficha["veredito"])

    def test_lista_inteira_e_tudo_casado_e_limpo(self):
        ficha = self._conferir([_linha(1)],
                               _no_canal([("y1", "public")], declarados=1))
        self.assertEqual("limpo", ficha["veredito"])

    def test_a_grade_continua_sendo_contada(self):
        ficha = self._conferir([_linha(1)],
                               _no_canal([("y1", "public")], declarados=9))
        self.assertEqual("incompleta", ficha["veredito"])
        self.assertEqual(1, ficha["horarios_cumpridos"])
        self.assertIn("deficit", ficha)

    def test_lista_de_duble_segue_como_antes(self):
        ficha = self._conferir([_linha(1)], [{"id": "y1", "titulo": "titulo 1",
                                              "privacidade": "public"}])
        self.assertIsNone(ficha["lista"])
        self.assertEqual("limpo", ficha["veredito"])


class ABuscaLevaODeclarado(unittest.TestCase):

    def test_buscar_no_canal_nao_perde_o_declarado(self):
        lista = metricas.ListaDoCanal()
        lista.declarados = 7
        lista.append({"youtube_id": "a", "titulo": "A"})
        reais = (metricas._token, metricas.enviados, metricas.estatisticas)
        metricas._token = lambda canal="builds": ("tok", None)
        metricas.enviados = lambda token, quantos=None: lista
        metricas.estatisticas = lambda ids, token: {
            "a": {"privacidade": "public"}}
        self.addCleanup(lambda: setattr(metricas, "_token", reais[0]))
        self.addCleanup(lambda: setattr(metricas, "enviados", reais[1]))
        self.addCleanup(lambda: setattr(metricas, "estatisticas", reais[2]))
        achados = conferencia.buscar_no_canal("builds")
        self.assertEqual(7, achados.declarados)
        self.assertEqual({"videos": 1, "publicos": 1, "declarados": 7,
                          "completa": False,
                          "motivo": "a lista do canal trouxe 1 publicos e o "
                                    "canal declara 7"},
                         metricas.conferir_lista(achados))


class OAlarme(unittest.TestCase):
    """Lista curta vira linha de erro no diario, uma vez por noite."""

    def _rodar(self, no_canal, anterior=None):
        from builds import atividade
        from builds.publicar import sinais
        avisos = []
        reais = (metricas.publicados, conferencia.buscar_no_canal,
                 conferencia.salvar, atividade.registrar, conferencia.ultima,
                 sinais.ler_diario, conferencia.rascunhos_aceitos)
        metricas.publicados = lambda canal="builds": [_linha(1)]
        conferencia.buscar_no_canal = lambda *a, **k: no_canal
        conferencia.salvar = lambda f: None
        atividade.registrar = lambda *a, **k: avisos.append(a)
        conferencia.ultima = lambda canal="builds": dict(anterior or {})
        sinais.ler_diario = lambda caminho=None: []
        conferencia.rascunhos_aceitos = lambda: {}

        def restaurar():
            (metricas.publicados, conferencia.buscar_no_canal,
             conferencia.salvar, atividade.registrar, conferencia.ultima,
             sinais.ler_diario, conferencia.rascunhos_aceitos) = reais

        self.addCleanup(restaurar)
        ficha = conferencia.conferir_tudo(("builds",), log=lambda _t: None,
                                          agora=AS_0520)["builds"]
        return ficha, [a for a in avisos if "lista do canal" in a[2]]

    def test_lista_curta_acende_com_os_numeros(self):
        ficha, alarmes = self._rodar(_no_canal([("y1", "public")], 151))
        (alarme,) = alarmes
        self.assertEqual("conferencia", alarme[0])
        self.assertIn("1 publicos e o canal declara 151", alarme[2])
        self.assertEqual("1/151", ficha["avisos"]["noite"]["lista"])

    def test_a_segunda_rodada_da_noite_nao_repete(self):
        primeira, _ = self._rodar(_no_canal([("y1", "public")], 151))
        _, alarmes = self._rodar(_no_canal([("y1", "public")], 151),
                                 anterior=primeira)
        self.assertEqual([], alarmes)

    def test_lista_inteira_nao_acende(self):
        _, alarmes = self._rodar(_no_canal([("y1", "public")], 1))
        self.assertEqual([], alarmes)

    def test_a_linha_de_comando_nao_sai_com_zero(self):
        ficha, _ = self._rodar(_no_canal([("y1", "public")], 151))
        real = conferencia.conferir_tudo
        conferencia.conferir_tudo = lambda *a, **k: {"builds": ficha}
        self.addCleanup(setattr, conferencia, "conferir_tudo", real)
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as saida:
            codigo = conferencia.main(["--canal", "builds"])
        self.assertEqual(1, codigo)
        self.assertIn("LISTA DO CANAL INCOMPLETA", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
