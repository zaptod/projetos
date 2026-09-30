# -*- coding: utf-8 -*-
"""O lote semanal de dia (decisoes do Adrian, 30/09/2026, Grimorio geral/lote-*).

    janela_pesada      07h-22h (de madrugada o PC faz barulho)
    dias_de_lote       seg-qua emendam historias ate o alvo
    alvo_do_lote       cobre ate a proxima segunda 07h + o piso
    piso_de_reposicao  qui-dom so consertam; criam abaixo de 20
    estoque zero       de madrugada, sem video para o proximo horario, LIBERA
    folga_da_grade     passo novo nao comeca perto de um post (12:07, 17:57)
    teto do PicassoIA  ao bater, a geracao para e avisa

Tudo aqui roda com o relogio CONGELADO, o sono que so avanca o relogio e
duble no lugar de `_trabalhar` (que e onde mora o navegador): nenhum teste
gera roteiro, imagem ou video, e o OUTPUTS vai para uma pasta temporaria.
Os casos ZERO vem primeiro porque sao os que um relatorio verde esconde.
"""
from __future__ import annotations

import contextlib
import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from contos.imagens import cota
from contos.pipeline import agenda

SEGUNDA = datetime(2026, 10, 5, 7, 2)        # o 1o lote
TERCA = datetime(2026, 10, 6, 7, 2)
QUARTA = datetime(2026, 10, 7, 7, 2)
QUINTA = datetime(2026, 10, 8, 10, 2)


def _video(serie: int, parte: int):
    fonte = f"historia_{serie:05d}"
    return type("V", (), {"id": f"{fonte}:celular:p{parte:02d}",
                          "fonte_id": fonte, "parte": parte,
                          "perfil": "celular"})()


def _series(quantas: int, partes: int, comeco: int = 90000) -> list:
    return [_video(comeco + s, p) for s in range(quantas)
            for p in range(1, partes + 1)]


class _Mundo(unittest.TestCase):
    """Relogio, estoque, trava, pausa, cota e Telegram: tudo de mentira."""

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pasta = Path(tmp.name)
        self._trocar(agenda, "OUTPUTS", self.pasta)
        self._trocar(cota, "CONTADOR", self.pasta / "_picasso_por_dia.json")
        self.imagens_json = self.pasta / "imagens.json"
        self.imagens_json.write_text(json.dumps(
            {"teto_de_imagens_por_dia": 450}), encoding="utf-8")
        self._trocar(cota, "CONFIG", self.imagens_json)

        self.agora = SEGUNDA
        self.dormiu = []
        self._trocar(agenda, "_relogio", lambda: self.agora)
        self._trocar(agenda, "_dormir", self._dormir)

        self.estoque, self.barrados = [], []
        self._trocar(agenda, "aprovados_no_estoque",
                     lambda: list(self.estoque))
        self._trocar(agenda, "barrados_no_estoque",
                     lambda: list(self.barrados))
        self._trocar(agenda, "incompletas", lambda: [])
        self._trocar(agenda, "partes_publicadas", lambda publicados=None: {})
        self._trocar(agenda, "_livre_gb", lambda _c: 100.0)
        self.avisos = []
        self._trocar(agenda, "avisar",
                     lambda texto, log=None: self.avisos.append(texto) or True)
        self._trocar(agenda, "_cronometrar", lambda *a, **k: None)
        self._trocar(agenda, "_registrar_erro", lambda *a, **k: None)

        from builds import travas
        from builds.identity import controle

        @contextlib.contextmanager
        def _livre(nome, esperar=0.0):
            yield True

        self._trocar(travas, "trava", _livre)
        self._trocar(controle, "pausado_para", lambda *a, **k: False)

        self.passos = []
        self.dura_min = 0
        self._trocar(agenda, "_trabalhar", self._passo)
        # O config REAL, para o teste conferir tambem o que esta no arquivo.
        # `avisar_telegram: False`: a suite nao toca o telefone de ninguem.
        self.config = {**agenda.carregar(), "avisar_telegram": False}

    def _trocar(self, alvo, nome, valor):
        self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
        setattr(alvo, nome, valor)

    def _dormir(self, segundos):
        self.dormiu.append(segundos)
        self.agora += timedelta(seconds=segundos)

    def _passo(self, config, headless, log):
        """O duble de `_trabalhar`: cria uma historia de 6 partes (ou so
        conserta) e gasta `dura_min` do relogio."""
        self.passos.append({"agora": self.agora, "config": config})
        self.agora += timedelta(minutes=self.dura_min)
        if config.get("so_consertar"):
            return {"feito": "nada", "motivo": "so consertar"}
        n = 80000 + len(self.passos)
        self.estoque.extend(_video(n, p) for p in range(1, 7))
        return {"feito": "historia", "historia_id": f"historia_{n:05d}",
                "erros": []}

    def _servico_feito(self):
        agenda._marcar_servico(self.agora)

    def rodar(self, **extra):
        return agenda.rodar(config={**self.config, **extra}, tela=None)


