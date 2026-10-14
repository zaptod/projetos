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


# Quem gera (Adrian, 14/10/2026: "Agora que tudo ja esta mais limpo e organizado
# quero que voce volte a utilizar o ChatGPT para os sprites"): o ChatGPT gera
# TODOS os sprites, peca e folha, palco e Vila. Antes (02/10) a peca ia ao
# Gemini e o Gemini cobria o ChatGPT ocupado; isso acabou: com o ChatGPT
# ocupado, a ficha ESPERA na caixa dele (o carteiro entrega quando ele livrar).
GERADOR = "chatgpt"


def gerador_do(item: dict) -> str:
    return GERADOR


def pedir(item_id: str, defeitos: str = "", prompt_pronto: str = "") -> dict:
    """Pede a imagem. `prompt_pronto` e o prompt reescrito pelo juiz: vai como esta."""
    item = config.item(item_id)
    if item.get("externo"):
        # a mestra da Vila e a do Neural: quem pede e aprova e o perfil palco
        raise ValueError(f"{item_id} vem de fora deste perfil ({item['externo']}); nao se pede aqui")
    dados = ficha.ler(item_id) or ficha.nova(item)
    # o item vem SEMPRE do inventario de agora: a copia velha da ficha fez o juiz
    # e o portao julgarem o habitante bolinha como o boneco de pernas (02/10/2026)
    dados["item"] = item
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
