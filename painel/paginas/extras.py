# -*- coding: utf-8 -*-
"""As tres paginas que sobram: Torneio, Reacoes e Audio.

Juntas num arquivo por serem pequenas e do mesmo tipo -- formulario curto
mais uma lista. Um arquivo por pagina aqui daria tres arquivos de setenta
linhas com o mesmo cabecalho.
"""
from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from .. import estilo

RAIZ = Path(__file__).resolve().parents[2]
RANDOM_BUILDS = RAIZ / "random_builds"
PY = sys.executable


class _Base:
    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema

    def rb(self, argumentos: list, rotulo: str, depois=None) -> None:
        self.casca.supervisor.rodar([PY, "-u", "-X", "utf8"] + argumentos,
                                    cwd=RANDOM_BUILDS, rotulo=rotulo,
                                    depois=depois)

    def _linha(self, pai):
        linha = tk.Frame(pai, bg=pai.cget("bg"))
        linha.pack(anchor="w", pady=(estilo.ESPACO["meio"], 0))
        return linha


class Torneio(_Base):
    chave = "torneio"
    rotulo = "Torneio"
    icone = "🏆"

    def construir(self, pai) -> None:
        self.o.titulo(pai, "Torneio — mata-mata dos personagens vira vídeo")

        card = self.o.cartao(
            pai, "Novo torneio — lutas reais no motor, vídeo nos 2 formatos")
        card.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=estilo.ESPACO["meio"])
        linha = self._linha(card.corpo)
        self.o.rotulo(linha, "Quem luta:", cor="texto_fraco",
                      bg=self.t.superficie).pack(
            side="left", padx=(0, estilo.ESPACO["meio"]))
        self.combo_fonte = self.o.combo(linha, ["misto", "gerados", "banco"],
                                        "misto", largura=9)
        self.combo_fonte.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        self.o.rotulo(linha, "Participantes:", cor="texto_fraco",
                      bg=self.t.superficie).pack(
            side="left", padx=(0, estilo.ESPACO["meio"]))
        self.combo_quantos = self.o.combo(linha, ["4", "8", "16", "32"], "8",
                                          largura=5)
        self.combo_quantos.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        moldura, self.var_seed = self.o.campo(linha, "Seed:", 10)
        moldura.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        caixa, self.var_preview = self.o.marcador(linha, "Preview")
        caixa.pack(side="left")

        linha = self._linha(card.corpo)
        self.o.botao(linha, "🏆  RODAR TORNEIO", self.rodar,
                     tipo="primario").pack(side="left")
        self.o.botao(linha, "Só as lutas (sem vídeo)",
                     lambda: self.rodar(so_dados=True)).pack(
            side="left", padx=estilo.ESPACO["meio"])
        self.o.legenda(linha, "as lutas são gravadas de verdade e entram no "
                              "vídeo").pack(side="left",
                                            padx=estilo.ESPACO["normal"])

        luta = self.o.cartao(pai, "Luta única — uma luta, um vídeo")
        luta.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=estilo.ESPACO["meio"])
        linha = self._linha(luta.corpo)
        moldura, self.var_p1 = self.o.campo(linha, "P1:", 18)
        moldura.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        moldura, self.var_p2 = self.o.campo(linha, "P2:", 18)
        moldura.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        moldura, self.var_seed_luta = self.o.campo(linha, "Seed:", 10)
        moldura.pack(side="left")
        linha = self._linha(luta.corpo)
        self.o.botao(linha, "🥊  GRAVAR LUTA", self.luta,
                     tipo="primario").pack(side="left")
        self.o.botao(linha, "🏅  Ranking da arena",
                     lambda: self.rb(["main.py", "arena", "ranking"],
                                     "ranking da arena")).pack(
            side="left", padx=estilo.ESPACO["meio"])
        self.o.legenda(
            luta.corpo,
            "P1 vazio = último criado na roleta; P2 vazio = adversário por "
            "continuidade/poder. Toda luta conta no cartel.").pack(
            anchor="w", pady=(estilo.ESPACO["meio"], 0))

        topo = tk.Frame(pai, bg=self.t.fundo)
        topo.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=(estilo.ESPACO["normal"], estilo.ESPACO["meio"]))
        self.o.secao(topo, "Torneios e lutas").pack(side="left")
        self.o.legenda(topo, "duplo-clique assiste").pack(
            side="left", padx=estilo.ESPACO["meio"])
        for texto, qual in (("↻", None), ("▶  Normal", "normal"),
                            ("▶  Celular", "celular")):
            self.o.botao(topo, texto,
                         self.recarregar if qual is None
                         else (lambda q=qual: self.assistir(q))).pack(
                side="right", padx=(estilo.ESPACO["pouco"], 0))

        self.tabela = self.o.tabela(pai, [
            ("id", "TORNEIO / LUTA", 190, "w"),
            ("tipo", "TIPO", 90, "w"),
            ("resumo", "RESUMO", 420, "w"),
            ("formatos", "FORMATOS", 150, "w"),
        ], altura=9, estica="resumo")
        self.tabela.pack(fill="both", expand=True,
                         padx=estilo.ESPACO["secao"],
                         pady=(0, estilo.ESPACO["normal"]))
        self.tabela.bind("<Double-1>", lambda _e: self.assistir("celular"))

    def ao_mostrar(self) -> None:
        self.recarregar()

    def recarregar(self) -> None:
        self.casca.supervisor.tarefa(self._ler, self._desenhar,
                                     rotulo="torneios")

    @staticmethod
    def _ler() -> list:
        saida = []
        pasta = RANDOM_BUILDS / "outputs"
        for padrao, tipo in (("tournament_*", "torneio"), ("fight_*", "luta")):
            for alvo in sorted(pasta.glob(padrao), reverse=True)[:20]:
                resumo = ""
                for nome in ("tournament.json", "fight.json"):
                    arquivo = alvo / nome
                    if not arquivo.is_file():
                        continue
                    try:
                        dados = json.loads(
                            arquivo.read_text(encoding="utf-8-sig"))
                    except (OSError, ValueError):
                        continue
                    estatisticas = dados.get("estatisticas") or {}
                    resumo = (f"{estatisticas.get('total_lutas', '?')} lutas · "
                              f"campeão {dados.get('campeao', '?')}"
                              if tipo == "torneio"
                              else f"{dados.get('vencedor', '?')} venceu")
                formatos = [n.replace("final_", "").replace(".mp4", "")
                            for n in ("final_celular.mp4", "final_normal.mp4")
                            if (alvo / n).is_file()]
                saida.append((alvo.name, tipo, resumo,
                              ", ".join(formatos) or "—"))
        return saida

    def _desenhar(self, linhas) -> None:
        if isinstance(linhas, dict):
            return
        self.tabela.delete(*self.tabela.get_children())
        for linha in linhas:
            self.tabela.insert("", "end", iid=linha[0], values=linha)

    def rodar(self, so_dados: bool = False) -> None:
        extras = ["--fonte", self.combo_fonte.get(),
                  "--participantes", self.combo_quantos.get()]
        if self.var_seed.get().strip():
            extras += ["--seed", self.var_seed.get().strip()]
        if self.var_preview.get():
            extras.append("--preview")
        if so_dados:
            extras.append("--generation-only")
        self.rb(["main.py", "tournament"] + extras, "torneio",
                depois=self.recarregar)

    def luta(self) -> None:
        extras = []
        for bandeira, variavel in (("--p1", self.var_p1), ("--p2", self.var_p2),
                                   ("--seed", self.var_seed_luta)):
            if variavel.get().strip():
                extras += [bandeira, variavel.get().strip()]
        self.rb(["main.py", "fight"] + extras, "luta única",
                depois=self.recarregar)

    def assistir(self, qual: str) -> None:
        iid = self.o.selecionado(self.tabela, "Escolha um torneio ou luta.")
        if iid is None:
            return
        alvo = RANDOM_BUILDS / "outputs" / iid / f"final_{qual}.mp4"
        if alvo.is_file():
            os.startfile(alvo)                               # noqa: S606
        else:
            self.casca._registrar(f"{iid}: não tem o formato {qual}.", "erro")


