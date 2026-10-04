# -*- coding: utf-8 -*-
"""Pedidos livres do Adrian atendidos pela equipe soberana (03/10/2026).

O Adrian: "atualmente o unico lugar confiavel para fazer requisicoes e aqui
[o chat do VS Code], mas isso me limita muito!". O pedido do app (Agora >
Pedir, Coordenador > Conversa) ou do Telegram vira um item aqui, e um
trabalhador de cargo `orquestrador` (remoto.delegar) o atende numa worktree.

O arquivo e o servidor sao a fonte da verdade.  O trabalhador e descartavel:
se a sessao some, trava ou o Claude fica proibido, o pedido fica "esperando"
com o motivo e o pulso o retoma.

Ciclo de um pedido:
    recebido -> trabalhando -> entregue -> (o vigia aplica) -> conferente
             -> conferido | falhou
    trabalhando sem mudanca de codigo -> respondido (nada a conferir)
    qualquer passo -> esperando (motivo) -> retomado

Nada aqui roda Claude/Codex no proprio processo: tudo vai por
`delegar.no_fundo` (o pulso do coordenador e a requisicao do app nunca ficam
presos uma hora numa rodada).
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from . import estado

SEM_EVENTO_S = 10 * 60      # sem evento ha 10 min = travado
RETOMAR_S = 120             # entre duas tentativas de retomar o mesmo pedido
PROGRESSO_S = 60            # no maximo uma linha de progresso por minuto
MAX_RETOMADAS = 5           # o mesmo trabalhador retomado 5 vezes: falhou
FINAIS = ("conferido", "falhou", "respondido")
VIVOS = ("recebido", "trabalhando", "esperando", "entregue")
PERMITIDOS = ["remoto/**", "coordenador/**", "docs/**", ".claude/agents/**"]
_TRAVA = threading.RLock()

# perguntas curtas de estado continuam no cerebro (resposta em segundos)
_DE_ESTADO = ("como est", "status", "no ar", "rodando", "serviço", "servico",
              "caiu", "ta de pe", "tá de pé", "está de pé", "esta de pe")
_CONSTRUIR = ("construa", "construir", "implemente", "implementar", "crie", "criar",
              "faça", "faca", "desenvolva", "desenvolver", "conserte", "consertar",
              "corrija", "corrigir", "adicione", "adicionar", "mude", "mudar")
_VERBO = {"le": "lendo", "testa": "rodando testes", "roda": "rodando", "muda": "mudando",
          "plano": "plano", "mensagem": "diz", "despachante": "despachante",
          "erro": "erro"}


def _agora():
    return datetime.now()


def _iso(quando=None):
    return (quando or _agora()).isoformat(timespec="seconds")


def _arquivo():
    return estado.pasta() / "pedidos.json"


def _ler():
    try:
        dados = json.loads(_arquivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = None
    if not isinstance(dados, dict):
        dados = {}
    if not isinstance(dados.get("pedidos"), list):
        dados["pedidos"] = []
    if not isinstance(dados.get("conversa"), list):
        dados["conversa"] = []
    return dados


def _gravar(dados):
    alvo = _arquivo()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    temporario = alvo.with_name("." + alvo.name + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")),
                          encoding="utf-8")
    os.replace(temporario, alvo)


def _linha(dados, pedido, texto, *, de="orquestrador", origem=None, tipo="progresso"):
    linha = {"id": uuid.uuid4().hex[:12], "em": _iso(), "pedido": pedido["id"],
             "de": de, "origem": origem or pedido.get("origem", "app"),
             "tipo": tipo, "texto": str(texto)[:600]}
    dados["conversa"].append(linha)
    dados["conversa"] = dados["conversa"][-400:]
    return linha


def e_de_estado(texto: str) -> bool:
    """Pergunta curta de estado ("o app esta no ar?"): vai ao cerebro, nao
    contrata ninguem."""
    texto = str(texto or "").strip().lower()
    if len(texto) > 160 or _construir(texto):
        return False
    pergunta = "?" in texto or texto.startswith("status")
    return pergunta and any(p in texto for p in _DE_ESTADO)


def _construir(texto):
    texto = str(texto or "").lower()
    return any(palavra in texto for palavra in _CONSTRUIR)


def _segundos_desde(iso, agora):
    try:
        return (agora - datetime.fromisoformat(str(iso))).total_seconds()
    except (TypeError, ValueError):
        return None


def _aprovado(resposta: str) -> bool:
    """O veredito e a PRIMEIRA palavra-chave: "APROVADO, nenhum defeito"
    aprova; "DEFEITOS: ... depois de corrigir fica APROVADO" nao."""
    texto = str(resposta or "").upper()
    sim, nao = texto.find("APROVADO"), texto.find("DEFEITO")
    return sim >= 0 and (nao < 0 or sim < nao)


def _id_conferente(trabalhador: str) -> str:
    # o MESMO id do gerente da equipe (`equipe._conferir_aplicadas`): se o
    # gerente estiver ligado, ele ve que a conferencia ja existe e nao duplica
    from .equipe import _id
    return _id("conf-" + trabalhador)


class MesaPedidos:
    """Entrada, acompanhamento e retomada, com dependencias injetaveis."""

    def __init__(self, *, despachante=None, claude=None, relogio=_agora, avisar=None,
                 uso=None):
        if despachante is None or claude is None:
            from remoto import claude_estado, delegar
            despachante = despachante or delegar
            claude = claude or claude_estado
        self.despachante = despachante
        self.claude = claude
        self.relogio = relogio
        self.avisar = avisar or (lambda _texto: None)
        # quem le as respostas do Grimorio: (leitor, marcar, carregar). Desligado por
        # padrao -- teste nunca le nem marca o Grimorio real; o MESA de producao liga.
        self.grimorio = None
        self.uso = uso

    # ------------------------------------------------------------ entrada
    def registrar(self, texto, origem="app", *, novo=False):
        """Guarda o pedido (ou a continuacao) e volta na hora: quem contrata,
        corrige e retoma e o `passo`, no pulso do coordenador."""
        texto = str(texto or "").strip()
        if not texto:
            raise ValueError("pedido vazio")
        if origem not in ("app", "telegram", "grimorio"):
            raise ValueError("origem desconhecida")
        with _TRAVA:
            dados = _ler()
            if dados.pop("novo_assunto", False):
                novo = True
            atual = None if novo else next((p for p in reversed(dados["pedidos"])
                                            if p.get("situacao") in VIVOS), None)
            if atual:
                atual["texto"] += "\n\nContinuação do Adrian:\n" + texto
                atual["ultima_continuacao"] = texto
                atual["continuar"] = True
                atual["atualizado_em"] = _iso()
                atual["mensagens"] = int(atual.get("mensagens") or 1) + 1
                _linha(dados, atual, texto, de="adrian", origem=origem, tipo="pedido")
                _linha(dados, atual, "continuação recebida; vai ao mesmo orquestrador")
                _gravar(dados)
                return dict(atual, continuacao=True)
            ident = "pedido-" + uuid.uuid4().hex[:8]
            agora = _iso()
            pedido = {"id": ident, "texto": texto, "origem": origem, "situacao": "recebido",
                      "motivo": "", "trabalhador": None, "conferente": None, "ia": None,
                      "contratos": 0, "criado_em": agora, "atualizado_em": agora,
                      "ultimo_evento_em": agora, "mensagens": 1}
            dados["pedidos"].append(pedido)
            dados["pedidos"] = dados["pedidos"][-100:]
            _linha(dados, pedido, texto, de="adrian", origem=origem, tipo="pedido")
            _linha(dados, pedido, "recebido; procurando um orquestrador")
            _gravar(dados)
        return dict(pedido, continuacao=False)

    def novo_assunto(self, origem="app"):
        """O proximo pedido abre outro orquestrador (botao do app, /novo)."""
        with _TRAVA:
            dados = _ler()
            dados["novo_assunto"] = True
            dados["conversa"].append({"id": uuid.uuid4().hex[:12], "em": _iso(),
                                      "pedido": None, "de": "orquestrador",
                                      "origem": origem, "tipo": "progresso",
                                      "texto": "novo assunto: o próximo pedido abre "
                                               "outro orquestrador"})
            _gravar(dados)

    # ------------------------------------------------------------ guardas
    def _motivo_claude(self):
        try:
            motivo = str(self.claude.motivo_proibido() or "")
        except Exception as exc:  # nao perde pedido se o interruptor estiver ilegivel
            return "não consegui ler o interruptor do Claude (" + type(exc).__name__ + ")"
        if motivo:
            return motivo
        try:
            if self.uso is not None:
                uso = self.uso()
            else:
                from remoto import orquestrador
                uso = orquestrador.ler_uso()
            if uso.get("passou_teto"):
                return "o Claude passou do teto de uso da Mesa"
        except Exception:
            pass
        return ""

    def _esperar(self, dados, pedido, motivo):
        """Em espera com o motivo, sem repetir a mesma linha a cada pulso."""
        motivo = str(motivo or "?")[:240]
        mudou = pedido.get("situacao") != "esperando" or pedido.get("motivo") != motivo
        pedido.update(situacao="esperando", motivo=motivo, atualizado_em=_iso())
        if mudou:
            _linha(dados, pedido, "em espera: " + motivo)

    def _estado_do(self, ident):
        if not ident:
            return None
        try:
            return self.despachante.ler_estado(ident)
        except Exception:
            return None

    def _pode_tentar(self, pedido, chave="tentou_em"):
        """Uma tentativa de retomar a cada RETOMAR_S, nao a cada pulso de 5 s."""
        desde = _segundos_desde(pedido.get(chave), self.relogio())
        return desde is None or desde >= RETOMAR_S

    def _ultimo_sinal(self, ident, ficha):
        """Quando o trabalhador deu sinal de vida pela ultima vez.

        O estado.json so muda no inicio, no fim e por rodada do Codex; numa
        rodada longa do Claude ele fica parado. O eventos.jsonl recebe cada
        evento, entao a hora dele e o sinal de vida de verdade."""
        candidatos = []
        try:
            caminho = self.despachante.pasta_da(ident) / "eventos.jsonl"
            candidatos.append(datetime.fromtimestamp(caminho.stat().st_mtime))
        except (OSError, TypeError, ValueError, AttributeError):
            pass
        for chave in ("atualizado_em", "inicio"):
            try:
                candidatos.append(datetime.fromisoformat(str(ficha.get(chave))))
            except (TypeError, ValueError):
                pass
        return max(candidatos) if candidatos else None

    def _motivo_do_fundo(self, ident):
        """A ultima linha do despachante no fundo (a recusa do `rodar`)."""
        try:
            bruto = (self.despachante.pasta_da(ident) / "fundo.txt").read_bytes()[-2000:]
        except (OSError, AttributeError):
            return ""
        linhas = [x.strip() for x in bruto.decode("utf-8", "replace").splitlines() if x.strip()]
        return linhas[-1][:200] if linhas else ""

    # ------------------------------------------------------------ contratar
    def _contratar(self, dados, pedido):
        if not self._pode_tentar(pedido):
            return
        pedido["tentou_em"] = _iso(self.relogio())
        motivo = self._motivo_claude()
        ia = "claude"
        if motivo:
            if not _construir(pedido["texto"]):
                self._esperar(dados, pedido, motivo)
                return
            ia = "codex"          # o Codex assume os pedidos de construir
        n = int(pedido.get("contratos") or 0)
        ident = pedido["id"] if n == 0 else f"{pedido['id']}-{n}"
        if self._estado_do(ident) is None:
            caminho = self.despachante.pasta_da(ident) / "pedido.md"
            caminho.parent.mkdir(parents=True, exist_ok=True)
            corpo = ("# PEDIDO do Adrian (" + ("Telegram" if pedido.get("origem") == "telegram"
                                                 else "app") + ")\n\n" + pedido["texto"])
            if ia == "codex":
                # o Codex nao recebe o prompt do cargo: vai junto com a tarefa
                try:
                    corpo = self.despachante.prompt_do_cargo("orquestrador") + "\n\n" + corpo
                except Exception:
                    pass
            caminho.write_text(corpo, encoding="utf-8")
            try:
                self.despachante.criar(ident, caminho, PERMITIDOS, ia=ia, cargo="orquestrador",
                                       titulo=pedido["texto"].splitlines()[0][:160])
            except Exception as exc:
                self._esperar(dados, pedido, "contratar: " + str(exc)[:200])
                return
        try:
            self.despachante.no_fundo(["rodar", "--id", ident], ident)
        except Exception as exc:
            pedido.update(trabalhador=ident, ia=ia)
            self._esperar(dados, pedido, "rodar: " + str(exc)[:200])
            return
        pedido.update(trabalhador=ident, ia=ia, situacao="trabalhando", motivo="",
                      continuar=False, atualizado_em=_iso(), ultimo_evento_em=_iso())
        _linha(dados, pedido, f"{ia} orquestrador contratado ({ident}); trabalhando numa worktree")

    # ------------------------------------------------------------ acompanhar
    def _progresso(self, dados, pedido, ident):
        """Os eventos do trabalhador, resumidos, no maximo um por minuto."""
        ler = getattr(self.despachante, "ler_eventos", None)
        if ler is None:
            return
        try:
            lido = ler(ident, desde=int(pedido.get("eventos_offset", -1)))
        except Exception:
            return
        pedido["eventos_offset"] = int(lido.get("offset") or 0)
        uteis = [e for e in lido.get("eventos") or []
                 if e.get("texto") and e.get("tipo") in _VERBO]
        if not uteis:
            return
        desde = _segundos_desde(pedido.get("progresso_em"), self.relogio())
        if desde is not None and desde < PROGRESSO_S:
            return
        e = uteis[-1]
        texto = f"{_VERBO[e['tipo']]}: {str(e['texto']).splitlines()[0][:160]}"
        if texto != pedido.get("progresso"):
            pedido.update(progresso=texto, progresso_em=_iso(self.relogio()))
            _linha(dados, pedido, texto)

    def _acompanhar(self, dados, pedido):
        trabalhador = pedido.get("trabalhador")
        ficha = self._estado_do(trabalhador)
        if not ficha:
            pedido.update(trabalhador=None, contratos=int(pedido.get("contratos") or 0) + 1)
            self._esperar(dados, pedido, "o trabalhador sumiu; vou contratar outro")
            return
        situacao = ficha.get("situacao")
        agora = self.relogio()
        if situacao == "rodando":
            if pedido.get("continuar") and pedido.get("continuar_em"):
                pedido.update(continuar=False, continuar_em=None, motivo="")
            sinal = self._ultimo_sinal(trabalhador, ficha)
            if sinal is not None:
                pedido["ultimo_evento_em"] = sinal.isoformat(timespec="seconds")
            self._progresso(dados, pedido, trabalhador)
            if sinal is not None and (agora - sinal).total_seconds() >= SEM_EVENTO_S:
                try:
                    self.despachante.parar(trabalhador)
                except Exception:
                    pass
                pedido["tentou_em"] = _iso(agora)
                self._esperar(dados, pedido, "trabalhador sem evento há mais de 10 min; "
                                             "parei e vou retomar")
            return
        if situacao == "criado":
            # o `rodar` no fundo ainda nao comecou, ou foi recusado (paralelo,
            # janela da postagem): da um prazo e mostra o porque
            desde = _segundos_desde(pedido.get("tentou_em") or pedido.get("atualizado_em"), agora)
            if desde is not None and desde >= RETOMAR_S:
                self._esperar(dados, pedido, self._motivo_do_fundo(trabalhador)
                              or "o trabalhador não começou")
            return
        if situacao == "terminou":
            self._entregue(dados, pedido, ficha)
            return
        self._esperar(dados, pedido, str(ficha.get("motivo") or situacao))

    def _entregue(self, dados, pedido, ficha):
        resposta = self._resposta(pedido.get("trabalhador"))
        diff = ficha.get("diff") if isinstance(ficha.get("diff"), dict) else {}
        if diff and not diff.get("arquivos") and not ficha.get("aplicado"):
            # so respondeu (nada de codigo): nao ha o que aplicar nem conferir
            pedido.update(situacao="respondido", motivo="", resposta=resposta[:1000],
                          atualizado_em=_iso())
            final = resposta.strip()[:500] or "terminou sem mudar código"
            _linha(dados, pedido, "respondido: " + final, tipo="final")
            self.avisar("🧭 Pedido respondido: " + final)
            return
        pedido.update(situacao="entregue", motivo="", atualizado_em=_iso())
        _linha(dados, pedido, "entregue; esperando o vigia testar e aplicar, "
                              "depois o conferente olha")

    def _resposta(self, ident):
        if not ident:
            return ""
        try:
            return (self.despachante.pasta_da(ident) / "resposta.md").read_text(encoding="utf-8")
        except (OSError, AttributeError):
            return ""

    def _retomar(self, dados, pedido):
        trabalhador = pedido["trabalhador"]
        ficha = self._estado_do(trabalhador)
        if not ficha:
            pedido.update(trabalhador=None, contratos=int(pedido.get("contratos") or 0) + 1)
            return
        situacao = ficha.get("situacao")
        if situacao == "rodando":
            if pedido.get("situacao") != "trabalhando":
                pedido.update(situacao="trabalhando", motivo="", atualizado_em=_iso())
                _linha(dados, pedido, "trabalhador de volta")
            return
        if situacao == "terminou" and not pedido.get("continuar"):
            self._entregue(dados, pedido, ficha)
            return
        if pedido.get("continuar"):
            # a continuacao sai no primeiro pulso; se o `corrigir` no fundo
            # nao comecou (paralelo, janela), reenvia depois de RETOMAR_S
            if not self._pode_tentar(pedido, "continuar_em"):
                return
            if pedido.get("continuar_em"):
                pedido["motivo"] = (self._motivo_do_fundo(trabalhador)
                                    or "a continuação não começou; reenviando")
        elif not self._pode_tentar(pedido):
            return
        pedido["tentou_em"] = _iso(self.relogio())
        if ficha.get("ia") == "claude":
            motivo = self._motivo_claude()
            if motivo:
                if _construir(pedido["texto"]):
                    # o Codex assume: um trabalhador novo, a worktree do
                    # Claude fica como estava (o diff dela nao se perde)
                    pedido.update(trabalhador=None,
                                  contratos=int(pedido.get("contratos") or 0) + 1,
                                  tentou_em=None)
                    self._esperar(dados, pedido, motivo + "; o Codex assume")
                else:
                    self._esperar(dados, pedido, motivo)
                return
        if pedido.get("continuar"):
            self._continuar(dados, pedido, ficha)
            return
        if int(pedido.get("retomadas") or 0) >= MAX_RETOMADAS:
            # o mesmo trabalhador caiu de novo e de novo: nao fica girando
            # para sempre gastando a janela; o Adrian ve e decide
            pedido.update(situacao="falhou", atualizado_em=_iso(),
                          motivo=f"caiu {MAX_RETOMADAS} vezes: " + str(pedido.get("motivo") or "?")[:200])
            _linha(dados, pedido, "falhou: " + pedido["motivo"], tipo="final")
            self.avisar("❌ Pedido parado: " + pedido["motivo"])
            return
        pedido["retomadas"] = int(pedido.get("retomadas") or 0) + 1
        try:
            self.despachante.no_fundo(["rodar", "--id", trabalhador], trabalhador)
        except Exception as exc:
            self._esperar(dados, pedido, "retomada: " + str(exc)[:200])
            return
        pedido.update(situacao="trabalhando", motivo="", atualizado_em=_iso())
        _linha(dados, pedido, "trabalhador retomado")

    def _continuar(self, dados, pedido, ficha):
        """A continuacao do Adrian vai ao MESMO trabalhador, no fundo."""
        trabalhador = pedido["trabalhador"]
        if ficha.get("aplicado"):
            # a entrega dele ja esta na arvore principal (e o `aplicar` nao
            # reaplica): a continuacao vai a um trabalhador novo, que parte do
            # HEAD com a mudanca e recebe o pedido inteiro
            pedido.update(trabalhador=None, conferente=None, continuar=False,
                          continuar_em=None, tentou_em=None, situacao="recebido",
                          contratos=int(pedido.get("contratos") or 0) + 1)
            _linha(dados, pedido, "a entrega anterior já foi aplicada; a continuação "
                                  "vai a um orquestrador novo com o pedido inteiro")
            return
        caminho = self.despachante.pasta_da(trabalhador) / "continuacao.md"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        # o Claude abre sessao nova a cada rodada: leva o pedido inteiro
        caminho.write_text("O Adrian continuou o pedido. Pedido inteiro, com as "
                           "continuações:\n\n" + pedido["texto"]
                           + "\n\nAtenda a ÚLTIMA continuação, sem desfazer o que já fez.",
                           encoding="utf-8")
        if ficha.get("ia") == "codex" and not ficha.get("thread_id"):
            argv = ["rodar", "--id", trabalhador]     # sem conversa para continuar
        else:
            argv = ["corrigir", "--id", trabalhador, "--texto", str(caminho)]
        try:
            self.despachante.no_fundo(argv, trabalhador)
        except Exception as exc:
            self._esperar(dados, pedido, "continuação: " + str(exc)[:200])
            return
        if pedido.get("conferente"):
            pedido["conferente"] = None       # a entrega vai mudar: confere de novo
        primeira = not pedido.get("continuar_em")
        # `continuar` so cai quando o trabalhador estiver rodando (_acompanhar)
        pedido.update(situacao="trabalhando", continuar_em=_iso(self.relogio()),
                      atualizado_em=_iso())
        if primeira:
            pedido["motivo"] = ""
            _linha(dados, pedido, "continuação entregue ao mesmo orquestrador")

    # ------------------------------------------------------------ conferir
    def _conferir(self, dados, pedido):
        trabalhador = pedido.get("trabalhador")
        ficha = self._estado_do(trabalhador)
        if not ficha:
            return
        if ficha.get("situacao") == "rodando":
            # o vigia achou teste vermelho e mandou corrigir
            pedido.update(situacao="trabalhando", motivo="", atualizado_em=_iso())
            _linha(dados, pedido, "o vigia mandou corrigir; trabalhando de novo")
            return
        if not ficha.get("aplicado"):
            return                # o vigia ainda nao aplicou (testes, momento seguro)
        ident = pedido.get("conferente") or _id_conferente(trabalhador)
        conf = self._estado_do(ident)
        if conf is None:
            if not self._pode_tentar(pedido, "conf_tentou_em"):
                return
            pedido["conf_tentou_em"] = _iso(self.relogio())
            motivo = self._motivo_claude()
            ia = "codex" if motivo else "claude"
            caminho = self.despachante.pasta_da(ident) / "pedido.md"
            caminho.parent.mkdir(parents=True, exist_ok=True)
            corpo = ("Confira a entrega do pedido " + pedido["id"] + " (trabalhador "
                     + trabalhador + "), JÁ APLICADA nesta worktree: "
                     + ", ".join((ficha.get("aplicado") or {}).get("arquivos") or [])
                     + ".\n\nO pedido do Adrian:\n\n" + pedido["texto"][:20_000]
                     + "\n\nA resposta do trabalhador:\n\n" + self._resposta(trabalhador)[:20_000]
                     + "\n\nDevolva APROVADO ou DEFEITOS (com a lista) em resposta.md.")
            if ia == "codex":
                try:
                    corpo = self.despachante.prompt_do_cargo("conferente") + "\n\n" + corpo
                except Exception:
                    pass
            caminho.write_text(corpo, encoding="utf-8")
            try:
                self.despachante.criar(ident, caminho, PERMITIDOS[:3], ia=ia,
                                       cargo="conferente", titulo="Conferir " + pedido["id"])
                self.despachante.no_fundo(["rodar", "--id", ident], ident)
            except Exception as exc:
                self._esperar_conferente(dados, pedido, str(exc)[:200])
                return
            pedido.update(conferente=ident, motivo="")
            _linha(dados, pedido, f"aplicado; conferente ({ia}) olhando")
            return
        pedido["conferente"] = ident
        situacao = conf.get("situacao")
        if situacao == "terminou":
            resposta = self._resposta(ident)
            if _aprovado(resposta):
                pedido.update(situacao="conferido", motivo="", resposta=resposta[:1000],
                              atualizado_em=_iso())
                final = (self._resposta(trabalhador).strip()[:400] or "pronto")
                _linha(dados, pedido, "conferido: " + final, tipo="final")
                self.avisar("✅ Pedido conferido: " + final)
            else:
                pedido.update(situacao="falhou", motivo="o conferente apontou defeitos",
                              resposta=resposta[:1000], atualizado_em=_iso())
                _linha(dados, pedido, "o conferente apontou defeitos: "
                       + (resposta.strip()[:400] or "(sem resposta)"), tipo="final")
                self.avisar("❌ Pedido com defeitos: " + (resposta.strip()[:400] or "?"))
            return
        if situacao in ("rodando", "criado"):
            return
        # parado/falhou: retoma o MESMO conferente, sem recriar
        if not self._pode_tentar(pedido, "conf_tentou_em"):
            return
        pedido["conf_tentou_em"] = _iso(self.relogio())
        motivo = self._motivo_claude() if conf.get("ia") == "claude" else ""
        if motivo:
            self._esperar_conferente(dados, pedido, motivo)
            return
        try:
            self.despachante.no_fundo(["rodar", "--id", ident], ident)
        except Exception as exc:
            self._esperar_conferente(dados, pedido, str(exc)[:200])

    def _esperar_conferente(self, dados, pedido, motivo):
        """Continua "entregue" (o pulso volta ao conferente), com o motivo."""
        motivo = "conferente: " + str(motivo)[:220]
        if pedido.get("motivo") != motivo:
            pedido["motivo"] = motivo
            _linha(dados, pedido, "em espera: " + motivo)

    # ------------------------------------------------------------ pulso
    def ler_grimorio(self, leitor=None, marcar=None, carregar=None):
        """Cada resposta NAO LIDA do Grimorio vira um pedido para um orquestrador do
        servidor, e a resposta fica marcada como lida apontando para ele.

        04/10/2026, o Adrian: "Por que nao tem ninguem lendo as decisoes?". Quem lia
        era so a sessao do VS Code: fechada ela, a resposta ficava parada."""
        if leitor is None or marcar is None or carregar is None:
            if self.grimorio is None:
                return []
            leitor, marcar, carregar = self.grimorio
        criados = []
        itens = carregar()
        for ev in leitor():
            if ev.get("lida") or ev.get("ilegivel") or not ev.get("id"):
                continue
            no = itens.get(ev["id"]) or {}
            opcao = next((o for o in no.get("opcoes") or [] if o.get("id") == ev.get("opcao")), {})
            texto = (f"O Adrian respondeu no Grimório ({ev.get('projeto')}/{ev['id']}): "
                     f"«{ev.get('titulo') or no.get('titulo')}»\n"
                     f"Pergunta: {no.get('pergunta') or ''}\n"
                     f"Escolheu: {ev.get('opcao_rotulo') or ev.get('opcao')} — {opcao.get('descricao') or ''}\n"
                     + (f"Comentário dele: {ev['comentario']}\n" if ev.get("comentario") else "")
                     + f"Contexto do nó: {no.get('contexto') or ''}\n\n"
                     "APLIQUE a escolha: faça o que ela pede (ou contrate quem faça), confira e "
                     "responda curto. Se já estiver feito, confirme e encerre. Se a escolha precisar "
                     "de algo que só ele faz (login, conta), diga exatamente o quê.")
            pedido = self.registrar(texto, "grimorio", novo=True)
            ref = f"{ev.get('projeto')}/{ev['id']}"
            try:
                marcar(ref, [f"tarefa:{pedido['id']}"],
                       nota="lida pelo servidor; virou pedido ao orquestrador", origem="leitor")
            except Exception as exc:                          # noqa: BLE001
                with _TRAVA:
                    dados = _ler()
                    _linha(dados, pedido, f"não consegui marcar {ref} como lida: {exc}")
                    _gravar(dados)
            criados.append(pedido["id"])
        return criados

    def passo(self):
        try:
            self.ler_grimorio()
        except Exception as exc:                              # noqa: BLE001
            self.avisar(f"⚠ não consegui ler o Grimório: {exc}")
        with _TRAVA:
            dados = _ler()
            for pedido in dados["pedidos"]:
                situacao = pedido.get("situacao")
                if situacao in FINAIS:
                    continue
                try:
                    if not pedido.get("trabalhador"):
                        self._contratar(dados, pedido)
                    elif situacao == "trabalhando":
                        if pedido.get("continuar"):
                            ficha = self._estado_do(pedido["trabalhador"]) or {}
                            if ficha.get("situacao") not in ("rodando", "criado"):
                                self._retomar(dados, pedido)
                                continue
                        self._acompanhar(dados, pedido)
                    elif situacao in ("esperando", "recebido"):
                        self._retomar(dados, pedido)
                    elif situacao == "entregue":
                        if pedido.get("continuar"):
                            self._retomar(dados, pedido)
                        else:
                            self._conferir(dados, pedido)
                except Exception as exc:    # um pedido ruim nao para os outros
                    self._esperar(dados, pedido, f"erro interno ({type(exc).__name__}: {exc})")
            _gravar(dados)
            return dados

    def para_o_app(self):
        dados = _ler()
        pedidos = [{k: v for k, v in p.items() if k != "resposta"}
                   for p in reversed(dados["pedidos"])][:40]
        return {"pedidos": pedidos, "conversa": dados["conversa"][-120:],
                "novo_assunto": bool(dados.get("novo_assunto")),
                "na_fila": sum(1 for p in pedidos if p.get("situacao") in VIVOS)}


MESA = MesaPedidos()


def _ligar_grimorio_real():
    from remoto import decisoes
    MESA.grimorio = (decisoes.leitor, decisoes.marcar, decisoes.carregar)


def registrar(texto, origem="app", *, novo=False):
    return MESA.registrar(texto, origem, novo=novo)


def novo_assunto(origem="app"):
    return MESA.novo_assunto(origem)


def passo():
    return MESA.passo()


def para_o_app():
    return MESA.para_o_app()
