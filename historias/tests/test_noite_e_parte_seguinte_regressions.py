# -*- coding: utf-8 -*-
"""Historias no YouTube: a noite com o melhor video e a parte seguinte ligada.

Decisao `publicacao/historias-21h-e-parte-seguinte` (19/10/2026). Medido
antes do codigo (videos de historias no YouTube com 3 a 40 dias, 19/10
13:4x): no 21:37, mediana de 254 views (25 videos, 17 com 100+); no 22:37,
6; no 23:37, 4. Entre os videos das 21h, a parte 1 fez 328,5 (10 videos) e
as outras partes 210 (15). "O melhor video pronto" e a parte 1 de uma serie
que ainda nao comecou, a primeira da fila, a limpa antes da retida.

A reserva e SO DE ORDEM: de dia a melhor vai para o fim, no primeiro
horario da noite sem video vai para a frente. Nunca sai da fila — senao,
sendo a unica limpa, o horario do dia sairia com uma RETIDA, e a valvula de
qualidade (decisao de 27/09) so solta retida quando nada mais pode sair.

A parte seguinte: o "video relacionado" do Shorts nao existe na API, e a
credencial de historias nao tem o escopo de edicao (medido em 19/10). Entao
a parte que tem seguinte sobe com "A parte seguinte já está no canal." no
fim da descricao, e com o link quando a seguinte ja esta no YouTube.
"""
from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_noite", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    modulo._linha = lambda *a, **k: None
    return modulo


class _Parte:
    def __init__(self, fonte, parte, partes=6, descricao="Parte de"):
        self.fonte_id = fonte
        self.parte = parte
        self.partes = partes
        self.id = f"{fonte}:celular:p{parte:02d}"
        self.titulo = f"{fonte} {parte}"
        self.descricao = descricao


def _yt(fonte, parte, quando, youtube_id="abc"):
    return {"video_id": f"{fonte}:celular:p{parte:02d}", "fonte_id": fonte,
            "parte": parte, "plataforma": "youtube", "quando": quando,
            "url": "https://youtu.be/x", "publicado": True,
            "youtube_id": youtube_id}


class ReordenarPelaNoiteTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()
        self.a, self.b, self.c = _Parte("h1", 3), _Parte("h2", 1), _Parte("h3", 2)
        self.fila = [self.a, self.b, self.c]

    def test_de_dia_a_melhor_vai_para_o_fim(self):
        nova = self.m._reordenar_pela_noite(self.fila, self.b, na_noite=False,
                                            de_dia=True)
        self.assertEqual([self.a, self.c, self.b], nova)

    def test_na_noite_vai_a_frente_atras_do_pedido_manual(self):
        nova = self.m._reordenar_pela_noite(self.fila, self.b, na_noite=True,
                                            de_dia=False)
        self.assertEqual([self.b, self.a, self.c], nova)
        nova = self.m._reordenar_pela_noite(self.fila, self.b, na_noite=True,
                                            de_dia=False, pedidos={self.c.id})
        self.assertEqual([self.c, self.b, self.a], nova)

    def test_a_serie_inteira_anda_junto_e_na_ordem(self):
        """Com so a parte 1 movida para o fim, a 2 da MESMA serie viria antes
        dela e `proxima_historia` a soltaria sem a 1 (o
        `test_adiada_nao_sai_limpa` pegou isso na 1a versao)."""
        b2 = _Parte("h2", 2)
        fila = [self.b, self.a, b2, self.c]
        nova = self.m._reordenar_pela_noite(fila, self.b, na_noite=False,
                                            de_dia=True)
        self.assertEqual([self.a, self.c, self.b, b2], nova)
        nova = self.m._reordenar_pela_noite([self.a, self.b, b2, self.c], self.b,
                                            na_noite=True, de_dia=False)
        self.assertEqual([self.b, b2, self.a, self.c], nova)
        # so a serie da melhor na fila: nada a reservar
        self.assertEqual([self.b, b2], self.m._reordenar_pela_noite(
            [self.b, b2], self.b, na_noite=False, de_dia=True))

    def test_noite_ja_paga_nao_mexe(self):
        self.assertEqual(self.fila, self.m._reordenar_pela_noite(
            self.fila, self.b, na_noite=False, de_dia=False))

    def test_zero_e_um_so_nao_mexem(self):
        self.assertEqual(self.fila, self.m._reordenar_pela_noite(
            self.fila, None, na_noite=True, de_dia=False))
        self.assertEqual([self.b], self.m._reordenar_pela_noite(
            [self.b], self.b, na_noite=False, de_dia=True))
        self.assertEqual([], self.m._reordenar_pela_noite(
            [], None, na_noite=True, de_dia=True))

    def test_ninguem_sai_da_fila(self):
        for noite, dia in ((True, False), (False, True), (False, False)):
            nova = self.m._reordenar_pela_noite(self.fila, self.b,
                                                na_noite=noite, de_dia=dia)
            self.assertEqual(sorted(v.id for v in self.fila),
                             sorted(v.id for v in nova))


