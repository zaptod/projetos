"""Relatorio de cobertura: o que o banco do jogo ja tem e a camada de video
ainda nao sabe descrever.

POR QUE existe: as roletas sao responsivas ao banco - classe, raridade, tipo,
estilo, encantamento e skill nova entram sozinhos e nada quebra. Mas entrar na
roleta nao e o mesmo que estar pronto: um estilo sem traducao vira portugues
cru dentro de um prompt em ingles, uma categoria de reacao sem clipe cai no
cartao sintetico, um tier novo sem legenda derruba a edicao. Isso nao da
excecao, so sai errado - entao alguem precisa ser AVISADO, com o nome exato e
o lugar exato onde cadastrar.

Este modulo so LE. Nao importa fila de identidade, nao abre browser, nao
escreve arquivo, nao depende de rede. Pode rodar antes ou depois de qualquer
um desses cadastros existir.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import loader as nf

RAIZ = Path(__file__).resolve().parents[2]
CONFIG_DIR = RAIZ / "config"
ASSETS_DIR = RAIZ / "assets"

FONTE_ESTILOS = "neural_fights/tools/gerador_database.py"
FONTE_ENCANTAMENTOS = "neural_fights/models/constants.py"


def _ler_json(caminho: Path) -> tuple[dict, str | None]:
    try:
        with open(caminho, encoding="utf-8") as fh:
            return json.load(fh), None
    except FileNotFoundError:
        return {}, f"arquivo nao encontrado: {caminho}"
    except (OSError, ValueError) as erro:
        return {}, f"nao foi possivel ler {caminho}: {erro}"


def _util(valor) -> bool:
    """O cadastro existe DE VERDADE ou e uma chave com nada dentro?

    Olhar so a chave fazia o relatorio dizer OK para
    `traducoes.raridade["Comum"] = ""`, e o prompt saia com "an -grade" e
    estilo vazio. Chave com texto vazio e pior que chave ausente: ela cala o
    aviso que existe justamente para ser lido.
    """
    if valor is None:
        return False
    if isinstance(valor, str):
        return bool(valor.strip())
    # Lista/dict vazio NAO conta como buraco: "este tier nao tem efeito de
    # tela" e uma decisao editorial legitima (config/editing.json ja usa
    # effects_by_tier vazio em WEAK e AVERAGE). O que nao pode existir vazio e
    # o TEXTO de uma traducao, e esse cai no ramo de cima.
    return True


def _chaves(mapa, caminho: str) -> set:
    """Chaves COM CONTEUDO de um caminho pontilhado num json ja carregado."""
    atual = mapa
    for parte in caminho.split("."):
        if not isinstance(atual, dict) or parte not in atual:
            return set()
        atual = atual[parte]
    if isinstance(atual, dict):
        return {k for k, v in atual.items() if _util(v)}
    if isinstance(atual, list):
        return {str(item) for item in atual if _util(item)}
    return set()


ONDE_PADRAO = '{arquivo} -> {caminho}["{nome}"]'


def _grupo(gid: str, titulo: str, arquivo: str, caminho: str,
           esperados: list, presentes: set, detalhes=None,
           dica: str | None = None, erro: str | None = None,
           onde_fmt: str = ONDE_PADRAO) -> dict:
    detalhes = detalhes or {}
    faltando = [
        {
            "nome": nome,
            "onde": onde_fmt.format(arquivo=arquivo, caminho=caminho, nome=nome),
            "detalhe": detalhes.get(nome, ""),
        }
        for nome in esperados if nome not in presentes
    ]
    return {
        "id": gid,
        "titulo": titulo,
        "arquivo": arquivo,
        "caminho": caminho,
        "total": len(esperados),
        "cobertos": len(esperados) - len(faltando),
        "faltando": faltando,
        "dica": dica,
        "erro": erro,
    }


# ------------------------------------------------------------------- grupos
def _grupos_de_traducao(identity: dict, erro: str | None) -> list[dict]:
    arquivo = "config/identity.json"
    traducoes = identity.get("traducoes") or {}
    tipos_por_estilo = nf.tipos_por_estilo()

    usos_do_elemento: dict[str, list[str]] = {}
    for enc in nf.LISTA_ENCANTAMENTOS:
        usos_do_elemento.setdefault(nf.elemento_bruto_do_encantamento(enc), []).append(enc)

    grupos = [
        _grupo("traducoes.classe", "Traducao de CLASSE (prompt)",
               arquivo, "traducoes.classe",
               list(nf.LISTA_CLASSES), _chaves(traducoes, "classe"), erro=erro),
        _grupo("traducoes.personalidade", "Traducao de PERSONALIDADE (prompt)",
               arquivo, "traducoes.personalidade",
               nf.lista_personalidades(), _chaves(traducoes, "personalidade"), erro=erro),
        _grupo("traducoes.tipo_arma", "Traducao de TIPO DE ARMA (prompt)",
               arquivo, "traducoes.tipo_arma",
               list(nf.LISTA_TIPOS_ARMA), _chaves(traducoes, "tipo_arma"), erro=erro),
        _grupo("traducoes.silhueta", "Silhueta fisica por TIPO DE ARMA (prompt)",
               arquivo, "traducoes.silhueta",
               list(nf.LISTA_TIPOS_ARMA), _chaves(traducoes, "silhueta"), erro=erro),
        _grupo("traducoes.raridade", "Traducao de RARIDADE (prompt)",
               arquivo, "traducoes.raridade",
               list(nf.LISTA_RARIDADES), _chaves(traducoes, "raridade"), erro=erro),
        _grupo("traducoes.estilo", "Traducao de ESTILO (prompt)",
               arquivo, "traducoes.estilo",
               nf.nomes_de_estilo(), _chaves(traducoes, "estilo"),
               detalhes={n: "tipo: " + ", ".join(t) for n, t in tipos_por_estilo.items()},
               erro=erro),
        _grupo("traducoes.elemento", "Traducao de ELEMENTO (prompt)",
               arquivo, "traducoes.elemento",
               nf.elementos_do_banco(), _chaves(traducoes, "elemento"),
               detalhes={e: "encantamentos: " + ", ".join(u)
                         for e, u in usos_do_elemento.items()},
               erro=erro),
        _grupo("traducoes.habilidade", "Traducao de HABILIDADE (prompt)",
               arquivo, "traducoes.habilidade",
               nf.skills_rolaveis(), _chaves(traducoes, "habilidade"),
               detalhes={s: "grupo " + str(nf.grupo_da_skill(s))
                         for s in nf.skills_rolaveis()},
               dica="a roleta de HABILIDADE sorteia estas skills; sem traducao o "
                    "nome vai em portugues (ou some) no prompt em ingles",
               erro=erro),
        _grupo("traducoes.encantamento", "Traducao de ENCANTAMENTO (prompt)",
               arquivo, "traducoes.encantamento",
               list(nf.LISTA_ENCANTAMENTOS), _chaves(traducoes, "encantamento"),
               detalhes={e: "elemento " + nf.elemento_bruto_do_encantamento(e)
                         for e in nf.LISTA_ENCANTAMENTOS},
               dica="o encantamento aparece no nameplate em portugues e so chega "
                    "ao prompt destilado em elemento",
               erro=erro),
        _grupo("aura", "AURA por elemento (prompt de video)",
               arquivo, "aura",
               nf.elementos_do_banco(), _chaves(identity, "aura"), erro=erro),
    ]
    return grupos


def _grupos_de_edicao(scoring: dict, captions: dict, editing: dict,
                      erros: dict) -> list[dict]:
    tiers = [t["name"] for t in scoring.get("tiers", []) if isinstance(t, dict)]
    verdicts = [v["name"] for v in scoring.get("build_verdicts", []) if isinstance(v, dict)]
    erro_scoring = erros.get("scoring.json")
    return [
        _grupo("captions.by_tier", "Legenda por TIER",
               "config/captions.json", "by_tier",
               tiers, _chaves(captions, "by_tier"),
               erro=erros.get("captions.json") or erro_scoring),
        _grupo("captions.final_by_verdict", "Legenda final por VEREDITO",
               "config/captions.json", "final_by_verdict",
               verdicts, _chaves(captions, "final_by_verdict"),
               erro=erros.get("captions.json") or erro_scoring),
        _grupo("editing.reaction_chance_by_tier", "Chance de reacao por TIER",
               "config/editing.json", "reaction_chance_by_tier",
               tiers, _chaves(editing, "reaction_chance_by_tier"),
               erro=erros.get("editing.json") or erro_scoring),
        _grupo("editing.reaction_chance_by_tier_tournament",
               "Chance de reacao por TIER (torneio)",
               "config/editing.json", "reaction_chance_by_tier_tournament",
               tiers, _chaves(editing, "reaction_chance_by_tier_tournament"),
               erro=erros.get("editing.json") or erro_scoring),
        _grupo("editing.effects_by_tier", "Efeito de tela por TIER",
               "config/editing.json", "effects_by_tier",
               tiers, _chaves(editing, "effects_by_tier"),
               erro=erros.get("editing.json") or erro_scoring),
    ]


def _grupo_estilos() -> dict:
    """Tipo de arma sem catalogo de estilos no proprio neural_fights."""
    orfaos = nf.tipos_sem_estilos()
    return _grupo("nf.estilos", "Estilos do tipo de arma (catalogo do jogo)",
                  FONTE_ESTILOS, "ESTILOS_ARMA",
                  list(nf.LISTA_TIPOS_ARMA),
                  {t for t in nf.LISTA_TIPOS_ARMA if t not in orfaos},
                  detalhes={t: "roleta, registro e prompt usam uma variante "
                               f"generica chamada '{t}'; a GEOMETRIA vem da "
                               "arma Reta ate o catalogo ter a dele"
                            for t in orfaos},
                  dica="sem variantes o tipo entra na roleta com um estilo so")


def _grupo_grupos_de_skill() -> dict:
    """Grupo de skill que nenhum encantamento alcanca.

    Nao e um defeito da roleta: o proprio gerador do jogo so escolhe skill do
    elemento do encantamento (ou do neutro). Sem um encantamento daquele
    elemento, as skills do grupo nao podem sair nem la nem aqui.
    """
    orfaos = nf.grupos_sem_encantamento()
    detalhes = {}
    for grupo in orfaos:
        skills = list(nf.SKILLS_OFENSIVAS.get(grupo, []))
        detalhes[grupo] = f"{len(skills)} skills inalcancaveis: " + ", ".join(skills)
    todos = list(nf.SKILLS_OFENSIVAS)
    return _grupo("nf.encantamento_por_grupo",
                  "Encantamento que libere cada grupo de skill",
                  FONTE_ENCANTAMENTOS, "ENCANTAMENTOS",
                  todos, {g for g in todos if g not in orfaos},
                  detalhes=detalhes,
                  dica="cadastre um encantamento com esse elemento para as "
                       "skills do grupo poderem ser sorteadas",
                  onde_fmt="{arquivo} -> {caminho}: um encantamento com "
                           "elemento '{nome}'")


def _texto_dano(raridade: str, curva: dict) -> str:
    """O valor que a roleta REALMENTE vai usar nesta raridade.

    Dizer "usa o padrao 9.0" era mentira util para ninguem: fora da curva o
    loader EXTRAPOLA pela posicao na lista canonica, e so cai no padrao quando
    nem posicao existe. Um operador lendo 9.0 e vendo 35.4 na build perde a
    confianca no relatorio inteiro.
    """
    valor = nf.dano_base(raridade)
    if valor == nf.DANO_BASE_PADRAO:
        return ("a roleta de DANO cai no padrao %s para esta raridade"
                % nf.DANO_BASE_PADRAO)
    return ("a roleta de DANO extrapola para %s nesta raridade (a curva "
            "oficial nao a cobre); cadastre-a para valer o numero do jogo"
            % valor)


def _grupo_curva_dano() -> dict:
    """Raridade cujo dano base a curva oficial de gerar_arma nao entrega.

    A curva e lida do PROPRIO fonte do jogo por AST, e essa leitura pode falhar
    calada: basta o jogo mover o dict `dano_base` para constante de modulo ou
    monta-lo com {**BASE, ...}. Sem este grupo, a roleta de DANO passaria a
    oferecer 6-12 para TODA raridade - uma arma Mitica revelaria dano de arma
    Comum e nada avisaria.
    """
    curva = nf.curva_dano_oficial()
    dica = ("a curva vem por AST do fonte de gerar_arma; se ela deixou de ser "
            "um dict literal dentro da funcao, a leitura devolve vazio e todo "
            "dano cai no padrao")
    return _grupo("nf.curva_dano", "Dano base por RARIDADE (curva de gerar_arma)",
                  FONTE_ESTILOS, "gerar_arma.dano_base",
                  list(nf.LISTA_RARIDADES), set(curva),
                  detalhes={r: _texto_dano(r, curva)
                            for r in nf.LISTA_RARIDADES if r not in curva},
                  dica=dica)


def _grupo_reacoes(assets_dir: Path) -> dict:
    try:
        from ..assets.catalog import AssetCatalog, CATEGORIES
    except Exception as erro:  # noqa: BLE001 - relatorio nunca pode derrubar
        return _grupo("reacoes", "Clipe de reacao por categoria",
                      "assets/reactions/", "catalog.json", [], set(),
                      erro=f"biblioteca de reacoes nao pode ser lida: {erro}")
    try:
        catalogo = AssetCatalog(assets_dir)
        com_clipe = {e.get("category") for e in catalogo.entries}
    except Exception as erro:  # noqa: BLE001
        return _grupo("reacoes", "Clipe de reacao por categoria",
                      "assets/reactions/", "catalog.json", list(CATEGORIES), set(),
                      erro=f"biblioteca de reacoes nao pode ser lida: {erro}")
    return _grupo("reacoes", "Clipe de reacao por categoria",
                  "assets/reactions", "catalog.json",
                  list(CATEGORIES), com_clipe,
                  dica="importe com: python main.py import-reactions <pasta>",
                  onde_fmt="{arquivo}/{nome}/ -> nenhum clipe de video")


def _grupo_classe_elemento() -> dict:
    """Rotulo de classe sem elemento equivalente: a sinergia elemental daquela
    classe nunca dispara, nem a favor nem contra."""
    try:
        from ..evaluation.synergy_engine import CLASSE_ELEMENTO_MAP
    except Exception as erro:  # noqa: BLE001
        return _grupo("synergy.classe_elemento", "Elemento equivalente da CLASSE",
                      "src/evaluation/synergy_engine.py", "CLASSE_ELEMENTO_MAP",
                      [], set(), erro=f"mapa nao pode ser lido: {erro}")
    rotulos, detalhes = [], {}
    for classe in nf.LISTA_CLASSES:
        rotulo = nf.classe_elemento(classe)
        if rotulo and rotulo not in rotulos:
            rotulos.append(rotulo)
            detalhes[rotulo] = f"classe {classe}"
    return _grupo("synergy.classe_elemento", "Elemento equivalente da CLASSE",
                  "src/evaluation/synergy_engine.py", "CLASSE_ELEMENTO_MAP",
                  rotulos, set(CLASSE_ELEMENTO_MAP), detalhes=detalhes,
                  dica="sem entrada, a sinergia elemento_da_classe e o conflito "
                       "elemento_oposto nunca disparam para essa classe")


# -------------------------------------------------------------------- api
def catalogo_vivo() -> dict:
    """Contagem do banco na hora da chamada - o cabecalho do relatorio."""
    return {
        "classes": len(nf.LISTA_CLASSES),
        "personalidades": len(nf.lista_personalidades()),
        "raridades": len(nf.LISTA_RARIDADES),
        "tipos_de_arma": len(nf.LISTA_TIPOS_ARMA),
        "estilos": len(nf.nomes_de_estilo()),
        "encantamentos": len(nf.LISTA_ENCANTAMENTOS),
        "elementos": len(nf.elementos_do_banco()),
        "skills_rolaveis": len(nf.skills_rolaveis()),
        "grupos_de_skill": len(nf.SKILLS_OFENSIVAS),
    }


def cobertura(config_dir: Path | str | None = None,
              assets_dir: Path | str | None = None) -> dict:
    """O que o banco ja tem e a camada de video ainda nao, agrupado.

    Cada item de `faltando` traz o NOME exato e o caminho de onde cadastrar.
    """
    config_dir = Path(config_dir) if config_dir else CONFIG_DIR
    assets_dir = Path(assets_dir) if assets_dir else ASSETS_DIR

    erros: dict[str, str] = {}
    dados: dict[str, dict] = {}
    for nome in ("identity.json", "scoring.json", "captions.json", "editing.json"):
        conteudo, erro = _ler_json(config_dir / nome)
        dados[nome] = conteudo
        if erro:
            erros[nome] = erro

    grupos = _grupos_de_traducao(dados["identity.json"], erros.get("identity.json"))
    grupos += _grupos_de_edicao(dados["scoring.json"], dados["captions.json"],
                                dados["editing.json"], erros)
    grupos += [_grupo_estilos(), _grupo_curva_dano(), _grupo_grupos_de_skill(),
               _grupo_reacoes(assets_dir), _grupo_classe_elemento()]

    total = sum(len(g["faltando"]) for g in grupos)
    return {
        "ok": total == 0 and not any(g["erro"] for g in grupos),
        "total_faltando": total,
        "catalogo": catalogo_vivo(),
        "grupos": grupos,
    }


def relatorio(dados: dict | None = None, *,
              config_dir: Path | str | None = None,
              assets_dir: Path | str | None = None,
              limite: int | None = None,
              apenas_faltando: bool = False) -> str:
    """Versao legivel do mesmo dado.

    O texto do relatorio e ASCII; os NOMES vindos do banco mantem o acento de
    proposito. Tirar o acento de "Epico" daria um caminho que nao existe no
    JSON, e o relatorio existe justamente para ser copiado sem pensar.
    """
    dados = dados if dados is not None else cobertura(config_dir, assets_dir)
    catalogo = dados["catalogo"]
    linhas = [
        "COBERTURA DO BANCO -> CAMADA DE VIDEO",
        "banco vivo: " + " | ".join(f"{k.replace('_', ' ')} {v}"
                                    for k, v in catalogo.items()),
        f"faltando cadastrar: {dados['total_faltando']}",
        "",
    ]
    for grupo in dados["grupos"]:
        faltando = grupo["faltando"]
        if apenas_faltando and not faltando and not grupo["erro"]:
            continue
        if grupo["erro"]:
            marca = "ERRO"
        elif faltando:
            marca = "FALTA"
        else:
            marca = "OK"
        linhas.append(f"[{marca}] {grupo['titulo']} "
                      f"({grupo['cobertos']}/{grupo['total']})")
        if grupo["erro"]:
            linhas.append(f"    {grupo['erro']}")
        if grupo["dica"] and faltando:
            linhas.append(f"    obs: {grupo['dica']}")
        mostrados = faltando if limite is None else faltando[:limite]
        for item in mostrados:
            detalhe = f"   [{item['detalhe']}]" if item["detalhe"] else ""
            linhas.append(f"    {item['onde']}{detalhe}")
        restantes = len(faltando) - len(mostrados)
        if restantes > 0:
            linhas.append(f"    ... mais {restantes}")
        linhas.append("")
    if dados["ok"]:
        linhas.append("Nada pendente: todo item do banco tem prompt e reacao.")
    return "\n".join(linhas).rstrip() + "\n"
