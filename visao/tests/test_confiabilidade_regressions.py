# -*- coding: utf-8 -*-
"""A familia de confiabilidade: o que foi afirmado e o que da para provar.

Tudo e injetado — ledgers, diario e conferencias. Nenhum caso toca disco de
verdade, rede ou subprocesso, e ha um caso que prova isso, porque esta
familia entra no pulso de 3 s do painel.
"""
import subprocess
import unittest

from panorama import confiabilidade as C

DIA = "2026-09-16"


def _yt(video_id, *, hora="09:40", prova_ok=True, qualidade="hd",
        reconhecido=True, url="https://youtu.be/x", laudo=True):
    linha = {"quando": f"{DIA}T{hora}:00", "plataforma": "youtube",
             "video_id": video_id, "titulo": video_id, "url": url}
    if laudo:
        linha["prova_ok"] = prova_ok
        linha["prova"] = [{"qualidade_no_clique": qualidade,
                           "reconhecido": reconhecido}]
    return linha


def _tk(video_id, *, hora="09:41", dia=DIA):
    return {"quando": f"{dia}T{hora}:00", "plataforma": "tiktok",
            "video_id": video_id, "titulo": video_id,
            "url": "publicado no TikTok", "prova_ok": True,
            "prova": [{"confirmado": True}]}


def _limpo():
    return {"veredito": "limpo", "dia": DIA, "casados": 1, "no_ledger": 1,
            "fantasmas": [], "rascunhos": [], "orfaos": [], "so_sd": []}


def _retrato(builds=(), historias=(), eventos=(), conferencias=None):
    if conferencias is None:
        conferencias = {"builds": _limpo(), "historias": _limpo()}
    return C.hoje(DIA, builds=builds, historias=historias,
                  eventos=eventos, conferencias=conferencias)


class OQueFoiAfirmado(unittest.TestCase):

    def test_dia_limpo_e_ok_sem_alerta(self):
        ficha = _retrato(builds=[_yt("g1"), _tk("g1")])
        self.assertEqual(ficha["veredito"], "ok")
        self.assertEqual(ficha["alertas"], [])
        self.assertEqual((ficha["prometido"], ficha["provado"]), (2, 2))

    def test_linha_antiga_e_nao_sei_e_nao_sem_prova(self):
        # O TERCEIRO ESTADO. Linha anterior ao laudo conta em `sem_campo` e
        # NAO em `sem_prova`: se ausencia valesse reprovacao, o alarme
        # acenderia para o acervo inteiro e ninguem o olharia de novo.
        ficha = _retrato(builds=[_yt("g1", laudo=False), _tk("g1")])
        self.assertEqual(ficha["sem_campo"], 1)
        self.assertEqual(ficha["sem_prova"], 0)

    def test_publicacao_sem_prova_acende(self):
        ficha = _retrato(builds=[_yt("g1", prova_ok=False), _tk("g1")])
        self.assertEqual(ficha["sem_prova"], 1)
        self.assertEqual(ficha["veredito"], "atencao")

    def test_outro_dia_nao_entra(self):
        ontem = _yt("g0")
        ontem["quando"] = "2026-09-15T23:40:00"
        ficha = _retrato(builds=[ontem, _tk("g0", dia="2026-09-15")])
        self.assertEqual(ficha["prometido"], 0)

    def test_linha_sem_url_nao_foi_ao_ar(self):
        ficha = _retrato(builds=[_yt("g1", url="")])
        self.assertEqual(ficha["prometido"], 0)


class AQualidadeNoClique(unittest.TestCase):

    def test_conta_quem_foi_ao_ar_antes_do_processamento(self):
        ficha = _retrato(builds=[
            _yt("g1", qualidade="processando"), _tk("g1"),
            _yt("g2", qualidade="subindo"), _tk("g2"),
            _yt("g3", qualidade="hd"), _tk("g3"),
            # "desconhecida" NAO e fora de HD: e "nao sei".
            _yt("g4", qualidade="desconhecida", reconhecido=False), _tk("g4"),
        ])
        self.assertEqual(ficha["fora_de_hd"], 2)

    def test_a_barra_que_ninguem_entendeu_vira_alerta(self):
        # O ALARME PROMETIDO NA ETAPA 1: se o Studio mudar o texto da barra,
        # a medida inteira vira palpite, e so este contador avisa.
        ficha = _retrato(builds=[
            _yt("g1", qualidade="desconhecida", reconhecido=False), _tk("g1")])
        self.assertEqual(ficha["barra_nao_entendida"], 1)
        self.assertTrue(any("barra do Studio" in a for a in ficha["alertas"]))

    def test_linha_sem_laudo_nao_conta_como_barra_nao_entendida(self):
        ficha = _retrato(builds=[_yt("g1", laudo=False), _tk("g1")])
        self.assertEqual(ficha["barra_nao_entendida"], 0)


