"""Entrada da esteira: cria a ficha e deixa o pedido no Correio."""
from __future__ import annotations

from ias import correio

from . import config, ficha, prompt


def marcar(item_id: str, estado: str) -> None:
    """Adaptador isolado para a marcacao visivel no app."""
    if not config.PAGINA:
        return              # perfil sem pagina de inventario no app (a Vila)
    from remoto import biblioteca
    biblioteca.marcar(config.PAGINA, item_id, estado)


# Quem gera o que (Adrian, 02/10/2026): o Gemini acerta a peca parada; o
# ChatGPT e melhor em folha de sprites (animacao e quadros).
def gerador_do(item: dict) -> str:
    return "chatgpt" if item.get("tipo") == "folha" else "gemini"


def pedir(item_id: str, defeitos: str = "", prompt_pronto: str = "") -> dict:
    """Pede a imagem. `prompt_pronto` e o prompt reescrito pelo juiz: vai como esta."""
    item = config.item(item_id)
    if item.get("externo"):
        # a mestra da Vila e a do Neural: quem pede e aprova e o perfil palco
        raise ValueError(f"{item_id} vem de fora deste perfil ({item['externo']}); nao se pede aqui")
    dados = ficha.ler(item_id) or ficha.nova(item)
    texto = prompt_pronto.strip() or prompt.montar(item, defeitos)
    caixa = gerador_do(item)
    mensagem = correio.pedir_imagem(caixa, texto, proporcao="1:1")
    tentativa = {"numero": len(dados.get("tentativas", [])) + 1,
                 "prompt": texto, "correio_id": mensagem["id"],
                 "caixa": caixa, "caminhos": {}, "medidas": None,
                 "veredito": None, "motivo": defeitos,
                 "prompt_do_juiz": bool(prompt_pronto.strip())}
    dados.setdefault("tentativas", []).append(tentativa)
    dados["estado"] = "pedido"
    ficha.registrar(dados, "pedido", correio_id=mensagem["id"], motivo=defeitos, caixa=caixa)
    ficha.gravar(dados)
    marcar(item_id, "esteira")
    return dados