class CasoZeroTests(_Mundo):
    """Os casos que o relatorio verde esconde: estoque ZERO."""

    def test_quinta_10h_com_zero_aprovados_cria(self):
        self.agora = QUINTA
        self._servico_feito()
        self.rodar()
        self.assertTrue(self.passos, "quinta com zero tinha de criar")
        primeiro = self.passos[0]["config"]
        self.assertFalse(primeiro["so_consertar"])
        self.assertEqual(20, primeiro["teto_de_estoque"])
        # emenda ate o piso (0 -> 6 -> 12 -> 18 -> 24) e para
        self.assertEqual(4, len(self.passos))
        self.assertGreaterEqual(len(self.estoque), 20)

    def test_quinta_00h_com_zero_libera_tudo(self):
        self.agora = datetime(2026, 10, 8, 0, 2)
        self.rodar()
        self.assertEqual(1, len(self.passos),
                         "de madrugada so ate haver video para o proximo "
                         "horario")
        config = self.passos[0]["config"]
        self.assertIsNone(config["janela_pesada"])
        self.assertFalse(config["so_consertar"])
        self.assertTrue(config["retomar_incompletas"])
        self.assertFalse(config["servico_do_dia"])

    def test_quinta_00h_com_25_nao_faz_nada(self):
        self.agora = datetime(2026, 10, 8, 0, 2)
        self.estoque = _series(5, 5)
        resultado = self.rodar()
        self.assertEqual("fora da janela", resultado["motivo"])
        self.assertEqual([], self.passos)

    def test_madrugada_com_video_no_disco_mas_nenhuma_proxima_parte(self):
        """25 partes no disco e nenhuma sai: todas esperam a parte 1."""
        self.agora = datetime(2026, 10, 8, 0, 2)
        self.estoque = [_video(90000 + s, p) for s in range(5)
                        for p in range(2, 7)]
        self.rodar()
        self.assertEqual(1, len(self.passos))

    def test_estoque_zero_sem_saber_contar_nao_e_zero(self):
        sem_parte = type("V", (), {"id": "x", "fonte_id": "", "parte": 0})()
        self.assertFalse(agenda.estoque_zero([sem_parte], {}))
        self.assertTrue(agenda.estoque_zero([], {}))


