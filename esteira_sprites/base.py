"""Sprite-base: o desenho parado de onde saem as folhas animadas.

14/10/2026, o Adrian: "gerar um sprite base para pegar o estilo certo e a
partir desse sprite base fazer as variacoes em sprite sheet das animacoes".
Antes, cada folha era pedida do zero, sem anexo: o mesmo habitante saia com
outra forma em cada animacao. Agora:

1. todo pedido de imagem anexa a imagem-mestra (o ESTILO; `pedir.py`);
2. toda folha tem um BASE: o personagem/objeto parado, um desenho so;
3. a folha so e pedida depois que o base dela esta pronto, e o pedido anexa a
   mestra E o base ("desenhe EXATAMENTE este personagem");
4. o juiz da folha recebe o base e responde se o personagem e o mesmo.

De quem e a folha (`id_do_base`), nesta ordem:
- campo `base` explicito no item do inventario;
- habitantes da Vila: o personagem e o `subgrupo` (as 7 folhas de cada IA) ->
  `habitante_<subgrupo>_base`;
- a PECA parada do mesmo objeto no inventario (o nome do arquivo da folha
  comeca pelo da peca: `cenario/arvore_vento.png` -> `cenario/arvore.png`);
- senao, um base derivado so dessa folha: `<id da folha>_base` (no palco, o
  quadro-chave do efeito).

Os bases derivados NAO estao no JSON do inventario (o Atelie e a Vila leem o
JSON e veriam pecas que nao existem): `config.itens()` os acrescenta.

De onde vem o desenho do base de uma folha (`referencia`), nesta ordem:
1. o Atelie: qualquer folha que o Adrian subiu para a mesma peca (o primeiro
   quadro dela) -- o que ele fez manda;
2. o que o Adrian aprovou: o base aprovado, ou uma folha irma (mesmo
   personagem) aprovada -- o primeiro quadro; ou a peca do objeto que ja
   esta na biblioteca sem ficha;
3. o base que o JUIZ aprovou (`juiz_aprovou`): ficha em `a_conferir` com a
   ultima tentativa do fluxo novo, veredito sem defeito grave e portao limpo.
   Nao espera o Adrian: ele aprova o base e as folhas juntos na conferencia.
"""
from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

from PIL import Image

# Marca das tentativas pedidas no fluxo novo (mestra anexada; folha com base).
# Ficha em producao sem ela e do fluxo antigo: o `ciclo` refaz (`__main__.py`).
FLUXO = "base_v1"
SUFIXO = "_base"
APROVADO_PELO_ADRIAN = ("aprovado", "na_biblioteca")


ORIGEM_TXT = {"atelie": "1º quadro do que o Adrian fez no Ateliê",
              "aprovado_pelo_adrian": "aprovado pelo Adrian",
              "folha_aprovada_pelo_adrian": "1º quadro da folha aprovada pelo Adrian",
              "biblioteca": "a peça já na biblioteca",
              "juiz": "aprovado pelo juiz"}


class BaseFaltando(ValueError):
    """A folha ainda nao tem base pronto: nao se pede."""


def _nome(item: dict) -> str:
    return str(item.get("nome_arquivo") or "").split(" (")[0].strip().replace("\\", "/")


def _stem(item: dict) -> str:
    return PurePosixPath(_nome(item)).stem


def e_folha(item: dict) -> bool:
    return item.get("tipo") == "folha" and not item.get("externo")


# indices por lista de itens (a mesma lista e consultada centenas de vezes num
# `lote`; guarda a lista para o `is` nao confundir com outra no mesmo endereco)
_CACHE: dict[str, tuple[list, object]] = {}


def _memo(nome: str, itens: list[dict], fazer):
    guardado = _CACHE.get(nome)
    if guardado is not None and guardado[0] is itens:
        return guardado[1]
    valor = fazer(itens)
    _CACHE[nome] = (itens, valor)
    return valor


