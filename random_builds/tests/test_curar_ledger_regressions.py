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

    def test_rascunho_sem_gemeo_perde_o_url(self):
        # Link de rascunho no campo de "saiu" faria `url` e `publicado`
        # discordarem para quem ainda olha o `url`.
        linha = _yt(url="https://youtu.be/rrr", youtube_id="rrr")
        (cura,) = C.calcular_curas([linha], [_video("rrr", privacidade="private")])
        self.assertEqual("", cura["depois"]["url"])
        self.assertEqual("rrr", cura["depois"]["rascunho_id"])

    def test_privada_de_proposito_continua_publicada(self):
        # Decisao do Adrian (16/09/2026) para h10 p01, h05 p03 e h04 p03.
        linha = _yt("h5:celular:p03", url="https://youtu.be/rrr",
                    youtube_id="rrr")
        (cura,) = C.calcular_curas(
            [linha], [_video("rrr", privacidade="private")], "historias",
            privadas={"h5:celular:p03"})
        self.assertEqual(("privado_de_proposito", "alta"),
                         (cura["tipo"], cura["certeza"]))
        self.assertIs(True, cura["depois"]["publicado"])
        (curada,) = C.aplicar([linha], [cura])
        self.assertTrue(M.publicado(curada))

    def test_curar_de_novo_nao_mexe_no_que_ja_foi_decidido(self):
        linhas = [_yt(url="https://youtu.be/rrr", youtube_id="rrr"),
                  _yt("h5:celular:p03", url="https://youtu.be/sss",
                      youtube_id="sss")]
        videos = [_video("rrr", privacidade="private"),
                  _video("sss", privacidade="private")]
        curadas = C.aplicar(linhas, C.calcular_curas(
            linhas, videos, privadas={"h5:celular:p03"}))
        self.assertEqual([], C.calcular_curas(
            curadas, videos, privadas={"h5:celular:p03"}))

    def test_decisao_do_adrian_vale_para_linha_ja_curada_como_rascunho(self):
        # Item 12 da segunda revisao: ignorar em silencio deixava a fila
        # republicar uma parte que ele quis privada.
        linha = dict(_yt("g5:build:celular", url="", youtube_id="rrr"),
                     publicado=False, estado="rascunho", rascunho_id="rrr")
        (cura,) = C.calcular_curas([linha],
                                   [_video("rrr", privacidade="private")],
                                   privadas={"g5:build:celular"})
        self.assertEqual("privado_de_proposito", cura["tipo"])
        self.assertIn("rascunho", cura["motivo"])
        (curada,) = C.aplicar([linha], [cura])
        self.assertTrue(M.publicado(curada))
        self.assertEqual("https://youtu.be/rrr", curada["url"])
        self.assertEqual([], C.calcular_curas(
            [curada], [_video("rrr", privacidade="private")],
            privadas={"g5:build:celular"}))

    def test_privada_que_nao_pegou_vira_aviso(self):
        linhas = [_yt("g1", url="https://youtu.be/pub", youtube_id="pub"),
                  _yt("g2", url="https://youtu.be/rrr", youtube_id="rrr")]
        videos = [_video("pub"), _video("rrr", privacidade="private")]
        privadas = ["g1", "g2", "digitado_errado"]
        curas = C.calcular_curas(linhas, videos, privadas=privadas)
        avisos = dict(C.privadas_sem_efeito(linhas, curas, privadas))
        self.assertEqual({"g1", "digitado_errado"}, set(avisos))
        self.assertIn("nao esta privado", avisos["g1"])
        self.assertIn("nenhuma linha", avisos["digitado_errado"])

    def test_privada_ja_decidida_nao_e_aviso(self):
        linha = dict(_yt("g2", url="https://youtu.be/rrr", youtube_id="rrr"),
                     publicado=True, estado="privado_de_proposito")
        self.assertEqual([], C.privadas_sem_efeito([linha], [], ["g2"]))

    def test_historia_privada_e_pergunta_para_o_adrian(self):
        # A historia_00005 pode ter sido privada DE PROPOSITO.
        linha = _yt("h5:celular:p03", url="https://youtu.be/rrr",
                    youtube_id="rrr")
        curas = C.calcular_curas([linha], [_video("rrr", privacidade="private")],
                                 "historias")
        self.assertEqual([(0, "historia_privada", "a_conferir")], _tipos(curas))


