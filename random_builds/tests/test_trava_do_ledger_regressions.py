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
        real_registro = M.REGISTRO
        M.REGISTRO = self.ledger
        self.addCleanup(lambda: setattr(M, "REGISTRO", real_registro))
        self.avisos = []
        real = atividade.registrar
        atividade.registrar = lambda *a, **k: self.avisos.append(a)
        self.addCleanup(lambda: setattr(atividade, "registrar", real))

    def _ocupar(self):
        real = travas.trava
        travas.trava = _ocupada
        self.addCleanup(lambda: setattr(travas, "trava", real))

    def linhas(self):
        if not self.ledger.is_file():
            return []
        return [json.loads(l) for l in
                self.ledger.read_text(encoding="utf-8").splitlines() if l]


class QuemAcrescenta(_Base):

    def test_trava_livre_grava_sem_aviso(self):
        M.acrescentar_ao_ledger(self.ledger, {"video_id": "g1"}, "builds",
                                paciencia=0.1)
        self.assertEqual(["g1"], [l["video_id"] for l in self.linhas()])
        self.assertEqual([], self.avisos)

    def test_trava_ocupada_guarda_pendente_e_avisa(self):
        # Publicacao que aconteceu e nao foi registrada gera repostagem.
        self._ocupar()
        M.acrescentar_ao_ledger(self.ledger,
                                {"video_id": "g1", "plataforma": "tiktok"},
                                "builds", paciencia=0.1)
        self.assertEqual([], self.linhas())
        self.assertEqual(["g1"], [l["video_id"]
                                  for l in M.publicados()])
        (aviso,) = self.avisos
        self.assertEqual(("publicacao", "erro"), aviso[:2])
        self.assertIn("pendente", aviso[2])

    def test_reescrita_incorpora_a_linha_pendente(self):
        self._ocupar()
        M.acrescentar_ao_ledger(self.ledger, {"video_id": "durante"},
                                "builds", paciencia=0.1)
        M.reescrever_ledger(self.ledger, [{"video_id": "antes"}])
        self.assertEqual(["antes", "durante"],
                         [l["video_id"] for l in self.linhas()])
        self.assertEqual([], list(self.ledger.parent.glob(
            "publicados.jsonl.pendentes/*.json")))

    def test_proximo_escritor_com_trava_esvazia_pendentes(self):
        M._guardar_pendente(self.ledger, {"video_id": "antes"})
        M.acrescentar_ao_ledger(self.ledger, {"video_id": "depois"},
                                "builds", paciencia=0.1)
        self.assertEqual(["antes", "depois"],
                         [l["video_id"] for l in self.linhas()])
        self.assertEqual([], list(self.ledger.parent.glob(
            "publicados.jsonl.pendentes/*.json")))

    def _trancar_o_replace(self, falhas: int = 99):
        """`os.replace` sobre o ledger falha `falhas` vezes (o leitor do
        Windows com o arquivo aberto); depois volta a funcionar."""
        real = M.os.replace
        contagem = {"n": 0}

        def trancado(origem, destino):
            if Path(destino) == self.ledger and contagem["n"] < falhas:
                contagem["n"] += 1
                raise PermissionError("ledger aberto para leitura")
            return real(origem, destino)

        M.os.replace = trancado
        self.addCleanup(lambda: setattr(M.os, "replace", real))
        return contagem

    def test_replace_trancado_guarda_a_linha_nova_como_pendente(self):
        """Leitor do Windows nao pode fazer publicacao sumir do ledger.

        Auditoria de 11/10/2026 (prova3): ledger com 1 linha, 1 pendente, um
        leitor com o arquivo aberto -> `acrescentar_ao_ledger` levantava
        `PermissionError`, a NOVA nao estava em lugar nenhum e um `.tmp`
        ficava orfao na pasta. Agora: a nova vai para a fila lateral, o
        ledger no disco fica como estava, zero `.tmp`, e o diario ganha o
        erro.
        """
        M._guardar_pendente(self.ledger, {"video_id": "antes"})
        contagem = self._trancar_o_replace()
        M.acrescentar_ao_ledger(self.ledger, {"video_id": "nova"}, "builds")
        self.assertEqual(["antes", "nova"],
                         sorted(l["video_id"] for l in M.publicados()))
        self.assertEqual([], list(self.ledger.parent.glob("*.tmp")))
        self.assertEqual([], self.linhas(), "o disco nao mudou")
        self.assertEqual(3, contagem["n"], "tentou 3 vezes antes de desistir")
        (aviso,) = self.avisos
        self.assertEqual(("publicacao", "erro"), aviso[:2])
        self.assertIn("nova", aviso[2])

    def test_replace_que_destranca_na_segunda_tentativa_grava(self):
        M._guardar_pendente(self.ledger, {"video_id": "antes"})
        self._trancar_o_replace(falhas=1)
        M.acrescentar_ao_ledger(self.ledger, {"video_id": "nova"}, "builds")
        self.assertEqual(["antes", "nova"], [l["video_id"] for l in self.linhas()])
        self.assertEqual([], list(self.ledger.parent.glob(
            "publicados.jsonl.pendentes/*.json")))
        self.assertEqual([], self.avisos)

    def test_reescrever_trancado_devolve_False_e_deixa_as_pendentes(self):
        M._guardar_pendente(self.ledger, {"video_id": "pendente"})
        self._trancar_o_replace()
        self.assertFalse(M.reescrever_ledger(self.ledger, [{"video_id": "x"}]))
        self.assertEqual(1, len(list(self.ledger.parent.glob(
            "publicados.jsonl.pendentes/*.json"))), "a pendente FICA")
        self.assertEqual([], list(self.ledger.parent.glob("*.tmp")))

    def test_registrar_publicado_que_falha_vai_ao_diario_e_nao_so_ao_print(self):
        """Nos builds `registrar_publicado` engolia tudo com `print`: a
        publicacao "deu certo" sem linha no ledger e sem linha no diario
        (prova3 da auditoria: `registrar_publicado -> None | linhas no
        diario: 0`)."""
        real = M.registrar_publicacao
        M.registrar_publicacao = lambda *a, **k: (_ for _ in ()).throw(
            PermissionError("ledger aberto"))
        self.addCleanup(lambda: setattr(M, "registrar_publicacao", real))
        video = type("V", (), {"id": "g1", "titulo": "T"})()
        self.assertIsNone(M.registrar_publicado(video, "https://youtu.be/x",
                                                canal="builds"))
        (aviso,) = self.avisos
        self.assertEqual(("publicacao", "erro"), aviso[:2])
        self.assertIn("PermissionError", aviso[2])