class Reacoes(_Base):
    chave = "reacoes"
    rotulo = "Reações"
    icone = "😂"

    def construir(self, pai) -> None:
        from builds.assets.catalog import CATEGORIES
        self.categorias = list(CATEGORIES)

        self.o.titulo(pai, "Biblioteca de vídeos de reação")
        topo = tk.Frame(pai, bg=self.t.fundo)
        topo.pack(fill="x", padx=estilo.ESPACO["secao"])
        self.o.rotulo(topo, "Categoria para importar:", cor="texto_fraco").pack(
            side="left", padx=(0, estilo.ESPACO["meio"]))
        self.combo_categoria = self.o.combo(topo, self.categorias, "insane",
                                            largura=12)
        self.combo_categoria.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        caixa, self.var_mover = self.o.marcador(topo, "mover em vez de copiar")
        caixa.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        self.o.botao(topo, "＋  Importar vídeos…",
                     lambda: self.importar(False), tipo="primario").pack(
            side="left")
        self.o.botao(topo, "＋  Importar pasta…",
                     lambda: self.importar(True)).pack(
            side="left", padx=estilo.ESPACO["meio"])

        self.tabela = self.o.tabela(pai, [
            ("id", "ID", 70, "w"), ("categoria", "CATEGORIA", 110, "w"),
            ("duracao", "DURAÇÃO", 90, "center"),
            ("origem", "ARQUIVO ORIGINAL", 420, "w"),
        ], altura=10, estica="origem")
        self.tabela.configure(selectmode="extended")
        self.tabela.pack(fill="both", expand=True,
                         padx=estilo.ESPACO["secao"],
                         pady=estilo.ESPACO["normal"])

        rodape = tk.Frame(pai, bg=self.t.fundo)
        rodape.pack(fill="x", padx=estilo.ESPACO["secao"],
                    pady=(0, estilo.ESPACO["normal"]))
        self.o.rotulo(rodape, "Selecionados:", cor="texto_fraco").pack(
            side="left", padx=(0, estilo.ESPACO["meio"]))
        self.combo_recategoria = self.o.combo(rodape, self.categorias, "good",
                                              largura=12)
        self.combo_recategoria.pack(side="left",
                                    padx=(0, estilo.ESPACO["meio"]))
        self.o.botao(rodape, "Recategorizar", self.recategorizar).pack(
            side="left")
        self.o.botao(rodape, "Remover", self.remover, tipo="perigo").pack(
            side="left", padx=estilo.ESPACO["meio"])
        self.o.botao(rodape, "↻  Atualizar", self.recarregar).pack(side="right")

    def ao_mostrar(self) -> None:
        self.recarregar()

    def recarregar(self) -> None:
        self.casca.supervisor.tarefa(self._ler, self._desenhar,
                                     rotulo="reações")

    @staticmethod
    def _ler() -> list:
        from builds.assets import importer
        return [(r.get("id", ""), r.get("category", ""),
                 f"{r.get('duration', 0):.1f}s" if r.get("duration") else "",
                 r.get("source", ""))
                for r in (importer.list_reactions() or [])]

    def _desenhar(self, linhas) -> None:
        if isinstance(linhas, dict):
            self.casca._registrar(f"[reações] {linhas.get('erro')}", "erro")
            return
        self.tabela.delete(*self.tabela.get_children())
        for linha in linhas:
            self.tabela.insert("", "end", iid=linha[0], values=linha)

    def importar(self, pasta_inteira: bool) -> None:
        if pasta_inteira:
            alvo = filedialog.askdirectory(title="Pasta com os vídeos")
            entrada = [alvo] if alvo else []
        else:
            entrada = list(filedialog.askopenfilenames(
                title="Vídeos de reação",
                filetypes=[("Vídeo", "*.mp4 *.mov *.webm *.mkv"),
                           ("Todos", "*.*")]))
        if not entrada:
            return
        argumentos = ["main.py", "import-reactions", "--categoria",
                      self.combo_categoria.get()]
        if self.var_mover.get():
            argumentos.append("--mover")
        self.rb(argumentos + entrada, "importar reações",
                depois=self.recarregar)

    def _escolhidos(self) -> list:
        escolhidos = list(self.tabela.selection())
        if not escolhidos:
            messagebox.showinfo("Reações", "Selecione pelo menos um vídeo.")
        return escolhidos

    def recategorizar(self) -> None:
        escolhidos = self._escolhidos()
        if not escolhidos:
            return
        self.rb(["main.py", "reactions", "--recategorizar",
                 self.combo_recategoria.get()] + escolhidos,
                "recategorizar", depois=self.recarregar)

    def remover(self) -> None:
        escolhidos = self._escolhidos()
        if not escolhidos:
            return
        if not messagebox.askyesno(
                "Remover", f"Remover {len(escolhidos)} vídeo(s) da "
                           "biblioteca?\n\nO arquivo original não é apagado."):
            return
        self.rb(["main.py", "reactions", "--remover"] + escolhidos,
                "remover reações", depois=self.recarregar)


