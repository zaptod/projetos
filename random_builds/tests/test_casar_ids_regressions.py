# -*- coding: utf-8 -*-
"""`casar_ids`: quem ganha qual id, e quem fica sem.

16/09/2026: a linha A de generation_00081 (15/09 21:39) saiu sem link, e a
reconciliacao lhe deu o id do upload B (16/09 00:39) porque os dois tem o
mesmo titulo e o canal lista o mais novo primeiro. O ledger passou a afirmar
que A foi ao ar com o video de B — e a conferencia contou o mesmo video em
duas linhas.

A funcao e pura: listas na mao, sem disco e sem rede. As horas do canal vem
em UTC; as do ledger sao montadas pela mesma conversao, para o teste nao
depender do fuso da maquina.
"""
import unittest
from datetime import timedelta

from builds.publicar import metricas as M

NO_AR = "2026-09-16T03:40:10Z"
BASE = M._instante(NO_AR)


def _hora(**delta):
    return (BASE + timedelta(**delta)).isoformat(timespec="seconds")


def _linha(titulo="T", *, quando=None, youtube_id=None, **extra):
    linha = {"titulo": titulo, "plataforma": "youtube",
             "youtube_id": youtube_id, "quando": quando or _hora(minutes=1)}
    linha.update(extra)
    return linha


def _video(vid, titulo="T", no_ar=NO_AR):
    return {"youtube_id": vid, "titulo": titulo, "publicado_em": no_ar}


class AGuardaDeHora(unittest.TestCase):

    def test_video_perto_da_linha_casa(self):
        pares = M.casar_ids([_linha()], [_video("aaa")])
        self.assertEqual([(0, "aaa")], [(i, v["youtube_id"]) for i, v in pares])

    def test_video_tres_horas_DEPOIS_nao_casa(self):
        # O caso real: A as 21:39, o video de B as 00:40.
        pares = M.casar_ids([_linha(quando=_hora(hours=-3, minutes=-1))],
                            [_video("aaa")])
        self.assertEqual([], pares)

    def test_video_muito_ANTES_tambem_nao_casa(self):
        pares = M.casar_ids([_linha(quando=_hora(hours=5))], [_video("aaa")])
        self.assertEqual([], pares)

    def test_agendado_usa_a_hora_agendada(self):
        # Publicacao agendada vai ao ar na hora marcada, nao na do registro.
        linha = _linha(quando=_hora(days=-2), agendado_para=_hora(minutes=0))
        self.assertEqual(1, len(M.casar_ids([linha], [_video("aaa")])))

    def test_video_sem_data_nao_casa(self):
        self.assertEqual([], M.casar_ids([_linha()], [_video("aaa", no_ar=None)]))

    def test_linha_sem_hora_nao_casa(self):
        linha = _linha()
        linha["quando"] = None
        self.assertEqual([], M.casar_ids([linha], [_video("aaa")]))


class AGuardaDeDono(unittest.TestCase):

    def test_id_de_outra_linha_nao_e_dado_de_novo(self):
        # Mesmo com a hora batendo: o id ja e de alguem.
        linhas = [_linha(), _linha(youtube_id="aaa")]
        self.assertEqual([], M.casar_ids(linhas, [_video("aaa")]))

    def test_duas_linhas_nao_levam_o_mesmo_video_na_mesma_rodada(self):
        linhas = [_linha(quando=_hora(minutes=1)),
                  _linha(quando=_hora(minutes=2))]
        pares = M.casar_ids(linhas, [_video("aaa")])
        self.assertEqual(1, len(pares))

    def test_cada_linha_fica_com_o_video_mais_proximo(self):
        # A e B com o mesmo titulo, cada um no seu horario.
        linhas = [_linha(quando=_hora(hours=-3)), _linha(quando=_hora(minutes=1))]
        videos = [_video("de_b"),
                  _video("de_a", no_ar=(BASE - timedelta(hours=3, minutes=1))
                         .strftime("%Y-%m-%dT%H:%M:%S"))]
        pares = {i: v["youtube_id"] for i, v in M.casar_ids(linhas, videos)}
        self.assertEqual({0: "de_a", 1: "de_b"}, pares)


class OResto(unittest.TestCase):

    def test_quem_ja_tem_id_e_tiktok_ficam_de_fora(self):
        linhas = [_linha(youtube_id="jasei"),
                  _linha(plataforma="tiktok")]
        self.assertEqual([], M.casar_ids(linhas, [_video("aaa")]))

    def test_titulo_diferente_nao_casa(self):
        self.assertEqual([], M.casar_ids([_linha("OUTRO")], [_video("aaa")]))

    def test_entrada_vazia(self):
        self.assertEqual([], M.casar_ids([], []))
        self.assertEqual([], M.casar_ids([_linha()], None))


if __name__ == "__main__":
    unittest.main()