class Reconciliacao(_Base):
    """O id que vem do canal depois e prova de que o video subiu (11/10/2026).

    Maquina.md item 7: 49 linhas de historias com `prova_ok=False` nos 30
    dias (o laudo saiu com `youtube_id=""`, o id veio do canal depois) — a
    reconciliacao preenchia o id e deixava `prova_ok` falso para sempre.
    """

    def setUp(self):
        super().setUp()
        real = M.registro_do_canal
        M.registro_do_canal = lambda canal="builds": self.ledger
        self.addCleanup(lambda: setattr(M, "registro_do_canal", real))
        for nome, valor in (("_token", lambda canal="builds": ("tok", None)),
                            ("conferir_lista", lambda lista: None)):
            original = getattr(M, nome)
            setattr(M, nome, valor)
            self.addCleanup(setattr, M, nome, original)

    def _canal(self, *videos):
        real = M.enviados
        M.enviados = lambda token, quantos=None: list(videos)
        self.addCleanup(lambda: setattr(M, "enviados", real))

    def test_id_do_canal_vira_prova_ok(self):
        no_ar = "2026-10-07T15:38:00Z"
        quando = M._instante(no_ar).isoformat(timespec="seconds")
        M.acrescentar_ao_ledger(self.ledger, {
            "video_id": "historia_00063:celular:p01", "plataforma": "youtube",
            "titulo": "A Pasta Verde (Parte 1/4)", "quando": quando,
            "youtube_id": None, "prova_ok": False,
            "prova": [{"estado": "publicado", "youtube_id": ""}]}, "builds")
        self._canal({"youtube_id": "abc123", "titulo": "A Pasta Verde (Parte 1/4)",
                     "publicado_em": no_ar})
        self.assertEqual(1, M.reconciliar("builds", log=lambda *_: None))
        (linha,) = self.linhas()
        self.assertEqual("abc123", linha["youtube_id"])
        self.assertIs(True, linha["prova_ok"])

    def test_sem_id_no_canal_a_prova_fica_como_estava(self):
        M.acrescentar_ao_ledger(self.ledger, {
            "video_id": "h:p1", "plataforma": "youtube", "titulo": "T",
            "quando": "2026-10-07T15:38:00", "prova_ok": False}, "builds")
        self._canal()
        self.assertEqual(0, M.reconciliar("builds", log=lambda *_: None))
        (linha,) = self.linhas()
        self.assertIs(False, linha["prova_ok"])

    def test_reescrita_trancada_nao_diz_reconciliado(self):
        no_ar = "2026-10-07T15:38:00Z"
        quando = M._instante(no_ar).isoformat(timespec="seconds")
        M.acrescentar_ao_ledger(self.ledger, {
            "video_id": "h:p1", "plataforma": "youtube", "titulo": "T",
            "quando": quando}, "builds")
        self._canal({"youtube_id": "abc", "titulo": "T", "publicado_em": no_ar})
        QuemAcrescenta._trancar_o_replace(self)
        falas = []
        self.assertEqual(0, M.reconciliar("builds", log=falas.append))
        self.assertIsNone(self.linhas()[0].get("youtube_id"))
        self.assertTrue(any("proxima reconciliacao" in f for f in falas), falas)

    def test_reconciliacao_le_a_pendente_e_nao_a_duplica(self):
        """`publicados()` ja traz a pendente; reescrever nao pode repeti-la."""
        M.acrescentar_ao_ledger(self.ledger, {"video_id": "antes", "plataforma": "youtube",
                                              "quando": "2026-10-11T09:00:00"}, "builds")
        M._guardar_pendente(self.ledger, {"video_id": "durante", "plataforma": "youtube",
                                          "quando": "2026-10-11T09:40:00"})
        linhas = M.publicados("builds")
        linhas[-1]["youtube_id"] = "abc"          # a reconciliacao completou o id
        M.reescrever_ledger(self.ledger, linhas)
        self.assertEqual([("antes", None), ("durante", "abc")],
                         [(l["video_id"], l.get("youtube_id")) for l in self.linhas()])

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
