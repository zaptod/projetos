# -*- coding: utf-8 -*-
"""A recuperacao do YouTube publicou CINCO duplicatas: o gemeo publico nao
estava na lista.

MEDIDO EM 28/09/2026. Entre 27/09 20:5x e 28/09 06:4x a recuperacao de
privados tornou publicos UlIc_DXyFa4, BM5BkPe56yo, EgganpfYcR0, y2H4ZzNIlEM
e eopdwaZ0swA — e os cinco tinham gemeo PUBLICO com o mesmo titulo no canal
(9U7UopBm3MM, XxOuPbJ2vtA, Jb7gIFumNQQ, xNZFFoMYQjk, UsDYI-pRqZ8), que a
busca do proprio canal acha. O crivo 4 de `recuperaveis` existe para isso,
e ficou cego: ele procurava o gemeo na playlist de ENVIOS (`UU...`), e ela
nao traz todos os Shorts publicos.

    canal de builds, 28/09 07:3x:   `statistics.videoCount` 145 publicos
    playlist UU (envios)            139 videos (115 publicos, 24 privados)
    playlist UUSH (Shorts)          145 — com xNZFFoMYQjk e UsDYI-pRqZ8
    uniao de todas                  169 (146 publicos, 23 privados)

No canal de historias a UU veio completa (180 publicos de 180).

O conserto: o canal e lido pela UNIAO da playlist de envios com a dos Shorts,
e a recuperacao confere a lista contra o numero de publicos que o proprio
canal declara — com publico faltando, o crivo do gemeo e cego, e ela NAO
recupera (duplicar e pior que adiar).
"""
from __future__ import annotations

import unittest

from builds.publicar import recuperar


class _Canal:
    """Um canal falso respondendo `_get` como a API: canal, playlists, videos."""

    def __init__(self, *, uu, uush, videos, declarados, uush_existe=True):
        self.uu, self.uush, self.videos = uu, uush, videos
        self.declarados, self.uush_existe = declarados, uush_existe

    def __call__(self, token, caminho, **params):
        if caminho == "channels":
            return {"items": [{
                "id": "UCx", "snippet": {"title": "canal"},
                "contentDetails": {"relatedPlaylists": {"uploads": "UUabc"}},
                "statistics": {"videoCount": str(self.declarados)}}]}
        if caminho == "playlistItems":
            lista = params["playlistId"]
            if lista == "UUSHabc" and not self.uush_existe:
                raise recuperar.PublicacaoFalhou(
                    "o YouTube recusou playlistItems (404): not found")
            ids = self.uu if lista == "UUabc" else self.uush
            return {"items": [{"contentDetails": {"videoId": i}} for i in ids]}
        if caminho == "videos":
            pedidos = params["id"].split(",")
            return {"items": [
                {"id": i, "snippet": {"title": self.videos[i][0],
                                      "description": "d",
                                      "publishedAt": self.videos[i][2]},
                 "status": {"privacyStatus": self.videos[i][1],
                            "uploadStatus": "processed"},
                 "contentDetails": {"duration": "PT1M"}}
                for i in pedidos if i in self.videos]}
        raise AssertionError(caminho)


class GemeoForaDaListaTests(unittest.TestCase):
    TITULO = "Juan Hector estreia contra Sveyn Miraleven — venceu por 2 x 0"

    def setUp(self):
        for nome, valor in (("conferir_o_canal", lambda canal, aberto: "UCx"),
                            ("_token", lambda canal, editar=True: "tok")):
            original = getattr(recuperar, nome)
            setattr(recuperar, nome, valor)
            self.addCleanup(setattr, recuperar, nome, original)

    def _com(self, canal):
        original = recuperar._get
        recuperar._get = canal
        self.addCleanup(setattr, recuperar, "_get", original)

    def _y2h4(self, **k):
        """A forma de y2H4ZzNIlEM: privado na UU, gemeo publico so na UUSH."""
        return _Canal(uu=["y2H4ZzNIlEM"], uush=["xNZFFoMYQjk"], videos={
            "y2H4ZzNIlEM": (self.TITULO, "private", "2026-09-14T12:29:29Z"),
            "xNZFFoMYQjk": (self.TITULO, "public", "2026-08-27T22:52:49Z")},
            declarados=1, **k)

    def test_o_gemeo_que_so_a_lista_dos_shorts_tem_barra(self):
        self._com(self._y2h4())
        self.assertEqual([], recuperar.recuperaveis("builds"))

    def test_o_canal_e_lido_pelas_duas_listas(self):
        self._com(self._y2h4())
        ids = {v["id"] for v in recuperar.videos_do_canal("builds")}
        self.assertEqual({"y2H4ZzNIlEM", "xNZFFoMYQjk"}, ids)

    def test_lista_com_publico_faltando_nao_recupera(self):
        """Sem a UUSH (404) e com o canal declarando 1 publico, a lista tem
        0: o crivo do gemeo esta cego, e a recuperacao para."""
        self._com(self._y2h4(uush_existe=False))
        with self.assertRaises(recuperar.ListaIncompleta):
            recuperar.recuperaveis("builds")

    def test_canal_sem_shorts_e_lista_completa_recupera(self):
        """404 na UUSH e canal sem Shorts, nao erro: com a conta batendo, o
        privado sem gemeo volta."""
        self._com(_Canal(uu=["priv", "pub"], uush=[], uush_existe=False,
                         videos={"priv": ("Outro titulo", "private", "2026-09-16T01:00:00Z"),
                                 "pub": ("Titulo publico", "public", "2026-09-10T01:00:00Z")},
                         declarados=1))
        self.assertEqual(["priv"], [v["id"] for v in recuperar.recuperaveis("builds")])

    def test_caso_zero_canal_vazio_nao_recupera_nada(self):
        self._com(_Canal(uu=[], uush=[], videos={}, declarados=0))
        self.assertEqual([], recuperar.recuperaveis("builds"))


if __name__ == "__main__":
    unittest.main()
