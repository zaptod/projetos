# -*- coding: utf-8 -*-
"""A casca: barra lateral, area de conteudo e o console em gaveta.

O QUE MUDOU DE VERDADE AQUI, e nao e gosto: o console ocupava ~130px FIXOS
na base da janela, quase sempre vazio. Numa tela de 768px, depois da barra do
Windows, do titulo e da barra de ferramentas, sobravam ~330px de conteudo --
e por isso o cartao "ONDE POSTAR" da pagina Publicar, a tabela de
paralelismo da Vila e uma fileira inteira de botoes ficavam ABAIXO DA DOBRA,
em coisas que o dono usa todo dia.

Agora ele e uma GAVETA: uma faixa de uma linha que mostra o estado e a ultima
saida, e que se abre sozinha quando um comando comeca. Devolve ~110px ao
conteudo sem tirar nada de ninguem.

O CONTRATO DE PAGINA, que e o que mata o espaguete estruturalmente:

    chave       identificador curto
    rotulo      o que aparece no menu
    construir(pai)      monta os widgets uma vez
    ao_mostrar()        chamada quando a pagina fica visivel
    atualizar(resumo)   recebe o dicionario do `panorama`

Antes, `_mostrar()` tinha uma cadeia de `if` com oito refreshes escritos na
mao, e dois dos mais caros rodavam a CADA saida de subprocesso, com a pagina
invisivel. Com o contrato, so a pagina visivel e atualizada, e nenhuma
precisa lembrar de se registrar em lugar nenhum.
"""
from __future__ import annotations

import tkinter as tk

from . import estilo
from .processos import Periodico, Supervisor
from .widgets import Oficina

# Quanto tempo entre duas leituras do `panorama`. Ele ja tem cache de 3 s;
# aqui o intervalo e o da TELA, que pode ser mais folgado.
INTERVALO_RESUMO_MS = 4000

LARGURA_BARRA = 196
LARGURA_BARRA_ESTREITA = 56
# Abaixo disto a barra lateral vira so icone. A tela dele tem 1366 de largura.
LIMITE_ESTREITO = 1000


