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
        self.assertIn("rodada anterior", self.avisos[0][0]["motivo"])
        self.assertTrue(any("rodada anterior" in str(a) for a in self.diario))

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


if __name__ == "__main__":
    unittest.main()
