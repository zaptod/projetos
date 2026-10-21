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
        # A fila propria do TikTok (19/10/2026) le o catalogo REAL: aqui ela
        # leva a parte da rodada.
        m._vez_do_tiktok_historias = lambda novo=None: (
            alvo if novo is not None else None, "")
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


class _BaseDaRodada(unittest.TestCase):
    """Base sem testes: a rodada com dubles e o segundo processo."""

    def setUp(self):
        self.m = m = _postar()
        m._linha = lambda *_a, **_k: None
        # A ORDEM DOS CANAIS LE O RELOGIO (21/10/2026, `_ordem_dos_canais`):
        # estes casos nao sao sobre o horario, entao ficam fora do horario dos
        # duelos — senao a suite ficava vermelha das 09:37 as 12:07.
        m._ordem_dos_canais = lambda agora=None: m.ORDEM_DO_RELATORIO
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
        for velha in (m._arquivo_da_dona(), m._arquivo_da_reserva()):
            try:
                velha.unlink()
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

class TravaDaRodadaEntreProcessosTests(_BaseDaRodada):
    """Um SEGUNDO PROCESSO segura a trava, como a rodada que estourou."""

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


# ------------------------------------------- a dona pendurada (0b5b6a9, 65dc781)
_PENDURADA = r"""
import importlib.util, subprocess, sys, time
spec = importlib.util.spec_from_file_location("postar_pendurado", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m._linha = lambda *a, **k: None
with m._trava_da_rodada(0, sys.argv[2]) as vez:
    # O "Chrome" dela: um filho que fica, como o que o Playwright abre.
    filho = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    if len(sys.argv) > 3:
        # Travada DEPOIS do clique, como o `page.evaluate` sem prazo: a saida
        # com pulso ve a frase do publicador e a ficha grava a etapa.
        import io
        real = sys.stdout
        sys.stdout = m._SaidaComPulso(io.StringIO())
        with m._em_voo("historias", sys.argv[3], "youtube"):
            print("[youtube-web] arquivo entregue (final_celular_p06.mp4)")
            print("[youtube-web] publicar clicado; confirmando...")
            real.write(f"PEGUEI {filho.pid}\n"); real.flush()
            time.sleep(600)
    real = sys.stdout
    real.write(("PEGUEI" if vez["minha"] else "NAO") + f" {filho.pid}\n")
    real.flush()
    time.sleep(600)
"""


def _vivo(pid) -> bool:
    return _postar()._criacao_do_processo(pid) is not None


class DonaPenduradaTests(unittest.TestCase):
    """`_pode_matar`, so a decisao: idade, pulso e horario simulados."""

    def setUp(self):
        self.m = _postar()
        self.meu = datetime(2026, 10, 6, 21, 37)
        self.agora = datetime(2026, 10, 6, 21, 48).timestamp()

    def _dona(self, minutos, horario="2026-10-06T20:37", tipo="rodada",
              pulso=None):
        bruta = {"pid": 4242, "criado": 1000.0, "tipo": tipo,
                 "horario": horario, "inicio": self.agora - minutos * 60,
                 "pulso": self.agora - (minutos if pulso is None
                                        else pulso) * 60}
        dona, problema = self.m._ficha_valida(bruta)
        self.assertIsNone(problema)
        return dona

    def _decide(self, dona, criacao=lambda pid: 1000.0):
        return self.m._pode_matar(dona, agora=self.agora,
                                  meu_horario=self.meu, criacao=criacao)[0]

    def test_horario_anterior_viva_ha_mais_de_70_min_e_pulso_parado_morre(self):
        self.assertEqual(70, self.m.RODADA_PENDURADA_MIN)
        self.assertEqual(20, self.m.PULSO_PARADO_MIN)
        self.assertTrue(self._decide(self._dona(71, pulso=21)))

    def test_69_min_ainda_e_rodada_lenta(self):
        self.assertFalse(self._decide(self._dona(69)))

    def test_lenta_mas_viva_nunca_morre(self):
        """O conferente do 65dc781: uma tentativa de mais de ~21 min faria a
        saudavel morrer aos 70. Com pulso de 19 min atras, ela vive — por
        mais velha que seja."""
        self.assertFalse(self._decide(self._dona(300, pulso=19)))

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

    def test_ficha_com_tipos_errados_e_invalida_e_nao_levanta(self):
        """As fichas do conferente (`fichas.py`): cada uma vira "invalida",
        sem excecao — antes, fuso e texto davam TypeError/ValueError fora
        do `try`, e 'tipo' lista chegava a MATAR."""
        boa = {"pid": 4242, "criado": 1000.0, "tipo": "rodada",
               "horario": "2026-10-06T20:37", "inicio": 1.0, "pulso": 1.0}
        ruins = {
            "lista": [1, 2],
            "vazio": {},
            "fuso": dict(boa, horario="2026-10-06T20:37+00:00"),
            "criado_texto": dict(boa, criado="ontem"),
            "inicio_nan": dict(boa, inicio=float("nan")),
            "horario_numero": dict(boa, horario=2037),
            "tipo_lista": dict(boa, tipo=["rodada"]),
            "pid_bool": dict(boa, pid=True),
            "voo_torto": dict(boa, em_voo={"canal": "x"}),
        }
        for nome, dados in ruins.items():
            with self.subTest(ficha=nome):
                dona, problema = self.m._ficha_valida(dados)
                self.assertIsNone(dona)
                self.assertTrue(problema)
                self.assertFalse(self._decide(dona))
        self.assertIsNotNone(self.m._ficha_valida(boa)[0])

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


