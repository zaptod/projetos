# -*- coding: utf-8 -*-
"""A conferencia que teria pego os 30 rascunhos em cinco dias.

Entre 10 e 15/09/2026, 29 videos entraram no ledger como publicados e
estavam como RASCUNHO no canal. Nenhum alarme disparou, porque auditoria,
gordura e meta leem o MESMO ledger que estava errado.

NENHUM caso aqui toca a rede: as duas listas sao injetadas, e ha um caso que
prova justamente isso.
"""
import unittest
from datetime import date

from builds.publicar import conferencia


HOJE = date(2026, 9, 16)

_ACEITOS_DE_VERDADE = None


def setUpModule():
    # HERMETICO: sem isto, todo `conferir` sem `aceitos=` leria a lista REAL
    # de rascunhos aceitos do runtime do Adrian, e o resultado do teste
    # passaria a depender do que foi aceito na maquina.
    global _ACEITOS_DE_VERDADE
    _ACEITOS_DE_VERDADE = conferencia.rascunhos_aceitos
    conferencia.rascunhos_aceitos = lambda: {}


def tearDownModule():
    conferencia.rascunhos_aceitos = _ACEITOS_DE_VERDADE


def _linha(video_id, titulo, *, quando="2026-09-16T09:40:02",
           youtube_id="", prova_ok=True, plataforma="youtube"):
    return {"video_id": video_id, "titulo": titulo, "quando": quando,
            "youtube_id": youtube_id, "prova_ok": prova_ok,
            "plataforma": plataforma, "url": "https://youtu.be/x"}


def _no_canal(vid, titulo, *, privacidade="public", definicao="hd",
              upload="processed"):
    return {"id": vid, "titulo": titulo, "privacidade": privacidade,
            "definicao": definicao, "upload": upload,
            "publicado_em": "2026-09-16T09:40:00Z"}


class OCasoDosRascunhos(unittest.TestCase):

    def test_video_privado_casado_vira_rascunho_e_suja_o_veredito(self):
        # A ASSINATURA EXATA do defeito de 15/09/2026: o ledger diz
        # publicado, o canal tem o video, e ele esta `private`.
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "O MAGO", youtube_id="aaa")],
            no_canal=[_no_canal("aaa", "O MAGO", privacidade="private")],
            hoje=HOJE)
        self.assertEqual(len(ficha["rascunhos"]), 1)
        self.assertEqual(ficha["rascunhos"][0]["youtube_id"], "aaa")
        self.assertEqual(ficha["veredito"], "sujo")

    def test_ledger_afirma_e_o_canal_nao_tem(self):
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "O MAGO"), _linha("g2", "O LADINO")],
            no_canal=[_no_canal("aaa", "O MAGO")],
            hoje=HOJE)
        self.assertEqual([f["video_id"] for f in ficha["fantasmas"]], ["g2"])
        self.assertEqual(ficha["veredito"], "sujo")

    def test_video_no_canal_sem_linha_no_ledger(self):
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "O MAGO", youtube_id="aaa")],
            no_canal=[_no_canal("aaa", "O MAGO"), _no_canal("bbb", "SOZINHO")],
            hoje=HOJE)
        self.assertEqual([o["youtube_id"] for o in ficha["orfaos"]], ["bbb"])

    def test_tudo_casado_e_limpo(self):
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "O MAGO", youtube_id="aaa")],
            no_canal=[_no_canal("aaa", "O MAGO")], hoje=HOJE)
        self.assertEqual(ficha["veredito"], "limpo")
        self.assertEqual(ficha["taxa"], 1.0)


