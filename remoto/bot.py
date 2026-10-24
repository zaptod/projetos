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

import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import api, avisos, comandos, config, vigia_tailnet
from .api import Telegram


def _codigo() -> str:
    return f"{random.randint(0, 999999):06d}"


def carimbar(texto: str, agora: datetime | None = None) -> str:
    """A linha do log com data e hora na frente.

    Ate 16/09/2026 o `outputs/bot.txt` nao tinha hora nenhuma: depois de um
    reinicio, "relatorio de metas enviado" no fim do arquivo podia ser de
    agora ou de tres dias atras, e so o `relatorios.json` desempatava.
    """
    return f"{(agora or datetime.now()).strftime('%d/%m %H:%M:%S')} {texto}"


def _log_com_hora(texto: str) -> None:
    print(carimbar(texto), flush=True)


BOT_VISTO = None           # os testes apontam para outro lugar
SEM_REDE_ESPERA_S = 10.0   # uma volta sem rede dorme isto antes de seguir
GETME_ESPERA_S = 30.0      # getMe sem rede: tenta de novo a cada isto
RELATORIO_REAPROVEITA_S = 3600.0
ALERTAS_UM_A_UM = 5        # os mais novos saem um a um; o resto vai junto


def _enfileirar_restos(restos, chave, origem: str) -> None:
    """O que faltou de uma mensagem entregue PELA METADE vai para a fila —
    so o resto: reenfileirar o texto inteiro mandava a parte 1 de novo."""
    for resto in dict.fromkeys(r for r in restos if isinstance(r, str) and r.strip()):
        avisos.enfileirar(resto, chave=(f"{chave}|resto" if chave else None), origem=origem)


def caminho_do_visto() -> Path:
    """Onde mora a marca-d'agua dos erros ja tratados (ao lado do remoto.json)."""
    return Path(BOT_VISTO) if BOT_VISTO else config.caminho().with_name("bot_visto.json")


