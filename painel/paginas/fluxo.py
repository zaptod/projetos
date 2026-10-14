# -*- coding: utf-8 -*-
"""Pagina FLUXO: onde cada build esta e o que destrava ela.

Toda a regra de estado mora em `builds.pipeline.fluxo` — esta pagina so
desenha. Os numeros de cima vem do `panorama`, o mesmo dicionario que a Vila
e o bot do Telegram leem: tres telas mostrando o mesmo numero e uma delas
errada era o que acontecia antes.
"""
from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path

from builds.pipeline import fluxo as regra

from .. import estilo

RAIZ = Path(__file__).resolve().parents[2]
RANDOM_BUILDS = RAIZ / "random_builds"

SIMBOLO = {"ok": "✓", "rodando": "▶", "fila": "…", "falhou": "✕",
           "ausente": "·"}


class Pagina:
    chave = "fluxo"
    rotulo = "Fluxo"
    icone = "🧭"

    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema
        self._por_id: dict = {}

    # ------------------------------------------------------------ montar
    def construir(self, pai) -> None:
        self.o.titulo(pai, "Fluxo da pipeline — o que já saiu e o que falta")

        cartoes = tk.Frame(pai, bg=self.t.fundo)
        cartoes.pack(fill="x", padx=estilo.ESPACO["secao"])
        self._cartoes = {}
        for chave, titulo in (("fila", "FILA DE IDENTIDADE"),
                              ("torneio", "PREPARAÇÃO DO TORNEIO"),
                              ("arena", "ARENA")):
            cartao = self.o.cartao(cartoes, titulo)
            cartao.pack(side="left", fill="both", expand=True,
                        padx=(0, estilo.ESPACO["meio"]))
            self._cartoes[chave] = self.o.rotulo(
                cartao.corpo, "—", cor="texto_fraco", bg=self.t.superficie,
                justify="left")
            self._cartoes[chave].pack(anchor="w")

        self._alerta = self.o.rotulo(pai, "", cor="aviso", peso="bold")
        self._alerta.pack(anchor="w", padx=estilo.ESPACO["secao"],
                          pady=(estilo.ESPACO["normal"], 0))
        # Rotulo PROPRIO para o erro de leitura da tabela: dividindo o
        # `_alerta`, o pulso de 4 s o apagava e deixava a cor vermelha no
        # alerta seguinte (PNL-16). So entra na tela quando ha erro.
        self._erro_leitura = self.o.rotulo(pai, "", cor="erro", peso="bold")
        self._erro_leitura_pack = dict(anchor="w", padx=estilo.ESPACO["secao"],
                                       after=self._alerta)

        topo = tk.Frame(pai, bg=self.t.fundo)
        topo.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=(estilo.ESPACO["normal"], estilo.ESPACO["meio"]))
        self.o.secao(topo, "Builds").pack(side="left")
        self.o.legenda(topo, "duplo-clique abre a pasta").pack(
            side="left", padx=estilo.ESPACO["meio"])
        self.o.botao(topo, "↻  Atualizar", self.recarregar).pack(side="right")

        # ids DISTINTOS: `regra.ETAPAS` ja tem "build" e "personagem", e
        # repetir esses nomes deixava duas colunas sem titulo e com 200px de
        # largura padrao. `Oficina.tabela` recusa repetido agora.
        colunas = [("id", "GERAÇÃO", 116, "w"), ("nome", "PERSONAGEM", 142, "w")]
        colunas += [(chave, regra.CURTOS.get(chave, chave.upper())[:8], 58,
                     "center") for chave, _r, _s in regra.ETAPAS]
        colunas += [(f"ret_{chave}", rotulo, 46, "center")
                    for chave, rotulo in regra.RETENCAO]
        colunas += [("dur", "DUR", 50, "center"),
                    ("passo", "PRÓXIMO PASSO", 240, "w")]
        self.tabela = self.o.tabela(pai, colunas, altura=11)
        self.tabela.pack(fill="both", expand=True,
                         padx=estilo.ESPACO["secao"])
        self.tabela.tag_configure("completa", foreground=self.t.ok)
        self.tabela.tag_configure("andando", foreground=self.t.aviso)
        self.tabela.tag_configure("parada", foreground=self.t.erro)
        self.tabela.tag_configure("neutra", foreground=self.t.texto)
        self.tabela.bind("<Double-1>", lambda _e: self.acao("pasta"))

        acoes = tk.Frame(pai, bg=self.t.fundo)
        acoes.pack(fill="x", padx=estilo.ESPACO["secao"],
                   pady=estilo.ESPACO["normal"])
        for texto, alvo in (("▶  Assistir", "assistir"),
                            ("📁  Pasta", "pasta"),
                            ("🔁  Re-renderizar", "rerender"),
                            ("🧩  Enfileirar identidade", "identidade")):
            self.o.botao(acoes, texto, lambda a=alvo: self.acao(a)).pack(
                side="left", padx=(0, estilo.ESPACO["meio"]))
        self.o.botao(acoes, "⬇  Processar fila", self.processar_fila,
                     tipo="primario").pack(side="right")

        self.o.legenda(
            pai, "✓ pronto    ▶ gerando agora    … na fila    "
                 "✕ falhou    · não começou").pack(
            anchor="w", padx=estilo.ESPACO["secao"],
            pady=(0, estilo.ESPACO["normal"]))

    # ------------------------------------------------------------ dados
    def ao_mostrar(self) -> None:
        self.recarregar()

    def recarregar(self) -> None:
        self.casca.supervisor.tarefa(
            lambda: regra.snapshot(limite=14), self._desenhar_tabela,
            rotulo="fluxo")

    def ilegivel(self, erro: str) -> None:
        """O panorama inteiro nao veio: os cartoes dizem, em vez de zerar."""
        for cartao in self._cartoes.values():
            cartao.configure(text=f"não consegui ler:\n{erro}"[:90],
                             fg=self.t.erro)
        self._alerta.configure(text="", fg=self.t.aviso)

    def atualizar(self, resumo: dict) -> None:
        """Os cartoes de cima vem do agregador, nao de leitura propria.

        Familia que falhou (`{"erro": ...}`) ou faltou diz "não consegui
        ler" no cartao dela, em vez de "0 na fila" (PNL-3).
        """
        if not isinstance(resumo, dict) or resumo.get("erro"):
            self.ilegivel((resumo or {}).get("erro", "?")
                          if isinstance(resumo, dict) else "?")
            return

        def familia(nome):
            valor = resumo.get(nome)
            if not isinstance(valor, dict):
                return {}, "não veio"
            if valor.get("erro"):
                return {}, str(valor["erro"])
            return valor, None

        saude, erro_saude = familia("saude")
        inventario, erro_inv = familia("inventario")
        qualidade, erro_qual = familia("qualidade")

        def pintar(chave, erro, texto):
            if erro:
                self._cartoes[chave].configure(
                    text=f"não consegui ler:\n{erro}"[:90], fg=self.t.erro)
            else:
                self._cartoes[chave].configure(text=texto,
                                               fg=self.t.texto_fraco)

        fila = saude.get("fila") or {}
        pintar("fila", erro_saude,
               f"{fila.get('pending', 0)} na fila · "
               f"{fila.get('running', 0)} gerando · "
               f"{fila.get('failed', 0)} com falha\n"
               f"{len(saude.get('trabalhando') or [])} fábrica(s) "
               "trabalhando agora")

        chaves = inventario.get("chaves") or {}
        banco = inventario.get("banco") or {}
        pintar("torneio", erro_inv,
               f"{chaves.get('prontos', '—')} build(s) com vídeo pronto\n"
               f"banco: {banco.get('personagens', '—')} personagens, "
               f"{banco.get('armas', '—')} armas")

        ledger = qualidade.get("ledger") or {}
        arena = inventario.get("arena") or {}
        pintar("arena", erro_inv or erro_qual,
               f"{arena.get('lutas', '—')} luta(s) registradas\n"
               f"campeão: {ledger.get('campeao') or '—'}")

        alertas = saude.get("alertas") or []
        # A cor volta SEMPRE para a do alerta: o erro de leitura tem rotulo
        # proprio e nao pode tingir o alerta seguinte.
        self._alerta.configure(
            text=("⚠  " + alertas[0]) if alertas else "", fg=self.t.aviso)

    def _desenhar_tabela(self, dados: dict) -> None:
        if not isinstance(dados, dict) or dados.get("erro"):
            self._erro_leitura.configure(
                text=f"não consegui ler o fluxo: "
                     f"{(dados or {}).get('erro', '?') if isinstance(dados, dict) else '?'}")
            self._erro_leitura.pack(**self._erro_leitura_pack)
            return
        self._erro_leitura.configure(text="")
        self._erro_leitura.pack_forget()
        geracoes = dados.get("geracoes") or []
        self._por_id = {g["generation_id"]: g for g in geracoes}

        escolhido = self.tabela.selection()
        self.tabela.delete(*self.tabela.get_children())
        for geracao in geracoes:
            estados = [geracao["etapas"][c]["estado"]
                       for c, _r, _s in regra.ETAPAS]
            simbolos = [SIMBOLO.get(e, "?") for e in estados]
            retencao = geracao.get("retencao") or {}
            extras = ["✓" if retencao.get(c) else "·"
                      for c, _r in regra.RETENCAO]
            duracao = (f"{retencao['duracao']:.0f}s"
                       if retencao.get("duracao") else "")
            if geracao.get("completa"):
                marca = "completa"
            elif "falhou" in estados:
                marca = "parada"
            elif "rodando" in estados or "fila" in estados:
                marca = "andando"
            else:
                marca = "neutra"
            self.tabela.insert(
                "", "end", iid=geracao["generation_id"],
                values=[geracao["generation_id"],
                        geracao.get("personagem") or ""]
                + simbolos + extras
                + [duracao, geracao.get("proximo_passo", "")],
                tags=(marca,))
        # Manter a selecao: sem isto a lista "pula" a cada atualizacao e o
        # dono perde a linha que estava olhando.
        for iid in escolhido:
            if self.tabela.exists(iid):
                self.tabela.selection_set(iid)

    # ------------------------------------------------------------ acoes
    def acao(self, qual: str) -> None:
        iid = self.o.selecionado(self.tabela, "Escolha uma build na tabela.")
        if iid is None:
            return
        pasta = RANDOM_BUILDS / "outputs" / iid
        if qual == "pasta":
            if pasta.is_dir():
                os.startfile(pasta)                          # noqa: S606
            return
        if qual == "assistir":
            for nome in ("final_celular.mp4", "final_normal.mp4"):
                if (pasta / nome).is_file():
                    os.startfile(pasta / nome)               # noqa: S606
                    return
            self.casca._registrar(f"{iid}: nenhum vídeo final ainda.", "erro")
            return
        comandos = {
            "rerender": ["main.py", "generate-video", "--rerender", iid],
            "identidade": ["main.py", "identity", "run", iid],
        }
        self.casca.supervisor.rodar(
            [self._python(), "-u", "-X", "utf8"] + comandos[qual],
            cwd=RANDOM_BUILDS, rotulo=f"{qual} {iid}", depois=self.recarregar)

    def processar_fila(self) -> None:
        self.casca.supervisor.rodar(
            [self._python(), "-u", "-X", "utf8", "main.py", "identity",
             "worker"], cwd=RANDOM_BUILDS, rotulo="worker de identidade",
            depois=self.recarregar)

    @staticmethod
    def _python() -> str:
        import sys
        return sys.executable


__all__ = ["Pagina"]