class OQueNaoPodeAcender(unittest.TestCase):

    def test_so_sd_nao_suja_sozinho(self):
        # `definition` reflete a melhor renderizacao ja disponivel e demora a
        # virar "hd". Fosse veredito, a conferencia acenderia todo dia por
        # algo que se resolve sozinho — e alarme que sempre acende e alarme
        # que ninguem le.
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "O MAGO", youtube_id="aaa")],
            no_canal=[_no_canal("aaa", "O MAGO", definicao="sd")],
            hoje=HOJE)
        self.assertEqual(len(ficha["so_sd"]), 1)
        self.assertEqual(ficha["veredito"], "limpo")

    def test_o_acervo_antigo_fica_fora_da_janela(self):
        # Sem isto, a primeira noite acenderia para todo o historico, que nao
        # tem laudo nem id.
        ficha = conferencia.conferir(
            publicados=[_linha("velho", "DE AGOSTO",
                               quando="2026-08-01T10:00:00")],
            no_canal=[], dias=3, hoje=HOJE)
        self.assertEqual(ficha["no_ledger"], 0)
        self.assertEqual(ficha["veredito"], "limpo")

    def test_a_outra_plataforma_nao_entra_na_conta(self):
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "O MAGO", plataforma="tiktok")],
            no_canal=[], hoje=HOJE)
        self.assertEqual(ficha["no_ledger"], 0)


class OCasamento(unittest.TestCase):

    def test_casa_por_id_quando_existe(self):
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "TITULO QUE MUDOU", youtube_id="aaa")],
            no_canal=[_no_canal("aaa", "TITULO ORIGINAL")], hoje=HOJE)
        self.assertEqual(ficha["casados"], 1)
        self.assertEqual(ficha["fantasmas"], [])

    def test_cai_para_o_titulo_quando_nao_ha_id(self):
        # O acervo anterior a 16/09/2026 nao tem id no ledger; sem esta queda
        # ele inteiro viraria fantasma.
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "O MAGO 🔥", youtube_id="")],
            no_canal=[_no_canal("aaa", "o mago")], hoje=HOJE)
        self.assertEqual(ficha["casados"], 1)

    def test_acha_o_mesmo_titulo_duas_vezes_no_canal(self):
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "O MAGO", youtube_id="aaa")],
            no_canal=[_no_canal("aaa", "O MAGO"), _no_canal("bbb", "O MAGO")],
            hoje=HOJE)
        self.assertEqual(len(ficha["duplicados"]), 1)
        self.assertEqual(sorted(ficha["duplicados"][0]["ids"]), ["aaa", "bbb"])


class NadaDeRede(unittest.TestCase):

    def test_com_as_listas_injetadas_ninguem_chama_a_rede(self):
        chamou = []
        real = conferencia.buscar_no_canal
        conferencia.buscar_no_canal = lambda *a, **k: chamou.append(1) or []
        self.addCleanup(
            lambda: setattr(conferencia, "buscar_no_canal", real))
        conferencia.conferir(publicados=[], no_canal=[], hoje=HOJE)
        self.assertEqual(chamou, [])

    def test_o_tiktok_diz_por_onde_e_em_vez_de_mentir(self):
        with self.assertRaises(ValueError) as erro:
            conferencia.buscar_no_canal("builds", "tiktok")
        self.assertIn("Studio", str(erro.exception))


class SoDentroDaJanela(unittest.TestCase):
    """Primeira rodada real: 98 "orfaos" que eram so os videos antigos."""

    def test_video_antigo_nao_vira_orfao(self):
        antigo = _no_canal("velho", "DE AGOSTO")
        antigo["publicado_em"] = "2026-08-01T10:00:00Z"
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "O MAGO", youtube_id="aaa")],
            no_canal=[_no_canal("aaa", "O MAGO"), antigo], hoje=HOJE)
        self.assertEqual([], ficha["orfaos"])
        self.assertEqual(1, ficha["no_canal_na_janela"])

    def test_video_sem_data_nao_vira_orfao(self):
        sem_data = _no_canal("x", "SEM DATA")
        sem_data["publicado_em"] = None
        ficha = conferencia.conferir(publicados=[], no_canal=[sem_data],
                                     hoje=HOJE)
        self.assertEqual([], ficha["orfaos"])

    def test_novo_com_titulo_de_um_antigo_e_duplicado(self):
        # O caso que restringir OS DOIS a janela esconderia.
        antigo = _no_canal("velho", "O MAGO")
        antigo["publicado_em"] = "2026-08-01T10:00:00Z"
        ficha = conferencia.conferir(
            publicados=[], no_canal=[antigo, _no_canal("novo", "O MAGO")],
            hoje=HOJE)
        self.assertEqual(1, len(ficha["duplicados"]))

    def test_dois_antigos_iguais_nao_entram(self):
        a, b = _no_canal("a1", "O MAGO"), _no_canal("a2", "O MAGO")
        a["publicado_em"] = b["publicado_em"] = "2026-08-01T10:00:00Z"
        ficha = conferencia.conferir(publicados=[], no_canal=[a, b],
                                     hoje=HOJE)
        self.assertEqual([], ficha["duplicados"])


