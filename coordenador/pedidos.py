# -*- coding: utf-8 -*-
"""Pedidos livres do Adrian atendidos pela equipe soberana (03/10/2026).

O Adrian: "atualmente o unico lugar confiavel para fazer requisicoes e aqui
[o chat do VS Code], mas isso me limita muito!". O pedido do app (Agora >
Pedir, Coordenador > Conversa) ou do Telegram vira um item aqui, e um
trabalhador de cargo `orquestrador` (remoto.delegar) o atende numa worktree.

O arquivo e o servidor sao a fonte da verdade.  O trabalhador e descartavel:
se a sessao some, trava ou o Claude fica proibido, o pedido fica "esperando"
com o motivo e o pulso o retoma.

Ciclo de um pedido:
    recebido -> trabalhando -> entregue -> (o vigia aplica) -> conferente
             -> conferido | falhou
    trabalhando sem mudanca de codigo -> respondido (nada a conferir)
    qualquer passo -> esperando (motivo) -> retomado
    caiu no limite do Claude -> parado_limite (NAO gasta retomada) -> esperando
             quando o uso liberar (ou o Codex assume, se for de construir)
    precisa de decisao do Adrian -> esperando_voce (o no) -> a resposta
             dele volta ao MESMO pedido como continuacao
    pediu `EXECUTAR: <acao>` -> executando (no repositorio principal, lista
             branca, nunca publica) -> o resultado volta ao mesmo trabalhador
    pediu `EXECUTAR: gerente ligar` (estado do servidor) -> o SERVIDOR grava,
             relê e responde (o trabalhador na worktree nao alcanca o LOCALAPPDATA)
    terminou: a ultima linha `DESFECHO: feito | bloqueado — ... | falhou — ...`
             decide entregue/respondido, esperando_voce (com o que falta) ou falhou.
             Sem a linha, frase de bloqueio ("nao foi possivel", "falta o Adrian")
             vira esperando_voce: "entregue" nunca sai as cegas (05/10/2026)
    saudacao/"como estao as coisas?" -> respondido na hora com o retrato do
             servidor; nunca gruda num pedido antigo (05/10/2026)

Nada aqui roda Claude/Codex no proprio processo: tudo vai por
`delegar.no_fundo` (o pulso do coordenador e a requisicao do app nunca ficam
presos uma hora numa rodada). A acao da lista branca roda numa thread, e o
pulso so le o resultado.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import unicodedata
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from . import estado

SEM_EVENTO_S = 10 * 60      # sem evento ha 10 min = travado
RETOMAR_S = 120             # entre duas tentativas de retomar o mesmo pedido
PROGRESSO_S = 60            # no maximo uma linha de progresso por minuto
MAX_RETOMADAS = 5           # o mesmo trabalhador retomado 5 vezes: falhou
MAX_EXECUCOES = 3           # acoes do repositorio real por pedido
FINAIS = ("conferido", "falhou", "respondido")
VIVOS = ("recebido", "trabalhando", "esperando", "entregue", "parado_limite",
         "esperando_voce", "executando")
PERMITIDOS = ["remoto/**", "coordenador/**", "docs/**", ".claude/agents/**"]
_TRAVA = threading.RLock()
RAIZ = Path(__file__).resolve().parents[1]
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# A resposta final do trabalhador pede a decisao ou a acao numa linha propria.
# O projeto pode ter hifen (app-e-bot, jogo-zombie, painel-e-vila).
_MARCA_GRIMORIO = re.compile(
    r"^[ \t>*_`-]*GRIM[ÓO]RIO[*_`]*\s*:[*_`]*\s*`?([a-z0-9][a-z0-9-]{0,39})\s*/\s*"
    r"([a-z0-9][a-z0-9-]{0,59})`?\s*$",
    re.IGNORECASE | re.MULTILINE)
_MARCA_EXECUTAR = re.compile(
    r"^[ \t>*_`-]*EXECUTAR[*_`]*\s*:\s*`?([a-z0-9_]+)((?:[ \t]+[^\s`]+)*)`?[ \t]*$",
    re.IGNORECASE | re.MULTILINE)
# 05/10/2026: "entregue" mentia. O cb44cd52 ("ligar o gerente") ficou
# "entregue" com a resposta "Nao foi possivel ligar"; o cd2e5e0c com "Status:
# bloqueado so pelo login do Drive". A ultima linha da resposta diz o desfecho.
_MARCA_DESFECHO = re.compile(
    r"^[ \t>*_`-]*DESFECHO[*_`]*[ \t]*:[*_` \t]*(feito|bloqueado|falhou)\b[*_`]*[ \t]*"
    r"(?:[—–:-]+[ \t]*)?(.*?)[*_` \t]*$",
    re.IGNORECASE | re.MULTILINE)
# Sem a linha, frases de quem NAO terminou (comparadas sem acento).
# 05/10/2026 (conferente): palavra solta em qualquer linha dava falso bloqueio
# em 7 de 59 respostas reais de entregas boas ("a remocao foi bloqueada pela
# politica do sandbox", no fim; "depende do Adrian aprovar", descrevendo o
# cerebro). Nos 5 bloqueios de verdade o veredito esta na ABERTURA ("Nao foi
# possivel ligar", "Nao apliquei a escolha") ou na forma de ESTADO ("Status:
# bloqueado", "Bloqueado por permissao", "Falta o Adrian abrir...").
_BLOQUEIO_ESTADO = tuple(re.compile(p) for p in (       # em qualquer linha
    r"^(?:status\s*:?\s*)?bloquead[oa]s?\b",
    r"\b(?:estou|fiquei|continuo|sigo|estamos|ficamos)\s+bloquead[oa]s?\b",
    r"\bfalta (?:o|do) adrian\b", r"\bso o adrian (?:pode|consegue|faz)\b"))
_BLOQUEIO_ABERTURA = tuple(re.compile(p) for p in (     # so no 1o paragrafo
    r"\bnao foi possivel\b", r"\bnao consegui\b", r"\bnao deu para\b", r"\bnao apliquei\b",
    r"\bnao da para\b", r"\bfoi bloquead[oa]\b", r"\bpermissao negada\b",
    r"\baguardando (?:a )?permissao\b", r"\b(?:depende|precisa) (?:do|que o) adrian\b"))
# "DESFECHO: feito parcialmente — faltou o teste" nao e feito
_FEITO_COM_RESSALVA = re.compile(
    r"\b(?:parcial\w*|faltou|faltam?|exceto|mas|porem|ressalvas?|pendentes?|incomplet\w*)\b")
_RASCUNHO = re.compile(r"(?:^|/)(?:resposta\.md|\.permissao\.json|\.codex_tarefa\.md|"
                       r"\.tarefa_[^/]*\.md|\.conf_[^/]*\.md)$")
# A queda por limite do Claude: so na rodada mais nova (depois do ultimo
# `delegar.inicio`), para um evento velho nao condenar uma rodada nova.
_FRASES_DE_LIMITE = ("hit your weekly limit", "hit your limit", "usage limit",
                     "weekly limit", "rate limit")

# Lacuna 3 (05/10/2026): o trabalhador vive numa worktree e nao alcanca o
# repositorio real (o estoque, o login, o perfil do navegador). O 66e4ba54
# pediu "rodar o teste ao vivo do PicassoIA e o main.py auto" e caiu 5 vezes
# esperando. Estas acoes o pulso roda no repositorio principal; estar nesta
# lista E a permissao. `{1}` e o 1o argumento depois do nome, conferido pela
# expressao de `parametros`. Nenhuma publica (e `_publica` barra de novo).
_PY = sys.executable or "python"
ACOES_REPO = {
    "historias_imagens": {
        "o_que": "teste ao vivo das imagens: 2 cenas de uma história (não publica)",
        "argv": [_PY, "-u", "-X", "utf8", "main.py", "imagens", "{1}", "--limite", "2"],
        "cwd": "historias", "parametros": [r"historia_\d{5}"], "timeout_s": 40 * 60},
    "historias_auto": {
        "o_que": "rodada de criação automática: enche a reserva de histórias (não publica)",
        "argv": [_PY, "-u", "-X", "utf8", "main.py", "auto"],
        "cwd": "historias", "timeout_s": 3 * 3600},
    "historias_auto_listar": {
        "o_que": "o que a criação automática faria agora (só lê)",
        "argv": [_PY, "-u", "-X", "utf8", "main.py", "auto", "--listar"],
        "cwd": "historias", "timeout_s": 5 * 60, "janela": False},
    "historias_conferir": {
        "o_que": "procura defeito no que já está no disco (só lê)",
        "argv": [_PY, "-u", "-X", "utf8", "main.py", "conferir"],
        "cwd": "historias", "timeout_s": 15 * 60, "janela": False},
    "testes_coordenador": {
        "o_que": "a suíte do coordenador e do orquestrador no repositório real",
        "argv": [_PY, "-m", "pytest", "coordenador", "remoto/test_orquestrador.py", "-q",
                 r"--basetemp=E:\tmp_pytest\executor_pedidos"],
        "cwd": ".", "timeout_s": 25 * 60, "janela": False,
        "env": {"TEMP": r"E:\tmp_pytest", "TMP": r"E:\tmp_pytest",
                "PYTEST_ADDOPTS": "-p no:cacheprovider"}},
}
# 05/10/2026: o cb44cd52 pediu "ligar o gerente" e o Codex respondeu "Nao foi
# possivel": a worktree nao grava o %LOCALAPPDATA% (delegar.lock). Estas acoes
# mudam o ESTADO do servidor: o pulso faz na hora (escrita de um json, sem
# janela), rele para conferir e responde ao Adrian. `fazer` e o nome da funcao
# deste modulo (procurada na hora: o teste troca). Nunca publica, conta ou push.
ACOES_SERVIDOR = {
    "gerente": {
        "o_que": "liga ou desliga o gerente da equipe (a fila anda sozinha)",
        "parametros": [r"ligar|desligar"], "fazer": "_servidor_gerente"},
    "renovacao": {
        "o_que": "renova a conversa do trabalhador depois de <turnos> turnos ou <minutos> min",
        "parametros": [r"[1-9]\d{0,2}", r"[1-9]\d{0,2}"], "fazer": "_servidor_renovacao"},
    "paralelo": {
        "o_que": "quantos trabalhadores ao mesmo tempo (1 a 8), pela Mesa",
        "parametros": [r"[1-8]"], "fazer": "_servidor_paralelo"},
}
_PUBLICA = ("publicar", "postar", "upload", "publish", "push")
JANELA_ANTES_MIN, JANELA_DEPOIS_MIN = 12, 18      # a janela das postagens

# perguntas curtas de estado continuam no cerebro (resposta em segundos)
_DE_ESTADO = ("como est", "status", "no ar", "rodando", "serviço", "servico",
              "caiu", "ta de pe", "tá de pé", "está de pé", "esta de pe")
_CONSTRUIR = ("construa", "construir", "implemente", "implementar", "crie", "criar",
              "faça", "faca", "desenvolva", "desenvolver", "conserte", "consertar",
              "corrija", "corrigir", "adicione", "adicionar", "mude", "mudar")
_VERBO = {"le": "lendo", "testa": "rodando testes", "roda": "rodando", "muda": "mudando",
          "plano": "plano", "mensagem": "diz", "despachante": "despachante",
          "erro": "erro"}

# 05/10/2026: "Ola coordenador, como as coisas estao" e "Coordenador?" viraram
# continuacao do cd2e5e0c (o arquivo no Drive). Conversa solta nao e pedido:
# responde na hora com o retrato do servidor e nao gruda em pedido nenhum.
_SAUDACAO = re.compile(r"^(?:oi+|ola|ole|opa|salve|hey|alo|e ai|eai|eae|bom dia|boa tarde|"
                       r"boa noite)\b")
_CHAMADO = re.compile(r"^(?:coordenador|orquestrador|servidor|ta ai|esta ai|alguem ai|"
                      r"tudo bem|tudo certo|e entao)?$")
# "como as coisas estao" (o verbo no fim) ou o substantivo de andamento numa
# PERGUNTA ("qual o progresso", "alguma novidade?"); "um pedido em andamento"
# e frase de pedido, nao conversa
_COMO_ESTA = re.compile(r"\bcomo\b.*\b(?:esta|estao|anda|andam|vai|vao|ficou|ficaram|ta|tao)$")
_ANDAMENTO = re.compile(r"\b(?:novidades?|progresso|andamento|status)\b")
_PERGUNTA = re.compile(r"^(?:qual|quais|como|tem|alguma|algum|cade|e o|e a|e os|e as)\b|"
                       r"^(?:o |a )?(?:novidades?|progresso|andamento|status)$")
# quem informa ou manda nao esta so conversando ("ja loguei", "pode ligar")
_INFORMA = re.compile(r"\b(?:loguei|liguei|entrei|instalei|fiz|pronto|feito|pode|use|usa|"
                      r"quero|prefiro|aprovo|liga|ligue|desliga|desligue|pare)\b")
_ROTULO = {"recebido": "recebido", "trabalhando": "trabalhando", "esperando": "em espera",
           "entregue": "entregue, esperando aplicar e conferir",
           "parado_limite": "parado no limite do Claude", "esperando_voce": "esperando você",
           "executando": "executando no servidor", "conferido": "conferido",
           "falhou": "falhou", "respondido": "respondido"}


def _agora():
    return datetime.now()


def _iso(quando=None):
    return (quando or _agora()).isoformat(timespec="seconds")


def _arquivo():
    return estado.pasta() / "pedidos.json"


def _ler():
    try:
        dados = json.loads(_arquivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = None
    if not isinstance(dados, dict):
        dados = {}
    if not isinstance(dados.get("pedidos"), list):
        dados["pedidos"] = []
    if not isinstance(dados.get("conversa"), list):
        dados["conversa"] = []
    return dados


def _gravar(dados):
    alvo = _arquivo()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    temporario = alvo.with_name("." + alvo.name + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")),
                          encoding="utf-8")
    os.replace(temporario, alvo)


def _linha(dados, pedido, texto, *, de="orquestrador", origem=None, tipo="progresso",
           limite=600):
    linha = {"id": uuid.uuid4().hex[:12], "em": _iso(), "pedido": pedido["id"],
             "de": de, "origem": origem or pedido.get("origem", "app"),
             "tipo": tipo, "texto": str(texto)[:limite]}
    dados["conversa"].append(linha)
    dados["conversa"] = dados["conversa"][-400:]
    return linha


def e_de_estado(texto: str) -> bool:
    """Pergunta curta de estado ("o app esta no ar?"): vai ao cerebro, nao
    contrata ninguem."""
    texto = str(texto or "").strip().lower()
    if len(texto) > 160 or _construir(texto):
        return False
    pergunta = "?" in texto or texto.startswith("status")
    return pergunta and any(p in texto for p in _DE_ESTADO)


def _construir(texto):
    texto = str(texto or "").lower()
    return any(palavra in texto for palavra in _CONSTRUIR)


def _sem_acento(texto) -> str:
    decomposto = unicodedata.normalize("NFKD", str(texto or "").lower())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def _plano(texto) -> str:
    """Minusculo, sem acento, sem pontuacao, espacos simples."""
    return " ".join(re.sub(r"[^\w\s]", " ", _sem_acento(texto)).split())


def e_conversa_solta(texto: str) -> bool:
    """Saudacao, chamado ("Coordenador?") ou pergunta curta de andamento
    ("como as coisas estao", "qual o progresso"): nao e pedido nem continuacao."""
    plano = _plano(texto)
    if len(plano) > 80 or _construir(plano) or _INFORMA.search(plano):
        return False
    resto = _SAUDACAO.sub("", plano).strip()
    resto = re.sub(r"^(?:coordenador|orquestrador)\b", "", resto).strip()
    if _CHAMADO.fullmatch(resto):
        return True
    if len(resto.split()) > 8:
        return False
    if _COMO_ESTA.search(resto):
        return True
    pergunta = "?" in str(texto) or bool(_PERGUNTA.search(resto))
    return pergunta and bool(_ANDAMENTO.search(resto))


def _frases_de_bloqueio(texto: str) -> list:
    """As linhas que dizem "nao terminei": a forma de estado em qualquer linha,
    a frase fraca so na abertura (o 1o paragrafo, ate 3 linhas). As linhas de
    marca (DESFECHO, EXECUTAR, GRIMORIO) nao contam."""
    linhas = [x.strip(" \t*_>-`") for x in str(texto or "").splitlines()]
    linhas = [x for x in linhas if not re.match(r"(?i)(?:desfecho|executar|grim[óo]rio)\s*[*_`]*:", x)]
    while linhas and not linhas[0]:
        linhas.pop(0)
    abertura = []
    for linha in linhas:
        if not linha or len(abertura) == 3:
            break
        abertura.append(linha)
    achadas = []
    for i, linha in enumerate(linhas):
        plano = _sem_acento(linha)
        if (any(p.search(plano) for p in _BLOQUEIO_ESTADO)
                or (i < len(abertura) and any(p.search(plano) for p in _BLOQUEIO_ABERTURA))):
            achadas.append(linha)
    return achadas


# Pedido que ja parou e espera: so recebe a mensagem que responde a ELE.
_AGUARDAM_RESPOSTA = ("entregue", "esperando_voce")
_CONTINUA = re.compile(r"^(?:e|tambem|agora|ainda|mais|alem disso|aproveita\w*|so que|mas|"
                       r"isso|esse|essa|nele|nela|nesse|nessa|neste|nesta|dele|dela|ok|sim|"
                       r"nao|beleza|blz|certo|ja|deu)\b")
_COMUNS = frozenset(
    "agora ainda antes depois quando porque sobre tambem fazer favor preciso quero outra outro "
    "outras outros coisa coisas pedido pedidos adrian todos todas mesmo mesma esses essas estes "
    "estas aquele aquela ficou estao voce entao assim alguma algum desse dessa deste desta onde "
    "aqui obrigado valeu coordenador orquestrador servidor responda resposta tarefa precisa "
    "pode podem deixa esta isto nisso".split())


def _palavras(texto) -> set:
    """As palavras que identificam um assunto (5+ letras, sem as comuns)."""
    return {p for p in _plano(texto).split()
            if len(p) >= 5 and p not in _COMUNS and not p.isdigit()}


def e_continuacao(texto: str) -> bool:
    """A mensagem tem forma de continuacao ou de resposta ("e confira no
    celular", "agora faca Y tambem", "ja loguei", "pode ligar")."""
    plano = _plano(texto)
    return bool(_CONTINUA.match(plano) or _INFORMA.search(plano))


def ler_desfecho(resposta: str) -> dict:
    """O desfecho da resposta final: {"tipo", "motivo", "fonte", "aviso"}.

    tipo: feito | bloqueado | falhou. fonte: "linha" (a marca DESFECHO, a
    ultima vale), "heuristica" (sem a marca, achou frase de bloqueio), "vazia"
    (terminou sem dizer nada: nao da para saber se fez) ou "sem_linha".
    aviso: o "feito" que o proprio texto desmente ("Nao foi possivel ligar" +
    "DESFECHO: feito", ou "feito parcialmente — faltou o teste"); quem decide
    o que fazer com ele e o `_encerrar` (com codigo: entregue com aviso; sem
    codigo: esperando voce)."""
    texto = str(resposta or "")
    marcas = list(_MARCA_DESFECHO.finditer(texto))
    if marcas:
        marca = marcas[-1]
        tipo = marca.group(1).lower()
        motivo = marca.group(2).strip(" \t*_`—–-:")
        aviso = ""
        if tipo == "feito":
            if motivo and _FEITO_COM_RESSALVA.search(_sem_acento(motivo)):
                aviso = "feito " + motivo
            else:
                aviso = " · ".join(_frases_de_bloqueio(texto))
            motivo = ""
        return {"tipo": tipo, "motivo": motivo[:300], "fonte": "linha", "aviso": aviso[:300]}
    if not texto.strip():
        return {"tipo": "bloqueado", "fonte": "vazia", "aviso": "",
                "motivo": "o trabalhador terminou sem resposta (não dá para saber se fez)"}
    achadas = _frases_de_bloqueio(texto)
    if achadas:
        return {"tipo": "bloqueado", "motivo": " · ".join(achadas)[:300], "fonte": "heuristica",
                "aviso": ""}
    return {"tipo": "feito", "motivo": "", "fonte": "sem_linha", "aviso": ""}


def arquivos_de_codigo(ficha: dict) -> int:
    """Quantos arquivos de CODIGO a entrega mudou (o rascunho resposta.md e o
    .permissao.json nao contam: o diff do cb44cd52 tinha "1 arquivo", que era
    o resposta.md)."""
    ficha = ficha if isinstance(ficha, dict) else {}
    aplicado = ficha.get("aplicado")
    if aplicado:
        lista = aplicado.get("arquivos") if isinstance(aplicado, dict) else None
        return len([a for a in lista or [] if not _RASCUNHO.search(str(a))]) or 1
    diff = ficha.get("diff") if isinstance(ficha.get("diff"), dict) else {}
    arquivos = diff.get("arquivos")
    if isinstance(arquivos, list):
        nomes = [a.get("caminho") if isinstance(a, dict) else a for a in arquivos]
        return len([n for n in nomes if not _RASCUNHO.search(str(n or ""))])
    try:
        total = int(arquivos or 0)
    except (TypeError, ValueError):
        total = 0
    rascunhos = sum(1 for a in diff.get("avisos") or []
                    if "(entrou):" in str(a)
                    and _RASCUNHO.search(str(a).rpartition("(entrou):")[2].strip()))
    return max(0, total - rascunhos)


def _segundos_desde(iso, agora):
    try:
        return (agora - datetime.fromisoformat(str(iso))).total_seconds()
    except (TypeError, ValueError):
        return None


def _aprovado(resposta: str) -> bool:
    """O veredito e a PRIMEIRA palavra-chave: "APROVADO, nenhum defeito"
    aprova; "DEFEITOS: ... depois de corrigir fica APROVADO" nao."""
    texto = str(resposta or "").upper()
    sim, nao = texto.find("APROVADO"), texto.find("DEFEITO")
    return sim >= 0 and (nao < 0 or sim < nao)


def _id_conferente(trabalhador: str) -> str:
    # o MESMO id do gerente da equipe (`equipe._conferir_aplicadas`): se o
    # gerente estiver ligado, ele ve que a conferencia ja existe e nao duplica
    from .equipe import _id
    return _id("conf-" + trabalhador)


def _num(valor):
    try:
        return None if valor is None else float(valor)
    except (TypeError, ValueError):
        return None


def _hora(epoch) -> str:
    try:
        return datetime.fromtimestamp(float(epoch)).strftime("%d/%m %H:%M")
    except (TypeError, ValueError, OSError, OverflowError):
        return "?"


def _texto_da_resposta(ref, rotulo, descricao="", comentario="", *, ja_dada=False):
    """A resposta do Adrian no Grimorio, como continuacao do pedido."""
    return ((f"O Adrian já tinha decidido no Grimório ({ref}): vale «{rotulo or '?'}»"
             if ja_dada else f"Resposta do Adrian no Grimório ({ref}): escolheu «{rotulo or '?'}»")
            + (f" — {descricao}" if descricao else "")
            + (f"\nComentário dele: {comentario}" if comentario else ""))


_BLOCO_EVENTOS = 256_000
_TETO_EVENTOS = 64_000_000


def _rodada_mais_nova(caminho):
    """O fim do eventos.jsonl a partir do ULTIMO `delegar.inicio`: (texto, tamanho).

    05/10/2026: ler so os ultimos 256 KB perdia o inicio das rodadas longas
    (vila-inventario 1751 KB, pedidos-app 1342 KB), e o `inicio_n` ficava None.
    Le de tras para frente, em blocos, ate achar o inicio (ou o comeco do arquivo)."""
    with open(caminho, "rb") as fh:
        fh.seek(0, 2)
        tamanho = fh.tell()
        pos, bruto = tamanho, b""
        while pos > 0 and len(bruto) < _TETO_EVENTOS:
            passo = min(_BLOCO_EVENTOS, pos)
            pos -= passo
            fh.seek(pos)
            bruto = fh.read(passo) + bruto
            if b'"delegar.inicio"' in bruto:
                break
    return bruto.decode("utf-8", "replace"), tamanho


# ------------------------------------------------------------ lista branca
def _grade():
    try:
        from builds import grade
        return tuple(grade.GRADE)
    except Exception:                                         # noqa: BLE001
        return ((0, 37), (6, 37), (9, 37), (12, 7), (15, 37), (17, 57),
                (20, 37), (21, 37), (22, 37), (23, 37))


def na_janela_das_postagens(agora: datetime) -> bool:
    """De 12 min antes a 18 min depois de um post, nada pesado comeca."""
    for dia in (-1, 0, 1):
        base = (agora + timedelta(days=dia)).replace(second=0, microsecond=0)
        for hora, minuto in _grade():
            post = base.replace(hour=hora, minute=minuto)
            if (post - timedelta(minutes=JANELA_ANTES_MIN) <= agora
                    <= post + timedelta(minutes=JANELA_DEPOIS_MIN)):
                return True
    return False


def _publica(argv) -> str:
    """O pedaco do comando que publicaria, ou ''. Nenhuma acao publica."""
    for parte in argv:
        baixo = str(parte).lower()
        for proibido in _PUBLICA:
            if proibido in baixo:
                return str(parte)
    return ""


def _argumentos_validos(nome, modelo, argumentos) -> list:
    argumentos = [str(a) for a in argumentos if str(a).strip()]
    padroes = list(modelo.get("parametros") or [])
    if len(argumentos) != len(padroes):
        raise ValueError(f"{nome} recebe {len(padroes)} argumento(s), vieram {len(argumentos)}")
    for valor, padrao in zip(argumentos, padroes):
        if not re.fullmatch(padrao, valor):
            raise ValueError(f"argumento inválido para {nome}: {valor!r}")
    return argumentos


def acao_do_servidor(nome: str, argumentos=()) -> tuple:
    """(a funcao, os argumentos) de uma acao de estado do servidor, ou ValueError."""
    nome = str(nome or "").strip().lower()
    modelo = ACOES_SERVIDOR.get(nome)
    if modelo is None:
        raise ValueError(f"“{nome}” não é ação do servidor ({', '.join(sorted(ACOES_SERVIDOR))})")
    argumentos = _argumentos_validos(nome, modelo, argumentos)
    if _publica([nome, *argumentos, modelo["fazer"]]):
        raise ValueError(f"{nome} publicaria: o servidor nunca publica")
    return globals()[modelo["fazer"]], argumentos


def marca_executar(resposta: str):
    """(nome, argumentos) da marca EXECUTAR, so se ela for a ULTIMA linha nao
    vazia (uma linha DESFECHO depois dela e tolerada), ou None.

    05/10/2026 (conferente): a primeira linha EXECUTAR em qualquer ponto
    disparava; um exemplo no meio da resposta ("EXECUTAR: `gerente ligar`")
    ligava o gerente."""
    linhas = [x for x in str(resposta or "").splitlines() if x.strip()]
    while linhas and _MARCA_DESFECHO.match(linhas[-1]):
        linhas.pop()
    marca = _MARCA_EXECUTAR.match(linhas[-1]) if linhas else None
    if not marca:
        return None
    return marca.group(1).lower(), marca.group(2).split()


# O que o Adrian precisa ter citado no pedido para a acao de estado valer.
# 05/10/2026 (conferente): qualquer trabalhador, de qualquer pedido, podia
# terminar com "EXECUTAR: paralelo 8" e o pulso executava -- furando "um
# projeto por vez" e o controle de capacidade, que e dele.
_OBJETO_DA_ACAO = {
    "gerente": ("o gerente", re.compile(r"\bgerente\b")),
    "paralelo": ("o paralelo", re.compile(
        r"\b(?:paralel\w*|simultane\w*|ao mesmo tempo|um por vez|capacidade)\b")),
    "renovacao": ("a renovação", re.compile(r"\brenov\w*")),
}


_NAO_E_ESCOLHA = re.compile(r"^(?:Pergunta|Contexto do nó)\s*:|^APLIQUE a escolha")


def _o_que_ele_escolheu(texto: str) -> str:
    """Do texto do Adrian, so o que ELE disse: o pedido do Grimorio traz a
    pergunta e o contexto do no (escritos por quem criou o no; o do cb44cd52
    fala em "paralelo"), que nao autorizam nada."""
    return "\n".join(x for x in str(texto or "").splitlines() if not _NAO_E_ESCOLHA.match(x))


def autorizada_pelo_adrian(nome: str, argumentos, texto_do_adrian: str) -> str:
    """'' se o texto do Adrian pede esta acao de estado; senao, o porque."""
    objeto, padrao = _OBJETO_DA_ACAO.get(nome, (nome, None))
    plano = _plano(_o_que_ele_escolheu(texto_do_adrian))
    if padrao is None or not padrao.search(plano):
        return f"você não pediu nada sobre {objeto} neste pedido"
    if nome == "gerente":
        palavras = plano.split()
        desligar = any(p.startswith(("deslig", "desativ")) for p in palavras)
        ligar = any(p.startswith(("lig", "ativ", "religa")) for p in palavras)
        quer = (list(argumentos) or [""])[0]
        if quer == "ligar" and desligar and not ligar:
            return "você pediu para DESLIGAR o gerente"
        if quer == "desligar" and ligar and not desligar:
            return "você pediu para LIGAR o gerente"
    return ""


_MARCAS_DO_SERVIDOR = re.compile(r"\n\n(?:O servidor recusou `EXECUTAR|Resultado de `EXECUTAR|"
                                 r"O nó `|O servidor executou)")


def texto_do_adrian(pedido: dict) -> str:
    """So o que o ADRIAN escreveu no pedido (o `texto` tambem leva o que o
    servidor devolve ao trabalhador, como a lista de acoes de uma recusa)."""
    do = pedido.get("do_adrian")
    if isinstance(do, list) and do:
        return "\n".join(str(x) for x in do)
    return _MARCAS_DO_SERVIDOR.split(str(pedido.get("texto") or ""))[0]


def _anotar_do_adrian(pedido: dict, texto: str) -> None:
    do = pedido.get("do_adrian")
    if not isinstance(do, list):
        do = [texto_do_adrian(pedido)] if pedido.get("texto") else []
    do.append(str(texto)[:2000])
    pedido["do_adrian"] = do[-20:]


def _servidor_gerente(argumentos) -> str:
    from remoto import delegar
    ligar = argumentos[0] == "ligar"
    delegar.gravar_config({"gerente_ligado": ligar})
    lido = delegar.ler_config().get("gerente_ligado")
    if lido is not ligar:
        raise RuntimeError(f"gravei gerente_ligado={ligar}, mas o config relido diz {lido!r}")
    return (f"gerente da equipe {'LIGADO' if ligar else 'DESLIGADO'} (relido em "
            f"delegados/config.json: gerente_ligado = {str(lido).lower()})")


def _servidor_renovacao(argumentos) -> str:
    from remoto import delegar
    turnos, minutos = int(argumentos[0]), int(argumentos[1])
    delegar.gravar_config({"renovar_apos_turnos": turnos, "renovar_apos_min": minutos})
    lido = delegar.ler_config()
    if (lido.get("renovar_apos_turnos"), lido.get("renovar_apos_min")) != (turnos, minutos):
        raise RuntimeError(f"gravei {turnos} turnos/{minutos} min, mas o config relido diz "
                           f"{lido.get('renovar_apos_turnos')}/{lido.get('renovar_apos_min')}")
    return (f"renovação a cada {turnos} turnos ou {minutos} min (relido em "
            "delegados/config.json)")


def _servidor_paralelo(argumentos) -> str:
    """Pela Mesa (a fonte do paralelo, com o historico e o no do Grimorio), e
    espelhado no despachante: gravar so o delegados/config.json seria desfeito
    na proxima mudanca da Mesa."""
    from remoto import delegar, orquestrador
    n = int(argumentos[0])
    orquestrador.capacidade([("modo", "um_por_vez" if n == 1 else "paralelo"),
                             ("max_paralelo", n)], fonte="app",
                            porque="pedido do Adrian, executado pelo servidor")
    orquestrador._espelhar_no_despachante("max_paralelo")
    efetivo = orquestrador.paralelo_efetivo(orquestrador.ler_config())
    despachante = int(delegar.ler_config().get("delegados_paralelo") or 1)
    if efetivo != n or despachante != n:
        raise RuntimeError(f"pedi {n}, mas relido: a Mesa diz {efetivo} e o despachante {despachante}")
    return f"até {n} trabalhador(es) ao mesmo tempo (relido na Mesa e no despachante)"


def montar_acao(nome: str, argumentos=()) -> dict:
    """A acao da lista branca pronta para rodar, ou ValueError com o porque."""
    nome = str(nome or "").strip().lower()
    modelo = ACOES_REPO.get(nome)
    if modelo is None:
        raise ValueError(f"“{nome}” não está na lista branca "
                         f"({', '.join(sorted({**ACOES_REPO, **ACOES_SERVIDOR}))})")
    argumentos = _argumentos_validos(nome, modelo, argumentos)
    argv = []
    for parte in modelo["argv"]:
        for i, valor in enumerate(argumentos, start=1):
            parte = parte.replace("{" + str(i) + "}", valor)
        argv.append(parte)
    publica = _publica(argv)
    if publica:
        raise ValueError(f"{nome} publicaria ({publica}): o executor nunca publica")
    cwd = (RAIZ / modelo.get("cwd", ".")).resolve()
    return {"nome": nome, "argv": argv, "cwd": str(cwd),
            "timeout_s": int(modelo.get("timeout_s") or 600),
            "janela": bool(modelo.get("janela", True)), "env": dict(modelo.get("env") or {}),
            "o_que": modelo.get("o_que", "")}


def _gravar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name("." + caminho.name + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    os.replace(temporario, caminho)


def executar_no_fundo(acao: dict, pasta: Path) -> threading.Thread:
    """Roda a acao numa thread: `saida.txt` ao vivo e `resultado.json` no fim.

    O pulso nao espera: ele le o `resultado.json` nas passadas seguintes."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)

    def correr():
        inicio = time.monotonic()
        resultado = {"codigo": None, "estourou": False, "erro": ""}
        env = dict(os.environ, PYTHONIOENCODING="utf-8", **(acao.get("env") or {}))
        try:
            with open(pasta / "saida.txt", "wb") as saida:
                feito = subprocess.run(acao["argv"], cwd=acao["cwd"], stdout=saida,
                                       stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                       timeout=acao["timeout_s"], env=env,
                                       creationflags=NO_WINDOW)
            resultado["codigo"] = feito.returncode
        except subprocess.TimeoutExpired:
            resultado["estourou"] = True
        except (OSError, ValueError) as exc:
            resultado["erro"] = f"{type(exc).__name__}: {exc}"[:300]
        resultado["dur_s"] = round(time.monotonic() - inicio, 1)
        try:
            _gravar_json(pasta / "resultado.json", resultado)
        except OSError:
            pass

    fio = threading.Thread(target=correr, name="executor-" + acao.get("nome", "acao"),
                           daemon=True)
    fio.start()
    return fio


def _lista_de_acoes() -> str:
    linhas = []
    for nome, acao in sorted({**ACOES_REPO, **ACOES_SERVIDOR}.items()):
        params = " ".join(f"<{p}>" for p in acao.get("parametros") or [])
        linhas.append(f"- `EXECUTAR: {nome}{(' ' + params) if params else ''}`: {acao.get('o_que', '')}")
    return "\n".join(linhas)


_COMO_RESPONDER = (
    "# Como responder (o servidor lê só a sua mensagem final)\n\n"
    "- Responda na sua mensagem final, curta, com o que foi feito e a prova. "
    "NÃO crie arquivo resposta.md (nem outro rascunho) na worktree: isto vale acima de "
    "qualquer instrução antiga do cargo, e uma marca (GRIMÓRIO, EXECUTAR) escrita num "
    "arquivo se perde.\n"
    "- Se faltar uma decisão do Adrian, não pergunte solto: escreva `.permissao.json` com a "
    "categoria `decisao_de_produto` (o servidor cria o nó no Grimório) e termine. A resposta "
    "dele volta a ESTE pedido como continuação. Se o nó já existe no Grimório do repositório "
    "principal, termine com a linha `GRIMÓRIO: <projeto>/<id>`.\n"
    "- Se precisar rodar algo no repositório real (fora da worktree), termine com UMA linha "
    "`EXECUTAR: <nome>` desta lista branca; o servidor roda, fora da janela das postagens, "
    "e devolve a saída a você. Nada fora da lista roda, e nada publica.\n"
    "- O ESTADO do servidor (`%LOCALAPPDATA%`: gerente, renovação, paralelo) a worktree NÃO "
    "grava. Não tente e não peça permissão para isso: termine com `EXECUTAR: gerente ligar` "
    "(ou `renovacao`, `paralelo`) e o próprio servidor grava, relê para conferir e responde "
    "ao Adrian. Só vale se o ADRIAN pediu isso neste pedido; a marca vale apenas na ÚLTIMA "
    "linha (no meio do texto, como exemplo, ela não roda).\n"
    + _lista_de_acoes() + "\n"
    "- A ÚLTIMA linha da mensagem final é o desfecho, num destes formatos:\n"
    "  `DESFECHO: feito` (fez e conferiu)\n"
    "  `DESFECHO: bloqueado — <o que falta e quem faz>` (ex.: falta o Adrian entrar na conta)\n"
    "  `DESFECHO: falhou — <motivo>`\n"
    "  Sem ela o servidor não marca o pedido como entregue. Quem termina com EXECUTAR ou "
    "GRIMÓRIO não precisa dela.\n")


class MesaPedidos:
    """Entrada, acompanhamento e retomada, com dependencias injetaveis."""

    def __init__(self, *, despachante=None, claude=None, relogio=_agora, avisar=None,
                 uso=None, executor=None, diario=None):
        if despachante is None or claude is None:
            from remoto import claude_estado, delegar
            despachante = despachante or delegar
            claude = claude or claude_estado
        self.despachante = despachante
        self.claude = claude
        self.relogio = relogio
        self.avisar = avisar or (lambda _texto: None)
        # quem le as respostas do Grimorio: (leitor, marcar, carregar). Desligado por
        # padrao -- teste nunca le nem marca o Grimorio real; o MESA de producao liga.
        self.grimorio = None
        self.uso = uso
        # a acao da lista branca (lacuna 3): `executor(acao, pasta)` volta na
        # hora; o resultado chega em `pasta/resultado.json`
        self.executor = executor or executar_no_fundo
        # o diario (atividade.jsonl): desligado por padrao -- teste nunca
        # escreve no diario real; o MESA de producao liga (`_ligar_producao`)
        self.diario = diario

    # ------------------------------------------------------------ entrada
    def registrar(self, texto, origem="app", *, novo=False):
        """Guarda o pedido (ou a continuacao) e volta na hora: quem contrata,
        corrige e retoma e o `passo`, no pulso do coordenador."""
        texto = str(texto or "").strip()
        if not texto:
            raise ValueError("pedido vazio")
        if origem not in ("app", "telegram", "grimorio"):
            raise ValueError("origem desconhecida")
        with _TRAVA:
            dados = _ler()
            if e_conversa_solta(texto):
                # nem continuacao nem trabalhador: o retrato, na hora (e o
                # "novo assunto" pedido antes continua valendo para o proximo)
                return self._responder_conversa(dados, texto, origem)
            if dados.pop("novo_assunto", False):
                novo = True
            atual = None if novo else self._continua_qual(dados, texto)
            if atual:
                _anotar_do_adrian(atual, texto)
                atual["texto"] += "\n\nContinuação do Adrian:\n" + texto
                atual["ultima_continuacao"] = texto
                atual["continuar"] = True
                atual["atualizado_em"] = _iso()
                atual["mensagens"] = int(atual.get("mensagens") or 1) + 1
                _linha(dados, atual, texto, de="adrian", origem=origem, tipo="pedido")
                _linha(dados, atual, "continuação recebida; vai ao mesmo orquestrador")
                _gravar(dados)
                return dict(atual, continuacao=True)
            ident = "pedido-" + uuid.uuid4().hex[:8]
            agora = _iso()
            pedido = {"id": ident, "texto": texto, "origem": origem, "situacao": "recebido",
                      "motivo": "", "trabalhador": None, "conferente": None, "ia": None,
                      "contratos": 0, "criado_em": agora, "atualizado_em": agora,
                      "ultimo_evento_em": agora, "mensagens": 1, "do_adrian": [texto[:2000]]}
            dados["pedidos"].append(pedido)
            dados["pedidos"] = dados["pedidos"][-100:]
            _linha(dados, pedido, texto, de="adrian", origem=origem, tipo="pedido")
            _linha(dados, pedido, "recebido; procurando um orquestrador")
            _gravar(dados)
        return dict(pedido, continuacao=False)

    @staticmethod
    def _continua_qual(dados, texto):
        """O pedido de que a mensagem e continuacao, ou None (pedido novo).

        05/10/2026 (conferente): "Faz o backup das fotos", com o cd2e5e0c
        parado no login do Drive, virava continuacao dele e o "destravava".
        Pedido ATIVO (trabalhando, em espera, executando, no limite) recebe a
        mensagem como antes; "entregue" e "esperando voce" so a que responde a
        ele: a que cita uma palavra dele ("ja loguei no Drive" vai ao do Drive,
        mesmo que outro seja mais novo) ou, no mais novo, a que tem forma de
        continuacao ("e confira no celular", "agora faca Y tambem", "pode")."""
        vivos = [p for p in reversed(dados["pedidos"]) if p.get("situacao") in VIVOS]
        if not vivos:
            return None
        minhas = _palavras(texto)
        for pedido in vivos:
            if (pedido.get("situacao") in _AGUARDAM_RESPOSTA and minhas
                    and minhas & _palavras(texto_do_adrian(pedido) + "\n"
                                           + str(pedido.get("motivo") or ""))):
                return pedido
        novo = vivos[0]
        if novo.get("situacao") not in _AGUARDAM_RESPOSTA or e_continuacao(texto):
            return novo
        return None

    def _retrato(self, dados) -> str:
        """O que o servidor esta fazendo, medido do pedidos.json."""
        agora = self.relogio()
        vivos = [p for p in dados["pedidos"] if p.get("situacao") in VIVOS]
        linhas = [f"Retrato do servidor ({agora:%H:%M}): "
                  + (f"{len(vivos)} pedido(s) aberto(s)." if vivos else "nenhum pedido aberto.")]
        for p in vivos[-8:]:
            titulo = (str(p.get("texto") or "").strip().splitlines() or [""])[0][:90]
            motivo = str(p.get("motivo") or "").strip()
            linhas.append(f"- {p['id']} ({_ROTULO.get(p.get('situacao'), p.get('situacao'))}): "
                          f"{titulo}" + (f" — {motivo[:160]}" if motivo else ""))
        encerrados = [p for p in dados["pedidos"] if p.get("situacao") in FINAIS][-3:]
        if encerrados:
            linhas.append("Últimos encerrados: " + "; ".join(
                f"{p['id']} {_ROTULO.get(p.get('situacao'), p.get('situacao'))}"
                for p in encerrados))
        if any(p.get("situacao") == "esperando_voce" for p in vivos):
            linhas.append("Os que esperam você andam quando você responder no próprio pedido "
                          "(ou no Grimório).")
        return "\n".join(linhas)

    def _responder_conversa(self, dados, texto, origem):
        ident = "pedido-" + uuid.uuid4().hex[:8]
        agora = _iso()
        retrato = self._retrato(dados)
        pedido = {"id": ident, "texto": texto, "origem": origem, "situacao": "respondido",
                  "motivo": "", "trabalhador": None, "conferente": None, "ia": None,
                  "contratos": 0, "criado_em": agora, "atualizado_em": agora,
                  "ultimo_evento_em": agora, "mensagens": 1, "conversa": True,
                  "resposta": retrato[:2000]}
        dados["pedidos"].append(pedido)
        dados["pedidos"] = dados["pedidos"][-100:]
        _linha(dados, pedido, texto, de="adrian", origem=origem, tipo="pedido")
        _linha(dados, pedido, retrato, tipo="final", limite=2000)
        _gravar(dados)
        if origem == "telegram":
            self.avisar("🧭 " + retrato[:1500])
        return dict(pedido, continuacao=False)

    def novo_assunto(self, origem="app"):
        """O proximo pedido abre outro orquestrador (botao do app, /novo)."""
        with _TRAVA:
            dados = _ler()
            dados["novo_assunto"] = True
            dados["conversa"].append({"id": uuid.uuid4().hex[:12], "em": _iso(),
                                      "pedido": None, "de": "orquestrador",
                                      "origem": origem, "tipo": "progresso",
                                      "texto": "novo assunto: o próximo pedido abre "
                                               "outro orquestrador"})
            _gravar(dados)

    # ------------------------------------------------------------ guardas
    def _motivo_claude(self):
        try:
            motivo = str(self.claude.motivo_proibido() or "")
        except Exception as exc:  # nao perde pedido se o interruptor estiver ilegivel
            return "não consegui ler o interruptor do Claude (" + type(exc).__name__ + ")"
        if motivo:
            return motivo
        uso = self._ler_uso()
        if uso and uso.get("passou_teto"):
            # 05/10/2026: a semana em 100% tambem conta (orquestrador.ler_uso)
            detalhe = str(uso.get("motivo_teto") or "")
            if uso.get("renova_em"):
                detalhe += (", " if detalhe else "") + "renova " + _hora(uso["renova_em"])
            return "o Claude passou do teto de uso da Mesa" + (f" ({detalhe})" if detalhe else "")
        return ""

    def _ler_uso(self):
        try:
            if self.uso is not None:
                return self.uso() or {}
            from remoto import orquestrador
            return orquestrador.ler_uso() or {}
        except Exception:                                     # noqa: BLE001
            return None

    # ------------------------------------------------------------ limite
    def _queda_por_limite(self, ident):
        """A ULTIMA rodada do trabalhador caiu no limite do Claude?

        04/10/2026: cb44cd52 e cd2e5e0c cairam 5 vezes com "o codex saiu com
        codigo 1"; o resposta.md dizia "You've hit your weekly limit" e cada
        retomada (a cada 120 s) queimava uma das 5. Devolve {"motivo",
        "renova_em", "inicio_n"} ou None."""
        if not ident:
            return None
        try:
            bruto, tamanho = _rodada_mais_nova(self.despachante.pasta_da(ident) / "eventos.jsonl")
        except (OSError, AttributeError, TypeError):
            bruto = None
        if bruto is None:
            texto = self._resposta(ident).lower()
            if "hit your" in texto and "limit" in texto:
                # a chave nunca e None: None == None fazia toda queda nova
                # parecer "ja liberada"
                try:
                    marca = int((self.despachante.pasta_da(ident) / "resposta.md").stat().st_mtime)
                except (OSError, AttributeError, TypeError):
                    marca = 0
                return {"motivo": "o Claude bateu no limite de uso", "renova_em": None,
                        "inicio_n": f"resposta@{marca}"}
            return None
        eventos, inicio_n = [], None
        for linha in bruto.splitlines():
            try:
                registro = json.loads(linha)
            except ValueError:
                continue
            ev = registro.get("ev") if isinstance(registro, dict) else None
            if not isinstance(ev, dict):
                continue
            if ev.get("type") == "delegar.inicio":
                eventos, inicio_n = [], registro.get("n")
                continue
            eventos.append(ev)
        achou, renova, texto, tipo = False, None, "", ""
        for ev in eventos:
            if ev.get("type") == "rate_limit_event":
                info = ev.get("rate_limit_info") or {}
                if str(info.get("status") or "").lower() == "rejected":
                    achou = True
                    renova = _num(info.get("resetsAt")) or renova
                    tipo = str(info.get("rateLimitType") or tipo)
            elif ev.get("type") == "result" and ev.get("is_error"):
                resultado = str(ev.get("result") or "")
                if (ev.get("api_error_status") == 429
                        or any(f in resultado.lower() for f in _FRASES_DE_LIMITE)):
                    achou, texto = True, resultado.strip()[:160]
        if not achou:
            return None
        motivo = texto or ("o Claude recusou por limite" + (f" ({tipo})" if tipo else ""))
        if inicio_n is None:            # arquivo sem `delegar.inicio`: o tamanho marca a rodada
            inicio_n = f"tam@{tamanho}"
        return {"motivo": motivo, "renova_em": renova, "inicio_n": inicio_n}

    def _queda_nova(self, pedido, ident):
        """A queda por limite que ainda nao foi liberada (a mesma rodada velha,
        ja liberada, nao prende o pedido de novo)."""
        queda = self._queda_por_limite(ident)
        if queda is None:
            return None
        if ("limite_liberado_n" in pedido
                and queda.get("inicio_n") == pedido["limite_liberado_n"]):
            return None
        return queda

    def _parar_por_limite(self, dados, pedido, queda):
        """Queda por limite NAO gasta retomada: o pedido para e volta sozinho
        quando o uso liberar. Pedido de construir vai ao Codex na hora."""
        if _construir(pedido["texto"]):
            pedido.update(trabalhador=None, contratos=int(pedido.get("contratos") or 0) + 1,
                          tentou_em=None, ia_forcada="codex", continuar=False,
                          continuar_em=None)
            self._esperar(dados, pedido, "o Claude bateu no limite (" + queda["motivo"][:120]
                          + "); o Codex assume")
            return
        renova = queda.get("renova_em")
        motivo = ("o Claude bateu no limite: " + queda["motivo"][:140]
                  + (f"; renova {_hora(renova)}" if renova else "")
                  + "; volta sozinho quando o uso liberar")
        mudou = pedido.get("situacao") != "parado_limite"
        pedido.update(situacao="parado_limite", motivo=motivo, limite_renova_em=renova,
                      limite_n=queda.get("inicio_n"), atualizado_em=_iso())
        if mudou:
            _linha(dados, pedido, "parado no limite (não gasta retomada): " + motivo)

    def _limite_liberou(self, pedido):
        renova = _num(pedido.get("limite_renova_em"))
        if renova is not None and self.relogio().timestamp() >= renova:
            return True
        uso = self._ler_uso()
        return bool(uso) and uso.get("situacao") == "ok" and not uso.get("passou_teto")

    def _cuidar_do_limite(self, dados, pedido):
        if pedido.get("continuar") and not self._limite_liberou(pedido):
            # 05/10/2026: a mensagem nova do Adrian ficava presa atras do
            # limite (podia ser dias, ate a semana renovar). Ele esta
            # esperando agora: o Codex assume com o pedido inteiro.
            ficha = self._estado_do(pedido.get("trabalhador")) or {}
            if ficha.get("ia") != "codex":
                pedido.update(situacao="esperando", motivo="", trabalhador=None,
                              contratos=int(pedido.get("contratos") or 0) + 1,
                              tentou_em=None, ia_forcada="codex", continuar=False,
                              continuar_em=None, limite_liberado_n=pedido.get("limite_n"),
                              atualizado_em=_iso())
                _linha(dados, pedido, "mensagem nova com o Claude no limite: o Codex assume "
                                      "agora, com o pedido inteiro")
                return
        if not self._limite_liberou(pedido):
            return
        pedido.update(situacao="esperando", motivo="", tentou_em=None,
                      limite_liberado_n=pedido.get("limite_n"), atualizado_em=_iso())
        _linha(dados, pedido, "o limite do Claude liberou; o pedido volta a andar")

    def _esperar(self, dados, pedido, motivo):
        """Em espera com o motivo, sem repetir a mesma linha a cada pulso."""
        motivo = str(motivo or "?")[:240]
        mudou = pedido.get("situacao") != "esperando" or pedido.get("motivo") != motivo
        pedido.update(situacao="esperando", motivo=motivo, atualizado_em=_iso())
        if mudou:
            _linha(dados, pedido, "em espera: " + motivo)

    def _estado_do(self, ident):
        if not ident:
            return None
        try:
            return self.despachante.ler_estado(ident)
        except Exception:
            return None

    def _situacao_do(self, ficha):
        """A situacao da ficha, com "rodando" de pid MORTO lido como "parado".

        05/10/2026 (conferente): o pedido-7c727778 alternou a cada pulso, por
        mais de 2 h, entre "sem evento ha mais de 10 min; parei e vou retomar"
        e "trabalhador de volta": o pid 11412 nao existia, a ficha seguia
        "rodando" e o `delegar.parar` recusa pid morto (nada mudava a ficha).
        O `delegar.rodar` aceita relancar uma ficha assim."""
        situacao = (ficha or {}).get("situacao")
        if situacao == "rodando" and self._pid_morto(ficha):
            return "parado"
        return situacao

    def _pid_morto(self, ficha) -> bool:
        vivo = getattr(self.despachante, "_pid_vivo", None)
        pid = (ficha or {}).get("pid")
        if vivo is None or not pid:
            return False
        try:
            return vivo(pid) is False
        except Exception:                                     # noqa: BLE001
            return False

    def _pode_tentar(self, pedido, chave="tentou_em"):
        """Uma tentativa de retomar a cada RETOMAR_S, nao a cada pulso de 5 s."""
        desde = _segundos_desde(pedido.get(chave), self.relogio())
        return desde is None or desde >= RETOMAR_S

    def _ultimo_sinal(self, ident, ficha):
        """Quando o trabalhador deu sinal de vida pela ultima vez.

        O estado.json so muda no inicio, no fim e por rodada do Codex; numa
        rodada longa do Claude ele fica parado. O eventos.jsonl recebe cada
        evento, entao a hora dele e o sinal de vida de verdade."""
        candidatos = []
        try:
            caminho = self.despachante.pasta_da(ident) / "eventos.jsonl"
            candidatos.append(datetime.fromtimestamp(caminho.stat().st_mtime))
        except (OSError, TypeError, ValueError, AttributeError):
            pass
        for chave in ("atualizado_em", "inicio"):
            try:
                candidatos.append(datetime.fromisoformat(str(ficha.get(chave))))
            except (TypeError, ValueError):
                pass
        return max(candidatos) if candidatos else None

    def _motivo_do_fundo(self, ident):
        """A ultima linha do despachante no fundo (a recusa do `rodar`)."""
        try:
            bruto = (self.despachante.pasta_da(ident) / "fundo.txt").read_bytes()[-2000:]
        except (OSError, AttributeError):
            return ""
        linhas = [x.strip() for x in bruto.decode("utf-8", "replace").splitlines() if x.strip()]
        return linhas[-1][:200] if linhas else ""

    # ------------------------------------------------------------ contratar
    def _contratar(self, dados, pedido):
        if not self._pode_tentar(pedido):
            return
        pedido["tentou_em"] = _iso(self.relogio())
        ia = pedido.get("ia_forcada") or "claude"
        motivo = self._motivo_claude() if ia == "claude" else ""
        if motivo:
            if not _construir(pedido["texto"]):
                self._esperar(dados, pedido, motivo)
                return
            ia = "codex"          # o Codex assume os pedidos de construir
        n = int(pedido.get("contratos") or 0)
        ident = pedido["id"] if n == 0 else f"{pedido['id']}-{n}"
        if self._estado_do(ident) is None:
            caminho = self.despachante.pasta_da(ident) / "pedido.md"
            caminho.parent.mkdir(parents=True, exist_ok=True)
            corpo = ("# PEDIDO do Adrian (" + ("Telegram" if pedido.get("origem") == "telegram"
                                                 else "app") + ")\n\n" + pedido["texto"]
                     + "\n\n" + _COMO_RESPONDER)
            if ia == "codex":
                # o Codex nao recebe o prompt do cargo: vai junto com a tarefa
                try:
                    corpo = self.despachante.prompt_do_cargo("orquestrador") + "\n\n" + corpo
                except Exception:
                    pass
            caminho.write_text(corpo, encoding="utf-8")
            try:
                self.despachante.criar(ident, caminho, PERMITIDOS, ia=ia, cargo="orquestrador",
                                       titulo=pedido["texto"].splitlines()[0][:160])
            except Exception as exc:
                self._esperar(dados, pedido, "contratar: " + str(exc)[:200])
                return
        try:
            self.despachante.no_fundo(["rodar", "--id", ident], ident)
        except Exception as exc:
            pedido.update(trabalhador=ident, ia=ia)
            self._esperar(dados, pedido, "rodar: " + str(exc)[:200])
            return
        pedido.update(trabalhador=ident, ia=ia, situacao="trabalhando", motivo="",
                      continuar=False, atualizado_em=_iso(), ultimo_evento_em=_iso())
        _linha(dados, pedido, f"{ia} orquestrador contratado ({ident}); trabalhando numa worktree")

    # ------------------------------------------------------------ acompanhar
    def _progresso(self, dados, pedido, ident):
        """Os eventos do trabalhador, resumidos, no maximo um por minuto."""
        ler = getattr(self.despachante, "ler_eventos", None)
        if ler is None:
            return
        try:
            lido = ler(ident, desde=int(pedido.get("eventos_offset", -1)))
        except Exception:
            return
        pedido["eventos_offset"] = int(lido.get("offset") or 0)
        uteis = [e for e in lido.get("eventos") or []
                 if e.get("texto") and e.get("tipo") in _VERBO]
        if not uteis:
            return
        desde = _segundos_desde(pedido.get("progresso_em"), self.relogio())
        if desde is not None and desde < PROGRESSO_S:
            return
        e = uteis[-1]
        texto = f"{_VERBO[e['tipo']]}: {str(e['texto']).splitlines()[0][:160]}"
        if texto != pedido.get("progresso"):
            pedido.update(progresso=texto, progresso_em=_iso(self.relogio()))
            _linha(dados, pedido, texto)

    def _acompanhar(self, dados, pedido):
        trabalhador = pedido.get("trabalhador")
        ficha = self._estado_do(trabalhador)
        if not ficha:
            pedido.update(trabalhador=None, contratos=int(pedido.get("contratos") or 0) + 1)
            self._esperar(dados, pedido, "o trabalhador sumiu; vou contratar outro")
            return
        situacao = self._situacao_do(ficha)
        agora = self.relogio()
        if situacao != ficha.get("situacao"):
            # a ficha diz "rodando", mas o processo morreu: retoma de verdade
            # (sem chamar `parar`, que recusa pid morto)
            self._esperar(dados, pedido, f"o processo do trabalhador (pid {ficha.get('pid')}) "
                                         "morreu com a ficha em 'rodando'; vou retomar")
            return
        if situacao == "rodando":
            if pedido.get("continuar") and pedido.get("continuar_em"):
                pedido.update(continuar=False, continuar_em=None, motivo="")
            sinal = self._ultimo_sinal(trabalhador, ficha)
            if sinal is not None:
                pedido["ultimo_evento_em"] = sinal.isoformat(timespec="seconds")
            self._progresso(dados, pedido, trabalhador)
            if sinal is not None and (agora - sinal).total_seconds() >= SEM_EVENTO_S:
                try:
                    self.despachante.parar(trabalhador)
                except Exception:
                    pass
                pedido["tentou_em"] = _iso(agora)
                self._esperar(dados, pedido, "trabalhador sem evento há mais de 10 min; "
                                             "parei e vou retomar")
            return
        if situacao == "criado":
            # o `rodar` no fundo ainda nao comecou, ou foi recusado (paralelo,
            # janela da postagem): da um prazo e mostra o porque
            desde = _segundos_desde(pedido.get("tentou_em") or pedido.get("atualizado_em"), agora)
            if desde is not None and desde >= RETOMAR_S:
                self._esperar(dados, pedido, self._motivo_do_fundo(trabalhador)
                              or "o trabalhador não começou")
            return
        queda = self._queda_nova(pedido, trabalhador) if situacao in ("terminou", "falhou",
                                                                      "parado") else None
        if queda:
            self._parar_por_limite(dados, pedido, queda)
            return
        if situacao == "terminou":
            self._entregue(dados, pedido, ficha)
            return
        if situacao == "aguardando_permissao" and self._permissao_vira_grimorio(dados, pedido, ficha):
            return
        self._esperar(dados, pedido, str(ficha.get("motivo") or situacao))

    # ------------------------------------------------------------ Grimorio
    def _permissao_vira_grimorio(self, dados, pedido, ficha):
        """A permissao `decisao_de_produto` ja virou no no Grimorio (o delegar
        cria): o pedido espera a resposta DELE, com a referencia do no."""
        pp = ficha.get("pedido_permissao") or {}
        if pp.get("categoria") != "decisao_de_produto" or not pp.get("decisao_id"):
            return False
        self._esperar_grimorio(dados, pedido, f"geral/{pp['decisao_id']}", "permissao",
                               pp.get("o_que") or "")
        return True

    def _esperar_grimorio(self, dados, pedido, ref, via, o_que=""):
        mudou = (pedido.get("situacao") != "esperando_voce"
                 or pedido.get("grimorio_ref") != ref)
        pedido.update(situacao="esperando_voce", grimorio_ref=ref, grimorio_via=via,
                      motivo=f"esperando a decisão do Adrian no Grimório ({ref})"
                             + (f": {o_que[:160]}" if o_que else ""),
                      atualizado_em=_iso())
        if mudou:
            _linha(dados, pedido, "em espera: " + pedido["motivo"])
            if via != "permissao":       # a permissao o gerente ja avisa
                self.avisar(f"❓ Um pedido espera a sua decisão no Grimório: {ref}")

    def _no_do_grimorio(self, ref):
        """O no da referencia: {} se nao existe, None se nao da para conferir
        (Grimorio desligado ou ilegivel)."""
        if self.grimorio is None:
            return None
        try:
            itens = self.grimorio[2]() or {}
        except Exception:                                     # noqa: BLE001
            return None
        return itens.get(str(ref).rpartition("/")[2]) or {}

    def _vigente_ja_lida(self, ref, no):
        """A resposta vigente do no, se ele JA respondeu e ela ja foi lida (a
        nao lida o `ler_grimorio` entrega no pulso seguinte)."""
        vigente = no.get("vigente") or {}
        if not vigente.get("opcao"):
            return None
        try:
            pendentes = self.grimorio[0]() or []
        except Exception:                                     # noqa: BLE001
            return None
        item_id = str(ref).rpartition("/")[2]
        if any(e.get("id") == item_id and not e.get("lida") for e in pendentes):
            return None
        return vigente

    def _pedir_ao_grimorio(self, dados, pedido, ref):
        """A marca `GRIMÓRIO: projeto/id`: confere o no ANTES de esperar.

        05/10/2026 (conferente): a marca para um no ja respondido e lido, ou
        para um no que nao existe, prendia o pedido para sempre e mandava ao
        Adrian "espera a sua decisao" sobre o que ele ja tinha decidido.
        Devolve False quando o pedido deve seguir como entrega comum."""
        pedido["grimorio_conferido_em"] = _iso(self.relogio())
        no = self._no_do_grimorio(ref)
        if no is None:
            self._esperar_grimorio(dados, pedido, ref, "resposta")
            return True
        if not no:
            vezes = int(pedido.get("grimorio_sem_no") or 0)
            if vezes >= 2:
                _linha(dados, pedido, f"a marca GRIMÓRIO aponta de novo para {ref}, que não "
                                      "existe; sigo sem esperar")
                return False
            pedido["grimorio_sem_no"] = vezes + 1
            _linha(dados, pedido, f"a marca GRIMÓRIO aponta para {ref}, que não existe no "
                                  "Grimório; devolvi ao trabalhador")
            self._devolver(dados, pedido, (
                f"O nó `{ref}` não existe no Grimório do repositório principal. Para pedir uma "
                "decisão nova, escreva `.permissao.json` com a categoria `decisao_de_produto` "
                "(o servidor cria o nó) e termine; ou siga sem a decisão, dizendo o que assumiu."))
            pedido.update(grimorio_ref=None, grimorio_via=None)
            return True
        ref = f"{no.get('projeto') or ref.rpartition('/')[0]}/{ref.rpartition('/')[2]}"
        vigente = self._vigente_ja_lida(ref, no)
        if vigente:
            opcao = next((o for o in no.get("opcoes") or []
                          if o.get("id") == vigente.get("opcao")), {})
            texto = _texto_da_resposta(ref, opcao.get("rotulo") or vigente.get("opcao"),
                                       opcao.get("descricao"), vigente.get("comentario"),
                                       ja_dada=True)
            _anotar_do_adrian(pedido, texto)
            self._devolver(dados, pedido, texto)
            pedido.update(grimorio_ref=None, grimorio_via=None,
                          mensagens=int(pedido.get("mensagens") or 1) + 1)
            _linha(dados, pedido, texto, de="adrian", origem="grimorio", tipo="pedido")
            _linha(dados, pedido, "o Adrian já tinha decidido; a decisão vigente volta ao "
                                  "mesmo orquestrador")
            return True
        self._esperar_grimorio(dados, pedido, ref, "resposta")
        return True

    def _cuidar_do_grimorio(self, dados, pedido):
        """A permissao foi decidida pelo app (fora do Grimorio), ou o Adrian
        escreveu uma continuacao: segue o fluxo sem esperar o no."""
        if pedido.get("continuar"):
            bloqueado = bool(pedido.get("bloqueio"))
            pedido.update(situacao="esperando", motivo="", grimorio_ref=None,
                          grimorio_via=None, tentou_em=None, bloqueio=None,
                          atualizado_em=_iso())
            _linha(dados, pedido, "a resposta do Adrian destrava o pedido; volta ao mesmo "
                                  "orquestrador" if bloqueado else
                                  "a continuação do Adrian segue sem esperar o Grimório")
            return
        if pedido.get("grimorio_via") == "resposta":
            # o no pode ter sido respondido e lido por outro (a sessao do VS
            # Code), ou sumido: confere de tempos em tempos
            if self._pode_tentar(pedido, "grimorio_conferido_em"):
                if not self._pedir_ao_grimorio(dados, pedido, pedido.get("grimorio_ref") or ""):
                    pedido.update(situacao="esperando", motivo="", grimorio_ref=None,
                                  grimorio_via=None, tentou_em=None, atualizado_em=_iso())
            return
        if pedido.get("grimorio_via") != "permissao":
            return
        ficha = self._estado_do(pedido.get("trabalhador")) or {}
        if ficha and ficha.get("situacao") != "aguardando_permissao":
            pedido.update(situacao="esperando", motivo="", grimorio_ref=None,
                          grimorio_via=None, tentou_em=None, atualizado_em=_iso())
            _linha(dados, pedido, "a permissão foi decidida fora do Grimório; seguindo")

    def _pedido_esperando(self, dados, projeto, item_id):
        for pedido in dados["pedidos"]:
            if pedido.get("situacao") != "esperando_voce":
                continue
            p_proj, _, p_id = str(pedido.get("grimorio_ref") or "").rpartition("/")
            if p_id == item_id and (not projeto or not p_proj or p_proj == projeto):
                return pedido
        return None

    def _retomar_com_resposta(self, ev, no, opcao):
        """A resposta do Adrian volta ao MESMO pedido, como continuacao.

        Lacuna 2 (05/10/2026): cada resposta virava um pedido NOVO, e o
        trabalhador que perguntou ficava parado para sempre."""
        with _TRAVA:
            dados = _ler()
            pedido = self._pedido_esperando(dados, ev.get("projeto"), ev["id"])
            if pedido is None:
                return None
            ref = pedido.get("grimorio_ref")
            texto = _texto_da_resposta(ref, ev.get("opcao_rotulo") or ev.get("opcao"),
                                       opcao.get("descricao"), ev.get("comentario"))
            if pedido.get("grimorio_via") == "permissao":
                # 05/10/2026 (conferente): respondido no app, o api_http JA
                # decidiu a permissao e relancou `retomar`. Decidir de novo
                # dava Recusa e uma rodada `corrigir` a mais, gastando uso.
                ficha = self._estado_do(pedido.get("trabalhador")) or {}
                if ficha and ficha.get("situacao") != "aguardando_permissao":
                    _linha(dados, pedido, f"a permissão ({ref}) já foi decidida no app; o "
                                          "trabalhador segue sem rodada a mais")
                    _gravar(dados)
                    return pedido["id"]    # fica lida; o _cuidar_do_grimorio segue o fluxo
                permitir = str(ev.get("opcao") or "").lower() == "permitir"
                try:
                    self.despachante.decidir_permissao(pedido["trabalhador"], permitir)
                except Exception as exc:                      # noqa: BLE001
                    _linha(dados, pedido, f"não consegui registrar a permissão: {exc}")
            _anotar_do_adrian(pedido, texto)
            pedido["texto"] += "\n\n" + texto
            pedido.update(situacao="esperando", motivo="", continuar=True,
                          ultima_continuacao=texto, continuar_em=None, tentou_em=None,
                          grimorio_ref=None, grimorio_via=None, atualizado_em=_iso(),
                          mensagens=int(pedido.get("mensagens") or 1) + 1)
            _linha(dados, pedido, texto, de="adrian", origem="grimorio", tipo="pedido")
            _linha(dados, pedido, "a resposta do Grimório volta ao mesmo orquestrador")
            _gravar(dados)
            return pedido["id"]

    # ------------------------------------------------------------ executar
    def _pedir_execucao(self, dados, pedido, nome, argumentos):
        """`EXECUTAR: <nome>` na resposta final. Devolve se cuidou do pedido."""
        feitas = int(pedido.get("execucoes") or 0)
        if feitas >= MAX_EXECUCOES:
            _linha(dados, pedido, f"pediu EXECUTAR {nome}, mas já foram {feitas} ações neste "
                                  "pedido; não executo mais")
            return False
        pedido["execucoes"] = feitas + 1
        try:
            acao = montar_acao(nome, argumentos)
        except ValueError as exc:
            _linha(dados, pedido, f"EXECUTAR {nome} recusado: {exc}")
            self._devolver(dados, pedido, f"O servidor recusou `EXECUTAR: {nome}`: {exc}. "
                                          "Ações liberadas:\n" + _lista_de_acoes())
            return True
        n = pedido["execucoes"]
        pasta = estado.pasta() / "execucoes" / f"{pedido['id']}-{n}-{acao['nome']}"
        pedido["execucao"] = {"nome": acao["nome"], "args": list(argumentos),
                              "pasta": str(pasta), "pedida_em": _iso(self.relogio()),
                              "inicio": None, "timeout_s": acao["timeout_s"]}
        pedido.update(situacao="executando", motivo=f"vai executar {acao['nome']} no "
                                                    "repositório principal",
                      atualizado_em=_iso())
        _linha(dados, pedido, f"o trabalhador pediu {acao['nome']} ({acao['o_que']})")
        self._andar_execucao(dados, pedido)
        return True

    def _registrar_no_diario(self, status, detalhe, *, ref="", dur_s=None):
        if self.diario is None:
            return
        try:
            self.diario("coordenador", status, detalhe[:300], "geral", etapa="executar",
                        ref=ref, dur_s=dur_s)
        except Exception:                                     # noqa: BLE001
            pass

    def _andar_execucao(self, dados, pedido):
        ex = pedido.get("execucao") or {}
        if not ex:
            pedido.update(situacao="esperando", motivo="")
            return
        pasta = Path(ex["pasta"])
        agora = self.relogio()
        if not ex.get("inicio"):
            try:
                acao = montar_acao(ex["nome"], ex.get("args") or [])
            except ValueError as exc:
                return self._fim_da_execucao(dados, pedido, {"erro": str(exc)}, "")
            if acao["janela"] and na_janela_das_postagens(agora):
                motivo = f"{acao['nome']} espera a janela da postagem passar"
                if pedido.get("motivo") != motivo:
                    pedido["motivo"] = motivo
                    _linha(dados, pedido, "em espera: " + motivo)
                return
            ex["inicio"] = _iso(agora)
            self._registrar_no_diario("inicio", f"{pedido['id']}: {acao['nome']} "
                                      + " ".join(ex.get("args") or []), ref=pedido["id"])
            try:
                self.executor(acao, pasta)
            except Exception as exc:                          # noqa: BLE001
                return self._fim_da_execucao(dados, pedido,
                                             {"erro": f"{type(exc).__name__}: {exc}"}, "")
            pedido["motivo"] = f"executando {acao['nome']} no repositório principal"
            _linha(dados, pedido, pedido["motivo"])
            return
        try:
            resultado = json.loads((pasta / "resultado.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            resultado = None
        if resultado is None:
            desde = _segundos_desde(ex["inicio"], agora)
            if desde is not None and desde > int(ex.get("timeout_s") or 600) + 300:
                resultado = {"erro": "a execução não voltou (o coordenador reiniciou no meio?)"}
            else:
                return
        try:
            saida = (pasta / "saida.txt").read_bytes()[-3000:].decode("utf-8", "replace")
        except OSError:
            saida = ""
        self._fim_da_execucao(dados, pedido, resultado, saida)

    def _fim_da_execucao(self, dados, pedido, resultado, saida):
        ex = pedido.get("execucao") or {}
        nome = ex.get("nome", "?")
        codigo = resultado.get("codigo")
        if resultado.get("erro"):
            desfecho, status = "não rodou: " + str(resultado["erro"])[:200], "erro"
        elif resultado.get("estourou"):
            desfecho, status = f"passou de {ex.get('timeout_s')} s e foi parado", "erro"
        else:
            desfecho, status = f"terminou com o código {codigo}", "ok"
        ultima = next((l for l in reversed(saida.splitlines()) if l.strip()), "")
        self._registrar_no_diario(status, f"{pedido['id']}: {nome} {desfecho}"
                                  + (f" — {ultima.strip()[:120]}" if ultima else ""),
                                  ref=pedido["id"], dur_s=_num(resultado.get("dur_s")))
        feitas = list(pedido.get("execucoes_feitas") or [])
        feitas.append({"nome": nome, "args": ex.get("args"), "desfecho": desfecho,
                       "em": _iso(self.relogio())})
        pedido["execucoes_feitas"] = feitas[-MAX_EXECUCOES:]
        pedido["execucao"] = None
        _linha(dados, pedido, f"executei {nome}: {desfecho}")
        self._devolver(dados, pedido, f"Resultado de `EXECUTAR: {nome}` no repositório "
                                      f"principal: {desfecho}.\nFim da saída:\n```\n"
                                      + (saida.strip()[-2500:] or "(vazia)") + "\n```")

    def _devolver(self, dados, pedido, texto):
        """O texto volta ao MESMO trabalhador como continuacao."""
        pedido["texto"] += "\n\n" + texto
        pedido.update(situacao="esperando", motivo="", continuar=True,
                      ultima_continuacao=texto[:600], continuar_em=None, tentou_em=None,
                      atualizado_em=_iso())

    def _entregue(self, dados, pedido, ficha):
        resposta = self._resposta(pedido.get("trabalhador"))
        marca = _MARCA_GRIMORIO.search(resposta)
        if marca and self._pedir_ao_grimorio(
                dados, pedido, f"{marca.group(1).lower()}/{marca.group(2).lower()}"):
            return
        acao = marca_executar(resposta)
        if acao and acao[0] in ACOES_SERVIDOR:
            if self._executar_no_servidor(dados, pedido, ficha, acao[0], acao[1]):
                return
        elif acao and self._pedir_execucao(dados, pedido, acao[0], acao[1]):
            return
        self._encerrar(dados, pedido, ficha, resposta, ler_desfecho(resposta))

    def _encerrar(self, dados, pedido, ficha, resposta, desfecho):
        """O desfecho decide: feito -> respondido/entregue; bloqueado ->
        esperando_voce com o que falta; falhou -> falhou com o motivo."""
        tipo, fonte = desfecho["tipo"], desfecho["fonte"]
        motivo = str(desfecho.get("motivo") or "").strip()
        aviso = str(desfecho.get("aviso") or "").strip()
        codigo = arquivos_de_codigo(ficha)
        if fonte in ("heuristica", "sem_linha", "vazia"):
            _linha(dados, pedido, "a resposta veio sem a linha DESFECHO; "
                   + ("li como BLOQUEADO pelas frases dela" if fonte == "heuristica" else
                      "terminou sem resposta: não marco como entregue" if fonte == "vazia" else
                      "nenhuma frase de bloqueio: sigo pelo que mudou"))
        if tipo == "bloqueado" and fonte == "heuristica" and codigo:
            # 05/10/2026 (conferente): adivinhado pelas frases, com codigo
            # mudado: nao some do vigia/conferente; entra com o aviso
            tipo, aviso, motivo = "feito", motivo, ""
            _linha(dados, pedido, f"mas mudou {codigo} arquivo(s) de código: vai como entregue "
                                  "com aviso, e o conferente olha")
        elif tipo == "feito" and aviso and not codigo:
            # "Nao foi possivel ligar" + "DESFECHO: feito", sem codigo: nada
            # foi entregue -- o "feito" mente
            tipo, motivo = "bloqueado", aviso
            _linha(dados, pedido, "a linha diz feito, mas o texto diz que não: " + aviso[:200])
        pedido["desfecho"] = {"tipo": tipo, "fonte": fonte, "motivo": motivo[:300],
                              "aviso": aviso[:300]}
        if tipo == "falhou":
            motivo = motivo or "o trabalhador disse que falhou, sem o motivo"
            pedido.update(situacao="falhou", motivo=motivo[:240], resposta=resposta[:1000],
                          atualizado_em=_iso())
            _linha(dados, pedido, "falhou: " + motivo, tipo="final")
            self.avisar("❌ Pedido falhou: " + motivo[:400])
            return
        if tipo == "bloqueado":
            self._bloquear(dados, pedido, motivo or "o trabalhador parou sem dizer o que falta",
                           resposta)
            return
        diff = ficha.get("diff") if isinstance(ficha.get("diff"), dict) else {}
        if diff and not codigo:
            # so respondeu (nada de codigo; o rascunho resposta.md nao conta):
            # nao ha o que aplicar nem conferir
            pedido.update(situacao="respondido", motivo="", resposta=resposta[:1000],
                          atualizado_em=_iso())
            final = resposta.strip()[:500] or "terminou sem mudar código"
            _linha(dados, pedido, "respondido: " + final, tipo="final")
            self.avisar("🧭 Pedido respondido: " + final)
            return
        motivo = ("entregue com aviso: " + aviso)[:240] if aviso else ""
        pedido.update(situacao="entregue", motivo=motivo, atualizado_em=_iso())
        _linha(dados, pedido, (motivo + "; " if motivo else "entregue; ")
               + "esperando o vigia testar e aplicar, depois o conferente olha")

    def _bloquear(self, dados, pedido, motivo, resposta=""):
        """Parou por algo que so o Adrian faz: "esperando voce", com o que falta.
        A resposta dele no proprio pedido volta ao MESMO trabalhador."""
        motivo = ("bloqueado: " + str(motivo).strip())[:240]
        mudou = pedido.get("situacao") != "esperando_voce" or pedido.get("motivo") != motivo
        pedido.update(situacao="esperando_voce", motivo=motivo, bloqueio=motivo,
                      grimorio_ref=None, grimorio_via=None, atualizado_em=_iso())
        if resposta:
            pedido["resposta"] = resposta[:1000]
        if mudou:
            _linha(dados, pedido, "esperando você — " + motivo, tipo="final")
            self.avisar("⏸ Pedido esperando você: " + motivo)

    def _executar_no_servidor(self, dados, pedido, ficha, nome, argumentos):
        """`EXECUTAR: gerente ligar`: o SERVIDOR grava o proprio estado, rele e
        responde. Devolve se cuidou do pedido (False: passou do teto de acoes)."""
        feitas = int(pedido.get("execucoes") or 0)
        if feitas >= MAX_EXECUCOES:
            _linha(dados, pedido, f"pediu EXECUTAR {nome}, mas já foram {feitas} ações neste "
                                  "pedido; não executo mais")
            return False
        pedido["execucoes"] = feitas + 1
        try:
            fazer, argumentos = acao_do_servidor(nome, argumentos)
        except ValueError as exc:
            _linha(dados, pedido, f"EXECUTAR {nome} recusado: {exc}")
            self._devolver(dados, pedido, f"O servidor recusou `EXECUTAR: {nome}`: {exc}. "
                                          "Ações liberadas:\n" + _lista_de_acoes())
            return True
        comando = " ".join([nome, *argumentos])
        porque = autorizada_pelo_adrian(nome, argumentos, texto_do_adrian(pedido))
        if porque:
            # o estado do servidor e do Adrian: o trabalhador nao muda sozinho
            _linha(dados, pedido, f"EXECUTAR {comando} NÃO executado: {porque}")
            self._registrar_no_diario("recusado", f"{pedido['id']}: {comando}: {porque}",
                                      ref=pedido["id"])
            self._bloquear(dados, pedido, f"o trabalhador pediu `EXECUTAR: {comando}`, mas "
                                          f"{porque}; não executei. Se quer, responda aqui "
                                          f"(ex.: «pode {comando}»)",
                           self._resposta(pedido.get("trabalhador")))
            return True
        self._registrar_no_diario("inicio", f"{pedido['id']}: {comando} (estado do servidor)",
                                  ref=pedido["id"])
        try:
            feito, ok = fazer(argumentos), True
        except Exception as exc:                              # noqa: BLE001
            feito, ok = f"{type(exc).__name__}: {exc}"[:300], False
        self._registrar_no_diario("ok" if ok else "erro", f"{pedido['id']}: {comando}: {feito}",
                                  ref=pedido["id"])
        historico = list(pedido.get("execucoes_feitas") or [])
        historico.append({"nome": nome, "args": argumentos, "em": _iso(self.relogio()),
                          "desfecho": ("conferido: " if ok else "não rodou: ") + feito})
        pedido["execucoes_feitas"] = historico[-MAX_EXECUCOES:]
        if not ok:
            self._encerrar(dados, pedido, ficha, feito, {
                "tipo": "falhou", "fonte": "servidor",
                "motivo": f"o servidor não conseguiu `{comando}`: {feito}"})
            return True
        _linha(dados, pedido, f"o servidor executou `{comando}` e conferiu: {feito}")
        if arquivos_de_codigo(ficha):
            # tambem mudou codigo: esse ainda passa pelo vigia e pelo conferente
            self._encerrar(dados, pedido, ficha, self._resposta(pedido.get("trabalhador")),
                           {"tipo": "feito", "fonte": "servidor", "motivo": ""})
            return True
        pedido.update(situacao="respondido", motivo="", atualizado_em=_iso(),
                      resposta=f"Feito pelo servidor: {feito}")
        pedido["desfecho"] = {"tipo": "feito", "fonte": "servidor", "motivo": ""}
        _linha(dados, pedido, "respondido: feito pelo servidor — " + feito, tipo="final")
        self.avisar("🧭 Pedido respondido: feito pelo servidor — " + feito)
        return True

    def _resposta(self, ident):
        if not ident:
            return ""
        try:
            return (self.despachante.pasta_da(ident) / "resposta.md").read_text(encoding="utf-8")
        except (OSError, AttributeError):
            return ""

    def _retomar(self, dados, pedido):
        trabalhador = pedido["trabalhador"]
        ficha = self._estado_do(trabalhador)
        if not ficha:
            pedido.update(trabalhador=None, contratos=int(pedido.get("contratos") or 0) + 1)
            return
        situacao = self._situacao_do(ficha)
        if situacao == "rodando":
            sinal = self._ultimo_sinal(trabalhador, ficha)
            if (sinal is not None and pedido.get("situacao") == "esperando"
                    and (self.relogio() - sinal).total_seconds() >= SEM_EVENTO_S):
                # pedi para parar e ele ainda nao parou: "de volta" aqui e
                # "parei" no pulso seguinte era o laco; espera ele sair (e
                # repete o pedido de parar a cada RETOMAR_S)
                if self._pode_tentar(pedido):
                    pedido["tentou_em"] = _iso(self.relogio())
                    try:
                        self.despachante.parar(trabalhador)
                    except Exception:                         # noqa: BLE001
                        pass
                self._esperar(dados, pedido, "pedi para o trabalhador parar (sem evento há mais "
                                             "de 10 min); espero ele sair para retomar")
                return
            if pedido.get("situacao") != "trabalhando":
                pedido.update(situacao="trabalhando", motivo="", atualizado_em=_iso())
                _linha(dados, pedido, "trabalhador de volta")
            return
        if situacao in ("terminou", "falhou", "parado"):
            queda = self._queda_nova(pedido, trabalhador)
            if queda:
                self._parar_por_limite(dados, pedido, queda)
                return
        if situacao == "aguardando_permissao" and not pedido.get("continuar"):
            # 03/10: o 66e4ba54 foi "retomado" 5 vezes ESPERANDO a permissao e
            # morreu em "falhou". Quem decide e o Adrian (ou o gerente): espera.
            if not self._permissao_vira_grimorio(dados, pedido, ficha):
                self._esperar(dados, pedido, str(ficha.get("motivo") or "aguardando permissão"))
            return
        if situacao == "terminou" and not pedido.get("continuar"):
            self._entregue(dados, pedido, ficha)
            return
        if pedido.get("continuar"):
            # a continuacao sai no primeiro pulso; se o `corrigir` no fundo
            # nao comecou (paralelo, janela), reenvia depois de RETOMAR_S
            if not self._pode_tentar(pedido, "continuar_em"):
                return
            if pedido.get("continuar_em"):
                pedido["motivo"] = (self._motivo_do_fundo(trabalhador)
                                    or "a continuação não começou; reenviando")
        elif not self._pode_tentar(pedido):
            return
        pedido["tentou_em"] = _iso(self.relogio())
        if ficha.get("ia") == "claude":
            motivo = self._motivo_claude()
            if motivo:
                if _construir(pedido["texto"]):
                    # o Codex assume: um trabalhador novo, a worktree do
                    # Claude fica como estava (o diff dela nao se perde)
                    pedido.update(trabalhador=None,
                                  contratos=int(pedido.get("contratos") or 0) + 1,
                                  tentou_em=None, ia_forcada="codex")
                    self._esperar(dados, pedido, motivo + "; o Codex assume")
                else:
                    self._esperar(dados, pedido, motivo)
                return
        if pedido.get("continuar"):
            self._continuar(dados, pedido, ficha)
            return
        if int(pedido.get("retomadas") or 0) >= MAX_RETOMADAS:
            # o mesmo trabalhador caiu de novo e de novo: nao fica girando
            # para sempre gastando a janela; o Adrian ve e decide
            pedido.update(situacao="falhou", atualizado_em=_iso(),
                          motivo=f"caiu {MAX_RETOMADAS} vezes: " + str(pedido.get("motivo") or "?")[:200])
            _linha(dados, pedido, "falhou: " + pedido["motivo"], tipo="final")
            self.avisar("❌ Pedido parado: " + pedido["motivo"])
            return
        pedido["retomadas"] = int(pedido.get("retomadas") or 0) + 1
        concedida = (situacao == "criado"
                     and str(ficha.get("motivo") or "").startswith("permissao concedida:"))
        try:
            self.despachante.no_fundo(["retomar" if concedida else "rodar", "--id", trabalhador],
                                      trabalhador)
        except Exception as exc:
            self._esperar(dados, pedido, "retomada: " + str(exc)[:200])
            return
        pedido.update(situacao="trabalhando", motivo="", atualizado_em=_iso())
        _linha(dados, pedido, "trabalhador retomado")

    def _continuar(self, dados, pedido, ficha):
        """A continuacao do Adrian vai ao MESMO trabalhador, no fundo."""
        trabalhador = pedido["trabalhador"]
        if ficha.get("aplicado"):
            # a entrega dele ja esta na arvore principal (e o `aplicar` nao
            # reaplica): a continuacao vai a um trabalhador novo, que parte do
            # HEAD com a mudanca e recebe o pedido inteiro
            pedido.update(trabalhador=None, conferente=None, continuar=False,
                          continuar_em=None, tentou_em=None, situacao="recebido",
                          contratos=int(pedido.get("contratos") or 0) + 1)
            _linha(dados, pedido, "a entrega anterior já foi aplicada; a continuação "
                                  "vai a um orquestrador novo com o pedido inteiro")
            return
        caminho = self.despachante.pasta_da(trabalhador) / "continuacao.md"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        # o Claude abre sessao nova a cada rodada: leva o pedido inteiro
        caminho.write_text("O Adrian continuou o pedido. Pedido inteiro, com as "
                           "continuações:\n\n" + pedido["texto"]
                           + "\n\nAtenda a ÚLTIMA continuação, sem desfazer o que já fez.",
                           encoding="utf-8")
        if ficha.get("ia") == "codex" and not ficha.get("thread_id"):
            argv = ["rodar", "--id", trabalhador]     # sem conversa para continuar
        else:
            argv = ["corrigir", "--id", trabalhador, "--texto", str(caminho)]
        try:
            self.despachante.no_fundo(argv, trabalhador)
        except Exception as exc:
            self._esperar(dados, pedido, "continuação: " + str(exc)[:200])
            return
        if pedido.get("conferente"):
            pedido["conferente"] = None       # a entrega vai mudar: confere de novo
        primeira = not pedido.get("continuar_em")
        # `continuar` so cai quando o trabalhador estiver rodando (_acompanhar)
        pedido.update(situacao="trabalhando", continuar_em=_iso(self.relogio()),
                      atualizado_em=_iso())
        if primeira:
            pedido["motivo"] = ""
            _linha(dados, pedido, "continuação entregue ao mesmo orquestrador")

    # ------------------------------------------------------------ conferir
    def _conferir(self, dados, pedido):
        trabalhador = pedido.get("trabalhador")
        ficha = self._estado_do(trabalhador)
        if not ficha:
            return
        if self._situacao_do(ficha) == "rodando":
            # o vigia achou teste vermelho e mandou corrigir
            pedido.update(situacao="trabalhando", motivo="", atualizado_em=_iso())
            _linha(dados, pedido, "o vigia mandou corrigir; trabalhando de novo")
            return
        if ficha.get("situacao") == "aguardando_permissao" and not ficha.get("aplicado"):
            # 05/10/2026: o cb44cd52 ficou "entregue" com o trabalhador parado
            # pedindo permissao: nada ia ser aplicado nem conferido
            if not self._permissao_vira_grimorio(dados, pedido, ficha):
                self._esperar(dados, pedido, str(ficha.get("motivo") or "aguardando permissão"))
            return
        if not ficha.get("aplicado"):
            return                # o vigia ainda nao aplicou (testes, momento seguro)
        ident = pedido.get("conferente") or _id_conferente(trabalhador)
        conf = self._estado_do(ident)
        if conf is None:
            if not self._pode_tentar(pedido, "conf_tentou_em"):
                return
            pedido["conf_tentou_em"] = _iso(self.relogio())
            motivo = self._motivo_claude()
            ia = "codex" if motivo else "claude"
            caminho = self.despachante.pasta_da(ident) / "pedido.md"
            caminho.parent.mkdir(parents=True, exist_ok=True)
            corpo = ("Confira a entrega do pedido " + pedido["id"] + " (trabalhador "
                     + trabalhador + "), JÁ APLICADA nesta worktree: "
                     + ", ".join((ficha.get("aplicado") or {}).get("arquivos") or [])
                     + ".\n\nO pedido do Adrian:\n\n" + pedido["texto"][:20_000]
                     + "\n\nA resposta do trabalhador:\n\n" + self._resposta(trabalhador)[:20_000]
                     + "\n\nDevolva APROVADO ou DEFEITOS (com a lista) na sua mensagem final; "
                       "não crie arquivo resposta.md (nem outro) na worktree.")
            if ia == "codex":
                try:
                    corpo = self.despachante.prompt_do_cargo("conferente") + "\n\n" + corpo
                except Exception:
                    pass
            caminho.write_text(corpo, encoding="utf-8")
            try:
                self.despachante.criar(ident, caminho, PERMITIDOS[:3], ia=ia,
                                       cargo="conferente", titulo="Conferir " + pedido["id"])
                self.despachante.no_fundo(["rodar", "--id", ident], ident)
            except Exception as exc:
                self._esperar_conferente(dados, pedido, str(exc)[:200])
                return
            pedido.update(conferente=ident, motivo="")
            _linha(dados, pedido, f"aplicado; conferente ({ia}) olhando")
            return
        pedido["conferente"] = ident
        situacao = self._situacao_do(conf)
        if situacao == "terminou":
            resposta = self._resposta(ident)
            if _aprovado(resposta):
                pedido.update(situacao="conferido", motivo="", resposta=resposta[:1000],
                              atualizado_em=_iso())
                final = (self._resposta(trabalhador).strip()[:400] or "pronto")
                _linha(dados, pedido, "conferido: " + final, tipo="final")
                self.avisar("✅ Pedido conferido: " + final)
            else:
                pedido.update(situacao="falhou", motivo="o conferente apontou defeitos",
                              resposta=resposta[:1000], atualizado_em=_iso())
                _linha(dados, pedido, "o conferente apontou defeitos: "
                       + (resposta.strip()[:400] or "(sem resposta)"), tipo="final")
                self.avisar("❌ Pedido com defeitos: " + (resposta.strip()[:400] or "?"))
            return
        if situacao in ("rodando", "criado"):
            return
        # parado/falhou: retoma o MESMO conferente, sem recriar
        if not self._pode_tentar(pedido, "conf_tentou_em"):
            return
        pedido["conf_tentou_em"] = _iso(self.relogio())
        motivo = self._motivo_claude() if conf.get("ia") == "claude" else ""
        if not motivo and conf.get("ia") == "claude":
            # caiu no limite e ele ainda nao renovou: nao relanca a cada 120 s
            queda = self._queda_por_limite(ident)
            renova = _num((queda or {}).get("renova_em"))
            if queda and renova is not None and self.relogio().timestamp() < renova:
                motivo = f"o Claude bateu no limite; renova {_hora(renova)}"
        if motivo:
            self._esperar_conferente(dados, pedido, motivo)
            return
        try:
            self.despachante.no_fundo(["rodar", "--id", ident], ident)
        except Exception as exc:
            self._esperar_conferente(dados, pedido, str(exc)[:200])

    def _esperar_conferente(self, dados, pedido, motivo):
        """Continua "entregue" (o pulso volta ao conferente), com o motivo."""
        motivo = "conferente: " + str(motivo)[:220]
        if pedido.get("motivo") != motivo:
            pedido["motivo"] = motivo
            _linha(dados, pedido, "em espera: " + motivo)

    # ------------------------------------------------------------ pulso
    def ler_grimorio(self, leitor=None, marcar=None, carregar=None):
        """Cada resposta NAO LIDA do Grimorio vira um pedido para um orquestrador do
        servidor, e a resposta fica marcada como lida apontando para ele.

        04/10/2026, o Adrian: "Por que nao tem ninguem lendo as decisoes?". Quem lia
        era so a sessao do VS Code: fechada ela, a resposta ficava parada."""
        if leitor is None or marcar is None or carregar is None:
            if self.grimorio is None:
                return []
            leitor, marcar, carregar = self.grimorio
        criados = []
        itens = carregar()
        for ev in leitor():
            if ev.get("lida") or ev.get("ilegivel") or not ev.get("id"):
                continue
            no = itens.get(ev["id"]) or {}
            opcao = next((o for o in no.get("opcoes") or [] if o.get("id") == ev.get("opcao")), {})
            ref = f"{ev.get('projeto')}/{ev['id']}"
            # Lacuna 2: um pedido PERGUNTOU isto e esta parado esperando: a
            # resposta volta a ele, e nao abre um pedido novo
            retomado = self._retomar_com_resposta(ev, no, opcao)
            if retomado:
                try:
                    marcar(ref, [f"tarefa:{retomado}"],
                           nota="lida pelo servidor; voltou ao pedido que esperava a decisão",
                           origem="leitor")
                except Exception as exc:                      # noqa: BLE001
                    with _TRAVA:
                        dados = _ler()
                        pedido = next((p for p in dados["pedidos"] if p["id"] == retomado), None)
                        if pedido:
                            _linha(dados, pedido, f"não consegui marcar {ref} como lida: {exc}")
                            _gravar(dados)
                criados.append(retomado)
                continue
            texto = (f"O Adrian respondeu no Grimório ({ev.get('projeto')}/{ev['id']}): "
                     f"«{ev.get('titulo') or no.get('titulo')}»\n"
                     f"Pergunta: {no.get('pergunta') or ''}\n"
                     f"Escolheu: {ev.get('opcao_rotulo') or ev.get('opcao')} — {opcao.get('descricao') or ''}\n"
                     + (f"Comentário dele: {ev['comentario']}\n" if ev.get("comentario") else "")
                     + f"Contexto do nó: {no.get('contexto') or ''}\n\n"
                     "APLIQUE a escolha: faça o que ela pede (ou contrate quem faça), confira e "
                     "responda curto. Se já estiver feito, confirme e encerre. Se a escolha precisar "
                     "de algo que só ele faz (login, conta), diga exatamente o quê.")
            pedido = self.registrar(texto, "grimorio", novo=True)
            try:
                marcar(ref, [f"tarefa:{pedido['id']}"],
                       nota="lida pelo servidor; virou pedido ao orquestrador", origem="leitor")
            except Exception as exc:                          # noqa: BLE001
                with _TRAVA:
                    dados = _ler()
                    _linha(dados, pedido, f"não consegui marcar {ref} como lida: {exc}")
                    _gravar(dados)
            criados.append(pedido["id"])
        return criados

    def passo(self):
        try:
            self.ler_grimorio()
        except Exception as exc:                              # noqa: BLE001
            self.avisar(f"⚠ não consegui ler o Grimório: {exc}")
        with _TRAVA:
            dados = _ler()
            for pedido in dados["pedidos"]:
                situacao = pedido.get("situacao")
                if situacao in FINAIS:
                    continue
                try:
                    if situacao == "parado_limite":
                        self._cuidar_do_limite(dados, pedido)
                    elif situacao == "esperando_voce":
                        self._cuidar_do_grimorio(dados, pedido)
                    elif situacao == "executando":
                        self._andar_execucao(dados, pedido)
                    elif not pedido.get("trabalhador"):
                        self._contratar(dados, pedido)
                    elif situacao == "trabalhando":
                        if pedido.get("continuar"):
                            ficha = self._estado_do(pedido["trabalhador"]) or {}
                            if self._situacao_do(ficha) not in ("rodando", "criado"):
                                self._retomar(dados, pedido)
                                continue
                        self._acompanhar(dados, pedido)
                    elif situacao in ("esperando", "recebido"):
                        self._retomar(dados, pedido)
                    elif situacao == "entregue":
                        if pedido.get("continuar"):
                            self._retomar(dados, pedido)
                        else:
                            self._conferir(dados, pedido)
                except Exception as exc:    # um pedido ruim nao para os outros
                    self._esperar(dados, pedido, f"erro interno ({type(exc).__name__}: {exc})")
            _gravar(dados)
            return dados

    def reabrir(self, ident, motivo="reaberto", continuacao=None):
        """Devolve um pedido encerrado (ou parado) para "esperando", com as
        retomadas zeradas: o pulso retoma o MESMO trabalhador.

        05/10/2026: cb44cd52 ("Ligar o gerente") e cd2e5e0c morreram em
        "falhou" queimando as 5 retomadas no limite semanal do Claude.

        Com `continuacao`, o texto vai ao mesmo trabalhador (o caminho novo,
        p.ex. "termine com EXECUTAR: gerente ligar"); a permissao que ele
        deixou pendente e negada antes, para ele nao ficar parado nela."""
        with _TRAVA:
            dados = _ler()
            pedido = next((p for p in dados["pedidos"] if p.get("id") == ident), None)
            if pedido is None:
                raise KeyError(f"não há o pedido {ident}")
            if pedido.get("situacao") in ("trabalhando", "executando"):
                raise ValueError(f"{ident} está {pedido['situacao']}; nada a reabrir")
            antes = pedido.get("situacao")
            pedido.update(situacao="esperando", motivo="", retomadas=0, tentou_em=None,
                          conf_tentou_em=None, continuar_em=None, bloqueio=None,
                          grimorio_ref=None, grimorio_via=None, atualizado_em=_iso())
            if antes == "falhou" and pedido.get("conferente"):
                pedido["conferente"] = None      # defeitos: confere de novo do zero
            _linha(dados, pedido, f"{motivo} (estava {antes}); o pulso retoma o mesmo "
                                  "trabalhador")
            if continuacao:
                trabalhador = pedido.get("trabalhador")
                ficha = self._estado_do(trabalhador) or {}
                if ficha.get("situacao") == "aguardando_permissao":
                    try:
                        self.despachante.decidir_permissao(trabalhador, False)
                        _linha(dados, pedido, "neguei a permissão que ele deixou pendente ("
                               + str((ficha.get("pedido_permissao") or {}).get("o_que") or "?")
                               + "): segue pelo caminho novo")
                    except Exception as exc:                  # noqa: BLE001
                        _linha(dados, pedido, f"não consegui negar a permissão pendente: {exc}")
                self._devolver(dados, pedido, str(continuacao).strip())
                _linha(dados, pedido, str(continuacao).strip(), tipo="pedido")
            _gravar(dados)
            return dict(pedido)

    def reavaliar(self, ident):
        """Passa a regra do desfecho num pedido "entregue" de antes dela.

        05/10/2026: cb44cd52 e cd2e5e0c estavam "entregue" com respostas que
        diziam "Nao foi possivel ligar" e "bloqueado so pelo login do Drive".
        Tira tambem as mensagens soltas que grudaram nele ("Coordenador?")."""
        with _TRAVA:
            dados = _ler()
            pedido = next((p for p in dados["pedidos"] if p.get("id") == ident), None)
            if pedido is None:
                raise KeyError(f"não há o pedido {ident}")
            if pedido.get("situacao") != "entregue":
                raise ValueError(f"{ident} está {pedido.get('situacao')}; só reavalio 'entregue'")
            trabalhador = pedido.get("trabalhador")
            ficha = self._estado_do(trabalhador) or {}
            if ficha.get("aplicado"):
                raise ValueError(f"{ident}: a entrega já foi aplicada; quem decide é o conferente")
            soltas = self._tirar_conversa_solta(pedido)
            if soltas:
                _linha(dados, pedido, f"tirei {len(soltas)} mensagem(ns) solta(s) que não eram "
                                      "deste pedido: " + " | ".join(soltas)[:300])
            resposta = self._resposta(trabalhador)
            desfecho = ler_desfecho(resposta)
            _linha(dados, pedido, f"reavaliado pela regra do desfecho (estava entregue; "
                                  f"a resposta diz: {desfecho['tipo']})")
            if desfecho["tipo"] != "feito":
                self._encerrar(dados, pedido, ficha, resposta, desfecho)
            else:
                pedido["desfecho"] = {"tipo": "feito", "fonte": desfecho["fonte"], "motivo": ""}
            _gravar(dados)
            return dict(pedido)

    @staticmethod
    def _tirar_conversa_solta(pedido):
        """As continuacoes do Adrian que eram conversa solta saem do texto."""
        marca = "\n\nContinuação do Adrian:\n"
        partes = str(pedido.get("texto") or "").split(marca)
        ficam, soltas = [partes[0]], []
        for parte in partes[1:]:
            (soltas if e_conversa_solta(parte) else ficam).append(parte)
        if soltas:
            pedido["texto"] = marca.join(ficam)
            pedido["mensagens"] = max(1, int(pedido.get("mensagens") or 1) - len(soltas))
            if pedido.get("ultima_continuacao") in soltas:
                pedido["ultima_continuacao"] = ficam[-1] if len(ficam) > 1 else None
        return [s.strip() for s in soltas]

    def para_o_app(self):
        dados = _ler()
        pedidos = [{k: v for k, v in p.items() if k != "resposta"}
                   for p in reversed(dados["pedidos"])][:40]
        return {"pedidos": pedidos, "conversa": dados["conversa"][-120:],
                "novo_assunto": bool(dados.get("novo_assunto")),
                "na_fila": sum(1 for p in pedidos if p.get("situacao") in VIVOS)}


MESA = MesaPedidos()


def _ligar_grimorio_real():
    from remoto import decisoes
    MESA.grimorio = (decisoes.leitor, decisoes.marcar, decisoes.carregar)


def _ligar_producao():
    """O MESA do servidor: le o Grimorio e escreve o desfecho das acoes da
    lista branca no diario (atividade.jsonl). Teste nunca chama isto."""
    _ligar_grimorio_real()
    try:
        from builds import atividade
        MESA.diario = atividade.registrar
    except Exception:                                         # noqa: BLE001
        MESA.diario = None


def registrar(texto, origem="app", *, novo=False):
    return MESA.registrar(texto, origem, novo=novo)


def reabrir(ident, motivo="reaberto", continuacao=None):
    return MESA.reabrir(ident, motivo, continuacao)


def reavaliar(ident):
    return MESA.reavaliar(ident)


def novo_assunto(origem="app"):
    return MESA.novo_assunto(origem)


def passo():
    return MESA.passo()


def para_o_app():
    return MESA.para_o_app()
