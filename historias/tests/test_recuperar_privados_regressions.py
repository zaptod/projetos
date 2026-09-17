"""A fila da recuperacao: o que o canal diz E o que o projeto sabe.

`builds.publicar.recuperar` responde "quais videos do CANAL fazem sentido" —
titulo sem gemeo publico, processado, com descricao. Este arquivo trava os
crivos que so o projeto conhece, e o que a rodada faz com eles.

O acontecimento vai para o DIARIO e nunca para o ledger: 14 dos 16 ja tem
linha dizendo "publicado no YouTube" com o id certo — foi ela que permitiu
achar o video no canal. Uma segunda linha contaria a mesma publicacao duas
vezes em toda estatistica, e a cura do ledger passaria a ver duplicata onde
ha conserto.
"""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "postar_recuperar", RAIZ / "ferramentas" / "postar.py")
postar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(postar)

from builds.publicar import recuperar  # noqa: E402


def _no_canal(vid, titulo, quando="2026-09-10T10:00:00"):
    return {"id": vid, "titulo": titulo, "descricao": "uma descricao",
            "quando": quando, "privacidade": "private", "upload": "processed",
            "duracao": "PT1M19S"}


def _no_ledger(youtube_id, video_id, fonte_id=None, quando="2026-09-10T10:08"):
    return {"plataforma": "youtube", "youtube_id": youtube_id,
            "video_id": video_id, "fonte_id": fonte_id or video_id.split(":")[0],
            "url": "publicado no YouTube", "quando": quando,
            "titulo": "t"}


class FilaTests(unittest.TestCase):
    def setUp(self):
        self.diario = []
        for nome in ("_publicados_do_canal", "a_conferir_no_tiktok",
                     "_fontes_cheias_hoje"):
            self.addCleanup(setattr, postar, nome, getattr(postar, nome))
        postar.a_conferir_no_tiktok = lambda _c, _p="tiktok": set()
        postar._fontes_cheias_hoje = lambda _p, _pl="tiktok": set()

    def _montar(self, no_canal, ledger):
        postar._publicados_do_canal = lambda _c: list(ledger)
        return patch.object(recuperar, "videos_do_canal",
                            lambda _c=None, _t=None: list(no_canal))

    def test_o_privado_conhecido_entra_com_o_id_do_projeto(self):
        with self._montar([_no_canal("yt1", "Brutus build 69/100")],
                          [_no_ledger("yt1", "generation_00006:build:celular")]):
            fila = postar.privados_no_youtube("builds")
        self.assertEqual(1, len(fila))
        self.assertEqual("generation_00006:build:celular", fila[0]["video_id"])
        self.assertEqual("generation_00006", fila[0]["fonte_id"])

    def test_o_privado_FORA_do_ledger_ainda_entra(self):
        """Ele existe no canal e esta parado; nao saber de que build veio nao
        e razao para deixa-lo privado para sempre."""
        with self._montar([_no_canal("solto", "Alguem build 50/100")], []):
            fila = postar.privados_no_youtube("builds")
        self.assertEqual(["solto"], [v["id"] for v in fila])
        self.assertEqual("", fila[0]["video_id"])

    def test_quem_espera_CONFERENCIA_nao_volta_sozinho(self):
        """A marca existe porque alguem tem de olhar. Torna-lo publico por
        conta propria e decidir justamente o que a marca adiou."""
        postar.a_conferir_no_tiktok = (
            lambda _c, _p="tiktok": {"generation_00006:build:celular"})
        with self._montar([_no_canal("yt1", "Brutus build 69/100")],
                          [_no_ledger("yt1", "generation_00006:build:celular")]):
            self.assertEqual([], postar.privados_no_youtube("builds"))

    def test_a_marca_do_CORTE_bloqueia_o_inteiro(self):
        postar.a_conferir_no_tiktok = (
            lambda _c, _p="tiktok": {"generation_00006:build:celular:corte01"})
        with self._montar([_no_canal("yt1", "Brutus build 69/100")],
                          [_no_ledger("yt1", "generation_00006:build:celular")]):
            self.assertEqual([], postar.privados_no_youtube("builds"))

    def test_nao_conseguir_ler_a_lista_de_bloqueados_ESVAZIA(self):
        """Falha fechada: tornar publico e irreversivel na pratica, porque o
        publico ja viu."""
        def explode(_c, _p="tiktok"):
            raise RuntimeError("lista ilegivel")
        postar.a_conferir_no_tiktok = explode
        with self._montar([_no_canal("yt1", "Brutus build 69/100")],
                          [_no_ledger("yt1", "generation_00006:build:celular")]):
            self.assertEqual([], postar.privados_no_youtube("builds"))

    def test_o_teto_por_fonte_vale_igual(self):
        """Recuperar quatro partes da mesma fonte de uma vez e a mesma
        enxurrada que o teto existe para evitar — e o publico nao distingue
        "recuperado" de "postado"."""
        postar._fontes_cheias_hoje = lambda _p, _pl="tiktok": {"generation_00006"}
        with self._montar([_no_canal("yt1", "Brutus build 69/100")],
                          [_no_ledger("yt1", "generation_00006:build:celular")]):
            self.assertEqual([], postar.privados_no_youtube("builds"))

    def test_o_teto_e_perguntado_ao_YOUTUBE(self):
        """O teto vale por destino, e aqui o destino e o YouTube. Perguntar
        pelo TikTok deixaria passar o que ja saiu de mais no canal certo."""
        vistos = []
        postar._fontes_cheias_hoje = (
            lambda _p, _pl="tiktok": vistos.append(_pl) or set())
        with self._montar([_no_canal("yt1", "Brutus build 69/100")],
                          [_no_ledger("yt1", "generation_00006:build:celular")]):
            postar.privados_no_youtube("builds")
        self.assertEqual(["youtube"], vistos)


class RodadaTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, postar, "privados_no_youtube",
                        postar.privados_no_youtube)
        self.addCleanup(setattr, postar, "_anotar_no_diario",
                        postar._anotar_no_diario)
        self.diario = []
        postar._anotar_no_diario = (
            lambda canal, texto, ref="", atividade_erro=False:
            self.diario.append((canal, texto, ref, atividade_erro)))
        self.alvo = dict(_no_canal("yt1", "Brutus build 69/100"),
                         video_id="generation_00006:build:celular",
                         fonte_id="generation_00006")
        postar.privados_no_youtube = lambda _c="builds", limite=40: [self.alvo]

    def _rodar(self, resultado=None, erro=None):
        def tornar(vid, canal="builds", token=None):
            if erro:
                raise erro
            return resultado
        with patch.object(recuperar, "tornar_publico", tornar):
            return postar.recuperar_no_youtube(canal="builds")

    def test_um_por_rodada(self):
        postar.privados_no_youtube = (
            lambda _c="builds", limite=40: [self.alvo, dict(self.alvo, id="y2")])
        r = self._rodar({"id": "yt1", "antes": "private", "depois": "public",
                         "mudou": True, "motivo": ""})
        self.assertTrue(r["feito"])
        self.assertEqual("yt1", r["alvo"])
        self.assertEqual(2, r["fila"], "a fila inteira aparece no relatorio")

    def test_o_sucesso_vai_para_o_DIARIO(self):
        self._rodar({"id": "yt1", "antes": "private", "depois": "public",
                     "mudou": True, "motivo": ""})
        self.assertEqual(1, len(self.diario))
        canal, texto, ref, erro = self.diario[0]
        self.assertFalse(erro)
        self.assertIn("yt1", ref)
        self.assertIn("generation_00006:build:celular", texto)

    def test_nao_grava_linha_nova_no_LEDGER(self):
        """As 14 linhas que ja existem dizem "publicado no YouTube" com o id
        certo. Uma segunda contaria a mesma publicacao duas vezes, e a cura
        do ledger veria duplicata onde ha conserto."""
        import inspect
        fonte = inspect.getsource(postar.recuperar_no_youtube)
        for proibido in ("registrar_publicado", "registrar_publicacao",
                         "acrescentar_ao_ledger"):
            self.assertNotIn(proibido, fonte)

    def test_200_sem_mudanca_vira_ERRO_e_nao_sucesso(self):
        r = self._rodar({"id": "yt1", "antes": "private", "depois": "private",
                         "mudou": False, "motivo": "o canal diz 'private'"})
        self.assertFalse(r["feito"])
        self.assertTrue(self.diario[0][3], "tinha de ser ERRO no diario")

    def test_falha_NAO_derruba_a_rodada(self):
        r = self._rodar(erro=RuntimeError("rede fora"))
        self.assertFalse(r["feito"])
        self.assertIn("rede fora", r["motivo"])
        self.assertTrue(self.diario[0][3])

    def test_falta_de_escopo_diz_o_comando_e_nao_explode(self):
        def explode(_c="builds", limite=40):
            raise recuperar.FaltaEscopo(
                recuperar.COMO_AUTORIZAR.format(escopo="x", conta="y"))
        postar.privados_no_youtube = explode
        r = postar.recuperar_no_youtube(canal="builds")
        self.assertFalse(r["feito"])
        self.assertIn("--com-edicao", r["detalhe"])

    def test_desligada_nao_faz_nada(self):
        self.addCleanup(setattr, postar, "RECUPERACAO_YOUTUBE_LIGADA", True)
        postar.RECUPERACAO_YOUTUBE_LIGADA = False
        r = postar.recuperar_no_youtube(canal="builds")
        self.assertFalse(r["feito"])
        self.assertIn("desligada", r["motivo"])

    def test_so_ver_nao_muda_nada(self):
        def nunca(*_a, **_k):
            raise AssertionError("--ver nao pode tocar no canal")
        with patch.object(recuperar, "tornar_publico", nunca):
            r = postar.recuperar_no_youtube(so_ver=True, canal="builds")
        self.assertFalse(r["feito"])
        self.assertEqual("yt1", r["veria"])
        self.assertEqual([], self.diario)


if __name__ == "__main__":
    unittest.main()
