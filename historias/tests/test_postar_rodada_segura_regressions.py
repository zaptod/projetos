# -*- coding: utf-8 -*-
"""A rodada do postar nao encosta no horario seguinte (conferente do 4e8df2b).

Tres defeitos achados pelo conferente em 06/10/2026, depois da volta final:

1. A janela contava so do COMECO da rodada (marcado ainda depois da espera
   da rede, de ate 300 s). Com a grade de 60 min (20:37 -> 21:37 ... 23:37 ->
   00:37) e a rodada que comeca atrasada, uma tentativa podia comecar a
   minutos do horario seguinte. Agora nenhuma tentativa comeca a menos de
   `MARGEM_ANTES_DO_PROXIMO_MIN` (20) do proximo horario, conferido depois
   de cada espera.
2. Duas rodadas (a que estourou e a do horario seguinte) publicavam juntas:
   perfil `youtube_web` disputado, a mesma parte escolhida duas vezes. Agora
   `TRAVA_DA_RODADA`, entre PROCESSOS (testado com um segundo processo de
   verdade: a trava e reentrante por thread, e um teste no mesmo processo
   passaria sem provar nada).
3. A guarda de um por horario falhava ABERTA: ledger ilegivel virava lista
   vazia, "nao sei" virava "nao publiquei", e o YouTube da mesma p06 subia
   duas vezes (teste C do conferente). Agora falha fechada.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_rodada_segura",
                                                  POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


# ------------------------------------------------------------------ item 1
class ProximoHorarioTests(unittest.TestCase):
    def test_proximo_em_atravessa_a_meia_noite(self):
        from builds import grade
        self.assertEqual(datetime(2026, 10, 7, 0, 37),
                         grade.proximo_em(datetime(2026, 10, 6, 23, 50)))
        self.assertEqual(datetime(2026, 10, 7, 0, 37),
                         grade.proximo_em(datetime(2026, 10, 7, 0, 10)))
        # Estritamente depois: as 12:07 em ponto o proximo e o 15:37.
        self.assertEqual(datetime(2026, 10, 6, 15, 37),
                         grade.proximo_em(datetime(2026, 10, 6, 12, 7)))


class MargemAntesDoProximoTests(unittest.TestCase):
    """`_ainda_no_horario` com o relogio da rodada em 1 min: so a margem decide."""

    PARES_DE_60_MIN = ((20, datetime(2026, 10, 6, 20, 37)),
                       (21, datetime(2026, 10, 6, 21, 37)),
                       (22, datetime(2026, 10, 6, 22, 37)),
                       (23, datetime(2026, 10, 6, 23, 37)))

    def setUp(self):
        self.m = _postar()

    def _pode(self, slot, agora, janela_min=None):
        return self.m._ainda_no_horario(0.0, slot, agora=agora,
                                        relogio=lambda: 60.0,
                                        janela_min=janela_min)

    def test_os_quatro_pares_de_60_min(self):
        """21 min antes do proximo: comeca; 19 min antes: nao comeca. Vale
        para a reposicao e para a volta final (janela de 40)."""
        self.assertEqual(20, self.m.MARGEM_ANTES_DO_PROXIMO_MIN)
        volta = self.m.JANELA_DA_VOLTA_FINAL_MIN
        for slot, inicio in self.PARES_DE_60_MIN:
            proximo = inicio + timedelta(hours=1)
            with self.subTest(horario=f"{inicio:%H:%M}->{proximo:%H:%M}"):
                cedo = proximo - timedelta(minutes=21)
                tarde = proximo - timedelta(minutes=19)
                self.assertTrue(self._pode(slot, cedo))
                self.assertTrue(self._pode(slot, cedo, volta))
                self.assertFalse(self._pode(slot, tarde))
                self.assertFalse(self._pode(slot, tarde, volta))

    def test_rodada_que_comecou_atrasada_nao_repoe(self):
        """O disparo das 20:37 que so rodou as 21:20 (Agendador com
        `StartWhenAvailable`): o relogio da rodada esta em ZERO, a janela de
        25 min esta inteira, e mesmo assim nada recomeca — faltam 17 min."""
        agora = datetime(2026, 10, 6, 21, 20)
        self.assertEqual(20, self.m.grade.slot(agora))
        self.assertFalse(self.m._ainda_no_horario(
            0.0, 20, agora=agora, relogio=lambda: 0.0))

    def test_horario_largo_continua_pela_janela(self):
        """06:37 -> 09:37: a margem nao pesa; quem limita e a janela."""
        agora = datetime(2026, 10, 6, 7, 10)
        self.assertTrue(self.m._ainda_no_horario(
            0.0, 6, agora=agora, relogio=lambda: 33 * 60.0,
            janela_min=self.m.JANELA_DA_VOLTA_FINAL_MIN))
        self.assertFalse(self.m._ainda_no_horario(
            0.0, 6, agora=agora, relogio=lambda: 33 * 60.0))

    def test_o_comeco_e_marcado_antes_da_espera_da_rede(self):
        fonte = POSTAR.read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def _main("):]
        self.assertLess(corpo.index("comeco_da_rodada = _time.monotonic()"),
                        corpo.index("esperar_a_rede()"))

    def test_reposicao_confere_de_novo_depois_da_espera_da_rede(self):
        m = self.m
        m._linha = lambda *_a, **_k: None
        m._dormir = lambda s: None
        estado = {"esperou": False}
        m.esperar_a_rede = lambda **k: estado.update(esperou=True) or True
        m._ainda_no_horario = lambda comeco, slot, **k: not estado["esperou"]
        chamadas = []

        def canal(so_ver=False):
            chamadas.append(1)
            return {"canal": "builds", "feito": False, "youtube_falhou": True,
                    "motivo": "YouTube falhou: infraestrutura: nao abriu"}
        m._publicar_canal("builds", canal, so_ver=False, comeco=0.0, slot=20)
        self.assertEqual(1, len(chamadas), "a janela fechou durante a espera")


# ------------------------------------------------------------------ item 3
class GuardaFalhaFechadaTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.diario = []
        from builds import atividade
        _trocar(self, atividade, "registrar",
                lambda *a, **k: self.diario.append((a, k)))
        from contos.publicar import serie

        def preso():
            raise OSError("ledger preso por outro processo")
        _trocar(self, serie, "publicados", preso)

    def test_ledger_ilegivel_barra_e_vai_ao_diario(self):
        achado = self.m.publicou_neste_horario("historias", "youtube")
        self.assertTrue(achado, "'nao sei' NAO pode virar 'nao publiquei'")
        self.assertIn("ledger", achado["ledger_ilegivel"])
        self.assertEqual(1, len(self.diario))
        self.assertEqual("erro", self.diario[0][0][1])

    def test_postar_historia_nao_publica_e_nao_repoe(self):
        self.m._tiktok_neste_horario = lambda agora=None: True
        self.m.proxima_historia = lambda: self.fail("escolheu parte")
        self.m._subir_parte_no_youtube = lambda *a, **k: self.fail("subiu")
        ficha = self.m.postar_historia()
        self.assertFalse(ficha["feito"])
        self.assertTrue(ficha["ledger_ilegivel"])
        self.assertEqual([], self.m._derrubados_pela_rede(ficha))

    def test_ledger_que_le_continua_livre(self):
        """Caso ZERO: ledger vazio (arquivo novo) libera, sem erro."""
        from contos.publicar import serie
        _trocar(self, serie, "publicados", lambda: [])
        self.assertIsNone(self.m.publicou_neste_horario("historias",
                                                        "youtube"))
        self.assertEqual([], self.diario)

    def test_os_crivos_de_fila_continuam_deixando_passar(self):
        """So a guarda de repeticao muda; teto e titulo seguem "nao sei
        deixa passar" (decisao antiga, testes proprios)."""
        alvo = type("V", (), {"id": "h3:celular:p01",
                              "fonte_id": "h3", "titulo": "Qualquer"})()
        self.assertFalse(self.m.titulo_repetido(alvo, "historias"))
        self.assertEqual([alvo], self.m._sem_fonte_cheia([alvo], "historias"))


