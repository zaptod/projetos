# -*- coding: utf-8 -*-
"""O catalogo de controles do app: o que da para mandar fazer do celular.

Pedido do Adrian (27/09/2026): "todos os controles possiveis para eu poder
controlar e gerir tudo de qualquer lugar".

COMO FUNCIONA. Cada controle e uma FICHA declarativa (nome, grupo, rotulo,
campos, se pede confirmacao, se e perigoso). O app baixa o catalogo e monta
a tela sozinho — nao ha uma segunda lista de botoes no JavaScript para
divergir desta. A execucao e sempre a mesma: valida os campos, roda as
guardas, monta a linha de comando e sobe uma TAREFA (processo desligado do
servidor, saida em arquivo), que o celular acompanha pelo log.

O QUE NAO ENTRA, e por que:
  - logins e OAuth: abrem navegador e esperam uma pessoa na frente;
  - a Oficina de sprites, as janelas do painel e o jogo: sao interface;
  - `os.startfile`: abrir pasta no PC nao serve para quem esta na rua (o
    app ja toca o mp4 por streaming).

TRES TRANCAS, alem das que o `acoes.py` ja impunha:
  1. NIVEL: `--acoes` liga os grupos comuns; os PERIGOSOS (apagar midia,
     regenerar banco, esquecer conta, trocar a conta de destino) exigem
     tambem `--perigosas` no servidor.
  2. DIGITAR: os perigosos so executam se o pedido vier com o nome do alvo
     digitado igual — um toque errado no bolso nao apaga nada.
  3. UMA DE CADA: acao que usa conta compartilhada ou o mesmo perfil de
     Chrome recusa se ja houver tarefa igual rodando, ou se o perfil
     estiver ocupado.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RANDOM_BUILDS = RAIZ / "random_builds"
HISTORIAS = RAIZ / "historias"
FERRAMENTAS = RAIZ / "ferramentas"

GRUPOS = {
    "producao": "Produção",
    "criacao": "Criação",
    "publicacao": "Publicação",
    "manutencao": "Manutenção",
    "perigo": "Zona de perigo",
}
# Contam no teto por hora junto com gerar/publicar: sao as que gastam conta
# compartilhada, tempo de maquina ou cota.
PESADAS = ("rerender", "identity_run", "identity_worker", "refazer_imagens",
           "trilha", "metricas", "gerar_historia", "historia_tudo",
           "historia_video", "duelo", "publicar_historia", "escoar",
           "recuperar", "apagar_midia", "regenerar_banco")


def _campo(nome, rotulo, tipo="texto", **extra):
    return dict(nome=nome, rotulo=rotulo, tipo=tipo, **extra)


CATALOGO = [
    # ------------------------------------------------------- producao
    {"nome": "rerender", "grupo": "producao", "rotulo": "Re-renderizar build",
     "descricao": "Refaz o vídeo de uma geração que já existe.",
     "campos": [_campo("geracao", "Geração", "build")],
     "dois_passos": True},
    {"nome": "identity_run", "grupo": "producao",
     "rotulo": "Enfileirar identidade",
     "descricao": "Põe os clipes de identidade dessa geração na fila e processa.",
     "campos": [_campo("geracao", "Geração", "build")],
     "dois_passos": True, "perfis": ("digen", "picasso")},
    {"nome": "identity_worker", "grupo": "producao",
     "rotulo": "Processar fila de identidade",
     "descricao": "Uma passada do worker (PicassoIA e Digen).",
     "campos": [], "dois_passos": True, "perfis": ("digen", "picasso")},
    {"nome": "refazer_imagens", "grupo": "producao",
     "rotulo": "Refazer imagens da história",
     "descricao": "Gera no PicassoIA as imagens que faltam.",
     "campos": [_campo("historia", "História", "historia")],
     "dois_passos": True, "perfis": ("picasso",)},
    {"nome": "trilha", "grupo": "producao", "rotulo": "Gerar trilha",
     "descricao": "Sintetiza a trilha sonora dos vídeos.",
     "campos": [], "dois_passos": False},
    {"nome": "metricas", "grupo": "producao", "rotulo": "Atualizar métricas",
     "descricao": "Busca retenção e números no YouTube (gasta cota da API).",
     "campos": [], "dois_passos": True},
    # -------------------------------------------------------- criacao
    {"nome": "gerar_historia", "grupo": "criacao", "rotulo": "Gerar história",
     "descricao": "Abre o LLM e escreve uma série nova. Leva minutos.",
     "campos": [_campo("provedor", "Com qual IA", "escolha",
                       opcoes=["deepseek", "chatgpt", "gemini"]),
                _campo("partes", "Partes", "numero", minimo=1, maximo=8,
                       padrao=6),
                _campo("cenas", "Cenas por parte", "numero", minimo=3,
                       maximo=20, padrao=14),
                _campo("tema", "Tema (opcional)", "texto", obrigatorio=False)],
     "dois_passos": True, "perfis": ("chatgpt", "gemini", "deepseek")},
    {"nome": "historia_tudo", "grupo": "criacao",
     "rotulo": "Terminar história (imagens + vídeo)",
     "descricao": "Gera o que falta de imagens e monta os vídeos.",
     "campos": [_campo("historia", "História", "historia")],
     "dois_passos": True, "perfis": ("picasso",)},
    {"nome": "historia_video", "grupo": "criacao",
     "rotulo": "Montar vídeo da história",
     "descricao": "Narração, legenda e mp4 (não gera imagem).",
     "campos": [_campo("historia", "História", "historia")],
     "dois_passos": True},
    {"nome": "duelo", "grupo": "criacao", "rotulo": "Gravar duelo",
     "descricao": "Uma luta curta, com vídeo, para repor estoque.",
     "campos": [_campo("p1", "Lutador 1 (opcional)", "texto",
                       obrigatorio=False),
                _campo("p2", "Lutador 2 (opcional)", "texto",
                       obrigatorio=False)],
     "dois_passos": True},
    # ----------------------------------------------------- publicacao
    {"nome": "publicar_historia", "grupo": "publicacao",
     "rotulo": "Publicar história",
     "descricao": "Publica a próxima parte, ou a série inteira agendada.",
     "campos": [_campo("historia", "História", "historia"),
                _campo("onde", "Onde", "escolha",
                       opcoes=["youtube", "tiktok", "ambos"]),
                _campo("serie", "A série inteira (agendada)", "bool")],
     "dois_passos": True, "grade": True, "perfis": ("youtube_web", "tiktok")},
    {"nome": "escoar", "grupo": "publicacao", "rotulo": "Escoar a fila",
     "descricao": "Publica vários de uma vez, ignorando o um-por-horário.",
     "campos": [_campo("limite", "Quantos", "numero", minimo=1, maximo=6,
                       padrao=2),
                _campo("canal", "Canal", "escolha",
                       opcoes=["builds", "historias"])],
     "dois_passos": True, "grade": True, "perfis": ("youtube_web", "tiktok")},
    {"nome": "recuperar", "grupo": "publicacao",
     "rotulo": "Recuperar vídeo privado",
     "descricao": "Devolve ao ar o que ficou privado ou sem confirmação.",
     "campos": [], "dois_passos": True, "grade": True,
     "perfis": ("youtube_web",)},
    # ----------------------------------------------------- manutencao
    {"nome": "ver_postagem", "grupo": "manutencao",
     "rotulo": "O que sai no próximo horário",
     "descricao": "Só olha: diz o que a grade publicaria agora.",
     "campos": [], "dois_passos": False},
    {"nome": "curar_ledger", "grupo": "manutencao", "rotulo": "Curar o ledger",
     "descricao": "A seco por padrão: mostra o que mudaria.",
     "campos": [_campo("canal", "Canal", "escolha",
                       opcoes=["builds", "historias"]),
                _campo("gravar", "Gravar de verdade", "bool")],
     "dois_passos": True, "perigo_se": "gravar"},
    {"nome": "conciliar_tiktok", "grupo": "manutencao",
     "rotulo": "Conciliar o TikTok",
     "descricao": "Importa para o ledger o que já está no perfil.",
     "campos": [_campo("gravar", "Gravar de verdade", "bool")],
     "dois_passos": True, "perigo_se": "gravar"},
    {"nome": "liberar", "grupo": "manutencao",
     "rotulo": "Liberar vídeo travado",
     "descricao": "Tira do “em voo” do app, depois de conferir no perfil.",
     "campos": [_campo("id", "Id do vídeo", "texto")],
     "dois_passos": True},
    {"nome": "soltar_marca", "grupo": "manutencao",
     "rotulo": "Soltar marca “a conferir”",
     "descricao": "Tira a marca que o app pôs, depois da conferência.",
     "campos": [_campo("id", "Id do vídeo", "texto")],
     "dois_passos": True},
    # --------------------------------------------------------- perigo
    {"nome": "apagar_midia", "grupo": "perigo",
     "rotulo": "Apagar vídeos baixados do Espelho",
     "descricao": "Apaga os mp4 baixados de um canal estudado.",
     "campos": [_campo("canal", "Id do canal", "texto")],
     "dois_passos": True, "perigo": True},
    {"nome": "regenerar_banco", "grupo": "perigo",
     "rotulo": "Regenerar o banco do jogo",
     "descricao": "Apaga e refaz a database inteira de personagens.",
     "campos": [], "dois_passos": True, "perigo": True},
    {"nome": "esquecer_conta", "grupo": "perigo", "rotulo": "Esquecer conta",
     "descricao": "Tira a conta do registro (o login em disco fica).",
     "campos": [_campo("servico", "Serviço", "texto"),
                _campo("conta", "Conta", "texto")],
     "dois_passos": True, "perigo": True},
    {"nome": "escolher_conta", "grupo": "perigo",
     "rotulo": "Trocar a conta de destino",
     "descricao": "Muda para onde as próximas publicações vão.",
     "campos": [_campo("servico", "Serviço", "texto"),
                _campo("canal", "Canal", "escolha",
                       opcoes=["builds", "historias"]),
                _campo("conta", "Conta", "texto")],
     "dois_passos": True, "perigo": True},
]

FICHAS = {ficha["nome"]: ficha for ficha in CATALOGO}


def catalogo(com_perigosas: bool) -> dict:
    """O que o app mostra. Sem `--perigosas`, a zona de perigo nem aparece."""
    fichas = [f for f in CATALOGO
              if com_perigosas or f["grupo"] != "perigo"]
    return {"grupos": [{"nome": g, "rotulo": GRUPOS[g]} for g in GRUPOS
                       if com_perigosas or g != "perigo"],
            "acoes": [{k: v for k, v in f.items()
                       if k in ("nome", "grupo", "rotulo", "descricao",
                                "campos", "dois_passos", "perigo",
                                "perigo_se")}
                      for f in fichas]}


# ------------------------------------------------------------- validacao
_TEXTO_OK = re.compile(r"^[\w .,:!?/@#-]{1,80}$", re.UNICODE)


def _erro(mensagem: str):
    from .acoes import Recusa
    return Recusa(mensagem)


def _validar_campo(campo: dict, bruto):
    tipo = campo["tipo"]
    rotulo = campo["rotulo"]
    obrigatorio = campo.get("obrigatorio", True)
    if bruto in (None, "", []) and tipo != "bool":
        if obrigatorio:
            raise _erro(f"falta preencher: {rotulo}")
        return None
    if tipo == "bool":
        return bool(bruto)
    if tipo == "numero":
        try:
            valor = int(bruto)
        except (TypeError, ValueError):
            raise _erro(f"{rotulo}: número inválido") from None
        if not campo.get("minimo", 0) <= valor <= campo.get("maximo", 10 ** 6):
            raise _erro(f"{rotulo}: fora do limite "
                        f"({campo.get('minimo')}–{campo.get('maximo')})")
        return valor
    if tipo == "escolha":
        if str(bruto) not in campo["opcoes"]:
            raise _erro(f"{rotulo}: escolha inválida")
        return str(bruto)
    if tipo in ("build", "historia"):
        return _validar_id(tipo, str(bruto))
    texto = str(bruto).strip()
    if not _TEXTO_OK.match(texto):
        raise _erro(f"{rotulo}: use só letras, números e pontuação simples")
    return texto


def _validar_id(tipo: str, bruto: str) -> str:
    """O id tem que EXISTIR. O app manda o que o catalogo dele mostrou."""
    from .acoes import id_base, mesmo_video
    alvo = id_base(bruto.strip())
    if tipo == "build":
        from builds.publicar import catalogo as cat
        try:
            ids = {id_base(v.id) for v in cat.listar()}
        except Exception as exc:                             # noqa: BLE001
            raise _erro("não consegui ler o catálogo de builds") from exc
        # a geracao e o pedaco antes do primeiro ":" (generation_00041)
        geracoes = {i.split(":")[0] for i in ids}
        if alvo.split(":")[0] not in geracoes:
            raise _erro(f"não achei a geração {alvo}")
        return alvo.split(":")[0]
    from contos.publicar import catalogo as cat
    try:
        historias = {str(v.fonte_id or v.id).split(":")[0] for v in cat.listar()}
    except Exception as exc:                                 # noqa: BLE001
        raise _erro("não consegui ler o catálogo de histórias") from exc
    alvo = alvo.split(":")[0]
    if alvo not in historias:
        raise _erro(f"não achei a história {alvo}")
    assert mesmo_video(alvo, alvo)
    return alvo


def validar(nome: str, args: dict) -> dict:
    ficha = FICHAS.get(nome)
    if ficha is None:
        raise _erro(f"ação desconhecida: {nome}")
    limpos = {}
    for campo in ficha["campos"]:
        limpos[campo["nome"]] = _validar_campo(campo, args.get(campo["nome"]))
    if e_perigosa(nome, limpos):
        digitado = str(args.get("confirmo") or "").strip()
        alvo = alvo_do_perigo(nome, limpos)
        if digitado != alvo:
            raise _erro(f"para confirmar, digite exatamente: {alvo}")
        limpos["confirmo"] = alvo
    return limpos


def e_perigosa(nome: str, args: dict) -> bool:
    ficha = FICHAS.get(nome) or {}
    if ficha.get("perigo"):
        return True
    gatilho = ficha.get("perigo_se")
    return bool(gatilho and args.get(gatilho))


def alvo_do_perigo(nome: str, args: dict) -> str:
    """O que a pessoa tem que digitar para confirmar."""
    if nome == "apagar_midia":
        return str(args.get("canal") or "")
    if nome == "regenerar_banco":
        return "regenerar banco"
    if nome in ("esquecer_conta", "escolher_conta"):
        return f"{args.get('servico')}/{args.get('conta')}"
    if nome == "curar_ledger":
        return f"curar {args.get('canal')}"
    if nome == "conciliar_tiktok":
        return "conciliar tiktok"
    return nome


# ---------------------------------------------------------------- guardas
def guardar(nome: str, args: dict) -> None:
    """Recusa quando o momento nao e bom. Tudo que nao da para ler RECUSA."""
    from . import acoes, tarefas
    ficha = FICHAS[nome]

    iguais = tarefas.rodando(nome)
    if iguais:
        raise _erro(f"já tem “{ficha['rotulo']}” rodando "
                    f"(desde {iguais[0]['inicio'][11:16]})")
    for destino in ficha.get("perfis", ()):
        ocupado = acoes.perfil_ocupado(destino) if destino in ("youtube_web", "tiktok") \
            else acoes.trava_ocupada(_trava_do_provedor(destino))
        if ocupado is None:
            raise _erro(f"não consegui conferir se {destino} está livre")
        if ocupado:
            raise _erro(f"{destino} está em uso agora; tente depois")
    if ficha.get("grade"):
        perto = acoes.postagem_em_curso(onde="ambos")
        if perto:
            raise _erro(f"a postagem das {perto} está perto demais; "
                        "tente de novo depois")
        vivos = acoes.processos()
        rodando = acoes.postando(vivos)
        if rodando is None:
            raise _erro("não consegui conferir se a postagem está rodando")
        if rodando:
            raise _erro("a postagem da grade está rodando agora")
    if nome in ("identity_worker", "identity_run", "refazer_imagens",
                "historia_tudo", "gerar_historia"):
        pausa = _pausa()
        if pausa:
            raise _erro(f"a produção está {pausa}; retome antes")


def _trava_do_provedor(provedor: str) -> str:
    from builds import travas
    try:
        return travas.do_perfil(provedor, "builds")
    except Exception:                                        # noqa: BLE001
        return provedor


def _pausa() -> str:
    from builds.identity import controle
    try:
        estado = controle.estado()
    except Exception:                                        # noqa: BLE001
        return ""
    return "" if estado.get("situacao") == "rodando" else estado.get("resumo", "")


# ---------------------------------------------------------------- comando
def montar(nome: str, args: dict) -> tuple:
    """(rotulo, comando, cwd) — a linha que a tarefa vai rodar."""
    from .comandos import PY
    py = [PY, "-X", "utf8"]
    if nome == "rerender":
        return (f"re-renderizar {args['geracao']}",
                py + ["main.py", "generate-video", "--rerender", args["geracao"]],
                RANDOM_BUILDS)
    if nome == "identity_run":
        return (f"identidade de {args['geracao']}",
                py + ["main.py", "identity", "run", args["geracao"]],
                RANDOM_BUILDS)
    if nome == "identity_worker":
        return ("processar a fila de identidade",
                py + ["main.py", "identity", "worker", "--once"], RANDOM_BUILDS)
    if nome == "refazer_imagens":
        return (f"imagens de {args['historia']}",
                py + ["main.py", "imagens", args["historia"]], HISTORIAS)
    if nome == "trilha":
        return ("gerar trilha", py + ["main.py", "trilha"], RANDOM_BUILDS)
    if nome == "metricas":
        return ("atualizar métricas",
                py + ["main.py", "metricas", "--atualizar"], RANDOM_BUILDS)
    if nome == "gerar_historia":
        comando = py + ["main.py", "gerar", "--provedor", args["provedor"],
                        "--partes", str(args["partes"]),
                        "--cenas", str(args["cenas"])]
        if args.get("tema"):
            comando += ["--tema", args["tema"]]
        return (f"história nova pelo {args['provedor']}", comando, HISTORIAS)
    if nome == "historia_tudo":
        return (f"terminar {args['historia']}",
                py + ["main.py", "tudo", args["historia"]], HISTORIAS)
    if nome == "historia_video":
        return (f"vídeo de {args['historia']}",
                py + ["main.py", "video", args["historia"]], HISTORIAS)
    if nome == "duelo":
        comando = py + ["main.py", "duelo"]
        for campo, bandeira in (("p1", "--p1"), ("p2", "--p2")):
            if args.get(campo):
                comando += [bandeira, args[campo]]
        return ("gravar duelo", comando, RANDOM_BUILDS)
    if nome == "publicar_historia":
        comando = py + ["main.py", "publicar", args["historia"]]
        if args.get("serie"):
            comando += ["--serie"]
        if args["onde"] in ("youtube", "ambos"):
            comando += ["--youtube", "--visibilidade", "public"]
        if args["onde"] in ("tiktok", "ambos"):
            comando += ["--tiktok"]
        return (f"publicar {args['historia']} em {args['onde']}", comando,
                HISTORIAS)
    if nome == "escoar":
        return (f"escoar {args['limite']} de {args['canal']}",
                py + [str(FERRAMENTAS / "postar.py"), "--tudo",
                      "--limite", str(args["limite"]), "--so", args["canal"]],
                RAIZ)
    if nome == "recuperar":
        return ("recuperar vídeo privado",
                py + [str(FERRAMENTAS / "postar.py"), "--recuperar"], RAIZ)
    if nome == "ver_postagem":
        return ("ver o próximo horário",
                py + [str(FERRAMENTAS / "postar.py"), "--ver"], RAIZ)
    if nome == "curar_ledger":
        comando = py + [str(FERRAMENTAS / "curar_ledger.py"),
                        "--canal", args["canal"]]
        if args.get("gravar"):
            comando += ["--gravar"]
        return (f"curar o ledger de {args['canal']}"
                + (" (gravando)" if args.get("gravar") else " (a seco)"),
                comando, RAIZ)
    if nome == "conciliar_tiktok":
        comando = py + [str(FERRAMENTAS / "conciliar_tiktok.py")]
        if args.get("gravar"):
            comando += ["--gravar"]
        return ("conciliar o TikTok"
                + (" (gravando)" if args.get("gravar") else " (a seco)"),
                comando, RAIZ)
    if nome == "apagar_midia":
        # o `mimetizar` nao tem esse comando; o laco vive em
        # `remoto/limpar_espelho.py`, igual ao que o painel faz
        return (f"apagar mídia de {args['canal']}",
                py + ["-m", "remoto.limpar_espelho", args["canal"]], RAIZ)
    if nome == "regenerar_banco":
        return ("regenerar o banco",
                py + ["-m", "neural_fights.tools.gerador_database"], RAIZ)
    raise _erro(f"ação sem comando: {nome}")


# ------------------------------------------------------------- execucao
def texto(nome: str, args: dict) -> str:
    """O que a confirmacao mostra. Diz o preco, nao so o nome."""
    ficha = FICHAS[nome]
    detalhes = ", ".join(f"{c['rotulo'].lower()}: {args.get(c['nome'])}"
                         for c in ficha["campos"]
                         if args.get(c["nome"]) not in (None, "", False))
    aviso = ""
    if nome == "publicar_historia":
        aviso = (" A série inteira fica agendada, uma parte por dia."
                 if args.get("serie") else " Vai ao ar como PÚBLICO.")
    elif nome in ("escoar", "recuperar"):
        aviso = " Publica de verdade, fora da grade."
    elif e_perigosa(nome, args):
        aviso = " NÃO tem desfazer."
    elif nome in ("gerar_historia", "identity_worker", "identity_run",
                  "refazer_imagens", "historia_tudo"):
        aviso = " Usa as contas compartilhadas e leva minutos."
    return f"{ficha['rotulo']}{(' — ' + detalhes) if detalhes else ''}?{aviso}"


def executar(nome: str, args: dict, aparelho: str = "") -> str:
    """Roda direto (as instantaneas) ou sobe uma tarefa com log."""
    from . import acoes, tarefas
    if nome == "liberar":
        saiu = acoes.liberar(args["id"])
        return f"liberados: {saiu}" if saiu else "esse vídeo não está em voo"
    if nome == "soltar_marca":
        return ("marca do app retirada" if acoes.soltar_marca(args["id"])
                else "esse vídeo não tem marca do app")
    if nome == "esquecer_conta":
        from builds import contas as registro
        registro.remover(args["servico"], args["conta"])
        return f"{args['servico']}/{args['conta']} saiu do registro"
    if nome == "escolher_conta":
        from builds import contas as registro
        registro.escolher(args["servico"], args["canal"], args["conta"])
        return (f"{args['canal']} passa a publicar em "
                f"{args['servico']}/{args['conta']}")
    rotulo, comando, cwd = montar(nome, args)
    chave = tarefas.iniciar(nome, rotulo, comando, cwd, aparelho, args)
    return f"comecei: {rotulo}. Acompanhe em Tarefas (#{chave[-6:]})."


__all__ = ["CATALOGO", "FICHAS", "GRUPOS", "PESADAS", "alvo_do_perigo",
           "catalogo", "e_perigosa", "executar", "guardar", "montar", "texto",
           "validar"]