class LoteTests(_Mundo):

    def test_segunda_07h_com_60_cria_ate_o_alvo(self):
        self.estoque = _series(10, 6)
        self.rodar()
        self.assertEqual(90, self.passos[0]["config"]["teto_de_estoque"])
        self.assertEqual(5, len(self.passos), "60 -> 90 sao cinco historias")
        self.assertEqual(90, len(self.estoque))

    def test_o_servico_do_dia_vai_no_primeiro_passo_so(self):
        self.estoque = _series(10, 6)
        self.dura_min = 1
        self._trocar(agenda, "servico_pendente",
                     lambda agora: not (self.pasta / "marca").exists())

        original = self._passo

        def _passo(config, headless, log):
            (self.pasta / "marca").write_text("x")
            return original(config, headless, log)

        self._trocar(agenda, "_trabalhar", _passo)
        self.rodar()
        pedidos = [p["config"]["servico_do_dia"] for p in self.passos]
        self.assertEqual([True] + [False] * (len(pedidos) - 1), pedidos)

    def test_segunda_09h30_nao_comeca_passo_novo(self):
        self.agora = datetime(2026, 10, 5, 9, 30)
        self.estoque = _series(10, 6)
        self._servico_feito()
        self.rodar(passos_por_rodada=1)
        self.assertTrue(self.dormiu, "tinha de esperar a postagem das 09:37")
        self.assertGreaterEqual(self.passos[0]["agora"],
                                datetime(2026, 10, 5, 9, 52))

    def test_a_folga_vale_para_12h07_e_17h57(self):
        config = self.config
        for hora, minuto, post in ((9, 30, (9, 37)), (12, 0, (12, 7)),
                                   (12, 20, (12, 7)), (17, 45, (17, 57)),
                                   (0, 30, (0, 37))):
            achado = agenda.postagem_perto(
                config, datetime(2026, 10, 5, hora, minuto))
            self.assertIsNotNone(achado, (hora, minuto))
            self.assertEqual(post, (achado.hour, achado.minute))
        for hora, minuto in ((10, 2), (12, 32), (18, 13), (14, 0)):
            self.assertIsNone(agenda.postagem_perto(
                config, datetime(2026, 10, 5, hora, minuto)), (hora, minuto))

    def test_quarta_22h_para(self):
        self.agora = datetime(2026, 10, 7, 22, 0)
        self.estoque = _series(5, 6)
        resultado = self.rodar()
        self.assertEqual("fora da janela", resultado["motivo"])
        self.assertEqual([], self.passos)

    def test_quarta_21h_emenda_so_ate_as_22h(self):
        self.agora = datetime(2026, 10, 7, 21, 0)
        self.estoque = _series(5, 6)
        self._servico_feito()
        self.dura_min = 70
        self.rodar()
        self.assertEqual(1, len(self.passos),
                         "passo novo depois das 22h faria barulho")

    def test_segunda_desligada_terca_e_quarta_compensam(self):
        config = self.config
        proxima = datetime(2026, 10, 12, 7, 0)
        for dia in (SEGUNDA, TERCA, QUARTA):
            self.assertEqual(proxima, agenda.fim_da_cobertura(config, dia))
        self.assertEqual(90, agenda.alvo_do_lote(config, SEGUNDA))
        self.assertEqual(80, agenda.alvo_do_lote(config, TERCA))
        self.assertEqual(70, agenda.alvo_do_lote(config, QUARTA))
        self.assertEqual(64, agenda.alvo_do_lote(
            config, datetime(2026, 10, 7, 22, 0)))
        # a segunda nao produziu nada: a terca cria com o estoque do piso
        self.agora = TERCA
        self.estoque = _series(4, 5)
        self._servico_feito()
        self.rodar(passos_por_rodada=3)
        self.assertEqual(80, self.passos[0]["config"]["teto_de_estoque"])
        self.assertEqual(3, len(self.passos))

    def test_antes_do_primeiro_lote_a_segunda_e_reposicao(self):
        agora = datetime(2026, 9, 28, 10, 2)
        self.assertEqual("reposicao", agenda.modo_da_hora(self.config, agora))
        self.assertEqual("lote", agenda.modo_da_hora(self.config, SEGUNDA))
        self.assertEqual("reposicao",
                         agenda.modo_da_hora(self.config, QUINTA))

    def test_passo_que_falhou_nao_emenda(self):
        self.estoque = _series(10, 6)
        self._servico_feito()

        def _falha(config, headless, log):
            self.passos.append(config)
            return {"feito": "historia", "historia_id": "historia_1",
                    "erros": ["imagens: a conta estava em uso"]}

        self._trocar(agenda, "_trabalhar", _falha)
        self.rodar()
        self.assertEqual(1, len(self.passos))


class ReposicaoTests(_Mundo):

    def test_quinta_com_estoque_so_conserta(self):
        self.agora = QUINTA
        self.estoque = _series(5, 5)
        self.barrados = [object(), object()]
        self._servico_feito()
        self.rodar()
        self.assertEqual(1, len(self.passos))
        config = self.passos[0]["config"]
        self.assertTrue(config["so_consertar"])
        self.assertEqual(2, config["reparos_por_rodada"])

    def test_quinta_cheia_e_sem_barrado_sai(self):
        self.agora = QUINTA
        self.estoque = _series(5, 5)
        self._servico_feito()
        resultado = self.rodar()
        self.assertEqual("estoque cheio", resultado["motivo"])
        self.assertEqual([], self.passos)

    def test_historia_pela_metade_e_terminada_na_reposicao(self):
        self.agora = QUINTA
        self.estoque = _series(5, 5)
        self._servico_feito()
        plano = agenda.planejar(self.config, self.agora,
                                pendentes=[{"historia_id": "h"}])
        self.assertTrue(plano["fazer"])
        self.assertFalse(plano["criar"])
        self.assertTrue(plano["config"]["retomar_incompletas"])

    def test_transicao_a_madrugada_antiga_continua(self):
        plano = agenda.planejar(self.config, datetime(2026, 10, 8, 2, 20),
                                aprovados=[])
        self.assertEqual("madrugada", plano["modo"])
        self.assertEqual({"inicio": 1, "fim": 6},
                         plano["config"]["janela_pesada"])
        self.assertFalse(plano["config"]["servico_do_dia"])
        sem = {k: v for k, v in self.config.items()
               if k != "madrugada_na_transicao"}
        self.assertEqual("noite", agenda.modo_da_hora(
            sem, datetime(2026, 10, 8, 2, 20)))


