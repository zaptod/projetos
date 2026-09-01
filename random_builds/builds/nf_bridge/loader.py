"""Ponte com o neural_fights: TODA categoria/caracteristica vem de la.

Nada e inventado aqui - este modulo apenas importa os catalogos canonicos
(classes, personalidades, tipos, estilos, raridades, encantamentos, skills)
e as fabricas oficiais (gerar_arma / gerar_personagem / salvar_database).

POR QUE quase tudo aqui e FUNCAO e nao constante: o banco do jogo cresce. Uma
constante congelada no import nao enxerga a raridade que entrou depois, e a
camada de video volta a ter uma copia paralela do catalogo - que e exatamente
o defeito que este modulo existe para nao ter. Leia a lista canonica na hora
da chamada, sempre.
"""
from __future__ import annotations

import ast
import inspect
import sys
import textwrap
import unicodedata
from pathlib import Path

# random_builds mora ao lado do pacote neural_fights (e:\projetos)
_PROJETOS = Path(__file__).resolve().parents[3]
if str(_PROJETOS) not in sys.path:
    sys.path.insert(0, str(_PROJETOS))

from neural_fights.models.constants import (  # noqa: E402
    LISTA_CLASSES, LISTA_RARIDADES, LISTA_TIPOS_ARMA,
    LISTA_ENCANTAMENTOS, ENCANTAMENTOS,
)
from neural_fights.ai.personalities import PERSONALIDADES_PRESETS  # noqa: E402
from neural_fights.core.skills import SKILL_DB  # noqa: E402
from neural_fights.tools.gerador_database import (  # noqa: E402
    ESTILOS_ARMA, SKILLS_OFENSIVAS, gerar_arma, gerar_personagem,
    salvar_database, selecionar_arma_por_classe,
)
from neural_fights.data import database  # noqa: E402

# Snapshot do import, mantido porque teste antigo itera a constante. Codigo
# novo usa lista_personalidades(), que le o preset vivo.
LISTA_PERSONALIDADES = list(PERSONALIDADES_PRESETS)

# Extremos da piramide de raridade. Peso e frequencia na roleta, score e
# quanto a rolagem vale. Os numeros sao os das pontas do desenho original
# (Comum 30/22, topo 4/97); o que fica entre eles sai da POSICAO na lista
# canonica, nunca de uma tabela literal que alguem precise editar.
PESO_MAIS_COMUM = 30
PESO_MAIS_RARO = 4
SCORE_MAIS_COMUM = 22
SCORE_MAIS_RARO = 97

# Dano base de uma raridade que a curva oficial nao conhece.
DANO_BASE_PADRAO = 9.0
# Folga da roleta de dano em volta da curva: gerar_arma soma uniform(-1.5, 2.5).
DANO_FOLGA_ABAIXO = 3
DANO_FOLGA_ACIMA = 3

# Faixa de peso de um estilo sem catalogo (o mesmo padrao de gerar_arma).
PESO_VARIANTE_PADRAO = (3, 5)

# Grupo de skills que serve QUALQUER encantamento, como no gerador oficial
# (SKILLS_OFENSIVAS.get(elemento, SKILLS_OFENSIVAS["FISICO"])).
GRUPO_NEUTRO_PADRAO = "FISICO"


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto))
                   if unicodedata.category(c) != "Mn")


def identificador(texto: str) -> str:
    """Slug ASCII para id de regra gerada.

    Existe para que dois nomes de estilo nunca produzam o mesmo id por
    acidente de pontuacao - id repetido faz a segunda regra sobrescrever a
    primeira sem ninguem perceber.
    """
    limpo = "".join(c if c.isalnum() else "_" for c in sem_acento(texto).lower())
    return "_".join(p for p in limpo.split("_") if p) or "sem_nome"


def lista_personalidades() -> list[str]:
    return list(PERSONALIDADES_PRESETS)


def _posicao(valor, lista) -> int | None:
    try:
        return list(lista).index(valor)
    except ValueError:
        return None


# ------------------------------------------------------------------ raridade
def raridade_peso(raridade: str) -> int:
    """Peso da raridade na roleta, derivado da POSICAO na lista canonica.

    Mais no fim da lista = mais raro = peso menor. Assim uma raridade nova
    entra sozinha com peso coerente, sem ninguem editar tabela nenhuma.
    """
    ordem = list(LISTA_RARIDADES)
    i = _posicao(raridade, ordem)
    if i is None or len(ordem) <= 1:
        return PESO_MAIS_COMUM
    passo = (PESO_MAIS_COMUM - PESO_MAIS_RARO) / (len(ordem) - 1)
    return max(1, round(PESO_MAIS_COMUM - passo * i))


def raridade_score(raridade: str) -> int:
    """Score da raridade, tambem pela posicao: mais raro = score maior."""
    ordem = list(LISTA_RARIDADES)
    i = _posicao(raridade, ordem)
    if i is None or len(ordem) <= 1:
        return SCORE_MAIS_COMUM
    passo = (SCORE_MAIS_RARO - SCORE_MAIS_COMUM) / (len(ordem) - 1)
    return round(SCORE_MAIS_COMUM + passo * i)


