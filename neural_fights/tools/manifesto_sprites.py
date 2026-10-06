"""Manifesto das partes estaticas que o palco pode montar.

O desenho dos eixos fica no prototipo aprovado pelo contrato.  Este modulo e
o ponto de entrada de producao: importa os catalogos da engine, normaliza os
campos que o painel consome e grava o resultado de modo atomico.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import runpy
import shutil
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


RAIZ = Path(__file__).resolve().parents[2]
PROTOCOLO = RAIZ / "docs" / "sprites" / "prototipo_gerar_manifesto.py"
PADRAO = RAIZ / "palco" / "biblioteca" / "manifesto_slots.json"


def arquivo_do_destino(biblioteca: Path, destino: str) -> Path:
    """Traduz o destino publicado no manifesto para uma biblioteca concreta.

    A API usa esta funcao e o palco le o mesmo campo do manifesto.  Assim,
    trocar a biblioteca para um teste nao cria uma segunda regra de caminhos.
    """
    partes = Path(destino.replace("\\", "/")).parts
    try:
        inicio = partes.index("biblioteca")
    except ValueError:
        raise ValueError("destino sem biblioteca") from None
    caminho = (biblioteca / Path(*partes[inicio + 1:])).resolve()
    try:
        caminho.relative_to(biblioteca.resolve())
    except ValueError:
        raise ValueError("destino fora da biblioteca") from None
    return caminho


# --------------------------------------------------------------- a regra do rosto
# Espelho de palco/nucleo/partes_lutador.gd (FAMILIA, PARTES_DE_EXPRESSAO e
# NIVEIS). tests/test_manifesto_sprites.py compara as duas tabelas pelo texto
# do .gd: se uma mudar sem a outra, a catraca fica vermelha.
EXPRESSOES = (
    "neutro", "focado", "glacial", "determinado", "furia", "berserk", "confiante", "animado",
    "euforico", "extase", "panico", "nervoso", "desespero", "tedio", "tristeza", "morto",
    "tonto", "dor", "esforco", "firmeza", "alerta", "confuso", "limite", "concentrado",
)
FAMILIA = {
    "neutro": "neutro", "focado": "neutro", "glacial": "neutro", "concentrado": "neutro",
    "firmeza": "neutro", "tedio": "neutro", "determinado": "furia", "furia": "furia",
    "berserk": "furia", "esforco": "furia", "limite": "furia", "confiante": "animado",
    "animado": "animado", "euforico": "animado", "extase": "animado", "panico": "panico",
    "nervoso": "panico", "desespero": "panico", "alerta": "panico", "confuso": "panico",
    "tonto": "dor", "tristeza": "dor", "dor": "dor", "morto": "morto",
}
REPRESENTANTES = ("neutro", "furia", "animado", "panico", "dor", "morto")
PARTES_DE_EXPRESSAO = ("olhos", "sobrancelhas", "boca", "detalhe_rosto")
NIVEIS = {
    "sombra": ("comum",), "acessorio_costas": ("personagem", "classe"),
    "pele": ("personagem", "classe", "comum"), "marcas": ("personagem", "classe"),
    "olhos": ("personagem", "classe", "comum"), "sobrancelhas": ("personagem", "classe", "comum"),
    "boca": ("personagem", "classe", "comum"), "detalhe_rosto": ("comum",),
    "acessorio_cabeca": ("personagem", "classe"),
}
CAMADA_Z = {"sombra": 0, "acessorio_costas": 10, "pele": 20, "marcas": 25, "olhos": 40,
            "sobrancelhas": 45, "boca": 50, "detalhe_rosto": 55, "acessorio_cabeca": 60}


def estados_da_expressao(parte: str, expressao: str) -> list[str]:
    """Expressao pedida -> representante da familia -> neutro (igual ao Godot)."""
    if parte not in PARTES_DE_EXPRESSAO:
        return ["base"]
    saida = [expressao]
    familia = FAMILIA.get(expressao, "neutro")
    if familia != expressao:
        saida.append(familia)
    if "neutro" not in saida:
        saida.append("neutro")
    return saida


def fnv1a32(texto: str) -> int:
    """FNV-1a de 32 bits sobre o UTF-8: explicito e igual no GDScript
    (`PartesLutador.fnv1a32`). `hash()` do Python e o do Godot nao servem."""
    h = 0x811C9DC5
    for byte in texto.encode("utf-8"):
        h = ((h ^ byte) * 16777619) & 0xFFFFFFFF
    return h


def _sorteio_variante(chave: str, parte: str, opcoes: list[str]) -> str:
    """Igual a PartesLutador._sorteio_variante: FNV-1a de `slug(chave):parte`,
    dobrado em 16 bits, modulo o numero de variantes, sobre os ids em ordem.

    `chave` e o nome do personagem como o jogo o recebe (ou a classe, sem
    personagem); o slug faz "Celeste a Impiedosa" e "celeste_a_impiedosa"
    sortearem igual. A dobra: sem ela o bit baixo do FNV e a paridade dos
    bytes, e com 2 variantes duas pecas do mesmo lutador coincidiam 44% das
    vezes (medido em 06/10/2026, 200 lutadores x 9 pecas; com a dobra, 50%).
    """
    h = fnv1a32(f"{slug(chave)}:{parte}")
    return sorted(opcoes)[((h >> 16) ^ (h & 0xFFFF)) % len(opcoes)]


def resolver_parte(parte: str, classe: str, expressao: str, existe, personagem: str = "",
                   guarda_roupa: dict | None = None, variantes=None) -> dict | None:
    """O mesmo `PartesLutador.resolver_com` do palco.

    `existe(parte, nivel, alvo, estado) -> bool` mantem o contrato antigo
    (uma arte por slot, sem variantes; a resposta nao traz `variante`).
    `variantes`, quando informado, devolve `{variante: {estados}}`; nesse
    modo o dono vem de `dono_da_parte` (personagem -> classe -> comum), a
    escolha e fixa por personagem + parte e so entao cai na carinha.
    `guarda_roupa` sao as escolhas fixadas DESTE personagem (`{parte:
    variante}`; `fixadas_do_personagem` tira do arquivo inteiro).
    """
    if parte not in NIVEIS:
        return None
    if variantes:
        dono = dono_da_parte(parte, classe, variantes, personagem)
        if dono is None:
            return None
        nivel, alvo, colecao = dono
        variante = variante_escolhida(colecao, (guarda_roupa or {}).get(parte, ""),
                                      personagem or classe, parte)
        estado = estado_na_variante(parte, expressao, colecao[variante])
        if estado is None:
            return None
        return {"nivel": nivel, "alvo": alvo, "estado": estado, "variante": variante}
    possiveis = EXPRESSOES if parte in PARTES_DE_EXPRESSAO else ("base",)
    for nivel, alvo in (("personagem", slug(personagem)), ("classe", slug(classe)), ("comum", "_")):
        if nivel not in NIVEIS[parte] or (nivel != "comum" and alvo in ("", "_")):
            continue
        # O primeiro nivel que possui QUALQUER estado e o dono da parte.
        estados_existentes = {estado for estado in possiveis if existe(parte, nivel, alvo, estado)}
        if not estados_existentes:
            continue
        estado = estado_na_variante(parte, expressao, estados_existentes)
        return None if estado is None else {"nivel": nivel, "alvo": alvo, "estado": estado}
    return None


def fixadas_do_personagem(guarda_roupa: dict | None, personagem: str) -> dict:
    """As escolhas fixadas de UM personagem no `guarda_roupa.json` inteiro
    (`{slug_do_personagem: {parte: variante}}`), pela chave que o palco le."""
    escolhas = (guarda_roupa or {}).get(slug(personagem)) if personagem else None
    return escolhas if isinstance(escolhas, dict) else {}


def variantes_no_disco(biblioteca: Path):
    """`variantes(parte, nivel, alvo)` lido das pastas de uma biblioteca
    (`<biblioteca>/partes/lutador/...`), como o palco descobre pelo nome."""
    raiz = Path(biblioteca) / "partes" / "lutador"

    def variantes(parte: str, nivel: str, alvo: str) -> dict:
        try:
            return {d.name: {f.stem for f in d.glob("*.png") if f.is_file()}
                    for d in (raiz / parte / nivel / alvo).iterdir() if d.is_dir()}
        except OSError:
            return {}
    return variantes


def resolver_no_disco(biblioteca: Path, parte: str, personagem: str, classe: str,
                      expressao: str) -> dict | None:
    """Espelho de `PartesLutador.resolver` numa biblioteca concreta (le o
    `partes/guarda_roupa.json` e as pastas); devolve tambem o `arquivo`."""
    biblioteca = Path(biblioteca)
    try:
        guarda = json.loads((biblioteca / "partes" / "guarda_roupa.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        guarda = {}
    achado = resolver_parte(parte, classe, expressao, lambda *_: False, personagem=personagem,
                            guarda_roupa=fixadas_do_personagem(guarda if isinstance(guarda, dict) else {},
                                                               personagem),
                            variantes=variantes_no_disco(biblioteca))
    if achado is not None:
        achado["arquivo"] = (biblioteca / "partes" / "lutador" / parte / achado["nivel"] / achado["alvo"]
                             / achado["variante"] / f"{achado['estado']}.png")
    return achado


# ------------------------------------------------------- provador (painel)
# O provador do app mostra, para UM lutador, de qual nivel vem cada peca e
# qual variante o jogo usa. As duas funcoes abaixo sao o mesmo
# `PartesLutador.resolver_com` do palco, em dois passos: o dono da peca
# (personagem -> classe -> comum, o primeiro com alguma variante) e a escolha
# dentro dele (a fixada no guarda-roupa ou o sorteio por `personagem:parte`).
def slug(texto: str) -> str:
    """O mesmo de `UtilPalco.slug` (palco/nucleo/util.gd)."""
    de, para = "áàâãäåéèêëíìîïóòôõöúùûüçñý", "aaaaaaeeeeiiiiooooouuuucny"
    saida = ""
    for letra in str(texto or "").strip().lower():
        indice = de.find(letra)
        if indice >= 0:
            letra = para[indice]
        if "a" <= letra <= "z" or "0" <= letra <= "9":
            saida += letra
        elif saida and not saida.endswith("_"):
            saida += "_"
    return saida.rstrip("_")


def dono_da_parte(parte: str, classe: str, variantes, personagem: str = "") -> tuple | None:
    """(nivel, alvo, {variante: {estados}}) do nivel que e dono da peca.

    `variantes(parte, nivel, alvo)` devolve a colecao daquele nivel. O
    personagem entra pelo slug do nome, como no palco; sem nome, so classe e
    comum. None quando nenhum nivel tem desenho (o jogo usa o de hoje).
    """
    if parte not in NIVEIS:
        return None
    for nivel, alvo in (("personagem", slug(personagem)), ("classe", slug(classe)), ("comum", "_")):
        if nivel not in NIVEIS[parte] or (nivel != "comum" and alvo in ("", "_")):
            continue
        # So conta o que o palco conta (PartesLutador._variantes): pasta
        # `v...` com pelo menos uma carinha valida para a peca. Um `base.png`
        # nos olhos ou uma pasta vazia nao viram variante.
        possiveis = set(EXPRESSOES if parte in PARTES_DE_EXPRESSAO else ("base",))
        colecao = {str(v): set(e) & possiveis for v, e in (variantes(parte, nivel, alvo) or {}).items()
                   if str(v).startswith("v")}
        colecao = {v: e for v, e in colecao.items() if e}
        if colecao:
            return nivel, alvo, colecao
    return None


def variante_escolhida(colecao: dict, fixada: str, chave_sorteio: str, parte: str) -> str:
    """A fixada, se ainda existir na colecao; senao o sorteio estavel.

    `chave_sorteio` e o nome do personagem como o jogo o recebe (ou a classe,
    no lutador de exemplo): o mesmo texto de `_sorteio_variante` no Godot.
    """
    fixada = str(fixada or "")
    return fixada if fixada in colecao else _sorteio_variante(chave_sorteio, parte, list(colecao))


def estado_na_variante(parte: str, expressao: str, estados) -> str | None:
    """A carinha que a variante mostra: exata -> familia -> neutro, so dentro dela."""
    for estado in estados_da_expressao(parte, expressao):
        if estado in estados:
            return estado
    return None


# ------------------------------------------------------------------ versoes
def pasta_de_versoes(arquivo: Path) -> Path:
    return arquivo.with_suffix(arquivo.suffix + ".historico")


def _ordem_da_versao(caminho: Path) -> tuple[int, str]:
    # Carimbo novo: nanossegundos com 20 digitos. Os nomes antigos
    # (milissegundos, "importacao-001") entram pela data do arquivo.
    if caminho.stem.isdigit():
        numero = int(caminho.stem)
        return (numero if len(caminho.stem) >= 19 else numero * 1_000_000), caminho.name
    try:
        return caminho.stat().st_mtime_ns, caminho.name
    except OSError:
        return 0, caminho.name


def versoes(arquivo: Path) -> list[Path]:
    """Versoes anteriores, da mais velha para a mais nova."""
    pasta = pasta_de_versoes(arquivo)
    if not pasta.is_dir():
        return []
    return sorted(pasta.glob("*.png"), key=_ordem_da_versao)


def nome_de_versao(pasta: Path) -> Path:
    """Carimbo unico: o mesmo para importacao e API, sempre crescente."""
    carimbo = time.time_ns()
    while True:
        candidato = pasta / f"{carimbo:020d}.png"
        if not candidato.exists():
            return candidato
        carimbo += 1


def guardar_versao(arquivo: Path, mover: bool = False) -> Path | None:
    """Guarda o PNG atual no historico; `mover` tira o atual do lugar."""
    if not arquivo.is_file():
        return None
    pasta = pasta_de_versoes(arquivo)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = nome_de_versao(pasta)
    if mover:
        os.replace(arquivo, destino)
    else:
        shutil.copy2(arquivo, destino)
    return destino


# -------------------------------------------------------------- textos da tela
NOMES_DAS_PARTES = {
    "sombra": "Sombra", "acessorio_costas": "Acessório de costas", "pele": "Pele (o corpo)",
    "marcas": "Marcas", "olhos": "Olhos", "sobrancelhas": "Sobrancelhas", "boca": "Boca",
    "detalhe_rosto": "Detalhe do rosto", "acessorio_cabeca": "Acessório de cabeça",
    "area_chao": "Área no chão", "area_borda": "Borda da área", "estrutura": "Estrutura",
    "feixe_corpo": "Feixe", "feixe_ponta": "Ponta do feixe", "invocacao": "Invocação",
    "portal": "Portal", "projetil": "Projétil", "conjuracao": "Conjuração",
    "evento": "Efeito", "impacto": "Impacto", "estado": "Estado", "status": "Status",
    "buffs": "Fortalecimento", "canais": "Canalização", "transformacoes": "Transformação",
    "arma": "Arma", "brilho_raridade": "Brilho de raridade", "corrente_cabeca": "Ponta da corrente",
    "corrente_cabo": "Cabo da corrente", "corrente_corda": "Corrente de corda",
    "corrente_couro": "Corrente de couro", "corrente_elos": "Elos da corrente",
    "encantamento": "Encantamento", "orbe": "Orbe", "projetil_arma": "Projétil da arma",
    "rastro": "Rastro do golpe", "chao": "Chão", "parede": "Parede", "obstaculo": "Obstáculo",
    "obstaculo_quebrado": "Obstáculo quebrado", "clima": "Clima", "barra_vida": "Barra de vida",
    "moldura_vida": "Moldura da vida", "placa_nome": "Placa do nome", "selo_plano": "Selo do plano",
}
NOMES_DAS_EXPRESSOES = {
    "neutro": "neutro", "focado": "focado", "glacial": "glacial", "determinado": "determinado",
    "furia": "fúria", "berserk": "berserk", "confiante": "confiante", "animado": "animado",
    "euforico": "eufórico", "extase": "êxtase", "panico": "pânico", "nervoso": "nervoso",
    "desespero": "desespero", "tedio": "tédio", "tristeza": "tristeza", "morto": "morto",
    "tonto": "tonto", "dor": "dor", "esforco": "esforço", "firmeza": "firmeza",
    "alerta": "alerta", "confuso": "confuso", "limite": "limite", "concentrado": "concentrado",
}
_PALAVRAS = {"gravitacao": "gravitação", "critico": "crítico", "projetil": "projétil",
             "colisao": "colisão", "obstaculo": "obstáculo", "explosao": "explosão",
             "agarrao": "agarrão", "vulneravel": "vulnerável", "relogio": "relógio",
             "paralisia": "paralisia", "lancado": "lançado", "magica": "mágica"}


def texto_humano(chave: str) -> str:
    """'acerto_critico' -> 'Acerto crítico'; 'GRAVITACAO' -> 'Gravitação'."""
    palavras = [_PALAVRAS.get(p, p) for p in str(chave).lower().replace("_", " ").split()]
    texto = " ".join(palavras)
    return texto[:1].upper() + texto[1:]


def nome_da_parte(parte: str) -> str:
    return NOMES_DAS_PARTES.get(parte) or texto_humano(parte)


def nome_do_estado(estado: str) -> str:
    if not estado or estado == "base":
        return ""
    return NOMES_DAS_EXPRESSOES.get(estado) or texto_humano(estado).lower()


def nome_do_alvo(alvo: dict, grupo: str = "") -> str:
    if alvo.get("chave") == "_" or alvo.get("nivel") == "comum":
        return "Comum (todos)"
    rotulo = str(alvo.get("rotulo") or alvo.get("chave") or "")
    if rotulo.isupper() or "_" in rotulo or rotulo == rotulo.lower():
        return texto_humano(rotulo)
    return rotulo


def rotulo_humano(slot: dict) -> str:
    """O nome do lugar no cartao: a peca e, quando varia, o estado."""
    estado = nome_do_estado(str(slot.get("estado") or ""))
    nome = nome_da_parte(str(slot.get("parte") or ""))
    return f"{nome} · {estado}" if estado else nome


# ----------------------------------------------------------------- gabarito
# Onde cada peca fica no quadrado de 1024 (corpo: centro 512,512, raio 256,
# olhando para +x). Caixas do CONTRATO_SLOTS.md, secao 2.3 "Zonas do
# gabarito", medidas no RostoPalco (palco/biblioteca/lutadores/rosto.gd): a
# peca nova cai onde o jogo poe o traco de hoje.
ZONAS_DO_GABARITO = {
    "olhos": [(480, 340, 645, 500), (480, 524, 645, 684)],
    "sobrancelhas": [(360, 342, 530, 482), (360, 542, 530, 682)],
    "boca": [(640, 405, 740, 620)],
    "detalhe_rosto": [(455, 675, 600, 727), (600, 600, 680, 640), (350, 597, 418, 663),
                      (294, 415, 364, 609), (480, 340, 645, 500), (480, 524, 645, 684)],
    "acessorio_cabeca": [(150, 300, 360, 724)],
    "marcas": [(300, 300, 724, 724)],
    "sombra": [(256, 532, 768, 748)],
}
DESCRICAO_DA_ZONA = {
    "olhos": "os dois olhos, um de cada lado, na frente",
    "sobrancelhas": "atrás de cada olho",
    "boca": "na ponta da frente, entre os olhos",
    "detalhe_rosto": "gota, lágrima, veia, faíscas ou brilho no olho",
    "acessorio_cabeca": "na nuca; passar da linha tampa os olhos",
    "acessorio_costas": "só aparece fora do círculo do corpo",
    "marcas": "dentro do círculo do corpo",
    "sombra": "no chão, metade para baixo do corpo",
    "pele": "o círculo inteiro é o corpo",
}


def _fonte(tamanho: int):
    for nome in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "arial.ttf"):
        with contextlib.suppress(OSError):
            return ImageFont.truetype(nome, tamanho)
    return ImageFont.load_default(size=tamanho)


def _linha_dupla(caneta, desenhar) -> None:
    """Contorno escuro largo e linha clara fina: aparece em fundo claro e escuro."""
    desenhar(caneta, (20, 20, 26, 230), 9)
    desenhar(caneta, (255, 255, 255, 235), 3)


def _texto_duplo(caneta, posicao, texto, fonte, cor=(255, 255, 255, 255)) -> None:
    caneta.text(posicao, texto, font=fonte, fill=cor, stroke_width=5, stroke_fill=(20, 20, 26, 235))


def gabarito_lutador(parte: str) -> bytes:
    """Devolve o PNG transparente que orienta o desenho das pecas do lutador."""
    imagem = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    caneta = ImageDraw.Draw(imagem, "RGBA")
    # A zona vem primeiro: as linhas do corpo ficam por cima dela.
    if parte == "acessorio_costas":
        # Embaixo da pele: so o que passa do corpo aparece.
        caneta.ellipse((96, 96, 928, 928), fill=(255, 196, 0, 46))
        caneta.ellipse((256, 256, 768, 768), fill=(0, 0, 0, 0))
    if parte == "sombra":
        caneta.ellipse(ZONAS_DO_GABARITO["sombra"][0], fill=(255, 196, 0, 60))
    for caixa in ZONAS_DO_GABARITO.get(parte, []):
        caneta.rounded_rectangle(caixa, radius=22, fill=(255, 196, 0, 46))
        _linha_dupla(caneta, lambda c, cor, w, caixa=caixa: c.rounded_rectangle(
            caixa, radius=22, outline=(cor[0], cor[1], cor[2], min(cor[3], 170)), width=max(2, w - 4)))
    _linha_dupla(caneta, lambda c, cor, w: c.ellipse((256, 256, 768, 768), outline=cor, width=w))
    _linha_dupla(caneta, lambda c, cor, w: c.line((512, 512, 880, 512), fill=cor, width=w))
    caneta.polygon(((900, 512), (860, 488), (860, 536)), fill=(20, 20, 26, 230))
    caneta.polygon(((892, 512), (865, 496), (865, 528)), fill=(255, 255, 255, 235))
    caneta.ellipse((502, 502, 522, 522), fill=(255, 255, 255, 235), outline=(20, 20, 26, 230), width=4)
    grande, pequena = _fonte(46), _fonte(30)
    _texto_duplo(caneta, (28, 22), f"Gabarito: {nome_da_parte(parte)}", grande)
    _texto_duplo(caneta, (790, 545), "olhando", pequena)
    _texto_duplo(caneta, (790, 580), "para →", pequena)
    _texto_duplo(caneta, (28, 900), "O círculo é o corpo (512 px). Desenhe no lugar certo,", pequena)
    _texto_duplo(caneta, (28, 940), "com fundo transparente, e apague estas linhas.", pequena)
    if parte in DESCRICAO_DA_ZONA:
        _texto_duplo(caneta, (28, 84), DESCRICAO_DA_ZONA[parte], pequena, (255, 214, 90, 255))
    return _png_bytes(imagem)


def _png_bytes(imagem: Image.Image) -> bytes:
    saida = io.BytesIO()
    imagem.save(saida, "PNG", optimize=True)
    return saida.getvalue()


# ---------------------------------------------------------- artes antigas
def _ajustar_circulo(pontos):
    """Circulo de minimos quadrados (Kasa): devolve (cx, cy, r)."""
    import numpy as np
    xs = pontos[:, 0].astype(float)
    ys = pontos[:, 1].astype(float)
    a = np.column_stack([xs, ys, np.ones_like(xs)])
    b = xs * xs + ys * ys
    (c1, c2, c3), *_ = np.linalg.lstsq(a, b, rcond=None)
    cx, cy = c1 / 2, c2 / 2
    return cx, cy, float(np.sqrt(max(c3 + cx * cx + cy * cy, 0.0)))


def circulo_do_miolo(peca: Image.Image) -> tuple[float, float, float] | None:
    """Acha o circulo do corpo num acessorio com miolo transparente.

    O capacete do Berserker e um anel: o miolo transparente e o lugar da
    bolinha, fechado embaixo por um arco fino.  Se existir esse arco (pixels
    opacos que encostam no miolo E no lado de fora), o circulo sai dele; se
    nao, sai da borda do miolo inteiro (um anel simples).
    """
    import numpy as np
    alfa = np.asarray(peca.getchannel("A")) > 32
    altura, largura = alfa.shape
    mascara = Image.new("L", (largura + 2, altura + 2), 255)  # borda transparente em volta
    mascara.paste(Image.fromarray(np.where(alfa, 0, 255).astype("uint8"), "L"), (1, 1))
    ImageDraw.floodfill(mascara, (0, 0), 128)
    regiao = np.asarray(mascara)[1:-1, 1:-1]
    miolo = regiao == 255
    fora = regiao == 128
    if miolo.sum() < 0.01 * altura * largura:
        return None

    # O arco: em cada coluna, a faixa opaca logo abaixo do miolo que chega
    # ao lado de fora e e fina (ate 24 px). O ponto e o meio da faixa, que e
    # a linha desenhada do corpo.
    pontos = []
    for x in range(largura):
        linhas = np.nonzero(miolo[:, x])[0]
        if not len(linhas):
            continue
        y = inicio = int(linhas.max()) + 1
        while y < altura and alfa[y, x]:
            y += 1
        espessura = y - inicio
        if 0 < espessura <= 24 and (y >= altura or fora[y, x]):
            pontos.append((x, inicio + espessura / 2.0))
    if len(pontos) >= 30:
        pontos = np.array(pontos)
        for _ in range(3):  # tira o que nao e arco (pontas do capacete)
            cx, cy, raio = _ajustar_circulo(pontos)
            erro = np.abs(np.hypot(pontos[:, 0] - cx, pontos[:, 1] - cy) - raio)
            if len(pontos[erro <= 4]) < 30:
                break
            pontos = pontos[erro <= 4]
        return _ajustar_circulo(pontos)
    ys, xs = np.nonzero(alfa & _perto(miolo, 1))
    if len(xs) < 20:
        return None
    return _ajustar_circulo(np.column_stack([xs, ys]))


def _perto(campo, raio):
    import numpy as np
    from PIL import ImageFilter
    img = Image.fromarray((campo * 255).astype("uint8"), "L").filter(ImageFilter.MaxFilter(2 * raio + 1))
    return np.asarray(img) > 0


def encaixar_no_corpo(peca: Image.Image, ancora: tuple[float, float]) -> Image.Image:
    """Poe a peca no gabarito 1024: pelo miolo quando houver, senao pela ancora."""
    circulo = circulo_do_miolo(peca)
    quadro = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    if circulo is None:
        quadro.alpha_composite(peca, (round(512 - ancora[0]), round(512 - ancora[1])))
        return quadro
    cx, cy, raio = circulo
    escala = 256.0 / raio
    nova = peca.resize((max(1, round(peca.width * escala)), max(1, round(peca.height * escala))),
                       Image.Resampling.LANCZOS)
    x, y = round(512 - cx * escala), round(512 - cy * escala)
    camada = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    camada.paste(nova, (x, y), nova)
    quadro.alpha_composite(camada)
    return quadro


ARTES_ANTIGAS = (
    # (arquivo, slot, ancora do .tscn, como encaixa)
    ("corpo_bolinha.png", "lutador/pele/comum/_/base", (256, 259), "ancora"),
    # O PNG do Berserker e um CAPACETE com chifres e miolo transparente:
    # e o acessorio de cabeca da classe, e o miolo vai em cima do corpo.
    ("classe_berserker.png", "lutador/acessorio_cabeca/classe/berserker_furia/base", (244, 234), "miolo"),
)


def _destino_do_slot(biblioteca: Path, slot_id: str) -> str:
    for manifesto in (biblioteca / "manifesto_slots.json", PADRAO):
        with contextlib.suppress(OSError, ValueError):
            for slot in json.loads(manifesto.read_text(encoding="utf-8")).get("slots", []):
                if slot.get("id") == slot_id:
                    return str(slot["destino"])
    return "palco/biblioteca/partes/" + slot_id + ".png"


def importar_antigas(biblioteca: Path = PADRAO.parent, origem: Path | None = None) -> list[Path]:
    """Copia as duas artes antigas para o gabarito, sem tocar nos originais."""
    origem = origem or RAIZ / "palco" / "biblioteca" / "efeitos" / "folhas"
    migrar_variantes(biblioteca)
    copiados = []
    for nome, slot_id, ancora, modo in ARTES_ANTIGAS:
        fonte = origem / nome
        if not fonte.is_file():
            continue
        arquivo = arquivo_do_destino(biblioteca, _destino_do_slot(biblioteca, slot_id))
        guardar_versao(arquivo)
        with Image.open(fonte) as aberta:
            peca = aberta.convert("RGBA")
        if modo == "miolo":
            quadro = encaixar_no_corpo(peca, ancora)
        else:
            quadro = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
            quadro.alpha_composite(peca, (512 - ancora[0], 512 - ancora[1]))
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = arquivo.with_suffix(".novo.png")
        quadro.save(temporario, "PNG", optimize=True)
        os.replace(temporario, arquivo)
        copiados.append(arquivo)
    return copiados


def migrar_variantes(biblioteca: Path = PADRAO.parent) -> list[Path]:
    """Move o formato anterior de lutador para v01, inclusive historico.

    Nunca sobrescreve uma v01 ja criada; assim uma segunda abertura e segura.
    """
    raiz = biblioteca / "partes" / "lutador"
    movidos = []
    if not raiz.is_dir():
        return movidos
    for arquivo in list(raiz.glob("*/*/*/*.png")):
        # antigo: parte/nivel/alvo/estado.png; novo tem um diretorio a mais.
        if arquivo.parent.parent.parent.parent != raiz:
            continue
        destino = arquivo.parent / "v01" / arquivo.name
        if destino.exists():
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        os.replace(arquivo, destino)
        antigo_historico = pasta_de_versoes(arquivo)
        novo_historico = pasta_de_versoes(destino)
        if antigo_historico.exists() and not novo_historico.exists():
            os.replace(antigo_historico, novo_historico)
        antigo_json = arquivo.with_suffix(".json")
        if antigo_json.exists() and not destino.with_suffix(".json").exists():
            os.replace(antigo_json, destino.with_suffix(".json"))
        movidos.append(destino)
    return movidos


def gerar() -> dict:
    """Importa a engine e devolve todos os slots, sem depender de banco real."""
    argv, sys.argv = sys.argv, [str(PROTOCOLO)]
    try:
        # O prototipo tambem serve de demonstracao na documentacao e imprime
        # resumo; o gerador nao pode poluir quem o importa.
        with contextlib.redirect_stdout(io.StringIO()):
            dados = runpy.run_path(str(PROTOCOLO))
    finally:
        sys.argv = argv
    slots = dados["slots"]
    for slot in slots:
        slot["rotulo"] = _rotulo(slot)
        slot["reserva"] = _reserva(slot)
        slot["obrigatorio"] = slot["papel"] == "obrigatorio"
        if slot["grupo"] in ("lutador", "camada_estado"):
            slot["tamanho_px"] = [1024, 1024]
            slot["ancora"] = "gabarito"
    resumo = dados["resumo"]
    return {"versao": 1, "resumo": resumo, "slots": slots}


def _rotulo(slot: dict) -> str:
    parte = str(slot["parte"]).replace("_", " ")
    alvo = slot["alvo"]["rotulo"]
    estado = slot["estado"]
    return " · ".join(x for x in (parte.capitalize(), alvo, "base" if estado == "base" else estado.replace("_", " ")) if x)


def _reserva(slot: dict) -> str:
    if slot["grupo"] == "lutador":
        return "desenho atual da bolinha"
    if slot["grupo"] == "camada_estado":
        return "efeito atual do jogo"
    return "desenho atual do palco"


def gravar(caminho: Path = PADRAO) -> dict:
    """Gera e troca o manifesto inteiro de uma vez, nunca um JSON pela metade."""
    manifesto = gerar()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix="manifesto-", suffix=".json", dir=caminho.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as arquivo:
            json.dump(manifesto, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
        os.replace(temporario, caminho)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(temporario)
        raise
    return manifesto


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "importar-antigas":
        args = sys.argv[2:]
        origem = Path(args[args.index("--origem") + 1]) if "--origem" in args else None
        biblioteca = Path(args[args.index("--biblioteca") + 1]) if "--biblioteca" in args else PADRAO.parent
        print("\n".join(str(p) for p in importar_antigas(biblioteca, origem)))
    else:
        saida = Path(sys.argv[1]) if len(sys.argv) > 1 else PADRAO
        manifesto = gravar(saida)
        print(json.dumps(manifesto["resumo"]["por_grupo"], ensure_ascii=False, sort_keys=True))
