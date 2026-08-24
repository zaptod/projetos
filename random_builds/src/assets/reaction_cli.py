"""Assistente interativo da biblioteca de reacoes.

`python main.py reactions` abre um menu para inserir e categorizar videos:
  - modo INDIVIDUAL: um arquivo, mostra duracao/resolucao, escolhe categoria
  - modo LOTE: uma pasta inteira — mesma categoria para todos, ou
    categorizando video por video
  - listar, recategorizar e remover por ID

Para uso em scripts, o comando nao-interativo continua existindo:
  python main.py import-reactions <pasta> --categoria insane
"""
from __future__ import annotations

from pathlib import Path

from .catalog import CATEGORIES, VIDEO_EXT
from .importer import (import_reactions, list_reactions, probe_info,
                       recategorize_reaction, remove_reaction)

CATEGORY_DESC = {
    "terrible": "rolagem HORRIVEL (fracasso total, risada)",
    "bad": "rolagem ruim (decepcao)",
    "neutral": "rolagem mediana (sem emocao)",
    "good": "rolagem boa (aprovacao)",
    "great": "rolagem otima (empolgacao)",
    "insane": "rolagem INSANA (hype maximo)",
    "funny": "resultado ENGRACADO (absurdo por comedia, nao por forca)",
    "contradictory": "resultado CONTRADITORIO (briga com o resto da build)",
    "rare": "resultado RARO (improvavel de sair, bom ou nao)",
}


