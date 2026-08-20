#!/usr/bin/env python3
"""Auditoria estrutural dos catalogos de personalidade.

Existe por uma razao concreta: ate agora esses catalogos nao tinham validacao
nenhuma, e o resultado foi que 107 dos 162 tracos declarados nao tinham qualquer
consumidor. Um lutador "Artista Marcial, Criativo, Dancarino, Stylist, Zen" se
comportava exatamente como um sem traco algum, e nada no projeto acusava isso.

O contrato que esta auditoria trava:

* **todo traco declara eixos** -- e o que faz um traco valer por construcao, em
  vez de valer so se alguem lembrou de escrever ``"NOME" in self.tracos``;
* **nenhum eixo vazio** -- declarar um traco sem opiniao nenhuma o torna inerte
  de novo, so que de forma mais dificil de perceber;
* **integridade referencial** -- preset e arquetipo so apontam para estilo,
  filosofia, quirk, instinto e ritmo que existem.

Le tudo por AST, sem importar o jogo, pelo mesmo motivo de ``auditoria_skills``:
o gate roda sem pygame, sem janela e sem inicializar combate.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any, Iterable

from neural_fights.utils.console import SafeArgumentParser, safe_print

CAMINHO = Path(__file__).resolve().parents[1] / "ai" / "personalities.py"
CAMINHO_BRAIN = Path(__file__).resolve().parents[1] / "ai" / "brain.py"

CATEGORIAS_DE_TRACO = (
    "TRACOS_AGRESSIVIDADE",
    "TRACOS_DEFENSIVO",
    "TRACOS_MOBILIDADE",
    "TRACOS_SKILLS",
    "TRACOS_MENTAL",
    "TRACOS_ESPECIAIS",
)


class ProblemaDeCatalogo(RuntimeError):
    """Falha estrutural que impede a auditoria de comecar."""


def _literais(caminho: Path) -> dict[str, Any]:
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    except (OSError, SyntaxError) as exc:
        raise ProblemaDeCatalogo(f"nao foi possivel ler {caminho}: {exc}") from exc

    encontrados: dict[str, Any] = {}
    for no in arvore.body:
        if not isinstance(no, ast.Assign) or len(no.targets) != 1:
            continue
        alvo = no.targets[0]
        if not isinstance(alvo, ast.Name):
            continue
        try:
            encontrados[alvo.id] = ast.literal_eval(no.value)
        except (ValueError, TypeError):
            continue
    return encontrados


def _chaves_duplicadas(caminho: Path, nome_dict: str) -> list[str]:
    """``literal_eval`` silencia chave repetida; a auditoria nao pode silenciar."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    duplicadas: list[str] = []
    for no in arvore.body:
        if not isinstance(no, ast.Assign) or len(no.targets) != 1:
            continue
        alvo = no.targets[0]
        if not isinstance(alvo, ast.Name) or alvo.id != nome_dict:
            continue
        if not isinstance(no.value, ast.Dict):
            continue
        vistas: set[str] = set()
        for chave in no.value.keys:
            if isinstance(chave, ast.Constant) and isinstance(chave.value, str):
                if chave.value in vistas:
                    duplicadas.append(chave.value)
                vistas.add(chave.value)
    return duplicadas


def _validar_eixos(
    catalogo: dict[str, Any],
    tracos: list[str],
    erros: list[str],
    avisos: list[str],
) -> None:
    eixos = catalogo.get("EIXOS_COMPORTAMENTO")
    mapa = catalogo.get("TRACO_EIXOS")
    if not isinstance(eixos, (tuple, list)) or not eixos:
        raise ProblemaDeCatalogo("EIXOS_COMPORTAMENTO ausente ou vazio")
    if not isinstance(mapa, dict):
        raise ProblemaDeCatalogo("TRACO_EIXOS ausente ou nao literal")

    conhecidos = set(eixos)
    declarados = set(tracos)

    for traco in sorted(declarados - set(mapa)):
        erros.append(f"traco sem eixos declarados: {traco!r}")
    for traco in sorted(set(mapa) - declarados):
        erros.append(f"TRACO_EIXOS aponta para traco inexistente: {traco!r}")

    for traco, valores in sorted(mapa.items()):
        caminho = f"TRACO_EIXOS[{traco!r}]"
        if not isinstance(valores, dict):
            erros.append(f"{caminho}: precisa ser um mapeamento de eixo -> valor")
            continue
        if not valores:
            # Um traco sem opiniao nenhuma volta a ser inerte, so que escondido.
            erros.append(f"{caminho}: nenhum eixo declarado; o traco nao faria nada")
            continue
        for eixo, valor in valores.items():
            if eixo not in conhecidos:
                erros.append(f"{caminho}: eixo desconhecido {eixo!r}")
                continue
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                erros.append(f"{caminho}[{eixo!r}]: precisa ser numerico")
            elif not -1.0 <= float(valor) <= 1.0:
                erros.append(f"{caminho}[{eixo!r}]: {valor} fora da faixa [-1, 1]")
            elif abs(float(valor)) < 0.05:
                avisos.append(
                    f"{caminho}[{eixo!r}]: {valor} e pequeno demais para ser percebido"
                )