class GemeoDeVerdade(unittest.TestCase):
    """B4 da revisao de 16/09/2026, confirmado nos dados: 11 dos 12 "gemeos"
    achados so pelo titulo foram ao ar ~17 dias ANTES do rascunho. Eram
    videos antigos de builds refeitas, com o mesmo personagem e nota."""

    def setUp(self):
        self.linha = _yt(url="https://youtu.be/rrr", youtube_id="rrr")
        self.rascunho = _video("rrr", privacidade="private")

    def test_homonimo_antigo_nao_e_gemeo(self):
        antigo = _video("velho", no_ar=_hora(days=-17))
        (cura,) = C.calcular_curas([self.linha], [self.rascunho, antigo])
        self.assertEqual("rascunho_sem_gemeo", cura["tipo"])
        self.assertIn("velho", cura["motivo"])

    def test_reenvio_depois_do_rascunho_e_gemeo(self):
        depois = _video("novo", no_ar=_hora(hours=5))
        (cura,) = C.calcular_curas([self.linha], [self.rascunho, depois])
        self.assertEqual("rascunho_com_gemeo", cura["tipo"])
        self.assertEqual("novo", cura["depois"]["youtube_id"])

    def test_reenvio_depois_de_uma_semana_nao_conta(self):
        tarde = _video("tarde", no_ar=_hora(days=9))
        (cura,) = C.calcular_curas([self.linha], [self.rascunho, tarde])
        self.assertEqual("rascunho_sem_gemeo", cura["tipo"])

    def test_parte_diferente_nao_e_gemeo_nas_historias(self):
        titulo = "Uma historia com titulo bem comprido para passar do corte"
        linha = _yt("h1:celular:p03", f"{titulo} (Parte 3/6)",
                    url="https://youtu.be/rrr", youtube_id="rrr")
        rascunho = _video("rrr", f"{titulo} (Parte 3/6)", privacidade="private")
        outra_parte = _video("p4", f"{titulo} (Parte 4/6)", no_ar=_hora(hours=1))
        (cura,) = C.calcular_curas([linha], [rascunho, outra_parte], "historias")
        self.assertEqual("historia_privada", cura["tipo"])

    def test_o_dono_verdadeiro_fica_com_o_video(self):
        # A regra da frase (hora exata) vem ANTES do gemeo e reserva o id.
        dono = _yt("g2", url="publicado no YouTube", quando=_hora(hours=5,
                                                                 seconds=10))
        publico = _video("novo", no_ar=_hora(hours=5))
        curas = C.calcular_curas([self.linha, dono], [self.rascunho, publico])
        por_linha = {c["linha"]: c for c in curas}
        self.assertEqual("link_de_frase", por_linha[1]["tipo"])
        self.assertEqual("novo", por_linha[1]["depois"]["youtube_id"])
        self.assertEqual("rascunho_sem_gemeo", por_linha[0]["tipo"])


class IdRepetido(unittest.TestCase):

    def test_video_fora_da_lista_do_canal_e_a_conferir(self):
        # B5: sem o video, "o mais proximo" seria sorteio.
        a = _yt("g1", url="https://youtu.be/xxx", youtube_id="xxx")
        b = _yt("g2", url="https://youtu.be/xxx", youtube_id="xxx")
        curas = C.calcular_curas([a, b], [])
        self.assertEqual({"id_repetido_sem_video"}, {c["tipo"] for c in curas})
        self.assertEqual({"a_conferir"}, {c["certeza"] for c in curas})
        self.assertEqual([a, b], C.aplicar([a, b], curas))

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


