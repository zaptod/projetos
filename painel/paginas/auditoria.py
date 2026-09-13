# -*- coding: utf-8 -*-
"""Pagina AUDITORIA: os quatro controles, e o que a grade vai barrar.

Toda a regra mora em `panorama.auditoria` — esta pagina so desenha. E a mesma
doutrina do Fluxo, e aqui ela importa mais: a coluna de qualidade tem de ser
a MESMA decisao que o `postar.py` toma no horario. Uma tela que calcula por
conta propria vira uma segunda opiniao, e duas opinioes sobre "pode publicar?"
e nenhuma.

O que a tela precisa deixar obvio, porque e onde o dia se perde:

    BARRADO     video pronto que NAO vai sair, e por que
    FALTANDO    horario que ja venceu e nao teve publicacao
    TRAVADO     historia que parou no meio da fabrica
    FALTA       disco, credencial, conta, freio de mao

A vistoria decodifica cada mp4, entao ela NAO roda no pulso de 4 s do painel:
roda ao abrir a pagina e no botao. O carimbo de hora no topo existe para
ninguem olhar numero velho achando que e de agora.
"""
from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path

from .. import estilo

RAIZ = Path(__file__).resolve().parents[2]
HISTORIAS = RAIZ / "historias"

CORES = {"ok": "ok", "aviso": "aviso", "erro": "erro"}