class Bot:
    def __init__(self, *, telegram=None, log=_log_com_hora, dormir=time.sleep):
        self.log = log
        self._dormir = dormir
        self.config = config.carregar()
        self.tg = telegram or Telegram(config.token())
        self.desde = None
        self.codigo = _codigo()
        self.pareado_agora = False
        # nome -> (texto, monotonic): o relatorio vencido montado e ainda nao
        # entregue (sem rede) e reaproveitado em vez de remontado a cada volta
        self._relatorio_montado: dict[str, tuple] = {}
        # So alerta o que acontecer DAQUI para a frente: ligar o bot nao pode
        # despejar no celular o historico inteiro de erros do dia. Por isso o
        # que ja esta no diario entra como "visto" antes da primeira volta.
        #
        # A marca e a IDENTIDADE do evento, nao o horario: o carimbo do
        # diario tem precisao de SEGUNDO, e uma marca-d'agua temporal engolia
        # todo erro que caisse no mesmo segundo do anterior — justamente o
        # caso de uma falha em cascata, que e quando avisar mais importa.
        #
        # Desde 14/10 (APP-11) o "visto" sobrevive a religada: o
        # `bot_visto.json` guarda o ts do ultimo erro tratado (e as marcas
        # daquele segundo). Um erro gravado nos ~30 s antes de uma religada
        # era marcado como visto pelo bot novo e nunca avisado.
        recentes = self._erros_no_diario()
        visto = self._ler_visto()
        if visto is None:
            # primeira subida (ou arquivo ilegivel): como sempre foi, o que
            # ja esta no diario e passado. Diario vazio grava ts "" (tudo o
            # que vier depois e novo, mesmo atravessando uma religada).
            self.avisados = {self._marca(e) for e in recentes}
            self._gravar_visto(recentes, inicial=True)
        else:
            ts_visto, marcas = visto
            self.avisados = {self._marca(e) for e in recentes
                             if str(e.get("ts", "")) < ts_visto
                             or (str(e.get("ts", "")) == ts_visto
                                 and self._marca(e) in marcas)}
        # So o laco de verdade (`rodar`) liga a vigia do tailnet: os testes
        # que chamam `uma_volta` nunca perguntam nada ao Tailscale nem abrem
        # a bandeja dele.
        self.vigia_tailnet = None

    @staticmethod
    def _marca(evento: dict) -> tuple:
        return (str(evento.get("ts", "")), evento.get("fabrica"),
                evento.get("canal"), str(evento.get("detalhe", ""))[:120])

    # ------------------------------------------- a marca-d'agua dos alertas
    def _ler_visto(self):
        """(ts, {marcas daquele ts}) ou None (nunca gravado / ilegivel)."""
        try:
            dados = json.loads(caminho_do_visto().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(dados, dict) or not isinstance(dados.get("ts"), str):
            return None
        marcas = {tuple(m) for m in dados.get("marcas") or [] if isinstance(m, list)}
        return dados["ts"], marcas

    def _gravar_visto(self, tratados: list, inicial: bool = False) -> None:
        """Avanca a marca para o erro mais novo tratado. Nunca volta atras."""
        if not tratados and not inicial:
            return
        ts = max((str(e.get("ts", "")) for e in tratados), default="")
        marcas = {self._marca(e) for e in tratados if str(e.get("ts", "")) == ts}
        anterior = None if inicial else self._ler_visto()
        if anterior is not None:
            if anterior[0] > ts:
                return
            if anterior[0] == ts:
                marcas |= anterior[1]
        try:
            destino = caminho_do_visto()
            destino.parent.mkdir(parents=True, exist_ok=True)
            tmp = destino.with_name(destino.name + ".tmp")
            tmp.write_text(json.dumps({"ts": ts, "marcas": sorted(
                [list(m) for m in marcas], key=str)}, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, destino)
        except OSError as exc:
            self.log(f"[remoto] nao gravei o bot_visto.json: {exc}")

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
        # `recentes` vem do mais novo para o mais velho. Os ALERTAS_UM_A_UM
        # mais novos saem um a um; os mais velhos que eles vao JUNTOS numa
        # mensagem so. Ate 14/10 (APP-11) eles entravam em `avisados` sem
        # sair, nem para a fila, nem para os calados: do 6o em diante sumiam.
        tratados = []
        saiu = False
        for evento in reversed(novos[:ALERTAS_UM_A_UM]):
            fabrica = comandos.atividade.FABRICAS.get(evento.get("fabrica"), {})
            texto = (f"❗ *{fabrica.get('rotulo', evento.get('fabrica'))}* "
                     f"({evento.get('canal', '?')})\n"
                     f"{(evento.get('detalhe') or '')[:400]}")
            # O MESMO ERRO, UMA VEZ POR DIA. A marca acima e a identidade do
            # EVENTO (com o segundo): o reparo que falha igual a cada tentativa
            # gera um evento novo por tentativa. Medido em 04/10/2026: 22 vezes
            # "No module named 'ias'" em 4 h, cada uma uma mensagem e uma
            # apuracao. O total do dia continua no relatorio de funcionamento.
            chave = "bot.erro|" + "|".join(str(evento.get(c) or "") for c in
                                           ("fabrica", "canal", "etapa"))
            chave_aviso = chave + "|" + avisos.normalizar(evento.get("detalhe") or "")[:200]
            saiu = self._mandar_alerta(texto, chave_aviso) or saiu
            tratados.append(evento)
        resto = novos[ALERTAS_UM_A_UM:]
        if resto:
            linhas = []
            for evento in reversed(resto):
                fabrica = comandos.atividade.FABRICAS.get(evento.get("fabrica"), {})
                linhas.append(f"• {fabrica.get('rotulo', evento.get('fabrica'))} "
                              f"({evento.get('canal', '?')}): "
                              f"{' '.join(str(evento.get('detalhe') or '').split())[:160]}")
            texto = f"❗ e mais {len(resto)} erro(s):\n" + "\n".join(linhas)
            chave_aviso = "bot.erro.mais|" + avisos.normalizar(" ".join(linhas))[:200]
            saiu = self._mandar_alerta(texto[:3900], chave_aviso, markdown=False) or saiu
            tratados.extend(resto)
        # O conjunto so guarda o que ainda esta na janela do diario: sem isso
        # ele cresceria para sempre num processo que fica ligado dias. Entra
        # o que foi mandado, juntado, enfileirado ou calado pelo porteiro.
        janela = {self._marca(e) for e in recentes}
        self.avisados = (self.avisados | {self._marca(e) for e in tratados}) & janela
        self._gravar_visto(tratados)
        if saiu:
            self._apurar()

    def _pos_entrega(self, chat, texto: str, resposta: dict) -> None:
        """Entrega pela metade: o resto vai para a fila (quem chama), entao a
        memoria do Telegram acaba; parte pulada e dita no log."""
        if resposta.get("resto"):
            self.tg.assumir_resto(chat, texto)
        if resposta.get("parcial"):
            self.log(f"[remoto] entrega parcial para {chat}: {resposta.get('description')}.")

    def _mandar_alerta(self, texto: str, chave: str, *, markdown: bool = True) -> bool:
        """Passa pelo porteiro e manda; sem entrega, vai para a fila. True = saiu."""
        if not avisos.liberar(texto, chave=chave, origem="bot.alerta"):
            return False
        entregues, restos = 0, []
        for chat in config.carregar()["autorizados"]:
            try:
                resposta = self.tg.mensagem(chat, texto, markdown=markdown)
                if api.chegou_algo(resposta):
                    entregues += 1
                    restos.append(resposta.get("resto"))
                    self._pos_entrega(chat, texto, resposta)
            except Exception:                                  # noqa: BLE001
                pass
        if entregues:
            avisos.confirmar(texto, chave=chave, origem="bot.alerta")
            _enfileirar_restos(restos, chave, "bot.alerta")
            return True
        avisos.desfazer(texto, chave=chave)
        avisos.enfileirar(texto, chave=chave, origem="bot.alerta")
        return False

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

        Marca DEPOIS de entregar a pelo menos um chat: sem rede, o relatorio
        tenta de novo na volta seguinte, e sai uma vez quando a rede voltar.
        O texto montado e reaproveitado por ate `RELATORIO_REAPROVEITA_S`
        enquanto nao sai (APP-9, 14/10): o `montar` consulta o Agendador e o
        OAuth, e sem rede ele rodava a cada volta do laco.
        """
        from . import relatorios

        horarios = config.carregar().get("relatorios") or {}
        vencidos = relatorios.devidos(horarios)
        if not vencidos:
            return
        hoje = datetime.now().strftime("%Y-%m-%d")
        for nome in vencidos:
            guardado = self._relatorio_montado.get(nome)
            # Entregue PELA METADE: o mesmo texto fica, por mais velho que
            # seja — o Telegram retoma da parte que falta so se o texto for
            # o mesmo; remontar mandaria a parte 1 de novo (21/10).
            if guardado and ((len(guardado) > 2 and guardado[2]) or
                             time.monotonic() - guardado[1] < RELATORIO_REAPROVEITA_S):
                texto = guardado[0]
            else:
                texto = relatorios.montar(nome)
                self._relatorio_montado[nome] = (texto, time.monotonic(), False)
            entregues, pela_metade = 0, False
            for chat in config.carregar()["autorizados"]:
                try:
                    resposta = self.tg.mensagem(chat, texto, markdown=True)
                    if resposta.get("ok"):
                        entregues += 1
                        if resposta.get("parcial"):
                            self.log(f"[remoto] relatorio de {nome}: "
                                     f"{resposta.get('description')}.")
                    elif resposta.get("partes_enviadas"):
                        pela_metade = True
                except Exception:                              # noqa: BLE001
                    pass
            if entregues:
                relatorios.marcar(nome, hoje)
                self._relatorio_montado.pop(nome, None)
                self.log(f"[remoto] relatorio de {nome} enviado.")
            elif pela_metade:
                self._relatorio_montado[nome] = (texto, self._relatorio_montado[nome][1], True)

    def avisar_todos(self, texto: str, *, chave: str | None = None) -> bool:
        """Aviso espontaneo (nao e resposta a comando): passa pelo porteiro."""
        if not avisos.liberar(texto, chave=chave, origem="bot"):
            return False
        entregues, restos = 0, []
        for chat in config.carregar()["autorizados"]:
            try:
                resposta = self.tg.mensagem(chat, texto)
                if api.chegou_algo(resposta):
                    entregues += 1
                    restos.append(resposta.get("resto"))
                    self._pos_entrega(chat, texto, resposta)
            except Exception:                                  # noqa: BLE001
                pass
        if entregues:
            avisos.confirmar(texto, chave=chave, origem="bot")
            _enfileirar_restos(restos, chave, "bot")
            return True
        avisos.desfazer(texto, chave=chave)
        avisos.enfileirar(texto, chave=chave, origem="bot")
        return False

    def _entregar_pendentes(self):
        """Tenta novamente os avisos que falharam por falta de rede."""
        agora = datetime.now()
        vivos = []
        # o que sai da fila no fim: entregues, calados e velhos. A fila e
        # RELIDA na hora de tirar (`retirar_pendentes`, sob a trava): o que
        # outro processo enfileirou durante a entrega fica (APP-12, 14/10;
        # antes ela era regravada inteira com o que sobrou daqui).
        saidos = []
        itens = avisos.pendentes()
        if not itens:
            return              # fila vazia: nada a regravar a cada volta
        for item in itens:
            quando = avisos._data(item.get("em"))
            if quando is None or quando < agora - timedelta(hours=24):
                self.log("[remoto] aviso pendente ha mais de 24 h descartado.")
                saidos.append(item)
            else:
                vivos.append(item)
        if not vivos:
            avisos.retirar_pendentes(saidos)
            return

        if len(vivos) > 3:
            grupos = []
            grupo = []
            tamanho = 100
            for item in vivos:
                item_tamanho = len(str(item.get("texto", ""))) + 2
                if grupo and tamanho + item_tamanho > 3800:
                    grupos.append(grupo)
                    grupo, tamanho = [], 100
                grupo.append(item)
                tamanho += item_tamanho
            if grupo:
                grupos.append(grupo)
        else:
            grupos = [[item] for item in vivos]
        for grupo in grupos:
            # o porteiro PRIMEIRO, e o texto so com o que ele liberou: ate
            # 14/10 o grupo inteiro ia, inclusive o que ele tinha calado (APP-16)
            liberados = [item for item in grupo if avisos.liberar(
                item.get("texto", ""), chave=item.get("chave"),
                origem=item.get("origem", "bot"))]
            saidos.extend(item for item in grupo if item not in liberados)
            if not liberados:
                continue
            primeiro = avisos._data(liberados[0].get("em")) or agora
            texto = ("⚠ Avisos que nao sairam por falta de rede (desde "
                     + primeiro.strftime("%H:%M") + ")\n\n"
                     + "\n\n".join(str(item.get("texto", "")) for item in liberados)
                     if len(liberados) > 1 else str(liberados[0].get("texto", "")))
            entregues, restos = 0, []
            for chat in config.carregar()["autorizados"]:
                try:
                    resposta = self.tg.mensagem(chat, texto)
                    if api.chegou_algo(resposta):
                        entregues += 1
                        restos.append(resposta.get("resto"))
                        self._pos_entrega(chat, texto, resposta)
                except Exception:                              # noqa: BLE001
                    pass
            if entregues:
                for item in liberados:
                    avisos.confirmar(item.get("texto", ""), chave=item.get("chave"),
                                     origem=item.get("origem", "bot"))
                saidos.extend(liberados)
                _enfileirar_restos(restos, None, liberados[0].get("origem", "bot"))
            else:
                for item in liberados:
                    avisos.desfazer(item.get("texto", ""), chave=item.get("chave"))
        avisos.retirar_pendentes(saidos)

    # ---------------------------------------------------------------- laco
    def uma_volta(self, timeout: int = 30) -> int:
        novidades = self.tg.novidades(self.desde, timeout=timeout)
        if novidades is None:
            # Sem rede o `getUpdates` volta NA HORA (nao espera os 30 s do
            # long polling): sem esta pausa o laco girava milhares de voltas
            # por segundo (APP-9, 14/10).
            self._dormir(SEM_REDE_ESPERA_S)
            novidades = []
        for atualizacao in novidades:
            mensagem = atualizacao.get("message") or {}
            try:
                self._mensagem(mensagem)
            except Exception as exc:      # uma mensagem ruim nao derruba o bot
                self.log(f"[remoto] erro tratando mensagem: {exc}")
                chat = (mensagem.get("chat") or {}).get("id")
                if chat is not None:
                    try:
                        self.tg.mensagem(chat, "nao consegui agora, mande de novo")
                    except Exception as resposta_exc:           # noqa: BLE001
                        self.log(f"[remoto] erro respondendo mensagem: {resposta_exc}")
            self.desde = int(atualizacao.get("update_id", 0)) + 1
        try:
            self._alertar()
        except Exception as exc:
            self.log(f"[remoto] erro nos alertas: {exc}")
        try:
            self._relatorios()
        except Exception as exc:   # relatorio quebrado nao derruba o bot
            self.log(f"[remoto] erro nos relatorios: {exc}")
        try:
            self._entregar_pendentes()
        except Exception as exc:
            self.log(f"[remoto] erro nos avisos pendentes: {exc}")
        try:
            self._vigiar_tailnet()
        except Exception as exc:   # vigia quebrada nao derruba o bot
            self.log(f"[remoto] erro na vigia do tailnet: {exc}")
        return len(novidades)

    # ------------------------------------------------------- vigia do tailnet
    def _ligar_vigia_tailnet(self):
        """O app do celular so existe dentro do tailnet; em 28/09/2026 ele
        ficou fora dele depois de um religamento e nada avisou. Desliga com
        `"vigiar_tailnet": false` no remoto.json."""
        if config.carregar().get("vigiar_tailnet", True):
            # chave UNICA "tailnet": caiu -> voltou -> caiu sai sempre (o
            # estado mudou); o mesmo "consertei" cinco vezes num dia, uma so.
            self.vigia_tailnet = vigia_tailnet.Vigia(
                avisar=lambda texto: self.avisar_todos(texto, chave="tailnet"),
                log=lambda texto: self.log(f"[remoto] {texto}"))

    def _vigiar_tailnet(self):
        if self.vigia_tailnet is None:
            return
        aviso = self.vigia_tailnet.talvez()
        if aviso:
            self.log(f"[remoto] tailnet: {aviso}")

    def _quem_sou(self) -> str | None:
        """O @ do bot. Sem rede, espera a rede voltar (APP-10, 14/10): ate
        entao um getMe sem resposta era tratado como token errado, e o
        processo saia — quem o trazia de volta era o coordenador, com limite
        de religadas por hora. Sai (None) so com token errado DE VERDADE."""
        bruto_de = getattr(self.tg, "eu_bruto", None)
        if bruto_de is None:                     # dubles antigos so tem `eu`
            return (self.tg.eu() or {}).get("username")
        avisou = False
        while True:
            bruto = bruto_de() or {}
            nome = (bruto.get("result") or {}).get("username")
            if bruto.get("ok") and nome:
                return nome
            if bruto.get("error_code") in (401, 404):
                return None
            if not avisou:
                motivo = ("sem rede" if not bruto
                          else f"o Telegram respondeu {bruto.get('error_code', '?')}")
                self.log(f"[remoto] getMe: {motivo}; tento a cada "
                         f"{GETME_ESPERA_S:.0f} s.")
                avisou = True
            self._dormir(GETME_ESPERA_S)

    def rodar(self):
        nome = self._quem_sou()
        if not nome:
            self.log("[remoto] o Telegram recusou o getMe. O token "
                     "está certo? (arquivo remoto.json ou TELEGRAM_BOT_TOKEN)")
            return
        self.log(f"[remoto] bot @{nome} no ar.")
        if not config.carregar()["autorizados"]:
            self.log("[remoto] ninguém autorizado ainda. No celular, abra a "
                     f"conversa com @{nome} e mande:\n"
                     f"     /parear {self.codigo}")
        else:
            # Uma vez por dia: o coordenador religa o bot a cada codigo novo
            # (60 religamentos em 48 h, medido em 04/10/2026), e cada um
            # mandava esta linha.
            self.avisar_todos("🤖 bot no ar. /ajuda para ver o que eu faço.",
                              chave="bot.no_ar")
        self._ligar_vigia_tailnet()
        while True:
            try:
                self.uma_volta()
            except KeyboardInterrupt:
                self.log("[remoto] encerrando.")
                return
            except Exception as exc:      # rede caindo nao encerra o bot
                self.log(f"[remoto] volta falhou ({exc}); tento de novo.")
                self._dormir(5)
