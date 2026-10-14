"""O que o Adrian ja fez: a esteira nunca pede de novo.

14/10/2026, religando a esteira com o ChatGPT: o Adrian faz sprites dele pelo
Atelie do app, e a IA nao pode refazer por cima. Um item esta feito quando:

1. **o Atelie tem folha dele**: `palco/biblioteca/animacoes/<peca>/<estado>/
   <animacao>/folha.png` (o `historico/` nao conta: e versao velha). Na Vila a
   chave e a mesma que o Atelie e a Vila usam (`catalogo_vila.chave_do_item`);
   no palco, a pasta do `nome_arquivo` aponta a familia do catalogo
   (`PALCO_NO_ATELIE`) e o nome do arquivo e a peca. Qualquer animacao da peca
   conta, porque e o Adrian quem desenha aquela peca agora;
2. **o destino ja esta ocupado**: a arte do item ja existe na biblioteca (a Vila
   em `painel/flutuante/arte_vila/<nome_arquivo>`; o palco em
   `palco/biblioteca/<nome_arquivo>` ou onde o `aprovar` exportaria). O
   `aprovar` nunca sobrescreve, entao pedir isso so gastaria a vez do ChatGPT.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath

from . import config

# pasta do `nome_arquivo` no inventario do palco -> familia da peca no catalogo
# do Atelie (`palco/biblioteca/catalogo_animacoes.json`), medido em 14/10/2026
PALCO_NO_ATELIE = {
    "armas/estilos": "arma.estilo",
    "efeitos/orbes": "arma.estilo",          # o orbe e o "orbitando" da arma magica
    "lutadores/estados": "estado_lutador",
    "lutadores/status": "estado",
    "lutadores/buffs": "skill",
    "lutadores/canais": "skill",
    "lutadores/transformacoes": "skill",
    "efeitos/pecas/skills": "skill",
    "efeitos/folhas/skills": "skill",        # <skill>_erupcao etc.: tenta tambem <skill>
    "lutadores/pecas": "lutador",
}


def _nome(item: dict) -> str:
    return str(item.get("nome_arquivo") or "").split(" (")[0].strip().replace("\\", "/")


def pastas_no_atelie(item: dict) -> list[Path]:
    """As pastas de peca/estado do Atelie que, com folha, dizem que o item e dele."""
    if config.PERFIL == "vila":
        from neural_fights.tools import catalogo_vila
        chave = catalogo_vila.chave_do_item(item)
        return [config.ATELIE / chave[0] / chave[1]] if chave else []
    nome = PurePosixPath(_nome(item))
    familia = PALCO_NO_ATELIE.get(str(nome.parent))
    if not familia or not nome.stem:
        return []
    candidatos = [nome.stem]
    if str(nome.parent) == "efeitos/folhas/skills" and "_" in nome.stem:
        candidatos.append(nome.stem.rsplit("_", 1)[0])
    return [config.ATELIE / f"{familia}.{c}" for c in candidatos]


def no_atelie(item: dict) -> Path | None:
    """A folha do Adrian no Atelie para este item, ou None."""
    for pasta in pastas_no_atelie(item):
        if not pasta.is_dir():
            continue
        for folha in sorted(pasta.rglob("folha.png")):
            if "historico" not in folha.relative_to(pasta).parts:
                return folha
    return None


def destino_ocupado(item: dict) -> Path | None:
    """A arte que ja esta onde o item iria morar, ou None."""
    nome = _nome(item)
    if config.PERFIL == "vila":
        raiz = config.biblioteca()
        if raiz and nome:
            for alvo in (raiz / nome, (raiz / nome).with_suffix(".json")):
                if alvo.exists():
                    return alvo
        return None
    if nome and (config.BIBLIOTECA_PALCO / nome).exists():
        return config.BIBLIOTECA_PALCO / nome
    from painel.sprites import exportar
    # onde o `aprovar` do palco escreveria (a mesma identidade de `aprovar._identidade`)
    ident = exportar.Identidade(nome=item["id"], tipo="skill", skill=item["id"])
    existentes = exportar.ja_existem(ident, config.BIBLIOTECA_PALCO)
    return Path(existentes[0]) if existentes else None


def motivo(item: dict) -> str:
    """Por que o item nao deve ser pedido ('' = pode pedir)."""
    folha = no_atelie(item)
    if folha:
        return f"o Adrian ja fez no Atelie ({folha})"
    ocupado = destino_ocupado(item)
    if ocupado:
        return f"a arte ja esta na biblioteca ({ocupado})"
    return ""
