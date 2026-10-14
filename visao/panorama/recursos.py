# -*- coding: utf-8 -*-
"""O que a producao CONSOME — e quanto ainda ha.

A quinta familia. As outras quatro respondem "o que esta acontecendo"; esta
responde "com o que". E a pergunta que nao estava em lugar nenhum, e por isso
cada falta dela virou um dia perdido, sempre do mesmo jeito: nada avisa, a
pipeline roda, e o resultado sai errado ou nao sai.

O que ja custou caro, cada um uma vez:

    disco           chegou a 0,33 GB livres e o render passou a morrer no
                    meio sem mensagem que dissesse "acabou o disco"
    credencial      o refresh_token do canal de historias venceu em 31/08 e
                    ficou onze dias morto; a publicacao continuou (ela vai
                    pelo navegador) e so a MEDICAO parou, sem uma linha de
                    erro em lugar nenhum
    conta travada   PicassoIA e conta compartilhada; com a trava presa, o
                    worker nao gera imagem e a historia trava na fila
                    esperando um dono que ja foi embora
    freio de mao    a pipeline pausada e uma pausa esquecida sao a mesma
                    coisa vista de fora: nada acontece

REGRA DESTE ARQUIVO, herdada do pacote: so LE, nao levanta, e e BARATO. O
painel le o `resumo()` a cada 4 s; um `schtasks` ou uma ida ao Google aqui
dentro viraria dezenas de subprocessos por minuto. O que custa caro mora em
`completo()`, que e chamado de proposito e com o proprio ritmo.
"""
from __future__ import annotations

import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# Abaixo disto o render comeca a falhar de formas que nao se parecem com
# falta de disco (ffmpeg morre no meio, JSON sai truncado). Medido em
# 10/09/2026, quando o disco chegou a 0,33 GB.
DISCO_CRITICO_GB = 2.0
DISCO_BAIXO_GB = 8.0

# As travas que, presas, param uma fabrica inteira.
TRAVAS_VITAIS = ("picasso", "instancia_unica", "historias_auto")


# Os configs que freiam a producao pelo disco, cada um com o volume dele.
_CONFIGS_DE_DISCO = (RAIZ / "historias" / "config" / "agenda.json",
                     RAIZ / "random_builds" / "config" / "geracao.json")
# "Baixo" = este tanto acima do freio do config.
FOLGA_DO_BAIXO_GB = 3.0
_ORDEM = {"ok": 0, "baixo": 1, "critico": 2}


def _volume(caminho) -> str:
    texto = str(caminho).replace("\\", "/")
    return (texto[:2].upper() + "/") if texto[1:2] == ":" else texto


def _volumes_a_vigiar() -> dict:
    """`{volume: (critico_gb, baixo_gb)}`: o do repositorio, com os limites de
    sempre, e o `disco_a_vigiar` de cada config, com o `disco_livre_minimo_gb`
    dele (SCR-P6, 14/10/2026)."""
    import json
    volumes = {_volume(RAIZ): (DISCO_CRITICO_GB, DISCO_BAIXO_GB)}
    for arquivo in _CONFIGS_DE_DISCO:
        try:
            config = json.loads(arquivo.read_text(encoding="utf-8-sig"))
            alvo = config.get("disco_a_vigiar")
            minimo = float(config.get("disco_livre_minimo_gb"))
        except (OSError, ValueError, TypeError):
            continue
        if not alvo:
            continue
        nome = _volume(alvo)
        critico, baixo = volumes.get(nome, (0.0, 0.0))
        volumes[nome] = (max(critico, minimo),
                         max(baixo, minimo + FOLGA_DO_BAIXO_GB))
    return volumes


