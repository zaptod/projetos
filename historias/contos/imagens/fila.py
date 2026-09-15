# -*- coding: utf-8 -*-
"""Quais cenas ainda precisam de imagem, e com que prompt.

Nao existe fila em arquivo aqui: o ESTADO E O DISCO. Uma cena esta pronta
quando `outputs/<id>/cenas/cena_03.png` existe e tem tamanho de imagem. Isso
e de proposito — a fila do outro projeto precisa de arquivo porque um job
pode estar "gerando" num site por 12 minutos; aqui a geracao de imagem dura
segundos e o worker roda do comeco ao fim numa passada. Menos estado, menos
mentira possivel.

`imagens.json` guarda o que o disco nao sabe dizer: o prompt exato enviado e
a PROVA de origem daquela imagem (conta compartilhada — a mesma doutrina do
random_builds: nada entra sem prova de que a imagem e nossa).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"

# Abaixo disto nao e imagem: download truncado ou pagina de erro salva.
BYTES_MINIMOS = 10_000


def carregar_config() -> dict:
    with open(RAIZ / "config" / "imagens.json", encoding="utf-8-sig") as fh:
        return json.load(fh)


def pasta_da_historia(historia_id: str) -> Path:
    return OUTPUTS / historia_id


def estilo_do_roteiro(roteiro: dict) -> str:
    """O estilo de imagem do MOLDE daquela historia, ou `""` para usar o padrao.

    Le do `roteiro.json` da propria historia, e nao de um parametro que
    alguem lembra de passar: a fila de imagens roda em outro processo, dias
    depois de o roteiro existir, e esquecer o estilo ali daria uma historia
    caricata com metade das cenas fotorrealistas.
    """
    from ..roteiro.serie import carregar_config as _config_roteiro
    molde = str((roteiro or {}).get("estrutura") or "")
    if not molde:
        return ""
    try:
        moldes = (_config_roteiro() or {}).get("modelos") or {}
    except Exception:                                          # noqa: BLE001
        return ""
    return str((moldes.get(molde) or {}).get("estilo_imagem") or "")


def caminho_da_cena(historia_id: str, n: int, parte: int | None = None) -> Path:
    """O arquivo daquela cena.

    Numa serie o nome carrega a parte (`p03_cena_07.png`), senao a cena 7 da
    parte 3 sobrescreveria a cena 7 da parte 1. Historia de uma parte so
    mantem o nome curto — e assim as que ja existiam continuam validas.
    """
    cenas = pasta_da_historia(historia_id) / "cenas"
    if not parte or int(parte) <= 1:
        curto = cenas / f"cena_{int(n):02d}.png"
        if int(parte or 1) <= 1 and (curto.is_file() or not parte):
            return curto
    return cenas / f"p{int(parte or 1):02d}_cena_{int(n):02d}.png"


# O video e 1080x1920 (0,5625). O PicassoIA devolve 1088x1920 quando obedece
# o pedido de 9:16 — e de vez em quando devolve 1024x1024, ignorando o
# seletor. O teto e folgado de proposito: 3:4 (0,75) ainda e retrato e cabe na
# tela com um corte suave; quadrado (1,0) e paisagem nao cabem de jeito nenhum.
PROPORCAO_MAXIMA = 0.75


def vertical(caminho: Path) -> bool:
    """A imagem tem a forma que foi PEDIDA?

    Medido em 11/09/2026, na primeira historia do genero caricato: 18 cenas
    voltaram 1088x1920 e uma voltou 1024x1024. `utilizavel` so olhava o
    tamanho em bytes, entao a quadrada passou como pronta, o worker nunca
    refez, e ela entrou no video — onde o renderizador a preenche com fundo
    borrado. O resultado e uma cena com cara de outro video no meio da
    historia, sem erro nenhum em lugar nenhum.

    Mesma doutrina da prova de origem: nao basta o arquivo existir, ele
    precisa ser o que foi pedido.
    """
    try:
        from PIL import Image
        with Image.open(caminho) as imagem:
            largura, altura = imagem.size
    except Exception:                                          # noqa: BLE001
        # Ilegivel nao e o problema desta funcao — `utilizavel` ja recusa por
        # tamanho, e recusar aqui tambem esconderia a causa real.
        return True
    return bool(altura) and (largura / altura) <= PROPORCAO_MAXIMA


def proporcao_ok(caminho: Path, aspecto: str = "9:16") -> bool:
    """A imagem tem a forma que a HISTORIA pede?

    Retrato (9:16, 3:4, 2:3) continua com a regra de sempre, `vertical`.
    Quadrada (1:1, desde 14/09/2026) aceita uma folga pequena; deitada, so
    deitada. Imagem que veio no formato de outra historia seria a "cena com
    cara de outro video" que `vertical` existe para barrar.
    """
    if aspecto in ("9:16", "3:4", "2:3"):
        return vertical(caminho)
    try:
        from PIL import Image
        with Image.open(caminho) as imagem:
            largura, altura = imagem.size
    except Exception:                                          # noqa: BLE001
        return True
    if not altura:
        return False
    razao = largura / altura
    if aspecto == "1:1":
        return 0.85 <= razao <= 1.18
    return razao >= 1.2


def utilizavel(caminho: Path, aspecto: str = "9:16") -> bool:
    return (caminho.is_file() and caminho.stat().st_size >= BYTES_MINIMOS
            and proporcao_ok(caminho, aspecto))


def aspecto_da_historia(historia_id: str) -> str:
    """A proporcao das fotos daquela historia (a trava de formato decide)."""
    from ..video import formato, timeline
    try:
        cfg = timeline.carregar_config("render.json")
        return formato.resolver(historia_id, cfg,
                                pasta_da_historia(historia_id))["aspecto"]
    except Exception:                                          # noqa: BLE001
        return formato.ASPECTO_LEGADO


# O enquadramento acompanha a proporcao pedida: "vertical composition" num
# pedido 1:1 puxaria o gerador a empilhar a cena num quadro que nao e retrato.
COMPOSICAO = {
    "9:16": "vertical composition", "3:4": "vertical composition",
    "2:3": "vertical composition",
    # "one continuous photograph": em 14/09/2026 uma cena com DUAS pessoas,
    # pedida com "subject centered with room around", saiu em diptico (cada
    # uma no seu painel). O enquadramento fala de uma foto so.
    # SEM A PALAVRA "composition" (15/09/2026 00:45): com "square composition"
    # o gerador desenhou LINHAS DE GRADE (os tercos) por cima da foto na
    # historia_00012 p06_cena_09 e p06_cena_10 — o "grade de paineis" que o
    # parecer veta. "everyone fully clothed": a p06_cena_11 saiu de costas nuas
    # so com o avental. O `imagens.json` pode trocar isto sem reiniciar
    # (`composicao` por proporcao).
    "1:1": "square photo, one continuous photograph of a single scene, "
           "everyone fully clothed",
    "4:3": "horizontal composition", "3:2": "horizontal composition",
    "16:9": "horizontal composition",
}


def _sem_barra(texto) -> str:
    """ "Nome | descricao" -> "Nome, descricao", com os espacos em ordem."""
    import re
    return " ".join(re.sub(r"\s*\|\s*", ", ", str(texto or "")).split())


def _descreve_alguem_do_elenco(texto: str, elenco: str) -> bool:
    """A cena ja traz a descricao fisica de alguem do elenco ("Nome | descricao;
    ...")? Compara o comeco de cada descricao, sem o nome."""
    baixo = " ".join(str(texto or "").lower().split())
    for pessoa in str(elenco or "").split(";"):
        descricao = pessoa.split("|", 1)[-1]
        nucleo = " ".join(descricao.lower().split())[:30].strip(" ,.")
        if len(nucleo) >= 15 and nucleo in baixo:
            return True
    return False


def prompt_da_cena(cena: dict, config: dict | None = None,
                   protagonista: str = "", estilo: str = "",
                   elenco: str = "") -> str:
    """O prompt que vai para o PicassoIA: cena + estilo + proibicoes.

    O estilo entra em TODAS as cenas: e ele que faz doze imagens parecerem do
    mesmo filme. `protagonista` e a descricao fisica curta repetida quando a
    cena esqueceu de repeti-la (a consistencia da pessoa vem do texto, porque
    este modelo nao aceita imagem de referencia).

    `estilo` sobrepoe o do `imagens.json` quando o MOLDE tem um proprio. O do
    arquivo e fotografico ("cinematic photography, shot on 35mm film,
    photorealistic") e serve ao relato confessional; aplicado a uma novela
    caricata, ele entrega gente de verdade encenando desenho — o pior dos
    dois. O molde e quem sabe qual dos dois a historia e.
    """
    config = config or carregar_config()
    # O roteiro escreve cada personagem como "Nome | descricao". Com DUAS
    # pessoas na cena a barra vira "A | B", que o gerador le como folha de
    # personagens e desenha em dois paineis (historia_00012 p01_cena_03,
    # 14/09/2026). A virgula diz a mesma coisa sem sugerir divisao.
    partes = [_sem_barra(cena.get("imagem")).strip().rstrip(".")]
    # CENA QUE JA DESCREVE UM PERSONAGEM ("Nome | descricao") NAO GANHA A
    # DESCRICAO DO PROTAGONISTA. Em 15/09/2026, na historia_00012, as cenas so
    # do Beto ("Black man...") recebiam a da Rosa no fim ("Brown-skinned
    # Latina..."), o gerador misturava as duas e o Beto saia de pele clara; o
    # Gemini tomou esse Beto como o certo e passou a vetar as cenas CERTAS.
    # O mesmo vale para a cena que descreve alguem do elenco SEM a barra
    # ("Black man, early 30s..."), que e como o roteiro escreve nas partes 4 a 6.
    ja_descreve = ("|" in str(cena.get("imagem") or "")
                   or _descreve_alguem_do_elenco(cena.get("imagem"), elenco))
    if protagonista and not ja_descreve and config.get("reforco_consistencia", True):
        # Mesma troca da barra que a cena: senao a descricao, que o roteiro
        # tambem escreve com "|", nunca casaria e sairia repetida.
        alvo = _sem_barra(protagonista).strip().rstrip(".")
        if alvo and alvo.lower() not in partes[0].lower():
            partes.append(alvo)
    partes.append(str(estilo or config.get("estilo") or "").strip().rstrip("."))
    aspecto = str(config.get("aspect") or "9:16")
    composicao = ((config.get("composicao") or {}).get(aspecto)
                  or COMPOSICAO.get(aspecto))
    if composicao and composicao.lower() not in ", ".join(partes).lower():
        partes.append(composicao)
    negativo = str(config.get("negativo") or "").strip()
    if negativo:
        partes.append(negativo.rstrip("."))
    texto = ", ".join(p for p in partes if p)
    teto = int(config.get("prompt_max_chars", 900))
    if len(texto) > teto:
        # Corta na virgula anterior ao teto: cortar no meio de uma clausula
        # deixa o prompt com metade de uma ideia.
        corte = texto.rfind(",", 0, teto)
        texto = texto[:corte if corte > teto * 0.5 else teto].strip().rstrip(",")
    return texto


def _meta(historia_id: str) -> dict:
    caminho = pasta_da_historia(historia_id) / "imagens.json"
    try:
        with open(caminho, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def registrar(historia_id: str, n: int, *, prompt: str, arquivo: Path,
              prova: dict | None = None, url: str = "",
              parte: int = 1, nivel: int | str = 0) -> None:
    """Anota prompt e prova daquela cena (append idempotente por cena).

    `nivel` registra qual foi o tratamento: 0 (original), 1-3 (suavizacao
    mecanica), ou "llm 1"/"llm 2" (reescrita com LLM). Importa saber qual
    dos dois passou a cena, porque muda o que a imagem mostra.
    """
    caminho = pasta_da_historia(historia_id) / "imagens.json"
    dados = _meta(historia_id)
    chave = f"{int(parte)}:{int(n)}"
    # `nivel` pode ser int ou str ("llm 1", etc). Se for 0 ou falsy, vira None.
    nivel_para_salvar = nivel if nivel else None
    dados.setdefault("cenas", {})[chave] = {
        "prompt": prompt,
        "arquivo": Path(arquivo).name,
        "url": url,
        "suavizacao": nivel_para_salvar,
        "prova": {"comprovada": bool((prova or {}).get("comprovada")),
                  "forca": (prova or {}).get("forca"),
                  "motivo": (prova or {}).get("motivo")} if prova else None,
    }
    # A cena passou: se estava marcada como recusada, deixa de estar.
    (dados.get("recusadas") or {}).pop(chave, None)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)


def registrar_recusa(historia_id: str, n: int, *, parte: int = 1,
                     motivo: str = "", prompt: str = "",
                     ultima_tentativa: str = "") -> None:
    """Marca a cena que o filtro de conteudo barrou ate o ultimo nivel.

    Fica no mesmo arquivo das cenas boas para o painel poder mostrar "esta
    aqui falta imagem, e o motivo foi este" — sem isso a cena reaparece como
    simples pendencia e ninguem descobre por que nunca gera.
    """
    caminho = pasta_da_historia(historia_id) / "imagens.json"
    dados = _meta(historia_id)
    dados.setdefault("recusadas", {})[f"{int(parte)}:{int(n)}"] = {
        "motivo": str(motivo)[:400], "prompt": prompt,
        # A ultima versao tentada (a reescrita do LLM, quando houve): serve
        # para voce ver o que ja foi tentado antes de mexer no roteiro.
        "ultima_tentativa": ultima_tentativa or prompt,
        "quando": datetime.now().isoformat(timespec="seconds"),
    }
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)


