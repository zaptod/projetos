# -*- coding: utf-8 -*-
"""O que a janela flutuante sabe do sistema. Funcoes PURAS, sem Tk.

Tudo aqui e LEITURA. A janela nunca publica, nunca gera, nunca pega trava:
ela so olha. Isso vale inclusive para as travas, e por um motivo concreto —
`travas.ocupada()` responde pegando a trava por um instante. Com os
trabalhadores usando `trava(nome)` sem espera, o instante em que a janela
segura o arquivo e um instante em que o dono de verdade ouve "ocupado" e
desiste da rodada. A sonda daqui (`trava_ocupada`) so tenta LER o byte que o
dono tranca: no Windows, byte trancado por outro processo nao le.

Separado da interface de proposito: estas sao as regras que decidem o que
aparece na tela ("esta trabalhando?", "que horas sai o proximo?", "esse
erro ainda vale?"), e sao elas que os testes exercitam sem abrir janela.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ------------------------------------------------------------------ predios
# A ordem e a ordem na tela. `casa` nao e fabrica: e onde os bots moram, e
# onde cai o trabalho que nao tem predio proprio (rodada de historias,
# estudo de canal alheio).
PREDIOS = {
    "deepseek": {"rotulo": "DeepSeek", "emoji": "🐋", "faz": "roteiro"},
    "chatgpt": {"rotulo": "ChatGPT", "emoji": "🤖", "faz": "roteiro"},
    "gemini": {"rotulo": "Gemini", "emoji": "✨", "faz": "roteiro e parecer"},
    "picasso": {"rotulo": "PicassoIA", "emoji": "🎨", "faz": "imagens"},
    "digen": {"rotulo": "Digen", "emoji": "🎥", "faz": "vídeo do payoff"},
    "estudio": {"rotulo": "Estúdio", "emoji": "🎬", "faz": "render"},
    "arena": {"rotulo": "Arena", "emoji": "⚔", "faz": "lutas"},
    "youtube": {"rotulo": "YouTube", "emoji": "▶", "faz": "upload"},
    "tiktok": {"rotulo": "TikTok", "emoji": "♪", "faz": "post"},
    "bot": {"rotulo": "Bot", "emoji": "📡", "faz": "Telegram"},
}
CASA = {"rotulo": "Vila", "emoji": "🏠", "faz": "rodadas"}

# Fabrica do diario -> predio. O que nao esta aqui e nem e predio cai na casa.
_FABRICA_PARA_PREDIO = {
    "conferencia": "youtube",
    "apurador": "bot",
    "remoto": "bot",
    "telegram": "bot",
}
# Servico de trava de perfil -> predio.
_SERVICO_PARA_PREDIO = {
    "youtube_web": "youtube", "youtube": "youtube", "tiktok": "tiktok",
    "picasso": "picasso", "digen": "digen", "chatgpt": "chatgpt",
    "gemini": "gemini", "deepseek": "deepseek",
}

# Erro mais velho que isto sai da tela: o erro de ontem ja virou diario.
JANELA_DE_ERROS_S = 2 * 3600
# Sem `ok`/`erro` depois disto e sem PID que responda, o inicio e de um
# processo morto (a mesma regra do `atividade.INICIO_VELHO_S`).
INICIO_VELHO_S = 2 * 3600


def rotulo(predio: str) -> str:
    return (PREDIOS.get(predio) or CASA)["rotulo"]


def emoji(predio: str) -> str:
    return (PREDIOS.get(predio) or CASA)["emoji"]


def predio_do_evento(evento: dict) -> str:
    """Em que predio este evento do diario acontece. `casa` quando nenhum."""
    fabrica = str(evento.get("fabrica") or "").lower()
    if fabrica in PREDIOS:
        return fabrica
    if fabrica in ("publicacao", "conferencia"):
        texto = f"{evento.get('etapa', '')} {evento.get('detalhe', '')}".lower()
        return "tiktok" if "tiktok" in texto else "youtube"
    return _FABRICA_PARA_PREDIO.get(fabrica, "casa")


# -------------------------------------------------------------------- tempo
def quando(ts) -> datetime | None:
    """O carimbo do diario (ISO, UTC) em hora LOCAL ingenua. None se ruim."""
    try:
        valor = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    if valor.tzinfo is not None:
        valor = valor.astimezone().replace(tzinfo=None)
    return valor


def duracao(segundos: float | None) -> str:
    """`1h53`, `12 min`, `40 s` — curto o bastante para caber num balao."""
    if segundos is None:
        return "—"
    s = max(0, int(segundos))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min"
    horas, resto = divmod(s, 3600)
    if horas >= 48:
        return f"{horas // 24} dias"
    return f"{horas}h{resto // 60:02d}"


def contagem(segundos: float) -> str:
    """A contagem regressiva: `em 4h 42min`, `em 3:05`, `agora`."""
    s = int(segundos)
    if s <= 0:
        return "agora"
    if s < 600:
        return f"em {s // 60}:{s % 60:02d}"
    if s < 3600:
        return f"em {s // 60} min"
    horas, resto = divmod(s, 3600)
    return f"em {horas}h {resto // 60:02d}min"


def _grade() -> tuple:
    try:
        from builds import grade
        return tuple(grade.GRADE)
    except Exception:                                        # noqa: BLE001
        # Copia de reserva, so para a janela abrir sem o workspace. Quem
        # manda e `builds.grade`; se divergir, a importacao acima ganha.
        return ((0, 37), (6, 37), (9, 37), (12, 7), (15, 37), (17, 57),
                (20, 37), (21, 37), (22, 37), (23, 37))


def proximo_horario(agora: datetime, grade: tuple | None = None) -> datetime:
    """O proximo horario da grade DEPOIS de `agora` (vira o dia se preciso)."""
    grade = tuple(grade or _grade())
    hoje = agora.replace(second=0, microsecond=0)
    for h, m in sorted(grade):
        alvo = hoje.replace(hour=h, minute=m)
        if alvo > agora:
            return alvo
    h, m = sorted(grade)[0]
    return (hoje + timedelta(days=1)).replace(hour=h, minute=m)


# ------------------------------------------------------------------ leitura
def ler_cauda(caminho, max_bytes: int = 96_000) -> list[str]:
    """As ultimas linhas de um arquivo que OUTRO processo esta escrevendo.

    Nunca levanta: arquivo sumido, preso ou pela metade devolve o que der.
    A primeira linha depois do `seek` e descartada (quase sempre cortada),
    e a ultima so entra se terminou com quebra — linha pela metade e o
    escritor no meio de um `write`.
    """
    try:
        with open(caminho, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            tamanho = fh.tell()
            inicio = max(0, tamanho - int(max_bytes))
            fh.seek(inicio)
            bruto = fh.read()
    except OSError:
        return []
    texto = bruto.decode("utf-8", errors="replace")
    linhas = texto.split("\n")
    if inicio > 0 and linhas:
        linhas = linhas[1:]
    # O ultimo pedaco do `split` e "" quando o arquivo termina em quebra, e a
    # linha pela metade quando nao termina: nos dois casos, fica de fora.
    if linhas:
        linhas = linhas[:-1]
    return [l.rstrip("\r") for l in linhas]


def ler_diario(caminho, max_bytes: int = 256_000) -> list[dict]:
    """Eventos do `atividade.jsonl`, do mais VELHO para o mais novo.

    Tolerante: linha que nao e JSON (a metade de um write concorrente, lixo
    de edicao manual) e pulada, nao derruba a leitura.
    """
    eventos = []
    for linha in ler_cauda(caminho, max_bytes):
        linha = linha.strip()
        if not linha.startswith("{"):
            continue
        try:
            evento = json.loads(linha)
        except ValueError:
            continue
        if isinstance(evento, dict):
            eventos.append(evento)
    return eventos


def ler_json(caminho, padrao=None):
    try:
        with open(caminho, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return padrao


def ler_ledger(caminho) -> list[dict]:
    """O `publicados.jsonl` inteiro, tolerante como o diario."""
    saida = []
    try:
        with open(caminho, encoding="utf-8", errors="replace") as fh:
            for linha in fh:
                linha = linha.strip()
                if not linha.startswith("{"):
                    continue
                try:
                    dado = json.loads(linha)
                except ValueError:
                    continue
                if isinstance(dado, dict):
                    saida.append(dado)
    except OSError:
        return []
    return saida


# ------------------------------------------------------------------- travas
def trava_ocupada(caminho) -> bool | None:
    """Alguem segura esta trava? Responde LENDO, nunca trancando.

    O dono tranca o byte 0 com `msvcrt.locking`; ler um byte trancado por
    outro processo falha com PermissionError. True = ocupada, False = livre,
    None = nao deu para saber (arquivo sumiu).
    """
    try:
        with open(caminho, "rb") as fh:
            fh.read(1)
        return False
    except PermissionError:
        return True
    except OSError:
        return None


def travas_ocupadas(pasta) -> list[str]:
    """Os nomes (sem `.lock`) das travas seguras agora."""
    try:
        arquivos = sorted(Path(pasta).glob("*.lock"))
    except OSError:
        return []
    saida = []
    for arquivo in arquivos:
        if arquivo.stem.startswith("teste_"):
            continue
        if trava_ocupada(arquivo):
            saida.append(arquivo.stem)
    return saida


_HEX = re.compile(r"^[0-9a-f]{8}$")


def ler_trava(nome: str) -> dict | None:
    """`perfil__tiktok__historinhas__9cfe3e40` -> predio, conta, o que e.

    None para o que nao interessa na tela (ledger, teste, sessao de edicao).
    """
    nome = str(nome)
    if nome.startswith("teste_") or nome.startswith("ledger__") \
            or nome == "sessao_editando":
        return None
    if nome == "remoto__bot":
        return {"predio": "bot", "conta": "", "texto": "bot no ar"}
    if nome == "remoto__apurador":
        return {"predio": "bot", "conta": "", "texto": "apurando um erro"}
    if nome == "historias__auto":
        return {"predio": "casa", "conta": "",
                "texto": "rodada automática de histórias"}
    if nome == "fila_identidade":
        return {"predio": "casa", "conta": "", "texto": "fila de builds"}
    if nome.startswith("historias__render__"):
        ref = nome[len("historias__render__"):]
        return {"predio": "estudio", "conta": "", "texto": f"render {ref}"}
    partes = nome.split("__")
    if partes[0] == "perfil" and len(partes) >= 2:
        partes = partes[1:]
        if len(partes) > 1 and _HEX.match(partes[-1]):
            partes = partes[:-1]
        servico = partes[0]
        conta = "__".join(partes[1:]) or "principal"
    elif len(partes) == 2:
        servico, conta = partes
    else:
        return None
    predio = _SERVICO_PARA_PREDIO.get(servico)
    if predio is None:
        return {"predio": "", "conta": conta,
                "texto": f"{servico} ({conta}) em uso"}
    return {"predio": predio, "conta": conta,
            "texto": f"conta {conta} em uso"}


def contas_por_predio(ocupadas: list[str]) -> dict:
    """{predio: [conta, ...]} das contas de navegador em uso agora."""
    saida: dict[str, list] = {}
    for nome in ocupadas:
        info = ler_trava(nome)
        if not info or not info["predio"] or info["predio"] in ("casa", "bot"):
            continue
        if info["texto"].startswith("render "):
            continue
        contas = saida.setdefault(info["predio"], [])
        if info["conta"] and info["conta"] not in contas:
            contas.append(info["conta"])
    return saida


# ------------------------------------------------------------ o que acontece
def ref_legivel(ref: str) -> str:
    """`historia_00016:celular:p05` -> `historia_00016 p05`."""
    partes = [p for p in str(ref or "").replace("|", ":").split(":")
              if p and p not in ("celular", "build")]
    return " ".join(partes)


_VERBOS = {"publicar.tiktok": "post", "publicar.youtube": "upload",
           "publicar.corte": "corte", "imagens": "imagens"}


def balao(evento: dict, limite: int = 30) -> str:
    """O texto curto em cima do bot: `render historia_00017`."""
    etapa = str(evento.get("etapa") or "")
    ref = ref_legivel(evento.get("ref") or "")
    if etapa and ref:
        texto = f"{_VERBOS.get(etapa, etapa)} {ref}"
    else:
        texto = str(evento.get("detalhe") or etapa or "trabalhando")
    texto = " ".join(texto.split())
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


def _pid_vivo(pid) -> bool | None:
    try:
        from builds.atividade import _vivo
        return _vivo(pid)
    except Exception:                                        # noqa: BLE001
        return None


def trabalhos_abertos(eventos: list[dict], agora_utc: datetime | None = None,
                      vivo=None) -> list[dict]:
    """Os `inicio` sem `ok`/`erro` depois, de processo que ainda existe.

    A chave e (fabrica, canal) — a mesma do `atividade.estado_por_canal`:
    builds e historias trabalhando no mesmo provedor sao dois bots.
    """
    vivo = vivo or _pid_vivo
    agora_utc = agora_utc or datetime.now(timezone.utc)
    ultimo: dict[tuple, dict] = {}
    for evento in eventos:
        if evento.get("status") == "log" or not evento.get("fabrica"):
            continue
        ultimo[(evento.get("fabrica"), evento.get("canal") or "")] = evento
    abertos = []
    for (fabrica, canal), evento in ultimo.items():
        if evento.get("status") != "inicio":
            continue
        try:
            inicio = datetime.fromisoformat(str(evento.get("ts")))
            if inicio.tzinfo is None:
                inicio = inicio.replace(tzinfo=timezone.utc)
            idade = (agora_utc - inicio).total_seconds()
        except (TypeError, ValueError):
            continue
        situacao = vivo(evento.get("pid"))
        if situacao is False:
            continue
        if situacao is None and idade > INICIO_VELHO_S:
            continue
        abertos.append({
            "predio": predio_do_evento(evento), "fabrica": fabrica,
            "canal": canal, "texto": balao(evento, 40),
            "balao": balao(evento), "detalhe": evento.get("detalhe", ""),
            "pid": evento.get("pid"), "desde": quando(evento.get("ts")),
            "ha_s": idade})
    abertos.sort(key=lambda t: t["ha_s"], reverse=True)
    return abertos


def erros_recentes(eventos: list[dict], agora_utc: datetime | None = None,
                   janela_s: float = JANELA_DE_ERROS_S) -> list[dict]:
    """Os erros das ultimas `janela_s`, do mais NOVO para o mais velho."""
    agora_utc = agora_utc or datetime.now(timezone.utc)
    saida = []
    for evento in reversed(eventos):
        if evento.get("status") != "erro":
            continue
        try:
            ts = datetime.fromisoformat(str(evento.get("ts")))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        idade = (agora_utc - ts).total_seconds()
        if idade > janela_s:
            # O diario e quase ordenado (varios processos escrevendo): muito
            # alem da janela, o resto e todo mais velho.
            if idade > janela_s * 6:
                break
            continue
        dado = dict(evento)
        dado["predio"] = predio_do_evento(evento)
        dado["quando"] = quando(evento.get("ts"))
        dado["ha_s"] = idade
        saida.append(dado)
    return saida


# Evento solto (vistoria, rodada, `ok` de render) nesta janela tambem conta
# como trabalho: o Estudio registra muita coisa so como `log`, sem `inicio`,
# e a tela dizia "tudo parado" com o render acontecendo (17/09/2026).
JANELA_RECENTE_S = 10 * 60


def _idade(evento: dict, agora_utc: datetime) -> float | None:
    try:
        ts = datetime.fromisoformat(str(evento.get("ts")))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (agora_utc - ts).total_seconds()


def atividade_recente(eventos: list[dict], agora_utc: datetime | None = None,
                      janela_s: float = JANELA_RECENTE_S,
                      vivo=None) -> dict:
    """{predio: {evento, balao, texto, ha_s}} do que aconteceu ha pouco.

    Erro fica de fora (tem o proprio estado). O balao prefere o ultimo
    evento que diz A QUAL coisa se refere (`ref`): "vistoria historia_09002
    p1" diz mais que "rodada: historia", que veio depois.
    """
    agora_utc = agora_utc or datetime.now(timezone.utc)
    vivo = vivo or _pid_vivo
    por_predio: dict[str, list] = {}
    for evento in reversed(eventos):
        idade = _idade(evento, agora_utc)
        if idade is None:
            continue
        if idade > janela_s:
            if idade > janela_s * 6:
                break
            continue
        if evento.get("status") == "erro" or not evento.get("fabrica"):
            continue
        # `inicio` de processo que MORREU e trabalho abortado, nao atividade.
        if evento.get("status") == "inicio" and vivo(evento.get("pid")) is False:
            continue
        por_predio.setdefault(predio_do_evento(evento), []).append(
            (idade, evento))
    saida = {}
    for predio, lista in por_predio.items():
        idade, evento = next(((i, e) for i, e in lista if e.get("ref")),
                             lista[0])
        saida[predio] = {"evento": evento, "balao": balao(evento),
                         "texto": balao(evento, 40), "ha_s": idade,
                         "pid": evento.get("pid")}
    return saida


def linha_do_diario(evento: dict) -> tuple[str, str]:
    """(texto, marca) de uma linha do feed. A marca e a cor na tela."""
    momento = quando(evento.get("ts"))
    hora = momento.strftime("%H:%M:%S") if momento else "--:--:--"
    predio = predio_do_evento(evento)
    status = str(evento.get("status") or "")
    simbolo = {"inicio": "▶", "ok": "✓", "erro": "✗", "log": "·"}.get(status,
                                                                     "·")
    canal = str(evento.get("canal") or "")
    canal = {"historias": "hist", "builds": "build"}.get(canal, canal[:5])
    detalhe = " ".join(str(evento.get("detalhe") or "").split())
    texto = f"{hora} {simbolo} {rotulo(predio):<9.9} {canal:<5} {detalhe}"
    marca = {"inicio": "inicio", "ok": "ok", "erro": "erro"}.get(status,
                                                                 "fraco")
    return texto, marca


def estado_dos_predios(abertos: list[dict], erros: list[dict],
                       ocupadas: list[str],
                       recentes: dict | None = None) -> dict:
    """{predio: {status, balao, trabalhos, contas, erro, recente}}.

    status: trabalhando (`inicio` aberto) > erro > recente (evento nos
    ultimos minutos) > ocioso. `recente` tambem leva o bot ao predio.
    """
    contas = contas_por_predio(ocupadas)
    recentes = recentes or {}
    saida = {}
    for nome in PREDIOS:
        trabalhos = [t for t in abertos if t["predio"] == nome]
        erro = next((e for e in erros if e["predio"] == nome), None)
        recente = recentes.get(nome)
        if erro is not None and recente is not None \
                and recente["ha_s"] < erro["ha_s"]:
            erro = None          # houve atividade DEPOIS do erro
        if trabalhos:
            status = "trabalhando"
            texto = trabalhos[0]["balao"]
            if len(trabalhos) > 1:
                texto = f"{texto} +{len(trabalhos) - 1}"
        elif erro is not None:
            status, texto = "erro", "❗ " + balao(erro, 26)
        elif recente is not None:
            status, texto = "recente", recente["balao"]
        else:
            status, texto = "ocioso", "💤"
        saida[nome] = {"status": status, "balao": texto,
                       "trabalhos": trabalhos, "contas": contas.get(nome, []),
                       "erro": erro, "recente": recente}
    # O bot do Telegram nao escreve `inicio` no diario: ele "trabalha" o dia
    # inteiro. Quem diz se ele esta vivo e a trava dele.
    if "remoto__bot" in ocupadas and saida["bot"]["status"] == "ocioso":
        saida["bot"]["status"] = "no_ar"
        saida["bot"]["balao"] = "no ar"
    return saida


# ---------------------------------------------------------------- processos
def classificar_processo(linha_de_comando: str) -> dict | None:
    """O que e este python? None para a propria janela."""
    cmd = str(linha_de_comando or "")
    baixo = cmd.lower().replace("\\", "/")
    if "painel.flutuante" in baixo or "vila_flutuante" in baixo:
        return None
    if re.search(r"-m\s+remoto\b", baixo):
        return {"tipo": "bot", "emoji": "📡", "quem": "Bot do Telegram"}
    if "main.py auto" in baixo:
        return {"tipo": "historias", "emoji": "📚",
                "quem": "Histórias (rodada automática)"}
    if "postar.py" in baixo:
        return {"tipo": "postar", "emoji": "📤", "quem": "Postagem da grade"}
    if "vila.editor" in baixo:
        return {"tipo": "oficina", "emoji": "🎨", "quem": "Oficina da Vila"}
    if re.search(r"-m\s+painel\b", baixo) or "painel_ui" in baixo:
        return {"tipo": "painel", "emoji": "🏘", "quem": "Painel"}
    if "pytest" in baixo or "testar.py" in baixo or "unittest" in baixo:
        return {"tipo": "testes", "emoji": "🧪", "quem": "Testes"}
    if "/scratchpad/" in baixo:
        # Script de uma sessao de desenvolvimento. O nome do arquivo basta
        # (o caminho e comprido e nao diz nada). A REMESSA e excecao: e
        # producao de historias rodando por la, e conta como trabalho.
        arquivo = baixo.rsplit("/", 1)[-1].split()[0].strip('"')
        if arquivo.startswith("remessa"):
            return {"tipo": "remessa", "emoji": "📚",
                    "quem": f"Remessa de histórias ({arquivo})"}
        return {"tipo": "sessao", "emoji": "·",
                "quem": f"sessão de desenvolvimento ({arquivo})"}
    achado = re.search(r"([\w.-]+\.py)\b(.*)$", cmd.replace("\\", "/"))
    if achado:
        resto = achado.group(2).split()
        sub = next((p for p in resto if not p.startswith("-")), "")
        return {"tipo": "script", "emoji": "🐍",
                "quem": f"{achado.group(1)} {sub}".strip()}
    modulo = re.search(r"-m\s+([\w.]+)", cmd)
    if modulo:
        return {"tipo": "modulo", "emoji": "🐍", "quem": f"-m {modulo.group(1)}"}
    return {"tipo": "python", "emoji": "🐍", "quem": "python"}


def ler_processos_json(texto: str) -> list[dict]:
    """A saida do `Get-CimInstance | ConvertTo-Json`: um objeto ou uma lista."""
    try:
        dado = json.loads(texto or "null")
    except ValueError:
        return []
    if isinstance(dado, dict):
        dado = [dado]
    if not isinstance(dado, list):
        return []
    saida = []
    for item in dado:
        if not isinstance(item, dict):
            continue
        try:
            pid = int(item.get("ProcessId"))
        except (TypeError, ValueError):
            continue
        inicio = None
        bruto = str(item.get("Inicio") or "")
        if bruto:
            try:
                inicio = datetime.fromisoformat(bruto[:19])
            except ValueError:
                inicio = None
        saida.append({"pid": pid, "pai": item.get("ParentProcessId"),
                      "cmd": str(item.get("CommandLine") or ""),
                      "inicio": inicio})
    return saida


# Processo destes tipos VIVO ja e trabalho, com ou sem etapa no diario.
PRODUCAO = ("historias", "postar", "remessa")
# A ordem na lista: producao, o bot, o resto; desenvolvimento por ultimo.
_ORDEM_TIPO = {"historias": 0, "postar": 0, "remessa": 0, "diario": 0,
               "bot": 1, "painel": 2, "oficina": 2, "script": 2,
               "modulo": 2, "python": 2, "sessao": 3, "testes": 3}


def linhas_vivas(processos: list[dict], abertos: list[dict],
                 agora: datetime, meu_pid: int | None = None,
                 eventos: list[dict] | None = None,
                 agora_utc: datetime | None = None) -> list[dict]:
    """Uma linha por processo vivo: quem, o que, desde quando.

    O "o que" vem do diario: os `inicio` abertos daquele PID ou, sem eles,
    o ultimo evento dele nos ultimos minutos. Processo de PRODUCAO vivo e
    trabalho mesmo sem nada no diario. Trabalho aberto cujo PID nao esta na
    lista ganha linha propria — melhor repetido que escondido.
    """
    agora_utc = agora_utc or datetime.now(timezone.utc)
    ultimo_do_pid: dict = {}
    for evento in eventos or []:
        if evento.get("pid") is None or evento.get("status") == "erro":
            continue
        idade = _idade(evento, agora_utc)
        if idade is not None and idade <= JANELA_RECENTE_S:
            ultimo_do_pid[str(evento["pid"])] = (idade, evento)
    linhas = []
    pids = set()
    for proc in processos:
        if meu_pid is not None and proc["pid"] == meu_pid:
            continue
        tipo = classificar_processo(proc["cmd"])
        if tipo is None:
            continue
        pids.add(proc["pid"])
        dele = [t for t in abertos if _mesmo_pid(t.get("pid"), proc["pid"])]
        recente = ultimo_do_pid.get(str(proc["pid"]))
        if dele:
            oque = " · ".join(f"{t['texto']} ({rotulo(t['predio'])})"
                              for t in dele)
        elif recente is not None:
            idade, evento = recente
            oque = (f"{balao(evento, 40)} "
                    f"({rotulo(predio_do_evento(evento))}, "
                    f"há {duracao(idade)})")
        elif tipo["tipo"] == "bot":
            oque = "ouvindo o celular e avisando erros"
        elif tipo["tipo"] in PRODUCAO:
            oque = "rodando (sem etapa no diário ainda)"
        else:
            oque = "sem etapa no diário"
        inicio = proc.get("inicio")
        ativo = (bool(dele) or recente is not None
                 or tipo["tipo"] in PRODUCAO) and tipo["tipo"] != "sessao"
        linhas.append({
            "emoji": tipo["emoji"], "quem": tipo["quem"], "oque": oque,
            "desde": inicio.strftime("%H:%M") if inicio else "?",
            "ha": duracao((agora - inicio).total_seconds()) if inicio else "",
            "pid": proc["pid"], "ativo": ativo, "tipo": tipo["tipo"],
            "ordem": inicio or agora})
    for t in abertos:
        if any(_mesmo_pid(t.get("pid"), p) for p in pids):
            continue
        desde = t.get("desde")
        linhas.append({
            "emoji": emoji(t["predio"]), "quem": rotulo(t["predio"]),
            "oque": t["texto"], "pid": t.get("pid"), "ativo": True,
            "desde": desde.strftime("%H:%M") if desde else "?",
            "ha": duracao(t.get("ha_s")), "tipo": "diario",
            "ordem": desde or agora})
    # Producao primeiro, desenvolvimento por ultimo; dentro de cada grupo,
    # quem trabalha antes, e o mais antigo antes.
    linhas.sort(key=lambda l: (_ORDEM_TIPO.get(l["tipo"], 2), not l["ativo"],
                               l["ordem"]))
    return linhas


def _mesmo_pid(a, b) -> bool:
    try:
        return int(a) == int(b)
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------- publicados
def publicado(linha: dict) -> bool:
    """A MESMA regra do `metricas.publicado`: o campo `publicado` manda."""
    if not isinstance(linha, dict):
        return False
    if "publicado" in linha:
        return bool(linha["publicado"])
    return bool(linha.get("url"))


def tem_prova(linha: dict) -> bool:
    """✓ quando o outro lado pode desmentir: laudo ok ou id do video."""
    if linha.get("prova_ok") is True:
        return True
    if linha.get("prova_ok") is False:
        return False
    tem_id = linha.get("tiktok_id") or linha.get("youtube_id")
    return bool(tem_id) and str(linha.get("url") or "").startswith("http")


def ultimos_publicados(por_canal: dict, n: int = 5) -> list[dict]:
    """Os `n` mais recentes dos dois ledgers, com a marca de prova."""
    todos = []
    for canal, linhas in por_canal.items():
        for linha in linhas:
            if not publicado(linha):
                continue
            momento = None
            try:
                momento = datetime.fromisoformat(str(linha.get("quando"))[:19])
            except ValueError:
                continue
            todos.append({"quando": momento, "canal": canal,
                          "plataforma": str(linha.get("plataforma") or ""),
                          "titulo": str(linha.get("titulo") or
                                        linha.get("video_id") or ""),
                          "prova": tem_prova(linha)})
    todos.sort(key=lambda d: d["quando"], reverse=True)
    return todos[:n]


# ------------------------------------------------------------------ terminal
def classificar_linha(texto: str) -> str:
    """A cor de uma linha de console, pelo que ela DIZ."""
    baixo = texto.lower()
    if not texto.strip():
        return ""
    if texto.startswith("   ") and not texto.lstrip().startswith(("!", "pulado")):
        return "fraco"
    if any(p in baixo for p in ("traceback", "error", "erro", "falhou",
                                "nao subiu", "não subiu", "exception",
                                "   ! ")):
        return "erro"
    if any(p in baixo for p in ("<<<", "aviso", "pulado", "fora da fila",
                                "atrasado", "desligada", "saindo")):
        return "aviso"
    if any(p in baixo for p in ("[postado]", "publicado", "recuperado",
                                "enviado", "no ar", " ok", "pronto")):
        return "ok"
    if texto.startswith("[-------]") or texto.startswith(">>>"):
        return "cmd"
    return ""


# ------------------------------------------------------------------- resumo
def resumo(estado: dict) -> dict:
    """O que a faixa MINI diz: um nivel, uma frase e o alerta."""
    erros = estado.get("erros") or []
    abertos = estado.get("abertos") or []
    bot = estado.get("bot") or {}
    agendador = estado.get("tarefas") or {}
    # Tarefa QUEBRADA (o oculto.vbs ou o .cmd sumiu) falha sem janela nenhuma
    # para mostrar: e erro. Tarefa que voltou a abrir console e so feiura.
    quebradas = [i for i in agendador.get("problemas") or []
                 if i.get("estado") == "quebrada"]
    alerta = ""
    if erros:
        e = erros[0]
        alerta = (f"{rotulo(e['predio'])}: "
                  f"{' '.join(str(e.get('detalhe') or '').split())}")
    elif bot.get("vivo") is False:
        alerta = "o bot do Telegram não está no ar"
    elif agendador.get("ok") is False:
        alerta = agendador.get("selo", "tarefas do Agendador com problema")
    # TRABALHO REAL tem tres fontes, e "tudo parado" so quando nenhuma diz
    # nada: `inicio` aberto, processo de producao vivo, evento recente.
    focos = [a["texto"] for a in abertos]
    predios_com_foco = {a.get("predio") for a in abertos}
    for predio, info in (estado.get("predios") or {}).items():
        if info.get("status") == "recente" and predio not in predios_com_foco:
            focos.append(info["balao"])
    for linha in estado.get("vivos") or []:
        if linha.get("tipo") in PRODUCAO and linha.get("ativo"):
            focos.append(linha["quem"])
    if erros or bot.get("vivo") is False or quebradas:
        nivel = "erro"
    elif focos:
        nivel = "trabalhando"
    else:
        nivel = "calmo"
    if focos:
        frase = f"⚙ {len(focos)} em andamento · {focos[0]}"
    else:
        frase = "💤 tudo parado"
    if erros:
        frase = f"❗ {len(erros)} erro(s) em 2 h · " + frase
    return {"nivel": nivel, "frase": frase, "alerta": alerta}


__all__ = [n for n in dir() if not n.startswith("_")]
