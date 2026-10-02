"""Monta as paginas do Inventario de Sprites a partir do JSON do repositorio."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[3]
CAMPOS = ["grupo", "subgrupo", "id", "descricao", "nome_arquivo", "tipo", "quadros", "tamanho",
          "fundo", "prioridade", "presenca_txt", "arte_atual", "existe", "caminho_existente",
          "falta", "compartilha", "opcional", "bloqueio", "notas", "ordem"]


def argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pagina_app", help="identificador da pagina servida pelo app")
    p.add_argument("--dados", type=Path, default=RAIZ / "docs/palco/inventario_sprites.json",
                   help="JSON de inventario (padrao: docs/palco/inventario_sprites.json)")
    p.add_argument("--saida", type=Path, default=RAIZ / "outputs/inventario",
                   help="diretorio das duas paginas geradas (padrao: outputs/inventario)")
    return p.parse_args()


def montar(dados: Path, saida: Path, pagina_app: str) -> tuple[Path, Path]:
    bruto = json.loads(dados.read_text(encoding="utf-8"))
    itens = [{k: item.get(k) for k in CAMPOS} for item in bruto["itens"]]
    texto = json.dumps(itens, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    molde = (Path(__file__).parent / "molde.html").read_text(encoding="utf-8")
    if "/*__DADOS__*/[]" not in molde or '"__PAGINA_APP__"' not in molde:
        raise ValueError("molde sem os placeholders esperados")
    base = molde.replace("/*__DADOS__*/[]", texto)
    saida.mkdir(parents=True, exist_ok=True)
    claude = saida / "inventario_sprites.html"
    app = saida / "inventario_app.html"
    claude.write_text(base, encoding="utf-8")
    app.write_text(base.replace('"__PAGINA_APP__"', json.dumps(pagina_app)), encoding="utf-8")
    return claude, app


def principal() -> int:
    a = argumentos()
    claude, app = montar(a.dados, a.saida, a.pagina_app)
    print(f"paginas montadas: {claude} e {app}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