class PreCondicaoDoPostar(unittest.TestCase):
    """B1 da revisao: com o postar.py lendo o `url`, a regra de formato
    apagaria a guarda de "ja esta no TikTok" de 46 builds e 51 historias."""

    def test_sem_a_constante_recusa(self):
        self.assertIn("CONTRATO_DO_LEDGER",
                      C.postar_migrado("def x():\n    return 1\n"))

    def test_constante_com_leitura_por_url_restante_recusa(self):
        fonte = ("CONTRATO_DO_LEDGER = 2\n"
                 "ja = {l.get('v') for l in x if l.get(\"url\")}\n")
        self.assertIn("1 ponto", C.postar_migrado(fonte))

    def test_arvore_pega_qualquer_nome_e_qualquer_formatacao(self):
        # Item 6: a regex so via `l`/`linha` na mesma linha do `if`.
        fonte = ("CONTRATO_DO_LEDGER = 2\n"
                 "a = any(x.get('video_id') == v and\n"
                 "        x.get(\"url\") for x in y)\n"
                 "b = [e for e in y\n"
                 "     if e.get('url')]\n"
                 "if not item.get('url'):\n    pass\n"
                 "c = 1 if w.get('url') else 2\n")
        self.assertEqual([3, 5, 6, 8], C.leituras_por_url(fonte))
        self.assertIn("4 ponto", C.postar_migrado(fonte))

    def test_valor_padrao_e_ficha_nao_sao_decisao(self):
        fonte = ("d = {'url': ja.get('url') or ''}\n"
                 "if r.get('url'):\n    pass\n"
                 "print(linha.get('url'))\n")
        self.assertEqual([], C.leituras_por_url(fonte))

    def test_codigo_que_nao_compila_recusa(self):
        self.assertIn("nao compila",
                      C.postar_migrado("CONTRATO_DO_LEDGER = 2\nif (:\n"))

    def test_migrado_de_verdade_libera(self):
        fonte = ("CONTRATO_DO_LEDGER = 2\n"
                 "ja = {l.get('v') for l in x if publicado(l)}\n"
                 "# o aviso da ficha nao e ledger:\n"
                 "if r.get(\"url\"):\n    pass\n")
        self.assertEqual("", C.postar_migrado(fonte))

    def test_o_postar_de_verdade_e_a_guarda_do_tiktok(self):
        """Pelo LEITOR do postar, e nao so por `metricas.publicado`.

        Uma linha de TikTok curada (url vazio, publicado=true) tem de
        continuar barrando a repostagem. Enquanto o postar.py nao estiver
        migrado, o que tem de valer e o outro lado: o --gravar recusa.
        """
        spec = importlib.util.spec_from_file_location(
            "postar_para_cura", FERRAMENTA.parent / "postar.py")
        postar = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(postar)
        curada = {"video_id": "g1:build:celular", "plataforma": "tiktok",
                  "url": "", "estado_texto": "publicado no TikTok",
                  "publicado": True, "estado": "publicado"}
        real = M.publicados
        M.publicados = lambda canal="builds": [curada]
        self.addCleanup(lambda: setattr(M, "publicados", real))
        if C.postar_migrado() == "":
            self.assertTrue(postar._build_ja_no_tiktok("g1:build:celular"))
        else:
            self.assertFalse(postar._build_ja_no_tiktok("g1:build:celular"),
                             "o postar ja enxerga a linha curada: suba o "
                             "CONTRATO_DO_LEDGER para 2")


POSTAR_MIGRADO = '''
CONTRATO_DO_LEDGER = 2
def _build_ja_no_tiktok(video_id):
    from builds.publicar import metricas
    return any(l.get("video_id") == video_id and metricas.publicado(l)
               and l.get("plataforma") == "tiktok"
               for l in metricas.publicados())
'''
POSTAR_ANTIGO = POSTAR_MIGRADO.replace("metricas.publicado(l)",
                                       "l.get(\"url\")")


class SondaDoLeitor(unittest.TestCase):
    """Item 6: carrega o postar e pergunta, com uma linha curada no lugar do
    ledger, se ela conta como publicada."""

    def _com_postar(self, fonte):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        falso = Path(pasta.name) / "postar.py"
        falso.write_text(fonte, encoding="utf-8")
        real = C.POSTAR
        C.POSTAR = falso
        self.addCleanup(lambda: setattr(C, "POSTAR", real))

    def test_postar_migrado_passa_nas_tres_provas(self):
        self._com_postar(POSTAR_MIGRADO)
        self.assertEqual("", C.postar_migrado())

    def test_leitor_que_ainda_le_o_url_e_recusado_pela_sonda(self):
        # Sem a varredura (que ja pegaria), a sonda sozinha tem de pegar.
        self._com_postar(POSTAR_ANTIGO)
        motivo = C.leitores_entendem_a_cura()
        self.assertIn("_build_ja_no_tiktok", motivo)

    def test_postar_que_quebra_ao_carregar_e_recusado(self):
        self._com_postar("CONTRATO_DO_LEDGER = 2\nraise RuntimeError('x')\n")
        self.assertIn("falhou", C.postar_migrado())

    def test_a_sonda_devolve_os_leitores_de_verdade(self):
        from contos.publicar import serie
        reais = (M.publicados, serie.publicados)
        self._com_postar(POSTAR_ANTIGO)
        C.leitores_entendem_a_cura()
        self.assertEqual(reais, (M.publicados, serie.publicados))


class SondaDosEscritores(unittest.TestCase):
    """Item 5: os tres escritores passam pela trava `ledger__<canal>`."""

    def test_o_codigo_de_hoje_passa(self):
        self.assertEqual("", C.escritores_travados())

    def test_escritor_que_foge_da_trava_e_pego_sem_tocar_no_ledger(self):
        real = M.registrar_publicacao
        registro_real = M.REGISTRO

        def por_fora(video, url, plataforma="youtube", extra=None):
            with open(M.REGISTRO, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"video_id": video.id}) + "\n")

        M.registrar_publicacao = por_fora
        self.addCleanup(lambda: setattr(M, "registrar_publicacao", real))
        antes = (Path(registro_real).read_bytes()
                 if Path(registro_real).is_file() else None)
        motivo = C.escritores_travados()
        self.assertIn("gravou fora", motivo)
        self.assertIn("['historias']", motivo)
        self.assertEqual(registro_real, M.REGISTRO)
        depois = (Path(registro_real).read_bytes()
                  if Path(registro_real).is_file() else None)
        self.assertEqual(antes, depois)

    def test_reconciliar_sem_trava_e_pego(self):
        real = M.reconciliar

        def sem_trava(canal="builds", log=print):
            return 0

        M.reconciliar = sem_trava
        self.addCleanup(lambda: setattr(M, "reconciliar", real))
        self.assertIn("travas pedidas", C.escritores_travados())