class VoltaComLedgerIlegivelTests(unittest.TestCase):
    """O teste C do conferente, com o `_publicados_do_canal` de VERDADE.

    YouTube da h44 p06 sai, o TikTok cai por rede 3x, o ledger fica preso
    depois da 3a; builds publica e a volta final roda. Antes: o YouTube da
    MESMA p06 subia de novo (2 envios). Agora: 1.
    """

    def setUp(self):
        self.m = m = _postar()
        self.ledger, self.envios, self.preso = [], [], False
        m._linha = lambda *_a, **_k: None
        m._dormir = lambda s: None
        m.esperar_a_rede = lambda **k: True
        m._ainda_no_horario = lambda comeco, slot, **k: True
        for nome in ("avisar", "avisar_lote_nao_fechou", "_registrar_valvula",
                     "_retida_chegou_ao_tiktok", "_marcar_retido"):
            setattr(m, nome, lambda *a, **k: None)
        m.estoque_do_lote = lambda *a, **k: {}
        m.linhas_do_estoque = lambda lote: []
        m.retidos_por_canal = lambda: {}
        m.reserva_do_tiktok = lambda *a, **k: []
        m.recuperar_no_tiktok = lambda so_ver=False, canal="historias": {
            "fila": 0}
        m.recuperar_no_youtube = lambda **k: {"fila": 0}
        m.publicar_da_reserva = lambda so_ver=False: {}
        m._tiktok_neste_horario = lambda agora=None: True
        m._valvula_da_parte = lambda ficha, alvo: ""
        m.titulo_repetido = lambda *a, **k: False
        m._visibilidade_das_historias = lambda: "public"
        alvo = type("A", (), {"id": "historia_00044:celular:p06",
                              "titulo": "O Laudo (Parte 6/6)", "parte": 6,
                              "partes": 6, "fonte_id": "historia_00044"})()
        m._video_por_id = lambda vid: alvo if vid == alvo.id else None
        m.proxima_historia = lambda: (alvo, [])
        m.postar_build = lambda so_ver=False: {
            "canal": "builds", "feito": True, "alvo": "g95",
            "url": "publicado no YouTube", "tiktok": "publicado no TikTok"}
        from builds import atividade
        _trocar(self, atividade, "registrar", lambda *a, **k: None)
        from builds.publicar import tiktok
        _trocar(self, tiktok, "confirmado",
                lambda e: str(e).startswith("publicado no TikTok"))
        from contos.publicar import serie

        def publicados():
            if self.preso:
                raise OSError("ledger preso por outro processo")
            return list(self.ledger)
        _trocar(self, serie, "publicados", publicados)
        _trocar(self, serie, "registrar",
                lambda alvo, url, plat, *a, **k: self._linha(alvo.id, plat))
        tiktoks = {"n": 0}

        def subir(alvo, vis, provas):
            self.envios.append("youtube")
            return "publicado no YouTube"

        def no_tiktok(alvo, falha=None):
            self.envios.append("tiktok")
            tiktoks["n"] += 1
            if tiktoks["n"] == 3:
                self.preso = True
            falha.update({"tipo": "TikTokFalhou", "mensagem":
                          "infraestrutura: a pagina do TikTok nao abriu"})
            return ""
        m._subir_parte_no_youtube = subir
        m._tiktok_das_historias = no_tiktok

    def _linha(self, vid, plat):
        self.ledger.append({"canal": "historias", "plataforma": plat,
                            "video_id": vid, "url": "u",
                            "quando": datetime.now().isoformat(
                                timespec="seconds")})

    def test_o_youtube_da_mesma_parte_nao_sobe_duas_vezes(self):
        self.m.main([])
        self.assertEqual(1, self.envios.count("youtube"), self.envios)
        self.assertEqual(3, self.envios.count("tiktok"), self.envios)