def _ask(prompt: str) -> str | None:
    """input() que devolve None em cancelamento (vazio, Ctrl+C ou EOF)."""
    try:
        answer = input(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return None
    return answer or None


def _ask_category(extra: str = "") -> str | None:
    print("\nCategorias:")
    for i, cat in enumerate(CATEGORIES, start=1):
        print(f"  [{i}] {cat:<9} - {CATEGORY_DESC[cat]}")
    answer = _ask(f"Categoria (1-{len(CATEGORIES)} ou nome{extra}, vazio cancela): ")
    if answer is None:
        return None
    lowered = answer.lower()
    if lowered in ("s", "q"):
        return lowered  # pular / sair (usado no lote video-a-video)
    if lowered in CATEGORIES:
        return lowered
    if lowered.isdigit() and 1 <= int(lowered) <= len(CATEGORIES):
        return CATEGORIES[int(lowered) - 1]
    print("  Opcao invalida.")
    return _ask_category(extra)


def _clean_path(raw: str) -> Path:
    return Path(raw.strip().strip('"').strip("'"))


def _describe(file: Path) -> str:
    info = probe_info(file)
    duracao = f"{info['duration']}s" if info["duration"] else "?s"
    res = (f"{info['width']}x{info['height']}"
           if info["width"] else "resolucao desconhecida")
    return f"{file.name}  ({duracao}, {res})"


def _print_imported(imported: list[dict]) -> None:
    for entry in imported:
        duracao = f"{entry['duration']}s" if entry["duration"] else "?s"
        print(f"  [OK] ID {entry['id']} <- {entry['source']} "
              f"({entry['category']}, {duracao})")


# ------------------------------------------------------------------ modos
def _modo_individual(assets_dir: Path) -> None:
    raw = _ask("\nCaminho do video: ")
    if raw is None:
        return
    file = _clean_path(raw)
    if not file.is_file():
        print(f"  Arquivo nao encontrado: {file}")
        return
    if file.suffix.lower() not in VIDEO_EXT:
        print(f"  Extensao nao suportada ({file.suffix}). "
              f"Use: {', '.join(sorted(VIDEO_EXT))}")
        return
    print(f"  Video: {_describe(file)}")
    category = _ask_category()
    if category in (None, "s", "q"):
        print("  Cancelado.")
        return
    mover = (_ask("Mover em vez de copiar? (s/N): ") or "n").lower() == "s"
    _print_imported(import_reactions(file, category, assets_dir, move=mover))


def _modo_lote(assets_dir: Path) -> None:
    raw = _ask("\nPasta com os videos: ")
    if raw is None:
        return
    folder = _clean_path(raw)
    if not folder.is_dir():
        print(f"  Pasta nao encontrada: {folder}")
        return
    files = sorted(f for f in folder.iterdir() if f.suffix.lower() in VIDEO_EXT)
    if not files:
        print("  Nenhum video na pasta.")
        return
    print(f"\n  {len(files)} video(s) encontrados:")
    for file in files:
        print(f"    - {_describe(file)}")

    print("\nComo categorizar?")
    print("  [1] mesma categoria para todos")
    print("  [2] escolher a categoria video por video")
    modo = _ask("Modo (1/2, vazio cancela): ")
    if modo is None:
        print("  Cancelado.")
        return
    mover = (_ask("Mover em vez de copiar? (s/N): ") or "n").lower() == "s"

    if modo == "1":
        category = _ask_category()
        if category in (None, "s", "q"):
            print("  Cancelado.")
            return
        _print_imported(import_reactions(folder, category, assets_dir, move=mover))
        return

    total = 0
    for i, file in enumerate(files, start=1):
        print(f"\n[{i}/{len(files)}] {_describe(file)}")
        category = _ask_category(", s pula, q encerra")
        if category is None or category == "q":
            break
        if category == "s":
            print("  Pulado.")
            continue
        _print_imported(import_reactions(file, category, assets_dir, move=mover))
        total += 1
    print(f"\n  Lote concluido: {total} video(s) importados.")


def _listar(assets_dir: Path) -> None:
    entries = list_reactions(assets_dir)
    if not entries:
        print("\n  Biblioteca vazia.")
        return
    print()
    for entry in entries:
        duracao = f"{entry['duration']}s" if entry.get("duration") else "?s"
        print(f"  {entry['id']}  {entry['category']:<9} {duracao:>6}  "
              f"({entry.get('source', '')})")
    print(f"  Total: {len(entries)} reacao(oes)")


def _recategorizar(assets_dir: Path) -> None:
    _listar(assets_dir)
    asset_id = _ask("\nID do video (ex.: 0001, vazio cancela): ")
    if asset_id is None:
        return
    category = _ask_category()
    if category in (None, "s", "q"):
        print("  Cancelado.")
        return
    entry = recategorize_reaction(asset_id, category, assets_dir)
    print(f"  [OK] {asset_id} agora e '{category}'." if entry
          else f"  ID nao encontrado: {asset_id}")


def _remover(assets_dir: Path) -> None:
    _listar(assets_dir)
    asset_id = _ask("\nID do video a REMOVER (vazio cancela): ")
    if asset_id is None:
        return
    confirma = (_ask(f"Remover {asset_id} definitivamente? (s/N): ") or "n").lower()
    if confirma != "s":
        print("  Cancelado.")
        return
    entry = remove_reaction(asset_id, assets_dir)
    print(f"  [OK] {asset_id} removido ({entry['source']})." if entry
          else f"  ID nao encontrado: {asset_id}")


# ------------------------------------------------------------------- menu
def run(assets_dir: Path) -> None:
    print("=" * 56)
    print("  BIBLIOTECA DE REACOES - Random Builds")
    print("=" * 56)
    while True:
        print("\n  [1] Adicionar video (individual)")
        print("  [2] Adicionar em lote (pasta)")
        print("  [3] Listar biblioteca")
        print("  [4] Recategorizar video")
        print("  [5] Remover video")
        print("  [0] Sair")
        opcao = _ask("Opcao: ")
        if opcao in (None, "0"):
            print("Ate mais!")
            return
        if opcao == "1":
            _modo_individual(assets_dir)
        elif opcao == "2":
            _modo_lote(assets_dir)
        elif opcao == "3":
            _listar(assets_dir)
        elif opcao == "4":
            _recategorizar(assets_dir)
        elif opcao == "5":
            _remover(assets_dir)
        else:
            print("  Opcao invalida.")
