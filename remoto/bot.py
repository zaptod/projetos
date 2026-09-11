# -*- coding: utf-8 -*-
"""O laco do bot: recebe comando, responde, e AVISA quando algo quebra.

Duas metades:

  RESPONDER. Long polling no Telegram; cada mensagem vira um comando da
  tabela fechada de `comandos.py`. Quem nao esta na lista branca leva uma
  recusa curta — e so.

  AVISAR. O diario (`atividade.jsonl`) e lido a cada poucos segundos; todo
  evento novo de ERRO vira uma mensagem no celular, sem ninguem perguntar.
  E o motivo de existir: descobrir que o PicassoIA bloqueou uma cena as 3 da
  manha nao pode depender de voce abrir o painel.

O bot nunca abre porta na maquina: quem inicia a conexao e ele, para fora.
"""
from __future__ import annotations

import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from . import comandos, config
from .api import Telegram


def _codigo() -> str:
    return f"{random.randint(0, 999999):06d}"


class Bot:
    def __init__(self, *, telegram=None, log=print):
        self.log = log
        self.config = config.carregar()
        self.tg = telegram or Telegram(config.token())
        self.desde = None
        self.codigo = _codigo()
        self.pareado_agora = False
        # So alerta o que acontecer DAQUI para a frente: ligar o bot nao pode
        # despejar no celular o historico inteiro de erros do dia. Por isso o
        # que ja esta no diario entra como "visto" antes da primeira volta.
        #
        # A marca e a IDENTIDADE do evento, nao o horario: o carimbo do
        # diario tem precisao de SEGUNDO, e uma marca-d'agua temporal engolia
        # todo erro que caisse no mesmo segundo do anterior — justamente o
        # caso de uma falha em cascata, que e quando avisar mais importa.
        self.avisados = {self._marca(e) for e in self._erros_no_diario()}

    @staticmethod
    def _marca(evento: dict) -> tuple:
        return (str(evento.get("ts", "")), evento.get("fabrica"),
                evento.get("canal"), str(evento.get("detalhe", ""))[:120])

    @staticmethod
    def _erros_no_diario(quantos: int = 60) -> list:
        return [e for e in comandos.atividade.recentes(quantos)
                if e.get("status") == "erro"]

    # ------------------------------------------------------------ responder
    def _responder(self, chat_id, texto: str, arquivo=None):
        if arquivo is not None:
            resposta = self.tg.arquivo(chat_id, arquivo, legenda=texto)
            if not resposta.get("ok"):
                motivo = resposta.get("description", "?")
                self.tg.mensagem(chat_id, f"{texto}\n\n(não consegui mandar o "
                                          f"arquivo: {motivo})\n{arquivo}")
            return
        self.tg.mensagem(chat_id, texto, markdown=True)

    def _mensagem(self, mensagem: dict):
        chat = (mensagem.get("chat") or {}).get("id")
        texto = (mensagem.get("text") or "").strip()
        if chat is None or not texto:
            return
        if not config.autorizado(chat):
            self._parear(chat, texto)
            return
        resposta, arquivo = comandos.executar(texto)
        self._responder(chat, resposta, arquivo)

    def _parear(self, chat, texto: str):
        """A unica coisa que um desconhecido pode fazer: acertar o codigo."""
        if texto.lower().startswith("/parear"):
            enviado = texto.split(maxsplit=1)[-1].strip()
            if enviado == self.codigo and not self.pareado_agora:
                config.autorizar(chat)
                self.pareado_agora = True
                self.log(f"[remoto] chat {chat} autorizado.")
                self.tg.mensagem(
                    chat, "✅ pronto, agora eu falo com você.\n\n"
                          + comandos.ajuda(), markdown=True)
                return
        # Nada de "código errado" nem de lista de comandos: um desconhecido
        # nao precisa saber o que existe do outro lado.
        self.tg.mensagem(chat, "não autorizado.")

    # -------------------------------------------------------------- avisar
    def _alertar(self):
        if not self.config.get("alertas", True):
            return
        recentes = self._erros_no_diario()
        novos = [e for e in recentes if self._marca(e) not in self.avisados]
        if not novos:
            return
        # O conjunto so guarda o que ainda esta na janela do diario: sem isso
        # ele cresceria para sempre num processo que fica ligado dias.
        self.avisados = {self._marca(e) for e in recentes}
        for evento in reversed(novos[:5]):
            fabrica = comandos.atividade.FABRICAS.get(evento.get("fabrica"), {})
            texto = (f"❗ *{fabrica.get('rotulo', evento.get('fabrica'))}* "
                     f"({evento.get('canal', '?')})\n"
                     f"{(evento.get('detalhe') or '')[:400]}")
            for chat in config.carregar()["autorizados"]:
                self.tg.mensagem(chat, texto, markdown=True)
        self._apurar()

    def _apurar(self):
        """Solta o Claude em cima dos erros novos, sem segurar o bot.

        `Popen` e nao `run`: a apuracao le arquivos e pensa, o que leva
        dezenas de segundos, e o bot precisa continuar respondendo comando do
        celular enquanto isso. O resultado chega no chat por conta propria.

        Quem se protege de rodar duas vezes e o proprio apurador (trava de
        arquivo e teto diario) — aqui so se dispara.
        """
        if not self.config.get("apurar", True):
            return
        try:
            subprocess.Popen(
                [sys.executable, "-m", "remoto", "--apurar"],
                cwd=str(Path(__file__).resolve().parents[1]),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as exc:                               # noqa: BLE001
            self.log(f"[remoto] nao consegui apurar os erros: {exc}")

    def _relatorios(self):
        """Manda os relatorios periodicos que ja venceram.

        Vence por "passou da hora e ainda nao saiu hoje", nao por "e
        exatamente a hora": o bot reinicia e a maquina dorme, e um relatorio
        que so sai se alguem estiver no minuto certo e um relatorio que nao
        sai. Mesma licao do `StartWhenAvailable` das tarefas do Windows.

        Marca ANTES de mandar: se o Telegram estiver fora do ar, o relatorio
        daquele dia se perde — e isso e melhor do que a alternativa, que e
        tentar de novo a cada volta do laco e entupir o chat quando a rede
        voltar.
        """
        from . import relatorios

        horarios = config.carregar().get("relatorios") or {}
        vencidos = relatorios.devidos(horarios)
        if not vencidos:
            return
        hoje = datetime.now().strftime("%Y-%m-%d")
        for nome in vencidos:
            relatorios.marcar(nome, hoje)
            texto = relatorios.montar(nome)
            for chat in config.carregar()["autorizados"]:
                self.tg.mensagem(chat, texto, markdown=True)
            self.log(f"[remoto] relatorio de {nome} enviado.")

    def avisar_todos(self, texto: str):
        for chat in config.carregar()["autorizados"]:
            self.tg.mensagem(chat, texto)

    # ---------------------------------------------------------------- laco
    def uma_volta(self, timeout: int = 30) -> int:
        novidades = self.tg.novidades(self.desde, timeout=timeout)
        for atualizacao in novidades:
            self.desde = int(atualizacao.get("update_id", 0)) + 1
            mensagem = atualizacao.get("message") or {}
            try:
                self._mensagem(mensagem)
            except Exception as exc:      # uma mensagem ruim nao derruba o bot
                self.log(f"[remoto] erro tratando mensagem: {exc}")
        try:
            self._alertar()
        except Exception as exc:
            self.log(f"[remoto] erro nos alertas: {exc}")
        try:
            self._relatorios()
        except Exception as exc:   # relatorio quebrado nao derruba o bot
            self.log(f"[remoto] erro nos relatorios: {exc}")
        return len(novidades)

    def rodar(self):
        eu = self.tg.eu()
        nome = eu.get("username")
        if not nome:
            self.log("[remoto] o Telegram não respondeu ao getMe. O token "
                     "está certo? (arquivo remoto.json ou TELEGRAM_BOT_TOKEN)")
            return
        self.log(f"[remoto] bot @{nome} no ar.")
        if not config.carregar()["autorizados"]:
            self.log("[remoto] ninguém autorizado ainda. No celular, abra a "
                     f"conversa com @{nome} e mande:\n"
                     f"     /parear {self.codigo}")
        else:
            self.avisar_todos("🤖 bot no ar. /ajuda para ver o que eu faço.")
        while True:
            try:
                self.uma_volta()
            except KeyboardInterrupt:
                self.log("[remoto] encerrando.")
                return
            except Exception as exc:      # rede caindo nao encerra o bot
                self.log(f"[remoto] volta falhou ({exc}); tento de novo.")
                time.sleep(5)
