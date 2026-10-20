# -*- coding: utf-8 -*-
"""A varredura de erros de 05/10/2026, lado da publicacao (`ferramentas/postar.py`).

Cada classe e um item do relatorio, com o numero medido:

- Item 2: `_linha` derrubava a contagem do estoque com o `sys.stdout` trocado
  por um objeto sem `.buffer` (`agenda._SaidaNoDiario`). `pendentes_por_canal`
  engolia o `AttributeError` e devolvia -1; o freio da agenda caia no plano B
  e contava as RETIDAS como estoque ("59-60 videos na fila, teto 20" contra 1
  parte limpa): tres madrugadas sem historia nova.
- Item 1: a parte CONSERTADA (o reparo refez as cenas depois do veto) saia
  com "o veto da IA venceu", o texto do mp4 ANTIGO. Medido na fila de 05/10,
  12:41: 57 partes, 1 limpa, 56 retidas — 37 delas consertadas. Ela continua
  retida (ninguem assistiu ao mp4 novo; o Adrian decidiu NAO ter nova olhada
  da IA, `historias/reolhar-depois-do-conserto`, opcao "nao", 05/10 12:32),
  mas passa na frente das outras retidas e nao diz mais "venceu".
- Conferente de 05/10: a retida que chega ao TikTok DEPOIS do YouTube (pela
  recuperacao ou pelo "levando so para o TikTok") nao ganhava a marca
  "[qualidade]" la nem a valvula no diario.
- Item 4: a retida que saiu so no YouTube ficava "a conferir" no TikTok
  tambem. Medido: 44 marcas `[qualidade]` no TikTok das historias, 2 de
  partes que NAO estavam la (h34 p06 e h42 p06): a recuperacao as descartava.
- Item 3: o 23:37 de 04/10 e o TikTok das 09:37 de 05/10 cairam por rede, sem
  segunda tentativa; `esperar_a_rede` so resolvia o NOME, e o TLS morria.
"""
from __future__ import annotations

import importlib.util
import io
import ssl
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_varredura_0510",
                                                  POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _video(h, p):
    return type("V", (), {"id": f"{h}:celular:p{p:02d}", "fonte_id": h,
                          "parte": p, "partes": 6, "caminho": "x.mp4",
                          "titulo": f"{h} parte {p}"})()


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


class _SaidaNoDiario:
    """Como a da agenda das historias: `write` e mais nada (sem `.buffer`)."""

    def __init__(self):
        self.linhas = []

    def write(self, texto):
        self.linhas.append(texto)

    def flush(self):
        pass


# ------------------------------------------------------------------ item 2
class LinhaSemBufferTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()

    def _com_saida(self, saida, funcao):
        original = sys.stdout
        sys.stdout = saida
        try:
            return funcao()
        finally:
            sys.stdout = original

    def test_saida_sem_buffer_recebe_a_linha_e_nao_levanta(self):
        saida = _SaidaNoDiario()
        self._com_saida(saida, lambda: self.m._linha("[postar] ola"))
        self.assertEqual(["[postar] ola\n"], saida.linhas)

    def test_saida_que_nao_codifica_nao_levanta(self):
        class Ascii(_SaidaNoDiario):
            encoding = "ascii"

            def write(self, texto):
                texto.encode("ascii")            # levanta com acento
                super().write(texto)
        saida = Ascii()
        self._com_saida(saida, lambda: self.m._linha("publicação → ok"))
        self.assertEqual(1, len(saida.linhas))

    def test_saida_que_explode_nao_derruba_quem_loga(self):
        class Quebrada:
            def write(self, _t):
                raise OSError("pipe fechado")
        self._com_saida(Quebrada(), lambda: self.m._linha("x"))

    def test_saida_normal_continua_pelo_buffer(self):
        bruto = io.BytesIO()
        saida = io.TextIOWrapper(bruto, encoding="utf-8")
        self._com_saida(saida, lambda: self.m._linha("ação"))
        self.assertEqual("ação\n".encode("utf-8"), bruto.getvalue())


class ContagemComSaidaDoDiarioTests(unittest.TestCase):
    """A contagem e a MESMA com o stdout da agenda e com o normal.

    Reproduz o caminho medido: a fila loga (`_sem_fonte_cheia` escreve uma
    linha quando uma historia ja saiu 2x no dia) no meio da contagem. Antes:
    -1 com o stdout trocado, 1 com o normal.
    """

    def setUp(self):
        self.m = _postar()
        limpa, retida = _video("historia_00044", 6), _video("historia_00042", 3)

        def fila():
            self.m._linha("[postar] historias: historia_00034 ja saiu 2x hoje")
            return [limpa, retida]
        self.m.fila_de_historias = fila
        self.m._retencao = lambda v: "retida" if v is retida else ""
        self.m._builds_prontos = lambda *a, **k: []

    def test_mesma_contagem_com_e_sem_buffer(self):
        normal = self.m.pendentes_por_canal()["historias"]
        original = sys.stdout
        sys.stdout = _SaidaNoDiario()
        try:
            trocado = self.m.pendentes_por_canal()["historias"]
        finally:
            sys.stdout = original
        self.assertEqual(1, normal)
        self.assertEqual(normal, trocado)

    def test_o_menos_um_deixa_rastro_no_diario(self):
        """Caso a contagem quebre de verdade: -1, mas com linha de ERRO."""
        from builds import atividade
        registros = []
        _trocar(self, atividade, "registrar",
                lambda *a, **k: registros.append((a, k)))

        def explode():
            raise RuntimeError("catalogo ilegivel")
        self.m.fila_de_historias = explode
        self.assertEqual(-1, self.m.pendentes_por_canal()["historias"])
        self.assertEqual(1, len(registros))
        self.assertEqual(atividade.ERRO, registros[0][0][1])
        self.assertIn("catalogo ilegivel", registros[0][0][2])

    def test_caso_zero_fila_vazia_e_zero_e_nao_menos_um(self):
        self.m.fila_de_historias = lambda: []
        self.assertEqual(0, self.m.pendentes_por_canal()["historias"])