class Pagina:
    chave = "auditoria"
    rotulo = "Auditoria"
    icone = "🛡"

    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema
        self._dados: dict = {}

    # ------------------------------------------------------------ montar
    def construir(self, pai) -> None:
        self.o.titulo(pai, "Auditoria — o que vai sair, e o que não vai")

        self.faixa = self.o.rotulo(pai, "lendo…", papel="secao", peso="bold")
        self.faixa.pack(anchor="w", padx=estilo.ESPACO["secao"])
        self.carimbo = self.o.legenda(pai, "")
        self.carimbo.pack(anchor="w", padx=estilo.ESPACO["secao"])

        cartoes = tk.Frame(pai, bg=self.t.fundo)
        cartoes.pack(fill="x", padx=estilo.ESPACO["secao"],
                     pady=(estilo.ESPACO["normal"], 0))
        self._cartoes = {}
        for chave, titulo in (("qualidade", "QUALIDADE"),
                              ("metas", "METAS"),
                              ("producao", "PRODUÇÃO"),
                              ("recursos", "RECURSOS")):
            cartao = self.o.cartao(cartoes, titulo)
            cartao.pack(side="left", fill="both", expand=True,
                        padx=(0, estilo.ESPACO["meio"]))
            self._cartoes[chave] = self.o.rotulo(
                cartao.corpo, "—", cor="texto_fraco", bg=self.t.superficie,
                justify="left")
            self._cartoes[chave].pack(anchor="w")

        self.o.secao(pai, "Fila — na ordem em que a grade vai pegar").pack(
            anchor="w", padx=estilo.ESPACO["secao"],
            pady=(estilo.ESPACO["normal"], estilo.ESPACO["pouco"]))
        colunas = [("marca", "", 44, "center"),
                   ("id", "VÍDEO", 250, "w"),
                   ("titulo", "TÍTULO", 300, "w"),
                   ("capa", "CAPA", 56, "center"),
                   ("motivo", "O QUE IMPEDE", 420, "w")]
        self.tabela = self.o.tabela(pai, colunas, altura=8, estica="motivo")
        self.tabela.pack(fill="both", expand=True,
                         padx=estilo.ESPACO["secao"])
        self.tabela.tag_configure("liberado", foreground=self.t.ok)
        self.tabela.tag_configure("barrado", foreground=self.t.erro)

        acoes = tk.Frame(pai, bg=self.t.fundo)
        acoes.pack(fill="x", padx=estilo.ESPACO["secao"],
                   pady=estilo.ESPACO["normal"])
        self.o.botao(acoes, "↻  Auditar de novo", self.recarregar,
                     tipo="primario").pack(side="left")
        for texto, alvo in (("🔁  Re-renderizar", "render"),
                            ("🖼  Refazer imagens", "imagens"),
                            ("📁  Pasta", "pasta")):
            self.o.botao(acoes, texto, lambda a=alvo: self.acao(a)).pack(
                side="left", padx=(estilo.ESPACO["meio"], 0))
        self.o.botao(acoes, "🌐  Conferir contas e tarefas",
                     self.com_rede).pack(side="right")

    # -------------------------------------------------------------- dados
    def ao_mostrar(self) -> None:
        self.recarregar()

    def atualizar(self, resumo: dict) -> None:
        """Nada daqui vem do pulso: a vistoria decodifica mp4, e fazer isso a
        cada 4 s com a pagina aberta deixaria a maquina inutil."""

    def recarregar(self) -> None:
        self._pedir(com_rede=False)

    def com_rede(self) -> None:
        """O Agendador e o OAuth de verdade — subprocesso e rede."""
        self._pedir(com_rede=True)

    def _pedir(self, *, com_rede: bool) -> None:
        self.faixa.configure(text="auditando…", fg=self.t.texto_fraco)
        self.casca.supervisor.tarefa(
            lambda: _auditar(com_rede), self._desenhar, rotulo="auditoria")

    def _desenhar(self, dados: dict) -> None:
        if not isinstance(dados, dict) or dados.get("erro"):
            self.faixa.configure(
                text=f"não consegui auditar: {(dados or {}).get('erro', '?')}",
                fg=self.t.erro)
            return
        self._dados = dados
        veredito = dados.get("veredito") or {}
        self.faixa.configure(text=veredito.get("frase", "—"),
                             fg=getattr(self.t,
                                        CORES.get(veredito.get("cor"), "texto")))
        self.carimbo.configure(
            text=f"auditado às {str(dados.get('quando'))[11:19]}"
                 + ("  ·  com contas e tarefas" if dados.get("com_rede")
                    else "  ·  sem rede (use o botão à direita)"))

        qual = dados.get("qualidade") or {}
        self._cartoes["qualidade"].configure(
            text=f"{qual.get('liberados', 0)} liberado(s)\n"
                 f"{qual.get('barrados', 0)} barrado(s)\n"
                 f"{qual.get('pendentes', 0)} na fila")

        alvo = dados.get("metas") or {}
        canais = alvo.get("canais") or {}
        linhas = [f"{alvo.get('horarios_vencidos', 0)}/"
                  f"{alvo.get('horarios_do_dia', 0)} horários hoje"]
        for canal, ficha in canais.items():
            pior = min((p.get("saiu", 0) for p in ficha.values()), default=0)
            linhas.append(f"{canal}: {pior}/{alvo.get('horarios_vencidos', 0)}")
        linhas.append(f"próximo {alvo.get('proximo', '—')}")
        self._cartoes["metas"].configure(text="\n".join(linhas))

        prod = dados.get("producao") or {}
        travadas = prod.get("historias_incompletas")
        quantas = len(travadas) if isinstance(travadas, list) else "?"
        # `videos_prontos`, e nao `chaves.prontos`: o segundo conta BUILDS
        # prontas para virar chave do torneio, que e outra coisa — e mostrava
        # "1 build com video" num dia com 231 videos no disco.
        pronto = (prod.get("estoque") or {}).get("videos_prontos") or {}
        self._cartoes["producao"].configure(
            text=f"{quantas} história(s) incompleta(s)\n"
                 f"{pronto.get('historias', '—')} vídeo(s) de história\n"
                 f"{pronto.get('builds', '—')} vídeo(s) de build")

        rec = dados.get("recursos") or {}
        disco = rec.get("disco") or {}
        alertas = rec.get("alertas") or []
        self._cartoes["recursos"].configure(
            text=f"disco {disco.get('livre_gb', '—')} GB\n"
                 f"{(rec.get('freio') or {}).get('situacao', '—')}\n"
                 + (f"⚠ {len(alertas)} alerta(s)" if alertas else "sem alerta"))

        escolhido = self.tabela.selection()
        self.tabela.delete(*self.tabela.get_children())
        for item in qual.get("fila") or []:
            motivo = "; ".join(item.get("erros") or []) or \
                "; ".join(item.get("avisos") or [])
            self.tabela.insert(
                "", "end", iid=item["id"],
                values=["✓" if item.get("ok") else "✕", item["id"],
                        item.get("titulo", "")[:70],
                        "✓" if item.get("capa") else "·", motivo[:200]],
                tags=("liberado" if item.get("ok") else "barrado",))
        for iid in escolhido:
            if self.tabela.exists(iid):
                self.tabela.selection_set(iid)

    # -------------------------------------------------------------- acoes
    def acao(self, qual: str) -> None:
        iid = self.o.selecionado(self.tabela, "Escolha um vídeo na fila.")
        if iid is None:
            return
        historia = str(iid).split(":")[0]
        if qual == "pasta":
            pasta = HISTORIAS / "outputs" / historia
            if pasta.is_dir():
                os.startfile(pasta)                            # noqa: S606
            return
        import sys
        comandos = {"render": ["main.py", "video", historia],
                    "imagens": ["main.py", "imagens", historia]}
        self.casca.supervisor.rodar(
            [sys.executable, "-u", "-X", "utf8"] + comandos[qual],
            cwd=HISTORIAS, rotulo=f"{qual} {historia}",
            depois=self.recarregar)


def _auditar(com_rede: bool) -> dict:
    """Fora da interface: a vistoria decodifica video e demora segundos."""
    try:
        from panorama import auditoria
        dados = auditoria.completa(com_rede=com_rede)
        dados["veredito"] = auditoria.veredito(dados)
        dados["com_rede"] = com_rede
        return dados
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}


__all__ = ["Pagina"]