def _disco(uso_de=None) -> dict:
    """O disco que PARA a producao, e nao so o do repositorio (SCR-P6).

    Ate 14/10/2026 media so o volume do repositorio (E:, 57 GB livres: "ok")
    enquanto o C: — o `disco_a_vigiar` dos dois configs, com freio de 5 GB —
    tinha 13 GB e caia. Agora mede cada volume vigiado com o limite dele; as
    chaves de cima (`livre_gb`, `situacao`, `volume`) sao as do PIOR volume,
    para as telas que ja liam assim, e `volumes` traz todos.
    """
    uso_de = uso_de or shutil.disk_usage
    volumes = {}
    for nome, (critico, baixo) in _volumes_a_vigiar().items():
        try:
            uso = uso_de(nome)
        except OSError as erro:
            volumes[nome] = {"erro": str(erro)}
            continue
        livre = uso.free / (1024 ** 3)
        volumes[nome] = {
            "livre_gb": round(livre, 2),
            "total_gb": round(uso.total / (1024 ** 3), 1),
            "critico_gb": critico,
            "situacao": ("critico" if livre < critico
                         else "baixo" if livre < baixo else "ok")}
    lidos = {n: v for n, v in volumes.items() if "erro" not in v}
    if not lidos:
        erros = "; ".join(f"{n}: {v['erro']}" for n, v in volumes.items())
        return {"erro": erros or "nenhum volume", "volumes": volumes}
    pior = max(lidos, key=lambda n: (_ORDEM[lidos[n]["situacao"]],
                                     -lidos[n]["livre_gb"]))
    saida = dict(lidos[pior], volume=pior, volumes=volumes)
    sem_leitura = [n for n in volumes if n not in lidos]
    if sem_leitura:
        saida["sem_leitura"] = sem_leitura
    return saida


def _travas() -> dict:
    """Quais perfis estao em uso AGORA.

    `travas.estado()` lista TODOS os perfis conhecidos com um campo
    `ocupada`, e nao so os seguradas — a primeira versao daqui mostrou os
    sete perfis como se todos estivessem presos. Quem responde a pergunta e
    o campo, nao o tamanho da lista.
    """
    try:
        from builds import travas
        linhas = travas.estado() or []
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}
    ocupadas = [{"servico": L.get("servico") or "?",
                 "canais": L.get("canais") or [],
                 "trava": L.get("trava") or ""}
                for L in linhas if isinstance(L, dict) and L.get("ocupada")]
    return {"ocupadas": ocupadas, "quantas": len(ocupadas),
            "conhecidas": len(linhas)}


def _freio() -> dict:
    """A pipeline esta pausada? Pausa esquecida e igual a producao parada."""
    try:
        from builds.identity import controle
        estado = controle.estado() or {}
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}
    pausas = estado.get("pausas") or {}
    return {"situacao": estado.get("situacao") or "",
            "pausado": bool(pausas),
            "alvos": sorted(pausas),
            "resumo": estado.get("resumo") or ""}


def _credenciais() -> dict:
    """Os ARQUIVOS de credencial existem e tem os campos?

    Leitura pura de proposito. `contas.oauth_vivo` pergunta ao Google e
    responde melhor — ele pega o refresh_token revogado, que este aqui nao
    pega —, mas usa rede, e rede nao entra no agregador. Quem faz a pergunta
    cara e o relatorio das 09:00 e `completo()` aqui embaixo.
    """
    try:
        from builds import contas
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}
    saida = {}
    for canal in ("builds", "historias"):
        ficha = {}
        for servico in ("youtube", "picasso", "tiktok"):
            try:
                ficha[servico] = bool(contas.tem_login(servico, canal))
            except Exception:                                  # noqa: BLE001
                ficha[servico] = None
        saida[canal] = ficha
    return saida


def leves() -> dict:
    """Os recursos baratos de ler. Entra no `resumo()` do pacote."""
    return {"disco": _disco(), "travas": _travas(), "freio": _freio(),
            "credenciais": _credenciais(), "alertas": []}


_PEDACOS = (("disco", "o disco"), ("travas", "as travas"),
            ("freio", "o freio da pipeline"),
            ("credenciais", "as credenciais"))


def _sem_verificar(dados: dict, pedacos) -> list:
    """Um alerta por pedaco que NAO foi lido.

    Ate 11/10/2026 o `erro` de cada pedaco ficava so no dicionario: nenhum
    alerta, e o veredito — que so le os alertas daqui — dizia "tudo em dia"
    sem ter olhado o disco ou o freio. Nao conseguir verificar e problema.
    """
    alertas = []
    for chave, nome in pedacos:
        pedaco = dados.get(chave)
        if isinstance(pedaco, dict) and pedaco.get("erro"):
            alertas.append(f"nao consegui verificar {nome}: {pedaco['erro']}")
    return alertas