class RascunhosAceitos(unittest.TestCase):
    """Decisao do Adrian em 15/09/2026: os rascunhos ficam de gordura."""

    ACEITOS = {"aaa": {"motivo": "gordura"}}

    def test_aceito_aparece_mas_nao_suja(self):
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "O MAGO", youtube_id="aaa")],
            no_canal=[_no_canal("aaa", "O MAGO", privacidade="private")],
            hoje=HOJE, aceitos=self.ACEITOS)
        self.assertEqual([], ficha["rascunhos"])
        self.assertEqual(["aaa"],
                         [r["youtube_id"] for r in ficha["rascunhos_aceitos"]])
        self.assertEqual("limpo", ficha["veredito"])

    def test_rascunho_novo_fora_da_lista_continua_sujando(self):
        # Sem isto a lista viraria uma forma de calar o proximo defeito.
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "O MAGO", youtube_id="aaa"),
                        _linha("g2", "O LADINO", youtube_id="bbb")],
            no_canal=[_no_canal("aaa", "O MAGO", privacidade="private"),
                      _no_canal("bbb", "O LADINO", privacidade="private")],
            hoje=HOJE, aceitos=self.ACEITOS)
        self.assertEqual(["bbb"],
                         [r["youtube_id"] for r in ficha["rascunhos"]])
        self.assertEqual("sujo", ficha["veredito"])

    def test_aceito_que_virou_publico_sai_sozinho(self):
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "O MAGO", youtube_id="aaa")],
            no_canal=[_no_canal("aaa", "O MAGO", privacidade="public")],
            hoje=HOJE, aceitos=self.ACEITOS)
        self.assertEqual([], ficha["rascunhos"])
        self.assertEqual([], ficha["rascunhos_aceitos"])


class OrfaoPrivado(unittest.TestCase):
    """Video privado no canal, sem linha no ledger: upload que ninguem
    registrou e que nao foi ao ar. Na primeira rodada real havia 10, e a
    conferencia disse "limpo" porque orfao nunca sujava."""

    def _ficha(self, privacidade, aceitos=None):
        return conferencia.conferir(
            publicados=[_linha("g1", "O MAGO", youtube_id="aaa")],
            no_canal=[_no_canal("aaa", "O MAGO"),
                      _no_canal("zzz", "TESTE DA MADRUGADA",
                                privacidade=privacidade)],
            hoje=HOJE, aceitos=aceitos or {})

    def test_orfao_privado_suja(self):
        ficha = self._ficha("private")
        self.assertEqual(["zzz"],
                         [o["youtube_id"] for o in ficha["orfaos_privados"]])
        self.assertEqual("sujo", ficha["veredito"])

    def test_orfao_publico_nao_suja(self):
        # Video no ar sem linha e dado faltando, nao defeito de publicacao.
        ficha = self._ficha("public")
        self.assertEqual([], ficha["orfaos_privados"])
        self.assertEqual(1, len(ficha["orfaos"]))
        self.assertEqual("limpo", ficha["veredito"])

    def test_orfao_privado_aceito_nao_suja(self):
        # Os 8 testes da madrugada de 16/09, explicados pelo Adrian.
        ficha = self._ficha("private", aceitos={"zzz": {"motivo": "teste"}})
        self.assertEqual([], ficha["orfaos_privados"])
        self.assertEqual(["zzz"], [o["youtube_id"]
                                   for o in ficha["orfaos_privados_aceitos"]])
        self.assertEqual("limpo", ficha["veredito"])

    def test_orfao_privado_antigo_fora_da_janela_nao_suja(self):
        velho = _no_canal("zzz", "ANTIGO", privacidade="private")
        velho["publicado_em"] = "2026-08-01T10:00:00Z"
        ficha = conferencia.conferir(publicados=[], no_canal=[velho],
                                     hoje=HOJE, aceitos={})
        self.assertEqual("limpo", ficha["veredito"])


