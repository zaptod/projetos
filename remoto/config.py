# -*- coding: utf-8 -*-
"""Onde mora o segredo do bot, e quem tem permissao de falar com ele.

O token do Telegram e uma CHAVE: quem o tem controla o bot, e o bot controla
uma maquina com YouTube, TikTok, ChatGPT e PicassoIA logados. Por isso ele
nunca entra no repositorio — fica em `%LOCALAPPDATA%/neural-fights/`, junto
das outras credenciais, e este modulo e o unico lugar que o le.

A lista branca (`autorizados`) e a segunda tranca: o Telegram deixa qualquer
pessoa mandar mensagem para um bot se souber o nome dele. Sem a lista, um
desconhecido poderia pausar a fila ou publicar um video. Quem nao esta na
lista recebe uma recusa curta e nada mais — nem a lista de comandos, que ja
seria informacao sobre a maquina.

Emparelhar: `python -m remoto` imprime um codigo de 6 digitos no console; a
primeira pessoa que mandar `/parear <codigo>` entra na lista. O codigo vale
uma vez e expira junto com o processo, entao ele nao precisa ser guardado.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def runtime_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "neural-fights"


ARQUIVO = None          # os testes apontam para outro lugar


def caminho() -> Path:
    return Path(ARQUIVO) if ARQUIVO else runtime_dir() / "remoto.json"


PADRAO = {
    "token": "",
    "autorizados": [],      # chat_ids que podem mandar comando
    "alertas": True,        # empurrar erro do diario sem ser perguntado
    "intervalo_alerta_s": 20,
    # Erro novo abre uma sessao do Claude que LE os arquivos e diz o que houve.
    "apurar": True,
    # ... e, com isto, ela tambem MEXE no codigo. Pedido dele em 08/09/2026.
    # O conserto so sobrevive se a suite inteira passar; reprovou, e desfeito.
    # Desligue aqui se um dia quiser so o diagnostico.
    "consertar": True,
    # Os dois relatorios periodicos (pedido de 09/09/2026), e a hora local de
    # cada um. Hora vazia ou invalida = aquele relatorio nao sai sozinho (o
    # comando continua funcionando).
    #
    # `metas` as 21:00: depois da postagem das 17:07 E depois do ultimo
    # disparo de geracao (20:00), entao o dia ja esta fechado quando ele fala.
    # `funcionamento` as 09:00: e o relatorio da NOITE — o que rodou enquanto
    # ninguem olhava e o que quebrou. De manha ainda da tempo de consertar
    # antes da postagem da tarde.
    "relatorios": {"metas": "21:00", "funcionamento": "09:00"},
}


def carregar() -> dict:
    dados = {}
    alvo = caminho()
    if alvo.is_file():
        try:
            with open(alvo, encoding="utf-8-sig") as fh:
                dados = json.load(fh)
        except (OSError, ValueError):
            dados = {}
    config = dict(PADRAO)
    config.update(dados if isinstance(dados, dict) else {})
    config["autorizados"] = [int(c) for c in (config.get("autorizados") or [])]
    return config


def salvar(config: dict) -> Path:
    alvo = caminho()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    limpo = {k: config.get(k, v) for k, v in PADRAO.items()}
    alvo.write_text(json.dumps(limpo, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return alvo


def token() -> str:
    """O token, do arquivo ou da variavel de ambiente (nesta ordem)."""
    return (carregar().get("token")
            or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()


def autorizado(chat_id) -> bool:
    return int(chat_id) in carregar()["autorizados"]


def autorizar(chat_id) -> dict:
    config = carregar()
    if int(chat_id) not in config["autorizados"]:
        config["autorizados"].append(int(chat_id))
        salvar(config)
    return config


def esquecer(chat_id) -> dict:
    config = carregar()
    config["autorizados"] = [c for c in config["autorizados"]
                             if c != int(chat_id)]
    salvar(config)
    return config
