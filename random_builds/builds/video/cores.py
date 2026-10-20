"""A cor de cada lado de uma luta: a do CORPO na arena e a do HUD do video.

Ate 20/10/2026 o desempate de duas cores parecidas era so do renderer: o
`duelo_00122` (Sigrid magenta 234,0,226 x Vesperia violeta 169,35,237) saiu
com a faixa e o HUD do lado 2 em VERDE e o lutador VIOLETA na arena — quem
assiste procura o verde e nao acha (conferente, 20/10/2026).

Agora o desempate e decidido UMA vez, antes de gravar (`cores_da_gravacao`),
vai ao gravador (`match_config["cores_da_tela"]`, so exibicao: nenhuma
decisao da luta le a cor) e volta no resultado como `cores_na_tela` — a cor
que o corpo TEVE no clipe. O renderer pinta o HUD, a faixa, a identidade e o
veredito com ela (`cores_do_clipe`). Clipe gravado antes disto nao tem a
chave: o corpo e a cor do banco, e o HUD tambem (sem giro).

O giro continua o da Onda 15C: o lado 2 gira o PROPRIO matiz por um valor
derivado do nome dele (crc32), entao a cor desempatada de um lutador e a
mesma contra qualquer adversario.
"""
from __future__ import annotations

import colorsys
import zlib

# Distancia L1 minima entre as cores dos dois lados. Abaixo disto o
# espectador nao separa quem e quem — dois verdes viram um borrao.
DISTANCIA_MINIMA_DE_COR = 140

# A cor que o jogo usa quando a ficha nao tem cor (Personagem: 200, 50, 50).
COR_PADRAO_DO_JOGO = (200, 50, 50)


def cor_da_ficha(ficha: dict | None, padrao=COR_PADRAO_DO_JOGO) -> tuple:
    """A cor com que o JOGO pinta o corpo desta ficha
    (``Simulador.cor_base_do_corpo``): canal 0 vira o padrao (``x or 50``) —
    a Sigrid do banco e 234,0,226 e o corpo dela na arena, 234,50,226."""
    ficha = ficha or {}
    return tuple(int(ficha.get(chave) or p)
                 for chave, p in zip(("cor_r", "cor_g", "cor_b"), padrao))


def distancia(a, b) -> int:
    return sum(abs(int(x) - int(y)) for x, y in zip(a, b))


def girar_matiz(cor: tuple, nome: str) -> tuple:
    """Desloca o MATIZ de uma cor por um giro derivado do nome.

    Deterministico e estavel: o mesmo lutador recebe sempre o mesmo
    deslocamento, contra qualquer adversario. crc32, nao `hash()`: o hash de
    str do Python e randomizado por processo (PYTHONHASHSEED), e a cor do
    lutador mudaria a cada gravacao — o mesmo padrao de `identity/prompt.py`.
    """
    h, l, s = colorsys.rgb_to_hls(*[c / 255.0 for c in cor])
    semente = zlib.crc32(nome.encode("utf-8"))
    # 0,28 a 0,72 de volta: longe o bastante para separar, e sem chegar
    # perto de uma volta inteira (que devolveria a cor original).
    giro = 0.28 + (semente % 1000) / 1000.0 * 0.44
    r, g, b = colorsys.hls_to_rgb((h + giro) % 1.0, max(0.45, l), max(0.55, s))
    return (int(r * 255), int(g * 255), int(b * 255))


def cores_desempatadas(cor1, cor2, nome2: str) -> tuple[tuple, tuple]:
    """As duas cores com contraste: se forem parecidas, o lado 2 gira."""
    cor1, cor2 = tuple(cor1), tuple(cor2)
    if distancia(cor1, cor2) < DISTANCIA_MINIMA_DE_COR:
        cor2 = girar_matiz(cor2, str(nome2 or ""))
    return cor1, cor2


def cores_da_gravacao(ficha1: dict | None, ficha2: dict | None,
                      nome2: str) -> dict:
    """O que o gravador recebe em ``cores_da_tela``: a cor do CORPO de cada
    lado, ja desempatada. Cores distantes saem iguais as do banco."""
    cor1, cor2 = cores_desempatadas(cor_da_ficha(ficha1), cor_da_ficha(ficha2), nome2)
    # o giro pode dar canal 0, que o jogo pinta como o padrao (``x or 50``):
    # ja sai normalizado, para o corpo e o HUD serem o MESMO numero
    return {"p1": list(cor_da_ficha(dict(zip(("cor_r", "cor_g", "cor_b"), cor1)))),
            "p2": list(cor_da_ficha(dict(zip(("cor_r", "cor_g", "cor_b"), cor2))))}


def _cor_valida(cor) -> tuple | None:
    if not isinstance(cor, (list, tuple)) or len(cor) != 3:
        return None
    try:
        valores = tuple(int(c) for c in cor)
    except (TypeError, ValueError):
        return None
    if not all(0 <= c <= 255 for c in valores):
        return None
    return valores


def cores_do_clipe(luta: dict | None) -> tuple[tuple, tuple] | None:
    """A cor que o corpo de cada lado TEVE no clipe (``luta["cores_na_tela"]``,
    o que o gravador devolveu), ou None para clipe gravado antes de 20/10."""
    cores = (luta or {}).get("cores_na_tela")
    if not isinstance(cores, dict):
        return None
    cor1, cor2 = _cor_valida(cores.get("p1")), _cor_valida(cores.get("p2"))
    if cor1 is None or cor2 is None:
        return None
    return cor1, cor2