def raridades_de_elite() -> list[str]:
    """Metade de cima da piramide - o bloco que ganha piso de critico.

    Com as 6 raridades de hoje devolve exatamente as 3 que gerar_arma lista
    literalmente; com 7 ou 8 continua sendo "a metade rara" sem ninguem
    reescrever a condicao.
    """
    ordem = list(LISTA_RARIDADES)
    return ordem[len(ordem) // 2:]


def curva_dano_oficial() -> dict:
    """Le a curva de dano base do PROPRIO fonte de gerar_arma.

    A curva e um dict LOCAL dentro de gerar_arma, nao exportado. Uma copia
    manual aqui divergiria calada no dia em que o jogo rebalancear - foi o que
    a auditoria apontou. Lendo o fonte, divergir deixa de ser possivel.
    """
    try:
        arvore = ast.parse(textwrap.dedent(inspect.getsource(gerar_arma)))
    except (OSError, TypeError, SyntaxError, IndentationError):
        return {}
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Assign) or not isinstance(no.value, ast.Dict):
            continue
        if not any(getattr(alvo, "id", None) == "dano_base" for alvo in no.targets):
            continue
        try:
            curva = ast.literal_eval(no.value)
        except ValueError:
            return {}
        if curva and all(isinstance(v, (int, float)) for v in curva.values()):
            return {str(k): float(v) for k, v in curva.items()}
    return {}


# Snapshot de conveniencia: o fonte de gerar_arma nao muda dentro de um
# processo. O que MUDA e o jogo mover o dict para constante de modulo ou monta-
# lo com {**BASE, ...} - ai a leitura devolve {} e todas as raridades caem em
# DANO_BASE_PADRAO sem excecao nenhuma. Quem grita nesse caso e o relatorio de
# cobertura (grupo nf.curva_dano), que chama curva_dano_oficial() na hora.
DANO_BASE_POR_RARIDADE = curva_dano_oficial()


def dano_base(raridade: str) -> float:
    """Dano base da raridade; se a curva oficial nao a conhece, extrapola.

    A extrapolacao usa a inclinacao entre a primeira e a ultima raridade
    conhecidas, entao uma raridade nova no topo recebe um dano base acima do
    topo atual em vez do 9.0 mudo do .get() do jogo.
    """
    curva = DANO_BASE_POR_RARIDADE
    if raridade in curva:
        return float(curva[raridade])
    ordem = list(LISTA_RARIDADES)
    alvo = _posicao(raridade, ordem)
    conhecidos = [(i, float(curva[r])) for i, r in enumerate(ordem) if r in curva]
    if alvo is None or not conhecidos:
        return DANO_BASE_PADRAO
    if len(conhecidos) == 1:
        return conhecidos[0][1]
    (i0, v0), (i1, v1) = conhecidos[0], conhecidos[-1]
    inclinacao = (v1 - v0) / (i1 - i0)
    return round(v0 + inclinacao * (alvo - i0), 1)


def dano_envelope() -> tuple[int, int]:
    """Faixa da roleta de DANO: envolve a curva inteira, raridade nova junto."""
    bases = [dano_base(r) for r in LISTA_RARIDADES] or [DANO_BASE_PADRAO]
    return (max(1, round(min(bases) - DANO_FOLGA_ABAIXO)),
            round(max(bases) + DANO_FOLGA_ACIMA))


# ----------------------------------------------------------------- elementos
def grupo_neutro() -> str | None:
    """O grupo de skills que atende qualquer encantamento."""
    if GRUPO_NEUTRO_PADRAO in SKILLS_OFENSIVAS:
        return GRUPO_NEUTRO_PADRAO
    return next(iter(SKILLS_OFENSIVAS), None)


def elemento_bruto_do_encantamento(encantamento: str) -> str:
    """Elemento como o BANCO o escreve, so normalizado (Relampago -> RAIO).

    Sem fallback de proposito: quem precisa da verdade do dado (o relatorio de
    cobertura, a traducao do prompt) nao pode receber FISICO no lugar de um
    elemento novo - e assim que uma arma de plasma vira aco cru na tela.
    """
    dados = ENCANTAMENTOS.get(encantamento) or {}
    elemento = dados.get("elemento") or GRUPO_NEUTRO_PADRAO
    return sem_acento(elemento).upper()


def grupo_de_skills(elemento: str) -> str | None:
    """Grupo de SKILLS_OFENSIVAS que serve o elemento; sem grupo, o neutro."""
    if elemento in SKILLS_OFENSIVAS:
        return elemento
    return grupo_neutro()


def elemento_do_encantamento(encantamento: str) -> str:
    """Grupo de skills do encantamento, como o gerador oficial resolve.

    Mantem a semantica antiga (elemento sem grupo cai no neutro) porque o
    prompt e o exporter dependem dela; quem quer o elemento cru chama
    elemento_bruto_do_encantamento.
    """
    bruto = elemento_bruto_do_encantamento(encantamento)
    return grupo_de_skills(bruto) or GRUPO_NEUTRO_PADRAO


