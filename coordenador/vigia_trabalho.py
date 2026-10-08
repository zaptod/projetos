# -*- coding: utf-8 -*-
"""O vigia de trabalho: alguem de olho nas tarefas, entregas e decisoes.

Pedido do Adrian (02/10, 00:1x): "as tarefas no app estao todas paradas,
quero alguem de olho nisso tambem", "alguem checando se precisa de decisao
pro Grimorio" e "alguem checando o avanco das tasks".

O laco do supervisor chama `VigiaTrabalho.passo()` a cada ~60 s, numa thread
propria (os testes de uma entrega levam minutos). Sem novidade, ele so le.

1. Entregas do Codex (`remoto.delegar`). Delegado que TERMINOU depois que o
   vigia nasceu, sem aplicar nem limpar:
   coletar -> validador -> testes da area -> momento seguro -> aplicar ->
   commit POR CAMINHO (so os arquivos do diff) -> limpar. Testes vermelhos:
   UMA correcao (`corrigir`, no fundo, com a cauda da saida); falhou de novo,
   ou o validador recusou: avisa ("precisa de olho") e nao mexe mais. Arvore
   suja nos arquivos da entrega, trava ocupada ou janela da postagem nao sao
   defeito: a entrega fica em `esperando` (arvore suja avisa UMA vez depois de
   60 min) e aplica sozinha quando passar. Codigo
   de servico mudou: pede o reinicio ao supervisor (que so reinicia em
   momento seguro). Entregas mais velhas que o vigia so aparecem no resumo:
   muitas ja foram aplicadas a mao, e reaplicar seria barulho.
2. Mesa (`remoto.orquestrador`). Item "CODEX ..." cujos delegados citados ja
   foram aplicados: fecha (`agente_fim`). Item sem relato ha 45 min: avisa
   uma vez por relato.
3. Grimorio (`remoto.decisoes`). A secao de duvida da resposta do Codex vai
   ao CEREBRO, que diz se e escolha de produto e redige o no (2 ou 3 opcoes).
   Sem cerebro (proibido, teto, limite), so avisa. No maximo 5 nos por dia,
   nunca dois de mesmo titulo.
4. Resumo de andamento no Telegram e nos eventos do app: so com novidade, e
   no maximo a cada 60 min. O retrato vai sempre para `estado.json`, chave
   `trabalho`:
     {"em", "proibido", "rodando": [{id, titulo}], "mesa": [{id, parte,
      titulo, sem_relato_min}], "aplicados": [{id, commit, em}] (ultimos 10),
      "olho": [{id, motivo, em}], "esperando": {id: motivo},
      "corrigindo": [ids], "antigos": [ids], "espera_adrian": {"decisoes": n,
      "titulos": [...], "propostas": n}, "fila": {"n", "primeiros"},
      "resumo_em", "novidades": n}
5. Com o Claude proibido, so observa: nao aplica, nao corrige, nao fecha a
   Mesa e nao cria no.

A memoria (o que ja foi avisado, aplicado, corrigido) fica em
`trabalho_memoria.json`, na pasta do coordenador: reiniciar nao repete aviso.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from .estado import pasta

INTERVALO_S = 60
PARADA_S = 45 * 60
NOS_POR_DIA = 5
RESUMO_A_CADA_S = 60 * 60
CORRECAO_ESPERA_S = 10 * 60      # a correcao pedida tem de comecar nesse prazo
CAUDA_TESTES = 4000
SEM_TESTE = ("docs",)            # pasta de topo que nao tem teste
# Varredura 05/10/2026 (itens 7, 12, 21c e 23):
ESPERA_SUJA_S = 60 * 60          # arvore suja: passado isto, avisa UMA vez (e segue esperando)
OLHO_VALIDADE_S = 48 * 3600      # item de olho/corrigidos mais velho que isto sai
FAXINA_APOS_S = 6 * 3600         # delegado encerrado ha mais que isto e limpo
FAXINA_POR_PASSO = 3
TERMINAIS = ("terminou", "falhou", "parado", "negado")
# Falha de teste que e do AMBIENTE, nao da entrega: roda de novo uma vez antes
# de pedir correcao (pasta presa pelo Windows, Tcl que nao achou a biblioteca).
INFRA = re.compile(r"WinError (?:5|145|183)\b|tcl_findLibrary|"
                   r"Can't find a usable init\.tcl", re.I)
# Recusa que passa sozinha: outra rodada segurando a trava, o trabalhador
# ainda rodando. Vira `esperando` (tenta no proximo passo), nunca `olho` com
# integrador contratado (05/10: conf-log-cp1252 foi para olho por "trava
# ocupada ha mais de 15 s: delegar.lock").
PASSAGEIRA = re.compile(r"trava ocupada|est[aá] em andamento|ainda est[aá] rodando", re.I)
# Marca do motivo de arvore suja (o vigia solta do `olho` quem tem isto).
SUJA_MARCA = "mudança não commitada"
# Titulo dos pedidos que nascem de uma resposta no Grimorio: e a PERGUNTA.
GRIMORIO = re.compile(r"^O Adrian respondeu no Grim[oó]rio\s*\(([^)]*)\)\s*:?\s*«?(.*?)»?\s*$")
ASSUNTO_MAX = 100
CO_AUTOR = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# "O que ficou duvidoso", "o que ficou de fora ou em duvida" (o pedido padrao
# do despachante), "Duvidas", "Precisa de decisao"
DUVIDA = re.compile(r"(o que ficou[\w\s]{0,24}duvid\w*|duvid\w*|precisa(?:m)? de decisao)",
                    re.I)
FIM_DE_SECAO = re.compile(r"^\s*(#+\s|\*\*[^*]+\*\*\s*:?\s*$|[A-Z][^.:]{0,60}:\s*$)")


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()


def _norm(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _sem_acento(texto).lower()).strip()


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _data(iso) -> datetime | None:
    try:
        return datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return None


# ================================================================ ajudantes
def extrair_duvida(resposta: str) -> str:
    """O texto da secao de duvida da resposta do Codex ('' se nao ha).

    Aceita "O que ficou duvidoso", "Duvidas", "Precisa de decisao", como
    titulo (##, **...**) ou como rotulo ("Duvidas: ..."). Vai ate o proximo
    titulo. "nenhuma", "nada" e "-" contam como sem duvida."""
    linhas = str(resposta or "").splitlines()
    for i, linha in enumerate(linhas):
        limpa = _sem_acento(linha)
        if not DUVIDA.search(limpa) or len(limpa.strip()) > 200:
            continue
        cabeca = re.match(r"^\s*(#+\s*|\*\*|[-*]\s*\*\*)?(.*)$", limpa).group(2)
        if not DUVIDA.match(cabeca.strip(" *:")):
            continue
        resto = linha.split(":", 1)[1].strip(" *") if ":" in linha else ""
        corpo = [resto] if resto else []
        for seguinte in linhas[i + 1:]:
            if FIM_DE_SECAO.match(seguinte) and corpo:
                break
            corpo.append(seguinte)
        texto = "\n".join(corpo).strip()
        if _norm(texto) in ("", "nenhuma", "nenhum", "nada", "nao", "sem duvidas",
                            "nenhuma duvida", "nada ficou duvidoso"):
            return ""
        return texto[:4000]
    return ""


def primeira_linha(resposta: str, reserva: str) -> str:
    """A primeira linha util da resposta (sem Markdown); generica = a reserva."""
    for linha in str(resposta or "").splitlines():
        # "[api_http.py](/E:/projetos-wt/...:186)" vira "api_http.py"
        limpa = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", linha)
        limpa = re.sub(r"[#*`>]+", "", limpa).strip(" -:")
        if not limpa:
            continue
        if len(limpa) < 12 or limpa.endswith(":") or _norm(limpa) in (
                "o que mudou", "resumo", "pronto", "feito", "o que construiu"):
            break
        return limpa[:120]
    return (str(reserva or "").strip() or "entrega do Codex")[:120]


def nome_da_ia(estado: dict) -> str:
    return "Claude" if str(estado.get("ia") or "") == "claude" else "Codex"


def recusa_passageira(exc) -> bool:
    """A recusa passa sozinha (trava ocupada, rodada em andamento)?"""
    return bool(getattr(exc, "passageira", False)) or bool(PASSAGEIRA.search(str(exc)))


def _sem_markdown(texto: str) -> str:
    limpo = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", str(texto or ""))
    limpo = re.sub(r"[#*`>]+", "", limpo)
    return " ".join(limpo.split()).strip(" -:")


def _cortar_na_palavra(texto: str, n: int = ASSUNTO_MAX, reticencias: bool = True) -> str:
    texto = str(texto or "").strip()
    if len(texto) <= n:
        return texto
    corte = texto[:n - 1].rsplit(" ", 1)[0].rstrip(",;:—–- ")
    return (corte or texto[:n - 1]) + ("…" if reticencias else "")


# Rascunho de agente, nao trabalho (mesmos nomes do RUIDO do despachante).
RASCUNHO = re.compile(r"^(resposta\.md|\.tarefa_.*\.md|\.conf_.*\.md|tarefa-.*\.md)$")


def o_que_mudou(resposta: str) -> str:
    """A primeira frase com conteudo da fala do agente, pulando as genericas
    ("Implementado.", "Alterações propostas:", "Mudanças:") em vez de desistir."""
    for linha in str(resposta or "").splitlines():
        crua = linha.strip()
        if not crua or crua.startswith(("```", "|")):
            continue
        limpa = _sem_markdown(crua).lstrip("•·").strip()
        if len(limpa) < 25 or crua.rstrip("*").endswith(":"):
            continue
        if re.match(r"(?i)(ainda sem sa[ií]da|aguardo|n[aã]o alterei|nada foi commitado)", limpa):
            continue
        return re.split(r"(?<=[.!?])\s+", limpa, maxsplit=1)[0].rstrip(".")
    return ""


def _e_teste(caminho: str) -> bool:
    nome = caminho.replace("\\", "/").rsplit("/", 1)[-1]
    partes = caminho.replace("\\", "/").split("/")
    return (nome.startswith("test_") or nome.endswith("_test.py") or nome == "conftest.py"
            or "tests" in partes[:-1] or "testes" in partes[:-1])


def arquivos_em_resumo(arquivos, n: int = 3) -> str:
    """"postar.py, reparo.py + 1 teste": os arquivos que a entrega mudou, curto."""
    arquivos = [a for a in arquivos
                if not RASCUNHO.match(a.replace("\\", "/").rsplit("/", 1)[-1])]
    codigo = [a for a in arquivos if not _e_teste(a)]
    testes = len(arquivos) - len(codigo)
    nomes = []
    for a in codigo:
        nome = a.replace("\\", "/").rsplit("/", 1)[-1]
        if nome not in nomes:
            nomes.append(nome)
    texto = ", ".join(nomes[:n])
    if len(nomes) > n:
        texto += f" e mais {len(nomes) - n}"
    if testes:
        texto += (" + " if texto else "") + (f"{testes} teste" + ("s" if testes > 1 else ""))
    return texto


def _e_pedido(estado: dict, titulo: str) -> bool:
    """Pedido (do app ou do Grimorio): o titulo e o pedido CRU ou a pergunta,
    e a fala final do orquestrador narra a espera ("O trabalhador x está
    rodando. Aguardo…"), nao o que mudou (medido em 05/10 nos 12 pedidos)."""
    return bool(GRIMORIO.match(titulo)) or str(estado.get("cargo") or "") == "orquestrador"


def titulo_do_commit(estado: dict, resposta: str, original: dict | None = None,
                     resposta_original: str = "", arquivos=(),
                     limite: int = ASSUNTO_MAX) -> str:
    """O assunto do commit: o que a tarefa FEZ, em uma linha.

    05/10: "Implementado." e "Ainda sem saída; aguardo…" viraram mensagem de
    commit porque a fala do agente vinha antes; o titulo resolve as tarefas
    comuns. Nos pedidos o titulo e o pedido cru do Adrian ("Preciso que você
    conserte…") ou a PERGUNTA do Grimorio («IA olha de novo a parte
    consertada?», cortada no meio aos 120), e a fala final so narra a espera:
    ali o assunto e o no do Grimorio (ou o pedido curto) com os ARQUIVOS que
    mudaram. O integrador ("Integrar pedido-x") herda o assunto da entrega
    original, com os arquivos dele."""
    titulo = _sem_markdown(estado.get("titulo"))
    cargo = str(estado.get("cargo") or "")
    if cargo == "integrador" or titulo.startswith("Integrar "):
        alvo = titulo[len("Integrar "):].strip() if titulo.startswith("Integrar ") else ""
        sufixo = " (integrado)"
        if original:
            base = titulo_do_commit(original, resposta_original or resposta, arquivos=arquivos,
                                    limite=limite - len(sufixo))
            return base + sufixo
        mudou = arquivos_em_resumo(arquivos) or o_que_mudou(resposta)
        if mudou:
            return _cortar_na_palavra(f"{alvo + ': ' if alvo else ''}{mudou}", limite)
    if _e_pedido(estado, titulo):
        grimorio = GRIMORIO.match(titulo)
        # pedido cru: a primeira oracao ("Preciso que você conserte o
        # problema do Picasso"); o pedido inteiro vai no corpo
        quem = (grimorio.group(1).strip() if grimorio else _cortar_na_palavra(
            re.split(r"[,.;!?]\s", titulo, maxsplit=1)[0], 60, reticencias=False))
        mudou = arquivos_em_resumo(arquivos)
        if not mudou:
            mudou = grimorio.group(2).strip() if grimorio else o_que_mudou(resposta)
        if quem and mudou:
            return _cortar_na_palavra(f"{quem}: {mudou}", limite)
    if len(titulo) >= 6:
        return _cortar_na_palavra(titulo, limite)
    return _cortar_na_palavra(o_que_mudou(resposta)
                              or primeira_linha(resposta, titulo or str(estado.get("id") or "")),
                              limite)


def medida_dos_testes(testes: dict | None) -> str:
    """O que o vigia MEDIU, curto: "1395 passed, 21 skipped" (sem o tempo)."""
    testes = testes or {}
    if testes.get("sem_testes"):
        return "só documentação, sem testes"
    resumo = " ".join(str(testes.get("resumo") or "").split()).strip("= ")
    resumo = re.sub(r"\s+in\s+[\d.]+s\b.*$", "", resumo)
    if resumo:
        return resumo[:80]
    return "testes verdes" if testes.get("ok") else f"testes com código {testes.get('codigo')}"


def mensagem_do_commit(estado: dict, resposta: str, testes: dict | None,
                       original: dict | None = None, resposta_original: str = "",
                       arquivos=()) -> str:
    """Assunto com o que mudou e o que foi medido; corpo com o pedido (quando
    o titulo era a pergunta), quem fez, o comando que o vigia rodou, os
    arquivos e o comeco da fala do agente (menos a do orquestrador, que so
    narra a espera)."""
    arquivos = list(arquivos or [])
    assunto = titulo_do_commit(estado, resposta, original, resposta_original, arquivos)
    medido = medida_dos_testes(testes)
    linhas = [f"{assunto} — {medido}", ""]
    for fonte in (original, estado):
        titulo = _sem_markdown((fonte or {}).get("titulo"))
        if fonte and _e_pedido(fonte, titulo):
            achado = GRIMORIO.match(titulo)
            linhas.append(f"Pedido: «{achado.group(2).strip() if achado else titulo[:300]}»"
                          + (f" (Grimório {achado.group(1).strip()})" if achado else ""))
            break
    cmd = str((testes or {}).get("cmd") or "").strip()
    linhas.append(f"Feito pelo {nome_da_ia(estado)} ({estado.get('id')}), validado pelo vigia"
                  + (f": `{cmd}` deu {medido}." if cmd else "."))
    if arquivos:
        linhas.append("Arquivos: " + ", ".join(arquivos[:20])
                      + (f" e mais {len(arquivos) - 20}" if len(arquivos) > 20 else ""))
    if str(estado.get("cargo") or "") == "orquestrador":
        resposta = ""
    corpo, total = [], 0
    for linha in str(resposta or "").splitlines():
        linha = linha.rstrip()
        if linha.strip().startswith("```"):
            break
        if total + len(linha) > 900 or len(corpo) >= 12:
            break
        corpo.append(linha)
        total += len(linha)
    corpo_txt = "\n".join(corpo).strip()
    if corpo_txt:
        linhas += ["", corpo_txt]
    linhas += ["", CO_AUTOR, ""]
    return "\n".join(linhas)


def veredito(resposta: str) -> str:
    """APROVADO / REPROVADO do conferente, ou a primeira linha da resposta."""
    achado = re.search(r"\b(REPROVAD[OA]|APROVAD[OA])\b", str(resposta or ""))
    if achado:
        return achado.group(1)[:-1] + "O"
    return primeira_linha(resposta, "sem veredito escrito")


def falha_de_infra(texto: str) -> bool:
    return bool(INFRA.search(str(texto or "")))


def comando_de_teste(estado: dict, arquivos: list[str]) -> str | None:
    """O comando dos testes: o do estado (`testes_cmd`, ou o `testes` em texto,
    ou o `cmd` da ultima rodada), senao o pytest das pastas de topo mudadas.
    None = so documentacao (nada para testar)."""
    for bruto in (estado.get("testes_cmd"), estado.get("testes")):
        if isinstance(bruto, str) and bruto.strip():
            return bruto.strip()
        if isinstance(bruto, dict) and str(bruto.get("cmd") or "").strip():
            return str(bruto["cmd"]).strip()
    pastas = []
    for caminho in arquivos:
        partes = str(caminho).replace("\\", "/").split("/")
        if len(partes) < 2 or partes[0] in SEM_TESTE or partes[0].startswith("."):
            continue
        if partes[0] not in pastas:
            pastas.append(partes[0])
    if not pastas:
        return None
    return "python -m pytest " + " ".join(pastas) + " -q"


def precisa_da_prova_de_tela(arquivos: list[str]) -> bool:
    """A casca ou a CSP mudou: o pytest precisa abrir o app de verdade."""
    caminhos = [str(a).replace("\\", "/") for a in arquivos]
    return any(caminho == "remoto/api_http.py" or caminho.startswith("remoto/app/")
               for caminho in caminhos)


def servicos_afetados(arquivos: list[str], servicos: dict) -> list[str]:
    saida = []
    for nome, ficha in servicos.items():
        for modulo in ficha.get("modulos", []):
            prefixo = str(modulo).rstrip("/") + "/"
            if any(str(a).replace("\\", "/").startswith(prefixo) for a in arquivos):
                saida.append(nome)
                break
    return saida


def delegados_citados(item: dict, delegados: list[dict]) -> list[dict]:
    """Os delegados que o titulo de um item da Mesa cita: o id literal, ou
    todas as palavras do id ("armas 16F" cita `armas-16f`). So os criados
    a partir de 30 min antes do item (um id antigo de palavra comum, como
    `coordenador`, nao conta)."""
    titulo = _norm(item.get("titulo"))
    palavras = set(titulo.split())
    desde = _data(item.get("desde"))
    saida = []
    for d in delegados:
        ident = str(d.get("id") or "")
        criado = _data(d.get("criado_em"))
        if desde and criado and criado < desde - timedelta(minutes=30):
            continue
        tokens = [t for t in ident.split("-") if len(t) >= 2]
        if ident.replace("-", " ") in titulo or (tokens and all(t in palavras for t in tokens)):
            saida.append(d)
    return saida


# ========================================================== efeitos reais
def _git(args, repo, entrada=None):
    return subprocess.run(["git", *args], cwd=str(repo), input=entrada, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          creationflags=NO_WINDOW)


def arquivos_sujos(arquivos: list[str], repo=None) -> list[str]:
    """Os arquivos do diff que ja tem mudanca nao commitada na arvore principal
    (aplicar por cima levaria a mudanca de outro para dentro do commit)."""
    if not arquivos:
        return []
    if repo is None:
        from remoto import delegar
        repo = delegar.repo()
    feito = _git(["status", "--porcelain", "--", *arquivos], repo)
    if feito.returncode != 0:
        raise RuntimeError("git status falhou: " + (feito.stderr or "").strip()[:200])
    return [linha[3:].strip() for linha in feito.stdout.splitlines() if linha.strip()]


def commitar_por_caminho(arquivos: list[str], mensagem: str, repo=None) -> str:
    """`git add` + `git commit -- <arquivos>` (so eles), com nova tentativa
    quando o index.lock esta preso. Devolve o hash curto."""
    if repo is None:
        from remoto import delegar
        repo = delegar.repo()
    feito = _git(["add", "-A", "--", *arquivos], repo)
    if feito.returncode != 0:
        raise RuntimeError("git add falhou: " + (feito.stderr or "").strip()[:300])
    for tentativa in range(6):
        feito = _git(["commit", "-F", "-", "--", *arquivos], repo, entrada=mensagem)
        if feito.returncode == 0:
            break
        erro = (feito.stderr or feito.stdout or "").strip()
        if "index.lock" not in erro or tentativa == 5:
            raise RuntimeError("git commit falhou: " + erro[:300])
        time.sleep(2)
    return _git(["rev-parse", "--short", "HEAD"], repo).stdout.strip()


def corrigir_no_fundo(ident: str, texto: str) -> None:
    """`python -m remoto.delegar corrigir --id X --texto arq --fundo`."""
    from remoto import delegar
    arquivo = delegar.pasta_da(ident) / "vigia_correcao.md"
    arquivo.write_text(texto, encoding="utf-8")
    delegar.no_fundo(["corrigir", "--id", ident, "--texto", str(arquivo)], ident)


def codex_pode_comecar(delegados: list[dict], agora: datetime) -> str:
    """'' se uma rodada do Codex pode comecar agora; senao, o motivo (as
    mesmas guardas do despachante, para a correcao nao ser recusada calada)."""
    from remoto import delegar
    try:
        config = delegar.ler_config()
        if delegar._janela(config["janela_sem_comecar"], agora):
            de, ate = config["janela_sem_comecar"]
            return f"nada começa entre :{de:02d} e :{ate:02d}"
        rodando = sum(1 for d in delegados if d.get("situacao") == "rodando")
        if rodando >= int(config.get("delegados_paralelo") or 1):
            return "outro delegado está rodando"
        delegar.conferir_teto(config)
    except Exception as exc:                                  # noqa: BLE001
        return str(exc) or type(exc).__name__
    return ""


def _proibido_real() -> str:
    try:
        from remoto import claude_estado
        return claude_estado.motivo_proibido()
    except Exception as exc:                                  # noqa: BLE001
        return f"não li o interruptor do Claude ({type(exc).__name__})"


def _classificar_real(duvida: str, contexto: str) -> dict:
    from . import cerebro
    return cerebro.classificar_duvida(duvida, contexto)


def _propostas_real() -> int:
    from . import cerebro
    return len(cerebro.propostas_pendentes())


def _em_uso_real() -> set:
    """Os delegados que um pedido ABERTO ainda cita (trabalhador e conferente):
    a faxina nao os toca, porque o pedido retoma o MESMO trabalhador depois de
    uma queda (ate dias, no limite semanal). Arquivo ilegivel LEVANTA: sem
    saber quem esta em uso, nada e limpo (o `_ler` dos pedidos daria lista
    vazia e tudo pareceria livre)."""
    from . import pedidos
    caminho = pedidos._arquivo()
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:
        return set()
    dados = json.loads(texto)
    em_uso = set()
    for pedido in (dados.get("pedidos") or []) if isinstance(dados, dict) else []:
        if not isinstance(pedido, dict) or pedido.get("situacao") in pedidos.FINAIS:
            continue
        for chave in ("trabalhador", "conferente"):
            if pedido.get(chave):
                em_uso.add(str(pedido[chave]))
    return em_uso


def _servicos_real() -> dict:
    from .supervisor import carregar_servicos
    return carregar_servicos()


# ================================================================== o vigia
class VigiaTrabalho:
    def __init__(self, *, delegar=None, orquestrador=None, decisoes=None, commitar=None,
                 sujos=None, corrigir=None, pode_corrigir=None, avisar=None, evento=None,
                 relogio=datetime.now, seguro=None, pedir_reinicio=None, proibido=None,
                 classificar=None, propostas=None, servicos=None, memoria=None,
                 em_uso=None):
        if delegar is None:
            from remoto import delegar
        if orquestrador is None:
            from remoto import orquestrador
        if decisoes is None:
            from remoto import decisoes
        self.delegar, self.orquestrador, self.decisoes = delegar, orquestrador, decisoes
        self.commitar = commitar or commitar_por_caminho
        self.sujos = sujos or arquivos_sujos
        self.corrigir = corrigir or corrigir_no_fundo
        self.pode_corrigir = pode_corrigir or codex_pode_comecar
        self.avisar = avisar or (lambda texto: False)
        self.evento = evento or (lambda tipo, texto: None)
        self.relogio = relogio
        # sem criterio de momento seguro, nunca e seguro (falha fechado)
        self.seguro = seguro or (lambda: (False, "sem critério de momento seguro"))
        self.pedir_reinicio = pedir_reinicio or (lambda nome: None)
        self.proibido = proibido or _proibido_real
        self.classificar = classificar or _classificar_real
        self.propostas = propostas or _propostas_real
        self.servicos = servicos or _servicos_real
        self.em_uso = em_uso or _em_uso_real
        self.caminho_memoria = Path(memoria) if memoria else pasta() / "trabalho_memoria.json"
        self.ultimo = {}

    def _aplica_sozinho(self) -> bool:
        """`{"vigia_aplica": false}` no config.json do coordenador para a
        entrega pronta e deixa o aplicar para o orquestrador (o padrao, como
        pedido em 02/10, e aplicar)."""
        try:
            dados = json.loads((self.caminho_memoria.parent / "config.json").read_text(
                encoding="utf-8"))
        except (OSError, ValueError):
            return True
        return not (isinstance(dados, dict) and dados.get("vigia_aplica") is False)

    # ------------------------------------------------------------ memoria
    def _ler_memoria(self) -> dict:
        try:
            dados = json.loads(self.caminho_memoria.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            dados = {}
        if not isinstance(dados, dict):
            dados = {}
        for chave, padrao in (("vistos", []), ("olho", {}), ("aplicados", {}),
                              ("corrigidos", {}), ("esperando", {}), ("parados", []),
                              ("nos", {}), ("titulos", []), ("novidades", []),
                              ("duvidas", []), ("fechados", []), ("conferencias", {}),
                              ("sem_mudanca", {}), ("sujo_desde", {}), ("sujo_avisado", {}),
                              ("retestes", {}),
                              ("arquivados", []), ("faxina", [])):
            if not isinstance(dados.get(chave), type(padrao)):
                dados[chave] = padrao
        return dados

    def _gravar_memoria(self, mem: dict) -> None:
        for chave, n in (("vistos", 300), ("parados", 300), ("titulos", 300),
                         ("novidades", 60), ("duvidas", 300), ("fechados", 300),
                         ("arquivados", 300), ("faxina", 100)):
            mem[chave] = mem[chave][-n:]
        for chave in ("conferencias", "sem_mudanca", "retestes", "sujo_avisado"):
            mem[chave] = dict(list(mem[chave].items())[-100:])
        mem["nos"] = dict(sorted(mem["nos"].items())[-10:])
        self.caminho_memoria.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho_memoria.with_name(f".{self.caminho_memoria.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.caminho_memoria)

    def _novidade(self, mem: dict, tipo: str, texto: str) -> None:
        mem["novidades"].append({"em": _iso(self.relogio()), "tipo": tipo, "texto": texto})
        self.evento(f"trabalho_{tipo}", texto)

    def _olho(self, mem: dict, ident: str, motivo: str, integrar: bool = True) -> None:
        mem["olho"][ident] = {"motivo": motivo[:400], "em": _iso(self.relogio())}
        mem["esperando"].pop(ident, None)
        mem["sujo_desde"].pop(ident, None)
        mem["sujo_avisado"].pop(ident, None)
        # 03/10/2026, o Adrian: "VOCE AINDA BARRA O CODEX DE RESOLVER O PROBLEMA".
        # Entrega travada nao fica esperando ninguem: um INTEGRADOR e contratado
        # na hora para juntar, testar e entregar de novo (uma vez por entrega).
        # Arvore principal suja nao e caso de integrador: a entrega dele
        # bateria na mesma mudanca nao commitada.
        integrador = self._contratar_integrador(mem, ident, motivo) if integrar else None
        texto = (f"entrega {ident} travou ({motivo[:300]}); "
                 + (f"o integrador {integrador} já está resolvendo" if integrador
                    else "precisa de olho"))
        self.avisar("⚠ " + texto)
        self._novidade(mem, "olho", texto)

    def _ia_do_integrador(self) -> str:
        """Claude so com ele liberado E abaixo do teto da Mesa (sessao ou semana).

        05/10/2026: integrar-pedido-66e4ba54 foi contratado como Claude com a
        semana no limite e morreu em "falhou" (rate_limit_event "rejected")."""
        try:
            if self.proibido():
                return "codex"
        except Exception:                                     # noqa: BLE001
            return "codex"
        ler_uso = getattr(self.orquestrador, "ler_uso", None)
        if callable(ler_uso):
            try:
                if (ler_uso() or {}).get("passou_teto"):
                    return "codex"
            except Exception:                                 # noqa: BLE001
                pass
        return "claude"

    def _contratar_integrador(self, mem: dict, ident: str, motivo: str) -> str | None:
        if ident.startswith("integrar-") or "não mudou nada" in motivo or PASSAGEIRA.search(motivo):
            # nao integra integrador; vazio vira permissao; trava ocupada passa sozinha
            return None
        feitos = mem.setdefault("integrando", {})
        if ident in feitos:
            return feitos[ident]
        criar, no_fundo = getattr(self.delegar, "criar", None), getattr(self.delegar, "no_fundo", None)
        if not (callable(criar) and callable(no_fundo)):
            return None
        novo = ("integrar-" + ident)[:40]
        try:
            pasta = self.delegar.pasta_da(ident)
            pedido = pasta / "integrar.md"
            pedido.write_text(
                f"A entrega `{ident}` travou no vigia: {motivo}\n\n"
                f"O diff dela está em `{pasta / 'diff.patch'}` e a tarefa original em "
                f"`{pasta / 'tarefa.md'}`. Na SUA worktree (que saiu do HEAD atual):\n"
                "1. aplique com `git apply -3`; resolva cada conflito JUNTANDO os dois lados "
                "(as duas funções têm de ficar); a casca do app (`painel-casca-vN`) fica na "
                "maior versão + 1, igual em `remoto/app/sw.js` e `remoto/test_app_vila_objetos.py`;\n"
                "2. se o motivo foi teste falhando, conserte o código (não o teste, a não ser "
                "que o teste seja instável de tempo — aí dê folga);\n"
                "3. rode os testes da parte com -p no:cacheprovider até ficarem verdes.\n"
                "A sua entrega É a entrega original, já integrada. Não desista: se precisar de "
                "algo fora do escopo, peça permissão (.permissao.json).\n", encoding="utf-8")
            ia = self._ia_do_integrador()
            permitidos = (self.delegar.ler_estado(ident).get("permitidos") or ["**"])
            criar(novo, pedido, permitidos, ia=ia, cargo="integrador",
                  titulo=f"Integrar {ident}")
            no_fundo(["rodar", "--id", novo], novo)
        except Exception as exc:                              # noqa: BLE001
            self.evento("trabalho_integrador", f"{ident}: não contratei o integrador ({exc})")
            return None
        feitos[ident] = novo
        self._novidade(mem, "integrando", f"{ident} travou; contratei o integrador {novo}")
        return novo

    # --------------------------------------------------------------- passo
    def passo(self) -> dict:
        agora = self.relogio()
        mem = self._ler_memoria()
        mem.setdefault("desde", _iso(agora))
        proibido = self.proibido()
        delegados = self._listar()
        mesa = self._mesa()
        self._faxina_olho(delegados, mem, agora)
        if not proibido:
            for d in delegados:
                if d.get("situacao") == "terminou" and not d.get("aplicado") and not d.get("limpo"):
                    if str(d.get("cargo") or "") == "conferente":
                        # o conferente SO LE: o desfecho dele e o veredito, nunca
                        # uma entrega para coletar, aplicar ou commitar (05/10)
                        self._conferencia(d, mem)
                        continue
                    try:
                        self._cuidar(d, mem, mesa, delegados, agora)
                    except Exception as exc:                  # noqa: BLE001
                        self._olho(mem, str(d.get("id")), f"o vigia tropeçou: {exc}")
            delegados = self._listar()
            self._fechar_mesa(mesa, delegados, mem)
            self._faxina_delegados(delegados, mem, agora)
            delegados = self._listar()
        self._mesa_parada(mesa, mem, agora)
        trabalho = self._retrato(delegados, mesa, mem, agora, proibido)
        self._resumo(trabalho, mem, agora)
        trabalho["resumo_em"] = mem.get("resumo_em")
        self._gravar_memoria(mem)
        self.ultimo = trabalho
        return trabalho

    def _listar(self) -> list[dict]:
        try:
            return [d for d in self.delegar.listar() if isinstance(d, dict)]
        except Exception:                                     # noqa: BLE001
            return []

    def _mesa(self) -> dict:
        try:
            estado = self.orquestrador.ler_estado()
        except Exception:                                     # noqa: BLE001
            return {"agora": [], "fila": [], "ilegivel": True}
        return {"agora": list(estado.get("agora") or []), "fila": list(estado.get("fila") or [])}

    # ----------------------------------------------------------- entregas
    def _resposta(self, ident: str) -> str:
        try:
            return (self.delegar.pasta_da(ident) / "resposta.md").read_text(encoding="utf-8")
        except (OSError, AttributeError):
            return ""

    def _cauda_testes(self, ident: str) -> str:
        try:
            texto = (self.delegar.pasta_da(ident) / "testes.log").read_text(
                encoding="utf-8", errors="replace")
        except (OSError, AttributeError):
            return ""
        return texto[-CAUDA_TESTES:]

    # ---------------------------------------------------------- faxinas
    def _faxina_olho(self, delegados: list, mem: dict, agora: datetime) -> None:
        """`olho` e `corrigidos` so guardam o que ainda pede atencao: sai o que
        foi aplicado, limpo, sumiu da lista ou tem mais de 48 h (05/10: 10 itens
        em `olho`, 5 de conferentes e 2 ja integrados). O que sai por idade vai
        para `arquivados`, e o vigia nao volta a mexer nele."""
        por_id = {str(d.get("id")): d for d in delegados}
        lista_ok = bool(delegados)          # lista vazia (falha de leitura) nao e "sumiu"
        for chave in ("olho", "corrigidos"):
            for ident in list(mem[chave]):
                d = por_id.get(ident)
                quando = _data((mem[chave][ident] or {}).get("em"))
                velho = quando is not None and (agora - quando).total_seconds() > OLHO_VALIDADE_S
                resolvido = d is not None and (d.get("aplicado") or d.get("limpo"))
                sumiu = d is None and lista_ok
                if resolvido or sumiu or velho:
                    mem[chave].pop(ident, None)
                    if velho and not resolvido and not sumiu and ident not in mem["arquivados"]:
                        mem["arquivados"].append(ident)

    def _faxina_delegados(self, delegados: list, mem: dict, agora: datetime) -> None:
        """Worktree de delegado encerrado ha mais de 6 h e sem commit proprio
        sai (05/10: 11 worktrees `delegar/*` paradas, `limpar` so rodava depois
        de aplicar). Entram: falhou ou negado, conferente encerrado e
        integrador aplicado ou caido. Nunca um que um pedido aberto cita (ele
        retoma o mesmo trabalhador), nem um em `olho` ou esperando."""
        limpar = getattr(self.delegar, "limpar", None)
        commits = getattr(self.delegar, "commits_a_frente", None)
        if not (callable(limpar) and callable(commits)):
            return
        candidatos = []
        for d in delegados:
            did, cargo = str(d.get("id") or ""), str(d.get("cargo") or "")
            situacao = d.get("situacao")
            if not did or d.get("limpo") or situacao not in TERMINAIS:
                continue
            fim = _data(d.get("fim"))
            if fim is None or (agora - fim).total_seconds() < FAXINA_APOS_S:
                continue
            if did in mem["olho"] or did in mem["esperando"]:
                continue
            if not (situacao in ("falhou", "negado")
                    or cargo == "conferente"
                    or (cargo == "integrador" and (d.get("aplicado")
                                                   or situacao in ("falhou", "negado", "parado")))):
                continue
            candidatos.append(d)
        try:
            em_uso = set(self.em_uso())
        except Exception as exc:                              # noqa: BLE001
            self.evento("trabalho_faxina", f"não li os pedidos; não limpo nada ({exc})")
            return
        abandonar = getattr(self.delegar, "abandonar", None)
        for d in delegados:
            did = str(d.get("id") or "")
            criado = _data(d.get("criado_em"))
            if (not callable(abandonar) or not did or did in em_uso or d.get("situacao") != "criado"
                    or criado is None or (agora - criado).total_seconds() < 24 * 3600):
                continue
            if commits(d) != 0:
                self._olho(mem, did, "precisa de olho: criado antigo com mudança não aplicada",
                           integrar=False)
                continue
            try:
                abandonar(did)
            except Exception as exc:                          # noqa: BLE001
                self.evento("trabalho_faxina", f"{did}: não abandonei ({exc})")
                continue
            self.evento("trabalho_faxina", f"abandonei {did} (criado há mais de 24 h)")
        if not candidatos:
            return
        livres = [d for d in candidatos if str(d["id"]) not in em_uso]
        for d in livres[:FAXINA_POR_PASSO]:
            did = str(d["id"])
            try:
                if commits(d) != 0:
                    continue
                if str(d.get("cargo") or "") != "conferente":
                    try:
                        self.delegar.coletar(did)     # o diff.patch fica na pasta do estado
                    except Exception:                 # noqa: BLE001
                        pass
                limpar(did)
            except Exception as exc:                          # noqa: BLE001
                self.evento("trabalho_faxina", f"{did}: não limpei ({exc})")
                continue
            mem["faxina"].append({"id": did, "em": _iso(self.relogio()),
                                  "situacao": d.get("situacao"), "cargo": d.get("cargo") or ""})
            self.evento("trabalho_faxina", f"limpei a worktree de {did} ({d.get('situacao')})")

    # ----------------------------------------------------------- entregas
    def _conferencia(self, d: dict, mem: dict) -> None:
        did = str(d["id"])
        if did in mem["conferencias"]:
            return
        texto = veredito(self._resposta(did))
        mem["conferencias"][did] = {"em": _iso(self.relogio()), "veredito": texto[:200]}
        if did not in mem["vistos"]:
            mem["vistos"].append(did)
        self._novidade(mem, "conferencia", f"conferente {did}: {texto[:200]}")

    def _cuidar(self, d: dict, mem: dict, mesa: dict, delegados: list, agora: datetime) -> None:
        did = str(d["id"])
        if SUJA_MARCA in str((mem["olho"].get(did) or {}).get("motivo") or ""):
            # Arvore suja nao e defeito da entrega: um `olho` com esse motivo
            # (de antes de 05/10) volta a ser avaliado, e aplica quando limpar.
            mem["olho"].pop(did, None)
        if did in mem["olho"] or did in mem["arquivados"] or did in mem["sem_mudanca"]:
            return
        if str(d.get("fim") or "") < mem["desde"]:
            mem.setdefault("antigos", [])
            if did not in mem["antigos"]:
                mem["antigos"].append(did)
            return
        if did not in mem["vistos"]:
            mem["vistos"].append(did)
            self._novidade(mem, "terminou", f"o {nome_da_ia(d)} terminou {did}")
            self._duvida(d, mem, mesa, agora)
        corr = mem["corrigidos"].get(did)
        if corr and str(d.get("fim") or "") <= corr.get("em", ""):
            # a correcao foi pedida e ainda nao rodou (ou foi recusada calada)
            pedida = _data(corr.get("em"))
            if pedida and (agora - pedida).total_seconds() > CORRECAO_ESPERA_S:
                self._olho(mem, did, "a correção pedida às "
                           f"{corr['em'][11:16]} não começou")
            return
        try:
            resumo = self.delegar.coletar(did)
        except Exception as exc:                              # noqa: BLE001
            if recusa_passageira(exc):
                mem["esperando"][did] = f"coletar o diff espera: {str(exc)[:300]}"
                return
            self._olho(mem, did, f"não consegui coletar o diff: {exc}")
            return
        motivos = list(resumo.get("motivos") or [])
        if not resumo.get("ok") and motivos and all("não mudou nada" in m for m in motivos):
            # sem mudanca = nada a aplicar: nao e defeito nem caso de integrador
            mem["sem_mudanca"][did] = {"em": _iso(self.relogio())}
            mem["esperando"].pop(did, None)
            self._novidade(mem, "sem_mudanca", f"{did} terminou sem mudança: nada a aplicar")
            return
        if not resumo.get("ok"):
            self._olho(mem, did, "o validador recusou: " + "; ".join(motivos))
            return
        arquivos = [a["caminho"] for a in resumo.get("arquivos") or []]
        ok, motivo = self.seguro()
        if not ok:
            mem["esperando"][did] = motivo
            return
        testes = d.get("testes") if isinstance(d.get("testes"), dict) else None
        if not testes or testes.get("diff_sha") != resumo.get("sha"):
            testes = self._testar(d, mem, arquivos)
            if testes is None:
                return
        if not testes.get("ok") and not testes.get("sem_testes") \
                and mem["retestes"].get(did) != resumo.get("sha") \
                and falha_de_infra(self._cauda_testes(did)):
            # pasta presa (WinError 5/145/183) ou Tcl sem biblioteca: e o
            # ambiente, nao a entrega. Roda de novo UMA vez por diff.
            mem["retestes"][did] = resumo.get("sha")
            self.evento("trabalho_reteste", f"{did}: falha de ambiente nos testes; rodo de novo")
            testes = self._testar(d, mem, arquivos)
            if testes is None:
                return
        if not testes.get("ok"):
            self._vermelho(d, mem, delegados, agora, resumo, testes)
            return
        ok, motivo = self.seguro()                 # os testes levaram minutos
        if not ok:
            mem["esperando"][did] = motivo
            return
        from .pedidos import na_janela_das_postagens
        if na_janela_das_postagens(agora):
            mem["esperando"][did] = "janela da postagem: aplicar e reiniciar depois"
            return
        if not self._aplica_sozinho():
            mem["esperando"][did] = ("pronta para aplicar (validador e testes ok); o aplicar "
                                     "sozinho está desligado no config.json do coordenador")
            return
        try:
            repo_da = getattr(self.delegar, "repo_da", None)
            if callable(repo_da):
                repo_tarefa = Path(repo_da(d))       # o principal, mesmo de estado antigo
            else:
                repo_tarefa = Path(d["repo"]) if d.get("repo") else None
            if repo_tarefa is None and hasattr(self.delegar, "repo"):
                repo_tarefa = self.delegar.repo()
            sujos = self.sujos(arquivos, repo=repo_tarefa) if repo_tarefa else self.sujos(arquivos)
        except Exception as exc:                              # noqa: BLE001
            self._olho(mem, did, f"não consegui conferir a árvore principal: {exc}")
            return
        if sujos:
            # alguem esta mexendo nesses arquivos agora: espera dizendo QUAL
            # arvore (04/10: o conf-log-cp1252 esperou calado por "arvore
            # principal suja" e a suja era uma worktree). Passado o prazo,
            # avisa UMA vez e SEGUE esperando: ir para `olho` era sem volta
            # (05/10, conferente), e a principal quase sempre tem arquivo M.
            arvore = str(repo_tarefa) if repo_tarefa else "principal"
            desde = _data(mem["sujo_desde"].setdefault(did, _iso(agora))) or agora
            prazo = desde + timedelta(seconds=ESPERA_SUJA_S)
            lista = ", ".join(sujos[:5])
            if agora >= prazo:
                motivo = (f"a árvore {arvore} segue com {SUJA_MARCA} em {lista} desde "
                          f"{desde:%d/%m %H:%M}; commite ou descarte e a entrega volta sozinha")
                if did not in mem["sujo_avisado"]:
                    mem["sujo_avisado"][did] = _iso(agora)
                    texto = f"entrega {did} parada: {motivo}"
                    self.avisar("⚠ " + texto)
                    self._novidade(mem, "olho", texto)
                mem["esperando"][did] = motivo + " (avisado)"
                return
            mem["esperando"][did] = (f"a árvore {arvore} tem {SUJA_MARCA} em {lista} "
                                     f"(esperando desde {desde:%H:%M}; às {prazo:%H:%M} "
                                     "aviso o Adrian)")
            return
        mem["sujo_desde"].pop(did, None)
        mem["sujo_avisado"].pop(did, None)
        try:
            aplicado = self.delegar.aplicar(did, sem_testes=bool(testes.get("sem_testes")))
        except Exception as exc:                              # noqa: BLE001
            texto = str(exc)
            if texto.startswith("aplicar só fora") or texto.startswith("publicação em voo"):
                mem["esperando"][did] = texto
            else:
                self._olho(mem, did, f"aplicar recusou: {texto}")
            return
        arquivos = list(aplicado.get("arquivos") or arquivos)
        mensagem = mensagem_do_commit(d, self._resposta(did), testes,
                                      *self._original_do_integrador(d), arquivos=arquivos)
        try:
            commit = (self.commitar(arquivos, mensagem, repo=repo_tarefa)
                      if repo_tarefa else self.commitar(arquivos, mensagem))
        except Exception as exc:                              # noqa: BLE001
            self._olho(mem, did, f"aplicado na árvore, mas o commit falhou ({exc}); "
                       "os arquivos estão lá sem commit: " + ", ".join(arquivos[:8]))
            return
        mem["esperando"].pop(did, None)
        mem["aplicados"][did] = {"commit": commit, "em": _iso(self.relogio()),
                                 "arquivos": arquivos[:20]}
        self._novidade(mem, "aplicado", f"entrega {did} aplicada: {commit}")
        try:
            servicos = self.servicos()
        except Exception:                                     # noqa: BLE001
            servicos = {}
        for nome in servicos_afetados(arquivos, servicos):
            self.pedir_reinicio(nome)
        if any(str(a).replace("\\", "/").startswith("coordenador/") for a in arquivos):
            self.pedir_reinicio("coordenador")
        try:
            self.delegar.limpar(did)
        except Exception as exc:                              # noqa: BLE001
            self.evento("trabalho_limpar", f"{did}: não limpei a worktree ({exc})")

    def _testar(self, d: dict, mem: dict, arquivos: list[str]) -> dict | None:
        """Os testes da area; None = nao rodou (ja foi para `olho`, ou para
        `esperando` quando a recusa passa sozinha)."""
        did = str(d["id"])
        cmd = comando_de_teste(d, arquivos)
        if cmd is None:
            return {"ok": True, "sem_testes": True, "resumo": "só documentação"}
        if precisa_da_prova_de_tela(arquivos):
            # `delegar.testar` usa cmd.exe: a prova, marcada para nao
            # abrir Chrome nas suites comuns, entra nesta entrega.
            cmd = "set NF_TESTE_NAVEGADOR=1&& " + cmd
        try:
            return self.delegar.testar(did, cmd)
        except Exception as exc:                              # noqa: BLE001
            if recusa_passageira(exc):
                # outra rodada segurando o testar.lock (o vigia e o
                # orquestrador testando juntos): tenta no proximo passo
                mem["esperando"][did] = f"os testes esperam: {str(exc)[:300]}"
                return None
            self._olho(mem, did, f"não consegui rodar os testes: {exc}")
            return None

    def _original_do_integrador(self, d: dict) -> tuple[dict | None, str]:
        """O estado e a fala da entrega que o integrador juntou (para o
        assunto do commit dizer o que mudou, nao "Integrar pedido-x")."""
        titulo = str(d.get("titulo") or "")
        if str(d.get("cargo") or "") != "integrador" and not titulo.startswith("Integrar "):
            return None, ""
        alvo = titulo[len("Integrar "):].strip() if titulo.startswith("Integrar ") else ""
        if not alvo and str(d.get("id") or "").startswith("integrar-"):
            alvo = str(d["id"])[len("integrar-"):]
        ler = getattr(self.delegar, "ler_estado", None)
        if not alvo or not callable(ler):
            return None, ""
        try:
            original = ler(alvo)
        except Exception:                                     # noqa: BLE001
            return None, ""
        if not isinstance(original, dict) or not original.get("titulo"):
            return None, ""
        return original, self._resposta(alvo)

    def _vermelho(self, d, mem, delegados, agora, resumo, testes) -> None:
        did = str(d["id"])
        if did in mem["corrigidos"]:
            self._olho(mem, did, "os testes falharam de novo depois da correção: "
                       + str(testes.get("resumo") or f"código {testes.get('codigo')}"))
            return
        motivo = self.pode_corrigir(delegados, agora)
        if motivo:
            mem["esperando"][did] = f"testes falharam; a correção espera: {motivo}"
            return
        cauda = self._cauda_testes(did)
        texto = ("Os testes da sua entrega falharam no vigia do coordenador.\n\n"
                 f"Comando: `{testes.get('cmd') or '?'}` (código {testes.get('codigo')}).\n\n"
                 f"Os últimos {CAUDA_TESTES} caracteres da saída:\n\n```\n{cauda}\n```\n\n"
                 "Conserte mexendo só nos caminhos permitidos, rode os testes de novo "
                 "(com -p no:cacheprovider) e responda como antes.")
        try:
            self.corrigir(did, texto)
        except Exception as exc:                              # noqa: BLE001
            self._olho(mem, did, f"os testes falharam e a correção não abriu: {exc}")
            return
        mem["corrigidos"][did] = {"em": _iso(self.relogio()), "sha": resumo.get("sha")}
        mem["esperando"].pop(did, None)
        self._novidade(mem, "corrigindo", f"testes de {did} falharam; pedi UMA correção")

    # ------------------------------------------------------------- duvidas
    def _projeto(self, ident: str, mesa: dict) -> str:
        projetos = getattr(self.decisoes, "PROJETOS", ())
        for item in mesa.get("agora") or []:
            if any(d.get("id") == ident for d in delegados_citados(item, [{"id": ident}])):
                if item.get("parte") in projetos:
                    return item["parte"]
        return "geral"

    def _duvida(self, d: dict, mem: dict, mesa: dict, agora: datetime) -> None:
        did = str(d["id"])
        if did in mem["duvidas"]:
            return
        mem["duvidas"].append(did)
        duvida = extrair_duvida(self._resposta(did))
        if not duvida:
            return
        hoje = agora.date().isoformat()
        if int(mem["nos"].get(hoje, 0)) >= NOS_POR_DIA:
            self.avisar(f"❔ dúvida na entrega do Codex {did} (já são {NOS_POR_DIA} nós "
                        f"hoje; não criei outro): {duvida[:600]}")
            return
        contexto = f"Entrega do Codex {did}: {d.get('titulo') or ''}"
        try:
            ficha = self.classificar(duvida, contexto)
        except Exception as exc:                              # noqa: BLE001
            self.avisar(f"❔ dúvida na entrega do Codex {did} (sem cérebro para "
                        f"classificar: {exc}): {duvida[:600]}")
            return
        if not isinstance(ficha, dict) or not ficha.get("precisa_decisao"):
            return                                   # detalhe tecnico: nao vira no
        titulo = str(ficha.get("titulo") or "").strip()[:80]
        pergunta = str(ficha.get("pergunta") or "").strip()
        opcoes = [o for o in ficha.get("opcoes") or []
                  if isinstance(o, dict) and str(o.get("rotulo") or "").strip()][:3]
        if not titulo or not pergunta or len(opcoes) < 2:
            self.avisar(f"❔ dúvida de produto na entrega {did}, mas o cérebro não "
                        f"redigiu um nó completo: {duvida[:400]}")
            return
        chave = _norm(titulo)
        try:
            existentes = {_norm(i.get("titulo")) for i in self.decisoes.carregar().values()}
        except Exception:                                     # noqa: BLE001
            existentes = set()
        if chave in existentes or chave in mem["titulos"]:
            return
        projeto = self._projeto(did, mesa)
        contexto_no = (str(ficha.get("contexto") or "").strip() + f" (entrega do Codex {did}; "
                       "nó criado pelo vigia de trabalho do coordenador)").strip()
        brutas = [{"id": str(o.get("id") or ""), "rotulo": str(o["rotulo"]).strip()[:80],
                   "descricao": str(o.get("descricao") or "").strip()[:300]} for o in opcoes]
        pedido = re.fullmatch(r"(pedido-[0-9a-f]+)(?:-\d+)?", did)
        try:
            item, _ = self.decisoes.adicionar_e_commitar(projeto, titulo, pergunta, brutas,
                                                         contexto=contexto_no,
                                                         pedido=pedido.group(1) if pedido else "")
        except Exception as exc:                              # noqa: BLE001
            self.avisar(f"❔ não consegui criar o nó da dúvida de {did}: {exc}")
            return
        mem["nos"][hoje] = int(mem["nos"].get(hoje, 0)) + 1
        mem["titulos"].append(chave)
        self._novidade(mem, "no", f"nó novo no Grimório: {projeto}/{item.get('id')} — {titulo}")

    # ---------------------------------------------------------------- Mesa
    def _fechar_mesa(self, mesa: dict, delegados: list, mem: dict) -> None:
        for item in mesa.get("agora") or []:
            if not re.search(r"\bCODEX\b", str(item.get("titulo") or "")):
                continue
            citados = delegados_citados(item, delegados)
            if not citados or not all(d.get("aplicado") for d in citados):
                continue
            commits = [mem["aplicados"].get(d["id"], {}).get("commit") for d in citados]
            commits = [c for c in commits if c]
            try:
                self.orquestrador.agente_fim(
                    item["id"], situacao="concluido", commits=commits,
                    relato_final="entregas do Codex aplicadas: "
                    + ", ".join(d["id"] for d in citados) + " (fechado pelo vigia)")
            except Exception as exc:                          # noqa: BLE001
                self.evento("trabalho_mesa", f"não fechei {item.get('id')}: {exc}")
                continue
            mem["fechados"].append(item["id"])
            self._novidade(mem, "mesa", f"fechei na Mesa: {item.get('titulo')}")

    def _mesa_parada(self, mesa: dict, mem: dict, agora: datetime) -> None:
        for item in mesa.get("agora") or []:
            ref = item.get("relato_em") or item.get("desde")
            quando = _data(ref)
            if quando is None:
                continue
            minutos = int((agora - quando).total_seconds() // 60)
            if minutos * 60 < PARADA_S:
                continue
            chave = f"{item.get('id')}@{ref}"
            if chave in mem["parados"]:
                continue
            mem["parados"].append(chave)
            texto = f"tarefa «{item.get('titulo')}» ({item.get('id')}) parada há {minutos} min"
            self.avisar("⏸ " + texto)
            self._novidade(mem, "parada", texto)

    # -------------------------------------------------------------- resumo
    def _espera_adrian(self) -> dict:
        saida = {"decisoes": None, "titulos": [], "propostas": None, "ids": None}
        try:
            itens = self.decisoes.carregar()
            pendentes = [i for i in itens.values() if i.get("situacao") in ("pendente", "a_rever")]
            saida["decisoes"] = len(pendentes)
            saida["titulos"] = [f"{i.get('projeto')}/{i.get('titulo')}" for i in pendentes][:5]
            saida["ids"] = [f"{i.get('projeto')}/{i.get('id') or i.get('titulo')}"
                            for i in pendentes]
        except Exception:                                     # noqa: BLE001
            pass
        try:
            saida["propostas"] = int(self.propostas())
        except Exception:                                     # noqa: BLE001
            pass
        return saida

    def _retrato(self, delegados, mesa, mem, agora, proibido) -> dict:
        agora_mesa = []
        for item in mesa.get("agora") or []:
            quando = _data(item.get("relato_em") or item.get("desde"))
            agora_mesa.append({"id": item.get("id"), "parte": item.get("parte"),
                               "titulo": item.get("titulo"),
                               "sem_relato_min": int((agora - quando).total_seconds() // 60)
                               if quando else None})
        aplicados = sorted(({"id": k, **v} for k, v in mem["aplicados"].items()),
                           key=lambda x: x.get("em", ""))[-10:]
        fila = mesa.get("fila") or []
        return {"em": _iso(agora), "proibido": proibido,
                "rodando": [{"id": d.get("id"), "titulo": d.get("titulo")}
                            for d in delegados if d.get("situacao") == "rodando"],
                "mesa": agora_mesa, "aplicados": aplicados,
                "olho": [{"id": k, **v} for k, v in mem["olho"].items()][-10:],
                "esperando": dict(mem["esperando"]),
                "corrigindo": [k for k in mem["corrigidos"] if k not in mem["aplicados"]
                               and k not in mem["olho"]],
                "antigos": list(mem.get("antigos", []))[-20:],
                "conferencias": [{"id": k, **v} for k, v in mem["conferencias"].items()][-10:],
                "faxina": list(mem["faxina"])[-10:],
                "espera_adrian": self._espera_adrian(),
                "fila": {"n": len(fila), "primeiros": [f"[{f.get('parte')}] {f.get('item')}"
                                                       for f in fila[:3]]},
                "novidades": len(mem["novidades"])}

    def _espera_nova(self, espera: dict, mem: dict, agora: datetime) -> None:
        """So o que CHEGOU para ele vira novidade, e dito com todas as letras.

        Ate 04/10/2026 qualquer mudanca na contagem (0 -> 1 -> 0, ou uma
        leitura do Grimorio que falhava e dava None) virava a novidade
        "mudou o que espera você" — que nem aparecia no texto. O resumo saia
        so com as linhas fixas, e a ultima era sempre "Fila: ...; primeiro:
        [builds] Som real nas 15 builds de estoque ainda com som sintetizado".
        Medido: 14 Andamentos em 48 h, 9 terminando nesse item parado e 3
        sem novidade nenhuma.
        """
        mem.pop("espera_assinatura", None)
        partes = []
        # DECISAO: pelo id, e cada uma so uma vez — o mesmo no indo e
        # voltando de "pendente" nao e no novo.
        ids = espera.get("ids")
        if ids is not None:
            vistos = mem.get("espera_vistos")
            primeira = not isinstance(vistos, list)
            vistos = [] if primeira else vistos
            novos = [i for i in ids if i not in vistos]
            mem["espera_vistos"] = (vistos + novos)[-300:]
            if novos and not primeira:
                partes.append(f"{len(novos)} decisão(ões) nova(s) no Grimório")
        # PROPOSTA do cerebro: so contagem que SOBE (uma leitura que falha
        # da None e nao conta como mudanca).
        propostas = espera.get("propostas")
        if propostas is not None:
            anterior = mem.get("espera_propostas")
            mem["espera_propostas"] = propostas
            if isinstance(anterior, int) and propostas > anterior:
                partes.append(f"{propostas - anterior} proposta(s) nova(s) do cérebro")
        if partes:
            mem["novidades"].append({"em": _iso(agora), "tipo": "espera",
                                     "texto": " e ".join(partes) + " esperando você"})

    def _resumo(self, trabalho: dict, mem: dict, agora: datetime) -> None:
        espera = trabalho["espera_adrian"]
        self._espera_nova(espera, mem, agora)
        icones = {"aplicado": "✓", "terminou": "⏹", "olho": "⚠", "corrigindo": "🔧",
                  "no": "🌳", "mesa": "📌", "parada": "⏸", "integrando": "🧩",
                  "espera": "📥", "conferencia": "🔎", "sem_mudanca": "∅"}
        # Novidade que nao aparece no texto nao justifica mensagem.
        mem["novidades"] = [n for n in mem["novidades"] if n.get("tipo") in icones]
        if not mem["novidades"]:
            return
        ultimo = _data(mem.get("resumo_em"))
        if ultimo and (agora - ultimo).total_seconds() < RESUMO_A_CADA_S:
            return
        linhas = [f"🛰 Andamento ({agora:%H:%M})"]
        for n in mem["novidades"][-12:]:
            linhas.append(f"{icones[n['tipo']]} {n['texto']}")
        rodando = len(trabalho["rodando"])
        linhas.append(f"Rodando: {rodando} delegado(s) do Codex, "
                      f"{len(trabalho['mesa'])} tarefa(s) na Mesa")
        if espera.get("decisoes") is not None or espera.get("propostas") is not None:
            linhas.append(f"Espera você: {espera.get('decisoes') or 0} decisão(ões) no "
                          f"Grimório, {espera.get('propostas') or 0} proposta(s) do cérebro")
        # A FILA SO QUANDO MUDA. O mesmo "primeiro da fila" parado desde 30/09
        # repetido em toda mensagem era a "notificacao infinita do re-render".
        fila = trabalho["fila"]
        linha_fila = (f"Fila: {fila['n']} item(ns)"
                      + (f"; primeiro: {fila['primeiros'][0]}" if fila["primeiros"] else ""))
        if linha_fila != mem.get("fila_dita"):
            linhas.append(linha_fila)
            mem["fila_dita"] = linha_fila
        if trabalho["proibido"]:
            linhas.append(f"({trabalho['proibido']}: só observo)")
        texto = "\n".join(linhas)
        self.avisar(texto)
        self.evento("trabalho_resumo", texto.replace("\n", " · ")[:300])
        mem["resumo_em"] = _iso(agora)
        mem["novidades"] = []