def _stems_das_pecas(itens: list[dict]) -> list[tuple[str, str]]:
    saida = [(_stem(i), str(i["id"])) for i in itens
             if i.get("tipo") != "folha" and not i.get("externo") and not i.get("derivado")]
    return [(s, i) for s, i in saida if s]


def _peca_do_objeto(folha: dict, itens: list[dict]) -> str:
    """A peca parada cujo arquivo e o comeco do arquivo da folha (o mais longo)."""
    stem = _stem(folha)
    melhor, tamanho = "", 0
    for s, item_id in _memo("pecas", itens, _stems_das_pecas):
        if stem.startswith(s + "_") and len(s) > tamanho:
            melhor, tamanho = item_id, len(s)
    return melhor


def id_do_base(folha: dict, itens: list[dict]) -> str:
    if folha.get("base"):
        return str(folha["base"])
    if folha.get("grupo") == "habitantes" and folha.get("subgrupo"):
        return f"habitante_{folha['subgrupo']}{SUFIXO}"
    return _peca_do_objeto(folha, itens) or f"{folha['id']}{SUFIXO}"


def _prioridade(folhas: list[dict]) -> str:
    return min((str(f.get("prioridade") or "P3") for f in folhas), default="P3")


def _tamanho(folha: dict) -> str:
    original = str(folha.get("tamanho") or "").strip()
    texto = "peça parada 1024x1024, o desenho centrado, do tamanho de um quadro da folha"
    mundo = re.search(r"no mundo \d+x\d+(?: \(x\d+ no celular\))?", original)
    if mundo:
        return f"{texto}; {mundo.group(0)}"
    return f"{texto} (a folha: {original})" if original else texto


def _descricao(folhas: list[dict], perfil: str) -> str:
    primeira = folhas[0]
    desenho = str(primeira.get("descricao") or primeira["id"]).strip()
    # a folha do habitante descreve a animacao depois de "Animacao '...'": o
    # base e so o personagem, parado
    desenho = re.split(r"\s*Anima[cç][aã]o '", desenho)[0].strip().rstrip(".")
    vista = ("de frente, olhando para quem vê" if perfil == "vila"
             else "visto de cima, apontando para a direita (+x)")
    alvo = (f"todas as {len(folhas)} folhas animadas dele" if len(folhas) > 1
            else "a folha animada dele")
    return (f"SPRITE-BASE de: {desenho}. Um desenho só, PARADO, {vista}, sem quadros e sem "
            f"animação: é a referência de forma, cores, proporções e acessórios para {alvo}.")


def derivar(itens: list[dict], perfil: str = "palco") -> list[dict]:
    """Os itens base que faltam no inventario (um por personagem/objeto com folha)."""
    existentes = {str(i.get("id")) for i in itens}
    grupos: dict[str, list[dict]] = {}
    for item in itens:
        if e_folha(item):
            grupos.setdefault(id_do_base(item, itens), []).append(item)
    novos = []
    for bid, folhas in grupos.items():
        if bid in existentes:
            continue
        primeira = folhas[0]
        stem = _stem(primeira)
        if primeira.get("grupo") == "habitantes" and primeira.get("subgrupo"):
            nome = f"habitantes/{primeira['subgrupo']}/base.png"
        elif stem:
            nome = str(PurePosixPath(_nome(primeira)).with_name(f"{stem}{SUFIXO}.png"))
        else:
            nome = f"{bid}.png"
        ordens = [f["ordem"] for f in folhas if isinstance(f.get("ordem"), (int, float))]
        novo = {"id": bid, "grupo": primeira.get("grupo", ""), "subgrupo": primeira.get("subgrupo", ""),
                "tipo": "peca", "descricao": _descricao(folhas, perfil), "nome_arquivo": nome,
                "tamanho": _tamanho(primeira), "fundo": primeira.get("fundo", ""),
                "prioridade": _prioridade(folhas),
                # logo antes da primeira folha dele
                "ordem": (min(ordens) - 0.5) if ordens else None,
                "bloqueio": "", "opcional": False,
                "presenca_txt": primeira.get("presenca_txt", ""),
                "derivado": True, "base_de": [f["id"] for f in folhas],
                "notas": "Sprite-base derivado das folhas (esteira_sprites/base.py, 14/10/2026)."}
        for campo in ("chroma", "contorno"):
            if campo in primeira:
                novo[campo] = primeira[campo]
        novos.append(novo)
    return novos


