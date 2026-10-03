# -*- coding: utf-8 -*-
"""Gerente soberano da equipe descartavel.

Ele nao conversa com trabalhadores: cria uma worktree, dispara uma sessao e
deixa o vigia aplicar. Assim app e VS Code continuam clientes do servidor.
"""
from __future__ import annotations

import re
from datetime import datetime
from remoto import delegar, orquestrador

INTERVALO_S = 60


def _agora():
    return datetime.now()


def _id(item_id: str) -> str:
    texto = re.sub(r"[^a-z0-9-]", "-", str(item_id).lower()).strip("-")
    return ("mesa-" + texto)[:40].rstrip("-") or "mesa-tarefa"


def _tipo(texto: str) -> str:
    texto = texto.lower()
    for nome in ("conferir", "consertar", "investigar", "implementar", "construir"):
        if nome in texto:
            return nome
    return "construir"


class GerenteEquipe:
    """Passada pequena, injetavel nos testes e chamada no pulso do coordenador."""
    def __init__(self, *, mesa=orquestrador, despachante=delegar, avisar=print,
                 evento=lambda _tipo, _texto: None, relogio=_agora):
        self.mesa, self.despachante = mesa, despachante
        self.avisar, self.evento, self.relogio = avisar, evento, relogio
        self.ultimo = None
        self.estado = {"conferidos": {}, "voltas": {}}

    def _pode_passar(self):
        agora = self.relogio()
        if self.ultimo and (agora - self.ultimo).total_seconds() < INTERVALO_S:
            return False
        self.ultimo = agora
        return bool(self.despachante.ler_config().get("gerente_ligado", False))

    def _contratar(self, item):
        tarefa_id = _id(item.get("id"))
        if any(t.get("id") == tarefa_id for t in self.despachante.listar()):
            return
        titulo = str(item.get("item") or item.get("titulo") or "")
        cargo = str(item.get("parte") or "integrador").lower()
        if cargo not in self.despachante.cargos():
            cargo = "integrador"
        regra = self.despachante.ler_config().get("regra_ia") or {}
        ia = regra.get(_tipo(titulo), "codex")
        pasta = self.despachante.pasta() / tarefa_id
        pasta.mkdir(parents=True, exist_ok=True)
        pedido = pasta / "pedido.md"
        pedido.write_text(titulo, encoding="utf-8")
        estado = self.despachante.criar(tarefa_id, pedido, ["remoto/**", "coordenador/**", "docs/**"],
                                        ia=ia, cargo=cargo, titulo=titulo)
        self.despachante.no_fundo(["rodar", "--id", tarefa_id], tarefa_id)
        self.evento("equipe_contratou", f"{estado['ia']} {cargo}: {titulo}")

    def _conferir_aplicadas(self):
        for trabalhador in self.despachante.listar():
            ident = trabalhador.get("id")
            if not ident or not trabalhador.get("aplicado") or ident in self.estado["conferidos"]:
                continue
            conferencia = _id("conf-" + ident)
            if not any(t.get("id") == conferencia for t in self.despachante.listar()):
                pasta = self.despachante.pasta() / conferencia
                pasta.mkdir(parents=True, exist_ok=True)
                pedido = pasta / "pedido.md"
                pedido.write_text("Confira a entrega aplicada " + ident + ". Devolva APROVADO ou DEFEITOS em resposta.md.",
                                  encoding="utf-8")
                self.despachante.criar(conferencia, pedido, ["remoto/**", "coordenador/**", "docs/**"],
                                       ia="claude", cargo="conferente", titulo="Conferir " + ident)
                self.despachante.no_fundo(["rodar", "--id", conferencia], conferencia)
            self.estado["conferidos"][ident] = conferencia
            self.evento("equipe_conferencia", f"conferente para {ident}")

    def passo(self):
        if not self._pode_passar():
            return {"ligado": False, **self.estado}
        estado_mesa = self.mesa.ler_estado()
        ativos = [t for t in self.despachante.listar() if t.get("situacao") == "rodando"]
        limite = max(1, int(self.despachante.ler_config().get("delegados_paralelo", 1)))
        if len(ativos) < limite:
            for item in estado_mesa.get("fila") or []:
                self._contratar(item)
                break
        self._conferir_aplicadas()
        return {"ligado": True, "ativos": len(ativos), **self.estado}
