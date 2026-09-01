# -*- coding: utf-8 -*-
"""O que ha no banco agora: contagem, os ultimos cadastrados e os arquivos.

    python -m neural_fights.tools.resumo_banco

Por que existe como MODULO: ate 01/09/2026 este texto era uma string de
codigo Python de 18 linhas dentro do painel (`RESUMO_BANCO`), executada com
`python -c`. Codigo dentro de string nao passa por linter, nao entra em
teste, nao aparece em busca por simbolo e quebra em silencio quando a API
que ele usa muda. Aqui e um modulo como os outros `neural_fights.tools.*`
que o painel ja chama.

O painel continua rodando isto por subprocesso de proposito: a saida vai
escorrendo para o console dele linha a linha, e ler o banco fora da thread
da interface e o que impede a janela de congelar.
"""
from __future__ import annotations

from neural_fights.data import database

QUANTOS = 5


def linhas() -> list[str]:
    """O resumo como lista de linhas — testavel sem capturar stdout."""
    armas, personagens = database.carregar_database()
    saida = [f"{len(personagens)} personagens | {len(armas)} armas", ""]

    saida.append(f"Ultimos {QUANTOS} personagens:")
    for p in personagens[-QUANTOS:]:
        saida.append(f"  - {p['nome']} ({p['classe']}, forca {p['forca']}, "
                     f"arma: {p['nome_arma']})")
    saida.append("")

    saida.append(f"Ultimas {QUANTOS} armas:")
    for a in armas[-QUANTOS:]:
        saida.append(f"  - {a['nome']} ({a['tipo']}/{a['estilo']}, "
                     f"{a['raridade']}, dano {a['dano']})")

    caminhos = database.resolver_database_paths(para_escrita=False)
    saida += ["", f"Arquivos: {caminhos[0]}", f"          {caminhos[1]}"]
    return saida


def main(argv=None) -> int:
    for linha in linhas():
        print(linha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
