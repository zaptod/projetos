# -*- coding: utf-8 -*-
"""O sistema visual: duas caras, uma gramatica.

DECISAO DO ADRIAN (01/09/2026): a Vila mantem a cara de jogo, com o pixel art
em destaque; as janelas de trabalho ficam sobrias e densas. Como cada uma vai
virar um PROCESSO separado, manter dois conjuntos custa pouco -- eles nunca
aparecem na mesma janela.

O QUE ISTO SUBSTITUI: o painel tinha 11 cores no topo do arquivo e mais 42
literais hexadecimais espalhados, 4 fontes nomeadas e mais 32 tuplas
`("Segoe UI", N)` escritas na mao, e espacamento decidido linha a linha
(`padx=4`, `padx=6`, `padx=8`, `pady=6`...). Nada disso e "gosto": e a
ausencia de decisao, repetida.

AS TRES ESCALAS

  ESPACO   4 8 12 16 24 32. Nada entre. Uma escala com poucos degraus e o
           que faz margens diferentes parecerem parentes em vez de erro.

  TEXTO    quatro niveis com funcao, nao com tamanho: TITULO da tela, SECAO
           dentro dela, CORPO, e LEGENDA. Antes havia dois niveis usados
           (15 e 10) e um monte de 8pt fazendo o papel de tudo que sobrava.

  COR      por SIGNIFICADO, nunca por aparencia. `erro`, e nao `vermelho`.
           Trocar a paleta vira trocar este arquivo; hoje viraria caca aos
           42 literais.

A REGRA QUE MAIS MUDA O RESULTADO: superficie se distingue por BORDA, nao
por bloco de cor mais clara. Quatro tons de roxo empilhados viram uma
mancha; uma borda de 1px sobre o mesmo fundo separa sem pesar. E o acento
vivo fica RESERVADO ao que e clicavel ou esta ativo -- se tudo e roxo, o
roxo nao quer dizer nada.
"""
from __future__ import annotations

# --------------------------------------------------------------- espaco
# Um unico degrau entre dois elementos irmaos; dois degraus entre grupos.
ESPACO = {"nada": 0, "pouco": 4, "meio": 8, "normal": 12,
          "muito": 16, "secao": 24, "pagina": 32}

RAIO = 6            # cantos: o Tk nao arredonda, mas o Canvas da Vila sim
BORDA = 1


class Tema:
    """Uma cara. Os nomes sao os mesmos nas duas — so os valores mudam."""

    def __init__(self, nome: str, cores: dict, fonte: str,
                 escala_texto: dict, densidade: int):
        self.nome = nome
        self._cores = cores
        self.fonte = fonte
        self._texto = escala_texto
        # Altura da linha de tabela. A tela dele e 1366x768: cada pixel de
        # entrelinha custa uma linha de conteudo.
        self.densidade = densidade

    def __getattr__(self, chave: str):
        try:
            return self._cores[chave]
        except KeyError:
            raise AttributeError(
                f"cor '{chave}' nao existe no tema '{self.nome}'. As cores "
                f"disponiveis: {', '.join(sorted(self._cores))}") from None

    # ------------------------------------------------------------ texto
    def texto(self, papel: str, peso: str = "normal") -> tuple:
        """`tema.texto("titulo")` — pelo PAPEL, nunca pelo tamanho.

        Pedir "15pt" espalha decisao; pedir "titulo" concentra. Quando o
        titulo tiver que mudar de tamanho, muda aqui e muda em todo lugar.
        """
        try:
            tamanho = self._texto[papel]
        except KeyError:
            raise AttributeError(
                f"papel de texto '{papel}' nao existe. Os papeis: "
                f"{', '.join(self._texto)}") from None
        if papel == "mono":
            return ("Consolas", tamanho) if peso == "normal" else \
                   ("Consolas", tamanho, peso)
        return (self.fonte, tamanho) if peso == "normal" else \
               (self.fonte, tamanho, peso)

    def cores(self) -> dict:
        """Copia do mapa — para quem precisa iterar (a Oficina, os testes)."""
        return dict(self._cores)


# =====================================================================
# OFICINA — as janelas de trabalho: video, historias, contas, jogo.
#
# Sobria e densa de proposito. Aqui se le tabela e se aperta botao; o que a
# tela tem a fazer e sumir. O fundo tem um resto de violeta (nao e cinza
# puro) para nao brigar com a Vila quando as duas estao abertas lado a lado.
# =====================================================================
OFICINA = Tema(
    nome="oficina",
    fonte="Segoe UI",
    densidade=22,
    escala_texto={"titulo": 17, "secao": 12, "corpo": 10, "legenda": 9,
                  "mono": 9},
    cores={
        # --- superficies, do fundo para a frente
        "fundo": "#121016",
        "superficie": "#191720",
        "superficie_alta": "#211d2b",
        # A borda e o que separa. Antes eram quatro tons de roxo empilhados,
        # que de longe viram uma mancha so.
        "borda": "#2a2635",
        "borda_forte": "#3b3550",

        # --- texto, tres niveis de presenca
        "texto": "#e9e7f0",
        "texto_fraco": "#a09ab0",
        "texto_apagado": "#6d6779",

        # --- acento: SO no que e clicavel ou esta ativo
        "acento": "#9b7dff",
        "acento_forte": "#b6a0ff",
        "acento_fundo": "#231d38",      # trilha de item ativo

        # --- significado
        "ok": "#4ade80",
        "aviso": "#fbbf24",
        "erro": "#f87171",
        "info": "#60a5fa",
        "ok_fundo": "#14251a",
        "erro_fundo": "#2a1618",

        # --- console
        "console_fundo": "#0d0b11",
        "console_texto": "#c9c4d4",
    },
)

# =====================================================================
# VILA — o painel principal, e o unico lugar com cara de jogo.
#
# O mundo e o protagonista: grama verde, caminho de terra, telhados
# coloridos. Entao a moldura e QUENTE e escura, para o pixel art saltar em
# vez de competir. Roxo aqui seria uma segunda cor forte brigando com a
# arte; o acento e ambar, que conversa com a terra do caminho.
# =====================================================================
VILA = Tema(
    nome="vila",
    fonte="Segoe UI",
    densidade=24,
    escala_texto={"titulo": 19, "secao": 13, "corpo": 11, "legenda": 9,
                  "mono": 9},
    cores={
        "fundo": "#171310",
        "superficie": "#211a15",
        "superficie_alta": "#2b2219",
        "borda": "#3a2e23",
        "borda_forte": "#54412f",

        "texto": "#f4ece2",
        "texto_fraco": "#b5a695",
        "texto_apagado": "#7d7062",

        "acento": "#ffb347",
        "acento_forte": "#ffc978",
        "acento_fundo": "#33240f",

        "ok": "#6ee7a0",
        "aviso": "#fcd34d",
        "erro": "#fb8a8a",
        "ok_fundo": "#1a2a1c",
        "erro_fundo": "#2e1a18",
        "info": "#7dd3fc",

        "console_fundo": "#100c09",
        "console_texto": "#d8cbba",
    },
)

TEMAS = {"oficina": OFICINA, "vila": VILA}


def tema(nome: str = "oficina") -> Tema:
    """O tema pelo nome. Desconhecido cai na oficina, que e o padrao."""
    return TEMAS.get(str(nome).lower(), OFICINA)


__all__ = ["BORDA", "ESPACO", "OFICINA", "RAIO", "TEMAS", "Tema", "VILA",
           "tema"]