def recusadas(historia_id: str) -> dict:
    """Cenas barradas pelo filtro: {"parte:cena": {motivo, prompt, quando}}."""
    return dict((_meta(historia_id).get("recusadas") or {}))


def estado(historia_id: str, roteiro: dict | None = None,
           parte: int | None = None) -> list[dict]:
    """Uma linha por cena (de toda a historia, ou so de uma parte)."""
    if roteiro is None:
        from ..roteiro import roteiro as R
        roteiro = R.carregar(historia_id)
    else:
        from ..roteiro import roteiro as R
        roteiro = R.normalizar(dict(roteiro))
    meta = _meta(historia_id).get("cenas", {})
    serie = bool(roteiro.get("serie"))
    aspecto = aspecto_da_historia(historia_id)
    saida = []
    for bloco in roteiro["partes"]:
        if parte is not None and int(bloco["n"]) != int(parte):
            continue
        for cena in bloco["cenas"]:
            numero_parte = bloco["n"] if serie else None
            caminho = caminho_da_cena(historia_id, cena["n"], numero_parte)
            registro = meta.get(f"{bloco['n']}:{cena['n']}") or \
                (meta.get(str(cena["n"])) if bloco["n"] == 1 else None) or {}
            saida.append({
                "parte": bloco["n"],
                "n": cena["n"],
                "imagem": cena.get("imagem", ""),
                "arquivo": caminho,
                "pronta": utilizavel(caminho, aspecto),
                "prompt_enviado": registro.get("prompt", ""),
                "prova": registro.get("prova"),
            })
    return saida


def pendentes(historia_id: str, roteiro: dict | None = None,
              parte: int | None = None) -> list[dict]:
    return [l for l in estado(historia_id, roteiro, parte) if not l["pronta"]]


def resumo(historia_id: str, roteiro: dict | None = None,
           parte: int | None = None) -> dict:
    linhas = estado(historia_id, roteiro, parte)
    prontas = [l for l in linhas if l["pronta"]]
    return {"total": len(linhas), "prontas": len(prontas),
            "faltam": len(linhas) - len(prontas),
            "completa": bool(linhas) and len(prontas) == len(linhas)}


def resumo_por_parte(historia_id: str, roteiro: dict | None = None) -> list[dict]:
    """Uma linha por parte: quantas imagens dela ja existem."""
    if roteiro is None:
        from ..roteiro import roteiro as R
        roteiro = R.carregar(historia_id)
    saida = []
    for bloco in roteiro.get("partes") or []:
        dados = resumo(historia_id, roteiro, bloco["n"])
        dados["parte"] = bloco["n"]
        saida.append(dados)
    return saida
