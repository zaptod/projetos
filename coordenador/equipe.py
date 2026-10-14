# -*- coding: utf-8 -*-
"""Gerente da equipe: so cuida das permissoes dos trabalhadores.

Contratar e trabalho exclusivo do passo da Mesa (`pedidos.MesaPedidos.passo`)
e a conferencia e a prova automatica do vigia (decisao de 07/10). COO-20
(auditoria 11/10): `_contratar` e `_conferir_aplicadas` eram codigo morto e sairam.
"""
from __future__ import annotations

from datetime import datetime
from remoto import delegar, orquestrador

INTERVALO_S = 60


def _agora():
    return datetime.now()


class GerenteEquipe:
    """Passada pequena, injetavel nos testes e chamada no pulso do coordenador."""
    def __init__(self, *, mesa=orquestrador, despachante=delegar, avisar=print,
                 evento=lambda _tipo, _texto: None, relogio=_agora):
        self.mesa, self.despachante = mesa, despachante
        self.avisar, self.evento, self.relogio = avisar, evento, relogio
        self.ultimo = None
        self.estado = {"conferidos": {}, "voltas": {}, "permissoes": {}}

    def _pode_passar(self):
        agora = self.relogio()
        if self.ultimo and (agora - self.ultimo).total_seconds() < INTERVALO_S:
            return False
        self.ultimo = agora
        return bool(self.despachante.ler_config().get("gerente_ligado", False))

    def _fila_pausada(self):
        """O "Pausar a fila" do app (04/10: o servidor aplica o comando na
        hora) vale aqui: pausada, ninguem e contratado da fila. Config
        ilegivel tambem nao contrata (falha fechado)."""
        ler = getattr(self.mesa, "ler_config", None)
        if ler is None:
            return False
        try:
            return bool(ler().get("fila_pausada"))
        except Exception:                                    # noqa: BLE001
            return True

    def _permissoes_pendentes(self, ligado: bool):
        """O gerente so executa a regra automatica quando esta ligado.

        Desligado, o mesmo pedido continua visivel para o Adrian em vez de
        morrer por falta de um gerente residente.

        Conferente 3 (05/10/2026): o aviso era deduplicado pelo id do
        TRABALHADOR para sempre; a segunda permissao do mesmo trabalhador (o
        pedido-cb44cd52-1 ja tinha pedido caminho_protegido) nao avisava. Agora
        a chave e o pedido de permissao (categoria, alvo, hora), e o que deixou
        de estar pendente sai da memoria.
        """
        pendentes = set()
        for trabalhador in self.despachante.listar():
            if trabalhador.get("situacao") != "aguardando_permissao":
                continue
            pedido = trabalhador.get("pedido_permissao") or {}
            ident = str(trabalhador.get("id") or "")
            categoria = str(pedido.get("categoria") or "")
            chave = "|".join([ident, categoria, str(pedido.get("alvo") or ""),
                              str(pedido.get("em") or ""), str(pedido.get("o_que") or "")])
            pendentes.add(chave)
            regra = self.despachante.regra_de_permissao(trabalhador.get("cargo", ""), categoria,
                                                        pedido.get("alvo", ""))
            if categoria == "estado_do_servidor" and regra == "gerente_aceita":
                # 05/10/2026 (v2): o estado do servidor nunca anda sozinho; o
                # `regra_de_permissao` ja garante, e aqui o gerente nao confia
                regra = "perguntar_ao_adrian"
            if categoria == "conta" or regra == "negar":
                self.despachante.decidir_permissao(ident, False)
                self.avisar(f"❌ permissao negada para {ident}: {pedido.get('o_que')}")
                continue
            if regra == "gerente_aceita" and ligado:
                self.despachante.decidir_permissao(ident, True)
                self.despachante.no_fundo(["retomar", "--id", ident], ident)
                self.evento("equipe_permissao", f"permissao aceita; retomei {ident}")
                continue
            if chave not in self.estado["permissoes"]:
                self.estado["permissoes"][chave] = pedido
                if not pedido.get("avisado"):
                    # o coordenador ja avisou as que ele pediu (com o id do pedido)
                    self.avisar(f"❓ permissao de {ident}: {pedido.get('o_que')} — "
                                f"{pedido.get('por_que')}")
                self.evento("equipe_permissao", f"permissao espera Adrian: {ident}")
        for chave in [c for c in self.estado["permissoes"] if c not in pendentes]:
            del self.estado["permissoes"][chave]

    def passo(self):
        if not self._pode_passar():
            # Mesmo desligado, a fila de perguntas nao depende do gerente.
            self._permissoes_pendentes(False)
            return {"ligado": False, **self.estado}
        ativos = [t for t in self.despachante.listar() if t.get("situacao") == "rodando"]
        # b3: fila e conferencia ja sao pedidos. O gerente so cuida de
        # permissoes; contratar e trabalho exclusivo do passo da Mesa.
        self._permissoes_pendentes(True)
        return {"ligado": True, "ativos": len(ativos), **self.estado}
