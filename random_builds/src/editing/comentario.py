"""O print do comentario que pediu o nome.

Um arquivo, um lugar: `comentario.<ext>` na pasta da geracao. Nao ha
catalogo nem id sequencial de proposito — ao contrario das reacoes, que sao
uma biblioteca reaproveitada entre videos, este print pertence a UMA geracao
e nunca a outra.

Guardar copia para dentro da pasta em vez de apontar para o original: o
print costuma nascer na area de trabalho ou em Downloads, e um re-render
meses depois nao pode depender de um arquivo que o dono ja apagou.

Quem monta o video le por `encontrar`; quem recebe o arquivo do usuario
(CLI, painel) chama `guardar`. As duas pontas usam o mesmo nome canonico
daqui — escrito em dois lugares, divergiriam no dia em que um deles mudasse.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from ..identity import artefato as identity_artefato
from ..identity import slots as identity_slots

NOME = "comentario"
EXTENSOES = identity_slots.EXTENSOES_IMAGEM


def encontrar(out_dir: Path | None) -> Path | None:
    """O print da geracao, ou None. So devolve imagem que presta."""
    if out_dir is None:
        return None
    for extensao in EXTENSOES:
        caminho = Path(out_dir) / f"{NOME}{extensao}"
        if caminho.is_file() and identity_artefato.presta(caminho):
            return caminho
    return None


def guardar(out_dir: Path, origem: str | Path | None) -> Path | None:
    """Copia o print para a pasta da geracao. Devolve o destino, ou None.

    Levanta `ValueError` quando o arquivo nao existe ou nao e imagem: um
    pedido com print errado tem que falhar ALTO, e nao render um video sem a
    prova e deixar o dono descobrir na hora de publicar.
    """
    if not origem:
        return None
    fonte = Path(origem).expanduser()
    if not fonte.is_file():
        raise ValueError(f"print do comentario nao encontrado: {fonte}")
    extensao = fonte.suffix.lower()
    if extensao not in EXTENSOES:
        raise ValueError(
            f"print do comentario precisa ser imagem {'/'.join(EXTENSOES)}: {fonte.name}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Troca de formato nao pode deixar os dois para tras: `encontrar` pegaria
    # o antigo, que vem primeiro na lista de extensoes.
    for antigo in EXTENSOES:
        anterior = out_dir / f"{NOME}{antigo}"
        if anterior.is_file():
            anterior.unlink()
    destino = out_dir / f"{NOME}{extensao}"
    shutil.copy2(fonte, destino)
    if not identity_artefato.presta(destino):
        destino.unlink(missing_ok=True)
        raise ValueError(f"print do comentario nao e uma imagem valida: {fonte.name}")
    return destino
