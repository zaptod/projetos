"""Interpretacao e despacho de comandos de espectador.

Um evento de plataforma **nunca** vira efeito direto. Ele atravessa quatro
fronteiras, nesta ordem, e cada uma pode encerrar o caminho:

1. **idempotencia** -- ``event_id`` ja no journal encerra em silencio;
2. **parsing** -- texto vira um comando do catalogo, ou nada;
3. **politica** -- cooldown, teto por round, saturacao e pagamento;
4. **efeito** -- traducao para a API de dominio, so entao.

Nada e descartado sem registro: todo evento recebido termina o percurso com um
status gravado. Dinheiro esta envolvido, e falha silenciosa e inaceitavel.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

from neural_fights.live import effects
from neural_fights.live.catalog import command_por_gatilho, get_command
from neural_fights.live.events import EventKind, ViewerEvent
from neural_fights.live.policy import Decisao, PolicyEngine
from neural_fights.live.registry import Fighter, LiveRegistry

logger = logging.getLogger(__name__)

PREFIXO_COMANDO = "!"
COMANDO_ENTRAR = "entrar"

# Status gravados no journal. Sao poucos de proposito: cada um exige uma
# resposta operacional diferente durante a transmissao.
STATUS_APLICADO = "APLICADO"
STATUS_ADIADO = "ADIADO"
STATUS_DUPLICADO = "DUPLICADO"
STATUS_IGNORADO = "IGNORADO"
STATUS_RECUSADO = "RECUSADO"
STATUS_ERRO = "ERRO"


@dataclass(frozen=True)
class ResultadoComando:
    """O que aconteceu com um evento. Nada e descartado em silencio."""

    aplicado: bool
    status: str
    detalhe: str = ""
    fighter: Fighter | None = None
    command_id: str = ""

    def __bool__(self) -> bool:
        return self.aplicado


def extrair_comando(texto: str) -> tuple[str, tuple[str, ...]]:
    """Separa ``!verbo arg arg`` em verbo minusculo e argumentos.

    Devolve verbo vazio quando a mensagem nao e um comando -- a maior parte do
    chat e conversa, e conversa nao deve custar processamento.
    """
    texto = (texto or "").strip()
    if not texto.startswith(PREFIXO_COMANDO):
        return "", ()
    partes = texto[len(PREFIXO_COMANDO):].split()
    if not partes:
        return "", ()
    return partes[0].lower(), tuple(partes[1:])


class CommandRouter:
    """Roteia eventos para comandos, com idempotencia, politica e journaling."""

    def __init__(
        self,
        registry: LiveRegistry,
        *,
        simulador=None,
        policy: PolicyEngine | None = None,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.registry = registry
        self.simulador = simulador
        self.policy = policy if policy is not None else PolicyEngine(relogio=relogio)

    # ------------------------------------------------------------------ ciclo

    def novo_round(self) -> None:
        """Zera os contadores por partida. Chamado pela sessao na troca."""
        self.policy.novo_round()

    def processar(self, evento: ViewerEvent) -> ResultadoComando:
        """Ponto unico de entrada. Toda decisao passa pelo journal."""
        # Idempotencia primeiro: uma reconexao reentrega o que ja foi lido, e
        # reprocessar um evento pago cobraria a pessoa duas vezes.
        if not self.registry.registrar_evento(
            event_id=evento.event_id,
            kind=evento.kind.value,
            status="RECEBIDO",
            sequence=evento.sequence,
            value_units=evento.value_units,
        ):
            return ResultadoComando(False, STATUS_DUPLICADO, evento.event_id)

        try:
            resultado = self._despachar(evento)
        except Exception as exc:
            logger.exception("falha ao processar %s", evento.event_id)
            resultado = ResultadoComando(False, STATUS_ERRO, f"{type(exc).__name__}: {exc}")

        self._anotar(evento, resultado)
        return resultado

    # -------------------------------------------------------------- despacho

    def _despachar(self, evento: ViewerEvent) -> ResultadoComando:
        verbo, argumentos = extrair_comando(evento.text)

        if verbo == COMANDO_ENTRAR:
            return self.entrar(evento)

        command_id = command_por_gatilho(f"{PREFIXO_COMANDO}{verbo}") if verbo else None
        if command_id is None:
            if verbo:
                return ResultadoComando(False, STATUS_IGNORADO, f"verbo desconhecido: {verbo}")
            if evento.kind is EventKind.CHAT:
                return ResultadoComando(False, STATUS_IGNORADO, "conversa")
            return ResultadoComando(False, STATUS_IGNORADO, "presente sem comando")

        return self.executar(command_id, evento, argumentos)

    def entrar(self, evento: ViewerEvent) -> ResultadoComando:
        """Registra o espectador e garante que ele tenha um lutador.

        Idempotente por natureza: quem ja tem lutador ativo recebe o mesmo de
        volta, entao repetir ``!entrar`` nunca gera um segundo personagem.
        """
        viewer = self._viewer_de(evento)
        if viewer.banned:
            return ResultadoComando(False, STATUS_RECUSADO, "espectador banido")

        ja_tinha = self.registry.obter_lutador_ativo(viewer.viewer_id)
        fighter = self.registry.criar_lutador(viewer)
        detalhe = "ja_registrado" if ja_tinha is not None else fighter.catalog_name
        return ResultadoComando(True, STATUS_APLICADO, detalhe, fighter, COMANDO_ENTRAR)

    def executar(
        self,
        command_id: str,
        evento: ViewerEvent,
        argumentos: tuple[str, ...] = (),
    ) -> ResultadoComando:
        """Avalia a politica e, se aprovado, aplica o efeito."""
        dados = get_command(command_id)
        viewer = self._viewer_de(evento)

        veredito = self.policy.avaliar(
            command_id,
            viewer_id=viewer.viewer_id,
            value_units=evento.value_units,
            banido=viewer.banned,
            privilegiado=evento.privilegiado,
            round_ativo=self._round_ativo(),
            estado_mundo=self._estado_mundo(),
        )

        if veredito.decisao == Decisao.RECUSAR:
            return ResultadoComando(
                False, STATUS_RECUSADO, f"{veredito.motivo} {veredito.detalhe}".strip(),
                command_id=command_id,
            )

        if veredito.decisao == Decisao.ADIAR:
            return self._adiar(command_id, evento, viewer, argumentos, veredito.motivo)

        if dados["escopo"] == "ROUND":
            return self._enfileirar(command_id, evento, viewer, argumentos)

        return self._aplicar_agora(command_id, dados, evento, viewer, argumentos)

    # -------------------------------------------------------------- execucao

    def _aplicar_agora(self, command_id, dados, evento, viewer, argumentos) -> ResultadoComando:
        if self.simulador is None:
            return ResultadoComando(False, STATUS_ADIADO, "sem simulador", command_id=command_id)

        alvo = None
        if dados["escopo"] == "ALVO":
            alvo = self._resolver_alvo(viewer, argumentos)
            if alvo is None:
                return ResultadoComando(
                    False, STATUS_RECUSADO, "alvo nao informado (use p1 ou p2)",
                    command_id=command_id,
                )

        try:
            detalhe = effects.aplicar(self.simulador, command_id, alvo=alvo)
        except effects.EfeitoIndisponivel as exc:
            # O mundo mudou entre a decisao e a aplicacao. Nada foi cobrado.
            return ResultadoComando(False, STATUS_ADIADO, str(exc), command_id=command_id)

        self.policy.registrar_uso(
            command_id, viewer.viewer_id, custo=int(dados["custo_units"])
        )
        return ResultadoComando(True, STATUS_APLICADO, detalhe, command_id=command_id)

    def _enfileirar(self, command_id, evento, viewer, argumentos) -> ResultadoComando:
        """Comando de proxima partida: nunca altera o round em andamento."""
        payload = self._payload_valido(command_id, argumentos)
        if payload is None:
            return ResultadoComando(
                False, STATUS_RECUSADO, "argumento invalido", command_id=command_id
            )
        self.registry.enfileirar_para_proximo_round(
            command_id=command_id, payload=payload, viewer_id=viewer.viewer_id
        )
        self.policy.registrar_uso(
            command_id, viewer.viewer_id, custo=int(get_command(command_id)["custo_units"])
        )
        return ResultadoComando(True, STATUS_APLICADO, f"fila:{payload}", command_id=command_id)

    def _adiar(self, command_id, evento, viewer, argumentos, motivo) -> ResultadoComando:
        """Intencao paga que nao coube agora vira credito do proximo round."""
        dados = get_command(command_id)
        if "ENTRE_ROUNDS" in dados["aplicavel_em"]:
            payload = self._payload_valido(command_id, argumentos)
            if payload is not None:
                self.registry.enfileirar_para_proximo_round(
                    command_id=command_id, payload=payload, viewer_id=viewer.viewer_id
                )
                return ResultadoComando(
                    False, STATUS_ADIADO, f"{motivo}->fila", command_id=command_id
                )
        return ResultadoComando(False, STATUS_ADIADO, motivo, command_id=command_id)

    # --------------------------------------------------------------- suporte

    def _viewer_de(self, evento: ViewerEvent):
        return self.registry.registrar_viewer(
            platform=evento.platform,
            platform_user_id=evento.viewer_id,
            display_name_bruto=evento.viewer_name,
        )

    def _resolver_alvo(self, viewer, argumentos: tuple[str, ...]):
        """Slot explicito vence; sem argumento, tenta o lutador do espectador."""
        for argumento in argumentos:
            alvo = effects.resolver_alvo(self.simulador, argumento)
            if alvo is not None:
                return alvo
        if argumentos:
            return None

        fighter = self.registry.obter_lutador_ativo(viewer.viewer_id)
        if fighter is None:
            return None
        for slot in ("p1", "p2"):
            lutador = effects.resolver_alvo(self.simulador, slot)
            nome = getattr(getattr(lutador, "dados", None), "nome", None)
            if nome == fighter.catalog_name:
                return lutador
        return None

    def _payload_valido(self, command_id: str, argumentos: tuple[str, ...]) -> str | None:
        dados = get_command(command_id)
        arenas = dados.get("arenas")
        if not arenas:
            return " ".join(argumentos)
        if not argumentos:
            return None
        pedido = " ".join(argumentos).strip().casefold()
        for arena in arenas:
            if arena.casefold() == pedido:
                return arena
        return None

    def _round_ativo(self) -> bool:
        if self.simulador is None:
            return False
        return not getattr(self.simulador, "round_finalizado", False)

    def _estado_mundo(self) -> dict[str, int]:
        if self.simulador is None:
            return {}
        return {"areas": effects.contar_areas_vivas(self.simulador)}

    def _anotar(self, evento: ViewerEvent, resultado: ResultadoComando) -> None:
        try:
            self.registry.atualizar_status_evento(
                evento.event_id,
                resultado.status,
                f"{resultado.command_id} {resultado.detalhe}".strip(),
            )
        except Exception:
            # Falhar ao anotar o journal nunca pode derrubar a transmissao.
            logger.exception("falha ao anotar status de %s", evento.event_id)


def criar_handler(registry: LiveRegistry, simulador=None, ao_aplicar=None, **opcoes):
    """Adapta o roteador a assinatura que ``LiveSession`` espera.

    ``ao_aplicar(resultado, evento)`` (Passe 3): o ResultadoComando
    completo era reduzido a bool e jogado fora — o overlay de broadcast
    precisa dele para o lower-third ("Fulano usou !meteoro") e para o
    feedback de recusa. O callback NUNCA derruba o frame.
    """
    router = CommandRouter(registry, simulador=simulador, **opcoes)

    def aplicar(sessao, evento: ViewerEvent) -> bool:
        if router.simulador is None:
            router.simulador = getattr(sessao, "sim", None)
        resultado = router.processar(evento)
        if ao_aplicar is not None:
            try:
                ao_aplicar(resultado, evento)
            except Exception:
                logger.exception("callback de overlay falhou")
        return bool(resultado)

    aplicar.router = router
    return aplicar


def criar_preparador(router: CommandRouter):
    """Monta o plano da proxima partida a partir do que foi comprado.

    Roda no unico instante em que alterar o match config tem efeito: entre o
    fim de um round e o ``recarregar_tudo()`` do proximo. Zerar os contadores
    por partida acontece aqui pelo mesmo motivo -- e o limite real do round.
    """

    def preparar(_sessao) -> dict:
        router.novo_round()
        plano: dict[str, object] = {}
        # Passe 3 (arte): o motor luta com catalog_name ("@<id>"); a TELA
        # mostra o display_name sanitizado — todo o identity.py existia
        # para isso e nunca chegava ao HUD.
        try:
            plano["nomes_exibicao"] = router.registry.mapa_nomes_exibicao()
        except Exception:
            logger.exception("mapa de nomes de exibicao indisponivel")
        for item in router.registry.consumir_fila_do_round():
            dados = get_command(item["command_id"]) if item["command_id"] else {}
            if dados.get("efeito") == "TROCAR_ARENA" and item["payload"]:
                # Ultimo da fila vence: quem comprou depois teve a palavra final.
                plano["cenario"] = item["payload"]
        return plano

    return preparar


__all__ = [
    "COMANDO_ENTRAR",
    "PREFIXO_COMANDO",
    "STATUS_ADIADO",
    "STATUS_APLICADO",
    "STATUS_DUPLICADO",
    "STATUS_ERRO",
    "STATUS_IGNORADO",
    "STATUS_RECUSADO",
    "CommandRouter",
    "ResultadoComando",
    "criar_handler",
    "extrair_comando",
]