def _mapa(itens: list[dict]) -> dict[str, list[str]]:
    saida: dict[str, list[str]] = {}
    for item in itens:
        if e_folha(item):
            saida.setdefault(id_do_base(item, itens), []).append(str(item["id"]))
    return saida


def mapa(itens: list[dict]) -> dict[str, list[str]]:
    """id do base -> ids das folhas que dependem dele."""
    return _memo("mapa", itens, _mapa)


# ------------------------------------------------------------- de onde vem
def juiz_aprovou(dados: dict | None) -> bool:
    """O juiz aprovou o base: `a_conferir` com o fluxo novo, sem grave e portao limpo.

    `a_conferir` sozinho nao basta: tentativas esgotadas e juiz que falhou 3x
    tambem caem la."""
    if not dados or dados.get("estado") != "a_conferir" or not dados.get("tentativas"):
        return False
    t = dados["tentativas"][-1]
    veredito = t.get("veredito")
    if t.get("fluxo") != FLUXO or not isinstance(veredito, dict) or t.get("controle"):
        return False
    if t.get("portao_reprovou"):
        return False
    graves = [d for d in veredito.get("defeitos") or [] if d.get("gravidade") == "grave"]
    return not graves and bool((t.get("caminhos") or {}).get("limpo"))


def _limpo(dados: dict | None) -> Path | None:
    if not dados or not dados.get("tentativas"):
        return None
    caminho = (dados["tentativas"][-1].get("caminhos") or {}).get("limpo")
    return Path(caminho) if caminho and Path(caminho).is_file() else None


def _folha_do_atelie(item: dict) -> Path | None:
    from . import ja_feito
    for pasta in ja_feito.pecas_no_atelie(item):
        if not pasta.is_dir():
            continue
        for folha in sorted(pasta.rglob("folha.png")):
            if "historico" not in folha.relative_to(pasta).parts:
                return folha
    return None


def referencia(folha: dict, itens: list[dict] | None = None) -> dict | None:
    """De onde vem o base desta folha agora, ou None (a folha espera)."""
    from . import config, ficha
    itens = itens if itens is not None else config.itens()
    bid = id_do_base(folha, itens)
    por_id = {str(i.get("id")): i for i in itens}
    base_item = por_id.get(bid)
    irmas = [por_id[i] for i in mapa(itens).get(bid, []) if i != folha.get("id") and i in por_id]
    # 1. o Atelie: a folha do Adrian para esta peca, para o base ou para uma irma
    for candidato in [folha] + ([base_item] if base_item else []) + irmas:
        achada = _folha_do_atelie(candidato)
        if achada:
            return {"base_id": bid, "origem": "atelie", "fonte": str(achada), "recorte": "atelie"}
    # 2. o que o Adrian aprovou: o base, ou uma folha irma (o primeiro quadro)
    dados_base = ficha.ler(bid)
    if dados_base and dados_base.get("estado") in APROVADO_PELO_ADRIAN and _limpo(dados_base):
        return {"base_id": bid, "origem": "aprovado_pelo_adrian", "fonte": str(_limpo(dados_base)),
                "recorte": "inteiro"}
    for irma in irmas:
        d = ficha.ler(irma["id"])
        if d and d.get("estado") in APROVADO_PELO_ADRIAN and _limpo(d):
            return {"base_id": bid, "origem": "folha_aprovada_pelo_adrian", "de": irma["id"],
                    "fonte": str(_limpo(d)), "recorte": "grade", "grade": _grade(irma)}
    # a peca do objeto ja esta na biblioteca sem ficha (arte que ele pos la): o
    # `lote` nunca a pede (`ja_feito`), entao sem isto as folhas dela esperariam
    # para sempre
    na_biblioteca = _na_biblioteca(base_item)
    if na_biblioteca:
        return {"base_id": bid, "origem": "biblioteca", "fonte": str(na_biblioteca), "recorte": "inteiro"}
    # 3. o base que o juiz aprovou
    if juiz_aprovou(dados_base):
        return {"base_id": bid, "origem": "juiz", "fonte": str(_limpo(dados_base)), "recorte": "inteiro"}
    return None


