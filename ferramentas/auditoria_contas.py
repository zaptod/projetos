# -*- coding: utf-8 -*-
"""Cada caminho de publicacao, e em qual canal ele desemboca.

    python ferramentas/auditoria_contas.py

A pergunta que isto responde e uma so, e e a que nao tem desfazer: SE EU
PUBLICAR AGORA, ONDE ISSO VAI PARAR? Ate 08/09/2026 so dava para responder
abrindo o navegador, porque os nomes das contas nao diziam nada — `principal`
significava tres destinos diferentes conforme o servico, o mesmo canal do
YouTube atendia por dois nomes, e uma conta se chamava `canal2`.

Sai 1 quando algo foge do padrao de nomes (`contas.conformidade`), para poder
entrar num gancho de CI ou num atalho do painel.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from builds import contas                                      # noqa: E402

LARGURA = 78


def _linha(texto: str = "") -> None:
    sys.stdout.buffer.write((texto + "\n").encode("utf-8", "replace"))


def mapa() -> None:
    _linha("=" * LARGURA)
    _linha("CAMINHOS DE PUBLICACAO — para onde cada canal vai")
    _linha("=" * LARGURA)
    for servico, ficha in contas.SERVICOS.items():
        if not ficha.get("publica"):
            continue
        _linha(f"\n{ficha['rotulo']}  ({servico})")
        for canal in contas.CANAIS:
            destino = contas.destino(servico, canal)
            marca = " " if destino["explicita"] else "~"
            login = "login ok" if destino["tem_login"] else "SEM LOGIN"
            onde = destino["identidade"] or "destino nao registrado"
            _linha(f"  {marca} {canal:<10} {destino['conta']:<16} "
                   f"-> {onde:<24} {login}")
            if destino["id"]:
                _linha(f"  {'':<11} {'':<16}    {destino['id']}")
    _linha("\n  ~ = caiu na queda padrao (o canal nao escolheu conta)")

    _linha("\n" + "=" * LARGURA)
    _linha("LOGINS SEM DESTINO (nao publicam; so entram em sites)")
    _linha("=" * LARGURA)
    for servico, ficha in contas.SERVICOS.items():
        if ficha.get("publica"):
            continue
        nomes = ", ".join(contas.contas(servico))
        _linha(f"  {ficha['rotulo']:<22} {nomes}")


def credenciais_vivas() -> list[dict]:
    """Pergunta ao Google se as credenciais OAuth ainda valem.

    `tem_login` so olha se o ARQUIVO existe com os campos certos — e isso
    mente. Em 08/09/2026 esta auditoria dizia "login ok" para uma credencial
    que o Google recusava com `invalid_grant`, e as metricas estavam paradas
    havia seis dias sem ninguem saber.
    """
    _linha("")
    _linha("=" * LARGURA)
    _linha("CREDENCIAIS OAUTH — perguntando ao Google (usa rede)")
    _linha("=" * LARGURA)
    mortas = []
    vistas = set()
    for canal in contas.CANAIS:
        conta = contas.ativa("youtube", canal)
        if conta in vistas:
            continue
        vistas.add(conta)
        estado = contas.oauth_vivo(canal, conta)
        marca = "ok " if estado["ok"] else "MORTA"
        _linha(f"  [{marca}] youtube/{conta}")
        if estado["motivo"]:
            _linha(f"          {estado['motivo']}")
        if not estado["ok"]:
            mortas.append({"servico": "youtube", "tipo": "credencial morta",
                           "detalhe": f"{conta}: {estado['motivo']}"})
    return mortas


def padrao(extras: list | None = None) -> int:
    _linha("\n" + "=" * LARGURA)
    _linha("PADRAO DE NOMES")
    _linha("=" * LARGURA)
    for regra in (
            "1. Um destino, um nome — o mesmo canal real tem o mesmo nome de "
            "conta em todos os servicos.",
            "2. O nome e o canal real, em slug (`neural_fights`, "
            "`historinhas`), nunca posicao nem arroba.",
            "3. `principal` e reservado ao login legado: ele mora nos caminhos "
            "antigos e nao pode ser renomeado sem perder as sessoes. Nao e "
            "destino — canal caindo nele significa 'nao configurado'.",
            "4. Todo canal que publica escolhe explicitamente."):
        _linha("  " + regra)

    fora = contas.conformidade() + list(extras or [])
    _linha("\n" + "=" * LARGURA)
    if not fora:
        _linha("TUDO DENTRO DO PADRAO")
        _linha("=" * LARGURA)
        return 0
    _linha(f"FORA DO PADRAO — {len(fora)} item(ns)")
    _linha("=" * LARGURA)
    for achado in fora:
        _linha(f"  [{achado['servico']:<11}] {achado['tipo']}")
        _linha(f"                {achado['detalhe']}")
    _linha("\n  Renomear leva o login junto:")
    _linha("     python -c \"from builds import contas; "
           "contas.renomear('<servico>', '<antigo>', '<novo>')\"")
    return 1


def main(argv=None) -> int:
    online = "--online" in (argv if argv is not None else sys.argv[1:])
    mapa()
    extras = credenciais_vivas() if online else []
    if not online:
        _linha("\n  (`--online` pergunta ao Google se as credenciais ainda "
               "valem — `tem_login` so ve o arquivo)")
    return padrao(extras)


if __name__ == "__main__":
    raise SystemExit(main())