# ------------------------------------------------------------------ item 2
_SEGURA = r"""
import sys, time
from builds import travas
print(travas._pasta(), flush=True)
with travas.trava(sys.argv[1]) as minha:
    print("PEGUEI" if minha else "NAO", flush=True)
    time.sleep(float(sys.argv[2]))
"""


class TravaDaRodadaEntreProcessosTests(unittest.TestCase):
    """Um SEGUNDO PROCESSO segura a trava, como a rodada que estourou."""

    def setUp(self):
        self.m = m = _postar()
        m._linha = lambda *_a, **_k: None
        m.esperar_a_rede = lambda **k: True
        self.avisos = []
        m.avisar = lambda r: self.avisos.append(r)
        m.avisar_lote_nao_fechou = lambda *a, **k: None
        m.estoque_do_lote = lambda *a, **k: {}
        m.linhas_do_estoque = lambda lote: []
        m.retidos_por_canal = lambda: {}
        m.reserva_do_tiktok = lambda *a, **k: []
        m.recuperar_no_tiktok = lambda so_ver=False, canal="historias": {
            "fila": 0}
        m.recuperar_no_youtube = lambda **k: {"fila": 0}
        m.publicar_da_reserva = lambda so_ver=False: {}
        self.ordem = []
        m.postar_historia = lambda so_ver=False: (
            self.ordem.append("historias") or {
                "canal": "historias", "feito": True, "alvo": "h",
                "url": "publicado no YouTube",
                "tiktok": "publicado no TikTok"})
        m.postar_build = lambda so_ver=False: (
            self.ordem.append("builds") or {
                "canal": "builds", "feito": True, "alvo": "g",
                "url": "publicado no YouTube",
                "tiktok": "publicado no TikTok"})
        self.diario = []
        from builds import atividade
        _trocar(self, atividade, "registrar",
                lambda *a, **k: self.diario.append(a))
        from builds.publicar import tiktok
        _trocar(self, tiktok, "confirmado",
                lambda e: str(e).startswith("publicado no TikTok"))
        self.telegram = []
        m._mandar_no_telegram = lambda texto: self.telegram.append(texto)
        m.INTERVALO_DE_OLHAR_A_DONA_S = 0.2
        m._cabe_antes_do_proximo = lambda *a, **k: True
        # Ficha velha de outro teste nao pode decidir este.
        try:
            m._arquivo_da_dona().unlink()
        except FileNotFoundError:
            pass

    def _outro_processo(self, segundos: float):
        from builds import travas
        ambiente = dict(os.environ)
        ambiente["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
        proc = subprocess.Popen(
            [sys.executable, "-c", _SEGURA, self.m.TRAVA_DA_RODADA,
             str(segundos)],
            stdout=subprocess.PIPE, text=True, env=ambiente)
        self.addCleanup(proc.wait, 30)
        self.addCleanup(proc.kill)
        pasta = proc.stdout.readline().strip()
        # O mesmo diretorio de travas, ou o teste nao prova nada.
        self.assertEqual(str(travas._pasta()), pasta)
        self.assertEqual("PEGUEI", proc.stdout.readline().strip())
        return proc

    def test_rodada_anterior_viva_a_nova_nao_publica_e_avisa(self):
        self._outro_processo(30)
        self.m.ESPERA_PELA_RODADA_ANTERIOR_S = 1.0
        self.assertEqual(1, self.m.main([]))
        self.assertEqual([], self.ordem, "nunca publica junto com a outra")
        self.assertTrue(self.avisos)
        motivo = self.avisos[0][0]["motivo"]
        # Sem ficha (a outra pegou a trava crua): diz que nao sabe quem e.
        self.assertIn("outra publicacao (sem ficha de quem e) ainda estava "
                      "rodando depois de 1 s de espera", motivo)
        self.assertNotIn("0 min", motivo)
        self.assertTrue(any("ainda estava rodando" in str(a)
                            for a in self.diario))
        self.assertEqual([], self.telegram, "ninguem foi morto")

    def test_rodada_anterior_que_termina_a_tempo_libera_a_nova(self):
        import time
        self._outro_processo(2)
        self.m.ESPERA_PELA_RODADA_ANTERIOR_S = 30.0
        antes = time.monotonic()
        self.assertEqual(0, self.m.main([]))
        self.assertEqual(["historias", "builds"], self.ordem)
        self.assertGreaterEqual(time.monotonic() - antes, 1.0,
                                "so andou depois que a outra soltou")

    def test_so_vendo_nao_espera_ninguem(self):
        self._outro_processo(30)
        self.m.ESPERA_PELA_RODADA_ANTERIOR_S = 30.0
        self.m.main(["--ver"])
        self.assertEqual(["historias", "builds"], self.ordem)


# ------------------------------------------------- a dona pendurada (0b5b6a9)
_PENDURADA = r"""
import importlib.util, subprocess, sys, time
spec = importlib.util.spec_from_file_location("postar_pendurado", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m._linha = lambda *a, **k: None
with m._trava_da_rodada(0, sys.argv[2]) as vez:
    # O "Chrome" dela: um filho que fica, como o que o Playwright abre.
    filho = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    print("PEGUEI" if vez["minha"] else "NAO", filho.pid, flush=True)
    time.sleep(600)
"""


def _vivo(pid) -> bool:
    return _postar()._criacao_do_processo(pid) is not None


class DonaPenduradaTests(unittest.TestCase):
    """`_pode_matar`, so a decisao: a idade e o horario sao simulados."""

    def setUp(self):
        self.m = _postar()
        self.meu = datetime(2026, 10, 6, 21, 37)
        self.agora = datetime(2026, 10, 6, 21, 48).timestamp()

    def _dona(self, minutos, horario="2026-10-06T20:37", tipo="rodada"):
        return {"pid": 4242, "criado": 1000.0, "tipo": tipo,
                "horario": horario, "inicio": self.agora - minutos * 60}

    def _decide(self, dona, criacao=lambda pid: 1000.0):
        return self.m._pode_matar(dona, agora=self.agora,
                                  meu_horario=self.meu, criacao=criacao)[0]

    def test_horario_anterior_viva_ha_mais_de_70_min_morre(self):
        self.assertEqual(70, self.m.RODADA_PENDURADA_MIN)
        self.assertTrue(self._decide(self._dona(71)))

    def test_69_min_ainda_e_rodada_lenta(self):
        self.assertFalse(self._decide(self._dona(69)))

    def test_nunca_mata_o_mesmo_horario(self):
        self.assertFalse(self._decide(self._dona(300,
                                                 "2026-10-06T21:37")))

    def test_nunca_mata_o_escoar_do_app(self):
        self.assertFalse(self._decide(self._dona(300, tipo="tudo")))

    def test_pid_reaproveitado_nao_morre(self):
        self.assertFalse(self._decide(self._dona(300),
                                      criacao=lambda pid: 5000.0))

    def test_processo_que_ja_morreu_nao_e_morto(self):
        self.assertFalse(self._decide(self._dona(300),
                                      criacao=lambda pid: None))

    def test_caso_zero_sem_ficha(self):
        self.assertFalse(self._decide(None))
        self.assertFalse(self._decide({"pid": "x"}))

    def test_o_aviso_diz_quem_e_a_dona(self):
        d = self.m._descrever_dona
        self.assertIn("escoar' do app", d(self._dona(5, tipo="tudo")))
        self.assertIn("recuperar video privado",
                      d(self._dona(5, tipo="recuperar")))
        self.assertIn("rodada da grade das 20:37", d(self._dona(5)))
        self.assertNotIn("rodada", d(self._dona(5, tipo="tudo")))

    def test_os_passos_extras_respeitam_a_margem(self):
        m = self.m
        m._linha = lambda *_a, **_k: None
        self.assertTrue(m._cabe_antes_do_proximo(
            agora=datetime(2026, 10, 6, 21, 16)))
        self.assertFalse(m._cabe_antes_do_proximo(
            agora=datetime(2026, 10, 6, 21, 18)))


class LimiteDaTarefaTests(unittest.TestCase):
    """PT72H -> PT2H. O Agendador so encerra o wscript (medido em 06/10: o
    cmd e o python sobreviveram ao limite de 1 min), mas devolve a tarefa:
    com IgnoreNew, a pendurada prendia o mesmo horario do dia seguinte."""

    def test_limite_invalido_nem_chega_ao_powershell(self):
        from builds import tarefas_windows as tw
        _trocar(self, tw, "_rodar", lambda *a, **k: self.fail("rodou"))
        self.assertFalse(tw.limitar_execucao("x", "2 horas")["ok"])

    def test_o_script_troca_so_o_limite(self):
        from builds import tarefas_windows as tw
        visto = {}

        def rodar(script, nome, timeout):
            visto.update(script=script, nome=nome)
            return 0, "", ""
        _trocar(self, tw, "_rodar", rodar)
        self.assertTrue(tw.limitar_execucao("NeuralFights_postar_20")["ok"])
        self.assertIn("$s.ExecutionTimeLimit = 'PT2H'", visto["script"])
        self.assertEqual("NeuralFights_postar_20", visto["nome"])

    def test_instalar_aplica_o_limite_de_2_horas(self):
        m = _postar()
        from builds import tarefas_windows as tw
        pedidos = []
        m.escrever_lancador = lambda: "E:/x/postar.cmd"
        m.subprocess = type("S", (), {
            "run": staticmethod(lambda *a, **k: type(
                "P", (), {"returncode": 0, "stdout": b"", "stderr": b""})()),
            "CREATE_NO_WINDOW": 0})
        _trocar(self, tw, "endurecer", lambda nome: {"ok": True})
        _trocar(self, tw, "limitar_execucao",
                lambda nome, limite: pedidos.append((nome, limite))
                or {"ok": True})
        ficha = m.instalar("20:37", nome="NeuralFights_postar_20")
        self.assertTrue(ficha["limite"])
        self.assertEqual([("NeuralFights_postar_20", "PT2H")], pedidos)


class DonaPenduradaEntreProcessosTests(TravaDaRodadaEntreProcessosTests):
    """Dois processos de verdade: a dona 'pendurada' dorme segurando a trava,
    com um filho; a idade e o horario dela sao simulados na ficha."""

    def _pendurada(self, tipo="rodada"):
        ambiente = dict(os.environ)
        ambiente["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
        proc = subprocess.Popen(
            [sys.executable, "-c", _PENDURADA, str(POSTAR), tipo],
            stdout=subprocess.PIPE, text=True, env=ambiente)
        estado, filho = proc.stdout.readline().split()
        filho = int(filho)
        self.addCleanup(lambda: subprocess.run(
            ["taskkill", "/F", "/PID", str(filho)], capture_output=True))
        self.addCleanup(proc.wait, 30)
        self.addCleanup(proc.kill)
        self.assertEqual("PEGUEI", estado)
        dona = self.m._ler_dona()
        self.assertEqual(proc.pid, dona["pid"])
        return proc, filho, dona

    def _envelhecer(self, dona, minutos, horario):
        dona = dict(dona, inicio=dona["inicio"] - minutos * 60,
                    horario=horario.isoformat(timespec="minutes"))
        self.m._arquivo_da_dona().write_text(json.dumps(dona),
                                             encoding="utf-8")

    def test_pendurada_de_horario_anterior_morre_com_o_filho_e_a_nova_publica(
            self):
        proc, filho, dona = self._pendurada()
        anterior = self.m._inicio_do_horario() - timedelta(hours=3)
        self._envelhecer(dona, 71, anterior)
        # So os descendentes DELA com este nome morrem junto (no teste o
        # "Chrome" e um python; na vida, chrome.exe e o node do Playwright).
        self.m.FILHOS_QUE_MORREM_JUNTO = ("python.exe",)
        self.m.ESPERA_PELA_RODADA_ANTERIOR_S = 30.0
        self.assertEqual(0, self.m.main([]))
        self.assertIsNotNone(proc.wait(15), "a dona morreu")
        self.assertFalse(_vivo(filho), "o filho que sobrou morreu")
        self.assertEqual(["historias", "builds"], self.ordem)
        self.assertEqual(1, len(self.telegram))
        self.assertIn("matei a rodada da grade", self.telegram[0])
        self.assertIn(str(filho), self.telegram[0])
        # A ficha agora e da rodada nova.
        self.assertEqual(os.getpid(), self.m._ler_dona()["pid"])

    def test_pendurada_do_MESMO_horario_nunca_morre(self):
        proc, filho, dona = self._pendurada()
        self._envelhecer(dona, 300, self.m._inicio_do_horario())
        self.m.ESPERA_PELA_RODADA_ANTERIOR_S = 1.0
        self.assertEqual(1, self.m.main([]))
        self.assertIsNone(proc.poll(), "continua viva")
        self.assertTrue(_vivo(filho))
        self.assertEqual([], self.ordem)
        self.assertEqual([], self.telegram)
        self.assertIn("rodada da grade", self.avisos[0][0]["motivo"])

    def test_escoar_do_app_nao_morre_e_o_aviso_diz_o_que_e(self):
        proc, filho, dona = self._pendurada("tudo")
        anterior = self.m._inicio_do_horario() - timedelta(hours=3)
        self._envelhecer(dona, 300, anterior)
        self.m.ESPERA_PELA_RODADA_ANTERIOR_S = 1.0
        self.assertEqual(1, self.m.main([]))
        self.assertIsNone(proc.poll())
        motivo = self.avisos[0][0]["motivo"]
        self.assertIn("o 'escoar' do app (postar.py --tudo)", motivo)
        self.assertNotIn("rodada anterior", motivo)


if __name__ == "__main__":
    unittest.main()
