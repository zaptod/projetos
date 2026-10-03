# -*- coding: utf-8 -*-
"""O que o bot sabe fazer. Tabela FECHADA de comandos, nunca shell.

Decisao de projeto, escrita aqui para nao se perder: este bot nao executa
texto vindo do celular. Cada comando e uma funcao Python desta tabela, e os
argumentos sao validados (um id de video so pode ser um id que existe no
catalogo). Um `/rodar <qualquer coisa>` seria conveniente por cinco minutos
e um buraco para sempre — a maquina do outro lado tem YouTube, TikTok,
ChatGPT e PicassoIA logados.

As funcoes devolvem TEXTO (e, as vezes, um caminho de arquivo para enviar).
Elas nao falam com o Telegram: isso deixa cada uma testavel sem rede, que e
como os testes deste arquivo rodam.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RANDOM_BUILDS = RAIZ / "random_builds"
HISTORIAS = RAIZ / "historias"
PY = sys.executable
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


from builds import atividade                                      # noqa: E402
from builds.identity import controle                              # noqa: E402

MAX_LINHAS = 18          # o celular nao le mais que isso de uma vez


# --------------------------------------------------------------- ajudantes
def _catalogo():
    from builds.publicar import catalogo
    return catalogo


def _tabela_videos(quantos: int = 8) -> list:
    try:
        videos = _catalogo().listar()
    except Exception:
        return []
    return sorted(videos, key=lambda v: v.quando, reverse=True)[:quantos]


def _rodar(args: list, cwd: Path, rotulo: str) -> str:
    """Dispara e NAO espera: uma geracao leva minutos, o celular nao espera.

    O resultado chega depois pelos alertas do diario — que e justamente o
    motivo de o diario existir.
    """
    try:
        subprocess.Popen(args, cwd=str(cwd), creationflags=NO_WINDOW,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return f"nao consegui iniciar {rotulo}: {exc}"
    return (f"comecei: {rotulo}\n"
            "Leva minutos. Eu aviso aqui quando terminar ou der erro.")


# ---------------------------------------------------------------- comandos
def ajuda(_args: str = "") -> str:
    return (
        "*O que eu faço*\n"
        "/status — o que está rodando agora\n"
        "/vila — as 7 fábricas, uma linha cada\n"
        "/erros — os últimos problemas\n"
        "/videos — os vídeos prontos, com id\n"
        "/ver <id> — manda o mp4 aqui pra você assistir\n"
        "/publicar — publicar é só pelo app do celular\n"
        "/gerar — uma build nova (roleta + vídeo)\n"
        "/historias — em que pé está o canal de histórias\n"
        "/metas — quantos vídeos, em que horário, em que canal\n"
        "/lote — o estoque contra o lote da semana (piso e janela)\n"
        "/funcionamento — tempos, erros e agendamento das últimas 24h\n"
        "/confiabilidade — o que saiu hoje e o que dá para provar\n"
        "/testar\\_conserto <carimbo> — a suíte com um remendo proposto\n"
        "/pausar [minutos] · /retomar · /parar\n"
        "/novo — o próximo pedido abre outro orquestrador\n"
        "/ajuda — isto aqui\n"
        "Texto sem / é um pedido: vai a um 🧭 orquestrador do servidor "
        "(pergunta curta de estado vai ao 🛰 coordenador). A resposta vem aqui.")


def status(_args: str = "") -> str:
    estado = atividade.estado_das_fabricas()
    trabalhando = [n for n, e in estado.items() if e["status"] == "trabalhando"]
    com_erro = [n for n, e in estado.items() if e["status"] == "erro"]
    pausa = controle.estado()

    linhas = []
    if trabalhando:
        for nome in trabalhando:
            dados = atividade.FABRICAS.get(nome, {})
            detalhe = (estado[nome].get("detalhe") or "")[:60]
            linhas.append(f"{dados.get('emoji', '•')} {dados.get('rotulo', nome)}"
                          f" — {detalhe}" if detalhe else
                          f"{dados.get('emoji', '•')} {dados.get('rotulo', nome)}")
        cabeca = f"⚙ {len(trabalhando)} fábrica(s) trabalhando"
    else:
        cabeca = "😴 nada rodando agora"
    if com_erro:
        linhas.append("")
        for nome in com_erro:
            dados = atividade.FABRICAS.get(nome, {})
            linhas.append(f"❗ {dados.get('rotulo', nome)}: "
                          f"{(estado[nome].get('detalhe') or '')[:70]}")
    resumo_pausa = pausa.get("resumo") or ""
    if resumo_pausa and "rodando" not in resumo_pausa.lower():
        linhas.append("")
        linhas.append(f"⏸ {resumo_pausa}")
    return "\n".join([cabeca] + linhas)


def vila(_args: str = "") -> str:
    estado = atividade.estado_das_fabricas()
    icone = {"trabalhando": "⚙", "erro": "❗", "ocioso": "·"}
    linhas = []
    for nome, dados in atividade.FABRICAS.items():
        info = estado.get(nome, {})
        situacao = info.get("status", "ocioso")
        detalhe = (info.get("detalhe") or "")[:40]
        linhas.append(f"{icone.get(situacao, '·')} {dados['emoji']} "
                      f"{dados['rotulo']:<11} {detalhe}".rstrip())
    return "\n".join(linhas)


def erros(args: str = "") -> str:
    try:
        quantos = min(int(args.strip()), MAX_LINHAS)
    except (TypeError, ValueError):
        quantos = 6
    eventos = [e for e in atividade.recentes(200)
               if e.get("status") == "erro"][:quantos]
    if not eventos:
        return "✓ nenhum erro registrado."
    linhas = []
    for evento in eventos:
        hora = str(evento.get("ts", ""))[11:16]
        fabrica = atividade.FABRICAS.get(evento.get("fabrica"), {})
        linhas.append(f"{hora} {fabrica.get('emoji', '•')} "
                      f"{(evento.get('detalhe') or '')[:110]}")
    return "\n".join(linhas)


def videos(_args: str = "") -> str:
    prontos = _tabela_videos()
    if not prontos:
        return "nenhum vídeo pronto ainda."
    linhas = ["*Prontos* (use /ver com o id; publicar é pelo app)"]
    for video in prontos:
        linhas.append(f"`{video.id}`\n   {video.titulo[:58]}")
    return "\n".join(linhas)


def _listar_videos() -> list:
    try:
        return list(_catalogo().listar())
    except Exception:
        return []


def procurar_video(pedaco: str, videos: list | None = None):
    """O video com ESTE id, ou o unico cujo id comeca com o pedaco.

    17/09/2026: casava por prefixo OU trecho e devolvia o primeiro. O id da
    variante A e prefixo do da B (`...:B`), e "00023" casava com qualquer id
    que tivesse isso no meio — o /publicar podia subir outro video. Prefixo
    com mais de um dono nao escolhe: devolve None e `candidatos` lista.
    """
    pedaco = (pedaco or "").strip()
    if not pedaco:
        return None
    videos = _listar_videos() if videos is None else videos
    for video in videos:
        if video.id == pedaco:
            return video
    comecam = [v for v in videos if v.id.startswith(pedaco)]
    return comecam[0] if len(comecam) == 1 else None


def candidatos(pedaco: str, videos: list | None = None,
               limite: int = 5) -> list:
    """Sugestoes quando `procurar_video` nao decide. So para MOSTRAR."""
    pedaco = (pedaco or "").strip()
    if not pedaco:
        return []
    videos = _listar_videos() if videos is None else videos
    achados = ([v for v in videos if v.id.startswith(pedaco)]
               or [v for v in videos if pedaco in v.id])
    return achados[:limite]


def _nao_achei(pedaco: str) -> str:
    opcoes = candidatos(pedaco)
    if not opcoes:
        return "não achei esse id. Use /videos para ver a lista."
    linhas = ["esse id não é exato; mande o id inteiro. Parecidos:"]
    linhas += [f"`{v.id}`" for v in opcoes]
    return "\n".join(linhas)


def ver(args: str = "") -> tuple:
    """(texto, caminho): o bot manda o arquivo quando ha caminho."""
    video = procurar_video(args)
    if video is None:
        return (_nao_achei(args), None)
    return (f"{video.titulo}", Path(video.caminho))


# ---------------------------------------------------------------- publicar
# SO O APP PUBLICA PELO CELULAR. Decisao do Adrian em 28/09/2026. Ate 27/09 o
# /publicar daqui chamava `main.py publicar` direto, num passo so: sem o "em
# voo" do app, sem a lista "a conferir", sem a janela da grade, sem olhar o
# `postar.py` — e sem `--visibilidade`, entao o YouTube subia PRIVADO. Na
# manha de 28/09 ele passou pelas guardas do app (d68523e); no mesmo dia o
# Adrian decidiu que publicar e so pelo app, que tem tela para conferir o
# video, e o comando passou a so responder isso. Nada daqui chega ao
# `main.py publicar` nem as `acoes` de publicacao.
SO_PELO_APP = ("Publicar é só pelo app do celular: lá tem a tela para "
               "conferir o vídeo, o destino e a confirmação em dois passos. "
               "Aqui eu não publico nada.")


def publicar(_args: str = "") -> str:
    return SO_PELO_APP


def gerar(_args: str = "") -> str:
    return _rodar([PY, "main.py", "generate-video"], RANDOM_BUILDS,
                  "uma build nova")


def historias(_args: str = "") -> str:
    try:
        saida = subprocess.run(
            [PY, "-X", "utf8", "main.py", "status"], cwd=str(HISTORIAS),
            capture_output=True, text=True, encoding="utf-8", timeout=120,
            creationflags=NO_WINDOW).stdout or ""
    except (OSError, subprocess.SubprocessError) as exc:
        return f"não consegui ler as histórias: {exc}"
    linhas = [l.rstrip() for l in saida.splitlines() if l.strip()]
    return "\n".join(linhas[:MAX_LINHAS]) or "nenhuma história ainda."


def metas(_args: str = "") -> str:
    """O mesmo texto que chega sozinho todo dia — sob demanda."""
    from . import relatorios
    return relatorios.montar("metas")


def lote(_args: str = "") -> str:
    """O lote da semana: estoque x alvo ate segunda, piso e janela. So le.

    O mesmo `remoto.lote.resumo` do relatorio de metas, do painel e do app
    (lote semanal de dia, decisoes de 30/09/2026).
    """
    from . import lote as _lote
    return _lote.texto()


def funcionamento(_args: str = "") -> str:
    from . import relatorios
    return relatorios.montar("funcionamento")


def confiabilidade(_args: str = "") -> str:
    """O que foi afirmado hoje e o que da para provar. So le disco."""
    from . import relatorios
    return relatorios.montar("confiabilidade")


def auditoria(_args: str = "") -> str:
    """Os quatro controles, e o que a grade vai barrar no proximo horario.

    Responde outra pergunta que `/metas` e `/funcionamento`: os dois olham
    para tras (o que saiu, o que falhou) e um video ruim que publica sem erro
    nao aparece em nenhum dos dois. Este olha para a frente.
    """
    from . import relatorios
    return relatorios.montar("auditoria")


def testar_conserto(args: str = "") -> str:
    """Testa um remendo PROPOSTO pelo conserto automatico. Nunca aplica.

    A suite leva minutos: o teste roda num processo a parte, e o resultado
    chega por mensagem. A validacao aqui e a barata (formato, remendo
    existe); as travas e o teto sao conferidos de novo la dentro.
    """
    from . import apurador
    carimbo = args.strip()
    if not carimbo:
        return "use: /testar_conserto <carimbo> (vem no aviso do conserto)"
    motivo = apurador.motivo_para_nao_testar(carimbo)
    if motivo:
        return f"não vou testar: {motivo}"
    return _rodar([PY, "-m", "remoto", "--testar-conserto", carimbo], RAIZ,
                  f"o teste do remendo {carimbo}")


def pausar(args: str = "") -> str:
    try:
        minutos = float(args.strip()) if args.strip() else None
    except ValueError:
        minutos = None
    estado = controle.pausar(motivo="pelo celular", minutos=minutos)
    return f"⏸ {estado.get('resumo', 'pausado')}"


def retomar(_args: str = "") -> str:
    estado = controle.retomar()
    return f"▶ {estado.get('resumo', 'retomado')}"


def parar(_args: str = "") -> str:
    estado = controle.pedir_parada("pelo celular")
    return (f"⏹ {estado.get('resumo', 'parada pedida')}\n"
            "O job atual termina antes de encerrar.")


# A tabela. Nada fora daqui roda — e de proposito.
TABELA = {
    "ajuda": ajuda, "start": ajuda, "help": ajuda,
    "status": status,
    "vila": vila,
    "erros": erros,
    "videos": videos,
    "ver": ver,
    "publicar": publicar,
    "gerar": gerar,
    "historias": historias,
    "metas": metas,
    "lote": lote,
    "funcionamento": funcionamento,
    "relatorio": funcionamento,
    "confiabilidade": confiabilidade,
    "prova": confiabilidade,
    "testar_conserto": testar_conserto,
    "auditoria": auditoria,
    "auditar": auditoria,
    "pausar": pausar,
    "retomar": retomar,
    "parar": parar,
}


def falar_ao_coordenador(texto: str) -> str:
    """Texto sem `/` e uma mensagem para o coordenador (02/10/2026).

    O bot NAO pensa nem executa nada: so grava e responde que recebeu.
    Desde 03/10, pergunta curta de estado ("o app esta no ar?") vai a entrada
    do cerebro (`coordenador.cerebro.registrar_entrada`, responde em
    segundos); o resto e PEDIDO (`coordenador.pedidos.registrar`), que um
    trabalhador `orquestrador` do servidor atende sem o VS Code aberto. As
    respostas chegam por aqui mesmo, pelo envio de sempre."""
    try:
        from coordenador import cerebro, pedidos
        if pedidos.e_de_estado(texto):
            cerebro.registrar_entrada(texto, "telegram")
            return ("🛰 recebido, pensando… o coordenador responde aqui. "
                    "Os comandos com / continuam: /ajuda")
        item = pedidos.registrar(texto, "telegram")
    except Exception as exc:      # nenhuma mensagem derruba o bot
        return (f"não consegui guardar sua mensagem para o coordenador "
                f"({type(exc).__name__}). Os comandos com / continuam: /ajuda")
    if item.get("continuacao"):
        return ("🧭 recebido; vai ao MESMO orquestrador do pedido aberto. "
                "Assunto novo: /novo antes. Os comandos com / continuam: /ajuda")
    return ("🧭 recebido; um orquestrador do servidor vai atender e eu aviso aqui "
            "quando estiver conferido. Os comandos com / continuam: /ajuda")


def novo(_args: str = "") -> str:
    """/novo — o proximo texto abre outro orquestrador (outro assunto)."""
    try:
        from coordenador import pedidos
        pedidos.novo_assunto("telegram")
    except Exception as exc:      # noqa: BLE001
        return f"não consegui abrir um assunto novo ({type(exc).__name__})."
    return "🧭 assunto novo: o próximo texto vai a um orquestrador novo."


TABELA["novo"] = novo


def executar(texto: str):
    """(resposta, arquivo_ou_None) para o texto que chegou do celular."""
    texto = (texto or "").strip()
    if not texto.startswith("/"):
        return (falar_ao_coordenador(texto), None)
    corpo = texto[1:]
    nome, _, args = corpo.partition(" ")
    nome = nome.split("@")[0].lower()       # /status@meubot
    funcao = TABELA.get(nome)
    if funcao is None:
        return (f"não conheço /{nome}. Veja /ajuda.", None)
    try:
        resultado = funcao(args.strip())
    except Exception as exc:      # nenhum comando pode derrubar o bot
        return (f"o comando /{nome} falhou: {type(exc).__name__}: {exc}", None)
    if isinstance(resultado, tuple):
        return resultado
    return (resultado, None)
