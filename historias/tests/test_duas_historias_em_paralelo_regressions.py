# -*- coding: utf-8 -*-
"""Duas historias ao mesmo tempo, uma em cada gerador (06/10/2026).

Decisao do Adrian no Grimorio (`historias/imagens-dois-geradores-juntos` =
"Duas historias ao mesmo tempo, uma em cada gerador"): sem o PicassoIA a
fabrica fazia ~1 parte/h, porque a rodada fazia uma historia por vez com UM
gerador (o rosto nao muda no meio: `imagens-divisao`) e so uma conta
trabalhava. Medido no correio (8 dias): Gemini ~20 imagens/h, ChatGPT
~15-30/h.

O que se guarda aqui:
- `faixas()`: desligado por padrao; ligado = os geradores da roda, ate 2;
- o worker numa FAIXA so pede ao gerador dela: historia sem dono passa a ser
  dele, historia do outro levanta `OutraFaixa`, e a cena que falha 2x NAO cai
  na conta da outra faixa (fora da faixa, a queda para o proximo continua);
- a POSSE de uma historia entre as faixas (incompleta, conserto, nascimento);
- o id novo sem corrida (`reservar_id`);
- o supervisor: lanca uma faixa por gerador, relanca a que terminou enquanto a
  outra trabalha, e respeita a trava de sempre (`historias__auto`);
- so a faixa do Gemini faz o servico do dia e o parecer do estoque.

Sem navegador e sem processo de verdade: entregador, `lancar` e travas sao
dubles; o OUTPUTS e o correio vao para uma pasta temporaria.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from contos.imagens import fila, worker
from contos.pipeline import agenda, reparo
from contos.roteiro import roteiro
from ias import correio

LIGADO = {"ligado": True, "maximo": 2, "relancar_min": 60, "vigiar_s": 30}


def _png(semente: int = 1) -> bytes:
    import numpy as np
    from PIL import Image
    gerador = np.random.default_rng(semente)
    pixels = gerador.integers(0, 256, size=(341, 192), dtype=np.uint8)
    saida = io.BytesIO()
    Image.fromarray(pixels, mode="L").convert("RGB").save(saida, format="PNG")
    return saida.getvalue()


class _Base(unittest.TestCase):

    def _trocar(self, alvo, nome, valor):
        self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
        setattr(alvo, nome, valor)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name)
        self.imagens = {"geradores_imagem": ["gemini", "chatgpt"],
                        "divisao": "por-historia", "aspect": "9:16",
                        "reescrever_com_llm": False, "suavizacao_max": 0}
        self._trocar(fila, "OUTPUTS", self.raiz / "outputs")
        self._trocar(fila, "carregar_config", lambda: dict(self.imagens))


# ------------------------------------------------------------------ config
class FaixasDoConfig(_Base):

    def test_o_config_real_vem_desligado(self):
        """Ligar e decisao de quem confere: o arquivo sai com `ligado: false`."""
        dados = json.loads((agenda.CONFIG).read_text(encoding="utf-8-sig"))
        self.assertIn("paralelo_por_gerador", dados)
        self.assertFalse(dados["paralelo_por_gerador"]["ligado"])
        self.assertEqual(2, dados["paralelo_por_gerador"]["maximo"])
        self.assertEqual([], agenda.faixas(dados))

    def test_ligado_sao_os_geradores_da_roda(self):
        self.assertEqual(["gemini", "chatgpt"],
                         agenda.faixas({"paralelo_por_gerador": LIGADO}))

    def test_casos_que_desligam(self):
        config = {"paralelo_por_gerador": LIGADO}
        self.imagens["geradores_imagem"] = ["gemini"]
        self.assertEqual([], agenda.faixas(config), "um gerador so")
        self.imagens["geradores_imagem"] = ["gemini", "chatgpt", "picasso"]
        self.assertEqual(["gemini", "chatgpt"], agenda.faixas(config),
                         "o maximo e 2")
        self.imagens["divisao"] = "por-cena"
        self.assertEqual([], agenda.faixas(config), "por-cena nao tem dono")
        self.assertEqual([], agenda.faixas({}))
        self.assertEqual([], agenda.faixas({"paralelo_por_gerador": True}))

    def test_so_a_faixa_do_gemini_faz_servico_e_parecer(self):
        self._trocar(agenda, "_gerador_pronto", lambda _g: "")
        base = {"paralelo_por_gerador": LIGADO}
        self.assertTrue(agenda._da_casa(base), "fora do paralelo, sempre")
        self.assertTrue(agenda._da_casa({**base, "faixa_de_imagem": "gemini"}))
        self.assertFalse(agenda._da_casa({**base, "faixa_de_imagem": "chatgpt"}))

    def test_gemini_parado_passa_o_servico_a_outra_faixa(self):
        self._trocar(agenda, "_gerador_pronto",
                     lambda g: "fora de cota" if g == "gemini" else "")
        base = {"paralelo_por_gerador": LIGADO}
        self.assertFalse(agenda._da_casa({**base, "faixa_de_imagem": "gemini"}))
        self.assertTrue(agenda._da_casa({**base, "faixa_de_imagem": "chatgpt"}))


# --------------------------------------------------------------------- id
class IdSemCorrida(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(setattr, roteiro, "OUTPUTS", roteiro.OUTPUTS)
        roteiro.OUTPUTS = Path(tmp.name)

    def test_dois_pedidos_dois_ids_com_a_pasta_criada(self):
        a, b = roteiro.reservar_id(), roteiro.reservar_id()
        self.assertEqual(("historia_00001", "historia_00002"), (a, b))
        self.assertTrue((roteiro.OUTPUTS / a).is_dir())

    def test_quem_perde_a_corrida_tira_o_seguinte(self):
        """A outra faixa criou a pasta entre o `proximo_id` e o `mkdir`."""
        (roteiro.OUTPUTS / "historia_00007").mkdir()
        sequencia = iter(["historia_00007", "historia_00008"])
        self.addCleanup(setattr, roteiro, "proximo_id", roteiro.proximo_id)
        roteiro.proximo_id = lambda: next(sequencia)
        self.assertEqual("historia_00008", roteiro.reservar_id())


# ----------------------------------------------------------------- worker
class WorkerNaFaixa(_Base):

    def setUp(self):
        super().setUp()
        anterior = os.environ.get("NF_IAS_PASTA")
        os.environ["NF_IAS_PASTA"] = str(self.raiz / "correio")
        self.addCleanup(lambda: os.environ.__setitem__("NF_IAS_PASTA", anterior)
                        if anterior is not None
                        else os.environ.pop("NF_IAS_PASTA", None))
        self.ordem = ["gemini", "chatgpt"]
        self._trocar(worker, "_ordem_de_geradores", lambda _cfg: list(self.ordem))
        self._trocar(worker._rb_atividade, "registrar", lambda *a, **k: None)
        self._trocar(roteiro, "carregar", lambda _id: {
            "titulo": "Teste", "protagonista": "", "partes": [{"n": 1, "cenas": [
                {"n": 1, "imagem": "scene 1", "tempo": 4, "narracao": "texto"},
                {"n": 2, "imagem": "scene 2", "tempo": 4, "narracao": "texto"}]}]})
        self.falha_em = set()

    def entregador(self, chamadas):
        def entregar(pedido, _prazo):
            chamadas.append(dict(pedido))
            gerador = pedido["para"]
            if gerador in self.falha_em:
                return correio.atualizar(gerador, pedido["id"], situacao="falhou",
                                         erro="nao respondeu", categoria="erro")
            pasta = correio.pasta_imagens(gerador)
            pasta.mkdir(parents=True, exist_ok=True)
            (pasta / f"{pedido['id']}.png").write_bytes(_png(len(chamadas)))
            (pasta / f"{pedido['id']}.prova.json").write_text(
                json.dumps({"prova": {"comprovada": True, "forca": "duble"}}),
                encoding="utf-8")
            return correio.atualizar(gerador, pedido["id"], situacao="respondida",
                                     gerador=gerador,
                                     imagem={"arquivo": f"{pedido['id']}.png",
                                             "prova": "turno do duble"})
        return entregar

    def _gerar(self, chamadas, linhas=None):
        return worker.gerar("historia_teste", entregador=self.entregador(chamadas),
                            log=(linhas.append if linhas is not None
                                 else lambda _m: None))

    def test_historia_sem_dono_vira_da_faixa(self):
        """Pelo rodizio iria ao gemini; na faixa do chatgpt, e do chatgpt."""
        chamadas = []
        with worker.na_faixa("chatgpt"):
            saida = self._gerar(chamadas)
        self.assertEqual(2, saida["geradas"])
        self.assertEqual({"chatgpt"}, {c["para"] for c in chamadas})
        self.assertEqual("chatgpt", fila.gerador_da_historia("historia_teste"))
        self.assertEqual("", worker.faixa_atual(), "a faixa e devolvida")

    def test_historia_da_outra_faixa_nao_gera_nada(self):
        fila.definir_gerador_da_historia("historia_teste", "gemini")
        chamadas = []
        with worker.na_faixa("chatgpt"):
            with self.assertRaises(worker.OutraFaixa):
                self._gerar(chamadas)
        self.assertEqual([], chamadas)
        self.assertTrue(issubclass(worker.OutraFaixa, worker.NaoRodou),
                        "o reparo adia NaoRodou sem gastar tentativa")

    def test_cena_que_falha_nao_cai_na_conta_da_outra_faixa(self):
        self.falha_em = {"gemini"}
        chamadas = []
        with worker.na_faixa("gemini"):
            saida = self._gerar(chamadas)
        self.assertEqual({"gemini"}, {c["para"] for c in chamadas})
        self.assertEqual(0, saida["geradas"])
        self.assertEqual(2, saida["faltam"])
        self.assertEqual("gemini", fila.gerador_da_historia("historia_teste"))

    def test_fora_da_faixa_a_queda_para_o_proximo_continua(self):
        """O comportamento de sempre (uma historia por vez) nao muda."""
        self.falha_em = {"gemini"}
        chamadas = []
        saida = self._gerar(chamadas)
        self.assertEqual(2, saida["geradas"])
        self.assertIn("chatgpt", {c["para"] for c in chamadas})

    def test_gerador_da_faixa_fora_de_cota_nao_rodou(self):
        self.ordem = ["chatgpt"]
        with worker.na_faixa("gemini"):
            with self.assertRaises(worker.NaoRodou):
                self._gerar([])

    def test_fixada_no_picasso_passa_a_faixa(self):
        fila.definir_gerador_da_historia("historia_teste", "picasso")
        chamadas, linhas = [], []
        with worker.na_faixa("chatgpt"):
            self._gerar(chamadas, linhas)
        self.assertEqual({"chatgpt"}, {c["para"] for c in chamadas})
        self.assertEqual("chatgpt", fila.gerador_da_historia("historia_teste"))
        self.assertTrue(any("saiu da roda" in linha for linha in linhas))

    def test_dono_das_imagens(self):
        roda = ["gemini", "chatgpt"]
        self.assertEqual("", fila.dono_das_imagens("historia_teste", roda))
        fila.definir_gerador_da_historia("historia_teste", "picasso")
        self.assertEqual("", fila.dono_das_imagens("historia_teste", roda))
        fila.definir_gerador_da_historia("historia_teste", "chatgpt")
        self.assertEqual("chatgpt", fila.dono_das_imagens("historia_teste", roda))
        dados = fila._meta("historia_outra")
        dados["cenas"] = {"1:1": {"gerador": "gemini"}, "1:2": {"gerador": "gemini"}}
        fila._gravar_meta("historia_outra", dados)
        self.assertEqual("gemini", fila.dono_das_imagens("historia_outra", roda))


# ------------------------------------------------------------------- posse
class PosseDaHistoria(_Base):
    """A posse e a trava DE VERDADE (pasta de runtime dos testes)."""

    def setUp(self):
        super().setUp()
        self.config = {"paralelo_por_gerador": LIGADO,
                       "faixa_de_imagem": "gemini"}
        self.prefixo = f"teste_{os.getpid()}_{id(self)}"
        self._trocar(agenda, "trava_da_historia",
                     lambda h: f"{self.prefixo}__{h}")

    @contextlib.contextmanager
    def _outra_faixa_segura(self, historia_id):
        """Outra thread = outro dono do arquivo (a trava e reentrante so na
        mesma thread), como o processo da outra faixa."""
        from builds import travas
        pegou, soltar = threading.Event(), threading.Event()

        def segurar():
            with travas.trava(agenda.trava_da_historia(historia_id)) as minha:
                self.assertTrue(minha)
                pegou.set()
                soltar.wait(10)

        fio = threading.Thread(target=segurar)
        fio.start()
        pegou.wait(10)
        try:
            yield
        finally:
            soltar.set()
            fio.join(10)

    def test_a_faixa_pega_a_primeira_que_pode_ser_dela(self):
        fila.definir_gerador_da_historia("h_chatgpt", "chatgpt")
        pendentes = [
            {"historia_id": "h_chatgpt", "partes_sem_texto": [3]},
            {"historia_id": "h_ocupada", "imagens_faltando": 4,
             "partes_sem_video": []},
            {"historia_id": "h_livre", "imagens_faltando": 2,
             "partes_sem_video": [1]},
        ]
        linhas = []
        with self._outra_faixa_segura("h_ocupada"):
            with contextlib.ExitStack() as pilha:
                alvo = agenda._escolher_incompleta(pendentes, self.config,
                                                   pilha, linhas.append)
        self.assertEqual("h_livre", alvo["historia_id"])
        self.assertTrue(any("h_chatgpt e do chatgpt" in l for l in linhas))
        self.assertTrue(any("h_ocupada esta com a outra faixa" in l
                            for l in linhas))

    def test_truncada_vem_antes_tambem_na_faixa(self):
        pendentes = [{"historia_id": "h_imagem", "imagens_faltando": 2,
                      "partes_sem_video": []},
                     {"historia_id": "h_texto", "partes_sem_texto": [2]}]
        with contextlib.ExitStack() as pilha:
            alvo = agenda._escolher_incompleta(pendentes, self.config, pilha,
                                               lambda _m: None)
        self.assertEqual("h_texto", alvo["historia_id"])

    def test_nada_que_seja_dela(self):
        fila.definir_gerador_da_historia("h1", "chatgpt")
        with contextlib.ExitStack() as pilha:
            alvo = agenda._escolher_incompleta(
                [{"historia_id": "h1", "imagens_faltando": 1,
                  "partes_sem_video": []}], self.config, pilha, lambda _m: None)
        self.assertIsNone(alvo)

    def test_fora_do_paralelo_e_a_primeira_como_sempre(self):
        fila.definir_gerador_da_historia("h1", "chatgpt")
        pendentes = [{"historia_id": "h1", "imagens_faltando": 1,
                      "partes_sem_video": []},
                     {"historia_id": "h2", "partes_sem_texto": [2]}]
        with contextlib.ExitStack() as pilha:
            self.assertEqual("h2", agenda._escolher_incompleta(
                pendentes, {}, pilha, lambda _m: None)["historia_id"])
            self.assertEqual("h1", agenda._escolher_incompleta(
                pendentes[:1], {}, pilha, lambda _m: None)["historia_id"])

    def test_a_posse_segura_ate_o_fim(self):
        from builds import travas
        with agenda._posse("h_minha", self.config, lambda _m: None) as minha:
            self.assertTrue(minha)
            resultado = []
            fio = threading.Thread(target=lambda: resultado.append(
                travas.ocupada(agenda.trava_da_historia("h_minha"))))
            fio.start()
            fio.join(10)
            self.assertEqual([True], resultado)


# ------------------------------------------------------------------ reparo
class ReparoNaFaixa(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(setattr, reparo, "REGISTRO", reparo.REGISTRO)
        reparo.REGISTRO = Path(tmp.name) / "_reparos.json"
        self.videos = [type("V", (), {"id": f"historia_0000{n}:celular:p01",
                                      "fonte_id": f"historia_0000{n}",
                                      "parte": 1})() for n in (1, 2, 3)]
        barrados = [(v, ["erro"]) for v in self.videos]
        for alvo, nome, valor in (
                (agenda, "barrados_no_estoque", lambda: list(barrados)),
                (reparo, "reparar", self._reparar)):
            self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
            setattr(alvo, nome, valor)
        self.consertados = []

    def _reparar(self, video, erros, **_k):
        self.consertados.append(video.fonte_id)
        return {"ok": False, "detalhe": "duble"}

    def test_sem_posse_os_primeiros_como_sempre(self):
        reparo.rodada(limite=2, log=lambda _m: None)
        self.assertEqual(["historia_00001", "historia_00002"], self.consertados)

    def test_com_posse_o_que_nao_e_dela_nao_gasta_o_limite(self):
        @contextlib.contextmanager
        def posse(historia_id):
            yield historia_id != "historia_00001"

        reparo.rodada(limite=1, log=lambda _m: None, posse=posse)
        self.assertEqual(["historia_00002"], self.consertados)

    def test_o_registro_e_gravado_sob_trava(self):
        from builds import travas
        nomes = []
        real = travas.trava

        @contextlib.contextmanager
        def espia(nome, esperar=0.0):
            nomes.append(nome)
            with real(nome, esperar=esperar) as minha:
                yield minha

        self.addCleanup(setattr, travas, "trava", real)
        travas.trava = espia
        self.assertEqual(1, reparo._anotar("v1", "motivo", "falhou"))
        reparo.esquecer("v1")
        self.assertEqual([reparo.TRAVA_DO_REGISTRO] * 2, nomes)
        self.assertEqual(0, reparo.tentativas("v1"))


# ------------------------------------------------------------- _trabalhar
class TrabalharNaFaixa(_Base):
    """`_trabalhar` com a faixa: conserto com posse, historia nova com dono."""

    def setUp(self):
        super().setUp()
        self.reparos = []
        self.terminadas = []
        self.servicos = []
        self._trocar(agenda, "incompletas", lambda: [])
        self._trocar(agenda, "_gerador_pronto", lambda _g: "")
        self._trocar(agenda, "_servico_do_dia",
                     lambda *a, **k: self.servicos.append("servico"))
        self._trocar(agenda, "revisar_estoque",
                     lambda *a, **k: self.servicos.append("parecer"))
        self._trocar(agenda, "tipo_mais_magro", lambda *a: "normal")
        self._trocar(agenda, "provedores_do_roteiro", lambda _c: ["deepseek"])
        self._trocar(agenda, "_terminar", self._terminar)
        self._trocar(reparo, "rodada", self._rodada)
        from contos.pipeline import controller
        self.nasceu_ocupada = []
        teste = self

        class Pipeline:
            def gerar(self, **k):
                teste.kwargs_gerar = k
                if "ao_nascer" in k:
                    k["ao_nascer"]("historia_00077")
                    resultado = []
                    fio = threading.Thread(target=lambda: resultado.append(
                        __import__("builds.travas", fromlist=["x"]).ocupada(
                            agenda.trava_da_historia("historia_00077"))))
                    fio.start()
                    fio.join(10)
                    teste.nasceu_ocupada = resultado
                return {"historia_id": "historia_00077", "partes": 1,
                        "cenas": 2, "titulo": "T"}

        self._trocar(controller, "Pipeline", Pipeline)
        from contos.roteiro import linguagem
        self._trocar(linguagem, "conferir", lambda _r: {"pare": []})
        self._trocar(linguagem, "resumo", lambda _a: [])
        self._trocar(roteiro, "carregar", lambda _id: {})
        self.prefixo = f"teste_{os.getpid()}_{id(self)}"
        self._trocar(agenda, "trava_da_historia",
                     lambda h: f"{self.prefixo}__{h}")
        self.base = {"paralelo_por_gerador": LIGADO, "janela_pesada": None,
                     "teto_de_estoque": 0, "avisar_telegram": False}

    def _rodada(self, **k):
        self.reparos.append(k)
        return {"barrados": 0, "consertados": 0, "insistentes": []}

    def _terminar(self, pipeline, historia_id, headless, log, **k):
        self.terminadas.append(historia_id)
        return {"feito": "historia", "historia_id": historia_id, "erros": []}

    def test_faixa_do_chatgpt_cria_com_dono_e_conserta_com_posse(self):
        config = {**self.base, "faixa_de_imagem": "chatgpt",
                  "servico_do_dia": True}
        saida = agenda._trabalhar(config, False, lambda _m: None)
        self.assertEqual("historia_00077", saida["historia_id"])
        self.assertIn("posse", self.reparos[0])
        self.assertIn("ao_nascer", self.kwargs_gerar)
        self.assertEqual("chatgpt", fila.gerador_da_historia("historia_00077"))
        self.assertEqual([True], self.nasceu_ocupada,
                         "a historia nasce segura pela faixa")
        self.assertEqual([], self.servicos, "servico e parecer sao do Gemini")

    def test_faixa_do_gemini_faz_o_servico(self):
        config = {**self.base, "faixa_de_imagem": "gemini",
                  "servico_do_dia": True,
                  "janela_pesada": {"inicio": 0, "fim": 0},
                  "minutos_minimos": 0, "minutos_por_historia": 0}
        self._trocar(agenda, "minutos_ate_fechar", lambda *_a: 999)
        agenda._trabalhar(config, False, lambda _m: None)
        self.assertEqual(["servico", "parecer"], self.servicos)

    def test_fora_do_paralelo_nada_muda(self):
        agenda._trabalhar(dict(self.base), False, lambda _m: None)
        self.assertNotIn("posse", self.reparos[0])
        self.assertNotIn("ao_nascer", self.kwargs_gerar)
        self.assertEqual("", fila.gerador_da_historia("historia_00077"))


# -------------------------------------------------------------- supervisor
class _Proc:
    def __init__(self, gerador, voltas):
        self.gerador, self.voltas, self.pid = gerador, voltas, 1000 + voltas

    def poll(self):
        self.voltas -= 1
        return None if self.voltas > 0 else 0


class Supervisor(unittest.TestCase):

    def _trocar(self, alvo, nome, valor):
        self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
        setattr(alvo, nome, valor)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self._trocar(agenda, "OUTPUTS", Path(tmp.name))
        self.agora = datetime(2026, 10, 7, 9, 2)
        self._trocar(agenda, "_relogio", lambda: self.agora)
        self._trocar(agenda, "_dormir", self._dormir)
        self.plano = {"fazer": True, "modo": "lote", "por_que": "teste"}
        self._trocar(agenda, "planejar", lambda *_a, **_k: dict(self.plano))
        self._trocar(agenda, "faixas", lambda _c=None: ["gemini", "chatgpt"])
        self.rodou = []
        self._trocar(agenda, "rodar", lambda **k: self.rodou.append(k) or {})
        from builds import travas
        from builds.identity import controle
        self.ocupadas = set()
        self.seguradas = []

        @contextlib.contextmanager
        def trava(nome, esperar=0.0):
            livre = nome not in self.ocupadas
            if livre:
                self.seguradas.append(nome)
            yield livre

        self._trocar(travas, "trava", trava)
        self._trocar(travas, "ocupada", lambda nome: nome in self.ocupadas)
        self._trocar(controle, "pausado_para", lambda *a, **k: False)
        self.voltas = {"gemini": [2, 2, 2, 2], "chatgpt": [400]}
        self.lancadas = []
        self.config = {"paralelo_por_gerador": {**LIGADO, "relancar_min": 60},
                       "avisar_telegram": False}

    def _dormir(self, segundos):
        self.agora += timedelta(seconds=segundos)

    def _lancar(self, gerador, headless):
        self.lancadas.append((gerador, self.agora))
        fila_de_voltas = self.voltas[gerador]
        return _Proc(gerador, fila_de_voltas.pop(0) if fila_de_voltas else 1)

    def _rodar(self):
        return agenda.rodar_faixas(config=self.config, tela=None,
                                   lancar=self._lancar)

    def test_lanca_as_duas_e_relanca_a_que_terminou(self):
        saida = self._rodar()
        self.assertEqual("faixas", saida["feito"])
        primeiras = [g for g, _q in self.lancadas[:2]]
        self.assertEqual(["gemini", "chatgpt"], primeiras)
        self.assertEqual(1, saida["lancadas"]["chatgpt"])
        # chatgpt vive 400 voltas de 30 s (~3h20): o gemini volta de hora
        # em hora enquanto isso, e nunca antes de uma hora.
        gemini = [q for g, q in self.lancadas if g == "gemini"]
        self.assertGreaterEqual(len(gemini), 3)
        for antes, depois in zip(gemini, gemini[1:]):
            self.assertGreaterEqual((depois - antes).total_seconds(), 3600)
        self.assertEqual([agenda.TRAVA], self.seguradas,
                         "o supervisor segura a trava de sempre")

    def test_sem_trabalho_nao_lanca_nada(self):
        self.plano = {"fazer": False, "motivo": "estoque cheio",
                      "por_que": "cheio", "modo": "reposicao"}
        saida = self._rodar()
        self.assertEqual([], self.lancadas)
        self.assertEqual("estoque cheio", saida["motivo"])

    def test_rodada_em_andamento_nao_lanca_nada(self):
        self.ocupadas.add(agenda.TRAVA)
        saida = self._rodar()
        self.assertEqual([], self.lancadas)
        self.assertEqual("ja rodando", saida["motivo"])

    def test_faixa_ja_rodando_fora_do_supervisor_nao_e_lancada_de_novo(self):
        self.ocupadas.add(agenda.trava_da_faixa("gemini"))
        self._rodar()
        self.assertEqual({"chatgpt"}, {g for g, _q in self.lancadas})

    def test_desligado_e_a_rodada_de_sempre(self):
        self._trocar(agenda, "faixas", lambda _c=None: [])
        self._rodar()
        self.assertEqual([], self.lancadas)
        self.assertEqual(1, len(self.rodou))
        self.assertNotIn("gerador", self.rodou[0])

    def test_o_lancador_chama_a_faixa_com_saida_em_arquivo(self):
        import subprocess
        visto = {}

        def popen(argv, **k):
            visto.update(argv=argv, **k)
            return _Proc("x", 1)

        self._trocar(subprocess, "Popen", popen)
        agenda._lancar_faixa("chatgpt")
        argv = visto["argv"]
        self.assertTrue(argv[4].endswith("main.py"))
        self.assertEqual(["auto", "--gerador", "chatgpt"], argv[5:8])
        self.assertIn("--saida", argv)
        self.assertTrue(argv[argv.index("--saida") + 1].endswith(
            "auto_saida_chatgpt.txt"))
        self.assertEqual(subprocess.DEVNULL, visto["stdout"])


# ------------------------------------------------------------ rodar(faixa)
class RodarUmaFaixa(unittest.TestCase):

    def _trocar(self, alvo, nome, valor):
        self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
        setattr(alvo, nome, valor)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pasta = Path(tmp.name)
        self._trocar(agenda, "OUTPUTS", self.pasta)
        self._trocar(agenda, "_relogio", lambda: datetime(2026, 10, 7, 9, 2))
        self._trocar(agenda, "planejar", lambda config, *_a, **_k: {
            "fazer": True, "modo": "livre", "emendar": False,
            "config": config})
        from builds import travas
        from builds.identity import controle
        self.nomes = []

        @contextlib.contextmanager
        def trava(nome, esperar=0.0):
            self.nomes.append(nome)
            yield True

        self._trocar(travas, "trava", trava)
        self._trocar(controle, "pausado_para", lambda *a, **k: False)
        self.vistos = []
        self._trocar(agenda, "_emendar", self._emendar)
        self._trocar(agenda, "_gerador_pronto", lambda _g: "")

    def _emendar(self, config, plano, headless, log):
        self.vistos.append((config.get("faixa_de_imagem"), worker.faixa_atual()))
        return {"feito": "nada", "motivo": "so consertar"}

    def test_a_faixa_tem_trava_log_e_gerador_proprios(self):
        agenda.rodar(config={"avisar_telegram": False}, tela=None,
                     gerador="ChatGPT")
        self.assertEqual([agenda.trava_da_faixa("chatgpt")], self.nomes)
        self.assertEqual([("chatgpt", "chatgpt")], self.vistos)
        self.assertEqual("", worker.faixa_atual())
        self.assertTrue((self.pasta / "_logs" / "auto_20261007_chatgpt.txt")
                        .is_file())

    def test_sem_gerador_e_a_rodada_de_sempre(self):
        agenda.rodar(config={"avisar_telegram": False}, tela=None)
        self.assertEqual([agenda.TRAVA], self.nomes)
        self.assertEqual([(None, "")], self.vistos)

    def test_gerador_fora_de_cota_sai_sem_trava(self):
        self._trocar(agenda, "_gerador_pronto",
                     lambda _g: "o gemini nao gera agora (ficha ou cota)")
        saida = agenda.rodar(config={"avisar_telegram": False}, tela=None,
                             gerador="gemini")
        self.assertEqual("gerador fora", saida["motivo"])
        self.assertEqual([], self.nomes)
        self.assertEqual([], self.vistos)


# ----------------------------------------------------------------- main.py
class MainEscolheORumo(unittest.TestCase):

    def _cmd(self, gerador=None, faixas=()):
        # O main.py DAS HISTORIAS pelo caminho, e nao `import main`: o
        # random_builds tem outro main.py, e quem poe `random_builds/` no
        # sys.path antes (ferramentas/capas_atrasadas.py) fazia o `import`
        # pegar o dele (15/10/2026).
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_main_historias_rumo", Path(__file__).resolve().parents[1] / "main.py")
        main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main)
        from contos.pipeline import agenda as A
        chamadas = []
        anteriores = (A.rodar, A.rodar_faixas, A.faixas, A.carregar)
        A.rodar = lambda **k: chamadas.append(("rodar", k.get("gerador"))) or {}
        A.rodar_faixas = lambda **k: chamadas.append(("faixas", None)) or {}
        A.faixas = lambda _c=None: list(faixas)
        A.carregar = lambda: {"horas": []}
        try:
            args = argparse.Namespace(horas=None, instalar=False, remover=False,
                                      listar=False, headless=False,
                                      gerador=gerador)
            main.cmd_auto(args, None)
        finally:
            A.rodar, A.rodar_faixas, A.faixas, A.carregar = anteriores
        return chamadas

    def test_rumos(self):
        self.assertEqual([("rodar", None)], self._cmd())
        self.assertEqual([("faixas", None)],
                         self._cmd(faixas=["gemini", "chatgpt"]))
        self.assertEqual([("rodar", "gemini")],
                         self._cmd(gerador="gemini", faixas=["gemini", "chatgpt"]))


# ------------------------------------------------- a conta da outra faixa
class ContaDaOutraFaixa(unittest.TestCase):
    """Defeito do conferente (06/10/2026): dentro da faixa do Gemini, o
    roteiro (`deepseek -> chatgpt -> gemini`), o conserto, o reescritor de
    prompt e a folha do parecer podiam cair no ChatGPT — o gerador de IMAGEM
    da outra faixa — e segura-lo por ate 30 min, com as cenas dela falhando.
    Na faixa, a conta da outra faixa VIVA sai da ordem de queda; e o funil
    (`abrir_cliente`) recusa como conta ocupada o caminho que esquecer."""

    def _trocar(self, alvo, nome, valor):
        self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
        setattr(alvo, nome, valor)

    def test_fora_do_paralelo_nada_e_evitado(self):
        from contos.llm import papeis
        self.assertEqual(set(), papeis.evitados())
        self.assertEqual(["deepseek", "chatgpt", "gemini"],
                         papeis.sem_evitados(["deepseek", "chatgpt", "gemini"]))

    def test_evitando_e_devolvido_e_nunca_levanta(self):
        from contos.llm import papeis

        def quebra():
            raise RuntimeError("x")

        with papeis.evitando(lambda: {"ChatGPT"}):
            self.assertEqual({"chatgpt"}, papeis.evitados())
            self.assertEqual(["deepseek", "gemini"],
                             papeis.sem_evitados(["deepseek", "chatgpt", "gemini"]))
            with papeis.evitando(quebra):
                self.assertEqual(set(), papeis.evitados())
            self.assertEqual({"chatgpt"}, papeis.evitados())
        self.assertEqual(set(), papeis.evitados())

    def test_o_funil_recusa_sem_pegar_trava_nem_abrir_chrome(self):
        from contos.llm import cliente, papeis

        def nao_toque(*_a, **_k):
            raise AssertionError("pegou a trava da conta da outra faixa")

        self._trocar(cliente._rb_travas, "trava", nao_toque)
        with papeis.evitando(lambda: {"chatgpt"}):
            with self.assertRaises(cliente.ContaOcupada):
                with cliente.abrir_cliente("chatgpt", log=lambda _m: None):
                    pass

    def test_o_reescritor_cai_no_mecanico(self):
        """Ele abre o cliente numa THREAD propria: a guarda e por processo."""
        from contos.imagens.reescritor import Reescritor
        from contos.llm import cliente, papeis

        self._trocar(cliente._rb_travas, "trava",
                     lambda *a, **k: (_ for _ in ()).throw(
                         AssertionError("pegou a trava")))
        linhas = []
        with papeis.evitando(lambda: {"chatgpt"}):
            r = Reescritor("chatgpt", log=linhas.append)
            try:
                self.assertIsNone(r._garantir())
            finally:
                r.fechar()
        self.assertTrue(r._desistiu)
        self.assertTrue(any("suavizacao automatica" in l for l in linhas))

    def test_roteiro_sem_a_conta_da_outra(self):
        from contos.llm import papeis
        completo = agenda.provedores_do_roteiro({})
        self.assertEqual(["deepseek", "chatgpt", "gemini"], completo)
        with papeis.evitando(lambda: {"chatgpt"}):
            self.assertEqual(["deepseek", "gemini"],
                             agenda.provedores_do_roteiro({}))
        with papeis.evitando(lambda: {"gemini"}):
            self.assertEqual(["deepseek", "chatgpt"],
                             agenda.provedores_do_roteiro({}))

    def test_parecer_sem_a_folha_na_conta_da_outra(self):
        from contos.llm import papeis
        from contos.publicar import parecer
        self.assertIn("chatgpt", parecer.provedores_da_analise())
        with papeis.evitando(lambda: {"chatgpt"}):
            self.assertEqual(["gemini"], parecer.provedores_da_analise())

    def test_retomada_nao_volta_ao_preferido_da_outra(self):
        from contos.llm import papeis
        from contos.roteiro import gerar as G
        vistos = []
        self._trocar(roteiro, "carregar", lambda _id: {"provedor": "chatgpt"})
        self._trocar(roteiro, "partes_que_faltam", lambda _r: [])
        self._trocar(G, "escrever_serie",
                     lambda ordem, **k: vistos.append(list(ordem)))
        self._trocar(agenda, "_terminar", lambda *a, **k: {"feito": "historia"})
        self._trocar(agenda, "carregar", lambda: {})
        with papeis.evitando(lambda: {"chatgpt"}):
            agenda._retomar_texto(None, "h1", [2], False, lambda _m: None)
        self.assertEqual([["deepseek", "gemini"]], vistos)

    def test_ninguem_livre_adia_sem_pegar(self):
        from contos.llm import papeis
        from contos.roteiro import gerar as G
        self._trocar(roteiro, "carregar", lambda _id: {"provedor": "chatgpt"})
        self._trocar(G, "escrever_serie", lambda *a, **k: self.fail("escreveu"))
        self._trocar(agenda, "carregar", lambda: {})
        with papeis.evitando(lambda: {"deepseek", "chatgpt", "gemini"}):
            saida = agenda._retomar_texto(None, "h1", [2], False,
                                          lambda _m: None)
        self.assertEqual("sem escritor livre", saida["motivo"])
        self.assertIsNone(agenda.mensagem(saida, 1), "adiar nao e falha")

    def test_contas_das_outras_faixas_sao_as_vivas(self):
        from builds import travas
        prefixo = f"teste_{os.getpid()}_{id(self)}"
        self._trocar(agenda, "trava_da_faixa", lambda g: f"{prefixo}__{g}")
        self._trocar(fila, "carregar_config",
                     lambda: {"geradores_imagem": ["gemini", "chatgpt"]})
        self.assertEqual(set(), agenda.contas_das_outras_faixas("gemini"))
        pegou, soltar = threading.Event(), threading.Event()

        def outra_faixa():
            with travas.trava(agenda.trava_da_faixa("chatgpt")):
                pegou.set()
                soltar.wait(10)

        fio = threading.Thread(target=outra_faixa)
        fio.start()
        pegou.wait(10)
        try:
            self.assertEqual({"chatgpt"},
                             agenda.contas_das_outras_faixas("gemini"))
            self.assertEqual(set(), agenda.contas_das_outras_faixas("chatgpt"),
                             "a propria conta nunca e evitada")
        finally:
            soltar.set()
            fio.join(10)
        self.assertEqual(set(), agenda.contas_das_outras_faixas("gemini"),
                         "a outra acabou: a conta volta")

    def test_a_faixa_liga_o_filtro_so_dentro_dela(self):
        from contos.llm import papeis
        from builds import travas
        from builds.identity import controle
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self._trocar(agenda, "OUTPUTS", Path(tmp.name))
        self._trocar(agenda, "planejar", lambda config, *_a, **_k: {
            "fazer": True, "modo": "livre", "emendar": False, "config": config})
        self._trocar(agenda, "_gerador_pronto", lambda _g: "")
        self._trocar(controle, "pausado_para", lambda *a, **k: False)

        @contextlib.contextmanager
        def livre(nome, esperar=0.0):
            yield True

        self._trocar(travas, "trava", livre)
        self._trocar(agenda, "contas_das_outras_faixas",
                     lambda g: {"chatgpt"} if g == "gemini" else set())
        vistos = []
        self._trocar(agenda, "_emendar", lambda *a, **k: vistos.append(
            papeis.evitados()) or {"feito": "nada", "motivo": "so consertar"})
        agenda.rodar(config={"avisar_telegram": False}, tela=None,
                     gerador="gemini")
        agenda.rodar(config={"avisar_telegram": False}, tela=None)
        self.assertEqual([{"chatgpt"}, set()], vistos)
        self.assertEqual(set(), papeis.evitados())

    def test_o_reparo_adia_quando_o_gemini_e_da_outra_faixa(self):
        fonte = Path(reparo.__file__).read_text(encoding="utf-8")
        trecho = fonte[fonte.index('"gemini" in papeis.evitados()'):]
        self.assertIn("conta_ocupada = True", trecho[:400])


class LogDaFaixaDepoisDaMeiaNoite(Supervisor):

    def test_a_relancada_aponta_o_log_do_dia_dela(self):
        self.agora = datetime(2026, 10, 7, 23, 50)
        linhas = []
        agenda.rodar_faixas(config=self.config, tela=linhas.append,
                            lancar=self._lancar)
        relancadas = [l for l in linhas if "faixa do gemini lancada" in l]
        self.assertGreaterEqual(len(relancadas), 2)
        self.assertIn("auto_20261007_gemini.txt", relancadas[0])
        self.assertIn("auto_20261008_gemini.txt", relancadas[1])


if __name__ == "__main__":
    unittest.main()
