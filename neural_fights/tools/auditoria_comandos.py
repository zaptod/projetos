#!/usr/bin/env python3
"""Auditoria estrutural do vocabulario de comandos de live.

Segue o mesmo desenho de ``auditoria_skills``: le os catalogos por **AST**, sem
importar o jogo, para que o gate rode sem pygame, sem janela e sem inicializar
combate. Ler por AST tambem deixa detectar chaves literais duplicadas, que
``literal_eval`` esconderia.

O que a auditoria garante, em ordem de severidade:

1. **inventario fechado de campos** -- chave nao declarada e erro, nunca aviso.
   E o que impede o vocabulario de crescer em silencio para dentro do runtime;
2. **integridade referencial** -- toda ``skill`` existe em ``SKILL_DB`` e toda
   arena existe em ``ARENAS``;
3. **coerencia de escopo e verbo** -- um verbo que precisa de skill nao pode
   ficar sem ela, e vice-versa;
4. **justica** -- comando de escopo ``GLOBAL`` nao pode referenciar skill com
   campo que beneficia o dono, porque nesse escopo o dono e um acidente de
   instanciacao;
5. **evidencia de runtime** -- cada comando aponta para um teste real, conferido
   por AST no checkout.

Erros retornam 1. Em ``--strict``, avisos tambem bloqueiam, com codigo 2.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any, Iterable

from neural_fights.utils.console import SafeArgumentParser, safe_print

RAIZ_PACOTE = Path(__file__).resolve().parents[1]
CAMINHO_CATALOGO = RAIZ_PACOTE / "live" / "catalog.py"
CAMINHO_SKILLS = RAIZ_PACOTE / "core" / "skills.py"
CAMINHO_ARENAS = RAIZ_PACOTE / "core" / "arena.py"
CAMINHO_EVIDENCIAS = RAIZ_PACOTE / "tools" / "command_runtime_evidence.py"
RAIZ_CHECKOUT = RAIZ_PACOTE.parent


class ProblemaDeCatalogo(RuntimeError):
    """Falha estrutural que impede a auditoria de sequer comecar."""


# --------------------------------------------------------------------- leitura


def _atribuicoes_literais(caminho: Path) -> dict[str, Any]:
    """Le atribuicoes de modulo cujo valor e literal puro."""
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


def _nomes_de_skills() -> set[str]:
    return set(_atribuicoes_literais(CAMINHO_SKILLS).get("SKILL_DB", {}))


def _dados_de_skills() -> dict[str, dict]:
    return _atribuicoes_literais(CAMINHO_SKILLS).get("SKILL_DB", {})


def _nomes_de_arenas() -> set[str]:
    """``ARENAS`` usa construtores, entao a leitura e pelas chaves do dict."""
    arvore = ast.parse(CAMINHO_ARENAS.read_text(encoding="utf-8"), filename=str(CAMINHO_ARENAS))
    for no in arvore.body:
        if not isinstance(no, ast.Assign) or len(no.targets) != 1:
            continue
        alvo = no.targets[0]
        if isinstance(alvo, ast.Name) and alvo.id == "ARENAS" and isinstance(no.value, ast.Dict):
            return {
                chave.value
                for chave in no.value.keys
                if isinstance(chave, ast.Constant) and isinstance(chave.value, str)
            }
    return set()


# ------------------------------------------------------------------ contratos


def _validar_comando(
    command_id: str,
    dados: Any,
    *,
    catalogo: dict[str, Any],
    skills: dict[str, dict],
    arenas: set[str],
    erros: list[str],
    avisos: list[str],
) -> None:
    caminho = f"COMMAND_DB[{command_id!r}]"
    if not isinstance(dados, dict):
        erros.append(f"{caminho} precisa ser um mapeamento")
        return

    # ``CAMPOS_ACEITOS`` e derivado por chamada no modulo, entao o leitor AST
    # nao o enxerga -- e nem deveria. O inventario e recomposto aqui a partir
    # das duas tuplas literais, que sao a fonte real da verdade.
    aceitos = set(catalogo["CAMPOS_OBRIGATORIOS"]) | set(catalogo["CAMPOS_OPCIONAIS"])
    desconhecidos = set(dados) - aceitos
    for campo in sorted(desconhecidos):
        erros.append(f"{caminho}: campo desconhecido {campo!r}")

    for campo in catalogo["CAMPOS_OBRIGATORIOS"]:
        if campo not in dados:
            erros.append(f"{caminho}: campo obrigatorio ausente {campo!r}")
    if set(catalogo["CAMPOS_OBRIGATORIOS"]) - set(dados):
        return

    categoria = dados["categoria"]
    escopo = dados["escopo"]
    efeito = dados["efeito"]

    if categoria not in catalogo["CATEGORIAS"]:
        erros.append(f"{caminho}: categoria desconhecida {categoria!r}")
    if escopo not in catalogo["ESCOPOS"]:
        erros.append(f"{caminho}: escopo desconhecido {escopo!r}")
    if efeito not in catalogo["EFEITOS"]:
        erros.append(f"{caminho}: efeito desconhecido {efeito!r}")

    _validar_numeros(caminho, dados, erros)
    _validar_momentos(caminho, dados, categoria, catalogo, erros)
    _validar_skill(caminho, dados, efeito, escopo, catalogo, skills, erros)
    _validar_arenas(caminho, dados, efeito, arenas, erros)

    if not str(dados.get("descricao", "")).strip():
        erros.append(f"{caminho}: descricao vazia")

    gatilho = dados.get("gatilho")
    if gatilho is not None:
        if not isinstance(gatilho, str) or not gatilho.startswith("!"):
            erros.append(f"{caminho}: gatilho precisa comecar com '!'")
        elif gatilho != gatilho.lower():
            erros.append(f"{caminho}: gatilho precisa ser minusculo")
    elif categoria != "PROXIMO_ROUND":
        avisos.append(f"{caminho}: sem gatilho de chat; so acessivel por gift")


def _validar_numeros(caminho: str, dados: dict, erros: list[str]) -> None:
    custo = dados.get("custo_units")
    if not isinstance(custo, int) or isinstance(custo, bool) or custo <= 0:
        erros.append(f"{caminho}: custo_units precisa ser inteiro positivo")

    cooldown = dados.get("cooldown_viewer")
    if not isinstance(cooldown, (int, float)) or isinstance(cooldown, bool) or cooldown <= 0:
        erros.append(f"{caminho}: cooldown_viewer precisa ser positivo")

    cooldown_global = dados.get("cooldown_global")
    if cooldown_global is not None:
        if not isinstance(cooldown_global, (int, float)) or cooldown_global < 0:
            erros.append(f"{caminho}: cooldown_global precisa ser nao negativo")
        elif cooldown_global > cooldown:
            erros.append(
                f"{caminho}: cooldown_global maior que cooldown_viewer torna o "
                "limite por espectador inalcancavel"
            )

    maximo = dados.get("max_por_round")
    if not isinstance(maximo, int) or isinstance(maximo, bool) or maximo < 1:
        erros.append(f"{caminho}: max_por_round precisa ser inteiro >= 1")


def _validar_momentos(
    caminho: str,
    dados: dict,
    categoria: str,
    catalogo: dict,
    erros: list[str],
) -> None:
    momentos = dados.get("aplicavel_em")
    if not isinstance(momentos, (tuple, list)) or not momentos:
        erros.append(f"{caminho}: aplicavel_em precisa listar ao menos um momento")
        return
    for momento in momentos:
        if momento not in catalogo["MOMENTOS"]:
            erros.append(f"{caminho}: momento desconhecido {momento!r}")
    if categoria == "PROXIMO_ROUND" and "ENTRE_ROUNDS" not in momentos:
        erros.append(
            f"{caminho}: comando de proximo round precisa ser aplicavel ENTRE_ROUNDS"
        )


def _validar_skill(
    caminho: str,
    dados: dict,
    efeito: str,
    escopo: str,
    catalogo: dict,
    skills: dict[str, dict],
    erros: list[str],
) -> None:
    skill = dados.get("skill")
    exige_skill = efeito in catalogo["EFEITOS_COM_SKILL"]

    if exige_skill and not skill:
        erros.append(f"{caminho}: efeito {efeito} exige o campo 'skill'")
        return
    if not exige_skill and skill:
        erros.append(f"{caminho}: efeito {efeito} nao aceita o campo 'skill'")
        return
    if not skill:
        return

    if skill not in skills:
        erros.append(f"{caminho}: skill inexistente no catalogo canonico: {skill!r}")
        return

    dados_skill = skills[skill]
    if escopo == "GLOBAL":
        # No escopo global o dono da area e um acidente de instanciacao; campo
        # que beneficia o dono distribuiria vantagem a quem ninguem escolheu.
        for campo in catalogo["CAMPOS_INJUSTOS_EM_GLOBAL"]:
            if campo in dados_skill:
                erros.append(
                    f"{caminho}: skill {skill!r} tem {campo!r}, que beneficia o "
                    "dono e nao pode aparecer em escopo GLOBAL"
                )
        if efeito != "AREA_SKILL":
            erros.append(f"{caminho}: escopo GLOBAL so suporta AREA_SKILL")
        if dados_skill.get("afeta_caster"):
            erros.append(
                f"{caminho}: skill {skill!r} tem afeta_caster; o escopo GLOBAL "
                "ja instancia uma area por lutador e atingiria em dobro"
            )


def _validar_arenas(
    caminho: str,
    dados: dict,
    efeito: str,
    arenas: set[str],
    erros: list[str],
) -> None:
    declaradas = dados.get("arenas")
    if efeito == "TROCAR_ARENA":
        if not declaradas:
            erros.append(f"{caminho}: efeito TROCAR_ARENA exige a lista 'arenas'")
            return
        for arena in declaradas:
            if arena not in arenas:
                erros.append(f"{caminho}: arena inexistente: {arena!r}")
    elif declaradas:
        erros.append(f"{caminho}: campo 'arenas' so faz sentido em TROCAR_ARENA")


def _validar_gatilhos_unicos(comandos: dict, erros: list[str]) -> None:
    vistos: dict[str, str] = {}
    for command_id, dados in comandos.items():
        gatilho = dados.get("gatilho") if isinstance(dados, dict) else None
        if not gatilho:
            continue
        if gatilho in vistos:
            erros.append(
                f"gatilho duplicado {gatilho!r}: {vistos[gatilho]!r} e {command_id!r}"
            )
        vistos[gatilho] = command_id


# ------------------------------------------------------- evidencia de runtime


def _classes_e_metodos(caminho: Path) -> dict[str, set[str]]:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    encontrados: dict[str, set[str]] = {}
    for no in ast.walk(arvore):
        if isinstance(no, ast.ClassDef):
            encontrados.setdefault(no.name, set()).update(
                filho.name
                for filho in no.body
                if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
    return encontrados


def _validar_evidencias(
    comandos: dict,
    *,
    verificar_fontes: bool,
    erros: list[str],
    avisos: list[str],
) -> None:
    evidencias = _atribuicoes_literais(CAMINHO_EVIDENCIAS).get("COMMAND_RUNTIME_EVIDENCE")
    if evidencias is None:
        erros.append("manifesto de evidencias ausente ou ilegivel")
        return

    faltando = set(comandos) - set(evidencias)
    for command_id in sorted(faltando):
        erros.append(f"comando sem entrada no manifesto de evidencias: {command_id!r}")

    sobrando = set(evidencias) - set(comandos)
    for command_id in sorted(sobrando):
        erros.append(f"manifesto aponta comando inexistente: {command_id!r}")

    for command_id, referencias in sorted(evidencias.items()):
        if not referencias:
            avisos.append(f"{command_id!r}: sem evidencia de runtime declarada")
            continue
        if not verificar_fontes:
            continue
        for referencia in referencias:
            _conferir_referencia(command_id, referencia, erros)


def _conferir_referencia(command_id: str, referencia: Any, erros: list[str]) -> None:
    if not isinstance(referencia, (tuple, list)) or len(referencia) != 3:
        erros.append(f"{command_id!r}: evidencia precisa ser (modulo, classe, metodo)")
        return
    modulo, classe, metodo = referencia
    caminho = RAIZ_CHECKOUT / Path(*str(modulo).split(".")).with_suffix(".py")
    if not caminho.is_file():
        erros.append(f"{command_id!r}: modulo de teste inexistente: {modulo}")
        return
    try:
        membros = _classes_e_metodos(caminho)
    except (OSError, SyntaxError) as exc:
        erros.append(f"{command_id!r}: nao foi possivel ler {modulo}: {exc}")
        return
    if classe not in membros:
        erros.append(f"{command_id!r}: classe inexistente em {modulo}: {classe}")
        return
    if not str(metodo).startswith("test_"):
        erros.append(f"{command_id!r}: evidencia precisa apontar para um test_*: {metodo}")
        return
    if metodo not in membros[classe]:
        erros.append(f"{command_id!r}: metodo inexistente em {modulo}.{classe}: {metodo}")


# ------------------------------------------------------------------ execucao


def auditar(*, verificar_fontes: bool = False) -> tuple[list[str], list[str]]:
    erros: list[str] = []
    avisos: list[str] = []

    catalogo = _atribuicoes_literais(CAMINHO_CATALOGO)
    comandos = catalogo.get("COMMAND_DB")
    if not isinstance(comandos, dict):
        raise ProblemaDeCatalogo("COMMAND_DB ausente ou nao literal em catalog.py")

    for chave in _chaves_duplicadas(CAMINHO_CATALOGO, "COMMAND_DB"):
        erros.append(f"COMMAND_DB tem a chave duplicada {chave!r}")

    skills = _dados_de_skills()
    arenas = _nomes_de_arenas()
    if not skills:
        raise ProblemaDeCatalogo("SKILL_DB nao pode ser lido por AST")
    if not arenas:
        raise ProblemaDeCatalogo("ARENAS nao pode ser lido por AST")

    for command_id, dados in sorted(comandos.items()):
        _validar_comando(
            command_id,
            dados,
            catalogo=catalogo,
            skills=skills,
            arenas=arenas,
            erros=erros,
            avisos=avisos,
        )

    _validar_gatilhos_unicos(comandos, erros)
    _validar_evidencias(
        comandos, verificar_fontes=verificar_fontes, erros=erros, avisos=avisos
    )
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
        description="Auditoria estrutural do vocabulario de comandos de live"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="avisos tambem bloqueiam, com codigo de saida 2",
    )
    parser.add_argument(
        "--verify-evidence-sources",
        action="store_true",
        help="confere por AST que cada evidencia aponta para um teste existente",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        erros, avisos = auditar(verificar_fontes=args.verify_evidence_sources)
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
