# -*- coding: utf-8 -*-
"""Contratos do controle pelo celular.

Este bot controla uma maquina com YouTube, TikTok, ChatGPT e PicassoIA
logados. Por isso os testes aqui sao menos sobre "funciona" e mais sobre
"nao faz o que nao devia":

1. LISTA BRANCA. Quem nao esta na lista nao executa NADA e nao descobre nada
   — nem a lista de comandos, que ja e informacao sobre a maquina.
2. TABELA FECHADA. Nao existe caminho de "texto do celular" para "comando do
   sistema". Um `/rodar rm -rf` tem que morrer como comando desconhecido.
3. NADA DERRUBA O BOT. Comando que explode, rede que cai e mensagem torta
   viram resposta, nao stack trace — um bot morto as 3 da manha e pior que
   um bot que erra.
4. ALERTA SO DO QUE E NOVO. Ligar o bot nao pode despejar o historico de
   erros do dia no celular.

Rode da raiz do repo:
    python -m unittest remoto.test_remoto -v
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from remoto import bot as bot_mod
from remoto import comandos, config, relatorios
from remoto.api import Telegram


def _serie():
    from contos.publicar import serie
    return serie


def _metricas():
    from builds.publicar import metricas
    return metricas


def _ts(minutos_atras: float = 0) -> str:
    return (datetime.now(timezone.utc)
            - timedelta(minutes=minutos_atras)).isoformat(timespec="seconds")


class TelegramFalso:
    """Guarda o que seria enviado, em vez de falar com a rede."""

    def __init__(self, novidades=None, nome="meubot"):
        self._novidades = list(novidades or [])
        self.enviadas = []
        self.arquivos = []
        self.nome = nome

    def eu(self):
        return {"username": self.nome}

    def novidades(self, desde=None, timeout=30):
        saida, self._novidades = self._novidades, []
        return saida

    def mensagem(self, chat_id, texto, markdown=False):
        self.enviadas.append((chat_id, texto))
        return {"ok": True}

    def arquivo(self, chat_id, caminho, legenda="", como_video=True):
        self.arquivos.append((chat_id, str(caminho), legenda))
        return {"ok": True}

    # atalhos de leitura para os testes
    def textos(self, chat=None):
        return [t for c, t in self.enviadas if chat is None or c == chat]


def _mensagem(texto, chat=42, update_id=1):
    return {"update_id": update_id,
            "message": {"chat": {"id": chat}, "text": texto}}


class BaseTemp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        config.ARQUIVO = str(self.pasta / "remoto.json")
        self.addCleanup(lambda: setattr(config, "ARQUIVO", None))
        # o diario tambem vai para a pasta temporaria
        self._arquivo_diario = comandos.atividade._arquivo
        comandos.atividade._arquivo = lambda: self.pasta / "atividade.jsonl"
        self.addCleanup(lambda: setattr(comandos.atividade, "_arquivo",
                                        self._arquivo_diario))
        # `_alertar` dispara a APURACAO, que abre uma sessao do Claude Code de
        # verdade. Rodar a suite nao pode gastar sessao nem tocar a maquina —
        # o disparo tem teste proprio (`ApuracaoTests`), com o subprocesso
        # dublado.
        self._apuracoes = []
        self._apurar_real = bot_mod.Bot._apurar
        bot_mod.Bot._apurar = lambda _s: self._apuracoes.append(1)
        self.addCleanup(lambda: setattr(bot_mod.Bot, "_apurar",
                                        self._apurar_real))
        # Mesma doutrina para os RELATORIOS periodicos: `uma_volta` os dispara,
        # e montar de verdade le os dois ledgers e consulta o Agendador do
        # Windows por PowerShell — dez chamadas, alguns minutos de suite. Pior:
        # eles mandariam mensagem no meio dos testes de ALERTA, que contam
        # exatamente quantas mensagens sairam. Quem os quer, liga (ver
        # `EnvioPeriodicoTests`).
        self._relatorios_real = bot_mod.Bot._relatorios
        bot_mod.Bot._relatorios = lambda _s: None
        self.addCleanup(lambda: setattr(bot_mod.Bot, "_relatorios",
                                        self._relatorios_real))


class ListaBrancaTests(BaseTemp):
    def test_desconhecido_nao_executa_nada(self):
        tg = TelegramFalso([_mensagem("/parar", chat=999)])
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        robo.uma_volta(timeout=0)
        self.assertEqual(["não autorizado."], tg.textos())

    def test_desconhecido_nao_recebe_a_lista_de_comandos(self):
        tg = TelegramFalso([_mensagem("/ajuda", chat=999)])
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        robo.uma_volta(timeout=0)
        junto = " ".join(tg.textos())
        self.assertNotIn("/publicar", junto)
        self.assertNotIn("/gerar", junto)

    def test_codigo_certo_autoriza_uma_vez_so(self):
        tg = TelegramFalso()
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        tg._novidades = [_mensagem(f"/parear {robo.codigo}", chat=7)]
        robo.uma_volta(timeout=0)
        self.assertTrue(config.autorizado(7))
        # um segundo desconhecido com o MESMO codigo nao entra
        tg._novidades = [_mensagem(f"/parear {robo.codigo}", chat=8, update_id=2)]
        robo.uma_volta(timeout=0)
        self.assertFalse(config.autorizado(8))

    def test_codigo_errado_nao_autoriza(self):
        tg = TelegramFalso([_mensagem("/parear 000000", chat=7)])
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        robo.codigo = "123456"
        robo.uma_volta(timeout=0)
        self.assertFalse(config.autorizado(7))

    def test_autorizado_executa(self):
        config.autorizar(42)
        tg = TelegramFalso([_mensagem("/vila")])
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        robo.uma_volta(timeout=0)
        self.assertTrue(tg.textos(), "não respondeu a quem tem permissão")

    def test_esquecer_revoga(self):
        config.autorizar(42)
        config.esquecer(42)
        self.assertFalse(config.autorizado(42))


class TabelaFechadaTests(BaseTemp):
    """Nao existe caminho de texto do celular para comando do sistema."""

    def test_comando_desconhecido_morre(self):
        for texto in ("/rodar rm -rf /", "/exec import os", "/shell dir",
                      "/eval 2+2", "/sh"):
            resposta, arquivo = comandos.executar(texto)
            self.assertIn("não conheço", resposta, texto)
            self.assertIsNone(arquivo)

    def test_texto_solto_nao_e_comando(self):
        resposta, _ = comandos.executar("apaga tudo por favor")
        self.assertIn("/ajuda", resposta)

    def test_a_tabela_nao_tem_nada_de_shell(self):
        proibidos = ("rodar", "exec", "shell", "sh", "cmd", "eval", "python")
        for nome in comandos.TABELA:
            self.assertNotIn(nome, proibidos, f"/{nome} não devia existir")

    def test_comando_que_explode_vira_resposta(self):
        def bomba(_args):
            raise RuntimeError("boom")

        comandos.TABELA["testebomba"] = bomba
        self.addCleanup(lambda: comandos.TABELA.pop("testebomba", None))
        resposta, _ = comandos.executar("/testebomba")
        self.assertIn("falhou", resposta)
        self.assertIn("boom", resposta)

    def test_publicar_exige_id_que_existe(self):
        self.assertIn("diga o id", comandos.publicar(""))
        self.assertIn("não achei", comandos.publicar("id_que_nao_existe_xyz"))

    def test_publicar_recusa_destino_invalido(self):
        original = comandos.procurar_video
        comandos.procurar_video = lambda _p: type(
            "V", (), {"id": "x", "titulo": "t"})()
        self.addCleanup(lambda: setattr(comandos, "procurar_video", original))
        self.assertIn("onde?", comandos.publicar("x instagram"))


class AlertaTests(BaseTemp):
    def test_so_avisa_o_que_e_novo(self):
        """Ligar o bot nao pode despejar o historico do dia no celular."""
        comandos.atividade.registrar("picasso", "erro", "erro velho")
        config.autorizar(42)
        tg = TelegramFalso()
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        robo.uma_volta(timeout=0)
        self.assertEqual([], tg.textos(), "avisou de erro anterior ao bot")

        comandos.atividade.registrar("digen", "erro", "quebrou agora")
        robo.uma_volta(timeout=0)
        self.assertTrue(any("quebrou agora" in t for t in tg.textos()))

    def test_nao_repete_o_mesmo_alerta(self):
        config.autorizar(42)
        tg = TelegramFalso()
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        comandos.atividade.registrar("digen", "erro", "quebrou")
        robo.uma_volta(timeout=0)
        antes = len(tg.textos())
        robo.uma_volta(timeout=0)
        self.assertEqual(antes, len(tg.textos()), "mandou o mesmo erro 2x")

    def test_sucesso_nao_vira_alerta(self):
        config.autorizar(42)
        tg = TelegramFalso()
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        comandos.atividade.registrar("estudio", "ok", "video pronto")
        robo.uma_volta(timeout=0)
        self.assertEqual([], tg.textos())

    def test_alerta_vai_para_todos_os_autorizados(self):
        config.autorizar(1)
        config.autorizar(2)
        tg = TelegramFalso()
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        comandos.atividade.registrar("arena", "erro", "caiu")
        robo.uma_volta(timeout=0)
        self.assertEqual({1, 2}, {c for c, _t in tg.enviadas})


class ResistenciaTests(BaseTemp):
    def test_mensagem_sem_texto_nao_quebra(self):
        config.autorizar(42)
        tg = TelegramFalso([{"update_id": 1,
                             "message": {"chat": {"id": 42}}}])
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        robo.uma_volta(timeout=0)          # nao pode levantar

    def test_rede_caida_devolve_vazio(self):
        def cair(*_a, **_k):
            raise OSError("sem rede")

        tg = Telegram("token-falso", abrir=cair)
        self.assertEqual([], tg.novidades())
        self.assertEqual({}, tg.chamar("getMe"))

    def test_arquivo_grande_demais_e_recusado_com_motivo(self):
        grande = self.pasta / "grande.mp4"
        grande.write_bytes(b"0" * 1024)
        from remoto import api
        limite = api.LIMITE_ARQUIVO_MB
        api.LIMITE_ARQUIVO_MB = 0.0001
        self.addCleanup(lambda: setattr(api, "LIMITE_ARQUIVO_MB", limite))
        resposta = Telegram("t").arquivo(1, grande)
        self.assertFalse(resposta["ok"])
        self.assertIn("limite", resposta["description"])

    def test_arquivo_que_nao_existe_nao_levanta(self):
        resposta = Telegram("t").arquivo(1, self.pasta / "fantasma.mp4")
        self.assertFalse(resposta["ok"])


class ConfigTests(BaseTemp):
    def test_token_do_ambiente_quando_nao_ha_arquivo(self):
        import os
        os.environ["TELEGRAM_BOT_TOKEN"] = "do-ambiente"
        self.addCleanup(lambda: os.environ.pop("TELEGRAM_BOT_TOKEN", None))
        self.assertEqual("do-ambiente", config.token())

    def test_arquivo_vence_o_ambiente(self):
        import os
        os.environ["TELEGRAM_BOT_TOKEN"] = "do-ambiente"
        self.addCleanup(lambda: os.environ.pop("TELEGRAM_BOT_TOKEN", None))
        config.salvar({**config.carregar(), "token": "do-arquivo"})
        self.assertEqual("do-arquivo", config.token())

    def test_config_torta_nao_derruba(self):
        Path(config.caminho()).write_text("{isto nao e json",
                                          encoding="utf-8")
        self.assertEqual([], config.carregar()["autorizados"])

    def test_o_token_nunca_aparece_na_ajuda(self):
        config.salvar({**config.carregar(), "token": "segredo123"})
        self.assertNotIn("segredo123", comandos.ajuda())


class RespostasTests(BaseTemp):
    def test_status_responde_sem_nada_rodando(self):
        self.assertIn("nada rodando", comandos.status())

    def test_vila_lista_as_sete_fabricas(self):
        linhas = comandos.vila().splitlines()
        self.assertEqual(len(comandos.atividade.FABRICAS), len(linhas))

    def test_erros_diz_quando_esta_limpo(self):
        self.assertIn("nenhum erro", comandos.erros())

    def test_erros_mostra_o_que_aconteceu(self):
        comandos.atividade.registrar("picasso", "erro", "cena bloqueada")
        self.assertIn("cena bloqueada", comandos.erros())

    def test_ajuda_lista_os_comandos_de_verdade(self):
        texto = comandos.ajuda()
        for nome in ("status", "vila", "erros", "publicar", "pausar"):
            self.assertIn(f"/{nome}", texto)


class AvisoAvulsoTests(BaseTemp):
    """`--avisar` manda uma mensagem e sai, sem ligar o bot (08/09/2026).

    Existe porque os alertas do bot so saem enquanto o processo dele esta no
    ar — e naquele dia ele NAO estava: token guardado, celular pareado,
    alertas ligados, e nada chegava. Uma tarefa agendada nao pode depender
    disso; ela roda sozinha, termina, e quer contar o que aconteceu.
    """

    def _telegram_falso(self, enviados, quebra=False):
        class _Falso:
            def __init__(self, _token):
                pass

            def mensagem(self, chat, texto, markdown=False):
                if quebra:
                    raise RuntimeError("rede fora")
                enviados.append((chat, texto))
                return {"ok": True}

        from remoto import api
        original = api.Telegram
        api.Telegram = _Falso
        self.addCleanup(setattr, api, "Telegram", original)

    def test_manda_para_todo_mundo_da_lista(self):
        from remoto.__main__ import avisar
        config.salvar({"token": "t", "autorizados": [1, 2], "alertas": True})
        enviados = []
        self._telegram_falso(enviados)
        self.assertTrue(avisar("pronto"))
        self.assertEqual([c for c, _t in enviados], [1, 2])

    def test_sem_ninguem_autorizado_nao_finge_que_avisou(self):
        from remoto.__main__ import avisar
        config.salvar({"token": "t", "autorizados": [], "alertas": True})
        self._telegram_falso([])
        self.assertFalse(avisar("pronto"))

    def test_telegram_fora_do_ar_nao_levanta(self):
        # Quem chama e uma tarefa agendada no fim de 4h de trabalho: o aviso
        # falhar nao pode virar excecao em cima da historia ja pronta.
        from remoto.__main__ import avisar
        config.salvar({"token": "t", "autorizados": [1], "alertas": True})
        self._telegram_falso([], quebra=True)
        self.assertFalse(avisar("pronto"))


class InstanciaUnicaTests(BaseTemp):
    """Dois bots no mesmo token brigam pelo `getUpdates`."""

    def test_o_segundo_bot_sai_sem_ligar(self):
        import contextlib
        from builds import travas
        from remoto import __main__ as principal

        ligou = []
        original_bot = principal.Bot
        principal.Bot = lambda *a, **k: type(
            "B", (), {"rodar": lambda _s: ligou.append(1)})()
        self.addCleanup(setattr, principal, "Bot", original_bot)

        original_trava = travas.trava

        @contextlib.contextmanager
        def _ocupada(nome, esperar=0.0):
            yield False

        travas.trava = _ocupada
        self.addCleanup(setattr, travas, "trava", original_trava)
        self.assertEqual(principal.ligar(), 0)
        self.assertEqual(ligou, [], "nao podia ter ligado um segundo bot")


class TarefaDoBotTests(unittest.TestCase):
    """A tarefa que mantem o bot no ar."""

    def test_bate_de_minuto_em_minuto_e_nao_no_logon(self):
        # `/SC ONLOGON` exige terminal de administrador (`Acesso negado`), e a
        # batida periodica ainda e mais forte: bot que cai as 3 da manha volta
        # sozinho as 3h10, em vez de esperar o proximo logon.
        from remoto import tarefa
        fonte = Path(tarefa.__file__).read_text(encoding="utf-8")
        self.assertIn('"MINUTE"', fonte)
        self.assertNotIn('"ONLOGON"', fonte)

    def test_o_lancador_entra_na_raiz_e_grava_a_saida(self):
        from remoto import tarefa
        texto = tarefa.escrever_lancador().read_text(encoding="utf-8")
        self.assertIn(f'cd /d "{tarefa.RAIZ}"', texto)
        self.assertIn("-m remoto", texto)
        self.assertIn("-X utf8", texto)
        self.assertIn("2>&1", texto)


class ApuracaoTests(BaseTemp):
    """Erro no ledger -> o Claude apura sozinho -> o diagnostico vai ao chat.

    Pedido dele em 08/09/2026: "os erros que acontecem na minha maquina vao
    para algum lugar que o Claude possa pegar" e "que ele proprio possa apurar
    todos os erros". O lugar ja existia (`atividade.jsonl`, de onde o bot tira
    os alertas); o que faltava era alguem LER aquilo — o alerta dizia "picasso
    falhou" e parava ai.
    """

    def test_alerta_novo_dispara_a_apuracao(self):
        config.autorizar(42)
        tg = TelegramFalso()
        robo = bot_mod.Bot(telegram=tg, log=lambda *_a: None)
        robo.uma_volta(timeout=0)          # limpa o historico anterior
        comandos.atividade.registrar("picasso", "erro", "quebrou agora")
        robo.uma_volta(timeout=0)
        self.assertTrue(self._apuracoes, "o erro novo nao disparou apuracao")

    def test_sem_erro_novo_nao_dispara(self):
        config.autorizar(42)
        robo = bot_mod.Bot(telegram=TelegramFalso(), log=lambda *_a: None)
        robo.uma_volta(timeout=0)
        self.assertEqual(self._apuracoes, [])

    def test_o_disparo_nao_segura_o_bot(self):
        """`Popen`, nao `run`: a apuracao pensa por dezenas de segundos.

        Se ela travasse o laco, o bot pararia de responder comando do celular
        justamente quando algo esta dando errado.
        """
        fonte = Path(bot_mod.__file__).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def _apurar("):]
        self.assertIn("subprocess.Popen", corpo)
        self.assertNotIn("subprocess.run", corpo.split("def ", 2)[0])

    def test_da_para_desligar_pelo_config(self):
        bot_mod.Bot._apurar = self._apurar_real
        chamou = []
        original = bot_mod.subprocess.Popen
        bot_mod.subprocess.Popen = lambda *a, **k: chamou.append(a)
        self.addCleanup(setattr, bot_mod.subprocess, "Popen", original)

        robo = bot_mod.Bot(telegram=TelegramFalso(), log=lambda *_a: None)
        robo.config = dict(robo.config, apurar=False)
        robo._apurar()
        self.assertEqual(chamou, [])

    @staticmethod
    def _corpo(nome: str) -> str:
        """So o corpo daquela funcao, ate a proxima de topo.

        Fatiar ate o fim do arquivo pegava o `consertar()` junto — e ele mexe
        no codigo de proposito, entao o teste do DIAGNOSTICO reprovava por
        causa da funcao vizinha.
        """
        from remoto import apurador
        fonte = Path(apurador.__file__).read_text(encoding="utf-8")
        inicio = fonte.index(f"def {nome}(")
        fim = fonte.find("\ndef ", inicio + 1)
        return fonte[inicio:fim if fim > 0 else len(fonte)]

    def test_o_DIAGNOSTICO_e_so_leitura(self):
        """Apurar e olhar. Quem mexe e o conserto, e ele tem outro contrato."""
        corpo = self._corpo("apurar")
        self.assertIn('"--allowedTools", "Read", "Grep", "Glob"', corpo)
        self.assertIn('"--permission-mode", "dontAsk"', corpo)
        for perigosa in ("Edit", "Write", "--dangerously-skip-permissions",
                         "bypassPermissions", "acceptEdits"):
            self.assertNotIn(perigosa, corpo, f"{perigosa} nao pode entrar")

    def test_o_CONSERTO_edita_mas_nao_roda_comando(self):
        """Ele pediu que mexesse no codigo. Bash e outra conversa.

        Editar arquivo, com a suite julgando depois, e reversivel. Rodar
        comando arbitrario e o que transforma um engano em estrago — e quem
        roda a suite e o `_testar()`, que o agente nao alcanca.
        """
        corpo = self._corpo("consertar")
        self.assertIn('"Edit", "Write"', corpo)
        for perigosa in ('"Bash"', "--dangerously-skip-permissions",
                         "bypassPermissions"):
            self.assertNotIn(perigosa, corpo, f"{perigosa} nao pode entrar")

    def test_conserto_reprovado_pela_suite_e_desfeito(self):
        """O unico juiz de um conserto que ninguem revisou sao os testes."""
        corpo = self._corpo("consertar")
        self.assertLess(corpo.index("passou, ultima = _testar()"),
                        corpo.index("restaurar(foto, alvos, depois)"))
        self.assertIn("if not passou:", corpo)

    def test_o_conserto_nao_alcanca_outputs_nem_git(self):
        from remoto import apurador
        for pasta in apurador.FONTES:
            self.assertNotIn("outputs", pasta)
            self.assertNotIn(".git", pasta)
        # e so texto de codigo: video e credencial nao entram
        self.assertEqual(set(apurador.EXTENSOES),
                         {".py", ".json", ".md", ".txt"})

    def test_desfazer_volta_o_conteudo_e_apaga_o_que_foi_criado(self):
        """`git checkout --` nao serve: a arvore tem trabalho nao commitado.

        Restaurar do HEAD apagaria o dele junto com o do agente.
        """
        from remoto import apurador
        antigo = self.pasta / "antigo.py"
        antigo.write_text("original", encoding="utf-8")
        foto = {str(antigo): b"original"}

        antigo.write_text("mexido pelo agente", encoding="utf-8")
        criado = self.pasta / "novo.py"
        criado.write_text("inventado", encoding="utf-8")

        apurador.restaurar(foto, [str(antigo), str(criado)])
        self.assertEqual(antigo.read_text(encoding="utf-8"), "original")
        self.assertFalse(criado.exists())

    def test_desfazer_nao_leva_o_que_outra_sessao_escreveu_depois(self):
        """14/09/2026, 6:53 e 11:49: a suite reprovou e a restauracao
        devolveu a foto de arquivos que OUTRA sessao editou durante a suite."""
        from remoto import apurador
        do_agente = self.pasta / "do_agente.py"
        de_outro = self.pasta / "de_outro.py"
        do_agente.write_text("original", encoding="utf-8")
        de_outro.write_text("original", encoding="utf-8")
        foto = {str(do_agente): b"original", str(de_outro): b"original"}

        do_agente.write_text("mexido pelo agente", encoding="utf-8")
        de_outro.write_text("mexido pelo agente", encoding="utf-8")
        depois = {str(do_agente): do_agente.read_bytes(),
                  str(de_outro): de_outro.read_bytes()}
        # durante a suite, outra sessao escreve por cima
        de_outro.write_text("trabalho de outra sessao", encoding="utf-8")

        apurador.restaurar(foto, [str(do_agente), str(de_outro)], depois)
        self.assertEqual(do_agente.read_text(encoding="utf-8"), "original")
        self.assertEqual(de_outro.read_text(encoding="utf-8"),
                         "trabalho de outra sessao")

    def test_conserto_espera_a_rodada_da_agenda_acabar(self):
        """14/09/2026: rodada longa importa modulo no meio do caminho, e codigo
        editado por baixo dela a derruba. Com a trava da agenda ocupada, so
        diagnostico."""
        from builds import travas
        from remoto import apurador
        from remoto import config as cfg_remoto
        chamadas = []
        for alvo, nome, valor in (
                (apurador, "pendentes",
                 lambda *a, **k: [{"ts": "x", "fabrica": "picasso"}]),
                (apurador, "apurar", lambda *a, **k: "diagnostico"),
                (apurador, "marcar", lambda *a, **k: None),
                (apurador, "consertar",
                 lambda *a, **k: chamadas.append(1) or {"mexeu": True}),
                (travas, "ocupada",
                 lambda nome: nome == apurador.TRAVA_DA_AGENDA),
                (cfg_remoto, "carregar", lambda *a, **k: {"consertar": True})):
            self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
            setattr(alvo, nome, valor)
        saida = apurador.uma_volta(log=lambda *_a: None)
        self.assertEqual([], chamadas)
        self.assertFalse(saida["conserto"]["mexeu"])
        self.assertEqual("historias__auto", apurador.TRAVA_DA_AGENDA)

    def test_o_remendo_mostra_so_o_que_o_agente_fez(self):
        from remoto import apurador
        alvo = apurador.RAIZ / "remoto" / "_alvo_de_teste.py"
        self.addCleanup(lambda: alvo.unlink(missing_ok=True))
        alvo.write_text("linha nova" + chr(10), encoding="utf-8")
        texto = apurador.remendo({}, [str(alvo)])
        self.assertIn("linha nova", texto)
        self.assertIn("_alvo_de_teste.py", texto)

    def test_erro_apurado_nao_volta(self):
        """Sem isso, cada volta reapuraria os mesmos erros para sempre."""
        from remoto import apurador
        original = apurador._estado_path
        apurador._estado_path = lambda: self.pasta / "apuracoes.json"
        self.addCleanup(setattr, apurador, "_estado_path", original)

        comandos.atividade.registrar("picasso", "erro", "quebrou")
        antes = apurador.pendentes()
        self.assertTrue(antes)
        apurador.marcar(antes)
        self.assertEqual(apurador.pendentes(), [])

    def test_teto_diario_segura_o_moinho(self):
        """Erro que nao para gastaria sessao ate o fim do mundo."""
        from remoto import apurador
        self.assertGreater(apurador.TETO_DIARIO, 0)
        self.assertLessEqual(apurador.TETO_DIARIO, 24)

    def test_o_conserto_e_proibido_de_largar_rascunho_na_raiz(self):
        """Em 09/09/2026 ele deixou tres, e um derrubou a propria suite.

        `run_test.py` mexia no `sys.path`, o que estourou a catraca de
        arquitetura (teto 2) — e a suite e justamente o juiz que decide se o
        conserto sobrevive. O rascunho reprovava o conserto.

        Este teste NAO escreve a chamada por extenso: a auditoria conta as
        ocorrencias no fonte inteiro, string inclusive, e o teste da regra
        viraria mais uma violacao dela.
        """
        from remoto import apurador
        prompt = apurador.prompt_de_conserto(
            [{"fabrica": "picasso", "detalhe": "quebrou"}], "diagnostico")
        baixo = prompt.lower()
        self.assertIn("nao crie arquivo novo na raiz", baixo)
        self.assertIn("sys.path", baixo)


# --------------------------------------------------------------- relatorios
class VencimentoTests(BaseTemp):
    """Quando cada relatorio periodico sai — pedido dele em 09/09/2026.

    A regra e "passou da hora e ainda nao foi hoje", nao "e exatamente a
    hora": o bot reinicia e a maquina dorme, e relatorio que so sai no minuto
    certo e relatorio que nao sai.
    """

    HORARIOS = {"metas": "21:00", "funcionamento": "09:00"}

    def _as(self, hora, minuto=0):
        return datetime(2026, 9, 9, hora, minuto)

    def test_antes_da_hora_nao_sai(self):
        self.assertEqual([], relatorios.devidos(
            self.HORARIOS, self._as(8, 59), ja_enviados={}))

    def test_na_hora_sai(self):
        self.assertEqual(["funcionamento"], relatorios.devidos(
            self.HORARIOS, self._as(9, 0), ja_enviados={}))

    def test_atrasado_ainda_sai(self):
        """Bot que so subiu as 23h ainda manda o das 21h."""
        vencidos = relatorios.devidos(self.HORARIOS, self._as(23, 30),
                                      ja_enviados={})
        self.assertEqual({"metas", "funcionamento"}, set(vencidos))

    def test_ja_enviado_hoje_nao_repete(self):
        self.assertEqual([], relatorios.devidos(
            self.HORARIOS, self._as(23, 0),
            ja_enviados={"metas": "2026-09-09",
                         "funcionamento": "2026-09-09"}))

    def test_enviado_ONTEM_sai_de_novo(self):
        self.assertEqual(["funcionamento"], relatorios.devidos(
            {"funcionamento": "09:00"}, self._as(9, 30),
            ja_enviados={"funcionamento": "2026-09-08"}))

    def test_hora_invalida_cala_o_relatorio_sem_quebrar(self):
        for ruim in ("", None, "banana", "99:99", "25:00"):
            self.assertEqual([], relatorios.devidos(
                {"metas": ruim}, self._as(23, 0), ja_enviados={}))

    def test_nome_desconhecido_e_ignorado(self):
        self.assertEqual([], relatorios.devidos(
            {"inventado": "01:00"}, self._as(23, 0), ja_enviados={}))

    def test_marcar_e_lido_de_volta(self):
        relatorios.marcar("metas", "2026-09-09")
        self.assertEqual({"metas": "2026-09-09"}, relatorios.enviados())

    def test_o_estado_mora_ao_lado_do_remoto_json(self):
        """Senao a suite marcaria 'ja mandei hoje' no arquivo DE VERDADE."""
        self.assertEqual(Path(config.caminho()).parent,
                         relatorios._estado_caminho().parent)


class EnvioPeriodicoTests(BaseTemp):
    def setUp(self):
        super().setUp()
        config.autorizar(42)
        config.autorizar(43)
        # A BaseTemp desliga os relatorios para todo mundo; esta classe e a
        # unica que os quer, entao devolve o metodo de verdade.
        bot_mod.Bot._relatorios = self._relatorios_real
        # Montar de verdade leria os dois ledgers e consultaria o Agendador
        # do Windows por PowerShell — lento, e nao e o que este teste mede.
        self._montar = relatorios.montar
        relatorios.montar = lambda nome, agora=None: f"corpo de {nome}"
        self.addCleanup(lambda: setattr(relatorios, "montar", self._montar))

    def _bot(self):
        return bot_mod.Bot(telegram=TelegramFalso(), log=lambda *_a: None)

    def test_vencido_vai_para_todos_os_autorizados(self):
        config.salvar({**config.carregar(),
                       "relatorios": {"metas": "00:00"}})
        bot = self._bot()
        bot._relatorios()
        self.assertEqual(["corpo de metas", "corpo de metas"],
                         bot.tg.textos())
        self.assertEqual({42, 43}, {c for c, _t in bot.tg.enviadas})

    def test_nao_manda_duas_vezes_no_mesmo_dia(self):
        config.salvar({**config.carregar(),
                       "relatorios": {"metas": "00:00"}})
        bot = self._bot()
        bot._relatorios()
        bot._relatorios()
        # Sao DOIS autorizados, entao um relatorio ja sao duas mensagens; o
        # que a segunda chamada nao pode e dobrar isso.
        self.assertEqual(2, len(bot.tg.enviadas))

    def test_sem_horario_configurado_nao_manda_nada(self):
        config.salvar({**config.carregar(), "relatorios": {}})
        bot = self._bot()
        bot._relatorios()
        self.assertEqual([], bot.tg.enviadas)

    def test_relatorio_que_explode_NAO_derruba_o_bot(self):
        config.salvar({**config.carregar(),
                       "relatorios": {"metas": "00:00"}})

        def explode(*_a, **_k):
            raise RuntimeError("o ledger sumiu")

        relatorios.montar = explode
        bot = self._bot()
        bot.uma_volta(timeout=0)          # nao pode levantar

    def test_a_volta_do_laco_chama_os_relatorios(self):
        config.salvar({**config.carregar(),
                       "relatorios": {"metas": "00:00"}})
        bot = self._bot()
        bot.uma_volta(timeout=0)
        self.assertIn("corpo de metas", bot.tg.textos())


class ConteudoDosRelatoriosTests(BaseTemp):
    """O texto responde a pergunta que ele foi criado para responder."""

    def setUp(self):
        super().setUp()
        self._ledgers = {}
        for modulo, nome in ((_serie(), "historias"), (_metricas(), "builds")):
            self._ledgers[nome] = modulo.REGISTRO
            modulo.REGISTRO = self.pasta / f"{nome}.jsonl"
        self.addCleanup(self._devolver)

    def _devolver(self):
        _serie().REGISTRO = self._ledgers["historias"]
        _metricas().REGISTRO = self._ledgers["builds"]

    def _publicar(self, modulo, nome, quando, video_id, visibilidade):
        import json
        alvo = self.pasta / f"{nome}.jsonl"
        with open(alvo, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"quando": quando, "video_id": video_id,
                                 "visibilidade": visibilidade,
                                 "titulo": "t"}) + "\n")

    def test_metas_diz_hora_e_canal_de_cada_video(self):
        self._publicar(_serie(), "historias", "2026-09-09T17:12:45",
                       "historia_00003:celular:p02", "public")
        self._publicar(_metricas(), "builds", "2026-09-09T17:13:26",
                       "generation_00007:build:celular", "public")
        texto = relatorios.metas(datetime(2026, 9, 9, 21, 0))
        self.assertIn("17:12", texto)
        self.assertIn("17:13", texto)
        self.assertIn("histórias", texto)
        self.assertIn("builds", texto)
        # O placar e por HORARIO (a grade tem oito), nao por canal: dizer "os
        # dois canais publicaram" com um post de oito daria por batida uma
        # meta que faltou 7/8.
        self.assertIn(f"1/{relatorios.META_DIARIA_POR_CANAL} horários", texto)

    def test_metas_acusa_canal_que_ficou_sem_postar(self):
        self._publicar(_serie(), "historias", "2026-09-09T17:12:45",
                       "historia_00003:celular:p02", "public")
        texto = relatorios.metas(datetime(2026, 9, 9, 21, 0))
        self.assertIn(f"builds: 0/{relatorios.META_DIARIA_POR_CANAL}", texto)

    def test_a_meta_e_a_grade_inteira_e_nao_um_por_dia(self):
        """Correcao dele em 09/09: 'quero um video em todos esses horarios'."""
        self.assertEqual(10, relatorios.META_DIARIA_POR_CANAL)
        self.assertEqual((0, 6, 9, 12, 15, 17, 20, 21, 22, 23),
                         relatorios.HORARIOS_DA_GRADE)

    def test_metas_acusa_video_que_NAO_esta_publico(self):
        """Meta batida com video privado e meta furada."""
        self._publicar(_serie(), "historias", "2026-09-09T17:12:45",
                       "historia_00010:celular:p01", "private")
        texto = relatorios.metas(datetime(2026, 9, 9, 21, 0))
        self.assertIn("NÃO público", texto)
        self.assertIn("historia_00010:celular:p01", texto)

    def test_metas_nao_inventa_publico_para_linha_antiga(self):
        """`visibilidade: null` e "nao sei", nunca "public"."""
        self._publicar(_serie(), "historias", "2026-09-09T17:12:45",
                       "historia_00003:celular:p01", None)
        texto = relatorios.metas(datetime(2026, 9, 9, 21, 0))
        self.assertNotIn("NÃO público", texto)
        self.assertIn("?", texto)

    def test_funcionamento_mede_a_duracao_pelo_par_inicio_fim(self):
        comandos.atividade.registrar("estudio", "inicio", "parte 1")
        comandos.atividade.registrar("estudio", "ok", "1 video")
        texto = relatorios.funcionamento()
        self.assertIn("Estúdio", texto)

    def test_o_fim_vem_antes_do_comeco_no_mesmo_segundo(self):
        """O Estudio abre a proxima parte no segundo em que fecha a anterior.

        Ordenando so por `ts`, o `inicio` podia sobrescrever o comeco aberto e
        casar com o `ok` do mesmo segundo — medindo ZERO onde havia 7 min.
        """
        base = datetime(2026, 9, 9, 12, 25, 0, tzinfo=timezone.utc)
        fim = datetime(2026, 9, 9, 12, 32, 26, tzinfo=timezone.utc)
        eventos = [
            {"ts": fim.isoformat(timespec="seconds"), "fabrica": "estudio",
             "pid": 1, "status": "inicio"},
            {"ts": fim.isoformat(timespec="seconds"), "fabrica": "estudio",
             "pid": 1, "status": "ok"},
            {"ts": base.isoformat(timespec="seconds"), "fabrica": "estudio",
             "pid": 1, "status": "inicio"},
        ]
        medidas = relatorios._duracoes(eventos)
        self.assertEqual([446.0], medidas["estudio"])

    def test_a_hora_do_erro_sai_no_fuso_da_casa(self):
        """O diario grava UTC e os ledgers gravam local: misturar mente."""
        marca = datetime(2026, 9, 9, 20, 11, 0, tzinfo=timezone.utc)
        esperado = marca.astimezone().strftime("%H:%M")
        self.assertEqual(esperado,
                         relatorios._hora_local(marca.isoformat()))

    def test_hora_torta_nao_quebra_o_relatorio(self):
        self.assertEqual("--:--", relatorios._hora_local("nao e data"))

    def test_montar_nunca_levanta(self):
        def explode(_agora=None):
            raise RuntimeError("sem ledger")
        original = relatorios.RELATORIOS["metas"]
        relatorios.RELATORIOS["metas"] = explode
        self.addCleanup(lambda: relatorios.RELATORIOS.__setitem__(
            "metas", original))
        self.assertIn("falhou", relatorios.montar("metas"))

    def test_relatorio_desconhecido_responde_sem_quebrar(self):
        self.assertIn("não conheço", relatorios.montar("inventado"))


class ComandosDeRelatorioTests(BaseTemp):
    def test_os_dois_estao_na_tabela(self):
        for nome in ("metas", "funcionamento"):
            self.assertIn(nome, comandos.TABELA)

    def test_a_ajuda_menciona_os_dois(self):
        texto = comandos.ajuda()
        self.assertIn("/metas", texto)
        self.assertIn("/funcionamento", texto)


if __name__ == "__main__":
    unittest.main()