class GravacaoSegura(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        self.ledger = self.pasta / "publicados.jsonl"
        self.ledger.write_text(json.dumps(_yt(), ensure_ascii=False) + "\n",
                               encoding="utf-8")
        real = M.registro_do_canal
        M.registro_do_canal = lambda canal="builds": self.ledger
        self.addCleanup(lambda: setattr(M, "registro_do_canal", real))

    def test_linha_escrita_durante_a_cura_nao_se_perde(self):
        # B2: a postagem acrescenta linhas enquanto a cura calcula.
        real = C.calcular_curas
        chamadas = []

        def calcular_e_postar_no_meio(*a, **k):
            if not chamadas:
                with open(self.ledger, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(_yt("g9", "NOVO"),
                                        ensure_ascii=False) + "\n")
            chamadas.append(1)
            return real(*a, **k)

        C.calcular_curas = calcular_e_postar_no_meio
        self.addCleanup(lambda: setattr(C, "calcular_curas", real))
        C.curar_canal("builds", [_video("aaa")], gravar_de_fato=True,
                      carimbo="t1")
        ids = [linha["video_id"] for linha in C.ler(self.ledger)]
        self.assertEqual(["g1:build:celular", "g9"], ids)
        self.assertEqual(2, len(chamadas), "tinha de recalcular")

    def test_ledger_travado_nao_grava(self):
        import contextlib

        @contextlib.contextmanager
        def ocupada(_canal):
            yield False

        real = C.trava_do_ledger
        C.trava_do_ledger = ocupada
        self.addCleanup(lambda: setattr(C, "trava_do_ledger", real))
        antes = self.ledger.read_bytes()
        with self.assertRaises(RuntimeError):
            C.curar_canal("builds", [_video("aaa")], gravar_de_fato=True,
                          carimbo="t2")
        self.assertEqual(antes, self.ledger.read_bytes())

    def test_troca_atomica_nao_deixa_temporario(self):
        # B3: o arquivo e escrito ao lado e trocado de uma vez.
        C.curar_canal("builds", [_video("aaa")], gravar_de_fato=True,
                      carimbo="t3")
        self.assertEqual([], list(self.pasta.glob("*.tmp")))
        self.assertEqual(1, len(list(self.pasta.glob("*.antes-cura-t3"))))


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

    def test_com_flag_e_postar_antigo_recusa(self):
        real = C.postar_migrado
        C.postar_migrado = lambda fonte=None: "o postar ainda le o url"
        self.addCleanup(lambda: setattr(C, "postar_migrado", real))
        antes = self.ledger.read_bytes()
        self.assertEqual(2, C.main(["--canal", "builds", "--gravar"]))
        self.assertEqual(antes, self.ledger.read_bytes())
        self.assertEqual([], list(self.ledger.parent.glob("*.antes-cura-*")))

    def test_com_flag_e_escritor_sem_trava_recusa(self):
        reais = (C.postar_migrado, C.escritores_travados)
        C.postar_migrado = lambda fonte=None: ""
        C.escritores_travados = lambda: "reconciliar sem trava"

        def restaurar():
            C.postar_migrado, C.escritores_travados = reais

        self.addCleanup(restaurar)
        antes = self.ledger.read_bytes()
        self.assertEqual(2, C.main(["--canal", "builds", "--gravar"]))
        self.assertEqual(antes, self.ledger.read_bytes())

    def test_com_flag_grava_e_guarda_copia(self):
        real = C.postar_migrado
        C.postar_migrado = lambda fonte=None: ""
        self.addCleanup(lambda: setattr(C, "postar_migrado", real))
        antes = self.ledger.read_bytes()
        C.main(["--canal", "builds", "--gravar"])
        (copia,) = self.ledger.parent.glob("*.antes-cura-*")
        self.assertEqual(antes, copia.read_bytes())
        (linha,) = C.ler(self.ledger)
        self.assertEqual("aaa", linha["youtube_id"])
        self.assertIs(True, linha["publicado"])


if __name__ == "__main__":
    unittest.main()