class TetoDoPicassoTests(_Mundo):

    def _bater_o_teto(self, teto=3):
        self.imagens_json.write_text(json.dumps(
            {"teto_de_imagens_por_dia": teto}), encoding="utf-8")
        for _ in range(teto):
            cota.contar()

    def test_teto_batido_nao_cria_e_avisa_uma_vez(self):
        self.agora = QUINTA
        self._servico_feito()
        self._bater_o_teto()
        resultado = self.rodar(avisar_telegram=True)
        self.assertEqual("impedido", resultado["motivo"])
        self.assertEqual([], self.passos)
        self.assertEqual(1, len(self.avisos))
        self.assertIn("PicassoIA", self.avisos[0])
        self.rodar(avisar_telegram=True)
        self.assertEqual(1, len(self.avisos), "o aviso repetiu no disparo "
                                              "seguinte")

    def test_teto_zero_e_sem_teto(self):
        self.imagens_json.write_text(json.dumps(
            {"teto_de_imagens_por_dia": 0}), encoding="utf-8")
        for _ in range(5):
            cota.contar()
        self.assertIsNone(cota.motivo())

    def test_o_worker_para_no_envio_que_passaria_do_teto(self):
        from contos.imagens import worker
        registrados = []
        self._trocar(worker._rb_atividade, "registrar",
                     lambda *a, **k: registrados.append(a))
        enviados = []

        class _Cliente:
            prompt_enviado, enviado_em = "", 0

            def submit_prompt(self, prompt, aspect=None):
                enviados.append(prompt)
                return 0

            def wait_for_render(self, antes=None):
                return "url"

        config = {"teto_de_imagens_por_dia": 2}
        for _ in range(2):
            worker._gerar_esperando(_Cliente(), "p", config, {}, print, "c1")
        with self.assertRaises(worker.TetoDoDia) as pego:
            worker._gerar_esperando(_Cliente(), "p", config, {}, print, "c1")
        self.assertEqual(2, len(enviados), "enviou alem do teto")
        # E `NaoRodou`: o reparo adia sem gastar tentativa do video.
        self.assertIsInstance(pego.exception, worker.NaoRodou)
        self.assertIsInstance(pego.exception, cota.TetoDoDia)
        self.assertTrue(registrados)

    def test_o_worker_nem_abre_o_navegador_com_o_teto_batido(self):
        from contos.imagens import fila, worker
        from contos.roteiro import roteiro as R
        self._bater_o_teto(teto=1)
        self._trocar(R, "carregar", lambda _h: {"partes": []})
        self._trocar(fila, "carregar_config",
                     lambda: {"teto_de_imagens_por_dia": 1})
        self._trocar(fila, "aspecto_da_historia", lambda _h: "1:1")
        self._trocar(fila, "pendentes",
                     lambda *a, **k: [{"n": 1, "parte": 1}])
        self._trocar(worker, "_pausado", lambda *a: (False, ""))
        self._trocar(worker._rb_atividade, "registrar", lambda *a, **k: None)

        def _nao_abre(*a, **k):
            raise AssertionError("abriu o navegador com o teto batido")

        self._trocar(worker._rb_identity_browser, "contexto_persistente",
                     _nao_abre)
        with self.assertRaises(worker.TetoDoDia):
            worker._gerar("historia_00001", log=lambda *_a: None)


class ParedeDePlanosTests(unittest.TestCase):
    """"Assine para Gerar" numa conta com plano: reabrir o perfil resolve."""

    def _gerar(self, falhas: int, reaberturas: int):
        from contos.imagens import fila, worker
        Parede = worker._rb_identity_picasso_client.ParedeDePlanos
        chamadas = []

        def _falso(*a, **k):
            chamadas.append(1)
            if len(chamadas) <= falhas:
                raise Parede("o botao de gerar virou 'Assine para Gerar'")
            return {"geradas": 1, "faltam": 0, "erros": [], "recusadas": []}

        for alvo, nome, valor in (
                (worker, "_gerar", _falso),
                (worker, "_registrar_parede", lambda *a: None),
                (fila, "carregar_config",
                 lambda: {"reaberturas_na_parede": reaberturas,
                          "pausa_antes_de_reabrir_s": 0})):
            self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
            setattr(alvo, nome, valor)
        return worker, chamadas

    def test_reabre_ate_o_config_mandar(self):
        worker, chamadas = self._gerar(falhas=2, reaberturas=2)
        saida = worker.gerar("h", log=lambda *_a: None)
        self.assertEqual(1, saida["geradas"])
        self.assertEqual(3, len(chamadas))

    def test_parede_que_volta_depois_das_reaberturas_e_nao_rodou(self):
        worker, chamadas = self._gerar(falhas=3, reaberturas=2)
        with self.assertRaises(worker.NaoRodou):
            worker.gerar("h", log=lambda *_a: None)
        self.assertEqual(3, len(chamadas))

    def test_o_config_pede_reabertura_automatica(self):
        from contos.imagens import fila
        config = fila.carregar_config()
        self.assertGreaterEqual(int(config["reaberturas_na_parede"]), 1)
        self.assertGreater(int(config["teto_de_imagens_por_dia"]), 0)
        self.assertTrue(config["exigir_prova_de_origem"])