def _validar_referencias(
    catalogo: dict[str, Any],
    tracos: list[str],
    erros: list[str],
) -> None:
    estilos = set(catalogo.get("ESTILOS_LUTA") or ())
    filosofias = set(catalogo.get("FILOSOFIAS") or ())
    quirks = set(catalogo.get("QUIRKS") or ())
    instintos = set(catalogo.get("INSTINTOS") or ())
    ritmos = set(catalogo.get("RITMOS") or ())
    declarados = set(tracos)

    presets = catalogo.get("PERSONALIDADES_PRESETS") or {}
    for nome, preset in sorted(presets.items()):
        caminho = f"PERSONALIDADES_PRESETS[{nome!r}]"
        if not isinstance(preset, dict):
            erros.append(f"{caminho}: precisa ser um mapeamento")
            continue
        for campo, universo, rotulo in (
            ("estilo_fixo", estilos, "estilo"),
            ("filosofia_fixa", filosofias, "filosofia"),
            ("ritmo_fixo", ritmos, "ritmo"),
        ):
            valor = preset.get(campo)
            if valor and valor not in universo:
                erros.append(f"{caminho}.{campo}: {rotulo} inexistente {valor!r}")
        for campo, universo, rotulo in (
            ("tracos_fixos", declarados, "traco"),
            ("quirks_fixos", quirks, "quirk"),
            ("instintos_fixos", instintos, "instinto"),
        ):
            for item in preset.get(campo) or ():
                if item not in universo:
                    erros.append(f"{caminho}.{campo}: {rotulo} inexistente {item!r}")

    arquetipos = catalogo.get("ARQUETIPO_DATA") or {}
    for nome, dados in sorted(arquetipos.items()):
        if not isinstance(dados, dict):
            erros.append(f"ARQUETIPO_DATA[{nome!r}]: precisa ser um mapeamento")
            continue
        estilo = dados.get("estilo")
        if estilo and estilo not in estilos:
            erros.append(f"ARQUETIPO_DATA[{nome!r}].estilo: inexistente {estilo!r}")

    instintos_dados = catalogo.get("INSTINTOS") or {}
    for nome, dados in sorted(instintos_dados.items()):
        if not isinstance(dados, dict):
            erros.append(f"INSTINTOS[{nome!r}]: precisa ser um mapeamento")
            continue
        for campo in ("trigger", "acao", "chance", "prioridade", "cooldown"):
            if campo not in dados:
                erros.append(f"INSTINTOS[{nome!r}]: campo obrigatorio ausente {campo!r}")


