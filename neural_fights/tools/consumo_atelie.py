"""Registro honesto de onde cada peca salva no Atelie e desenhada.

Uma entrada so entra em ``PECAS_VILA_COM_PROVA`` quando a prova salva uma
folha de cor unica e o consumidor real devolve essa cor.
"""
from __future__ import annotations


PECAS_VILA_COM_PROVA = frozenset({
    *("vila.habitantes." + nome for nome in ("arena", "bot", "chatgpt",
      "deepseek", "digen", "estudio", "gemini", "grok", "picasso",
      "tiktok", "youtube")),
    *("vila.predios." + nome for nome in ("arena", "arena_noite", "bot",
      "bot_noite", "casa", "casa_noite", "chatgpt", "chatgpt_noite",
      "deepseek", "deepseek_noite", "digen", "digen_noite", "estudio",
      "estudio_noite", "gemini", "gemini_noite", "grok", "grok_noite",
      "picasso", "picasso_noite", "tiktok", "tiktok_noite", "youtube",
      "youtube_noite")),
    "vila.cenario.arvore", "vila.cenario.banco",
    "vila.cenario.caminho_terra", "vila.cenario.canteiro",
    "vila.cenario.chao_grama", "vila.cenario.fonte", "vila.cenario.lago",
    "vila.cenario.lago_brilho", "vila.cenario.lua", "vila.cenario.moita",
    "vila.cenario.morro", "vila.cenario.nuvem", "vila.cenario.placa",
    "vila.bichos.gato", "vila.bichos.passaro", "vila.bichos.pato",
    "vila.bichos.vagalume",
    *("vila.interface." + nome for nome in ("arco", "balao", "bandeirolas",
      "estatua", "gnomo", "lanterna", "balao_emote", "confete")),
    *("vila.objetos." + nome for nome in ("agora", "decidir", "mandar", "ver")),
})
VILA = "Vila (PC e celular)"


def consumidores(peca: str, grupo: str = "") -> list[dict[str, str]]:
    """Devolve apenas consumidores cobertos pela prova automatica."""
    if peca in PECAS_VILA_COM_PROVA:
        if peca.startswith("vila.objetos."):
            return [{"onde": "App (prateleira)",
                     "funcao": "remoto.api_http._icone_do_objeto_do_atelie"}]
        if peca.startswith("vila.habitantes."):
            funcao = "painel.flutuante.arte.desenhar_personagem / remoto.vila_nova.atlas"
        elif peca.startswith("vila.predios."):
            funcao = "painel.flutuante.arte.desenhar_predio"
        elif peca.startswith("vila.bichos."):
            nome = peca.rsplit(".", 1)[-1]
            funcao = "painel.flutuante.arte.desenhar_" + nome
        elif peca.startswith("vila.interface."):
            nome = peca.rsplit(".", 1)[-1]
            funcao = ("painel.flutuante.arte.emote" if nome == "balao_emote"
                      else "painel.flutuante.arte.desenhar_confete" if nome == "confete"
                      else "painel.flutuante.arte.desenhar_decoracao")
        elif peca in {"vila.cenario.chao_grama", "vila.cenario.caminho_terra"}:
            funcao = "painel.flutuante.arte.desenhar_chao"
        else:
            nome = peca.rsplit(".", 1)[-1]
            funcao = "painel.flutuante.arte.desenhar_" + nome
        onde = "Vila (PC)" if peca in {"vila.interface.balao_emote",
                                        "vila.interface.confete"} else VILA
        return [{"onde": onde, "funcao": funcao}]
    if grupo in {"lutador", "arma"}:
        return [{"onde": "Luta no Godot e previa do launcher",
                 "funcao": "palco/nucleo/biblioteca.gd:_cena_catalogo"}]
    return []


def motivo_sem_consumidor(peca: str, grupo: str = "") -> str:
    if grupo in {"skill", "efeito", "elemento", "estado_personagem", "buff"}:
        return "aguarda ligacao dos gatilhos do Godot"
    return "a Vila ainda nao consulta esta peca"


def aparece_em(peca: str, grupo: str = "") -> list[str]:
    return [item["onde"] for item in consumidores(peca, grupo)]


def sem_consumidor(pecas: list[dict]) -> list[str]:
    return [str(p.get("id", "")) for p in pecas
            if not consumidores(str(p.get("id", "")), str(p.get("grupo", "")))]
