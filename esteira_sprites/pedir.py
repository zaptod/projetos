"""Entrada da esteira: cria a ficha e deixa o pedido no Correio."""
from __future__ import annotations

from ias import correio

from . import config, ficha, prompt


def marcar(item_id: str, estado: str) -> None:
    """Adaptador isolado para a marcacao visivel no app."""
    from remoto import biblioteca
    biblioteca.marcar(config.PAGINA, item_id, estado)


def pedir(item_id: str, defeitos: str = "") -> dict:
    item = config.item(item_id)
    dados = ficha.ler(item_id) or ficha.nova(item)
    texto = prompt.montar(item, defeitos)
    mensagem = correio.pedir_imagem("chatgpt", texto, proporcao="1:1")
    tentativa = {"numero": len(dados.get("tentativas", [])) + 1,
                 "prompt": texto, "correio_id": mensagem["id"],
                 "caixa": "chatgpt", "caminhos": {}, "medidas": None,
                 "veredito": None, "motivo": defeitos}
    dados.setdefault("tentativas", []).append(tentativa)
    dados["estado"] = "pedido"
    ficha.registrar(dados, "pedido", correio_id=mensagem["id"], motivo=defeitos)
    ficha.gravar(dados)
    marcar(item_id, "esteira")
    return dados
