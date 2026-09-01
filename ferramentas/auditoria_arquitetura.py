# -*- coding: utf-8 -*-
"""A arquitetura do repositorio piorou? Uma catraca, nao um relatorio.

    python ferramentas/auditoria_arquitetura.py            mostra o estado
    python ferramentas/auditoria_arquitetura.py --strict    falha se PIOROU
    python ferramentas/auditoria_arquitetura.py --gravar    fixa o novo teto

Por que existe: a reorganizacao de 01/09/2026 tem seis etapas, e entre elas
e facil reintroduzir exatamente o que se acabou de tirar - mais uma cirurgia
de `sys.path`, mais um pacote com nome repetido. Um relatorio que so imprime
numeros ninguem le. Uma catraca que fecha em vermelho quando o numero SOBE,
sim.

Nao exige que os numeros sejam zero: exige que nao aumentem. Isso e o que
torna a ferramenta util JA na etapa 0, com 41 mutacoes de `sys.path` no
lugar - em vez de so no fim, quando ja nao adianta.

O que ele mede, e por que cada coisa esta aqui:

  SYS.PATH      cada `sys.path.insert/append` e uma importacao que so
                funciona por acidente de diretorio atual. Eram 41.
  NOMES         dois pacotes de topo com o mesmo nome (`src` e `src`): o
                que ganha depende da ORDEM do sys.path, e um pacote regular
                ganha de um namespace PEP 420 SEM ERRO NENHUM. Foi assim que
                o painel ficou impedido de importar o outro projeto.
  COLISAO       pacote com o nome de um diretorio da raiz. Verificado nesta
                maquina: `import historias` da raiz ja devolve um namespace
                VAZIO (`__file__ = None`), porque o PathFinder acha o
                diretorio antes de o finder do editable install ser
                consultado. Por isso o pacote se chama `contos`.
  ANCORAS       `Path(__file__).resolve().parents[N]` resolve caminho por
                PROFUNDIDADE. Mover um arquivo de nivel quebra a ancora em
                SILENCIO: a funcao passa a olhar a pasta errada e devolve
                lista vazia, sem excecao e sem teste vermelho.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BASELINE = Path(__file__).resolve().parent / "arquitetura_baseline.json"

IGNORAR = ("__pycache__", ".venv", "venv", "build", "dist", ".git",
           ".ruff_cache", ".pytest_cache", "node_modules", ".browser_profile")

# Mutacao de sys.path que e legitima e nao entra na conta. Mantenha esta
# lista CURTA e com o motivo escrito - allowlist que cresce sem justificativa
# e o mesmo que nao ter catraca.
PERDOADAS = {
    # A propria auditoria nao mexe em sys.path; o slot fica documentado para
    # quando uma excecao real aparecer, com o porque ao lado.
}


ESTE_ARQUIVO = Path(__file__).resolve()


def _fontes():
    for caminho in RAIZ.rglob("*.py"):
        if any(parte in IGNORAR for parte in caminho.parts):
            continue
        # A propria auditoria contem os literais que ela procura. Contar a si
        # mesma inflaria o teto e, pior, esconderia uma reintroducao real
        # atras da propria margem.
        if caminho.resolve() == ESTE_ARQUIVO:
            continue
        yield caminho


def _relativo(caminho: Path) -> str:
    try:
        return caminho.relative_to(RAIZ).as_posix()
    except ValueError:
        return str(caminho)


def mutacoes_de_path() -> list:
    """Cada `sys.path.insert/append` do repositorio, com arquivo e linha."""
    achados = []
    for caminho in _fontes():
        try:
            texto = caminho.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "sys.path" not in texto:
            continue
        for numero, linha in enumerate(texto.splitlines(), 1):
            limpa = linha.strip()
            if limpa.startswith("#"):
                continue
            if "sys.path.insert" in limpa or "sys.path.append" in limpa:
                onde = f"{_relativo(caminho)}:{numero}"
                if onde not in PERDOADAS:
                    achados.append(onde)
    return sorted(achados)


def _e_pacote(pasta: Path) -> bool:
    """Pasta com .py dentro conta como pacote, com ou sem __init__.py.

    Sem `__init__.py` ela e um namespace PEP 420 - que importa do mesmo
    jeito e colide do mesmo jeito, so que em silencio.
    """
    if any(parte in IGNORAR for parte in pasta.parts):
        return False
    return any(pasta.glob("*.py"))


def pacotes_de_topo() -> dict:
    """{nome: [caminhos]} dos pacotes que podem virar import de topo."""
    encontrados = {}
    for pasta in [RAIZ] + [d for d in RAIZ.iterdir() if d.is_dir()]:
        if pasta != RAIZ and any(p in IGNORAR for p in pasta.parts):
            continue
        for filho in pasta.iterdir() if pasta.is_dir() else []:
            if filho.is_dir() and _e_pacote(filho):
                encontrados.setdefault(filho.name, []).append(_relativo(filho))
    return encontrados


def nomes_repetidos() -> dict:
    return {n: c for n, c in pacotes_de_topo().items() if len(c) > 1}


def colisoes_com_a_raiz() -> list:
    """Pacote cujo nome e tambem um diretorio da raiz que nao e ele mesmo.

    O caso real: `historias/` (sem __init__.py) sombreia qualquer pacote
    instalado chamado `historias`, devolvendo namespace vazio.
    """
    da_raiz = {d.name for d in RAIZ.iterdir()
               if d.is_dir() and not any(p in IGNORAR for p in d.parts)}
    ruins = []
    for nome, caminhos in pacotes_de_topo().items():
        if nome in da_raiz and nome not in caminhos:
            ruins.append(f"{nome} (pacote em {caminhos[0]} x pasta ./{nome})")
    return sorted(ruins)


def ancoras_quebradas() -> list:
    """`parents[N]` que aponta para um caminho que nao existe."""
    quebradas = []
    for caminho in _fontes():
        try:
            texto = caminho.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "parents[" not in texto:
            continue
        try:
            arvore = ast.parse(texto)
        except SyntaxError:
            continue
        for no in ast.walk(arvore):
            if not (isinstance(no, ast.Subscript)
                    and isinstance(no.value, ast.Attribute)
                    and no.value.attr == "parents"):
                continue
            indice = no.slice
            if not (isinstance(indice, ast.Constant)
                    and isinstance(indice.value, int)):
                continue
            nivel = indice.value
            try:
                alvo = caminho.resolve().parents[nivel]
            except IndexError:
                quebradas.append(
                    f"{_relativo(caminho)}:{no.lineno} parents[{nivel}] "
                    "passa da raiz do disco")
                continue
            if not alvo.exists():
                quebradas.append(
                    f"{_relativo(caminho)}:{no.lineno} parents[{nivel}] "
                    f"-> {alvo} (nao existe)")
    return sorted(quebradas)


def medir() -> dict:
    return {
        "sys_path": mutacoes_de_path(),
        "nomes_repetidos": nomes_repetidos(),
        "colisoes_com_a_raiz": colisoes_com_a_raiz(),
        "ancoras_quebradas": ancoras_quebradas(),
    }


def _contagens(dados: dict) -> dict:
    return {chave: len(valor) for chave, valor in dados.items()}


def _ler_baseline() -> dict:
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def imprimir(dados: dict, teto: dict, detalhar: bool) -> None:
    agora = _contagens(dados)
    print("=" * 68)
    print("ARQUITETURA — quanto ainda falta desmontar")
    print("=" * 68)
    rotulos = {
        "sys_path": "cirurgias de sys.path",
        "nomes_repetidos": "nomes de pacote repetidos",
        "colisoes_com_a_raiz": "pacote x pasta da raiz",
        "ancoras_quebradas": "ancoras parents[N] quebradas",
    }
    for chave, rotulo in rotulos.items():
        atual, limite = agora[chave], teto.get(chave)
        if limite is None:
            marca, nota = " ? ", "sem teto gravado"
        elif atual > limite:
            marca, nota = "PIOR", f"teto {limite}"
        elif atual < limite:
            marca, nota = "  +", f"era {limite}"
        else:
            marca, nota = "  =", f"teto {limite}"
        print(f"  [{marca}] {rotulo:32} {atual:4}   ({nota})")
        if detalhar and dados[chave]:
            itens = dados[chave]
            for item in (itens if isinstance(itens, list) else
                         [f"{n}: {', '.join(c)}" for n, c in itens.items()]):
                print(f"          {item}")
    print("=" * 68)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="auditoria_arquitetura",
        description="catraca: falha quando a arquitetura PIORA")
    parser.add_argument("--strict", action="store_true",
                        help="sai 1 se algum numero subiu")
    parser.add_argument("--gravar", action="store_true",
                        help="fixa os numeros atuais como novo teto")
    parser.add_argument("--detalhe", action="store_true",
                        help="lista arquivo e linha de cada ocorrencia")
    args = parser.parse_args(argv)

    dados = medir()
    teto = _ler_baseline()
    imprimir(dados, teto, args.detalhe or args.strict)

    if args.gravar:
        BASELINE.write_text(
            json.dumps(_contagens(dados), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        print(f"teto gravado em {_relativo(BASELINE)}")
        return 0

    if not args.strict:
        return 0

    agora = _contagens(dados)
    piorou = [c for c, v in agora.items()
              if teto.get(c) is not None and v > teto[c]]
    if piorou:
        print("PIOROU: " + ", ".join(piorou))
        print("Se a piora for intencional, rode --gravar e explique no commit.")
        return 1
    print("nada piorou.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
