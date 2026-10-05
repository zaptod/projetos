# -*- coding: utf-8 -*-
"""Varredura de 05/10/2026 (itens 8, 9 e 10), com dublês: nenhum teste abre
navegador, toca o Telegram ou o `%LOCALAPPDATA%` real (`NF_IAS_PASTA`).

8.  A mesma imagem entregue DUAS vezes: desde 02/10, 36 de 173 do PicassoIA,
    12 de 178 do Gemini e 6 de 166 do ChatGPT (o worker das historias e o
    carteiro de servico pegavam o mesmo pedido); 5 respondidas viraram falha.
9.  A recuperacao depois de "Chrome fechou no download" nunca funcionou (25 de
    25): uma leitura so, retorno de `abrir_casa` ignorado, falha fora do diario.
10. A casa recriada a cada pedido: URL gravada antes do turno (a raiz do
    site), casa aberta em pedido de imagem, resumo de recusa injetado.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path

from ias import carteiro as carteiro_mod, correio, imagem


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._antes = os.environ.get("NF_IAS_PASTA")
        os.environ["NF_IAS_PASTA"] = str(Path(self._tmp.name) / "ias")
        self._vivo_original = correio._pid_vivo

    def tearDown(self):
        correio._pid_vivo = self._vivo_original
        if self._antes is None:
            os.environ.pop("NF_IAS_PASTA", None)
        else:
            os.environ["NF_IAS_PASTA"] = self._antes
        self._tmp.cleanup()


@contextmanager
def _trava_livre(nome, esperar=0.0):
    yield True


class _TravaDuble:
    """A trava da conta entre DOIS carteiros (processos diferentes no mundo
    real): por nome, NAO reentrante, com espera."""

    def __init__(self):
        self._travas: dict = {}
        self._guarda = threading.Lock()

    @contextmanager
    def __call__(self, nome, esperar=0.0):
        with self._guarda:
            trava = self._travas.setdefault(nome, threading.Lock())
        pego = trava.acquire(timeout=max(0.01, float(esperar)))
        try:
            yield pego
        finally:
            if pego:
                trava.release()


def _novo(fabrica=None, fabrica_imagem=None, **kw):
    avisos, documentos, diario = [], [], []
    kw.setdefault("trava", _trava_livre)
    kw.setdefault("nome_da_trava", lambda ia: f"perfil__{ia}__teste")
    kw.setdefault("avisar", avisos.append)
    kw.setdefault("avisar_arquivo", lambda caminho, legenda: documentos.append(caminho))
    kw.setdefault("log", lambda m: None)
    kw.setdefault("dormir", lambda s: None)
    ajustes = {"janela_conversa_s": 0, "resumo_a_cada": 50, "espera_conta_max_s": 100,
               "rodizio_imagem": ["picasso", "gemini", "chatgpt"], "cota_pausa_h": 6}
    ajustes.update(kw.pop("ajustes", {}))
    c = carteiro_mod.Carteiro(
        fabrica_de_sessao=fabrica or carteiro_mod.fabrica_duble(),
        fabrica_imagem=fabrica_imagem or imagem.fabrica_imagem_duble(),
        ajustes=ajustes, **kw)
    c._diario = lambda ia, status, detalhe, ref: diario.append((ia, status, detalhe, ref))
    c.avisos, c.documentos, c.diario = avisos, documentos, diario
    return c


# ============================================================== item 8
class ReivindicarEReserva(_Base):
    def test_reivindicar_e_atomico_e_so_de_pendente(self):
        m = correio.pedir_imagem("picasso", "x", proporcao="1:1")
        primeira = correio.reivindicar("picasso", m["id"], pid=111)
        self.assertEqual(primeira["situacao"], "entregue")
        self.assertEqual(primeira["entregador"], 111)
        self.assertNotIn("dono", primeira)        # quem entrega nao vira quem pediu
        # o segundo carteiro chega tarde: nada
        self.assertIsNone(correio.reivindicar("picasso", m["id"], pid=222))
        # o dono retoma a dele (a recuperacao depois de o Chrome cair)
        self.assertIsNotNone(correio.reivindicar("picasso", m["id"], pid=111))
        correio.atualizar("picasso", m["id"], situacao="respondida", resposta="ok")
        self.assertIsNone(correio.reivindicar("picasso", m["id"], pid=111))

    def test_pedido_reservado_nasce_com_o_dono(self):
        m = correio.pedir_imagem("gemini", "x", proporcao="1:1", dono=4242)
        self.assertEqual(correio.uma("gemini", m["id"])["dono"], 4242)
        correio._pid_vivo = lambda pid: True
        self.assertTrue(correio.reservado_por_outro(correio.uma("gemini", m["id"])))
        self.assertEqual(correio.pendentes("gemini", so_livres=True), [])
        self.assertEqual(len(correio.pendentes("gemini")), 1)    # o app ainda ve
        # reserva velha demais nao vale (o Windows reusa PID)
        velho = time.time() + correio.RESERVA_MAX_S + 60
        self.assertFalse(correio.reservado_por_outro(correio.uma("gemini", m["id"]),
                                                     agora_s=velho))

    def test_carteiro_de_servico_nao_entrega_o_pedido_reservado(self):
        correio._pid_vivo = lambda pid: True
        fabrica_imagem = imagem.fabrica_imagem_duble()
        c = _novo(fabrica_imagem=fabrica_imagem)
        m = correio.pedir_imagem("picasso", "x", proporcao="1:1", dono=4242)
        self.assertIsNone(c.uma_volta())
        self.assertEqual(fabrica_imagem.criadas, [])
        self.assertEqual(correio.uma("picasso", m["id"])["situacao"], "pendente")

    def test_quem_reservou_entrega_o_proprio(self):
        fabrica_imagem = imagem.fabrica_imagem_duble()
        c = _novo(fabrica_imagem=fabrica_imagem)
        m = correio.pedir_imagem("picasso", "x", proporcao="1:1", dono=os.getpid())
        fim = c.entregar(m)
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(len(fabrica_imagem.criadas), 1)

    def test_pedido_de_processo_morto_vira_falha_sem_gerar(self):
        correio._pid_vivo = lambda pid: False
        fabrica_imagem = imagem.fabrica_imagem_duble()
        c = _novo(fabrica_imagem=fabrica_imagem)
        m = correio.pedir_imagem("picasso", "x", proporcao="1:1", dono=4242)
        self.assertIsNone(c.uma_volta())
        fim = correio.uma("picasso", m["id"])
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "abandonado")
        self.assertEqual(fabrica_imagem.criadas, [])
        self.assertEqual(c.avisos + c.documentos, [])              # sem Telegram


class DoisCarteiros(_Base):
    """O worker (Carteiro sincrono) e o servico (pid 784) com o MESMO pedido."""

    def _sha(self, gerador, mid):
        return correio.uma(gerador, mid)["imagem"]["sha256"]

    def test_copia_velha_depois_da_entrega_nao_gera_de_novo(self):
        trava = _TravaDuble()
        img_a = imagem.fabrica_imagem_duble(corpo=imagem.png_de_teste(64, 64, (10, 200, 10)))
        img_b = imagem.fabrica_imagem_duble(corpo=imagem.png_de_teste(64, 64, (200, 10, 10)))
        a = _novo(fabrica_imagem=img_a, trava=trava)
        b = _novo(fabrica_imagem=img_b, trava=trava)
        m = correio.pedir_imagem("picasso", "x", proporcao="1:1")
        copia_do_b = correio.proxima_pendente(correio.CAIXAS, so_livres=True)
        self.assertEqual(a.entregar(m)["situacao"], "respondida")
        sha = self._sha("picasso", m["id"])
        fim = b.entregar(copia_do_b)                     # a copia ainda diz "pendente"
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(img_b.criadas, [])              # nem abriu o navegador
        self.assertEqual(self._sha("picasso", m["id"]), sha)
        self.assertEqual(b.avisos + b.documentos, [])

    def test_ao_mesmo_tempo_so_um_gera(self):
        trava = _TravaDuble()
        img_a = imagem.fabrica_imagem_duble(demora_s=0.3, dormir=time.sleep)
        img_b = imagem.fabrica_imagem_duble(demora_s=0.3, dormir=time.sleep)
        a = _novo(fabrica_imagem=img_a, trava=trava)
        b = _novo(fabrica_imagem=img_b, trava=trava)
        m = correio.pedir_imagem("picasso", "x", proporcao="1:1")
        saidas = []
        fios = [threading.Thread(target=lambda c=c: saidas.append(c.entregar(dict(m))))
                for c in (a, b)]
        for fio in fios:
            fio.start()
        for fio in fios:
            fio.join(30)
        self.assertEqual(len(saidas), 2)
        geracoes = sum(len(s.pedidos) for s in img_a.criadas + img_b.criadas)
        self.assertEqual(geracoes, 1)
        self.assertEqual([s["situacao"] for s in saidas], ["respondida", "respondida"])
        estados = [linha for linha in correio.ler("picasso")]
        self.assertEqual(estados[0]["situacao"], "respondida")

    def test_rodizio_tambem_rele_depois_da_trava(self):
        trava = _TravaDuble()
        img_a, img_b = imagem.fabrica_imagem_duble(), imagem.fabrica_imagem_duble()
        a = _novo(fabrica_imagem=img_a, trava=trava, ajustes={"rodizio_imagem": ["picasso"]})
        b = _novo(fabrica_imagem=img_b, trava=trava, ajustes={"rodizio_imagem": ["picasso"]})
        m = correio.pedir_imagem("livre", "x", proporcao="1:1")
        self.assertEqual(a.entregar(dict(m))["situacao"], "respondida")
        self.assertEqual(b.entregar(dict(m))["situacao"], "respondida")
        self.assertEqual(img_b.criadas, [])

    def test_guardar_nunca_sobrescreve_imagem_provada(self):
        m = correio.pedir_imagem("picasso", "x", proporcao="1:1")
        prova = {"comprovada": True, "metodo": "duble"}
        primeiro = imagem.png_de_teste(64, 64, (1, 2, 3))
        salvo = imagem.guardar("picasso", m["id"], primeiro, prova)
        with self.assertRaises(imagem.JaGuardada) as ctx:
            imagem.guardar("picasso", m["id"], imagem.png_de_teste(64, 64, (9, 9, 9)), prova)
        self.assertEqual(ctx.exception.resumo["arquivo"], salvo["arquivo"])
        alvo = correio.pasta_imagens("picasso") / salvo["arquivo"]
        self.assertEqual(alvo.read_bytes(), primeiro)

    def test_falha_tardia_nao_desfaz_a_resposta(self):
        c = _novo()
        m = correio.pedir_imagem("picasso", "x", proporcao="1:1")
        correio.atualizar("picasso", m["id"], situacao="respondida", resposta="ok")
        fim = c._falhar("picasso", "picasso", m["id"], "estourou", "erro")
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(correio.uma("picasso", m["id"])["situacao"], "respondida")
        self.assertEqual(c.avisos, [])

    def test_janela_zero_nao_leva_a_fila_do_adrian(self):
        c = _novo(ajustes={"janela_conversa_s": 0})
        correio.enviar("gemini", "oi do Adrian")
        self.assertIsNone(c._esperar_proxima("gemini"))


# ======================================= conferencia de 05/10/2026 (14:25)
class ConferenciaDaReserva(_Base):
    """Defeito 1: o `reivindicar` gravava o PID de quem ENTREGA no campo da
    reserva (`dono`); a mensagem do Adrian que voltou a pendente (a rede
    caiu) com o carteiro religado virava "falhou/abandonado" sem Telegram."""

    def test_rede_caiu_e_carteiro_religado_nao_abandona_a_do_adrian(self):
        correio._pid_vivo = lambda pid: False if int(pid) == 999991 else None
        m = correio.enviar("gemini", "pergunta do Adrian")
        correio.reivindicar("gemini", m["id"], pid=999991)
        correio.atualizar("gemini", m["id"], situacao="pendente", rede_tentativas=1,
                          nota="a rede caiu")
        atual = correio.uma("gemini", m["id"])
        self.assertFalse(correio.abandonada(atual))
        self.assertFalse(correio.reservado_por_outro(atual))
        c = _novo()
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "respondida")
        self.assertNotEqual(correio.uma("gemini", m["id"]).get("categoria"), "abandonado")

    def test_reivindicar_nao_apaga_a_reserva_de_quem_pediu(self):
        correio._pid_vivo = lambda pid: True
        m = correio.pedir_imagem("picasso", "x", proporcao="1:1", dono=4242)
        self.assertIsNotNone(correio.reivindicar("picasso", m["id"], pid=4242))
        atual = correio.uma("picasso", m["id"])
        self.assertEqual((atual["dono"], atual["entregador"]), (4242, 4242))
        # voltou a pendente (rede): continua do worker, nao do servico
        correio.atualizar("picasso", m["id"], situacao="pendente")
        self.assertTrue(correio.reservado_por_outro(correio.uma("picasso", m["id"]), pid=1))

    def test_dono_sem_reservado_em_nao_e_reserva(self):
        # linhas gravadas pelo codigo de 05/10 14:00 (reivindicar punha `dono`)
        correio._pid_vivo = lambda pid: False
        m = correio.enviar("gemini", "pergunta")
        correio.atualizar("gemini", m["id"], dono=999991)
        atual = correio.uma("gemini", m["id"])
        self.assertFalse(correio.abandonada(atual))
        self.assertFalse(correio.reservado_por_outro(atual))
        self.assertEqual(len(correio.pendentes("gemini", so_livres=True)), 1)

    def test_pid_vivo_nunca_usa_os_kill_no_windows(self):
        import builtins
        import sys
        chamadas = []
        kill_original, import_original = os.kill, builtins.__import__

        def sem_atividade(nome, *a, **kw):
            if nome == "builds.atividade":
                raise ImportError("sem builds")
            return import_original(nome, *a, **kw)

        os.kill = lambda *a: chamadas.append(a)
        builtins.__import__ = sem_atividade
        try:
            vivo = self._vivo_original(os.getpid())
            morto = self._vivo_original(2 ** 31 - 3)
        finally:
            os.kill, builtins.__import__ = kill_original, import_original
        if sys.platform == "win32":
            self.assertEqual(chamadas, [])            # os.kill = TerminateProcess
            self.assertTrue(vivo)
            self.assertIsNot(morto, True)


class ConferenciaDaEspera(_Base):
    """Defeito 2: a espera pela conta nao relia a mensagem e o estouro a
    marcava "falhou" (com Telegram) mesmo ja respondida por outro processo."""

    def _trava_que_responde(self, caixa, mid, situacao="respondida"):
        @contextmanager
        def trava(nome, esperar=0.0):
            if correio.uma(caixa, mid)["situacao"] == "pendente":
                correio.atualizar(caixa, mid, situacao=situacao, resposta="ok do worker")
            yield False
        return trava

    def _relogio(self):
        t = [0.0]

        def relogio():
            t[0] += 50
            return t[0]
        return relogio

    def test_respondida_durante_a_espera_nao_vira_falha(self):
        m = correio.pedir_imagem("chatgpt", "x", proporcao="1:1", de="historias")
        c = _novo(trava=self._trava_que_responde("chatgpt", m["id"]),
                  relogio=self._relogio(), ajustes={"espera_conta_max_s": 100})
        fim = c.entregar(m)
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(correio.uma("chatgpt", m["id"])["situacao"], "respondida")
        self.assertEqual(c.avisos + c.documentos, [])

    def test_levada_por_outro_durante_a_espera_nao_vira_falha(self):
        # o outro processo ainda esta GERANDO (entregue): o estouro da espera
        # aqui nao pode marcar "falhou" por cima, e a espera acaba na hora
        m = correio.pedir_imagem("chatgpt", "x", proporcao="1:1", de="historias")
        tentativas = []
        base = self._trava_que_responde("chatgpt", m["id"], situacao="entregue")

        @contextmanager
        def trava(nome, esperar=0.0):
            tentativas.append(nome)
            with base(nome, esperar) as minha:
                yield minha
        c = _novo(trava=trava, relogio=self._relogio(), ajustes={"espera_conta_max_s": 1000})
        fim = c.entregar(m)
        self.assertEqual(fim["situacao"], "entregue")
        self.assertEqual(correio.uma("chatgpt", m["id"])["situacao"], "entregue")
        self.assertEqual(len(tentativas), 1)
        self.assertEqual(c.avisos + c.documentos, [])

    def test_rodizio_respondido_durante_a_espera_nao_vira_falha(self):
        m = correio.pedir_imagem("livre", "x", proporcao="1:1")
        c = _novo(trava=self._trava_que_responde("livre", m["id"]),
                  relogio=self._relogio(),
                  ajustes={"espera_conta_max_s": 100, "rodizio_imagem": ["picasso"]})
        fim = c.entregar(m)
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(c.avisos + c.documentos, [])

    def test_estouro_de_verdade_falha_pelo_diario(self):
        @contextmanager
        def ocupada(nome, esperar=0.0):
            yield False
        m = correio.pedir_imagem("chatgpt", "x", proporcao="1:1")
        c = _novo(trava=ocupada, relogio=self._relogio(),
                  ajustes={"espera_conta_max_s": 100})
        fim = c.entregar(m)
        self.assertEqual((fim["situacao"], fim["categoria"]), ("falhou", "conta_ocupada"))
        self.assertTrue(any("conta_ocupada" in d[2] for d in c.diario))

    def test_falha_do_turno_de_texto_vai_ao_diario(self):
        c = _novo(fabrica=carteiro_mod.fabrica_duble(falhar=RuntimeError("site fora")))
        m = correio.enviar("gemini", "pergunta")
        fim = c.entregar(m)
        self.assertEqual(fim["situacao"], "falhou")
        self.assertTrue(any(d[1] == "erro" for d in c.diario))

    def test_nenhuma_falha_direta_fora_do_falhar(self):
        # toda falha passa por `_falhar` (diario + nao desfaz respondida); so a
        # varredura de abandonadas marca direto (sem Telegram, de proposito)
        import inspect
        import re
        fonte = inspect.getsource(carteiro_mod.Carteiro)
        diretas = re.findall(r'def (\w+)\(|situacao="falhou"', fonte)
        donos, atual = [], None
        for m in re.finditer(r'def (\w+)\(|situacao="falhou"', fonte):
            if m.group(1):
                atual = m.group(1)
            else:
                donos.append(atual)
        self.assertTrue(diretas)
        self.assertEqual(sorted(set(donos)), ["_falhar", "_varrer_abandonadas"])


# ============================================================== item 9
class _ClienteRecuperando:
    """Um cliente falso da conversa reaberta: a imagem so fica pronta na
    leitura `pronta_na`."""

    provedor = "gemini"
    sel = {"imagem_gerada": ["single-image img"]}
    ajustes = {}
    modelo_atual = "Pro"

    def __init__(self, pronta_na: int | None):
        self.pronta_na = pronta_na
        self.leituras = 0
        self.esperas = []
        self.roladas = 0
        corpo = imagem.png_de_teste(300, 300)
        cliente = self

        class _Resp:
            ok, status = True, 200

            @staticmethod
            def body():
                return corpo

        class _Ctx:
            class request:                                      # noqa: N801
                @staticmethod
                def get(url, timeout=None):
                    return _Resp()

        class _Pagina:
            url = "https://gemini.google.com/app/abc123def"

            @staticmethod
            def evaluate(script, arg=None):
                if "scrollIntoView" in script:
                    cliente.roladas += 1
                return None

            @staticmethod
            def wait_for_timeout(ms):
                cliente.esperas.append(ms)

        self.ctx = _Ctx()
        self.page = _Pagina()
        self.corpo = corpo
        self.imagens_na_resposta = []
        self._srcs_antes_do_envio = None

    def imagens_da_resposta(self):
        self.leituras += 1
        pronta = self.pronta_na is not None and self.leituras >= self.pronta_na
        imagens = ([{"src": "https://lh3/gato", "w": 300, "h": 300, "pronta": True}]
                   if pronta else [])
        turno = imagem.pedido_de_imagem("um gato", "1:1")
        return {"ancorado": True, "turno": turno, "resposta": True, "gerando": False,
                "imagens": imagens, "fora": 0}

    @staticmethod
    def imagens_prontas(achado, antes=()):
        return [i for i in achado.get("imagens") or [] if i.get("pronta")]


class RecuperarDepoisDoChrome(_Base):
    def test_le_de_novo_com_rolagem_ate_a_imagem_aparecer(self):
        cli = _ClienteRecuperando(pronta_na=3)
        sessao = carteiro_mod.SessaoReal(cli, log=lambda *_a: None)
        saida = sessao.recuperar_imagem("um gato", "1:1")
        self.assertEqual(saida["bytes"], cli.corpo)
        self.assertEqual(cli.leituras, 4)                     # 3 esperando + a da prova
        self.assertEqual(cli.roladas, 3)                      # rolou antes de cada leitura
        self.assertEqual(cli.esperas, [3000, 3000])

    def test_desiste_no_prazo_dizendo_quantas_leituras(self):
        cli = _ClienteRecuperando(pronta_na=None)
        sessao = carteiro_mod.SessaoReal(cli, log=lambda *_a: None)
        with self.assertRaises(imagem.SemImagem) as ctx:
            sessao.recuperar_imagem("um gato", "1:1", prazo_s=60, passo_s=3)
        self.assertEqual(cli.leituras, 21)
        self.assertIn("21 leituras", str(ctx.exception))
        self.assertGreaterEqual(carteiro_mod.RECUPERAR_PRAZO_S, 45)

    def _sessao_que_cai(self, *, reabre: bool, url_da_imagem="https://gemini.google.com/app/abc123"):
        criadas, aberturas = [], []

        class _Sessao:
            def __init__(self, numero):
                self.numero = numero
                self.geradas = self.recuperadas = self.novos = 0

            def abrir_casa(self, url):
                aberturas.append((self.numero, url))
                return reabre

            def novo_chat(self):
                self.novos += 1

            def gerar_imagem(self, prompt, proporcao, mensagem_id):
                self.geradas += 1
                raise RuntimeError("Target page, context or browser has been closed")

            def recuperar_imagem(self, prompt, proporcao):
                self.recuperadas += 1
                return {"bytes": imagem.png_de_teste(),
                        "prova": {"comprovada": True, "metodo": "duble"}}

            def url(self):
                return url_da_imagem

        @contextmanager
        def fabrica(ia):
            sessao = _Sessao(len(criadas))
            criadas.append(sessao)
            yield sessao

        return fabrica, criadas, aberturas

    def test_conversa_que_nao_reabre_falha_com_motivo_e_vai_ao_diario(self):
        fabrica, criadas, aberturas = self._sessao_que_cai(reabre=False)
        c = _novo(fabrica=fabrica)
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "recuperacao")
        self.assertIn("não reabriu", fim["erro"])
        self.assertEqual([s.geradas for s in criadas], [1, 0])     # nao pediu outra
        self.assertEqual([s.recuperadas for s in criadas], [0, 0])  # nem leu a pagina errada
        self.assertEqual(aberturas, [(1, "https://gemini.google.com/app/abc123")])
        self.assertEqual([d[1] for d in c.diario], ["erro"])
        self.assertEqual(c.diario[0][3], m["id"])

    def test_recuperacao_nao_abre_a_casa_de_texto_antes(self):
        fabrica, criadas, aberturas = self._sessao_que_cai(reabre=True)
        correio.gravar_casa("gemini", {**correio.casa("gemini"),
                                       "url": "https://gemini.google.com/app/casa999"})
        c = _novo(fabrica=fabrica)
        correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
        self.assertEqual(c.uma_volta()["situacao"], "respondida")
        # so a conversa da IMAGEM foi aberta; a casa de texto nem foi tocada
        self.assertEqual(aberturas, [(1, "https://gemini.google.com/app/abc123")])

    def test_endereco_da_imagem_na_raiz_nao_e_guardado(self):
        fabrica, criadas, _ = self._sessao_que_cai(reabre=True,
                                                   url_da_imagem="https://gemini.google.com/app")
        c = _novo(fabrica=fabrica)
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["categoria"], "recuperacao")
        self.assertIsNone(correio.uma("gemini", m["id"]).get("chat_imagem_url"))

    def test_falha_de_imagem_vai_ao_diario(self):
        c = _novo(fabrica_imagem=imagem.fabrica_imagem_duble(
            falhar=imagem.SemImagem("nada voltou")))
        m = correio.pedir_imagem("picasso", "x", proporcao="1:1")
        self.assertEqual(c.uma_volta()["situacao"], "falhou")
        self.assertEqual([(d[1], d[3]) for d in c.diario], [("erro", m["id"])])

    def test_chrome_caiu_olha_a_excecao_embrulhada(self):
        try:
            try:
                raise RuntimeError("TargetClosedError: Target closed")
            except RuntimeError as dentro:
                raise imagem.ImagemFalhou("o download falhou") from dentro
        except imagem.ImagemFalhou as fora:
            self.assertTrue(carteiro_mod.chrome_caiu(fora))
        self.assertFalse(carteiro_mod.chrome_caiu(ValueError("outra coisa")))


class BaixarPeloBotaoComReserva(_Base):
    """`download.path()` caiu com o Chrome (TargetClosedError, 04-05/10)."""

    def _cliente(self, download, respostas=()):
        from contos.llm import seletores

        class _Alvo:
            first = None

            def scroll_into_view_if_needed(self, timeout=None):
                pass

            def evaluate(self, script):
                return True

            def hover(self, timeout=None, force=False):
                pass

            def click(self, timeout=None, force=False):
                for r in respostas:
                    pagina.ouvintes["response"](r)
                pagina.ouvintes["download"](download)

        alvo = _Alvo()
        alvo.first = alvo

        class _Pagina:
            url = "https://gemini.google.com/app/abc123"

            def __init__(self):
                self.ouvintes = {}

            def evaluate(self, script, arg=None):
                return {"imagem": True, "botao": True}

            def locator(self, seletor):
                return alvo

            def on(self, evento, funcao):
                self.ouvintes[evento] = funcao

            def remove_listener(self, evento, funcao):
                self.ouvintes.pop(evento, None)

            def wait_for_timeout(self, ms):
                pass

        pagina = _Pagina()

        class _Cli:
            provedor = "gemini"
            sel = seletores.GEMINI
            page = pagina
        return _Cli()

    def test_path_cai_e_o_save_as_salva(self):
        original = imagem.png_de_teste(120, 80)

        class _Download:
            suggested_filename = "Gemini_Generated_Image.png"

            @staticmethod
            def path():
                raise RuntimeError("TargetClosedError: Target page, context or browser "
                                   "has been closed")

            @staticmethod
            def save_as(destino):
                Path(destino).write_bytes(original)

        corpo = imagem.baixar_pelo_botao(self._cliente(_Download()), {"src": "x"},
                                         log=lambda *_a: None)
        self.assertEqual(corpo, original)

    def test_path_e_save_as_caem_vale_a_maior_resposta_de_imagem(self):
        grande = b"\xff\xd8\xff\xe0" + b"j" * 5000
        pequena = b"\xff\xd8\xff\xe0" + b"j" * 900

        class _Download:
            suggested_filename = "x.png"

            @staticmethod
            def path():
                raise RuntimeError("TargetClosedError")

            @staticmethod
            def save_as(destino):
                raise RuntimeError("TargetClosedError")

        class _Resposta:
            headers = {"content-type": "image/jpeg"}

            class request:                                      # noqa: N801
                resource_type = "fetch"

            def __init__(self, corpo):
                self._corpo = corpo

            def body(self):
                return self._corpo

        corpo = imagem.baixar_pelo_botao(
            self._cliente(_Download(), [_Resposta(pequena), _Resposta(grande)]),
            {"src": "x"}, log=lambda *_a: None)
        self.assertEqual(corpo, grande)

    def test_tudo_cai_e_o_motivo_guarda_o_nome_da_queda(self):
        class _Download:
            suggested_filename = "x.png"

            @staticmethod
            def path():
                raise RuntimeError("TargetClosedError: fechou")

            @staticmethod
            def save_as(destino):
                raise RuntimeError("TargetClosedError: fechou")

        with self.assertRaises(imagem.ImagemFalhou) as ctx:
            imagem.baixar_pelo_botao(self._cliente(_Download()), {"src": "x"},
                                     log=lambda *_a: None)
        self.assertTrue(carteiro_mod.chrome_caiu(ctx.exception))


# ============================================================== item 10
class CasaSoComConversa(_Base):
    def test_raiz_do_site(self):
        for url in ("", "https://gemini.google.com/app", "https://chatgpt.com/",
                    "https://chatgpt.com/?model=auto", "https://grok.com/",
                    "https://gemini.google.com/u/1/app", "https://duble.local/"):
            self.assertTrue(carteiro_mod.e_raiz(url), url)
        for url in ("https://gemini.google.com/app/3f2a9b1c0d", "https://chatgpt.com/c/68e1a",
                    "https://chat.deepseek.com/a/chat/s/cc2d815e-b38d",
                    "https://grok.com/c/41049bb0?rid=b76e", "https://duble.local/grok/c/1-17"):
            self.assertFalse(carteiro_mod.e_raiz(url), url)

    def test_url_da_casa_e_a_da_conversa_depois_do_turno(self):
        c = _novo()
        correio.enviar("gemini", "oi")
        self.assertEqual(c.uma_volta()["situacao"], "respondida")
        url = correio.casa("gemini")["url"]
        self.assertFalse(carteiro_mod.e_raiz(url))
        self.assertIn("/gemini/c/", url)

    def test_casa_nova_sem_turno_nao_grava_a_raiz(self):
        from contos.llm.cliente import LLMFalhou
        c = _novo(fabrica=carteiro_mod.fabrica_duble(falhar=LLMFalhou("travou")))
        correio.enviar("chatgpt", "oi")
        self.assertEqual(c.uma_volta()["situacao"], "falhou")
        self.assertIsNone(correio.casa("chatgpt")["url"])

    def test_raiz_guardada_nao_e_reaberta(self):
        fabrica = carteiro_mod.fabrica_duble()
        c = _novo(fabrica=fabrica)
        correio.gravar_casa("gemini", {**correio.casa("gemini"),
                                       "url": "https://gemini.google.com/app", "geracao": 71})
        correio.enviar("gemini", "oi")
        c.uma_volta()
        self.assertEqual(fabrica.criadas[0].casas_novas, 1)
        casa = correio.casa("gemini")
        self.assertEqual(casa["geracao"], 72)
        self.assertFalse(carteiro_mod.e_raiz(casa["url"]))

    def test_pedido_de_imagem_nao_abre_a_casa(self):
        fabrica = carteiro_mod.fabrica_duble()
        c = _novo(fabrica=fabrica)
        correio.gravar_resumo_da_casa("chatgpt", "combinamos: sprites da Vila com contorno "
                                                 "preto forte e fundo transparente")
        m = correio.pedir_imagem("chatgpt", "um gato", proporcao="1:1")
        self.assertEqual(c.uma_volta()["situacao"], "respondida")
        s = fabrica.criadas[0]
        self.assertEqual(s.casas_novas, 1)                       # so a conversa da imagem
        self.assertEqual([t.get("imagem") for t in s.turnos], ["1:1"])   # sem o "responda OK"
        self.assertEqual(correio.casa("chatgpt")["geracao"], 0)
        self.assertTrue(correio.arquivo_da_imagem("chatgpt", m["id"]).is_file())

    def test_prologo_tem_prazo_curto(self):
        fabrica = carteiro_mod.fabrica_duble()
        c = _novo(fabrica=fabrica)
        correio.gravar_resumo_da_casa("gemini", "combinamos: histórias curtas, em primeira "
                                                "pessoa, com gancho no fim de cada parte")
        correio.enviar("gemini", "e agora?")
        c.uma_volta()
        turnos = fabrica.criadas[0].turnos
        self.assertTrue(turnos[0]["texto"].startswith(carteiro_mod.PROLOGO_CASA_NOVA))
        self.assertEqual(turnos[0]["prazo_s"], carteiro_mod.PRAZO_PROLOGO_S)
        self.assertLessEqual(carteiro_mod.PRAZO_PROLOGO_S, 120)
        self.assertIsNone(turnos[1]["prazo_s"])                 # o pedido dele tem o prazo normal

    def test_resumo_de_recusa_guardado_nao_entra_na_casa_nova(self):
        fabrica = carteiro_mod.fabrica_duble()
        c = _novo(fabrica=fabrica)
        correio.gravar_resumo_da_casa("gemini", "Não fui programado para fazer essas coisas.")
        correio.enviar("gemini", "oi")
        c.uma_volta()
        self.assertEqual([t["texto"] for t in fabrica.criadas[0].turnos], ["oi"])
        self.assertNotIn("comecou_com_resumo", correio.casa("gemini"))

    def test_resumo_velho_nao_entra_na_casa_nova(self):
        fabrica = carteiro_mod.fabrica_duble()
        c = _novo(fabrica=fabrica)
        alvo = correio.gravar_resumo_da_casa(
            "gemini", "combinamos: histórias curtas, em primeira pessoa, com gancho no fim")
        velho = time.time() - carteiro_mod.RESUMO_VALIDADE_S - 3600
        os.utime(alvo, (velho, velho))
        correio.enviar("gemini", "oi")
        c.uma_volta()
        self.assertEqual([t["texto"] for t in fabrica.criadas[0].turnos], ["oi"])

    def test_resumo_de_recusa_nao_e_gravado(self):
        fabrica = carteiro_mod.fabrica_duble(
            responder=lambda t: ("Não fui programado para fazer essas coisas."
                                 if "resuma" in t else "OK"))
        c = _novo(fabrica=fabrica, ajustes={"resumo_a_cada": 2})
        for n in range(2):
            correio.enviar("gemini", f"m{n}")
            c.uma_volta()
        self.assertEqual(correio.resumo_da_casa("gemini"), "")
        casa = correio.casa("gemini")
        # a proxima tentativa so depois de mais `resumo_a_cada` (nao a cada turno)
        self.assertEqual(casa["resumo_mensagens"], 2)
        self.assertIsNone(casa["ultimo_resumo_em"])

    def test_sessao_real_passa_o_prazo_ao_cliente(self):
        recebidos = []

        class _Cli:
            provedor = "gemini"
            sel = {}

            class page:                                         # noqa: N801
                @staticmethod
                def evaluate(script):
                    return ""

            def perguntar(self, texto, timeout=None, anexos=None):
                recebidos.append(timeout)
                return "OK"

        sessao = carteiro_mod.SessaoReal(_Cli(), log=lambda *_a: None)
        sessao.perguntar("oi", prazo_s=90)
        sessao.perguntar("oi")
        self.assertEqual(recebidos, [90.0, None])


if __name__ == "__main__":
    unittest.main()