class AListaDeAceitos(unittest.TestCase):

    def setUp(self):
        import tempfile
        from pathlib import Path
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        arquivo = Path(self._tmp.name) / "rascunhos_aceitos.json"
        real = conferencia.arquivo_de_aceitos
        conferencia.arquivo_de_aceitos = lambda: arquivo
        self.addCleanup(
            lambda: setattr(conferencia, "arquivo_de_aceitos", real))
        # O modulo inteiro troca `rascunhos_aceitos` por um vazio; aqui se
        # testa a de verdade, contra o arquivo descartavel.
        conferencia.rascunhos_aceitos = _ACEITOS_DE_VERDADE
        self.addCleanup(lambda: setattr(conferencia, "rascunhos_aceitos",
                                        lambda: {}))

    def _ficha(self, *ids):
        return {"canal": "builds", "rascunhos": [
            {"youtube_id": i, "video_id": f"g-{i}", "titulo": i,
             "quando": "2026-09-13T06:09:34"} for i in ids]}

    def test_grava_com_motivo_e_le_de_volta(self):
        conferencia.aceitar_rascunhos(self._ficha("aaa", "bbb"))
        lidos = conferencia.rascunhos_aceitos()
        self.assertEqual({"aaa", "bbb"}, set(lidos))
        self.assertIn("15/09/2026", lidos["aaa"]["motivo"])
        self.assertEqual("g-aaa", lidos["aaa"]["video_id"])

    def test_soma_e_nunca_apaga(self):
        conferencia.aceitar_rascunhos(self._ficha("aaa"))
        conferencia.aceitar_rascunhos(self._ficha("bbb"))
        self.assertEqual({"aaa", "bbb"}, set(conferencia.rascunhos_aceitos()))

    def test_aceitar_orfao_guarda_o_motivo_proprio(self):
        conferencia.aceitar_rascunhos(self._ficha("aaa"))
        conferencia.aceitar(
            [{"youtube_id": "zzz", "titulo": "final celular",
              "publicado_em": "2026-09-16T03:50:00Z"}],
            "testes do conserto do rascunho, 16/09 madrugada")
        lidos = conferencia.rascunhos_aceitos()
        self.assertIn("15/09/2026", lidos["aaa"]["motivo"])
        self.assertIn("testes do conserto", lidos["zzz"]["motivo"])
        self.assertEqual("2026-09-16T03:50:00Z", lidos["zzz"]["publicado_em"])

    def test_aceito_mantem_o_motivo_original(self):
        conferencia.aceitar([{"youtube_id": "aaa"}], "primeiro")
        conferencia.aceitar([{"youtube_id": "aaa"}], "segundo")
        self.assertEqual("primeiro",
                         conferencia.rascunhos_aceitos()["aaa"]["motivo"])

    def test_le_o_formato_antigo_com_motivo_no_topo(self):
        # O arquivo gravado na primeira rodada (7a3941d) tinha "motivo" no
        # topo; o leitor so olha "ids".
        conferencia.arquivo_de_aceitos().write_text(
            '{"motivo": "x", "ids": {"aaa": {"motivo": "x"}}}',
            encoding="utf-8")
        self.assertEqual({"aaa"}, set(conferencia.rascunhos_aceitos()))

    def test_arquivo_ausente_ou_torto_e_lista_vazia(self):
        self.assertEqual({}, conferencia.rascunhos_aceitos())
        conferencia.arquivo_de_aceitos().write_text("nao e json",
                                                    encoding="utf-8")
        self.assertEqual({}, conferencia.rascunhos_aceitos())

    def test_a_madrugada_nunca_aceita_sozinha(self):
        # Se `conferir_tudo` aceitasse, todo rascunho novo seria calado na
        # mesma noite em que aparecesse.
        chamou = []
        real_ac, real_conf, real_salvar = (conferencia.aceitar_rascunhos,
                                           conferencia.conferir,
                                           conferencia.salvar)
        conferencia.aceitar_rascunhos = lambda *a, **k: chamou.append(1)
        conferencia.conferir = lambda *a, **k: dict(
            self._ficha("zzz"), plataforma="youtube", veredito="sujo",
            fantasmas=[], orfaos=[], casados=1, no_ledger=1, janela_dias=3)
        conferencia.salvar = lambda f: None
        self.addCleanup(lambda: setattr(conferencia, "aceitar_rascunhos",
                                        real_ac))
        self.addCleanup(lambda: setattr(conferencia, "conferir", real_conf))
        self.addCleanup(lambda: setattr(conferencia, "salvar", real_salvar))
        from builds import atividade
        real_reg = atividade.registrar
        atividade.registrar = lambda *a, **k: None
        self.addCleanup(lambda: setattr(atividade, "registrar", real_reg))
        conferencia.conferir_tudo(("builds",), log=lambda _t: None)
        self.assertEqual([], chamou)