class MelhorDaNoiteTests(unittest.TestCase):
    def setUp(self):
        self.m = m = _postar()
        self.retidas = set()
        m._veto_lembrado = lambda alvo: ""
        m._retencao = lambda alvo: "retida" if alvo.id in self.retidas else ""

    def test_parte_1_de_serie_nova_a_primeira_da_fila(self):
        fila = [_Parte("h1", 3), _Parte("h2", 1), _Parte("h3", 1)]
        self.assertEqual("h2:celular:p01",
                         self.m._melhor_da_noite(fila, {"h1"}).id)

    def test_a_limpa_antes_da_retida(self):
        fila = [_Parte("h2", 1), _Parte("h3", 1)]
        self.retidas.add("h2:celular:p01")
        self.assertEqual("h3:celular:p01", self.m._melhor_da_noite(fila, set()).id)
        self.retidas.add("h3:celular:p01")
        self.assertEqual("h2:celular:p01", self.m._melhor_da_noite(fila, set()).id,
                         "todas retidas: a primeira (a valvula decide se sai)")

    def test_zero_sem_serie_nova(self):
        self.assertIsNone(self.m._melhor_da_noite([_Parte("h1", 2)], {"h1"}))
        self.assertIsNone(self.m._melhor_da_noite([_Parte("h1", 1)], {"h1"}),
                          "parte 1 de serie ja comecada nao e serie nova")
        self.assertIsNone(self.m._melhor_da_noite([], set()))


class NoiteSemVideoTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()

    def test_21h_sempre(self):
        self.assertTrue(self.m._noite_sem_video([], datetime(2026, 10, 20, 21, 40)))

    def test_22h_so_se_o_das_21h_nao_saiu(self):
        agora = datetime(2026, 10, 20, 22, 40)
        self.assertTrue(self.m._noite_sem_video([], agora))
        pago = [_yt("h1", 1, "2026-10-20T21:42:00")]
        self.assertFalse(self.m._noite_sem_video(pago, agora))
        # a linha de ONTEM nao paga a noite de hoje
        ontem = [_yt("h1", 1, "2026-10-19T21:42:00")]
        self.assertTrue(self.m._noite_sem_video(ontem, agora))

    def test_de_dia_e_00h_nao_e_noite(self):
        self.assertFalse(self.m._noite_sem_video([], datetime(2026, 10, 20, 15, 40)))
        self.assertFalse(self.m._noite_sem_video([], datetime(2026, 10, 21, 0, 40)))


class ParteSeguinteNaDescricaoTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()

    def test_parte_com_seguinte_ganha_o_texto(self):
        alvo = _Parte("h1", 1, 6, "O que voce faria?")
        novo = self.m._com_a_parte_seguinte(alvo, publicados=[])
        self.assertTrue(novo.descricao.endswith("A parte seguinte já está no canal."))
        self.assertTrue(novo.descricao.startswith("O que voce faria?"))
        self.assertEqual("O que voce faria?", alvo.descricao, "o original nao muda")

    def test_com_a_seguinte_ja_no_youtube_vai_o_link(self):
        alvo = _Parte("h1", 1, 6, "x")
        novo = self.m._com_a_parte_seguinte(
            alvo, publicados=[_yt("h1", 2, "2026-10-20T09:40:00", "ID2")])
        self.assertIn("Parte 2: https://youtube.com/shorts/ID2", novo.descricao)

    def test_zero_sem_parte_seguinte(self):
        """Ultima parte e parte unica nao prometem seguinte."""
        ultima = _Parte("h1", 6, 6, "fim")
        self.assertIs(ultima, self.m._com_a_parte_seguinte(ultima, publicados=[]))
        unica = _Parte("h1", 1, 1, "so")
        self.assertIs(unica, self.m._com_a_parte_seguinte(unica, publicados=[]))

    def test_nao_repete_o_texto(self):
        alvo = _Parte("h1", 2, 6, "x\n\nA parte seguinte já está no canal.")
        self.assertIs(alvo, self.m._com_a_parte_seguinte(alvo, publicados=[]))

    def test_o_funil_do_youtube_sobe_a_copia_com_o_texto(self):
        from contos.publicar import catalogo
        subidos = []

        def publicar(video, visibilidade=None, provas=None, **k):
            subidos.append(video.descricao)
            return "https://youtu.be/x"
        original = catalogo.publicar_youtube
        catalogo.publicar_youtube = publicar
        self.addCleanup(setattr, catalogo, "publicar_youtube", original)
        self.m._publicados_do_canal = lambda canal: []
        self.m._subir_parte_no_youtube(_Parte("h1", 1, 6, "x"), "public", [])
        self.assertIn("A parte seguinte já está no canal.", subidos[0])


class LigarAParteAnteriorTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()
        self.m._publicados_do_canal = lambda canal: [
            _yt("h1", 1, "2026-10-20T21:40:00", "ID1")]
        self.chamadas = []

    def _editar(self, video_id, texto, canal):
        self.chamadas.append((video_id, texto, canal))
        return {"mudou": True}

    def test_desligado_nao_toca_no_canal(self):
        self.assertFalse(self.m.LIGAR_PELA_API, "so liga com o escopo de edicao")
        r = self.m._ligar_a_parte_anterior(_Parte("h1", 2), [{"youtube_id": "ID2"}],
                                           editar=self._editar)
        self.assertFalse(r["ligou"])
        self.assertEqual([], self.chamadas)

    def test_ligado_poe_o_link_da_nova_na_anterior(self):
        self.m.LIGAR_PELA_API = True
        r = self.m._ligar_a_parte_anterior(_Parte("h1", 2), [{"youtube_id": "ID2"}],
                                           editar=self._editar)
        self.assertTrue(r["ligou"])
        self.assertEqual([("ID1", "Parte 2: https://youtube.com/shorts/ID2",
                           "historias")], self.chamadas)

    def test_zero_parte_1_e_sem_id(self):
        self.m.LIGAR_PELA_API = True
        self.m._ligar_a_parte_anterior(_Parte("h1", 1), [{"youtube_id": "ID1"}],
                                       editar=self._editar)
        self.m._ligar_a_parte_anterior(_Parte("h1", 2), [{}], editar=self._editar)
        self.assertEqual([], self.chamadas)

    def test_erro_nao_derruba(self):
        self.m.LIGAR_PELA_API = True

        def quebra(*a):
            raise RuntimeError("403")
        r = self.m._ligar_a_parte_anterior(_Parte("h1", 2), [{"youtube_id": "ID2"}],
                                           editar=quebra)
        self.assertFalse(r["ligou"])


if __name__ == "__main__":
    unittest.main()