IMAGENS = (".png", ".webp")


def _na_biblioteca(base_item: dict | None) -> Path | None:
    """A imagem do base que ja esta na biblioteca (so imagem: a cena .tscn nao serve)."""
    if not base_item:
        return None
    from . import ja_feito
    try:
        ocupado = ja_feito.destino_ocupado(base_item)
    except (OSError, ValueError, ImportError):
        return None
    if ocupado and ocupado.suffix.lower() in IMAGENS and ocupado.is_file():
        return ocupado
    return None


def _grade(item: dict) -> list[int]:
    from . import prompt
    return list(prompt.grade(item))


# ------------------------------------------------------------- o desenho
def _primeiro_quadro(ref: dict) -> Image.Image:
    with Image.open(ref["fonte"]) as aberta:
        img = aberta.convert("RGBA")
    if ref["recorte"] == "atelie":
        meta = Path(ref["fonte"]).with_name("animacao.json")
        caixa = None
        try:
            q = json.loads(meta.read_text(encoding="utf-8"))["quadros"][0]
            caixa = (int(q["x"]), int(q["y"]), int(q["x"]) + int(q["w"]), int(q["y"]) + int(q["h"]))
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            caixa = (0, 0, img.width // 4, img.height // 4)
        img = img.crop(caixa)
    elif ref["recorte"] == "grade":
        colunas, linhas = ref.get("grade") or (4, 4)
        img = img.crop((0, 0, img.width // int(colunas), img.height // int(linhas)))
    # so o desenho, com uma margem
    caixa = img.getbbox()
    if caixa:
        img = img.crop(caixa)
    margem = max(4, round(max(img.size) * 0.08))
    tela = Image.new("RGBA", (img.width + 2 * margem, img.height + 2 * margem), (0, 0, 0, 0))
    tela.alpha_composite(img, (margem, margem))
    return tela


def preparar(folha: dict, pasta: Path, numero: int, anterior: dict | None = None) -> dict:
    """Grava o base desta tentativa na pasta da ficha e diz o que anexar.

    `base_<n>.png` (transparente: o juiz) e `base_<n>_chroma.png` (sobre o fundo
    chroma da folha: o gerador). Sem referencia agora, reaproveita o base da
    tentativa anterior (o juiz pedindo refazer); sem nenhum, `BaseFaltando`."""
    from . import prompt
    ref = referencia(folha)
    if ref is None:
        if (anterior and anterior.get("caminho") and Path(anterior["caminho"]).is_file()
                and anterior.get("anexo") and Path(anterior["anexo"]).is_file()):
            return dict(anterior, reaproveitado=True)
        raise BaseFaltando(f"{folha['id']}: a folha espera o sprite-base "
                           f"({id_do_base(folha, _itens())}) ser aprovado pelo juiz")
    pasta.mkdir(parents=True, exist_ok=True)
    desenho = _primeiro_quadro(ref)
    transparente = pasta / f"base_{numero}.png"
    desenho.save(transparente, "PNG")
    cor = prompt.fundo_do(folha)
    fundo = Image.new("RGBA", desenho.size, cor)
    fundo.alpha_composite(desenho)
    chroma = pasta / f"base_{numero}_chroma.png"
    fundo.convert("RGB").save(chroma, "PNG")
    return {**ref, "caminho": str(transparente), "anexo": str(chroma)}


def _itens() -> list[dict]:
    from . import config
    return config.itens()
