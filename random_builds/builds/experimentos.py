# -*- coding: utf-8 -*-
"""Experimentos: uma mudanca de cada vez, medida contra o proprio canal.

O problema que isto resolve e velho e caro: toda mudanca de edicao ate agora
foi PALPITE. Trocou-se o volume da trilha, a velocidade da voz, o formato do
video — e a unica prova era a impressao de quem assistiu. Quando o numero
finalmente aparecia, ele nao sabia dizer de QUAL mudanca veio, porque duas
ou tres tinham entrado juntas.

O desenho, entao, e todo sobre atribuicao:

    experimento   uma pergunta ("a trilha instrumental muda a retencao?")
    braco         uma resposta possivel, com o AJUSTE que a produz
    atribuicao    qual braco cada video recebeu, gravado no ato
    resultado     o cruzamento com a metrica, ja separado por braco

Tres regras que parecem detalhe e nao sao:

1. UM experimento em curso por canal. Dois ao mesmo tempo confundem: se a
   trilha e a voz mudam juntas, nenhum numero no fim responde por qual das
   duas. A funcao `ativar` recusa o segundo.

2. RODIZIO, nao periodo. Rodar o braco A uma semana e o B na seguinte parece
   mais simples, mas mistura a mudanca com tudo o que muda no tempo: o canal
   cresce, o horario varia, o YouTube muda a vitrine. Alternando video a
   video, essas forcas caem igualmente nos dois lados.

3. O ajuste mora no BRACO, em chaves pontilhadas do config de render
   (`audio.trilha_procedural`). Assim o experimento nao precisa de codigo
   novo para cada hipotese, e `aplicar` e um no-op exato quando nao ha nada
   em curso — que e o estado normal da producao.

O que este modulo NAO faz, de proposito: estatistica. Com 8 videos por dia e
views em um digito, qualquer p-valor aqui seria teatro. Ele mostra n, a
diferenca e um rotulo honesto de confianca, e deixa a leitura com o dono.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "outputs" / "_experimentos"
REGISTRO = PASTA / "experimentos.json"
ATRIBUICOES = PASTA / "atribuicoes.jsonl"
# Qual braco cada PRODUCAO recebeu, pela identidade estavel dela (o
# `historia_id`). E o que faz um re-render manter a trilha da primeira vez em
# vez de sortear outra e trocar o som do video pelo meio.
PRODUCOES = PASTA / "producoes.json"

CANAIS = ("historias", "builds")
ESTADOS = ("rascunho", "rodando", "encerrado")

# Duas naturezas de pergunta, e a diferenca entre elas e quem decide o braco:
#
#   ajuste         o experimento MUDA a producao e sorteia quem recebe o que.
#                  E o unico jeito de responder "e se a trilha fosse outra?",
#                  porque a outra trilha ainda nao existe em video nenhum.
#   observacional  o experimento nao muda nada: agrupa o que JA foi medido por
#                  um campo que ja varia (formato, variante do gancho, perfil).
#                  Responde hoje, com os videos que ja estao no ar, e nao corre
#                  risco nenhum na producao.
#
# Comecar tudo como "ajuste" seria desperdicio: metade das perguntas que ele
# faz ja tem resposta no disco.
TIPOS = ("ajuste", "observacional")
# Os campos do registro de metrica que fazem sentido como eixo.
CAMPOS_OBSERVAVEIS = {
    "origem": "formato do video (duelo, build, estreia)",
    "variante": "variante do gancho (A/B)",
    "perfil": "perfil de render (celular, normal)",
}

# Abaixo disto por braco, a diferenca nao se distingue de sorte. Nao e um
# teste de hipotese — e um piso para nao chamar de resultado o que ainda e
# ruido. Medido no proprio canal: videos vizinhos no mesmo dia ja variam 3x
# em views sem mudanca nenhuma.
MINIMO_POR_BRACO = 6
MINIMO_CONFIANTE = 15
# Diferenca relativa abaixo da qual nao vale nem falar em indicio.
DIFERENCA_MINIMA = 0.15


class ExperimentoInvalido(ValueError):
    """A definicao nao fecha — antes de gravar, e nao depois de produzir."""


# --------------------------------------------------------------- persistencia
def carregar() -> dict:
    if not REGISTRO.is_file():
        return {}
    try:
        with open(REGISTRO, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar(dados: dict) -> None:
    PASTA.mkdir(parents=True, exist_ok=True)
    with open(REGISTRO, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)


def listar(canal: str | None = None, estado: str | None = None) -> list[dict]:
    """Os experimentos, mais novo primeiro."""
    saida = []
    for chave, exp in carregar().items():
        if canal and exp.get("canal") != canal:
            continue
        if estado and exp.get("estado") != estado:
            continue
        saida.append({**exp, "id": chave})
    saida.sort(key=lambda e: str(e.get("criado") or ""), reverse=True)
    return saida


def em_curso(canal: str) -> dict | None:
    """O experimento de AJUSTE rodando naquele canal, ou None. No maximo um.

    Observacionais nao entram: eles nao mexem na producao, entao dez ao mesmo
    tempo nao se atrapalham — cada um so olha um campo de um jeito diferente.
    """
    rodando = [e for e in listar(canal, "rodando")
               if e.get("tipo", "ajuste") == "ajuste"]
    return rodando[0] if rodando else None


# ------------------------------------------------------------------ definicao
def _limpar_bracos(bracos) -> list[dict]:
    limpos = []
    for bruto in bracos or []:
        nome = str((bruto or {}).get("nome") or "").strip()
        if not nome:
            raise ExperimentoInvalido("todo braco precisa de nome.")
        ajuste = (bruto or {}).get("ajuste") or {}
        if not isinstance(ajuste, dict):
            raise ExperimentoInvalido(
                f"o ajuste do braco {nome!r} tem que ser um dicionario de "
                "chave pontilhada para valor.")
        if nome in {b["nome"] for b in limpos}:
            raise ExperimentoInvalido(f"dois bracos chamados {nome!r}.")
        limpos.append({"nome": nome, "ajuste": dict(ajuste)})
    if len(limpos) < 2:
        raise ExperimentoInvalido(
            "um experimento precisa de pelo menos DOIS bracos — com um so "
            "nao ha contra o que comparar.")
    return limpos


def criar(nome: str, pergunta: str, canal: str, bracos: list | None = None, *,
          tipo: str = "ajuste", campo: str = "") -> dict:
    """Nasce em rascunho: nada entra em producao sem um `ativar` explicito."""
    if canal not in CANAIS:
        raise ExperimentoInvalido(f"canal desconhecido: {canal!r}")
    if tipo not in TIPOS:
        raise ExperimentoInvalido(f"tipo desconhecido: {tipo!r}")
    if not str(nome or "").strip():
        raise ExperimentoInvalido("o experimento precisa de um nome.")
    if tipo == "observacional":
        if campo not in CAMPOS_OBSERVAVEIS:
            raise ExperimentoInvalido(
                f"{campo!r} nao e um campo observavel — use um de: "
                f"{', '.join(sorted(CAMPOS_OBSERVAVEIS))}.")
        bracos = []
    else:
        bracos = _limpar_bracos(bracos)
    dados = carregar()
    numero = 1 + max((int(c.split("_")[-1]) for c in dados if "_" in c),
                     default=0)
    chave = f"exp_{numero:04d}"
    dados[chave] = {
        "nome": str(nome).strip(),
        "pergunta": str(pergunta or "").strip(),
        "canal": canal,
        "tipo": tipo,
        "campo": campo if tipo == "observacional" else "",
        "estado": "rascunho",
        "criado": datetime.now().isoformat(timespec="seconds"),
        "encerrado": None,
        "bracos": bracos,
        "proximo": 0,
        "veredito": "",
    }
    _gravar(dados)
    return {**dados[chave], "id": chave}


def editar(exp_id: str, *, nome=None, pergunta=None, bracos=None) -> dict:
    """So o que nao invalida o que ja foi medido.

    Os bracos so mudam enquanto ninguem recebeu atribuicao: trocar o ajuste
    de um braco no meio faria dois videos diferentes carregarem o mesmo
    rotulo, e o resultado somaria laranja com banana sem avisar.
    """
    dados = carregar()
    exp = dados.get(exp_id)
    if exp is None:
        raise ExperimentoInvalido(f"experimento {exp_id!r} nao existe.")
    if nome is not None:
        exp["nome"] = str(nome).strip()
    if pergunta is not None:
        exp["pergunta"] = str(pergunta).strip()
    if bracos is not None:
        if atribuicoes(exp_id):
            raise ExperimentoInvalido(
                "este experimento ja tem video atribuido: mexer nos bracos "
                "agora misturaria dois ajustes sob o mesmo rotulo. Encerre e "
                "crie outro.")
        exp["bracos"] = _limpar_bracos(bracos)
        exp["proximo"] = 0
    _gravar(dados)
    return {**exp, "id": exp_id}


def ativar(exp_id: str) -> dict:
    dados = carregar()
    exp = dados.get(exp_id)
    if exp is None:
        raise ExperimentoInvalido(f"experimento {exp_id!r} nao existe.")
    corrente = em_curso(exp["canal"])
    if (exp.get("tipo", "ajuste") == "ajuste"
            and corrente is not None and corrente["id"] != exp_id):
        raise ExperimentoInvalido(
            f"{corrente['nome']!r} ja esta rodando em {exp['canal']}. Dois ao "
            "mesmo tempo se confundem: nenhum numero no fim diria de qual "
            "mudanca veio. Encerre aquele primeiro.")
    exp["estado"] = "rodando"
    _gravar(dados)
    return {**exp, "id": exp_id}


def encerrar(exp_id: str, veredito: str = "") -> dict:
    dados = carregar()
    exp = dados.get(exp_id)
    if exp is None:
        raise ExperimentoInvalido(f"experimento {exp_id!r} nao existe.")
    exp["estado"] = "encerrado"
    exp["encerrado"] = datetime.now().isoformat(timespec="seconds")
    exp["veredito"] = str(veredito or "").strip()
    _gravar(dados)
    return {**exp, "id": exp_id}


def apagar(exp_id: str) -> bool:
    """So rascunho. O que ja produziu video fica como historico."""
    dados = carregar()
    exp = dados.get(exp_id)
    if exp is None:
        return False
    if atribuicoes(exp_id):
        raise ExperimentoInvalido(
            "ja ha video produzido sob este experimento — apagar apagaria a "
            "explicacao dele. Encerre em vez de apagar.")
    del dados[exp_id]
    _gravar(dados)
    return True


# ------------------------------------------------------------------ producao
def _com_ajuste(config: dict, ajuste: dict) -> dict:
    """Copia do config com as chaves pontilhadas trocadas.

    Copia, e nao mutacao: o `render_config` do Pipeline e lido por varias
    etapas e por varias partes da mesma historia. Mexer nele no lugar faria o
    braco vazar para o video seguinte, que e justamente o erro que destruiria
    a atribuicao sem deixar rastro.
    """
    saida = json.loads(json.dumps(config))
    for caminho, valor in (ajuste or {}).items():
        partes = str(caminho).split(".")
        alvo = saida
        for pedaco in partes[:-1]:
            proximo = alvo.get(pedaco)
            if not isinstance(proximo, dict):
                proximo = {}
                alvo[pedaco] = proximo
            alvo = proximo
        alvo[partes[-1]] = valor
    return saida


def sortear(canal: str) -> dict | None:
    """O proximo braco do rodizio daquele canal, ou None se nada roda.

    AVANCA o contador e grava: e a chamada que consome a vez. Quem so quer
    olhar usa `em_curso`.
    """
    dados = carregar()
    for chave, exp in dados.items():
        if exp.get("canal") != canal or exp.get("estado") != "rodando":
            continue
        if exp.get("tipo", "ajuste") != "ajuste":
            continue
        bracos = exp.get("bracos") or []
        if not bracos:
            return None
        indice = int(exp.get("proximo") or 0) % len(bracos)
        exp["proximo"] = (indice + 1) % len(bracos)
        _gravar(dados)
        return {"experimento": chave, "nome_experimento": exp.get("nome", ""),
                "braco": bracos[indice]["nome"],
                "ajuste": dict(bracos[indice].get("ajuste") or {})}
    return None


def _producoes() -> dict:
    if not PRODUCOES.is_file():
        return {}
    try:
        with open(PRODUCOES, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def braco_da_producao(canal: str, chave: str) -> dict | None:
    """O braco que ESTA producao ja recebeu, ou None se e a primeira vez."""
    if not chave:
        return None
    return _producoes().get(f"{canal}/{chave}")


def _fixar_producao(canal: str, chave: str, marca: dict) -> None:
    dados = _producoes()
    dados[f"{canal}/{chave}"] = marca
    PASTA.mkdir(parents=True, exist_ok=True)
    with open(PRODUCOES, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)


def aplicar(canal: str, config: dict,
            chave: str = "") -> tuple[dict, dict | None]:
    """`(config, marca)`. Sem experimento em curso devolve o config INTACTO.

    Este e o unico ponto de contato com a producao, e ele e desenhado para
    ser inerte: nenhum experimento rodando e o caminho normal, e nele nada
    e copiado, nada e gravado e nada muda.

    `chave` e a identidade ESTAVEL da producao (o `historia_id`), e ela e o
    que torna o experimento valido. Sem ela, medido em 11/09/2026 na
    `historia_00008`:

        15:22  trilha atual   p01     (primeira renderizacao)
        15:28  trilha atual   p02
        15:29  instrumental   p01     (re-render: sorteou de NOVO)
        15:34  trilha atual   p01
        15:40  trilha atual   p02

    O mesmo video com dois bracos, e o contador do rodizio queimado tres
    vezes por uma historia so. Re-renderizar uma parte (porque uma imagem foi
    refeita, por exemplo) e rotina — e cada re-render sorteava outra vez,
    trocava a trilha do video e desalinhava o rodizio dos videos seguintes.

    Uma producao pertence a UM braco, da primeira renderizacao ate sempre.
    """
    marca = braco_da_producao(canal, chave)
    if marca is not None:
        # Ja sorteado: nao consome a vez do rodizio de novo.
        return _com_ajuste(config, marca.get("ajuste") or {}), marca
    marca = sortear(canal)
    if marca is None:
        return config, None
    if chave:
        _fixar_producao(canal, chave, marca)
    return _com_ajuste(config, marca["ajuste"]), marca


def atribuir(marca: dict | None, video_id: str) -> dict | None:
    """Grava que ESTE video saiu daquele braco. Nunca derruba a producao."""
    if not marca or not video_id:
        return None
    linha = {
        "quando": datetime.now().isoformat(timespec="seconds"),
        "experimento": marca.get("experimento"),
        "braco": marca.get("braco"),
        "video_id": str(video_id),
    }
    try:
        PASTA.mkdir(parents=True, exist_ok=True)
        with open(ATRIBUICOES, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except OSError as exc:                                    # pragma: no cover
        print(f"[experimento] nao gravei a atribuicao: {exc}")
        return None
    return linha


def atribuicoes(exp_id: str | None = None) -> list[dict]:
    if not ATRIBUICOES.is_file():
        return []
    saida = []
    with open(ATRIBUICOES, encoding="utf-8") as fh:
        for linha in fh:
            linha = linha.strip()
            if not linha:
                continue
            try:
                dado = json.loads(linha)
            except ValueError:
                continue
            if exp_id and dado.get("experimento") != exp_id:
                continue
            saida.append(dado)
    return saida


def marcar_a_mao(exp_id: str, braco: str, video_ids: list) -> int:
    """Rotula video JA publicado — para comparar o que a producao nao dividiu.

    Serve para a pergunta feita depois do fato ("os que tinham trilha
    renderam mais?"). O rotulo e o mesmo do rodizio, entao o resultado le os
    dois do mesmo jeito.
    """
    dados = carregar()
    exp = dados.get(exp_id)
    if exp is None:
        raise ExperimentoInvalido(f"experimento {exp_id!r} nao existe.")
    nomes = {b["nome"] for b in exp.get("bracos") or []}
    if braco not in nomes:
        raise ExperimentoInvalido(
            f"{braco!r} nao e um braco de {exp.get('nome')!r} "
            f"(tem: {', '.join(sorted(nomes)) or 'nenhum'}).")
    ja = {a["video_id"] for a in atribuicoes(exp_id)}
    marca = {"experimento": exp_id, "braco": braco}
    quantos = 0
    for video_id in video_ids or []:
        if not video_id or video_id in ja:
            continue
        if atribuir(marca, video_id):
            ja.add(video_id)
            quantos += 1
    return quantos


# ----------------------------------------------------------------- resultado
def _metricas_por_video(canal: str) -> dict:
    """`video_id do catalogo` -> metrica do YouTube daquele video.

    O ledger e o unico lugar que liga o mp4 ao id do YouTube. Videos
    publicados pelo navegador ficam sem esse id ate `metricas.reconciliar`
    casar pelo titulo — antes disso eles simplesmente nao aparecem aqui, que
    e o certo: e melhor um braco com n=0 visivel do que um numero montado em
    cima de metade dos videos sem dizer.
    """
    from .publicar import metricas as m
    por_youtube = {d.get("youtube_id"): d for d in m.carregar_salvas(canal)
                   if d.get("youtube_id")}
    saida = {}
    for linha in m.publicados(canal):
        if linha.get("plataforma", "youtube") != "youtube":
            continue
        dado = por_youtube.get(linha.get("youtube_id"))
        if dado and linha.get("video_id"):
            saida[linha["video_id"]] = dado
    return saida


def _agrupar_por_campo(medidas: dict, campo: str) -> dict:
    """Os bracos saem dos VALORES que o campo ja tem no disco.

    Sem atribuicao nenhuma: quem decidiu foi a producao passada. E por isso
    que um observacional responde no mesmo dia em que e criado.
    """
    grupos: dict = {}
    for video_id, dado in medidas.items():
        valor = dado.get(campo)
        nome = str(valor) if valor not in (None, "") else "(sem valor)"
        grupos.setdefault(nome, []).append(video_id)
    return grupos


def _mediana(valores: list) -> float | None:
    limpos = sorted(v for v in valores if v is not None)
    if not limpos:
        return None
    meio = len(limpos) // 2
    if len(limpos) % 2:
        return float(limpos[meio])
    return (limpos[meio - 1] + limpos[meio]) / 2.0


def _media(valores: list) -> float | None:
    limpos = [v for v in valores if v is not None]
    return sum(limpos) / len(limpos) if limpos else None


def _confianca(bracos: list, chave: str) -> tuple[str, str]:
    """Rotulo honesto: o que estes numeros permitem dizer, e nada alem.

    A leitura e sobre os DOIS PRIMEIROS bracos, nao sobre todos. Com quatro
    formatos no eixo, um deles com um video so, olhar o minimo global dizia
    "insuficiente" mesmo quando os dois do topo tinham 32 e 10 videos e uma
    diferenca de 6x. O que o dono compara e o primeiro contra o segundo.
    """
    medidos = [b for b in bracos if b["medidos"] and b[chave] is not None]
    if len(medidos) < 2:
        return "sem dados", ("ainda nao ha video medido nos dois lados — "
                             "publique e rode a atualizacao de metricas.")
    primeiro, segundo = medidos[0], medidos[1]
    menor = min(primeiro["medidos"], segundo["medidos"])
    alto, baixo = primeiro[chave], segundo[chave]
    diferenca = abs(alto - baixo) / alto if alto else 0.0
    entre = f"{primeiro['nome']} x {segundo['nome']}"
    if menor < MINIMO_POR_BRACO:
        return "insuficiente", (
            f"{entre}: so {menor} video(s) no menor dos dois; abaixo de "
            f"{MINIMO_POR_BRACO} a diferenca nao se separa de sorte.")
    if diferenca < DIFERENCA_MINIMA:
        return "empate", (
            f"{entre} ficaram a {diferenca * 100:.0f}% um do outro — perto "
            "demais para chamar de efeito.")
    if menor < MINIMO_CONFIANTE:
        return "indicio", (
            f"{entre}: {diferenca * 100:.0f}% de diferenca com {menor} "
            f"video(s) no menor. Vale continuar ate {MINIMO_CONFIANTE}.")
    return "claro", (
        f"{entre}: {diferenca * 100:.0f}% de diferenca com {menor}+ videos "
        "de cada lado.")


def resultado(exp_id: str, chave: str = "retencao") -> dict:
    """O cruzamento, ja separado por braco.

    `chave` e a metrica que decide: `retencao` (media percentual assistida) ou
    `views_por_dia` (normaliza a idade — video de ontem nao perde para um de
    um mes atras so por ter existido menos tempo).
    """
    dados = carregar()
    exp = dados.get(exp_id)
    if exp is None:
        raise ExperimentoInvalido(f"experimento {exp_id!r} nao existe.")
    canal = exp.get("canal") or "builds"
    medidas = _metricas_por_video(canal)
    if exp.get("tipo", "ajuste") == "observacional":
        por_braco = _agrupar_por_campo(medidas, exp.get("campo") or "origem")
    else:
        por_braco = {b["nome"]: [] for b in exp.get("bracos") or []}
        # UMA atribuicao por video, e vale a ULTIMA. Re-renderizar uma parte
        # (por causa de uma imagem refeita, por exemplo) grava outra linha
        # para o mesmo `video_id` — e o arquivo que existe no disco saiu do
        # braco da ultima passada, nao da primeira. Somando as duas, o mesmo
        # video contaria em dois bracos ao mesmo tempo e inflaria `medidos`
        # dos dois lados, sem nenhum erro no caminho.
        ultima = {}
        for linha in atribuicoes(exp_id):
            ultima[linha["video_id"]] = linha.get("braco")
        for video_id, braco in ultima.items():
            por_braco.setdefault(braco, []).append(video_id)

    bracos = []
    for nome, ids in por_braco.items():
        vistos = [medidas[i] for i in ids if i in medidas]
        bracos.append({
            "nome": nome,
            "videos": len(ids),
            "medidos": len(vistos),
            "views": sum(int(d.get("views") or 0) for d in vistos),
            "views_por_dia": _mediana([d.get("views_por_dia") for d in vistos]),
            "retencao": _media([d.get("media_percentual") for d in vistos
                                if d.get("media_percentual")]),
            "ids": ids,
        })
    bracos.sort(key=lambda b: (b[chave] is None, -(b[chave] or 0)))
    rotulo, recado = _confianca(bracos, chave)
    return {"id": exp_id, "nome": exp.get("nome", ""),
            "pergunta": exp.get("pergunta", ""), "canal": canal,
            "tipo": exp.get("tipo", "ajuste"), "campo": exp.get("campo", ""),
            "estado": exp.get("estado"), "veredito": exp.get("veredito", ""),
            "metrica": chave, "bracos": bracos,
            "confianca": rotulo, "leitura": recado}


__all__ = [
    "ExperimentoInvalido", "aplicar", "ativar", "atribuicoes", "atribuir",
    "carregar", "criar", "editar", "em_curso", "encerrar", "apagar", "listar",
    "marcar_a_mao", "resultado", "sortear",
]