class DiscoTests(_Mundo):

    def test_disco_apertado_nao_cria(self):
        self.agora = QUINTA
        self._servico_feito()
        self._trocar(agenda, "_livre_gb", lambda _c: 3.0)
        resultado = self.rodar()
        self.assertEqual("impedido", resultado["motivo"])
        self.assertEqual([], self.passos)


class ServicoDoDiaTests(_Mundo):

    def test_servico_uma_vez_por_dia(self):
        self.agora = QUINTA
        self.assertTrue(agenda.servico_pendente(self.agora))
        agenda._marcar_servico(self.agora)
        self.assertFalse(agenda.servico_pendente(self.agora))
        self.assertTrue(agenda.servico_pendente(self.agora
                                                + timedelta(days=1)))

    def test_o_servico_usa_a_chave_do_dia_e_marca(self):
        from builds import tempos
        from builds.publicar import conferencia, metricas
        chaves = []
        self._trocar(metricas, "atualizar_uma_vez_por_dia",
                     lambda log=None, chave=None: chaves.append(chave))
        self._trocar(tempos, "consolidar", lambda: self.pasta / "t.json")
        self._trocar(conferencia, "conferir_tudo", lambda log=None: None)
        self.agora = QUINTA
        agenda._servico_do_dia({}, False, lambda *_a: None)
        self.assertEqual(["dia-2026-10-08"], chaves)
        self.assertFalse(agenda.servico_pendente(self.agora))

    def test_trabalhar_so_chama_o_servico_quando_o_plano_pede(self):
        # Do ARQUIVO: aqui `_trabalhar` esta dublado pelo `_Mundo`.
        texto = Path(agenda.__file__).read_text(encoding="utf-8")
        fonte = texto[texto.index("def _trabalhar("):]
        fonte = fonte[:fonte.index("\ndef ", 10)]
        self.assertIn('if config.get("servico_do_dia"):', fonte)
        self.assertLess(fonte.index('config.get("servico_do_dia")'),
                        fonte.index("_servico_do_dia("))

    def test_janela_de_dia_usa_a_data_do_calendario(self):
        janela = {"inicio": 7, "fim": 22}
        self.assertEqual("2026-10-08", agenda.chave_da_noite(
            datetime(2026, 10, 8, 10, 0), janela))


class RenderEsperaAGradeTests(unittest.TestCase):

    def test_janela_fechada_adia_o_render(self):
        from contos.imagens import fila
        from contos.pipeline import conferir
        from contos.roteiro import roteiro as R
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        roteiro = {"serie": True, "titulo": "T", "total_cenas": 2,
                   "partes": [{"n": 1}, {"n": 2}]}
        for alvo, nome, valor in (
                (agenda, "OUTPUTS", Path(tmp.name)),
                (R, "carregar", lambda _h: roteiro),
                (fila, "resumo", lambda *a, **k: {"faltam": 0}),
                (fila, "resumo_por_parte", lambda *a, **k: []),
                (conferir, "partes_da_historia", lambda _h: [])):
            self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
            setattr(alvo, nome, valor)
        renderizadas = []
        pipeline = type("P", (), {"render": staticmethod(
            lambda _h, parte=None, log=None: renderizadas.append(parte))})()
        respostas = iter([True, False])
        resultado = agenda._terminar(pipeline, "historia_1", False,
                                     lambda *_a: None, criada=False,
                                     guarda=lambda: next(respostas))
        self.assertEqual([1], renderizadas)
        self.assertTrue(any("janela fechou" in e for e in resultado["erros"]))


if __name__ == "__main__":
    unittest.main()