class OEstadoGanhaDoEvento(unittest.TestCase):

    def test_video_num_destino_so_e_estado(self):
        # O que a outra sessao pediu: 14 de 59 partes estavam so no YouTube,
        # e isso nao aparecia em lugar nenhum.
        ficha = _retrato(historias=[_yt("h12:p4")])
        self.assertEqual(ficha["num_destino_so"]["historias"], ["h12:p4"])
        self.assertTrue(any("destino só" in a for a in ficha["alertas"]))

    def test_nos_dois_destinos_nao_entra(self):
        ficha = _retrato(historias=[_yt("h12:p4"), _tk("h12:p4")])
        self.assertEqual(ficha["num_destino_so"]["historias"], [])

    def test_fora_da_janela_nao_conta(self):
        # O acervo de antes do TikTok entrar na grade nao pode inflar isto.
        velho = _yt("h1:p1")
        velho["quando"] = "2026-08-01T10:00:00"
        ficha = _retrato(historias=[velho])
        self.assertEqual(ficha["num_destino_so"]["historias"], [])

    def test_falha_do_tiktok_e_contada_mas_nao_acende_sozinha(self):
        # Evento e ruido; o estado (destino so) e quem alarma.
        eventos = [{"ts": f"{DIA}T12:40:00", "fabrica": "publicacao",
                    "status": "erro",
                    "detalhe": "TikTok: o botão de publicar não ficou clicável"}]
        ficha = _retrato(builds=[_yt("g1"), _tk("g1")], eventos=eventos)
        self.assertEqual(ficha["falhas_tiktok"], 1)
        self.assertEqual(ficha["veredito"], "ok")


class AValvula(unittest.TestCase):

    def test_cada_abertura_aparece_com_o_motivo(self):
        eventos = [{"ts": f"{DIA}T12:10:00", "fabrica": "publicacao",
                    "status": "log", "canal": "builds", "etapa": "valvula",
                    "ref": "g1:build:celular:B|titulo_repetido",
                    "detalhe": "titulo ja publicado"}]
        ficha = _retrato(builds=[_yt("g1"), _tk("g1")], eventos=eventos)
        self.assertEqual(len(ficha["valvula"]), 1)
        self.assertEqual(ficha["valvula"][0]["marca"], "titulo_repetido")
        self.assertEqual(ficha["valvula"][0]["alvo"], "g1:build:celular:B")
        self.assertEqual(ficha["veredito"], "atencao")


class AConferencia(unittest.TestCase):

    def test_sujo_acende(self):
        sujo = dict(_limpo(), veredito="sujo", rascunhos=[{}, {}])
        ficha = _retrato(conferencias={"builds": sujo,
                                       "historias": _limpo()})
        self.assertTrue(any("2 rascunho" in a for a in ficha["alertas"]))

    def test_falha_de_oauth_aparece_em_vez_de_passar_por_limpa(self):
        # O caso REAL de 16/09/2026: os tres tokens revogados. Uma
        # conferencia que nao rodou nao pode aparecer como "tudo certo".
        ficha = _retrato(conferencias={
            "builds": {"canal": "builds", "erro": "token invalido"},
            "historias": _limpo()})
        self.assertEqual(ficha["conferencia"]["builds"]["estado"], "falhou")
        self.assertTrue(any("não rodou" in a for a in ficha["alertas"]))

    def test_nunca_rodou_e_alerta(self):
        ficha = _retrato(conferencias={"builds": {}, "historias": _limpo()})
        self.assertTrue(any("nunca rodou" in a for a in ficha["alertas"]))

    def test_conferencia_parada_ha_dias_e_alerta(self):
        velha = dict(_limpo(), dia="2026-09-10")
        ficha = _retrato(conferencias={"builds": velha,
                                       "historias": _limpo()})
        self.assertTrue(any("parada desde" in a for a in ficha["alertas"]))


class ARegraDaCasa(unittest.TestCase):

    def test_nao_abre_subprocesso(self):
        # O pulso do painel e de 3 s. Um ffprobe aqui travaria a tela.
        chamados = []
        reais = (subprocess.run, subprocess.Popen)
        subprocess.run = lambda *a, **k: chamados.append(a)
        subprocess.Popen = lambda *a, **k: chamados.append(a)
        self.addCleanup(lambda: setattr(subprocess, "run", reais[0]))
        self.addCleanup(lambda: setattr(subprocess, "Popen", reais[1]))
        _retrato(builds=[_yt("g1"), _tk("g1")])
        self.assertEqual(chamados, [])

    def test_entrada_torta_nao_levanta(self):
        ficha = C.hoje(DIA, builds=[None, "x", {}], historias=[{"url": "y"}],
                       eventos=[None, 3, {}], conferencias={"builds": None})
        self.assertIn("veredito", ficha)

    def test_esta_no_resumo_do_panorama(self):
        import panorama
        self.assertIn("confiabilidade", panorama.resumo(forcar=True))


if __name__ == "__main__":
    unittest.main()