# ------------------------------------------------------------------ item 1
class ConsertadaTests(unittest.TestCase):
    """A situacao vem de `parecer.estado_do_video` (um criterio so, la)."""

    def setUp(self):
        from contos.publicar import parecer, qualidade
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.estados = {}
        patcher = patch.object(
            parecer, "estado_do_video",
            lambda v: self.estados.get(getattr(v, "id", v), ""), create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        # O veto de um mp4 ANTIGO, com a passada gasta (o reparo que refez
        # as cenas gasta a passada): era "veto vencido" ate 05/10.
        self.veto_antigo = {"aprovado": False, "motivos": ["cena 3: mulher"],
                            "quando": "2026-10-03T03:00:00"}
        _trocar(self, parecer, "lembrado", lambda v: None)
        _trocar(self, parecer, "veto_por_id", lambda v: self.veto_antigo)
        _trocar(self, qualidade, "veto_vencido", lambda v: True)
        self.alvo = _video("historia_00044", 4)

    def test_consertada_e_retida_com_o_motivo_certo(self):
        self.estados[self.alvo.id] = "consertado"
        retencao = self.m._retencao(self.alvo)
        self.assertIn("refez as cenas", retencao)
        self.assertNotIn("passada de conserto ja foi gasta", retencao)

    def test_consertada_nao_e_veto_vencido_nem_veto_de_pe(self):
        self.estados[self.alvo.id] = "consertado"
        self.assertFalse(self.m._veto_vencido(self.alvo))
        self.assertEqual("", self.m._veto_lembrado(self.alvo),
                         "o veto e do mp4 antigo; o novo ninguem viu")

    def test_reprovada_sem_conserto_continua_como_era(self):
        self.estados[self.alvo.id] = "reprovado"
        self.assertTrue(self.m._veto_vencido(self.alvo))
        self.assertIn("passada de conserto ja foi gasta",
                      self.m._retencao(self.alvo))

    def test_re_render_sem_conserto_nao_apaga_o_veto(self):
        """15/09/2026: o veto e do VIDEO. Sem "refiz" depois do parecer, o
        mp4 novo nao e conserto (`estado_do_video` diz "reprovado")."""
        from contos.publicar import qualidade
        _trocar(self, qualidade, "veto_vencido", lambda v: False)
        self.estados[self.alvo.id] = "reprovado"
        self.assertIn("a IA REPROVOU", self.m._veto_lembrado(self.alvo))

    def test_sem_a_funcao_nova_vale_a_situacao_de_antes(self):
        """Se `parecer` nao tiver `estado_do_video`, a resposta e a de
        `situacao_do_video` — nada inventado aqui."""
        from contos.publicar import parecer
        _trocar(self, self.m, "_situacao_do_parecer",
                self.m._situacao_do_parecer)
        with patch.object(parecer, "estado_do_video", None, create=True), \
                patch.object(parecer, "situacao_do_video",
                             lambda v: "reprovado"):
            self.assertEqual("reprovado",
                             self.m._situacao_do_parecer(self.alvo))
            self.assertFalse(self.m._consertada(self.alvo))

    def test_caso_zero_sem_parecer_nenhum_nao_retem(self):
        self.assertEqual("", self.m._retencao(self.alvo))
        self.assertFalse(self.m._consertada(self.alvo))


class ConsertadaNaFrenteTests(unittest.TestCase):
    """No ultimo recurso, entre as retidas, a consertada sai primeiro."""

    def setUp(self):
        from builds import travas
        from contos.publicar import qualidade
        from contos.roteiro import roteiro as R
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.m._veto_lembrado = lambda alvo: ""
        self.m._parecer_da_ia = lambda *_a, **_k: ""
        self.consertadas = set()
        self.m._situacao_do_parecer = lambda alvo: (
            "consertado" if alvo.id in self.consertadas else "reprovado")
        self.m._veto_vencido = lambda alvo: alvo.id not in self.consertadas
        _trocar(self, qualidade, "vistoriar_parte",
                lambda h, p, caminho, r: {"ok": True, "erros": []})
        _trocar(self, R, "carregar", lambda _hid: {})
        _trocar(self, travas, "ocupada", lambda _nome: False)

    def test_consertada_atras_na_fila_passa_na_frente_da_vencida(self):
        fila = [_video("historia_00042", 3), _video("historia_00044", 4)]
        self.consertadas.add("historia_00044:celular:p04")
        self.m.fila_de_historias = lambda: fila
        alvo, _ = self.m.proxima_historia()
        self.assertEqual("historia_00044:celular:p04", alvo.id)

    def test_sem_consertada_a_ordem_da_fila_vale(self):
        fila = [_video("historia_00042", 3), _video("historia_00044", 4)]
        self.m.fila_de_historias = lambda: fila
        alvo, _ = self.m.proxima_historia()
        self.assertEqual("historia_00042:celular:p03", alvo.id)

    def test_a_parte_limpa_continua_na_frente_de_tudo(self):
        fila = [_video("historia_00044", 4), _video("historia_00050", 1)]
        self.consertadas.add("historia_00044:celular:p04")
        self.m._situacao_do_parecer = lambda alvo: (
            "consertado" if alvo.id in self.consertadas else "")
        self.m.fila_de_historias = lambda: fila
        alvo, _ = self.m.proxima_historia()
        self.assertEqual("historia_00050:celular:p01", alvo.id)


class ConsertadaNaPostagemTests(unittest.TestCase):
    """`postar_historia` de verdade: a consertada que sai nao diz "venceu"."""

    def setUp(self):
        from builds.publicar import desfecho, tiktok
        from contos.publicar import catalogo, serie
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.m.publicou_neste_horario = lambda *a, **k: None
        self.m._tiktok_neste_horario = lambda agora=None: True
        self.m.titulo_repetido = lambda *a, **k: False
        self.m._registrar_valvula = lambda ficha: None
        self.m._situacao_do_parecer = lambda alvo: "consertado"
        self.alvo = _video("historia_00044", 4)
        self.m.proxima_historia = lambda **k: (self.alvo, [])
        # Sem divida do YouTube: ela vem antes da fila e leria o ledger REAL.
        self.m._divida_do_youtube = lambda: (None, "", [])
        # A fila propria do TikTok (19/10/2026) tambem: leva a parte da rodada.
        self.m._vez_do_tiktok_historias = lambda novo=None: (self.alvo, "")
        self.marcas = []
        _trocar(self, desfecho, "marcar_para_conferir",
                lambda canal, vid, estado, plataforma="tiktok", **k:
                self.marcas.append(plataforma) or True)
        _trocar(self, serie, "registrar", lambda *a, **k: {})
        _trocar(self, tiktok, "confirmado",
                lambda estado: estado == "publicado no TikTok")
        _trocar(self, catalogo, "publicar_youtube",
                lambda *a, **k: "publicado no YouTube")
        self.m._tiktok_das_historias = (
            lambda alvo, falha=None: "publicado no TikTok")

    def test_sai_retida_consertada_e_sem_veto_vencido(self):
        ficha = self.m.postar_historia()
        self.assertTrue(ficha["feito"])
        self.assertTrue(ficha.get("consertada"))
        self.assertNotIn("veto_vencido", ficha)
        self.assertIn("refez as cenas", ficha["retido"])
        self.assertEqual(["youtube", "tiktok"], self.marcas)


# ------------------------------------------------------------------ item 4
class RetidaQueFalhouNoTikTokVoltaAtrasadaTests(unittest.TestCase):
    """O caminho inteiro: a retida sai so no YouTube, a marca vai so para o
    YouTube, e a fila de atrasados do TikTok a encontra."""

    def setUp(self):
        from builds.publicar import desfecho, tiktok
        from contos.publicar import catalogo, serie
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.m.publicou_neste_horario = lambda *a, **k: None
        self.m._tiktok_neste_horario = lambda agora=None: True
        self.m.titulo_repetido = lambda *a, **k: False
        self.m._registrar_valvula = lambda ficha: None
        self.m._retencao = lambda _a: "historia_00042:celular:p06: a IA reprovou"
        self.m._consertada = lambda _a: False
        self.m._veto_vencido = lambda _a: True
        self.m._veto_lembrado = lambda _a: ""
        self.alvo = _video("historia_00042", 6)
        self.m.proxima_historia = lambda **k: (self.alvo, [])
        # Sem divida do YouTube: ela vem antes da fila e leria o ledger REAL.
        self.m._divida_do_youtube = lambda: (None, "", [])
        self.marcas = {"youtube": set(), "tiktok": set()}
        _trocar(self, desfecho, "marcar_para_conferir",
                lambda canal, vid, estado, plataforma="tiktok", **k:
                self.marcas[plataforma].add(vid) or True)
        _trocar(self, serie, "registrar", lambda *a, **k: {})
        _trocar(self, tiktok, "confirmado",
                lambda estado: estado == "publicado no TikTok")
        _trocar(self, catalogo, "publicar_youtube",
                lambda *a, **k: "publicado no YouTube")
        self.m._tiktok_das_historias = lambda alvo, falha=None: ""

    def test_a_p06_que_falhou_no_tiktok_entra_nos_atrasados(self):
        self.m.postar_historia()
        self.assertEqual({self.alvo.id}, self.marcas["youtube"])
        self.assertEqual(set(), self.marcas["tiktok"])
        ledger = [{"video_id": f"historia_00042:celular:p{n:02d}",
                   "fonte_id": "historia_00042", "parte": n,
                   "plataforma": plataforma, "url": "http://x",
                   "titulo": f"historia_00042 parte {n}",
                   "quando": "2026-10-04T12:00:00"}
                  for n in range(1, 6) for plataforma in ("youtube", "tiktok")]
        ledger.append({"video_id": self.alvo.id, "fonte_id": "historia_00042",
                       "parte": 6, "plataforma": "youtube", "url": "http://x",
                       "titulo": self.alvo.titulo,
                       "quando": "2026-10-05T09:42:00"})
        self.m._fontes_de_atraso = lambda canal: (ledger,
                                                  {self.alvo.id: self.alvo})
        self.m.desistencias_do_tiktok = lambda canal="historias": set()
        self.m.a_conferir_no_tiktok = (
            lambda canal="historias", plataforma="tiktok":
            set(self.marcas["tiktok"]))
        self.m._fontes_cheias_hoje = lambda *a, **k: set()
        fila = [v.id for v in self.m.atrasados_no_tiktok(canal="historias")]
        self.assertEqual([self.alvo.id], fila)


class RetidaQueChegaDepoisAoTikTokTests(unittest.TestCase):
    """Conferente de 05/10: com a marca so onde a parte saiu, a retida chega
    ao TikTok DEPOIS — e os dois caminhos que a levam la nao marcavam nada.

    Medido por leitura: `_marcar_retido` era chamado em 2 lugares (rodada
    inteira e `--so-youtube`), nenhum deles a recuperacao ou o "levando so
    para o TikTok". A retida reprovada ia ao ar no TikTok fora da lista que
    uma pessoa confere, e a valvula nao ia ao diario.
    """

    def setUp(self):
        from builds.publicar import desfecho, tiktok
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        # Horario do TikTok vago, sem relogio nem ledger de producao.
        self.m._vaga_do_tiktok = lambda *a, **k: ""
        self.retencao = "historia_00042:celular:p06: a IA reprovou"
        self.m._retencao = lambda _a: self.retencao
        self.m._consertada = lambda _a: False
        self.m._veto_vencido = lambda _a: False
        self.m._veto_lembrado = lambda _a: ""
        self.alvo = _video("historia_00042", 6)
        self.marcas = []
        _trocar(self, desfecho, "marcar_para_conferir",
                lambda canal, vid, estado, plataforma="tiktok", **k:
                self.marcas.append((vid, plataforma, estado)) or True)
        _trocar(self, tiktok, "confirmado",
                lambda estado: estado == "publicado no TikTok")
        self.valvulas = []
        self.m._registrar_valvula = lambda ficha: self.valvulas.append(
            dict(ficha))
        self.tiktok = "publicado no TikTok"
        self.m._tiktok_das_historias = lambda alvo, falha=None: self.tiktok
        self.m._tiktok_dos_builds = lambda alvo, falha=None: self.tiktok
        self.m._esquecer_falhas_no_tiktok = lambda *a: None
        self.m._anotar_falha_no_tiktok = lambda *a: 1
        self.m.desfecho_do_tiktok = lambda estado, falha=None: (
            "publicado" if estado == "publicado no TikTok" else "falha")
        self.m.atrasados_no_tiktok = lambda canal="historias": [self.alvo]
        _trocar(self, self.m, "RECUPERACAO_LIGADA", True)

    # --- (a) a recuperacao do TikTok
    def test_recuperacao_marca_a_retida_no_tiktok_e_grava_a_valvula(self):
        resultado = self.m.recuperar_no_tiktok(canal="historias")
        self.assertTrue(resultado["feito"])
        self.assertEqual(self.retencao, resultado["retido"])
        self.assertEqual([(self.alvo.id, "tiktok",
                           self.m.PREFIXO_DA_RETENCAO + self.retencao)],
                         self.marcas)
        self.assertEqual(1, len(self.valvulas))
        self.assertEqual(self.retencao, self.valvulas[0]["retido"])
        self.assertTrue(self.valvulas[0]["feito"])

    def test_recuperacao_que_falhou_nao_marca(self):
        self.tiktok = ""
        resultado = self.m.recuperar_no_tiktok(canal="historias")
        self.assertFalse(resultado["feito"])
        self.assertEqual([], self.marcas)
        self.assertEqual([], self.valvulas)
        self.assertNotIn("retido", resultado)

    def test_caso_zero_parte_limpa_nao_marca_nada(self):
        self.retencao = ""
        resultado = self.m.recuperar_no_tiktok(canal="historias")
        self.assertTrue(resultado["feito"])
        self.assertEqual([], self.marcas)
        self.assertNotIn("retido", resultado)
        self.assertFalse(any(self.valvulas[0].get(m)
                             for m in self.m.VALVULAS),
                         "parte limpa nao abre valvula nenhuma")

    def test_recuperacao_de_builds_nao_passa_pela_valvula_das_historias(self):
        self.m._retencao = lambda _a: self.fail("builds nao tem retencao")
        resultado = self.m.recuperar_no_tiktok(canal="builds")
        self.assertTrue(resultado["feito"])
        self.assertEqual([], self.marcas)

    # --- (b) "YouTube ja saiu nesta hora; levando so para o TikTok"
    def _so_tiktok(self):
        self.m.publicou_neste_horario = lambda canal, plataforma: (
            {"video_id": self.alvo.id, "url": "https://youtu.be/x"}
            if plataforma == "youtube" else None)
        self.m._tiktok_neste_horario = lambda agora=None: True
        self.m._video_por_id = lambda vid: self.alvo
        self.m._anotar_falha_do_tiktok = lambda ficha, falha: None
        return self.m.postar_historia()

    def test_so_tiktok_marca_a_retida_no_tiktok(self):
        ficha = self._so_tiktok()
        self.assertTrue(ficha["so_tiktok"])
        self.assertEqual(self.retencao, ficha["retido"])
        self.assertEqual([(self.alvo.id, "tiktok",
                           self.m.PREFIXO_DA_RETENCAO + self.retencao)],
                         self.marcas)
        self.assertEqual(1, len(self.valvulas))

    def test_so_tiktok_que_nao_confirmou_nao_marca_nem_conta_valvula(self):
        self.tiktok = "cliquei em publicar, mas o TikTok nao confirmou"
        ficha = self._so_tiktok()
        self.assertNotIn("retido", ficha)
        self.assertEqual([], self.marcas)
        self.assertEqual([], self.valvulas,
                         "valvula so conta o que SAIU naquele destino")


# ------------------------------------------------------------------ item 3
class RedeDeVerdadeTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()

    def test_o_token_da_api_e_conferido_mas_nao_barra(self):
        """Sem a API o video sai igual (so sem capa e sem o id pelo canal):
        "nao sei" nunca barra video."""
        self.assertIn("oauth2.googleapis.com", self.m.ALVOS_AVISADOS)
        self.assertNotIn("oauth2.googleapis.com", self.m.ALVOS_DE_REDE)
        self.m._conexao_tls = lambda alvo, prazo=0: (
            "TLS falhou (SSLEOFError)" if "oauth2" in alvo else "")
        linhas = []
        self.assertTrue(self.m.esperar_a_rede(limite=0, log=linhas.append))
        self.assertTrue(any("oauth2" in l and "assim mesmo" in l
                            for l in linhas))

    def test_dns_ok_e_tls_morto_nao_e_rede_ok(self):
        """A madrugada de 05/10: o nome resolvia, o aperto de mao morria."""
        import socket

        def conecta(*_a, **_k):
            raise ssl.SSLEOFError(8, "EOF occurred in violation of protocol")
        with patch.object(socket, "getaddrinfo", lambda *a, **k: [()]), \
                patch.object(socket, "create_connection", conecta):
            motivo = self.m._conexao_tls("studio.youtube.com", 1)
        self.assertIn("TLS", motivo)
        self.assertIn("SSLEOFError", motivo)

    def test_esperar_a_rede_desiste_com_tls_morto(self):
        self.m._conexao_tls = lambda alvo, prazo=0: "TLS falhou (SSLEOFError)"
        linhas = []
        self.assertFalse(self.m.esperar_a_rede(limite=0, log=linhas.append))
        self.assertIn("TLS", linhas[-1])

    def test_esperar_a_rede_passa_com_tudo_ok(self):
        vistos = []
        self.m._conexao_tls = lambda alvo, prazo=0: vistos.append(alvo) or ""
        self.assertTrue(self.m.esperar_a_rede(limite=0, log=lambda _s: None))
        self.assertEqual(list(self.m.ALVOS_DE_REDE)
                         + list(self.m.ALVOS_AVISADOS), vistos)


class QueDestinoARedeDerrubouTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()
        # Horario do TikTok vago, sem relogio nem ledger de producao.
        self.m._vaga_do_tiktok = lambda *a, **k: ""
        from builds.publicar import tiktok
        _trocar(self, tiktok, "confirmado",
                lambda estado: str(estado).startswith("publicado no TikTok"))

    def test_caso_zero_ficha_vazia_ou_de_sucesso_nao_repoe(self):
        self.assertEqual([], self.m._derrubados_pela_rede({}))
        self.assertEqual([], self.m._derrubados_pela_rede(
            {"feito": True, "url": "u", "tiktok": "publicado no TikTok"}))

    def test_tiktok_que_nao_abriu_e_rede(self):
        r = {"feito": True, "url": "u", "tiktok": "",
             "tiktok_falha": "TikTokFalhou: infraestrutura: a pagina do "
                             "TikTok nao abriu (Timeout 90000ms)"}
        self.assertEqual(["tiktok"], self.m._derrubados_pela_rede(r))

    def test_rede_depois_do_clique_NAO_repoe(self):
        """O clique ja saiu: o post pode estar no ar, e repor duplicaria no
        perfil. A marca vem do `laudo["clicou"]`, que sobrevive a excecao."""
        r = {"feito": True, "url": "u", "tiktok": "", "tiktok_clicou": True,
             "tiktok_falha": "Error: net::ERR_CONNECTION_RESET"}
        self.assertEqual([], self.m._derrubados_pela_rede(r))

    def test_o_clique_chega_a_ficha(self):
        import tempfile
        from builds.publicar import desfecho, tiktok
        # Desde o PUB-1 (14/10/2026) o funil grava a marca "a conferir" do
        # clique: ela vai para uma lista TEMPORARIA, nunca para a real.
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        _trocar(self, desfecho, "arquivo_a_conferir",
                lambda canal, p="tiktok": Path(pasta.name) / f"{canal}_{p}.json")
        self.addCleanup(desfecho._SEM_MARCA.clear)
        self.m._mandar_no_telegram = lambda texto: None
        alvo = type("V", (), {"id": "g1:build:celular"})()
        self.m._build_ja_no_tiktok = lambda _vid: False
        self.m._linha = lambda *_a, **_k: None

        def publica(video, prova=None, **_k):
            prova["clicou"] = True
            raise RuntimeError("net::ERR_CONNECTION_RESET")
        _trocar(self, tiktok, "publicar", publica)
        falha: dict = {}
        ficha = {"tiktok": self.m._tiktok_dos_builds(alvo, falha)}
        self.m._anotar_falha_do_tiktok(ficha, falha)
        self.assertTrue(ficha["tiktok_clicou"])
        self.assertEqual([], self.m._derrubados_pela_rede(
            dict(ficha, feito=True, url="u")))

    def test_legenda_que_nao_entrou_nao_e_rede(self):
        r = {"feito": True, "url": "u", "tiktok": "",
             "tiktok_falha": "TikTokFalhou: a legenda não entrou"}
        self.assertEqual([], self.m._derrubados_pela_rede(r))

    def test_youtube_com_sslerror_e_rede(self):
        r = {"feito": False, "youtube_falhou": True,
             "motivo": "YouTube falhou: SSLError: EOF occurred", "tiktok": ""}
        self.assertEqual(["youtube"], self.m._derrubados_pela_rede(r))

    def test_login_e_cota_nao_sao_rede(self):
        for motivo in ("YouTube falhou: o Google pediu login",
                       "YouTube na cota: limite diário de envios"):
            with self.subTest(motivo=motivo):
                r = {"feito": False, "youtube_falhou": True, "motivo": motivo}
                self.assertEqual([], self.m._derrubados_pela_rede(r))

    def test_so_ver_e_repetido_nunca_repoem(self):
        self.assertEqual([], self.m._derrubados_pela_rede(
            {"veria": "x", "motivo": "infraestrutura"}))
        self.assertEqual([], self.m._derrubados_pela_rede(
            {"repetido": True, "motivo": "infraestrutura"}))


class ReporNoMesmoHorarioTests(unittest.TestCase):
    """`_publicar_canal`: a rede derrubou, espera, confere e tenta de novo."""

    def setUp(self):
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.m._dormir = lambda s: self.dormiu.append(s)
        self.m.esperar_a_rede = lambda **k: True
        self.m._ainda_no_horario = lambda comeco, slot, **k: True
        self.dormiu = []
        from builds.publicar import tiktok
        _trocar(self, tiktok, "confirmado",
                lambda estado: str(estado).startswith("publicado no TikTok"))

    def _canal(self, respostas):
        chamadas = []

        def funcao(so_ver=False):
            chamadas.append(so_ver)
            return respostas[min(len(chamadas), len(respostas)) - 1]
        return funcao, chamadas

    def test_tiktok_que_caiu_por_rede_vai_de_novo_com_o_mesmo_video(self):
        primeira = {"canal": "builds", "feito": True, "alvo": "g102",
                    "url": "u", "tiktok": "",
                    "tiktok_falha": "TikTokFalhou: infraestrutura: nao abriu"}
        segunda = {"canal": "builds", "feito": True, "alvo": "g102",
                   "so_tiktok": True, "tiktok": "publicado no TikTok"}
        funcao, chamadas = self._canal([primeira, segunda])
        fichas = self.m._publicar_canal("builds", funcao, so_ver=False,
                                        comeco=0.0, slot=9)
        self.assertEqual(2, len(chamadas))
        self.assertEqual(1, len(fichas))
        self.assertEqual("publicado no TikTok", fichas[0]["tiktok"])
        self.assertNotIn("tiktok_falha", fichas[0])
        self.assertTrue(fichas[0]["reposto"])
        self.assertEqual([self.m.PAUSA_ANTES_DE_REPOR_S], self.dormiu)

    def test_rede_que_nao_volta_desiste_no_teto(self):
        caiu = {"canal": "builds", "feito": True, "alvo": "g102", "url": "u",
                "tiktok": "", "tiktok_falha": "infraestrutura: nao abriu"}
        so_tk = dict(caiu, so_tiktok=True)
        funcao, chamadas = self._canal([caiu, so_tk])
        self.m._publicar_canal("builds", funcao, so_ver=False, comeco=0.0,
                               slot=9)
        self.assertEqual(1 + self.m.TENTATIVAS_POR_REDE, len(chamadas))

    def test_falha_que_nao_e_de_rede_nao_repoe(self):
        r = {"canal": "builds", "feito": True, "alvo": "g", "url": "u",
             "tiktok": "", "tiktok_falha": "TikTokFalhou: legenda"}
        funcao, chamadas = self._canal([r])
        self.m._publicar_canal("builds", funcao, so_ver=False, comeco=0.0,
                               slot=9)
        self.assertEqual(1, len(chamadas))
        self.assertEqual([], self.dormiu)

    def test_fora_do_horario_nao_repoe(self):
        self.m._ainda_no_horario = lambda comeco, slot, **k: False
        caiu = {"canal": "builds", "feito": False, "youtube_falhou": True,
                "motivo": "YouTube falhou: infraestrutura"}
        funcao, chamadas = self._canal([caiu])
        self.m._publicar_canal("builds", funcao, so_ver=False, comeco=0.0,
                               slot=9)
        self.assertEqual(1, len(chamadas))

    def test_so_vendo_nunca_repoe(self):
        caiu = {"canal": "builds", "feito": False, "youtube_falhou": True,
                "motivo": "infraestrutura"}
        funcao, chamadas = self._canal([caiu])
        self.m._publicar_canal("builds", funcao, so_ver=True, comeco=0.0,
                               slot=9)
        self.assertEqual([True], chamadas)

    def test_youtube_caiu_e_o_tiktok_tinha_ido_sai_outro_video(self):
        """A parte p foi ao TikTok e caiu no YouTube: a reposicao leva a
        proxima ao YouTube (a guarda do TikTok ja barra o segundo TikTok), e
        o relatorio mostra as duas."""
        primeira = {"canal": "historias", "feito": True, "alvo": "h:p03",
                    "youtube_falhou": True,
                    "motivo": "YouTube falhou: YouTubeWebFalhou: "
                              "infraestrutura: nao abriu",
                    "tiktok": "publicado no TikTok"}
        segunda = {"canal": "historias", "feito": True, "alvo": "h:p04",
                   "url": "publicado no YouTube", "tiktok": ""}
        funcao, chamadas = self._canal([primeira, segunda])
        fichas = self.m._publicar_canal("historias", funcao, so_ver=False,
                                        comeco=0.0, slot=9)
        self.assertEqual(["h:p03", "h:p04"], [f["alvo"] for f in fichas])
        self.assertEqual(2, len(chamadas), "repos uma vez e parou")

    def test_a_janela_e_o_mesmo_horario_da_grade(self):
        from datetime import datetime
        m = _postar()
        agora = datetime(2026, 10, 5, 9, 50)
        self.assertTrue(m._ainda_no_horario(0.0, 9, agora=agora,
                                            relogio=lambda: 60.0))
        # A reposicao comum continua com 25 min.
        self.assertTrue(m._ainda_no_horario(0.0, 9, agora=agora,
                                            relogio=lambda: 24 * 60.0))
        self.assertFalse(m._ainda_no_horario(0.0, 9, agora=agora,
                                             relogio=lambda: 25 * 60.0))
        # 06/10, 06:37: a volta final das 07:10 estava a 33 min do comeco
        # (a janela de 25 a barrava); a da volta e 40.
        volta = m.JANELA_DA_VOLTA_FINAL_MIN
        self.assertTrue(m._ainda_no_horario(0.0, 9, agora=agora,
                                            relogio=lambda: 33 * 60.0,
                                            janela_min=volta))
        self.assertFalse(m._ainda_no_horario(0.0, 9, agora=agora,
                                             relogio=lambda: 40 * 60.0,
                                             janela_min=volta))
        self.assertFalse(m._ainda_no_horario(0.0, 6, agora=agora,
                                             relogio=lambda: 60.0))


class VoltaFinalTests(unittest.TestCase):
    """`main` de verdade com `_publicar_canal` de verdade: a volta final.

    Medido em 06/10/2026, 06:37: a historia_00044 p06 (limpa) caiu 3x por
    rede das 06:37:04 as 07:05:50 (Studio em branco 160/107/151 s; TikTok sem
    abrir 6x e, na 3a, o envio sem chegar a 100%); os builds publicaram logo
    depois nos dois destinos (07:05:57-07:10:12) e o horario de historias
    ficou vazio. Agora historias volta UMA vez depois dos builds.
    """

    CAIU = {"canal": "historias", "feito": False,
            "alvo": "historia_00044:celular:p06", "youtube_falhou": True,
            "motivo": "YouTube falhou: YouTubeWebFalhou: infraestrutura: a "
                      "pagina de upload abriu e ficou em branco",
            "tiktok": "", "tiktok_falha": "TikTokFalhou: infraestrutura: a "
                                          "pagina do TikTok nao abriu"}
    # A 3a de 06/10: YouTube em branco de novo, TikTok com o botao preso
    # (nao e rede) — o YouTube continua derrubado pela rede.
    CAIU_3A = dict(CAIU, tiktok_falha="TikTokFalhou: o botao de publicar nao "
                                      "ficou clicavel em 2 min")
    SAIU = {"canal": "historias", "feito": True,
            "alvo": "historia_00044:celular:p06",
            "url": "publicado no YouTube", "tiktok": "publicado no TikTok"}
    BUILD_SAIU = {"canal": "builds", "feito": True,
                  "alvo": "generation_00095:estreia:celular",
                  "url": "publicado no YouTube",
                  "tiktok": "publicado no TikTok"}
    BUILD_CAIU = {"canal": "builds", "feito": False,
                  "alvo": "generation_00095:estreia:celular",
                  "youtube_falhou": True,
                  "motivo": "YouTube falhou: infraestrutura: nao abriu",
                  "tiktok": "", "tiktok_falha": "infraestrutura: nao abriu"}

    def setUp(self):
        self.m = _postar()
        m = self.m
        m._linha = lambda *_a, **_k: None
        m._dormir = lambda s: None
        m.esperar_a_rede = lambda **k: True
        m._ainda_no_horario = lambda comeco, slot, **k: True
        m.avisar = lambda r: None
        m.avisar_lote_nao_fechou = lambda *a, **k: None
        m.estoque_do_lote = lambda *a, **k: {}
        m.linhas_do_estoque = lambda lote: []
        m.retidos_por_canal = lambda: {}
        m.reserva_do_tiktok = lambda *a, **k: []
        m.recuperar_no_tiktok = lambda so_ver=False, canal="historias": {
            "fila": 0}
        m.recuperar_no_youtube = lambda **k: {"fila": 0}
        m.publicar_da_reserva = lambda so_ver=False: {}
        from builds.publicar import tiktok
        _trocar(self, tiktok, "confirmado",
                lambda estado: str(estado).startswith("publicado no TikTok"))
        self.ordem = []

    def _canal(self, nome, respostas):
        def funcao(so_ver=False):
            self.ordem.append(nome)
            vezes = self.ordem.count(nome)
            return dict(respostas[min(vezes, len(respostas)) - 1])
        return funcao

    def _rodada(self, historias, builds):
        self.m.postar_historia = self._canal("historias", historias)
        self.m.postar_build = self._canal("builds", builds)
        return self.m.main([])

    def test_historias_cai_3x_e_builds_publica_volta_uma_vez_depois(self):
        saida = self._rodada([self.CAIU, self.CAIU, self.CAIU_3A, self.SAIU],
                             [self.BUILD_SAIU])
        self.assertEqual(["historias"] * 3 + ["builds", "historias"],
                         self.ordem)
        self.assertEqual(0, saida)

    def test_caso_zero_os_dois_caem_nenhuma_volta(self):
        saida = self._rodada([self.CAIU], [self.BUILD_CAIU])
        self.assertEqual(["historias"] * 3 + ["builds"] * 3, self.ordem)
        self.assertEqual(1, saida, "tentou e nada saiu")

    def test_volta_que_cai_de_novo_nao_vira_laco(self):
        self._rodada([self.CAIU], [self.BUILD_SAIU])
        self.assertEqual(["historias"] * 3 + ["builds", "historias"],
                         self.ordem)

    def test_fora_da_janela_nao_volta(self):
        volta = self.m.JANELA_DA_VOLTA_FINAL_MIN
        self.m._ainda_no_horario = (
            lambda comeco, slot, janela_min=None, **k: janela_min != volta)
        self._rodada([self.CAIU], [self.BUILD_SAIU])
        self.assertEqual(["historias"] * 3 + ["builds"], self.ordem)

    def test_janela_que_fecha_DURANTE_a_espera_da_rede_nao_volta(self):
        """Conferida de novo depois de `esperar_a_rede`, logo antes de
        publicar: a espera (ate 120 s) pode empurrar para perto do horario
        seguinte."""
        volta = self.m.JANELA_DA_VOLTA_FINAL_MIN
        estado = {"esperou": False}

        def esperar(**k):
            # So a espera DA VOLTA (com `limite`) conta; a do comeco da
            # rodada (`esperar_a_rede()`) nao.
            if "limite" in k:
                estado["esperou"] = True
            return True
        self.m.esperar_a_rede = esperar
        self.m._ainda_no_horario = (
            lambda comeco, slot, janela_min=None, **k:
            not (janela_min == volta and estado["esperou"]))
        # Sem reposicoes: so a volta espera a rede.
        self.m.TENTATIVAS_POR_REDE = 0
        self._rodada([self.CAIU], [self.BUILD_SAIU])
        self.assertTrue(estado["esperou"], "a volta chegou a esperar a rede")
        self.assertEqual(["historias", "builds"], self.ordem)

    def test_o_caso_das_06_37_as_07_10_volta_pela_janela_de_40(self):
        """O relogio de verdade do caso medido: 07:10, 33 min de rodada.
        A reposicao comum (25 min) ja fechou; a volta (40) ainda cabe."""
        from datetime import datetime
        # O `_ainda_no_horario` de VERDADE (o `setUp` troca o deste modulo
        # por um que diz sempre sim).
        original = _postar()._ainda_no_horario
        self.m._ainda_no_horario = (
            lambda comeco, slot, janela_min=None, **k: original(
                0.0, 6, agora=datetime(2026, 10, 6, 7, 10),
                relogio=lambda: 33 * 60.0, janela_min=janela_min))
        self._rodada([self.CAIU, self.SAIU], [self.BUILD_SAIU])
        self.assertEqual(["historias", "builds", "historias"], self.ordem)

    def test_builds_com_tiktok_derrubado_pela_rede_nao_prova_nada(self):
        """`_publicou_sem_queda`: o YouTube dos builds saiu, o TikTok caiu
        por rede. Isso NAO e "a rede voltou", e historias nao volta."""
        meio = dict(self.BUILD_SAIU, tiktok="",
                    tiktok_falha="TikTokFalhou: infraestrutura: nao abriu")
        so_tk = dict(meio, so_tiktok=True)
        self._rodada([self.CAIU], [meio, so_tk])
        self.assertEqual(["historias"] * 3 + ["builds"] * 3, self.ordem)

    def test_reposicao_que_ja_levou_outro_video_nao_volta(self):
        """`len(fichas) == 1`: o YouTube da p03 caiu (o TikTok tinha ido) e a
        reposicao levou a p04 ao YouTube — o horario esta coberto, mesmo com
        a primeira ficha ainda "derrubada"."""
        p03 = {"canal": "historias", "feito": True, "alvo": "h:p03",
               "youtube_falhou": True,
               "motivo": "YouTube falhou: YouTubeWebFalhou: infraestrutura: "
                         "nao abriu",
               "tiktok": "publicado no TikTok"}
        p04 = {"canal": "historias", "feito": True, "alvo": "h:p04",
               "url": "publicado no YouTube", "tiktok": ""}
        self._rodada([p03, p04, self.SAIU], [self.BUILD_SAIU])
        self.assertEqual(["historias", "historias", "builds"], self.ordem)

    def test_historias_que_saiu_nao_volta(self):
        self._rodada([self.SAIU], [self.BUILD_SAIU])
        self.assertEqual(["historias", "builds"], self.ordem)

    def test_o_ultimo_canal_nunca_volta(self):
        self._rodada([self.SAIU], [self.BUILD_CAIU])
        self.assertEqual(["historias"] + ["builds"] * 3, self.ordem)

    def test_so_vendo_nunca_volta(self):
        fichas = self.m._volta_final(
            [("historias", self._canal("historias", [self.SAIU]),
              [dict(self.CAIU)]),
             ("builds", self._canal("builds", [self.BUILD_SAIU]),
              [dict(self.BUILD_SAIU)])],
            so_ver=True, comeco=0.0, slot=6)
        self.assertEqual([], self.ordem)
        self.assertEqual(2, len(fichas))

    def test_pedaco_no_ar_nunca_volta(self):
        meio = dict(self.CAIU, youtube_meio_no_ar=True)
        self.m._volta_final(
            [("historias", self._canal("historias", [self.SAIU]), [meio]),
             ("builds", None, [dict(self.BUILD_SAIU)])],
            so_ver=False, comeco=0.0, slot=6)
        self.assertEqual([], self.ordem)


class RecuperacaoNaoRepeteOTimeoutTests(unittest.TestCase):
    """`main` de verdade: TikTok caiu por rede, recuperacao e reserva esperam."""

    def setUp(self):
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.m.esperar_a_rede = lambda **k: True
        self.m.avisar = lambda r: None
        self.m.avisar_lote_nao_fechou = lambda *a, **k: None
        self.m.estoque_do_lote = lambda *a, **k: {}
        self.m.linhas_do_estoque = lambda lote: []
        self.m.retidos_por_canal = lambda: {}
        self.m.reserva_do_tiktok = lambda *a, **k: []
        self.chamou = []
        self.m.recuperar_no_tiktok = (
            lambda so_ver=False, canal="historias":
            self.chamou.append(("recuperar", canal)) or {"fila": 0})
        self.m.recuperar_no_youtube = lambda **k: {"fila": 0}
        self.m.publicar_da_reserva = (
            lambda so_ver=False: self.chamou.append(("reserva",)) or {})

    def _rodada(self, ficha_builds):
        self.m._publicar_canal = (
            lambda canal, funcao, **k: [dict(ficha_builds, canal=canal)])
        return self.m.main([])

    def test_tiktok_caido_por_rede_nao_chama_recuperacao_nem_reserva(self):
        from builds.publicar import tiktok
        _trocar(self, tiktok, "confirmado", lambda e: False)
        self._rodada({"feito": True, "url": "u", "tiktok": "",
                      "tiktok_falha": "infraestrutura: nao abriu"})
        self.assertEqual([], self.chamou)

    def test_rodada_sadia_chama_as_duas(self):
        from builds.publicar import tiktok
        _trocar(self, tiktok, "confirmado", lambda e: bool(e))
        # Longe do horario seguinte (a margem tem teste proprio, com relogio
        # fixo; aqui o relogio da maquina nao pode decidir).
        self.m._cabe_antes_do_proximo = lambda *a, **k: True
        self._rodada({"feito": True, "url": "u",
                      "tiktok": "publicado no TikTok"})
        self.assertIn(("recuperar", "historias"), self.chamou)
        self.assertIn(("recuperar", "builds"), self.chamou)
        self.assertIn(("reserva",), self.chamou)


if __name__ == "__main__":
    unittest.main()