class MesmoVideoEmDuasLinhas(unittest.TestCase):

    def test_duas_linhas_com_o_mesmo_id_viram_achado(self):
        # O caso real: I9ETJSGR1A0 as 07:08 e as 08:08 de 15/09/2026.
        ficha = conferencia.conferir(
            publicados=[
                _linha("g1", "ERIK", youtube_id="I9ETJSGR1A0",
                       quando="2026-09-15T07:08:48"),
                _linha("g1", "ERIK", youtube_id="I9ETJSGR1A0",
                       quando="2026-09-15T08:08:48"),
                _linha("g2", "OUTRO", youtube_id="ccc")],
            no_canal=[_no_canal("I9ETJSGR1A0", "ERIK"),
                      _no_canal("ccc", "OUTRO")], hoje=HOJE)
        (grupo,) = ficha["mesmo_video"]
        self.assertEqual("I9ETJSGR1A0", grupo["youtube_id"])
        self.assertEqual(2, len(grupo["linhas"]))

    def test_e_achado_e_nao_suja_sozinho(self):
        ficha = conferencia.conferir(
            publicados=[_linha("g1", "X", youtube_id="aaa"),
                        _linha("g1", "X", youtube_id="aaa",
                               quando="2026-09-16T10:00:00")],
            no_canal=[_no_canal("aaa", "X")], hoje=HOJE)
        self.assertEqual(1, len(ficha["mesmo_video"]))
        self.assertEqual("limpo", ficha["veredito"])


class ABuscaDeVerdade(unittest.TestCase):
    """`buscar_no_canal` com a rede dublada UM NIVEL ABAIXO.

    Ate 16/09/2026 nenhum caso passava por esta funcao — todos injetavam as
    listas prontas. Foi assim que `token = _token(canal)` mandou a TUPLA
    `(token, credenciais)` como token: o Google respondeu 401, o 401 virou
    "token revogado", e o diagnostico errado chegou ao Adrian.
    """

    def _dublar(self, *, enviados, detalhes):
        from builds.publicar import metricas
        visto = {}
        reais = (metricas._token, metricas.enviados, metricas.estatisticas)

        def enviados_falso(token, quantos=200):
            visto["token_enviados"] = token
            return enviados

        def estatisticas_falsa(ids, token):
            visto["token_estatisticas"] = token
            visto["ids"] = list(ids)
            return detalhes

        metricas._token = lambda canal="builds": ("TOKEN-DE-VERDADE",
                                                  object())
        metricas.enviados = enviados_falso
        metricas.estatisticas = estatisticas_falsa

        def restaurar():
            (metricas._token, metricas.enviados,
             metricas.estatisticas) = reais

        self.addCleanup(restaurar)
        return visto

    def test_o_token_vai_como_texto_e_nao_como_tupla(self):
        visto = self._dublar(enviados=[{"youtube_id": "aaa",
                                        "titulo": "O MAGO"}],
                             detalhes={"aaa": {"privacidade": "public"}})
        conferencia.buscar_no_canal("builds")
        self.assertEqual("TOKEN-DE-VERDADE", visto["token_enviados"])
        self.assertEqual("TOKEN-DE-VERDADE", visto["token_estatisticas"])

    def test_junta_a_lista_do_canal_com_os_detalhes(self):
        self._dublar(
            enviados=[{"youtube_id": "aaa", "titulo": "O MAGO",
                       "publicado_em": "2026-09-16T09:40:00Z"}],
            detalhes={"aaa": {"privacidade": "private", "definicao": "sd",
                              "upload": "processed"}})
        (video,) = conferencia.buscar_no_canal("builds")
        self.assertEqual("aaa", video["id"])
        self.assertEqual("O MAGO", video["titulo"])
        self.assertEqual("private", video["privacidade"])

    def test_video_que_a_api_nao_detalhou_continua_na_lista(self):
        # Sem detalhe nao da para dizer se e rascunho — mas sumir com ele
        # faria a linha do ledger virar fantasma sem ser.
        self._dublar(enviados=[{"youtube_id": "bbb", "titulo": "X"}],
                     detalhes={})
        (video,) = conferencia.buscar_no_canal("builds")
        self.assertEqual("bbb", video["id"])
        self.assertNotIn("privacidade", video)

    def test_canal_vazio_nao_pede_detalhe(self):
        visto = self._dublar(enviados=[], detalhes={})
        self.assertEqual([], conferencia.buscar_no_canal("builds"))
        self.assertNotIn("ids", visto)


