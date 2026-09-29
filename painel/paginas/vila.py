# -*- coding: utf-8 -*-
"""Pagina VILA: o hub -- o placar, as outras janelas e o que esta
acontecendo AGORA (o diario e o paralelismo).

E o painel principal por escolha dele, com a cara quente.

O MAPA EM PIXEL SAIU (28/09/2026). Decisao do Adrian
(`painel-e-vila/aposentar-vila-pixel` = "aposentar"): a Vila em pixel art
(`vila/`, o motor e a Oficina dela) foi tirada do painel e do codigo; o
historico fica no git. A Vila que vive e a FOFA, na janela flutuante e no
celular. O que o mapa fazia e ainda serve ficou: o placar, o filtro do
diario (agora numa caixa, em vez de clicar no predio) e o botao da Oficina
-- que abre a Oficina de SPRITES, a ferramenta de limpar folhas do ChatGPT
para o palco, na janela dela.

O QUE MUDOU EM RELACAO A VERSAO ANTIGA, e nao e enfeite:

  A VILA MENTIA. `publicar/tiktok.py` e `publicar/youtube_web.py` nao
  escreviam no diario, entao a fabrica "publicacao" ficava OCIOSA durante
  quase todo upload real. Corrigido na etapa 2; aqui a consequencia aparece.

  O PLACAR ERA CONTAGEM DE LINHA. "32 publicados" saia de contar as linhas
  de dois arquivos, o que conta tambem o que falhou. Agora vem do
  `panorama`, o MESMO dicionario que as outras telas leem.
"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from builds import atividade

from .. import estilo, janelas
from ..processos import Periodico

RAIZ = Path(__file__).resolve().parents[2]
PY = sys.executable

LEITURA_MS = 3500
TODAS = "todas as fábricas"


class Pagina:
    chave = "vila"
    rotulo = "Vila"
    icone = "🏘"

    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema
        self._filtro: str | None = None
        self._visivel = False
        self._leitura = None

    # ------------------------------------------------------------ montar
    def construir(self, pai) -> None:
        topo = tk.Frame(pai, bg=self.t.fundo)
        topo.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=(estilo.ESPACO["muito"], estilo.ESPACO["meio"]))
        self.lbl_placar = self.o.rotulo(topo, "…", papel="secao",
                                        peso="bold")
        self.lbl_placar.pack(side="left")
        self.o.botao(topo, "↻", self.recarregar, compacto=True).pack(
            side="right", padx=(estilo.ESPACO["pouco"], 0))
        self.o.botao(topo, "🤖  Bot do celular", self.bot).pack(side="right")

        # AS OUTRAS JANELAS, cada uma em processo proprio. Uma travar nao
        # derruba as outras -- e com Tkinter isso e mais que preferencia:
        # duas telas pesadas no mesmo processo disputam a mesma thread.
        abrir = tk.Frame(pai, bg=self.t.fundo)
        abrir.pack(fill="x", padx=estilo.ESPACO["secao"],
                   pady=(0, estilo.ESPACO["meio"]))
        for chave in ("criacao", "jogo", "oficina"):
            receita = janelas.JANELAS[chave]
            self.o.botao(
                abrir, f"{receita['icone']}  {receita['titulo'].split(' —')[0]}",
                lambda c=chave: self.abrir_janela(c),
                tipo="primario" if chave == "criacao" else "normal").pack(
                side="left", padx=(0, estilo.ESPACO["meio"]))
        self.o.botao(abrir, "🪟  Vila flutuante", self.flutuante).pack(
            side="left", padx=(0, estilo.ESPACO["meio"]))
        self.o.legenda(
            abrir, "cada uma abre numa janela própria — fechar uma não mexe "
                   "nas outras").pack(side="left",
                                      padx=estilo.ESPACO["meio"])

        # --- paralelismo antes do diario: o diario e quem estica
        self._paralelismo(pai)

        # --- diario
        rodape = tk.Frame(pai, bg=self.t.fundo)
        rodape.pack(fill="both", expand=True, padx=estilo.ESPACO["secao"],
                    pady=(0, estilo.ESPACO["normal"]))
        cabeca = tk.Frame(rodape, bg=self.t.fundo)
        cabeca.pack(fill="x")
        self.lbl_filtro = self.o.secao(cabeca, "Diário")
        self.lbl_filtro.pack(side="left")
        self._rotulos_fabrica = {
            info.get("rotulo", chave): chave
            for chave, info in atividade.FABRICAS.items()}
        self.cmb_filtro = self.o.combo(
            cabeca, [TODAS] + list(self._rotulos_fabrica), TODAS, largura=16)
        self.cmb_filtro.pack(side="right")
        self.cmb_filtro.bind("<<ComboboxSelected>>",
                             lambda _e: self._escolheu_filtro())
        self.o.legenda(cabeca, "filtrar por fábrica").pack(
            side="right", padx=estilo.ESPACO["meio"])
        self.texto = tk.Text(rodape, height=6, bg=self.t.console_fundo,
                             fg=self.t.console_texto, font=self.t.letra("mono"),
                             relief="flat", bd=0, state="disabled",
                             wrap="none", padx=estilo.ESPACO["meio"],
                             pady=estilo.ESPACO["pouco"])
        self.texto.pack(fill="both", expand=True,
                        pady=(estilo.ESPACO["meio"], 0))
        for marca, cor in (("erro", self.t.erro), ("ok", self.t.ok),
                           ("inicio", self.t.aviso)):
            self.texto.tag_configure(marca, foreground=cor)

    def _paralelismo(self, pai) -> None:
        """Quem divide pasta com quem — a serializacao que ninguem ve.

        Uma trava usada por DOIS canais e um lugar onde o paralelismo
        prometido nao acontece. Isso e CONFIGURACAO, nao codigo: o valor de
        mostrar aqui e poder agir.
        """
        area = tk.Frame(pai, bg=self.t.fundo)
        area.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=(estilo.ESPACO["normal"], estilo.ESPACO["normal"]))
        cabeca = tk.Frame(area, bg=self.t.fundo)
        cabeca.pack(fill="x")
        self.o.secao(cabeca, "Paralelismo").pack(side="left")
        self.o.legenda(cabeca, "uma pasta de perfil = uma fila").pack(
            side="left", padx=estilo.ESPACO["meio"])
        self.lbl_paralelo = self.o.legenda(cabeca, "")
        self.lbl_paralelo.pack(side="right")
        self.tabela = self.o.tabela(area, [
            ("servico", "SERVIÇO", 110, "w"),
            ("canais", "USADA POR", 170, "w"),
            ("estado", "AGORA", 90, "w"),
            ("perfil", "PASTA DO PERFIL", 380, "w"),
        ], altura=4, estica="perfil")
        self.tabela.tag_configure("ocupada", foreground=self.t.aviso)
        self.tabela.tag_configure("dividida", foreground=self.t.erro)
        self.tabela.pack(fill="x", pady=(estilo.ESPACO["meio"], 0))

    # ------------------------------------------------------------ estado
    def ao_mostrar(self) -> None:
        self._visivel = True
        if self._leitura is None:
            self._leitura = Periodico(self.casca, LEITURA_MS, self.recarregar)
        self._leitura.ligar()
        self.recarregar()

    def ao_esconder(self) -> None:
        """Desliga a leitura DE VERDADE (o `Periodico` cancela o agendamento):
        ler o diario para uma pagina escondida custa disco e nada mais."""
        self._visivel = False
        if self._leitura is not None:
            self._leitura.desligar()

    def recarregar(self) -> None:
        self.casca.supervisor.tarefa(self._ler, self._aplicar, rotulo="vila")

    def _ler(self) -> dict:
        return {"eventos": atividade.recentes(40, self._filtro)}

    def _aplicar(self, dados: dict) -> None:
        if dados.get("erro"):
            return
        self._diario(dados.get("eventos") or [])

    def atualizar(self, resumo: dict) -> None:
        """O placar vem do agregador, e nao de contagem de linha de arquivo."""
        saude = resumo.get("saude") or {}
        desempenho = resumo.get("desempenho") or {}
        inventario = resumo.get("inventario") or {}
        qualidade = resumo.get("qualidade") or {}

        prontos = (inventario.get("videos_prontos") or {}).get("total", 0)
        trabalhando = len(saude.get("trabalhando") or [])
        problemas = qualidade.get("total_erros", 0)
        self.lbl_placar.configure(
            text=f"📤 {desempenho.get('total', 0)} publicados   ·   "
                 f"🎬 {prontos} prontos   ·   "
                 f"⚙ {trabalhando} trabalhando   ·   "
                 f"⚠ {problemas} problema(s)")

        paralelo = saude.get("paralelismo") or {}
        self.tabela.delete(*self.tabela.get_children())
        for linha in paralelo.get("travas") or []:
            canais = linha.get("canais") or []
            marca = ("dividida" if len(canais) > 1
                     else "ocupada" if linha.get("ocupada") else "")
            self.tabela.insert(
                "", "end",
                values=(linha.get("servico", ""), " + ".join(canais),
                        "em uso" if linha.get("ocupada") else "livre",
                        linha.get("perfil", "")),
                tags=(marca,) if marca else ())
        divididas = len(paralelo.get("divididas") or [])
        self.lbl_paralelo.configure(
            text=f"{paralelo.get('ocupadas', 0)} em uso · {divididas} pasta(s) "
                 "usada(s) por DOIS canais (essas não rodam juntas)",
            fg=self.t.erro if divididas else self.t.texto_fraco)

    def _diario(self, eventos: list) -> None:
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        for evento in eventos:
            hora = str(evento.get("ts", ""))[11:19]
            fabrica = atividade.FABRICAS.get(evento.get("fabrica"), {})
            rotulo = fabrica.get("rotulo", evento.get("fabrica", "?"))
            estado = evento.get("status", "")
            self.texto.insert(
                "end",
                f"{hora}  {rotulo:<11} {evento.get('canal', ''):<10} "
                f"{estado:<7} {evento.get('detalhe', '')}\n",
                estado if estado in ("erro", "ok", "inicio") else "")
        self.texto.configure(state="disabled")

    # ------------------------------------------------------------ acoes
    def _escolheu_filtro(self) -> None:
        escolha = self.cmb_filtro.get()
        if escolha == TODAS:
            self.sem_filtro()
        else:
            self.filtrar(self._rotulos_fabrica.get(escolha, escolha))

    def filtrar(self, fabrica: str) -> None:
        self._filtro = fabrica
        rotulo = atividade.FABRICAS.get(fabrica, {}).get("rotulo", fabrica)
        self.lbl_filtro.configure(text=f"DIÁRIO — {rotulo.upper()}")
        self.recarregar()

    def sem_filtro(self) -> None:
        self._filtro = None
        self.lbl_filtro.configure(text="DIÁRIO")
        self.cmb_filtro.set(TODAS)
        self.recarregar()

    def abrir_janela(self, chave: str) -> None:
        processo = janelas.abrir(chave)
        if processo is None:
            self.casca._registrar(f"[vila] não conheço a janela {chave}.",
                                  "erro")
            return
        nome = janelas.JANELAS[chave]["titulo"].split(" —")[0]
        self.casca._registrar(f"[vila] abri {nome} (processo "
                              f"{processo.pid}).", "fim")

    def flutuante(self) -> None:
        """A janela pequena, por cima de tudo, no lugar dos consoles."""
        try:
            processo = janelas.abrir_flutuante()
        except OSError as erro:
            self.casca._registrar(f"[vila] a flutuante não abriu: {erro}",
                                  "erro")
            return
        self.casca._registrar(f"[vila] abri a Vila flutuante (processo "
                              f"{processo.pid}).", "fim")

    def bot(self) -> None:
        self.casca.supervisor.rodar([PY, "-u", "-X", "utf8", "-m", "remoto"],
                                    cwd=RAIZ, rotulo="bot do Telegram")


__all__ = ["Pagina"]