def situacao() -> dict:
    """`leves()` com os alertas ja resolvidos em frases."""
    dados = leves()
    alertas = _sem_verificar(dados, _PEDACOS)

    disco = dados.get("disco") or {}
    for nome, volume in sorted((disco.get("volumes") or {}).items()):
        if volume.get("situacao") == "critico":
            # "critico" na frase: e o que o veredito le como grave
            alertas.append(f"disco {nome} critico: {volume.get('livre_gb')} GB "
                           f"livres (freio em {volume.get('critico_gb')} GB) — "
                           "a producao para e o render morre no meio")
        elif volume.get("situacao") == "baixo":
            alertas.append(f"disco {nome} em {volume.get('livre_gb')} GB livres")
    for nome in disco.get("sem_leitura") or []:
        alertas.append(f"nao consegui verificar o disco {nome}")

    freio = dados.get("freio") or {}
    if freio.get("pausado"):
        alertas.append("a pipeline esta PAUSADA ("
                       + ", ".join(freio.get("alvos") or []) + ")")

    for canal, ficha in (dados.get("credenciais") or {}).items():
        if isinstance(ficha, dict):
            faltando = [s for s, ok in ficha.items() if ok is False]
            if faltando:
                alertas.append(f"{canal}: sem login de "
                               + ", ".join(sorted(faltando)))
            # `None` e "a pergunta estourou", nao "tem login".
            sem_resposta = [s for s, ok in ficha.items() if ok is None]
            if sem_resposta:
                alertas.append(f"{canal}: nao consegui verificar o login de "
                               + ", ".join(sorted(sem_resposta)))

    ocupadas = (dados.get("travas") or {}).get("ocupadas") or []
    if ocupadas:
        # Nao e alerta de ERRO: trava ocupada e o estado normal de quem esta
        # trabalhando. E informacao de por que a outra fabrica esta esperando.
        dados["em_uso"] = sorted({t["servico"] for t in ocupadas})

    dados["alertas"] = alertas
    return dados


def completo() -> dict:
    """`situacao()` mais o que custa caro: Agendador e OAuth de verdade.

    Fora do `resumo()` de proposito — cada uma destas respostas custa um
    subprocesso ou uma ida a rede, e o painel le o resumo a cada 4 s.
    """
    dados = situacao()
    dados["agendador"] = _agendador()
    dados["oauth"] = _oauth_vivo()
    dados["alertas"].extend(_sem_verificar(
        dados, (("oauth", "o OAuth das contas"),
                ("agendador", "as tarefas do Agendador"))))
    for canal, ficha in (dados["oauth"] or {}).items():
        if isinstance(ficha, dict) and not ficha.get("ok"):
            dados["alertas"].append(f"{canal}: {ficha.get('motivo')}")
    agendador = dados["agendador"] or {}
    faltando = agendador.get("faltando") or []
    fracas = agendador.get("fracas") or []
    sem_leitura = agendador.get("sem_leitura") or []
    if sem_leitura and len(sem_leitura) >= agendador.get("total", 0):
        dados["alertas"].append(
            f"o Agendador do Windows nao respondeu: nao consegui verificar "
            f"nenhuma das {len(sem_leitura)} tarefa(s) "
            f"({agendador.get('motivo_sem_leitura') or '?'})")
    elif sem_leitura:
        dados["alertas"].append(
            f"nao consegui verificar {len(sem_leitura)} tarefa(s) do "
            "Windows: " + ", ".join(sem_leitura[:3]))
    if faltando:
        dados["alertas"].append(f"{len(faltando)} tarefa(s) do Windows nao "
                                "existem: " + ", ".join(faltando[:3]))
    if fracas:
        dados["alertas"].append(f"{len(fracas)} tarefa(s) desligadas, ligadas "
                                "sem dever, ou que somem na bateria: "
                                + ", ".join(fracas[:3]))
    return dados