class OAlarme(unittest.TestCase):
    """O alarme e uma linha de erro no diario — nada de Telegram proprio."""

    def _rodar(self, ficha):
        avisos = []
        from builds import atividade
        real_conf, real_salvar = conferencia.conferir, conferencia.salvar
        real_reg = atividade.registrar
        conferencia.conferir = lambda *a, **k: ficha
        conferencia.salvar = lambda f: None
        atividade.registrar = lambda *a, **k: avisos.append((a, k))
        self.addCleanup(lambda: setattr(conferencia, "conferir", real_conf))
        self.addCleanup(lambda: setattr(conferencia, "salvar", real_salvar))
        self.addCleanup(lambda: setattr(atividade, "registrar", real_reg))
        conferencia.conferir_tudo(("builds",), log=lambda _t: None)
        return avisos

    def test_sujo_acende(self):
        avisos = self._rodar({
            "canal": "builds", "plataforma": "youtube", "veredito": "sujo",
            "fantasmas": [{}], "rascunhos": [], "orfaos": [], "casados": 0,
            "no_ledger": 1, "janela_dias": 3})
        self.assertEqual(len(avisos), 1)

    def test_o_alarme_tem_fabrica_propria(self):
        # Com "publicacao", o apurador tratava achado de dados como defeito
        # de codigo e abria um conserto (16/09/2026). O outro lado — o
        # apurador ignorar esta fabrica — e testado em remoto/test_remoto.py:
        # `builds` nao pode importar `remoto`.
        avisos = self._rodar({
            "canal": "builds", "plataforma": "youtube", "veredito": "sujo",
            "fantasmas": [], "rascunhos": [{}], "orfaos": [], "casados": 1,
            "no_ledger": 1, "janela_dias": 3})
        (args, _kw), = avisos
        self.assertEqual("conferencia", args[0])

    def test_falha_tambem_vai_para_disco(self):
        # 16/09/2026: com os tres tokens revogados a pagina dizia "nunca
        # rodou", porque a falha nao era gravada. Sao acoes diferentes.
        salvos = []
        real_conf, real_salvar = conferencia.conferir, conferencia.salvar

        def explode(*_a, **_k):
            raise RuntimeError("token invalido ou revogado")

        conferencia.conferir = explode
        conferencia.salvar = salvos.append
        self.addCleanup(lambda: setattr(conferencia, "conferir", real_conf))
        self.addCleanup(lambda: setattr(conferencia, "salvar", real_salvar))
        fichas = conferencia.conferir_tudo(("builds",), log=lambda _t: None)
        self.assertIn("revogado", fichas["builds"]["erro"])
        self.assertEqual(len(salvos), 1)
        self.assertTrue(salvos[0]["dia"])

    def test_limpo_NAO_acende(self):
        # Alarme que sempre acende e alarme que ninguem le.
        avisos = self._rodar({
            "canal": "builds", "plataforma": "youtube", "veredito": "limpo",
            "fantasmas": [], "rascunhos": [], "orfaos": [], "casados": 1,
            "no_ledger": 1, "janela_dias": 3})
        self.assertEqual(avisos, [])


if __name__ == "__main__":
    unittest.main()
