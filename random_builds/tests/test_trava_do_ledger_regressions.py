# -*- coding: utf-8 -*-
"""A trava do ledger: quem acrescenta nunca perde a linha; quem reescreve
desiste.

16/09/2026: a cura e a reconciliacao reescrevem o ledger inteiro, e a
postagem acrescenta linhas a cada horario. Sem uma trava comum, a linha
acrescentada no meio de uma reescrita some — e publicacao que sumiu do
ledger vira REPOSTAGEM. Por isso a regra e assimetrica.

Nada toca a rede nem o ledger de verdade.
"""
import contextlib
import json
import tempfile
import unittest
from pathlib import Path

from builds import atividade, travas
from builds.publicar import metricas as M


@contextlib.contextmanager
def _ocupada(_nome, esperar=0.0):
    yield False


class _Base(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ledger = Path(self._tmp.name) / "publicados.jsonl"
        self.avisos = []
        real = atividade.registrar
        atividade.registrar = lambda *a, **k: self.avisos.append(a)
        self.addCleanup(lambda: setattr(atividade, "registrar", real))

    def _ocupar(self):
        real = travas.trava
        travas.trava = _ocupada
        self.addCleanup(lambda: setattr(travas, "trava", real))

    def linhas(self):
        return [json.loads(l) for l in
                self.ledger.read_text(encoding="utf-8").splitlines() if l]


class QuemAcrescenta(_Base):

    def test_trava_livre_grava_sem_aviso(self):
        M.acrescentar_ao_ledger(self.ledger, {"video_id": "g1"}, "builds",
                                paciencia=0.1)
        self.assertEqual(["g1"], [l["video_id"] for l in self.linhas()])
        self.assertEqual([], self.avisos)

    def test_trava_ocupada_grava_mesmo_assim_e_avisa(self):
        # Publicacao que aconteceu e nao foi registrada gera repostagem.
        self._ocupar()
        M.acrescentar_ao_ledger(self.ledger,
                                {"video_id": "g1", "plataforma": "tiktok"},
                                "builds", paciencia=0.1)
        self.assertEqual(["g1"], [l["video_id"] for l in self.linhas()])
        (aviso,) = self.avisos
        self.assertEqual(("publicacao", "erro"), aviso[:2])
        self.assertIn("SEM a trava", aviso[2])

    def test_o_escritor_de_builds_usa_a_trava(self):
        real = M.REGISTRO
        M.REGISTRO = self.ledger
        self.addCleanup(lambda: setattr(M, "REGISTRO", real))
        usadas = []
        original = travas.trava

        @contextlib.contextmanager
        def espia(nome, esperar=0.0):
            usadas.append((nome, esperar))
            with original(nome, esperar=0.0) as minha:
                yield minha

        travas.trava = espia
        self.addCleanup(lambda: setattr(travas, "trava", original))
        video = type("V", (), {"id": "g1", "titulo": "T"})()
        M.registrar_publicacao(video, "https://youtu.be/x")
        self.assertEqual([("ledger__builds", M.PACIENCIA_DO_ESCRITOR)], usadas)

    def test_o_escritor_das_historias_usa_a_mesma_funcao(self):
        from contos.publicar import serie
        chamadas = []
        real_reg, real_fn = serie.REGISTRO, M.acrescentar_ao_ledger
        serie.REGISTRO = self.ledger
        M.acrescentar_ao_ledger = lambda caminho, linha, canal, **k: (
            chamadas.append(canal))
        self.addCleanup(lambda: setattr(serie, "REGISTRO", real_reg))
        self.addCleanup(lambda: setattr(M, "acrescentar_ao_ledger", real_fn))
        video = type("V", (), {"id": "h1:celular:p01", "fonte_id": "h1",
                               "parte": 1, "partes": 6, "titulo": "T"})()
        serie.registrar(video, "publicado no TikTok", "tiktok", None)
        self.assertEqual(["historias"], chamadas)


class QuemReescreve(_Base):

    def setUp(self):
        super().setUp()
        self.ledger.write_text(json.dumps(
            {"video_id": "g1", "plataforma": "youtube", "titulo": "O MAGO",
             "url": "publicado no YouTube", "youtube_id": None,
             "quando": "2026-09-16T09:42:20"}) + "\n", encoding="utf-8")
        reais = (M.REGISTRO, M._token, M.enviados)
        M.REGISTRO = self.ledger
        M._token = lambda canal="builds": ("t", None)
        M.enviados = lambda token, quantos=200: [
            {"youtube_id": "aaa", "titulo": "O MAGO",
             "publicado_em": M._instante("2026-09-16T09:42:08")
             .astimezone().isoformat()}]

        def restaurar():
            M.REGISTRO, M._token, M.enviados = reais

        self.addCleanup(restaurar)

    def test_reconciliar_desiste_com_a_trava_ocupada(self):
        self._ocupar()
        antes = self.ledger.read_bytes()
        self.assertEqual(0, M.reconciliar("builds", log=lambda *_a: None))
        self.assertEqual(antes, self.ledger.read_bytes())

    def test_linha_acrescentada_durante_a_consulta_nao_some(self):
        # A postagem escreve enquanto a lista do canal e baixada.
        baixar = M.enviados

        def baixar_e_postar(token, quantos=200):
            with open(self.ledger, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"video_id": "g2", "plataforma": "tiktok",
                                     "url": "publicado no TikTok"}) + "\n")
            return baixar(token, quantos)

        M.enviados = baixar_e_postar
        self.assertEqual(1, M.reconciliar("builds", log=lambda *_a: None))
        linhas = self.linhas()
        self.assertEqual(["g1", "g2"], [l["video_id"] for l in linhas])
        self.assertEqual("aaa", linhas[0]["youtube_id"])

    def test_reescrita_e_atomica(self):
        M.reconciliar("builds", log=lambda *_a: None)
        self.assertEqual([], list(self.ledger.parent.glob("*.tmp")))


class ACuraUsaOMesmoNome(unittest.TestCase):

    def test_mesma_trava_da_cura(self):
        import importlib.util
        caminho = (Path(__file__).resolve().parents[2] / "ferramentas"
                   / "curar_ledger.py")
        spec = importlib.util.spec_from_file_location("cura_trava", caminho)
        cura = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cura)
        usadas = []
        original = travas.trava

        @contextlib.contextmanager
        def espia(nome, esperar=0.0):
            usadas.append(nome)
            yield True

        travas.trava = espia
        self.addCleanup(lambda: setattr(travas, "trava", original))
        with cura.trava_do_ledger("historias"):
            pass
        self.assertEqual([M.nome_da_trava("historias")], usadas)


if __name__ == "__main__":
    unittest.main()