class Audio(_Base):
    chave = "audio"
    rotulo = "Áudio"
    icone = "🔊"

    def construir(self, pai) -> None:
        self.o.titulo(pai, "Áudio — os sons do jogo")
        card = self.o.cartao(
            pai, "Sons empacotados e substituições locais")
        card.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=estilo.ESPACO["meio"])
        self.o.legenda(
            card.corpo,
            "Os sons que vêm no pacote ficam em neural_fights/sounds/. Uma "
            "substituição local vale só nesta máquina e mora no diretório de "
            "runtime — o pacote nunca é alterado.").pack(anchor="w")
        linha = self._linha(card.corpo)
        self.o.botao(linha, "📂  Abrir pasta dos sons locais",
                     self.abrir_runtime).pack(side="left")
        self.o.botao(linha, "📦  Abrir pasta do pacote",
                     self.abrir_pacote).pack(side="left",
                                             padx=estilo.ESPACO["meio"])

        self.tabela = self.o.tabela(pai, [
            ("evento", "EVENTO", 200, "w"),
            ("origem", "DE ONDE VEM", 130, "w"),
            ("arquivo", "ARQUIVO", 460, "w"),
        ], altura=12, estica="arquivo")
        self.tabela.tag_configure("local", foreground=self.t.aviso)
        self.tabela.pack(fill="both", expand=True,
                         padx=estilo.ESPACO["secao"],
                         pady=(0, estilo.ESPACO["normal"]))

    def ao_mostrar(self) -> None:
        self.recarregar()

    def recarregar(self) -> None:
        self.casca.supervisor.tarefa(self._ler, self._desenhar, rotulo="áudio")

    @staticmethod
    def _ler() -> list:
        from neural_fights.effects import audio_paths
        config = audio_paths.load_sound_config()
        locais = audio_paths.get_runtime_sound_dir()
        saida = []
        for evento, nome in sorted(config.items()):
            if evento.startswith("_") or not isinstance(nome, str):
                continue
            local = (locais / nome).is_file() if nome else False
            saida.append((evento, "local" if local else "pacote", nome or "—"))
        return saida

    def _desenhar(self, linhas) -> None:
        if isinstance(linhas, dict):
            self.casca._registrar(f"[áudio] {linhas.get('erro')}", "erro")
            return
        self.tabela.delete(*self.tabela.get_children())
        for evento, origem, arquivo in linhas:
            self.tabela.insert("", "end", values=(evento, origem, arquivo),
                               tags=("local",) if origem == "local" else ())

    def abrir_runtime(self) -> None:
        from neural_fights.effects import audio_paths
        pasta = audio_paths.get_runtime_sound_dir()
        pasta.mkdir(parents=True, exist_ok=True)
        os.startfile(pasta)                                  # noqa: S606

    def abrir_pacote(self) -> None:
        from neural_fights.effects import audio_paths
        os.startfile(audio_paths.PACKAGE_SOUND_DIR)          # noqa: S606


__all__ = ["Audio", "Reacoes", "Torneio"]