def _horas_de_criacao() -> list:
    """Os disparos da criacao, lidos do config da agenda.

    Desde 13/09/2026 eles sao de madrugada. A lista fixa com os oito horarios
    do dia acusaria oito tarefas sumidas e deixaria as sete reais sem
    conferencia nenhuma.
    """
    try:
        from contos.pipeline import agenda
        return list(agenda.carregar()["horas"])
    except Exception:                                          # noqa: BLE001
        return []


def _tarefas_de_geracao() -> list:
    """As `NeuralFights_gerar_HH` (duelos de madrugada), lidas do config dela.

    Criadas em 27/09/2026 (01:02 a 05:02). Ate 28/09 esta lista nao as
    conferia: se o Agendador as perdesse, a geracao de duelos pararia e
    nenhuma tela diria — foi exatamente assim que o builds ficou sem estoque
    de 22 a 26/09. Geracao desligada (`ativo: false`) nao cobra tarefa.
    """
    try:
        from builds.pipeline import noite, tarefas_noite
        config = noite.carregar()
    except Exception:                                          # noqa: BLE001
        return []
    if not config.get("ativo", True):
        return []
    return [tarefas_noite.nome_da_tarefa(h) for h in config.get("horas") or ()]


# Desde b1ef6f7 (13/10/2026, decisao `geral/gerente-unico-dos-servicos`) bot,
# app e Vila sao do coordenador, e as tarefas antigas deles ficam DESLIGADAS
# de proposito: religadas, abririam um segundo bot/app.
DESLIGADAS_DE_PROPOSITO = ("NeuralFights_app_celular", "NeuralFights_bot_telegram",
                           "NeuralFights_vila_flutuante")


def tarefas_esperadas(ilegiveis: list | None = None) -> dict:
    """`{nome: "ligada"|"desligada"}` — a lista UNICA das tarefas (SCR-P10).

    O panorama e o relatorio do bot (`remoto.relatorios._linhas_do_agendador`)
    tinham listas diferentes, nenhuma com o coordenador, e as duas cobravam o
    bot como tarefa ligada depois de ele passar ao coordenador.

    LISTA QUE NAO SE LE NAO SOME EM SILENCIO: o config que nao abriu vai para
    `ilegiveis` ("da criação das histórias", "da geração noturna").
    """
    from builds import grade
    ilegiveis = ilegiveis if ilegiveis is not None else []
    horas = _horas_de_criacao()
    if not horas:
        try:
            from contos.pipeline import agenda
            agenda.carregar()["horas"]
        except Exception:                                      # noqa: BLE001
            ilegiveis.append("da criação das histórias")
    try:
        from builds.pipeline import noite
        noite.carregar()
    except Exception:                                          # noqa: BLE001
        ilegiveis.append("da geração noturna")
    saida = {f"Historias_auto_{h:02d}": "ligada" for h in horas}
    saida.update({nome: "ligada" for nome in _tarefas_de_geracao()})
    saida.update({f"NeuralFights_postar_{h:02d}": "ligada" for h in grade.HORAS})
    saida["NeuralFights_coordenador"] = "ligada"
    saida.update({nome: "desligada" for nome in DESLIGADAS_DE_PROPOSITO})
    return saida


def _agendador() -> dict:
    try:
        from builds import tarefas_windows
        esperadas = tarefas_esperadas()
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}
    # Ate 11/10/2026 a tarefa que nao deu para ler era `continue`: com o
    # Agendador fora, saiam "34 tarefas, nada faltando, nada fraco". Agora
    # ela vai para `sem_leitura` (em `tarefas_windows.julgar`).
    return tarefas_windows.julgar(esperadas)


def _oauth_vivo() -> dict:
    try:
        from builds import contas
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}
    saida = {}
    for canal in ("builds", "historias"):
        try:
            saida[canal] = contas.oauth_vivo(canal)
        except Exception as erro:                              # noqa: BLE001
            saida[canal] = {"ok": False,
                            "motivo": f"nao deu para conferir ({erro})"}
    return saida


__all__ = ["leves", "situacao", "completo", "DISCO_CRITICO_GB",
           "DISCO_BAIXO_GB"]