class Casca(tk.Tk):
    """A janela. Recebe as paginas prontas — nao sabe o que elas fazem."""

    @classmethod
    def criar(cls, classes: list, *, tema: str = "oficina",
              titulo: str = "Neural Fights"):
        """A porta de entrada.

        As paginas recebem a casca no construtor (precisam do supervisor e da
        oficina de widgets), e a casca precisa das paginas para montar o
        menu. Este metodo desata o no: cria a janela, instancia as paginas
        com ela, e so entao monta.
        """
        return cls(classes, tema=tema, titulo=titulo)

    def __init__(self, classes: list, *, tema: str = "oficina",
                 titulo: str = "Neural Fights"):
        super().__init__()
        self.tema = estilo.tema(tema)
        self.oficina = Oficina(self.tema)
        self.title(titulo)
        self.configure(bg=self.tema.fundo)
        self.minsize(1000, 600)

        self.oficina.aplicar_ttk(self)
        paginas = [classe(self) for classe in classes]
        self._paginas = {p.chave: p for p in paginas}
        self.paginas = self._paginas          # contrato do smoke
        self._quadros: dict = {}
        self._atual: str | None = None
        self._console_aberto = False

        self._montar()
        self.supervisor = Supervisor(
            self, ao_registrar=self._registrar,
            ao_terminar=lambda _n, _c: self._pintar_faixa())
        self._pulso = Periodico(self, INTERVALO_RESUMO_MS, self._pedir_resumo)
        self._pulso.ligar()

        self.bind("<Configure>", self._ao_redimensionar)
        self.bind("<F11>", lambda _e: self._alternar_cheia())
        self.bind("<Escape>", lambda _e: self._fechar_console())
        if self._paginas:
            self.mostrar(next(iter(self._paginas)))

    # ------------------------------------------------------------ layout
    def _montar(self) -> None:
        t, o = self.tema, self.oficina

        # A GAVETA E EMPACOTADA PRIMEIRO, e isso nao e detalhe: no `pack` do
        # Tk quem chega antes reserva o espaco. Com o corpo (`expand=True`)
        # empacotado na frente, ele engolia a faixa inteira e o console
        # simplesmente nao aparecia -- sem erro nenhum.
        self._montar_console()

        corpo = tk.Frame(self, bg=t.fundo)
        corpo.pack(fill="both", expand=True)

        # --- barra lateral
        self._barra = tk.Frame(corpo, bg=t.superficie, width=LARGURA_BARRA)
        self._barra.pack(side="left", fill="y")
        self._barra.pack_propagate(False)
        self._marca = o.rotulo(self._barra, "NEURAL FIGHTS", papel="secao",
                               peso="bold", cor="acento", bg=t.superficie)
        self._marca.pack(anchor="w", padx=estilo.ESPACO["muito"],
                         pady=(estilo.ESPACO["muito"], estilo.ESPACO["secao"]))

        self._itens: dict = {}
        for pagina in self._paginas.values():
            item = self._item_de_menu(pagina)
            self._itens[pagina.chave] = item

        # --- area de conteudo
        self._area = tk.Frame(corpo, bg=t.fundo)
        self._area.pack(side="left", fill="both", expand=True)

    def _item_de_menu(self, pagina):
        t, o = self.tema, self.oficina
        linha = tk.Frame(self._barra, bg=t.superficie, cursor="hand2")
        linha.pack(fill="x")
        # A trilha de 3px a esquerda e o que marca o item ativo. Pintar o
        # fundo inteiro de roxo competiria com o conteudo da pagina.
        trilha = tk.Frame(linha, bg=t.superficie, width=3)
        trilha.pack(side="left", fill="y")
        etiqueta = o.rotulo(linha, f"{pagina.icone}  {pagina.rotulo}",
                            cor="texto_fraco", bg=t.superficie)
        etiqueta.pack(side="left", fill="x", expand=True,
                      padx=(estilo.ESPACO["normal"], 0),
                      pady=estilo.ESPACO["meio"])
        for alvo in (linha, etiqueta):
            alvo.bind("<Button-1>", lambda _e, c=pagina.chave: self.mostrar(c))
            alvo.bind("<Enter>", lambda _e, e=etiqueta, c=pagina.chave:
                      e.configure(fg=t.texto) if self._atual != c else None)
            alvo.bind("<Leave>", lambda _e, e=etiqueta, c=pagina.chave:
                      e.configure(fg=t.texto_fraco) if self._atual != c
                      else None)
        return {"linha": linha, "trilha": trilha, "etiqueta": etiqueta,
                "pagina": pagina}

    # ----------------------------------------------------------- console
    def _montar_console(self) -> None:
        t, o = self.tema, self.oficina
        self._gaveta = tk.Frame(self, bg=t.console_fundo)
        self._gaveta.pack(side="bottom", fill="x")

        # Um fio de 1px separando a faixa do conteudo. Sem ele a gaveta
        # existe (medido: 32px, no lugar certo) mas ninguem enxerga: preto
        # sobre preto nao e discricao, e invisibilidade.
        tk.Frame(self._gaveta, bg=t.borda, height=1).pack(fill="x")

        faixa = tk.Frame(self._gaveta, bg=t.superficie, cursor="hand2")
        faixa.pack(fill="x")
        self._seta = o.rotulo(faixa, "▸", papel="legenda",
                              cor="texto_apagado", bg=t.superficie)
        self._seta.pack(side="left", padx=(estilo.ESPACO["normal"], 4))
        self._estado = o.rotulo(faixa, "pronto", papel="legenda",
                                cor="texto_fraco", bg=t.superficie)
        self._estado.pack(side="left")
        self._ultima = o.rotulo(faixa, "", papel="legenda",
                                cor="texto_apagado", bg=t.superficie)
        self._ultima.pack(side="left", padx=estilo.ESPACO["normal"])

        self._btn_parar = o.botao(faixa, "Parar", self._parar, tipo="perigo",
                                  compacto=True)
        self._btn_parar.pack(side="right", padx=estilo.ESPACO["meio"], pady=3)
        for alvo in (faixa, self._seta, self._estado, self._ultima):
            alvo.bind("<Button-1>", lambda _e: self._alternar_console())

        self._texto = tk.Text(
            self._gaveta, height=9, bg=t.console_fundo, fg=t.console_texto,
            font=t.letra("mono"), relief="flat", bd=0, wrap="word",
            insertbackground=t.texto, padx=estilo.ESPACO["normal"],
            pady=estilo.ESPACO["meio"])
        self._texto.tag_configure("cmd", foreground=t.acento)
        self._texto.tag_configure("erro", foreground=t.erro)
        self._texto.tag_configure("fim", foreground=t.ok)
        self._texto.tag_configure("saida", foreground=t.console_texto)

    def _alternar_console(self) -> None:
        if self._console_aberto:
            self._fechar_console()
        else:
            self._abrir_console()

    def _abrir_console(self) -> None:
        if self._console_aberto:
            return
        self._console_aberto = True
        self._seta.configure(text="▾")
        self._texto.pack(fill="both", expand=True)

    def _fechar_console(self) -> None:
        if not self._console_aberto:
            return
        self._console_aberto = False
        self._seta.configure(text="▸")
        self._texto.pack_forget()

    def _registrar(self, texto: str, tipo: str = "saida") -> None:
        """Toda saida passa por aqui. Chamado SO na thread da interface."""
        self._texto.insert("end", texto + "\n", tipo)
        self._texto.see("end")
        self._ultima.configure(text=texto[:90])
        if tipo == "cmd":
            # Comando comecando: a gaveta se abre sozinha. Quem disparou quer
            # ver o que aconteceu; quem nao quer, fecha com Esc.
            self._abrir_console()
        self._pintar_faixa()

    def _pintar_faixa(self) -> None:
        ativos = self.supervisor.ativos
        self._estado.configure(
            text=f"{ativos} rodando" if ativos else "pronto",
            fg=self.tema.acento if ativos else self.tema.texto_fraco)

    def _parar(self) -> None:
        quantos = self.supervisor.parar_tudo()
        self._registrar(f"parei {quantos} processo(s).",
                        "fim" if quantos else "saida")

    # ---------------------------------------------------------- paginas
    def mostrar(self, chave: str) -> None:
        pagina = self._paginas.get(chave)
        if pagina is None:
            return
        if chave not in self._quadros:
            quadro = tk.Frame(self._area, bg=self.tema.fundo)
            quadro.place(x=0, y=0, relwidth=1, relheight=1)
            pagina.construir(quadro)
            self._quadros[chave] = quadro
        self._quadros[chave].tkraise()

        anterior, self._atual = self._atual, chave
        if anterior and anterior in self._itens:
            self._pintar_item(anterior, ativo=False)
        self._pintar_item(chave, ativo=True)

        # Sair de uma pagina e tao importante quanto entrar: e o que desliga
        # a animacao da Vila em vez de deixa-la rodando escondida.
        if anterior and anterior != chave:
            deixar = getattr(self._paginas[anterior], "ao_esconder", None)
            if deixar:
                deixar()
        entrar = getattr(pagina, "ao_mostrar", None)
        if entrar:
            entrar()
        self._pedir_resumo()

    # Nome antigo, mantido: `testar.py --smoke` chama `_mostrar`.
    _mostrar = mostrar

    def _pintar_item(self, chave: str, *, ativo: bool) -> None:
        item = self._itens.get(chave)
        if not item:
            return
        t = self.tema
        item["trilha"].configure(bg=t.acento if ativo else t.superficie)
        item["linha"].configure(bg=t.acento_fundo if ativo else t.superficie)
        item["etiqueta"].configure(
            bg=t.acento_fundo if ativo else t.superficie,
            fg=t.texto if ativo else t.texto_fraco,
            font=t.letra("corpo", "bold" if ativo else "normal"))

    # ----------------------------------------------------------- resumo
    def _pedir_resumo(self) -> None:
        """Le o `panorama` FORA da interface e entrega para a pagina visivel."""
        pagina = self._paginas.get(self._atual or "")
        if pagina is None or not hasattr(pagina, "atualizar"):
            return

        def ler():
            import panorama
            return panorama.resumo()

        self.supervisor.tarefa(ler, self._entregar_resumo, rotulo="panorama")

    def _entregar_resumo(self, dados) -> None:
        pagina = self._paginas.get(self._atual or "")
        if pagina is None:
            return
        atualizar = getattr(pagina, "atualizar", None)
        if atualizar:
            atualizar(dados)

    # -------------------------------------------------------- responsivo
    def _ao_redimensionar(self, evento) -> None:
        if evento.widget is not self:
            return
        estreita = evento.width < LIMITE_ESTREITO
        largura = LARGURA_BARRA_ESTREITA if estreita else LARGURA_BARRA
        if self._barra.cget("width") != largura:
            self._barra.configure(width=largura)
            self._marca.configure(text="NF" if estreita else "NEURAL FIGHTS")
            for chave, item in self._itens.items():
                pagina = item["pagina"]
                item["etiqueta"].configure(
                    text=pagina.icone if estreita
                    else f"{pagina.icone}  {pagina.rotulo}")

    def _alternar_cheia(self) -> None:
        self.attributes("-fullscreen",
                        not self.attributes("-fullscreen"))

    def encerrar(self) -> None:
        self._pulso.desligar()
        self.supervisor.encerrar()


__all__ = ["Casca", "INTERVALO_RESUMO_MS"]
