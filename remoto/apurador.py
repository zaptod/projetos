# -*- coding: utf-8 -*-
"""Erro na maquina -> Claude apura sozinho -> o diagnostico chega no Telegram.

Pedido dele (08/09/2026): "quando der algum erro que for mandado telegram,
tambem seja mandada a mensagem de erro e comece uma nova interacao... para que
ele proprio possa apurar todos os erros que estejam acontecendo" e "quero que
os erros que acontecem na minha maquina vao para algum lugar que o Claude
possa pegar".

O LUGAR JA EXISTIA: `builds/atividade.py` grava tudo em `atividade.jsonl`, e e
de la que o bot tira os alertas. O que faltava era alguem LER aquilo e
descobrir o que esta acontecendo — o alerta dizia "picasso falhou" e parava
ali, e a pessoa e que ia atras do log.

Aqui a apuracao roda uma sessao do Claude Code local (`claude -p`) em cima dos
erros novos e manda a conclusao para o mesmo chat.

TRES LIMITES, e nenhum e enfeite:

  SO LEITURA. `--allowedTools Read Grep Glob` e `--permission-mode dontAsk`.
  Uma sessao automatica, sem ninguem olhando, nao mexe em codigo: ela conta o
  que achou e a decisao continua sendo dele. Consertar sozinho de madrugada e
  como o defeito da retencao zero — o estrago que ninguem ve chegar.
  UMA DE CADA VEZ. Trava de arquivo: um erro que se repete seis vezes por dia
  nao pode virar seis sessoes simultaneas.
  TETO POR DIA. Erro que nao para de acontecer gastaria sessao ate o fim do
  mundo. Passou do teto, ele para e diz que parou.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Quantas apuracoes por dia, no maximo.
TETO_DIARIO = 8
# Quanto tempo uma apuracao pode levar antes de ser abandonada.
LIMITE_S = 420
# Erros mais velhos que isto nao interessam mais: o que importa e o que esta
# acontecendo agora, nao o que ja foi consertado.
JANELA_H = 12
MODELO = "claude-haiku-4-5-20251001"


def _estado_path() -> Path:
    from builds.contas import runtime_dir
    return runtime_dir() / "apuracoes.json"


def _ler_estado() -> dict:
    try:
        with open(_estado_path(), encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _gravar_estado(dados: dict) -> None:
    caminho = _estado_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)


def caminho_do_claude() -> str | None:
    """O executavel do Claude Code nesta maquina.

    A extensao do VSCode carrega o binario dentro da pasta da VERSAO, que muda
    a cada atualizacao — por isso ele e procurado, e nao escrito fixo. `which`
    vem antes: quem instalou o CLI de proposito quer o dele.
    """
    if os.environ.get("CLAUDE_BIN"):
        return os.environ["CLAUDE_BIN"]
    from shutil import which
    achado = which("claude")
    if achado:
        return achado
    base = Path.home() / ".vscode" / "extensions"
    candidatos = sorted(base.glob("anthropic.claude-code-*/resources/"
                                  "native-binary/claude.exe"))
    return str(candidatos[-1]) if candidatos else None


def _quando(evento: dict) -> str:
    return str(evento.get("ts") or evento.get("quando") or "")


def pendentes(janela_h: float = JANELA_H) -> list[dict]:
    """Os erros do ledger que ainda nao foram apurados."""
    from builds import atividade

    ja_visto = set(_ler_estado().get("apurados") or [])
    limite = datetime.now().timestamp() - janela_h * 3600
    novos = []
    for evento in atividade.recentes(300):
        if (evento.get("status") or "") != "erro":
            continue
        marca = f"{_quando(evento)}|{evento.get('fabrica')}"
        if marca in ja_visto:
            continue
        try:
            if datetime.fromisoformat(_quando(evento)).timestamp() < limite:
                continue
        except ValueError:
            pass
        novos.append(evento)
    return novos


def marcar(erros: list[dict]) -> None:
    """Erro apurado nao volta. Sem isso, cada volta reapuraria os mesmos."""
    estado = _ler_estado()
    vistos = list(estado.get("apurados") or [])
    vistos += [f"{_quando(e)}|{e.get('fabrica')}" for e in erros]
    # A lista so precisa cobrir a janela; guardar tudo cresceria para sempre.
    estado["apurados"] = vistos[-400:]
    _gravar_estado(estado)


def _contagem_de_hoje(estado: dict) -> int:
    return int((estado.get("por_dia") or {}).get(date.today().isoformat(), 0))


def _somar_uma(estado: dict) -> None:
    por_dia = estado.setdefault("por_dia", {})
    hoje = date.today().isoformat()
    por_dia[hoje] = int(por_dia.get(hoje, 0)) + 1
    for dia in list(por_dia):
        if dia < (date.today().replace(day=1)).isoformat():
            por_dia.pop(dia, None)
    _gravar_estado(estado)


def prompt_de(erros: list[dict]) -> str:
    linhas = [
        "Voce e o diagnostico automatico deste monorepo. Aconteceram erros na "
        "maquina e eu quero saber O QUE ESTA ACONTECENDO — nao um conserto.",
        "",
        "ERROS DO LEDGER (outputs de `builds/atividade.py`):",
    ]
    for erro in erros[:8]:
        linhas.append(f"  - {_quando(erro)} [{erro.get('fabrica')}/"
                      f"{erro.get('canal')}] {str(erro.get('detalhe'))[:400]}")
    linhas += [
        "",
        "Investigue lendo os arquivos: os logs da criacao automatica ficam em "
        "`historias/outputs/_logs/auto_<data>.txt`, e o estado das historias "
        "em `historias/outputs/historia_*/`.",
        "",
        "Responda em PORTUGUES, no maximo 12 linhas, nesta ordem:",
        "1. O que quebrou, em uma frase.",
        "2. A causa, se der para saber pelos arquivos (cite arquivo e linha).",
        "3. Se ja se resolveu sozinho (a rodada seguinte retoma o que ficou "
        "pela metade) ou se precisa de alguem.",
        "4. O comando que a pessoa rodaria para conferir.",
        "",
        "Nao invente: se os arquivos nao disserem, diga que nao deu para saber.",
    ]
    return "\n".join(linhas)


def apurar(erros: list[dict], *, log=print) -> str | None:
    """Roda a sessao de leitura e devolve o texto do diagnostico."""
    executavel = caminho_do_claude()
    if not executavel:
        log("[apurador] nao achei o executavel do Claude Code nesta maquina.")
        return None

    estado = _ler_estado()
    if _contagem_de_hoje(estado) >= TETO_DIARIO:
        log(f"[apurador] ja foram {TETO_DIARIO} apuracoes hoje; parando por "
            "aqui para nao virar moinho.")
        return None

    comando = [
        executavel, "-p", prompt_de(erros),
        # SO LEITURA. Qualquer outra ferramenta cai em pedido de permissao, e
        # em modo nao-interativo pedido de permissao e negacao.
        "--allowedTools", "Read", "Grep", "Glob",
        "--permission-mode", "dontAsk",
        "--model", MODELO,
    ]
    log(f"[apurador] apurando {len(erros)} erro(s) com o Claude...")
    try:
        proc = subprocess.run(comando, cwd=str(RAIZ), capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=LIMITE_S, creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        log(f"[apurador] a apuracao passou de {LIMITE_S}s e foi abandonada.")
        return None
    except OSError as exc:
        log(f"[apurador] nao consegui rodar o Claude ({exc}).")
        return None
    _somar_uma(estado)
    if proc.returncode != 0:
        log(f"[apurador] o Claude saiu com {proc.returncode}: "
            f"{(proc.stderr or '')[-200:]}")
        return None
    return (proc.stdout or "").strip() or None


# ------------------------------------------------------------------ conserto
# As pastas que o conserto pode MEXER. Nada fora daqui: `outputs/` tem
# gigabytes de video, `.git` e historico, e um agente perdido dentro deles nao
# tem nada a consertar.
FONTES = ("historias/contos", "historias/tests", "historias/config",
          "random_builds/builds", "random_builds/tests", "random_builds/config",
          "remoto", "painel", "ferramentas", "vila", "visao", "mimetizar")
EXTENSOES = (".py", ".json", ".md", ".txt")
# Arquivo maior que isso nao e codigo; e dado que entrou onde nao devia.
TAMANHO_MAX = 2_000_000


def _arquivos_de_fonte() -> list[Path]:
    achados = []
    for pasta in FONTES:
        raiz = RAIZ / pasta
        if not raiz.is_dir():
            continue
        for caminho in raiz.rglob("*"):
            if (caminho.is_file() and caminho.suffix in EXTENSOES
                    and "__pycache__" not in caminho.parts
                    and caminho.stat().st_size <= TAMANHO_MAX):
                achados.append(caminho)
    return achados


def fotografar() -> dict:
    """O conteudo de cada fonte ANTES do conserto.

    Nao da para usar `git checkout --` para desfazer: a arvore dele tem
    trabalho NAO COMMITADO (24 arquivos em 08/09/2026), e restaurar do HEAD
    apagaria o dele junto com o do agente. A foto e do estado real de agora.
    """
    foto = {}
    for caminho in _arquivos_de_fonte():
        try:
            foto[str(caminho)] = caminho.read_bytes()
        except OSError:
            continue
    return foto


def mexidos(foto: dict) -> list[str]:
    """O que mudou desde a foto — arquivos criados inclusive."""
    saida = []
    for caminho in _arquivos_de_fonte():
        chave = str(caminho)
        try:
            agora = caminho.read_bytes()
        except OSError:
            continue
        if foto.get(chave) != agora:
            saida.append(chave)
    return sorted(saida)


def restaurar(foto: dict, alvos: list[str]) -> None:
    """Desfaz o conserto: volta o que mudou e apaga o que foi criado."""
    for chave in alvos:
        caminho = Path(chave)
        if chave in foto:
            caminho.write_bytes(foto[chave])
        else:
            caminho.unlink(missing_ok=True)


def remendo(foto: dict, alvos: list[str]) -> str:
    """O diff do que o AGENTE fez — sem o trabalho nao commitado dele no meio.

    `git diff` nao serve aqui: ele mostraria as duas coisas juntas, e o que se
    quer revisar (ou desfazer) e so o que a maquina escreveu sozinha.
    """
    import difflib
    pedacos = []
    for chave in alvos:
        antes = foto.get(chave, b"").decode("utf-8", "replace").splitlines(True)
        try:
            depois = Path(chave).read_text(
                encoding="utf-8", errors="replace").splitlines(True)
        except OSError:
            depois = []
        rel = Path(chave).relative_to(RAIZ).as_posix()
        pedacos.extend(difflib.unified_diff(antes, depois,
                                            f"a/{rel}", f"b/{rel}"))
    return "".join(pedacos)


def _testar() -> tuple:
    """A suite inteira. E o unico juiz de um conserto que ninguem revisou."""
    try:
        proc = subprocess.run([sys.executable, "testar.py"], cwd=str(RAIZ),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=900,
                              creationflags=NO_WINDOW)
    except Exception as exc:                                   # noqa: BLE001
        return False, f"nao consegui rodar a suite: {exc}"
    saida = (proc.stdout or "") + (proc.stderr or "")
    ultima = [l for l in saida.splitlines() if l.strip()][-1:] or [""]
    return proc.returncode == 0, ultima[0].strip()[:200]


def prompt_de_conserto(erros: list[dict], diagnostico: str) -> str:
    return "\n".join([
        "Voce e o conserto automatico deste monorepo. Um diagnostico ja foi "
        "feito; agora CONSERTE a causa no codigo.",
        "",
        "DIAGNOSTICO:",
        diagnostico[:2000],
        "",
        "ERROS QUE O ORIGINARAM:",
        *[f"  - [{e.get('fabrica')}] {str(e.get('detalhe'))[:300]}"
          for e in erros[:6]],
        "",
        "REGRAS:",
        "- Mexa SO no que causou o erro. Nao aproveite para melhorar outra coisa.",
        "- Se o erro foi de REDE, de servico externo fora do ar, ou de limite de "
        "tempo de um site, NAO ha o que consertar no codigo: nao mexa em nada e "
        "explique por que.",
        "- Escreva no estilo do arquivo que voce esta editando, e comente o "
        "PORQUE quando a razao nao for obvia.",
        "- Se mexer em comportamento, ajuste ou acrescente o teste que trava isso.",
        "- Nao toque em `outputs/`, em credencial, nem em `.git`.",
        # Em 09/09/2026 a apuracao deixou `run_test.py`, `test_runner.py` e
        # `verify_fix.py` na raiz. Um deles tinha `sys.path.insert(0, ".")`, o
        # que estourou a catraca de arquitetura (teto 2) e DERRUBOU a suite —
        # exatamente o juiz que decide se o conserto sobrevive. Um rascunho de
        # verificacao nao pode reprovar o conserto que ele foi escrever.
        "- NAO crie arquivo novo na raiz do repositorio, nem script de "
        "verificacao ('run_test.py', 'verify_fix.py' e parecidos). Para "
        "conferir o que voce escreveu, LEIA o arquivo — a suite roda depois de "
        "voce, e ela e quem julga.",
        # A frase evita escrever a chamada por extenso DE PROPOSITO: a
        # auditoria conta as ocorrencias no fonte inteiro, inclusive dentro de
        # string, entao a propria regra estouraria a catraca que ela protege.
        "- Nada de mexer no `sys.path` (insert/append) em lugar nenhum: ha uma "
        "catraca de arquitetura contando, e passar do teto reprova a suite.",
        "",
        "A suite inteira vai rodar depois de voce. Se ela reprovar, tudo o que "
        "voce escreveu sera DESFEITO — entao prefira a mudanca pequena e certa "
        "a mudanca grande e esperta.",
        "",
        "Termine com um resumo de 3 linhas: o que mudou, onde, e por que.",
    ])


def consertar(erros: list[dict], diagnostico: str, *, log=print) -> dict:
    """Deixa o Claude MEXER no codigo, com a suite como juiz.

    Ele pediu isso em 08/09/2026, depois de ver a apuracao so diagnosticar. O
    risco de um agente que edita sozinho, oito vezes por dia, sem ninguem
    olhando, e quebrar as rodadas seguintes em silencio — por isso o conserto
    so SOBREVIVE se os 2248 testes passarem, e o que ele escreveu vai inteiro
    para o Telegram e para um arquivo de remendo que da para reverter.
    """
    executavel = caminho_do_claude()
    if not executavel:
        return {"mexeu": False, "motivo": "sem o executavel do Claude"}

    foto = fotografar()
    comando = [
        executavel, "-p", prompt_de_conserto(erros, diagnostico),
        # Edit/Write SIM, Bash NAO. Rodar comando e o que transforma um engano
        # em estrago; a suite quem roda e o `_testar()` aqui embaixo, que o
        # agente nao alcanca.
        "--allowedTools", "Read", "Grep", "Glob", "Edit", "Write",
        "--permission-mode", "acceptEdits",
        "--model", MODELO,
    ]
    log("[apurador] deixando o Claude consertar...")
    try:
        proc = subprocess.run(comando, cwd=str(RAIZ), capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=LIMITE_S * 2, creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        restaurar(foto, mexidos(foto))
        return {"mexeu": False,
                "motivo": "o conserto passou do tempo e foi desfeito"}
    except OSError as exc:
        return {"mexeu": False, "motivo": f"nao rodou: {exc}"}

    alvos = mexidos(foto)
    resumo = (proc.stdout or "").strip()
    if not alvos:
        return {"mexeu": False, "motivo": "nada a mexer no codigo",
                "resumo": resumo[-600:]}

    log(f"[apurador] {len(alvos)} arquivo(s) mexido(s); rodando a suite...")
    passou, ultima = _testar()
    if not passou:
        restaurar(foto, alvos)
        log("[apurador] a suite reprovou; desfiz tudo.")
        return {"mexeu": False, "desfeito": True, "arquivos": alvos,
                "motivo": f"os testes reprovaram ({ultima}); desfiz o conserto",
                "resumo": resumo[-600:]}

    destino = RAIZ / "outputs" / "_apuracoes"
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"conserto_{datetime.now():%Y%m%d_%H%M%S}.patch"
    arquivo.write_text(remendo(foto, alvos), encoding="utf-8")
    return {"mexeu": True, "arquivos": alvos, "remendo": str(arquivo),
            "testes": ultima, "resumo": resumo[-600:]}


def uma_volta(*, log=print) -> dict:
    """Pega os erros novos, apura e devolve o que houve. Nunca levanta."""
    from builds import travas

    with travas.trava("remoto__apurador", esperar=0.0) as minha:
        if not minha:
            log("[apurador] ja tem uma apuracao rodando.")
            return {"feito": False, "motivo": "ja rodando"}
        erros = pendentes()
        if not erros:
            return {"feito": False, "motivo": "nenhum erro novo"}
        texto = apurar(erros, log=log)
        # Marca mesmo quando a apuracao falha: senao o mesmo erro seria
        # tentado a cada volta, e um erro que o Claude nao consegue explicar
        # viraria uma fila infinita de sessoes.
        marcar(erros)
        if not texto:
            return {"feito": False, "motivo": "sem diagnostico",
                    "erros": len(erros)}
        saida = {"feito": True, "erros": len(erros), "diagnostico": texto}
        # O conserto vem DEPOIS do diagnostico e em cima dele: mexer no codigo
        # sem antes entender o que quebrou e como consertar no escuro.
        from . import config
        if config.carregar().get("consertar", True):
            saida["conserto"] = consertar(erros, texto, log=log)
        return saida
