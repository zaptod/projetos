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

    def test_limpo_NAO_acende(self):
        # Alarme que sempre acende e alarme que ninguem le.
        avisos = self._rodar({
            "canal": "builds", "plataforma": "youtube", "veredito": "limpo",
            "fantasmas": [], "rascunhos": [], "orfaos": [], "casados": 1,
            "no_ledger": 1, "janela_dias": 3})
        self.assertEqual(avisos, [])


if __name__ == "__main__":
    unittest.main()