def elementos_do_banco() -> list[str]:
    """Todo elemento que o banco consegue produzir: os grupos de skill mais os
    elementos crus dos encantamentos (inclusive os que nao viraram grupo)."""
    vistos: list[str] = []
    for chave in list(SKILLS_OFENSIVAS):
        if chave not in vistos:
            vistos.append(chave)
    for enc in LISTA_ENCANTAMENTOS:
        bruto = elemento_bruto_do_encantamento(enc)
        if bruto not in vistos:
            vistos.append(bruto)
    return vistos


def encantamentos_do_grupo(grupo: str) -> list[str]:
    """Encantamentos que liberam as skills daquele grupo.

    O grupo neutro serve todos, igual ao fallback do gerador oficial.
    """
    if grupo == grupo_neutro():
        return list(LISTA_ENCANTAMENTOS)
    return [e for e in LISTA_ENCANTAMENTOS if elemento_do_encantamento(e) == grupo]


def grupos_sem_encantamento() -> list[str]:
    """Grupos de skill que nenhum encantamento alcanca - as skills la dentro
    nao podem ser sorteadas, nem aqui nem no proprio jogo."""
    return [g for g in SKILLS_OFENSIVAS if not encantamentos_do_grupo(g)]


def skills_rolaveis() -> list[str]:
    """Toda skill ofensiva que a roleta de HABILIDADE pode mostrar."""
    vistas: list[str] = []
    for skills in SKILLS_OFENSIVAS.values():
        for skill in skills:
            if skill not in vistas:
                vistas.append(skill)
    return vistas


def grupo_da_skill(skill: str) -> str | None:
    for grupo, skills in SKILLS_OFENSIVAS.items():
        if skill in skills:
            return grupo
    return None


def kit_do_personagem(registro: dict) -> list[dict]:
    """Kit visível na ficha (Onda 11D): o ``kit_skills`` sorteado na criação
    ou, em registro antigo, o kit fixo da classe — com papel, elemento, cor e
    a DESCRIÇÃO do catálogo (o que o card e o showcase mostram)."""
    from neural_fights.models.constants import CLASSES_DATA, KIT_PAPEIS

    nomes = list(registro.get("kit_skills") or [])
    if not nomes:
        classe = registro.get("classe", "")
        nomes = list(CLASSES_DATA.get(classe, {}).get("skills_afinidade", []))
    kit = []
    for idx, nome in enumerate(nomes):
        dados = SKILL_DB.get(nome, {})
        kit.append({
            "nome": nome,
            "papel": KIT_PAPEIS[idx] if idx < len(KIT_PAPEIS) else "",
            "elemento": dados.get("elemento") or "",
            "descricao": dados.get("descricao") or "",
            "cor": list(dados.get("cor", (255, 255, 255)))[:3],
        })
    return kit


# ------------------------------------------------------------------- classes
def classe_base(classe: str) -> str:
    return classe.split(" (")[0]


def classe_elemento(classe: str) -> str | None:
    """O rotulo entre parenteses da classe ('Piromante (Fogo)' -> 'Fogo')."""
    if "(" in classe and classe.endswith(")"):
        return classe[classe.index("(") + 1:-1]
    return None


def tipos_preferidos_da_classe(classe: str) -> list[str]:
    """Reusa a preferencia oficial classe->tipos de arma."""
    dummy = [{"tipo": t, "nome": t} for t in LISTA_TIPOS_ARMA]
    preferidas = selecionar_arma_por_classe(classe_base(classe), dummy)
    return [a["tipo"] for a in preferidas]


# ------------------------------------------------------------------- estilos
def variantes_do_tipo(tipo: str) -> list[dict]:
    """Variantes do tipo. Tipo sem catalogo NAO herda as de outro tipo.

    Herdar (era ESTILOS_ARMA["Reta"]) duplicava os 12 nomes da Reta na roleta,
    fazia duas regras de peso com o mesmo id e mandava a roda destacar o
    segmento errado. Uma variante generica com o nome do proprio tipo mantem a
    roleta honesta, e o relatorio de cobertura acusa o buraco.
    """
    dados = ESTILOS_ARMA.get(tipo) or {}
    variantes = dados.get("variantes") or []
    if variantes:
        return list(variantes)
    return [{"nome": tipo, "peso": PESO_VARIANTE_PADRAO}]


def tipos_sem_estilos() -> list[str]:
    return [t for t in LISTA_TIPOS_ARMA
            if not (ESTILOS_ARMA.get(t) or {}).get("variantes")]


def tipos_por_estilo() -> dict[str, list[str]]:
    """nome do estilo -> tipos de arma que o oferecem."""
    mapa: dict[str, list[str]] = {}
    for tipo in LISTA_TIPOS_ARMA:
        for variante in variantes_do_tipo(tipo):
            nome = variante["nome"]
            mapa.setdefault(nome, [])
            if tipo not in mapa[nome]:
                mapa[nome].append(tipo)
    return mapa


def nomes_de_estilo() -> list[str]:
    return list(tipos_por_estilo())
