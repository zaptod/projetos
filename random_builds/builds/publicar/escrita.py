# -*- coding: utf-8 -*-
"""Escrever num campo do navegador sem apostar na velocidade da maquina.

O DEFEITO, medido em 27/09/2026. Desde 20/09 o YouTube falhou 12 vezes com
`Locator.type: Timeout 30000ms exceeded` (titulo e descricao) e o TikTok 22
vezes com "a legenda nao entrou (TimeoutError)". A suspeita era um dialogo
cobrindo o campo, como a parede do PicassoIA. Nao era: o log do Playwright diz
"locator resolved to <div id="textbox" ...>" — o campo existia, o clique
passou (`click` exige que nada o cubra) e a falha e do `type`.

O `type` e UMA acao com UM prazo para o texto INTEIRO: cada caractere e uma
tecla descendo e subindo, cada uma uma ida e volta ao processo da pagina, e os
30 s do Playwright sao para todas elas juntas. Medido nesta maquina (i5-4590,
4 nucleos), numa pagina local vazia, com o League of Legends aberto e a CPU em
100%: **126 ms por caractere** — 300 caracteres em 37,9 s. As descricoes
tem 230 a 250 caracteres; 30 s cobrem ~238. Sem partida, no TikTok de
verdade (23:39 de 27/09, contador da tela): 69 ms por caractere — a folga era
de 1,8x mesmo num dia bom.

A PROVA ESTA NO CANAL: o rascunho que cada falha deixou guarda o campo como
ele estava quando o relogio venceu. `fn1_Sy3RpMk` (h27 p01, 22/09) tem 88
dos 245 caracteres da descricao; `YqbQUrY1nuE` (h32 p04, 27/09) tem o titulo
"A Filha que Ficou — O grupo da f", 32 de 71 — quase 1 s por tecla no Studio.
O campo ACEITOU texto; nao havia nada na frente. Cruzando o diario com os
registros do jogo: 13 das 17 falhas de 25 a 27/09 cairam DENTRO de uma
partida; na rodada das 23:37 de 27/09, sem partida, as cinco escritas passaram.

O CONSERTO tem tres partes, e nenhuma e "aumentar o prazo":

1. COLAR (`colar=True`). `keyboard.insert_text` entrega o trecho inteiro num
   evento so (e o que o navegador faz num Ctrl+V): 1500 caracteres em 0,05 s
   na mesma CPU em 100%. Continuam TECLA a quebra de linha (`Enter`, o que
   `type` fazia com "\\n") e a hashtag com o espaco que a segue (o site abre
   sugestao no `#` e fecha no espaco): 46 teclas em vez de 238.
2. TECLA A TECLA sem o relogio unico (`colar=False`): o prazo e DESTE modulo,
   180 s, conferido entre palavras — e nao 30 s para o texto inteiro.
3. LER DE VOLTA (`estado`), exigindo cada linha de conteudo: "o type voltou
   sem erro" nunca foi prova.

QUAL VEM PRIMEIRO depende do site, e foi medido em producao, na rodada das
00:37 de 28/09/2026. No YouTube a colagem saiu identica nas duas publicacoes
(titulo e descricao conferidos pela API). No TikTok, uma das duas legendas
coladas perdeu dois dos quatro paragrafos — o editor dele come o texto colado
quando o Enter chega logo atras. Entao: YouTube cola primeiro e digita se nao
pegar; TikTok digita primeiro (o jeito que sempre deu legenda inteira, agora
sem os 30 s) e so cola se a maquina estiver lenta demais ate para isso.
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PASTA_DAS_TELAS = RAIZ / "outputs" / "_publicar" / "telas"
# Fotos guardadas; as mais velhas saem. E prova de falha, nao arquivo.
TELAS_GUARDADAS = 40

# O prazo da escrita INTEIRA, conferido entre pedacos. Folgado de proposito:
# a 400 ms por tecla o jeito tecla a tecla leva ~100 s para 250 caracteres, e
# o menor buraco da grade e de 60 min. O pior medido (~1 s por tecla, o titulo
# cortado no Studio com partida aberta) nao cabe — e para esse caso que o
# TikTok tem a colagem de segunda tentativa, e o YouTube a tem de primeira.
PRAZO_S = 180.0
ATRASO_TECLA_MS = 8
RELOGIO = time.monotonic

# Hashtag e o espaco que a segue (sem atravessar a linha): digitados.
_HASHTAG = re.compile(r"#\S+[ \t]*")


class EscritaLenta(TimeoutError):
    """A escrita passou do prazo DESTE modulo. E TimeoutError de proposito:
    o diario e os testes antigos contam as falhas de escrita por esse nome."""


def pedacos(texto: str, *, colar: bool = True) -> list:
    """O texto em `(modo, trecho)`: "colar", "digitar" ou "tecla" (Enter).

    Com `colar=False` e o jeito antigo — tudo tecla —, mas quebrado por
    palavra, para o prazo ser conferido no meio e nao so no fim.
    """
    saida: list = []

    def por(modo: str, trecho: str) -> None:
        if not trecho:
            return
        if saida and saida[-1][0] == modo == "colar":
            saida[-1] = ("colar", saida[-1][1] + trecho)
        else:
            saida.append((modo, trecho))

    linhas = str(texto or "").split("\n")
    for i, linha in enumerate(linhas):
        if i:
            por("tecla", "Enter")
        if not colar:
            for palavra in re.findall(r"\S+\s*|\s+", linha):
                por("digitar", palavra)
            continue
        fim = 0
        for achado in _HASHTAG.finditer(linha):
            por("colar", linha[fim:achado.start()])
            por("digitar", achado.group(0))
            fim = achado.end()
        por("colar", linha[fim:])
    return saida


def escrever(page, campo, texto: str, *, colar: bool = True,
             atraso_ms: int = ATRASO_TECLA_MS, prazo_s: float = PRAZO_S,
             relogio=None) -> dict:
    """Limpa o campo e escreve `texto`. Devolve o laudo; NAO confere.

    Conferir e com `estado`, e quem decide o que fazer com "nao pegou" e quem
    chama — o TikTok tenta de novo, o YouTube tambem, e as mensagens sao de
    cada um.

    `relogio` (ou `RELOGIO` do modulo) existe para o teste medir o prazo no
    MESMO relogio em que o teclado dublado gasta o tempo medido.
    """
    relogio = relogio or RELOGIO
    comeco = relogio()
    campo.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    teclas = 0
    for modo, trecho in pedacos(texto, colar=colar):
        passou = relogio() - comeco
        if passou > prazo_s:
            raise EscritaLenta(
                f"a escrita passou de {prazo_s:.0f}s ({passou:.0f}s, "
                f"{teclas} teclas) — a maquina esta lenta demais agora")
        if modo == "colar":
            page.keyboard.insert_text(trecho)
        elif modo == "tecla":
            page.keyboard.press(trecho)
            teclas += 1
        else:
            page.keyboard.type(trecho, delay=atraso_ms)
            teclas += len(trecho)
    return {"modo": "colado" if colar else "digitado", "teclas": teclas,
            "s": round(relogio() - comeco, 1)}


def sem_emoji(texto: str) -> str:
    """So o que o `inner_text` consegue devolver.

    O TikTok troca emoji por `<img>` enquanto se digita, e `inner_text` nao ve
    imagem. Uma legenda que COMECE com emoji some dos primeiros caracteres e a
    conferencia acusaria vazio num campo cheio — adiando video bom e, pior,
    somando falhas ate o contador desistir dele. Tirar dos DOIS lados antes de
    comparar e o que torna a comparacao honesta.
    """
    return "".join(c for c in texto if c.isalnum() or c.isspace()
                   or c in ".,;:!?-_#@/()'\"").strip()


def linhas_de_conteudo(texto: str) -> list:
    """As linhas que TEM de estar no campo: sem hashtag, sem emoji, com o
    espaco normalizado. Linha so de hashtag nao entra."""
    saida = []
    for linha in str(texto or "").split("\n"):
        palavras = [p for p in sem_emoji(linha).split() if not p.startswith("#")]
        if palavras:
            saida.append(" ".join(palavras))
    return saida


def estado(campo, texto: str) -> str:
    """"escrita", "ficou vazia" ou "ficou incompleta".

    Separadas porque tem causas diferentes: vazia e o campo que nao aceitou
    nada (clique perdido, elemento trocado); incompleta e a escrita
    interrompida ou comida no meio. Gravadas como a mesma coisa, o diario nao
    permite distinguir "o site recusou o foco" de "a pagina travou".

    TODA LINHA DE CONTEUDO TEM DE ESTAR LA, desde 28/09/2026. O criterio
    antigo ("os 20 primeiros caracteres, ou metade do volume") aprovou, na
    rodada das 00:37, a legenda da `historia_00031:celular:p06` com dois dos
    quatro paragrafos sumidos — 85 de 230 caracteres no contador do TikTok —
    e aprovaria o titulo cortado "A Filha que Ficou — O grupo da f". O que
    continua de fora e so o que o site reformata: hashtag (vira `span` ou
    some do fim) e emoji (vira imagem, que `inner_text` nao ve).
    """
    try:
        atual = (campo.inner_text() or "").strip()
    except Exception:                                          # noqa: BLE001
        # Nao deu para ler: nao invente falha. Quem decide e a etapa seguinte.
        return "escrita"
    if not atual:
        return "ficou vazia"
    # a hashtag sai dos DOIS lados: o lutador "Kuro #2" (duelo_00023, 02/10/2026)
    # nunca batia — o esperado perdia o "#2" e o lido nao — e o video era adiado
    # para sempre nos dois destinos com o titulo certo na tela
    visto = " ".join(p for p in sem_emoji(atual).split() if not p.startswith("#"))
    faltam = [linha for linha in linhas_de_conteudo(texto) if linha not in visto]
    return "ficou incompleta" if faltam else "escrita"


def fotografar(page, rotulo: str, *, pasta: Path | None = None) -> str:
    """A tela no instante da falha. Devolve o caminho, ou "" se nao deu.

    Existe por causa da regra "ler a tela, nao o DOM": a falha de escrita
    passou uma semana sendo investigada por mensagem de erro, e a mensagem
    cortada em 200 caracteres nao mostra o que havia na frente do campo. Nunca
    levanta — a foto e prova, e prova nao pode derrubar a rodada.
    """
    tirar = getattr(page, "screenshot", None)
    if tirar is None:
        # Pagina sem camera (duble de teste): nada a guardar, e nenhuma pasta
        # criada em outputs/ por quem nao ia gravar nada nela.
        return ""
    pasta = pasta or PASTA_DAS_TELAS
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        nome = re.sub(r"[^\w.-]+", "_", str(rotulo))[:60]
        destino = pasta / f"{datetime.now():%Y%m%d_%H%M%S}_{nome}.png"
        tirar(path=str(destino), timeout=15_000)
    except Exception:                                          # noqa: BLE001
        return ""
    try:
        velhas = sorted(pasta.glob("*.png"))[:-TELAS_GUARDADAS]
        for arquivo in velhas:
            arquivo.unlink(missing_ok=True)
    except Exception:                                          # noqa: BLE001
        pass
    return str(destino)