class DescendentesTests(unittest.TestCase):
    """Filho so conta se nasceu DEPOIS do pai (conferente do 65dc781,
    `orfao.py`: o Windows guarda o pid do pai morto e o reaproveita)."""

    def test_orfao_de_outro_pai_com_o_mesmo_pid_nao_entra(self):
        m = _postar()
        processos = [
            {"pid": 100, "pai": 1, "nome": "python.exe", "criado": 5000.0},
            {"pid": 200, "pai": 100, "nome": "node.exe", "criado": 5001.0},
            {"pid": 300, "pai": 200, "nome": "chrome.exe", "criado": 5002.0},
            # O Chrome de um pai ANTIGO que tambem teve o pid 100.
            {"pid": 400, "pai": 100, "nome": "chrome.exe", "criado": 10.0},
            {"pid": 500, "pai": 100, "nome": "chrome.exe", "criado": None},
        ]
        achados = {p["pid"] for p in m._descendentes(100, processos, 5000.0)}
        self.assertEqual({200, 300}, achados)
        self.assertEqual([], m._descendentes(100, processos, None))


class SaidaComPulsoTests(unittest.TestCase):
    """O voo na ficha, escrito pelas frases dos publicadores."""

    def setUp(self):
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.addCleanup(self.m._DONA.clear)
        self.m._gravar_dona("rodada")

    def _ficha(self):
        return json.loads(self.m._arquivo_da_dona().read_text(
            encoding="utf-8"))

    def test_entregue_e_clicou_vao_ao_disco_na_hora(self):
        import io
        saida = self.m._SaidaComPulso(io.StringIO())
        with self.m._em_voo("historias", "h44:celular:p06", "youtube"):
            self.assertEqual("escolhido", self._ficha()["em_voo"]["etapa"])
            saida.write("[youtube-web] arquivo entregue (x.mp4); subindo\n")
            self.assertEqual("entregue", self._ficha()["em_voo"]["etapa"])
            saida.write("[youtube-web] publicar clicado; confirmando...\n")
            voo = self._ficha()["em_voo"]
            self.assertEqual(("clicou", "h44:celular:p06", "youtube"),
                             (voo["etapa"], voo["alvo"], voo["destino"]))
            # Nunca volta atras.
            saida.write("[youtube-web] arquivo entregue (pedaco 2)\n")
            self.assertEqual("clicou", self._ficha()["em_voo"]["etapa"])
        self.assertIsNone(self._ficha()["em_voo"], "pousou")

    def test_as_frases_existem_nos_publicadores(self):
        """Contrato: se a frase mudar la, a etapa para de ser gravada."""
        raiz = (Path(__file__).resolve().parents[2] / "random_builds"
                / "builds" / "publicar")
        for nome in ("youtube_web.py", "tiktok.py"):
            fonte = (raiz / nome).read_text(encoding="utf-8")
            for frase, _etapa in self.m.ETAPAS_DO_VOO:
                self.assertIn(f'passo("{frase}' if frase.startswith("publicar")
                              else f'passo(f"{frase}', fonte, (nome, frase))

    def test_os_quatro_funis_voam(self):
        fonte = POSTAR.read_text(encoding="utf-8")
        for decorador, funil in (
                ('@_voando("historias", "youtube")',
                 "def _subir_parte_no_youtube("),
                ('@_voando("historias", "tiktok")',
                 "def _tiktok_das_historias("),
                ('@_voando("builds", "youtube")', "def _youtube_dos_builds("),
                ('@_voando("builds", "tiktok")', "def _tiktok_dos_builds(")):
            self.assertIn(f"{decorador}\n{funil}", fonte)
        # Com o laudo (11/10/2026): a marca `clicou` chega a ficha por ele.
        self.assertIn("url = _youtube_dos_builds(alvo, laudo_yt)", fonte)


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
        _trocar(self, tw, "garantir_vbs", lambda pasta=None: "C:/rt/oculto.vbs")
        ficha = m.instalar("20:37", nome="NeuralFights_postar_20")
        self.assertTrue(ficha["limite"])
        self.assertEqual([("NeuralFights_postar_20", "PT2H")], pedidos)

    def _instalar_e_ver(self, *args, **kwargs):
        m = _postar()
        from builds import tarefas_windows as tw
        chamadas = []
        m.escrever_lancador = lambda: "E:/x/postar.cmd"
        m.subprocess = type("S", (), {
            "run": staticmethod(lambda a, **k: chamadas.append(a) or type(
                "P", (), {"returncode": 0, "stdout": b"", "stderr": b""})()),
            "CREATE_NO_WINDOW": 0})
        _trocar(self, tw, "endurecer", lambda nome: {"ok": True})
        _trocar(self, tw, "limitar_execucao",
                lambda nome, limite: {"ok": True})
        _trocar(self, tw, "garantir_vbs", lambda pasta=None: "C:/rt/oculto.vbs")
        return m.instalar(*args, **kwargs), chamadas

    def test_instalar_usa_wscript_oculto(self):
        """SCR-4 (14/10/2026): era o unico instalador sem o `oculto.vbs`;
        reinstalar voltava com 10 janelas pretas por dia."""
        _ficha, chamadas = self._instalar_e_ver("17:57",
                                                nome="NeuralFights_postar_17")
        acao = chamadas[0][chamadas[0].index("/TR") + 1]
        self.assertIn("wscript.exe", acao)
        self.assertIn("//B", acao)
        self.assertTrue(acao.endswith('"E:/x/postar.cmd"'), acao)

    def test_hora_usa_nome_com_sufixo(self):
        """SCR-4: `--hora 17:57` recriava `NeuralFights_postar` (sem sufixo),
        a tarefa antiga que `instalar_grade` apaga para nao dobrar a postagem."""
        ficha, chamadas = self._instalar_e_ver("17:57")
        self.assertEqual("NeuralFights_postar_17", ficha["tarefa"])
        self.assertEqual("NeuralFights_postar_17",
                         chamadas[0][chamadas[0].index("/TN") + 1])

    def test_lancador_sem_cr_cr_lf(self):
        """SCR-11: `write_text` com CRLF gravava CR CR LF no `postar.cmd`."""
        import tempfile
        from pathlib import Path
        m = _postar()
        with tempfile.TemporaryDirectory() as tmp:
            m.RAIZ = Path(tmp)
            texto = m.escrever_lancador().read_bytes()
        self.assertNotIn(b"\r\r\n", texto)
        self.assertIn(b"\r\n", texto)