def _literais_comparados(caminho: Path, funcao: str, variavel: str) -> set[str]:
    """Literais de string comparados com ``variavel`` dentro de ``funcao``.

    E o inventario do que o runtime realmente despacha: ``trigger == "x"``
    e ``acao in ("a", "b")`` viram o universo permitido para o catalogo.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    literais: set[str] = set()
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.FunctionDef) and no.name == funcao):
            continue
        for comparacao in ast.walk(no):
            if not isinstance(comparacao, ast.Compare):
                continue
            lados = [comparacao.left, *comparacao.comparators]
            nomes = {lado.id for lado in lados if isinstance(lado, ast.Name)}
            if variavel not in nomes:
                continue
            for lado in lados:
                if isinstance(lado, ast.Constant) and isinstance(lado.value, str):
                    literais.add(lado.value)
                elif isinstance(lado, (ast.Tuple, ast.List)):
                    for elemento in lado.elts:
                        if isinstance(elemento, ast.Constant) and isinstance(
                            elemento.value, str
                        ):
                            literais.add(elemento.value)
    return literais


def _validar_instintos_vs_runtime(
    catalogo: dict[str, Any],
    erros: list[str],
    avisos: list[str],
) -> None:
    """Todo instinto declarado precisa de despacho REAL no brain (Onda 5D).

    A podridao original: 8/15 instintos referenciavam triggers/acoes que o
    runtime nunca despachou (ataque_baixo/alto num jogo top-down,
    sendo_combo com a chave errada, p.iniciar_dash inexistente) — o
    catalogo prometia reflexos mortos e nada acusava. A checagem e
    bidirecional: catalogo sem despacho e ERRO; despacho sem catalogo e
    aviso de ramo morto.
    """
    triggers_runtime = _literais_comparados(
        CAMINHO_BRAIN, "_avaliar_trigger_instinto", "trigger"
    )
    acoes_runtime = _literais_comparados(CAMINHO_BRAIN, "_executar_instinto", "acao")
    if not triggers_runtime or not acoes_runtime:
        erros.append(
            "auditoria nao encontrou o despacho de instintos no brain "
            "(_avaliar_trigger_instinto/_executar_instinto)"
        )
        return

    usados_triggers: set[str] = set()
    usadas_acoes: set[str] = set()
    for nome, dados in sorted((catalogo.get("INSTINTOS") or {}).items()):
        if not isinstance(dados, dict):
            continue
        trigger = dados.get("trigger")
        acao = dados.get("acao")
        if trigger:
            usados_triggers.add(trigger)
            if trigger not in triggers_runtime:
                erros.append(
                    f"INSTINTOS[{nome!r}].trigger: sem despacho no runtime {trigger!r}"
                )
        if acao:
            usadas_acoes.add(acao)
            if acao not in acoes_runtime:
                erros.append(
                    f"INSTINTOS[{nome!r}].acao: sem executor no runtime {acao!r}"
                )

    for orfao in sorted(triggers_runtime - usados_triggers):
        avisos.append(f"trigger despachado sem instinto que o use: {orfao!r}")
    for orfao in sorted(acoes_runtime - usadas_acoes):
        avisos.append(f"acao executavel sem instinto que a use: {orfao!r}")


def auditar() -> tuple[list[str], list[str]]:
    erros: list[str] = []
    avisos: list[str] = []

    catalogo = _literais(CAMINHO)

    tracos: list[str] = []
    for categoria in CATEGORIAS_DE_TRACO:
        itens = catalogo.get(categoria)
        if not isinstance(itens, list):
            raise ProblemaDeCatalogo(f"{categoria} ausente ou nao literal")
        tracos.extend(itens)

    repetidos = sorted({t for t in tracos if tracos.count(t) > 1})
    for traco in repetidos:
        erros.append(f"traco declarado em mais de uma categoria: {traco!r}")

    for chave in _chaves_duplicadas(CAMINHO, "TRACO_EIXOS"):
        erros.append(f"TRACO_EIXOS tem a chave duplicada {chave!r}")

    _validar_eixos(catalogo, tracos, erros, avisos)
    _validar_referencias(catalogo, tracos, erros)
    _validar_instintos_vs_runtime(catalogo, erros, avisos)
    return erros, avisos


def _render(titulo: str, itens: Iterable[str]) -> None:
    itens = list(itens)
    if not itens:
        return
    safe_print(f"\n{titulo} ({len(itens)}):")
    for item in itens:
        safe_print(f"  - {item}")


def build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(
        description="Auditoria estrutural dos catalogos de personalidade"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="avisos tambem bloqueiam, com codigo de saida 2",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        erros, avisos = auditar()
    except ProblemaDeCatalogo as exc:
        safe_print(f"Falha estrutural: {exc}", file=sys.stderr)
        return 1

    _render("Erros", erros)
    _render("Avisos", avisos)
    if not erros and not avisos:
        safe_print("Findings: none")
    safe_print(
        "Scope: structural contracts only; this report does not claim runtime "
        "functionality."
    )

    if erros:
        return 1
    if avisos and args.strict:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
