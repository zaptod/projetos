# -*- coding: utf-8 -*-
"""`ferramentas/curar_ledger.py`: o passo 2 do contrato do campo `url`.

O que mais importa aqui e o que NAO acontece: a seco nada muda no ledger, e
cura "a conferir" nunca e aplicada. As curas mudam o que a fila considera
publicado, e isso e decisao do Adrian.

Nada toca a rede: a lista do canal e injetada, e os ledgers sao arquivos
descartaveis.
"""
import importlib.util
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from builds.publicar import metricas as M

FERRAMENTA = Path(__file__).resolve().parents[2] / "ferramentas" / "curar_ledger.py"


def _modulo():
    spec = importlib.util.spec_from_file_location("curar_ledger", FERRAMENTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


C = _modulo()
NO_AR = "2026-09-16T09:42:08Z"
BASE = M._instante(NO_AR)


def _hora(**delta):
    return (BASE + timedelta(**delta)).isoformat(timespec="seconds")


def _yt(vid="g1:build:celular", titulo="O MAGO", *, url="publicado no YouTube",
        youtube_id=None, quando=None, plataforma="youtube"):
    return {"video_id": vid, "titulo": titulo, "plataforma": plataforma,
            "url": url, "youtube_id": youtube_id,
            "quando": quando or _hora(seconds=15)}


def _video(vid, titulo="O MAGO", privacidade="public", no_ar=NO_AR):
    return {"youtube_id": vid, "titulo": titulo, "privacidade": privacidade,
            "publicado_em": no_ar}


def _tipos(curas):
    return [(c["linha"], c["tipo"], c["certeza"]) for c in curas]


class FraseNoUrl(unittest.TestCase):

    def test_um_video_vira_link_com_certeza_alta(self):
        (cura,) = C.calcular_curas([_yt()], [_video("aaa")])
        self.assertEqual(("link_de_frase", "alta"), (cura["tipo"], cura["certeza"]))
        self.assertEqual("https://youtu.be/aaa", cura["depois"]["url"])
        self.assertEqual("publicado no YouTube", cura["depois"]["estado_texto"])
        self.assertIs(True, cura["depois"]["publicado"])

    def test_dois_pedacos_viram_lista(self):
        # O caso de historia_00003: a parte saiu em "(1 de 2)" e "(2 de 2)".
        linha = _yt("h3:celular:p04", "A historia oficial (Parte 4)",
                    url="publicado no YouTube | publicado no YouTube")
        videos = [_video("p1", "A historia oficial (Parte 4) (1 de 2)",
                         no_ar=_hora(seconds=-26)),
                  _video("p2", "A historia oficial (Parte 4) (2 de 2)")]
        (cura,) = C.calcular_curas([linha], videos, "historias")
        self.assertEqual("link_de_pedacos", cura["tipo"])
        self.assertEqual(["p1", "p2"], cura["depois"]["youtube_ids"])
        self.assertEqual("p1", cura["depois"]["youtube_id"])

    def test_pedaco_faltando_nao_vira_link(self):
        # Meia parte nao e publicacao.
        linha = _yt("h3:celular:p04", "A historia oficial (Parte 4)")
        videos = [_video("p1", "A historia oficial (Parte 4) (1 de 2)")]
        tipos = [c["tipo"] for c in C.calcular_curas([linha], videos)]
        self.assertNotIn("link_de_pedacos", tipos)


class VideoPrivado(unittest.TestCase):

    def test_sem_gemeo_deixa_de_contar_como_publicado(self):
        linha = _yt(url="https://youtu.be/rrr", youtube_id="rrr")
        (cura,) = C.calcular_curas([linha], [_video("rrr", privacidade="private")])
        self.assertEqual("rascunho_sem_gemeo", cura["tipo"])
        self.assertIs(False, cura["depois"]["publicado"])
        self.assertEqual("rrr", cura["depois"]["rascunho_id"])

    def test_com_um_gemeo_passa_a_apontar_para_ele(self):
        linha = _yt(url="https://youtu.be/rrr", youtube_id="rrr")
        videos = [_video("rrr", privacidade="private"), _video("ppp")]
        (cura,) = C.calcular_curas([linha], videos)
        self.assertEqual("rascunho_com_gemeo", cura["tipo"])
        self.assertEqual("ppp", cura["depois"]["youtube_id"])
        self.assertIs(True, cura["depois"]["publicado"])

    def test_gemeo_ambiguo_e_a_conferir_e_nao_e_aplicado(self):
        linha = _yt(url="https://youtu.be/rrr", youtube_id="rrr")
        videos = [_video("rrr", privacidade="private"), _video("p1"),
                  _video("p2")]
        curas = C.calcular_curas([linha], videos)
        self.assertEqual([(0, "rascunho_gemeo_ambiguo", "a_conferir")],
                         _tipos(curas))
        (depois,) = C.aplicar([linha], curas)
        self.assertEqual(linha, depois)

    def test_video_repetido_na_lista_do_canal_nao_vira_dois_gemeos(self):
        # A lista de uploads trouxe `U7n1dgQCidA` duas vezes (16/09/2026).
        linha = _yt(url="https://youtu.be/rrr", youtube_id="rrr")
        videos = [_video("rrr", privacidade="private"), _video("ppp"),
                  _video("ppp")]
        (cura,) = C.calcular_curas([linha], videos)
        self.assertEqual("rascunho_com_gemeo", cura["tipo"])

    def test_gemeo_que_ja_tem_dono_nao_e_dado_de_novo(self):
        linhas = [_yt(url="https://youtu.be/rrr", youtube_id="rrr"),
                  _yt("g2", url="https://youtu.be/ppp", youtube_id="ppp")]
        videos = [_video("rrr", privacidade="private"), _video("ppp")]
        tipos = [c["tipo"] for c in C.calcular_curas(linhas, videos)]
        self.assertIn("rascunho_sem_gemeo", tipos)

    def test_historia_privada_e_pergunta_para_o_adrian(self):
        # A historia_00005 pode ter sido privada DE PROPOSITO.
        linha = _yt("h5:celular:p03", url="https://youtu.be/rrr",
                    youtube_id="rrr")
        curas = C.calcular_curas([linha], [_video("rrr", privacidade="private")],
                                 "historias")
        self.assertEqual([(0, "historia_privada", "a_conferir")], _tipos(curas))


class IdRepetido(unittest.TestCase):

    def test_a_linha_longe_da_hora_do_video_perde_o_id(self):
        # generation_00081: A (21:39) recebeu o id do upload B (00:39).
        a = _yt("g81:build:celular", url="https://youtu.be/xxx",
                youtube_id="xxx", quando=_hora(hours=-3))
        b = _yt("g81:build:celular:B", url="https://youtu.be/xxx",
                youtube_id="xxx", quando=_hora(seconds=10))
        curas = C.calcular_curas([a, b], [_video("xxx")])
        (repetido,) = [c for c in curas if c["tipo"] == "id_repetido"]
        self.assertEqual(0, repetido["linha"])
        self.assertIsNone(repetido["depois"]["youtube_id"])
        self.assertIs(False, repetido["depois"]["publicado"])


class Formato(unittest.TestCase):

    def test_tiktok_perde_a_frase_do_url_e_ganha_publicado(self):
        tk = _yt(url="publicado no TikTok", plataforma="tiktok")
        (cura,) = C.calcular_curas([tk], [])
        self.assertEqual("formato", cura["tipo"])
        self.assertEqual("", cura["depois"]["url"])
        self.assertEqual("publicado no TikTok", cura["depois"]["estado_texto"])
        self.assertIs(True, cura["depois"]["publicado"])

    def test_linha_com_link_so_ganha_o_campo(self):
        linha = _yt(url="https://youtu.be/aaa", youtube_id="aaa")
        (cura,) = C.calcular_curas([linha], [_video("aaa")])
        self.assertEqual({"publicado": True, "estado": "publicado"},
                         cura["depois"])

    def test_a_leitura_nao_muda_para_quem_so_ganhou_formato(self):
        # A regra 4 nao pode mudar a resposta de `publicado()` de ninguem.
        linhas = [_yt(url="https://youtu.be/aaa", youtube_id="aaa"),
                  _yt("g2", url="publicado no TikTok", plataforma="tiktok"),
                  _yt("g3", url="")]
        antes = [M.publicado(L) for L in linhas]
        depois = [M.publicado(L)
                  for L in C.aplicar(linhas, C.calcular_curas(linhas, []))]
        self.assertEqual(antes, depois)

    def test_curar_duas_vezes_nao_acha_mais_nada(self):
        linhas = [_yt(), _yt("g2", url="publicado no TikTok",
                             plataforma="tiktok")]
        videos = [_video("aaa")]
        curadas = C.aplicar(linhas, C.calcular_curas(linhas, videos))
        self.assertEqual([], C.calcular_curas(curadas, videos))

    def test_cura_de_conteudo_deixa_historico_na_linha(self):
        (curada,) = C.aplicar([_yt()], C.calcular_curas([_yt()], [_video("aaa")]))
        (hist,) = curada["cura"]
        self.assertEqual("link_de_frase", hist["tipo"])
        self.assertEqual("publicado no YouTube", hist["antes"]["url"])


class ASecoEPadrao(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        pasta = Path(self._tmp.name)
        self.ledger = pasta / "publicados.jsonl"
        self.ledger.write_text(json.dumps(_yt(), ensure_ascii=False) + "\n",
                               encoding="utf-8")
        reais = (C.buscar_canal, C.SAIDA, M.registro_do_canal)
        C.buscar_canal = lambda canal: [_video("aaa")]
        C.SAIDA = pasta / "_cura"
        M.registro_do_canal = lambda canal="builds": self.ledger

        def restaurar():
            C.buscar_canal, C.SAIDA, M.registro_do_canal = reais

        self.addCleanup(restaurar)

    def test_sem_flag_nada_muda_no_ledger(self):
        antes = self.ledger.read_bytes()
        self.assertEqual(0, C.main(["--canal", "builds"]))
        self.assertEqual(antes, self.ledger.read_bytes())
        self.assertEqual([], list(self.ledger.parent.glob("*.antes-cura-*")))
        (resumo,) = C.SAIDA.glob("*/resumo.json")
        dados = json.loads(resumo.read_text(encoding="utf-8"))
        self.assertIs(False, dados["gravado"])
        self.assertEqual({"link_de_frase (alta)": 1}, dados["canais"]["builds"])

    def test_com_flag_grava_e_guarda_copia(self):
        antes = self.ledger.read_bytes()
        C.main(["--canal", "builds", "--gravar"])
        (copia,) = self.ledger.parent.glob("*.antes-cura-*")
        self.assertEqual(antes, copia.read_bytes())
        (linha,) = C.ler(self.ledger)
        self.assertEqual("aaa", linha["youtube_id"])
        self.assertIs(True, linha["publicado"])


if __name__ == "__main__":
    unittest.main()