class _BaseDaDona(_BaseDaRodada):
    """Dois processos de verdade: a dona 'pendurada' dorme segurando a trava,
    com um filho; idade, pulso e horario dela sao simulados na ficha. A lista
    "a conferir" vai para uma pasta do teste."""

    VOO = "historia_00044:celular:p06"
    OUTRO = "historia_00051:celular:p04"

    def setUp(self):
        super().setUp()
        import tempfile
        from builds.publicar import desfecho
        pasta = Path(tempfile.mkdtemp(dir=os.environ.get("TEMP")))
        _trocar(self, desfecho, "arquivo_a_conferir",
                lambda canal, plataforma="tiktok":
                pasta / f"{canal}_{plataforma}_a_conferir.json")
        self.escolhidos = []
        m = self.m
        alvos = [type("V", (), {"id": i})() for i in (self.VOO, self.OUTRO)]

        # A escolha de VERDADE do que fica fora da fila: `_sem_a_conferir`.
        def postar_historia(so_ver=False):
            self.ordem.append("historias")
            livres = m._sem_a_conferir(list(alvos), "historias")
            self.escolhidos.append(livres[0].id if livres else None)
            return {"canal": "historias", "feito": True,
                    "alvo": self.escolhidos[-1],
                    "url": "publicado no YouTube",
                    "tiktok": "publicado no TikTok"}
        m.postar_historia = postar_historia

    def _pendurada(self, tipo="rodada", voo=None):
        ambiente = dict(os.environ)
        ambiente["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
        comando = [sys.executable, "-c", _PENDURADA, str(POSTAR), tipo]
        if voo:
            comando.append(voo)
        proc = subprocess.Popen(comando, stdout=subprocess.PIPE, text=True,
                                env=ambiente)
        estado, filho = proc.stdout.readline().split()
        filho = int(filho)
        self.addCleanup(lambda: subprocess.run(
            ["taskkill", "/F", "/PID", str(filho)], capture_output=True))
        self.addCleanup(proc.wait, 30)
        self.addCleanup(proc.kill)
        self.assertEqual("PEGUEI", estado)
        dona, problema = self.m._ler_dona()
        self.assertIsNone(problema)
        self.assertEqual(proc.pid, dona["pid"])
        return proc, filho, dona

    def _envelhecer(self, dona, minutos, horario, pulso=None, **troca):
        bruta = {k: v for k, v in dona.items() if k != "horario_dt"}
        import time
        agora = time.time()
        bruta.update(inicio=agora - minutos * 60,
                     pulso=agora - (minutos if pulso is None else pulso) * 60,
                     horario=horario.isoformat(timespec="minutes"), **troca)
        self.m._arquivo_da_dona().write_text(json.dumps(bruta),
                                             encoding="utf-8")

    def _anterior(self):
        return self.m._inicio_do_horario() - timedelta(hours=3)

class DonaPenduradaEntreProcessosTests(_BaseDaDona):
    """Dois processos de verdade (ver `_BaseDaDona`)."""

    def test_pendurada_de_horario_anterior_morre_com_o_filho_e_a_nova_publica(
            self):
        proc, filho, dona = self._pendurada()
        self._envelhecer(dona, 71, self._anterior())
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
        self.assertEqual(os.getpid(), self.m._ler_dona()[0]["pid"])

    def test_morta_DEPOIS_do_clique_a_nova_nao_sobe_o_mesmo_video(self):
        """O defeito MEDIO do 65dc781: a dona travou depois do clique no
        YouTube da h44 p06. A nova mata, poe a p06 "a conferir" no YouTube
        ANTES de escolher, e leva outra parte."""
        from builds.publicar import desfecho
        proc, filho, dona = self._pendurada(voo=self.VOO)
        self.assertEqual("clicou", dona["em_voo"]["etapa"])
        self._envelhecer(dona, 71, self._anterior())
        self.m.ESPERA_PELA_RODADA_ANTERIOR_S = 30.0
        self.assertEqual(0, self.m.main([]))
        self.assertIsNotNone(proc.wait(15))
        self.assertIn(self.VOO, desfecho.a_conferir("historias", "youtube"))
        self.assertEqual([self.OUTRO], self.escolhidos)
        self.assertTrue(any("pode ter saido publico" in t
                            for t in self.telegram), self.telegram)

    def test_dona_que_morreu_sozinha_com_voo_no_ar_tambem_pousa(self):
        """Sem ninguem matar: a dona caiu (energia, Ctrl+C) depois do clique.
        A trava esta livre, mas a ficha diz o que ficou no ar."""
        from builds.publicar import desfecho
        proc, filho, dona = self._pendurada(voo=self.VOO)
        proc.kill()
        proc.wait(15)
        self.assertEqual(0, self.m.main([]))
        self.assertIn(self.VOO, desfecho.a_conferir("historias", "youtube"))
        self.assertEqual([self.OUTRO], self.escolhidos)

    def test_marca_que_nao_grava_a_rodada_nao_publica(self):
        from builds.publicar import desfecho
        proc, filho, dona = self._pendurada(voo=self.VOO)
        proc.kill()
        proc.wait(15)

        def quebra(*a, **k):
            raise OSError("lista a conferir presa")
        _trocar(self, desfecho, "marcar_para_conferir", quebra)
        self.assertEqual(1, self.m.main([]))
        self.assertEqual([], self.ordem)
        # A ficha velha fica: a proxima rodada tenta pousar de novo.
        self.assertEqual(self.VOO, self.m._ler_dona()[0]["em_voo"]["alvo"])

    def test_lenta_mas_viva_nao_morre(self):
        proc, filho, dona = self._pendurada()
        self._envelhecer(dona, 300, self._anterior(), pulso=1)
        self.m.ESPERA_PELA_RODADA_ANTERIOR_S = 1.0
        self.assertEqual(1, self.m.main([]))
        self.assertIsNone(proc.poll(), "continua viva")
        self.assertEqual([], self.telegram)

    def test_ficha_invalida_espera_nao_mata_e_avisa(self):
        proc, filho, dona = self._pendurada()
        self._envelhecer(dona, 300, self._anterior())
        bruta = json.loads(self.m._arquivo_da_dona().read_text("utf-8"))
        bruta["horario"] += "+00:00"           # o TypeError do conferente
        self.m._arquivo_da_dona().write_text(json.dumps(bruta), "utf-8")
        self.m.ESPERA_PELA_RODADA_ANTERIOR_S = 1.0
        self.assertEqual(1, self.m.main([]))
        self.assertIsNone(proc.poll(), "continua viva")
        self.assertTrue(any("ficha da trava da rodada esta invalida"
                            in str(a) for a in self.diario), self.diario)

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
        self._envelhecer(dona, 300, self._anterior())
        self.m.ESPERA_PELA_RODADA_ANTERIOR_S = 1.0
        self.assertEqual(1, self.m.main([]))
        self.assertIsNone(proc.poll())
        motivo = self.avisos[0][0]["motivo"]
        self.assertIn("o 'escoar' do app (postar.py --tudo)", motivo)
        self.assertNotIn("rodada anterior", motivo)


class FichaAnteriorSemDonaVivaTests(_BaseDaDona):
    """A trava esta livre e a ficha da rodada anterior ficou no disco
    (conferente do 9025da2). Herda a escolha de verdade (`_sem_a_conferir`)
    e a lista "a conferir" na pasta do teste."""

    BOA = {"pid": 4242, "criado": 1000.0, "inicio": 1000.0, "pulso": 1000.0,
           "horario": "2026-10-06T12:07", "tipo": "rodada", "comando": "x"}

    def _ficha(self, conteudo):
        caminho = self.m._arquivo_da_dona()
        if isinstance(conteudo, bytes):
            caminho.write_bytes(conteudo)
        else:
            caminho.write_text(json.dumps(conteudo), encoding="utf-8")
        return caminho

    def _voo(self, etapa="clicou", **troca):
        return dict({"canal": "historias", "alvo": self.VOO,
                     "destino": "youtube", "etapa": etapa}, **troca)

    def _marcados(self):
        from builds.publicar import desfecho
        return desfecho.a_conferir("historias", "youtube")

    def test_voo_em_escolhido_NAO_pousa(self):
        """O mutante que sobreviveu: antes da entrega nada subiu; marcar
        prenderia o video a toa. A rodada segue e pode leva-lo."""
        self._ficha(dict(self.BOA, em_voo=self._voo("escolhido")))
        self.assertEqual(0, self.m.main([]))
        self.assertNotIn(self.VOO, self._marcados())
        self.assertEqual([self.VOO], self.escolhidos)

    def test_ficha_invalida_com_voo_inteiro_clicou_pousa(self):
        """Ficha que nao valida (fuso no horario), mas com o voo inteiro:
        o voo pousa como qualquer outro, e a rodada leva outra parte."""
        self._ficha(dict(self.BOA, horario="2026-10-06T12:07+00:00",
                         em_voo=self._voo("clicou")))
        self.assertEqual(0, self.m.main([]))
        self.assertIn(self.VOO, self._marcados())
        self.assertEqual([self.OUTRO], self.escolhidos)
        self.assertTrue(any("ficha da trava da rodada esta invalida"
                            in str(a) for a in self.diario))

    def test_ficha_invalida_com_voo_torto_nao_publica(self):
        caminho = self._ficha(dict(self.BOA, criado="ontem",
                                   em_voo={"etapa": "clicou"}))
        antes = caminho.read_bytes()
        self.assertEqual(1, self.m.main([]))
        self.assertEqual([], self.ordem)
        self.assertEqual(antes, caminho.read_bytes(), "a ficha fica")
        self.assertIn("nao da para saber", self.avisos[0][0]["motivo"])

    def test_ficha_ilegivel_nao_publica(self):
        self._ficha(b"\x00{ isto nao e json")
        self.assertEqual(1, self.m.main([]))
        self.assertEqual([], self.ordem)
        self.assertIn("nao da para saber", self.avisos[0][0]["motivo"])

    def test_ficha_invalida_sem_voo_segue(self):
        self._ficha(dict(self.BOA, horario="2026-10-06T12:07+00:00",
                         em_voo=None))
        self.assertEqual(0, self.m.main([]))
        self.assertEqual([self.VOO], self.escolhidos)

    def test_caso_zero_sem_ficha_segue(self):
        self.assertFalse(self.m._arquivo_da_dona().exists())
        self.assertEqual(0, self.m.main([]))
        self.assertEqual([self.VOO], self.escolhidos)

    # --- queda de energia na gravacao (conferente do 78112e5) ------------
    def _reserva(self, conteudo):
        caminho = self.m._arquivo_da_reserva()
        if isinstance(conteudo, bytes):
            caminho.write_bytes(conteudo)
        else:
            caminho.write_text(json.dumps(conteudo), encoding="utf-8")

    def test_principal_vazia_e_bak_com_voo_clicou_pousa(self):
        self._ficha(b"")
        self._reserva(dict(self.BOA, em_voo=self._voo("clicou")))
        self.assertEqual(0, self.m.main([]))
        self.assertIn(self.VOO, self._marcados())
        self.assertEqual([self.OUTRO], self.escolhidos)

    def test_principal_so_de_NUL_e_bak_sem_voo_segue_e_publica(self):
        self._ficha(b"\x00" * 205)
        self._reserva(dict(self.BOA, em_voo=None))
        self.assertEqual(0, self.m.main([]))
        self.assertNotIn(self.VOO, self._marcados())
        self.assertEqual([self.VOO], self.escolhidos)

    def test_principal_e_bak_ilegiveis_nao_publica(self):
        self._ficha(b"\x00" * 205)
        self._reserva(b"")
        self.assertEqual(1, self.m.main([]))
        self.assertEqual([], self.ordem)
        self.assertIn("apague as duas fichas", self.avisos[0][0]["motivo"])

    def test_principal_vazia_sem_bak_nao_publica(self):
        """Nada responde: nao da para saber (ficha VAZIA nao e "sem ficha")."""
        self._ficha(b"")
        self.assertEqual(1, self.m.main([]))
        self.assertEqual([], self.ordem)

    def test_principal_sumiu_no_meio_da_troca_decide_pela_bak(self):
        """Queda entre as duas trocas: so a `.bak` existe."""
        self._reserva(dict(self.BOA, em_voo=self._voo("entregue")))
        self.assertEqual(0, self.m.main([]))
        self.assertIn(self.VOO, self._marcados())
        self.assertEqual([self.OUTRO], self.escolhidos)

    def test_voo_torto_na_principal_e_bak_boa_decide_pela_bak(self):
        self._ficha(dict(self.BOA, criado="ontem", em_voo={"etapa": "x"}))
        self._reserva(dict(self.BOA, em_voo=None))
        self.assertEqual(0, self.m.main([]))
        self.assertEqual([self.VOO], self.escolhidos)

    # --- a `.bak` uma gravacao atras (conferente do f79a894) -------------
    # Medido as 23:47 de 06/10/2026, depois do 23:37: principal com
    # `em_voo: null` e a `.bak` com {"canal": "builds", "alvo":
    # "generation_00096:estreia:celular", "destino": "tiktok", "etapa":
    # "clicou", "desde": 23:42:21} — e a linha do TikTok dela no ledger as
    # 23:42:50. Sem o conserto, principal perdida = "a conferir" (+ Telegram)
    # para um video que ja tinha saido.
    # 06/10/2026 23:42:21 na hora LOCAL de quem roda, como o ledger grava.
    # Era o epoch fixo 1791340941.21 -- 23:42:21 so no fuso dele (-03); no
    # runner do CI, em UTC, o voo "comecava" as 02:42 e a linha do ledger
    # ficava de antes dele (CI 38625290567).
    DESDE = datetime(2026, 10, 6, 23, 42, 21, 210684).timestamp()

    def _ledger(self, *linhas, quebra=False):
        def publicados(canal):
            if quebra:
                raise self.m.LedgerIlegivel(f"{canal}: OSError: preso")
            return [dict(l) for l in linhas]
        self.m._publicados_do_canal = publicados

    def _linha(self, quando, vid=None, plataforma="youtube", publicado=True):
        return {"quando": quando, "plataforma": plataforma,
                "video_id": vid or self.VOO, "publicado": publicado,
                "url": "publicado no YouTube"}

    def test_o_pouso_grava_a_principal_e_a_bak(self):
        """As duas fichas sem voo depois do pouso. Antes: a `.bak` ficava com
        o ultimo `clicou`."""
        self.addCleanup(self.m._DONA.clear)
        self.m._gravar_dona("rodada")
        with self.m._em_voo("builds", "generation_00096:estreia:celular",
                            "tiktok"):
            self.m._ao_escrever("[tiktok] arquivo entregue (x.mp4)")
            self.m._ao_escrever("[tiktok] publicar clicado; confirmando...")
        ler = lambda c: json.loads(c.read_text(encoding="utf-8"))  # noqa: E731
        self.assertIsNone(ler(self.m._arquivo_da_dona())["em_voo"])
        self.assertIsNone(ler(self.m._arquivo_da_reserva())["em_voo"])

    def test_principal_vazia_e_bak_com_voo_ja_no_ledger_nao_marca(self):
        """O caso medido: o voo da `.bak` ja saiu e esta no ledger."""
        self._ficha(b"")
        self._reserva(dict(self.BOA, em_voo=self._voo("clicou",
                                                       desde=self.DESDE)))
        self._ledger(self._linha("2026-10-06T23:42:50"))
        self.assertEqual(0, self.m.main([]))
        self.assertNotIn(self.VOO, self._marcados())
        self.assertFalse(any("pode ter saido publico" in t
                             for t in self.telegram), self.telegram)

    def test_principal_com_voo_clicou_ja_no_ledger_nao_marca(self):
        """A dona morreu depois de gravar a linha e antes de pousar."""
        self._ficha(dict(self.BOA, em_voo=self._voo("clicou",
                                                     desde=self.DESDE)))
        self._ledger(self._linha("2026-10-06T23:42:21"))   # o mesmo segundo
        self.assertEqual(0, self.m.main([]))
        self.assertNotIn(self.VOO, self._marcados())

    def test_linha_de_antes_do_voo_rascunho_ou_outro_destino_nao_contam(self):
        self._ficha(dict(self.BOA, em_voo=self._voo("clicou",
                                                     desde=self.DESDE)))
        self._ledger(self._linha("2026-10-06T23:42:20"),
                     self._linha("2026-10-06T23:43:00", publicado=False),
                     self._linha("2026-10-06T23:43:00", plataforma="tiktok"),
                     self._linha("2026-10-06T23:43:00", vid=self.OUTRO))
        self.assertEqual(0, self.m.main([]))
        self.assertIn(self.VOO, self._marcados())
        self.assertEqual([self.OUTRO], self.escolhidos)

    def test_ledger_ilegivel_marca_como_antes(self):
        self._ficha(b"")
        self._reserva(dict(self.BOA, em_voo=self._voo("clicou",
                                                       desde=self.DESDE)))
        self._ledger(quebra=True)
        self.assertEqual(0, self.m.main([]))
        self.assertIn(self.VOO, self._marcados())
        self.assertEqual([self.OUTRO], self.escolhidos)

    def test_principal_vazia_e_bak_em_escolhido_pousa(self):
        """O caso espelhado: a principal se perdeu (podia estar em
        `entregue`/`clicou`) e a `.bak` diz `escolhido`. Antes: nao pousava,
        e a rodada podia subir o mesmo video de novo."""
        self._ficha(b"")
        self._reserva(dict(self.BOA, em_voo=self._voo("escolhido",
                                                       desde=self.DESDE)))
        self._ledger()
        self.assertEqual(0, self.m.main([]))
        self.assertIn(self.VOO, self._marcados())
        self.assertEqual([self.OUTRO], self.escolhidos)
        self.assertTrue(any("ou depois" in t for t in self.telegram),
                        self.telegram)

    def test_a_gravacao_faz_fsync_e_guarda_a_anterior(self):
        from unittest import mock
        self.m._linha = lambda *_a, **_k: None
        with mock.patch.object(os, "fsync", wraps=os.fsync) as fsync:
            self.m._gravar_ficha({"n": 1})
            self.m._gravar_ficha({"n": 2})
        self.assertEqual(2, fsync.call_count)
        ler = lambda c: json.loads(c.read_text(encoding="utf-8"))  # noqa: E731
        self.assertEqual({"n": 2}, ler(self.m._arquivo_da_dona()))
        self.assertEqual({"n": 1}, ler(self.m._arquivo_da_reserva()))
        sobras = list(self.m._arquivo_da_dona().parent.glob("*.tmp"))
        self.assertEqual([], sobras)


class UploadQueFalaTests(unittest.TestCase):
    """O laco do upload do `youtube_web` ficava ate 15 min calado: com os
    20 min de pulso parado, a folga era ~4 min. Agora fala a cada 60 s."""

    def test_uma_linha_por_minuto(self):
        from builds.publicar import youtube_web as yw
        falas = []
        aviso = yw._AvisoDoUpload(falas.append, 1000.0)
        self.assertFalse(aviso.talvez(1030.0))
        self.assertTrue(aviso.talvez(1061.0))
        self.assertFalse(aviso.talvez(1100.0))
        self.assertTrue(aviso.talvez(1122.0))
        self.assertEqual(2, len(falas))
        self.assertIn("61 s de 900 s", falas[0])

    def test_o_laco_do_upload_chama_o_aviso(self):
        raiz = Path(__file__).resolve().parents[2]
        fonte = (raiz / "random_builds" / "builds" / "publicar"
                 / "youtube_web.py").read_text(encoding="utf-8")
        laco = fonte[fonte.index("limite = time.time() + ESPERA_UPLOAD_S"):]
        laco = laco[:laco.index("if pronto is None:")]
        self.assertIn("aviso_do_upload.talvez(time.time())", laco)

    def test_a_fala_do_upload_nao_e_etapa_do_voo(self):
        """A frase nova nao pode ser lida como "arquivo entregue"."""
        import io
        m = _postar()
        m._linha = lambda *_a, **_k: None
        self.addCleanup(m._DONA.clear)
        m._gravar_dona("rodada")
        saida = m._SaidaComPulso(io.StringIO())
        with m._em_voo("builds", "g1", "youtube"):
            saida.write("[youtube-web] o arquivo ainda sobe (61 s de 900 s)"
                        "...\n")
            self.assertEqual("escolhido", m._DONA["em_voo"]["etapa"])


class ReservaRespeitaAMargemTests(unittest.TestCase):
    """A reserva do TikTok sem `_cabe_antes_do_proximo` sobreviveu a mutacao
    do conferente (65dc781)."""

    def setUp(self):
        self.m = m = _postar()
        m._linha = lambda *_a, **_k: None
        m.esperar_a_rede = lambda **k: True
        for nome in ("avisar", "avisar_lote_nao_fechou"):
            setattr(m, nome, lambda *a, **k: None)
        m.estoque_do_lote = lambda *a, **k: {}
        m.linhas_do_estoque = lambda lote: []
        m.retidos_por_canal = lambda: {}
        m.recuperar_no_tiktok = lambda so_ver=False, canal="historias": {
            "fila": 0}
        m.recuperar_no_youtube = lambda **k: {"fila": 0}
        saiu = {"feito": True, "url": "u", "tiktok": "publicado no TikTok"}
        m._publicar_canal = lambda canal, funcao, **k: [dict(saiu,
                                                             canal=canal)]
        self.reserva = []
        m.publicar_da_reserva = lambda so_ver=False: (
            self.reserva.append(1) or {})
        from builds.publicar import tiktok
        _trocar(self, tiktok, "confirmado", lambda e: bool(e))

    def test_perto_do_horario_seguinte_a_reserva_fica(self):
        self.m._cabe_antes_do_proximo = (
            lambda passo="", **k: passo != "reserva do TikTok")
        self.m.main([])
        self.assertEqual([], self.reserva)

    def test_longe_do_horario_seguinte_a_reserva_roda(self):
        self.m._cabe_antes_do_proximo = lambda *a, **k: True
        self.m.main([])
        self.assertEqual([1], self.reserva)


if __name__ == "__main__":
    unittest.main()
