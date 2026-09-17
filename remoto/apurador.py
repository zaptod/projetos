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

import contextlib
import json
import os
import re
import subprocess
import sys
import tempfile
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


# Fabricas cujo "erro" e ACHADO DE DADOS, nao defeito de codigo. Medido em
# 16/09/2026: os dois alarmes da conferencia ("22 rascunho(s) no canal")
# dispararam uma sessao de conserto que EDITOU codigo — e deixou uma mudanca
# sem dono no `contos/publicar/__init__.py`. Rascunho no canal nao se
# conserta mexendo no fonte; o alerta no celular continua (o bot le o mesmo
# diario), so a apuracao por `claude -p` fica de fora.
# `apurador` e o alarme deste proprio modulo (conserto que mexeu na
# arvore principal): ele nao pode abrir outro conserto.
FABRICAS_SEM_APURACAO = frozenset({"conferencia", "apurador"})


def pendentes(janela_h: float = JANELA_H) -> list[dict]:
    """Os erros do ledger que ainda nao foram apurados."""
    from builds import atividade

    ja_visto = set(_ler_estado().get("apurados") or [])
    limite = datetime.now().timestamp() - janela_h * 3600
    novos = []
    for evento in atividade.recentes(300):
        if (evento.get("status") or "") != "erro":
            continue
        if evento.get("fabrica") in FABRICAS_SEM_APURACAO:
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


def prompt_de_conserto(erros: list[dict], diagnostico: str,
                       pasta: Path | None = None) -> str:
    # O diagnostico foi escrito olhando a arvore PRINCIPAL e cita caminhos
    # absolutos dela. Na worktree, esses caminhos levariam o agente para
    # fora — entao eles viram relativos antes de chegar a ele.
    pasta = pasta or RAIZ
    for raiz in {str(RAIZ), str(RAIZ).replace("\\", "/")}:
        diagnostico = diagnostico.replace(raiz, ".")
    return "\n".join([
        "Voce e o conserto automatico deste monorepo. Um diagnostico ja foi "
        "feito; agora CONSERTE a causa no codigo.",
        "",
        f"VOCE ESTA NUMA COPIA DE TRABALHO: {pasta}. Todo caminho que voce "
        "ler ou editar e RELATIVO a ela (ex.: `remoto/apurador.py`). Nunca "
        "use caminho absoluto, e nunca saia desta pasta: as permissoes "
        "negam, e a tentativa descarta o conserto inteiro.",
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
        "- NAO crie nem altere teste (`tests/`, `test_*.py`, `conftest.py`, "
        "`testar.py`): a suite executa o que estiver la, e um conserto que "
        "mexe em teste e descartado sem rodar.",
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
        "A suite inteira vai rodar depois de voce. Se ela reprovar, nada do que "
        "voce escreveu entra — entao prefira a mudanca pequena e certa a "
        "mudanca grande e esperta. Se passar, vira uma branch que uma pessoa "
        "revisa antes de entrar.",
        "",
        "Termine com um resumo de 3 linhas: o que mudou, onde, e por que.",
    ])


# ------------------------------------------------ protecoes do conserto
# Desenho de 16/09/2026, depois de um conserto automatico ter editado codigo
# por causa de um ACHADO DE DADOS (rascunhos no canal) com tres sessoes
# trabalhando na mesma arvore, e revisado de forma independente no mesmo dia.
# O conserto nunca toca a arvore principal:
#
#   1. so comeca com a arvore LIMPA (sem alteracao pendente);
#   2. trabalha numa WORKTREE propria, com o `claude -p` PRESO a ela (regras de
#      caminho, modo `dontAsk`) e a suite rodando LA; depois confere que a
#      arvore principal e os hooks do git nao mudaram;
#   3. entrega um COMMIT numa branch `conserto/<carimbo>` — o merge e de uma
#      pessoa; conserto que mexe em teste, ou fora das fontes, nao entrega;
#   4. so gasta um `claude -p` com erro que vale: fabrica de codigo, `ref` de
#      um video que existe, e erro que se REPETIU;
#   5. teto de TENTATIVAS por dia, e espera a rodada da agenda e qualquer
#      sessao que segure a trava de edicao.
#
# Desligado falha FECHADO: sem `"consertar": true` explicito no remoto.json,
# ou com o arquivo ilegivel, nao ha conserto.

TETO_CONSERTOS_DIA = 3
TRAVA_DE_SESSAO = "sessao_editando"
REPETICOES_MINIMAS = 2
# Onde moram os pacotes instalados em modo editavel. A suite da worktree tem
# de importar DAQUI: sem isto, `import builds` acharia a arvore PRINCIPAL e a
# suite aprovaria um conserto sem nunca te-lo testado.
PACOTES_DA_ARVORE = ("random_builds", "historias", "visao", "mimetizar", "")
ID_DE_VIDEO = re.compile(r"^(?:generation|historia|duelo|tournament)_\d+")
# O que um conserto NAO pode criar nem alterar: a suite da worktree EXECUTA
# qualquer teste, e um teste escrito pelo agente e codigo arbitrario rodando
# com o nome de "juiz". O preco e real — o conserto nao traz teste novo — e
# esta escrito aqui de proposito.
CAMINHOS_DE_TESTE = re.compile(
    r"(?:^|/)(?:tests?/|test_[^/]*\.py$|[^/]*_test\.py$|conftest\.py$"
    r"|testar\.py$)")
# A fabrica deste proprio modulo: alarme dele nunca pode abrir outro conserto.
FABRICA = "apurador"
PREFIXO_TEMPORARIO = "conserto-"


def no_escopo(relativo: str) -> bool:
    """O arquivo esta numa fonte permitida e e texto de codigo?"""
    caminho = str(relativo).replace("\\", "/").strip('"')
    return (caminho.startswith(tuple(f"{f}/" for f in FONTES))
            and Path(caminho).suffix in EXTENSOES)


def e_teste(relativo: str) -> bool:
    return bool(CAMINHOS_DE_TESTE.search(str(relativo).replace("\\", "/")))


def _git(args: list, cwd=None, timeout: int = 120):
    return subprocess.run(["git", *args], cwd=str(cwd or RAIZ),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout,
                          creationflags=NO_WINDOW)


def _git_com_retomada(args: list, cwd=None, tentativas: int = 3) -> bool:
    """No Windows um arquivo ainda aberto faz `worktree remove` falhar."""
    for tentativa in range(tentativas):
        with contextlib.suppress(Exception):
            if _git(args, cwd=cwd).returncode == 0:
                return True
        if tentativa + 1 < tentativas:
            _esperar(2.0)
    return False


def _esperar(segundos: float) -> None:
    import time
    time.sleep(segundos)


def arvore_limpa() -> tuple:
    """(limpa?, motivo). Qualquer duvida conta como SUJA."""
    try:
        proc = _git(["status", "--porcelain"])
    except Exception as exc:                                   # noqa: BLE001
        return False, f"nao consegui ler o git ({exc})"
    if proc.returncode != 0:
        return False, "o git status falhou"
    sujos = [linha for linha in proc.stdout.splitlines() if linha.strip()]
    if sujos:
        return False, (f"{len(sujos)} arquivo(s) com alteracao pendente — "
                       "alguem esta trabalhando na arvore")
    return True, ""


def retrato_da_arvore() -> dict:
    """O estado da arvore principal que o conserto NAO pode mudar.

    `git status` pega arquivo versionado e novo; os hooks do git nao sao
    versionados e rodam em todo commit — e o lugar mais perigoso para um
    agente escrever.
    """
    import hashlib
    retrato = {"status": ""}
    with contextlib.suppress(Exception):
        retrato["status"] = _git(["status", "--porcelain",
                                  "--untracked-files=all"]).stdout
    ganchos = RAIZ / ".git" / "hooks"
    with contextlib.suppress(OSError):
        for arquivo in sorted(ganchos.iterdir()):
            if arquivo.is_file():
                retrato[f"hook:{arquivo.name}"] = hashlib.md5(
                    arquivo.read_bytes()).hexdigest()
    return retrato


def fonte_do_ref(ref) -> str:
    """O id de fonte dentro de um `ref`, ou "".

    Os refs chegam em varias formas: "historia_00016",
    "historia_00016:p3", "historia_00012:celular:p02",
    "generation_00081:build:celular|titulo_repetido". Todas dizem a que
    fonte o erro pertence; e so isso que se procura no catalogo.
    """
    texto = str(ref or "").split("|", 1)[0].strip()
    achado = ID_DE_VIDEO.match(texto)
    return achado.group(0) if achado else ""


def _fontes_do_catalogo() -> set:
    """Os ids de fonte que existem de verdade. Nunca levanta."""
    fontes = set()
    for modulo in ("builds.publicar.catalogo", "contos.publicar.catalogo"):
        try:
            catalogo = __import__(modulo, fromlist=["listar"])
            for video in catalogo.listar():
                fonte = (getattr(video, "fonte_id", "")
                         or fonte_do_ref(getattr(video, "id", "")))
                if fonte:
                    fontes.add(str(fonte))
        except Exception:                                      # noqa: BLE001
            continue
    return fontes


def _assinatura(evento: dict) -> tuple:
    """O mesmo erro, mesmo com numero e hora diferentes no texto."""
    detalhe = re.sub(r"\d+", "#", str(evento.get("detalhe") or "").lower())
    return (evento.get("fabrica"), detalhe[:120])


def erros_que_valem(erros: list, recentes=None, fontes=None) -> list:
    """Os erros que justificam gastar um `claude -p` com permissao de editar.

      - fabrica de codigo (as de dados e a deste modulo ficam de fora);
      - `ref` OBRIGATORIO, e de uma fonte que existe num catalogo —
        16/09/2026: "trava:build:celular" era duble de teste escrito no
        diario de producao, e abriu um conserto de verdade;
      - erro que se REPETIU: uma linha solta nao prova defeito.
    """
    if recentes is None:
        from builds import atividade
        recentes = [e for e in atividade.recentes(300)
                    if e.get("status") == "erro"]
    contagem: dict = {}
    for evento in recentes or ():
        contagem[_assinatura(evento)] = contagem.get(_assinatura(evento), 0) + 1
    valem = []
    for erro in erros:
        if erro.get("fabrica") in FABRICAS_SEM_APURACAO:
            continue
        fonte = fonte_do_ref(erro.get("ref"))
        if not fonte:
            continue
        if fontes is None:
            fontes = _fontes_do_catalogo()
        if fonte not in fontes:
            continue
        if contagem.get(_assinatura(erro), 0) < REPETICOES_MINIMAS:
            continue
        valem.append(erro)
    return valem


def _estado_estrito():
    """O estado, `{}` se ainda nao existe, ou `None` se esta ILEGIVEL."""
    caminho = _estado_path()
    if not caminho.exists():
        return {}
    try:
        with open(caminho, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def tentativas_hoje():
    """Quantas TENTATIVAS de conserto hoje, ou `None` se nao da para saber."""
    estado = _estado_estrito()
    if estado is None:
        return None
    return int((estado.get("tentativas_por_dia") or {})
               .get(date.today().isoformat(), 0))


def _somar_tentativa() -> None:
    estado = _ler_estado()
    dias = estado.setdefault("tentativas_por_dia", {})
    hoje = date.today().isoformat()
    dias[hoje] = int(dias.get(hoje, 0)) + 1
    _gravar_estado(estado)


def motivo_para_nao_consertar(valem: list) -> str:
    """`""` se pode consertar; senao, o motivo. Da mais barata a mais cara."""
    from builds import travas
    if travas.ocupada(TRAVA_DA_AGENDA):
        return "rodada da agenda em andamento: conserto adiado"
    if travas.ocupada(TRAVA_DE_SESSAO):
        return "ha uma sessao editando o codigo: conserto adiado"
    feitas = tentativas_hoje()
    if feitas is None:
        return "estado do apurador ilegivel: tratado como teto esgotado"
    if feitas >= TETO_CONSERTOS_DIA:
        return f"teto de {TETO_CONSERTOS_DIA} tentativas de conserto por dia"
    if not valem:
        return ("nenhum erro vale um conserto (sem ref de video existente, "
                "dado, duble de teste ou ocorrencia unica)")
    limpa, motivo = arvore_limpa()
    if not limpa:
        return f"arvore suja, so diagnostico: {motivo}"
    return ""


def ambiente_da_worktree(pasta: Path) -> dict:
    """O ambiente da suite na worktree: os pacotes vem DELA."""
    caminhos = [str(pasta / p) if p else str(pasta)
                for p in PACOTES_DA_ARVORE]
    ambiente = dict(os.environ)
    ambiente["PYTHONPATH"] = os.pathsep.join(caminhos)
    return ambiente


def _matar_arvore(pid: int) -> None:
    """No Windows, matar o `python testar.py` deixa os filhos vivos."""
    with contextlib.suppress(Exception):
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=30,
                           creationflags=NO_WINDOW)
        else:
            os.killpg(pid, 9)


def _testar(pasta: Path | None = None, timeout: int = 1800) -> tuple:
    """A suite inteira, na pasta dada. E o unico juiz de um conserto."""
    pasta = pasta or RAIZ
    try:
        proc = subprocess.Popen(
            [sys.executable, "testar.py"], cwd=str(pasta),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace",
            env=ambiente_da_worktree(pasta), creationflags=NO_WINDOW)
    except Exception as exc:                                   # noqa: BLE001
        return False, f"nao consegui rodar a suite: {exc}"
    try:
        saida, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _matar_arvore(proc.pid)
        with contextlib.suppress(Exception):
            proc.communicate(timeout=30)
        return False, f"a suite passou de {timeout} s e foi encerrada"
    ultima = [l for l in (saida or "").splitlines() if l.strip()][-1:] or [""]
    return proc.returncode == 0, ultima[0].strip()[:200]


def comando_de_conserto(executavel: str, prompt: str) -> list:
    """O `claude -p` do conserto, PRESO a pasta onde ele roda.

    As regras de caminho sao relativas ao diretorio de trabalho, que e a
    worktree. Com `dontAsk`, tudo o que nao esta na lista e negado — e o
    que impede um `Edit` com caminho absoluto da arvore principal (ou de
    `.git/hooks`), que o diagnostico, escrito la, costuma citar.
    """
    return [
        executavel, "-p", prompt,
        "--allowedTools", "Read(./**)", "Grep", "Glob",
        "Edit(./**)", "Write(./**)",
        "--disallowedTools", "Bash", "WebFetch", "WebSearch",
        "Edit(./.git/**)", "Write(./.git/**)", "Edit(./.git)",
        "Write(./.git)",
        "--permission-mode", "dontAsk",
        "--model", MODELO,
    ]


def _rodar_claude(comando: list, pasta: Path):
    return subprocess.run(comando, cwd=str(pasta), capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=LIMITE_S * 2, creationflags=NO_WINDOW)


def _alarmar(texto: str) -> None:
    with contextlib.suppress(Exception):
        from builds import atividade
        atividade.registrar(FABRICA, "erro", texto[:300], "builds")


def consertar(erros: list[dict], diagnostico: str, *, log=print) -> dict:
    """Deixa o Claude mexer no codigo — numa WORKTREE, com a suite de juiz.

    Ele pediu isso em 08/09/2026, depois de ver a apuracao so diagnosticar.
    O conserto nunca escreve na arvore principal: o que passar na suite vira
    um commit na branch `conserto/<carimbo>`, e o merge e de uma pessoa. O
    que reprovar some com a worktree, sem nada a restaurar.
    """
    executavel = caminho_do_claude()
    if not executavel:
        return {"mexeu": False, "motivo": "sem o executavel do Claude"}

    _somar_tentativa()
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    ramo = f"conserto/{carimbo}"
    pasta = Path(tempfile.mkdtemp(prefix=PREFIXO_TEMPORARIO)) / "arvore"
    try:
        criada = _git(["worktree", "add", "-b", ramo, str(pasta), "HEAD"])
    except Exception as exc:                                   # noqa: BLE001
        return {"mexeu": False, "motivo": f"nao criei a worktree: {exc}"}
    if criada.returncode != 0:
        return {"mexeu": False,
                "motivo": f"nao criei a worktree: {criada.stderr[:160]}"}

    antes = retrato_da_arvore()
    entregue = False
    try:
        prompt = prompt_de_conserto(erros, diagnostico, pasta=pasta)
        log(f"[apurador] consertando numa worktree ({ramo})...")
        try:
            proc = _rodar_claude(comando_de_conserto(executavel, prompt), pasta)
        except subprocess.TimeoutExpired:
            return {"mexeu": False,
                    "motivo": "o conserto passou do tempo; nada entrou"}
        except OSError as exc:
            return {"mexeu": False, "motivo": f"nao rodou: {exc}"}
        resumo = (proc.stdout or "").strip()

        depois = retrato_da_arvore()
        if depois != antes:
            mudou = sorted(k for k in set(antes) | set(depois)
                           if antes.get(k) != depois.get(k))
            texto = ("conserto automatico MEXEU NA ARVORE PRINCIPAL "
                     f"({', '.join(mudou)}): nenhuma branch entregue; "
                     "confira a arvore e os hooks do git")
            log(f"[apurador] ALARME: {texto}")
            _alarmar(texto)
            return {"mexeu": False, "desfeito": True, "alarme": True,
                    "motivo": texto, "resumo": resumo[-600:]}

        estado = _git(["status", "--porcelain", "--untracked-files=all"],
                      cwd=pasta)
        alvos = [linha[3:].strip() for linha in estado.stdout.splitlines()
                 if linha.strip()]
        if not alvos:
            return {"mexeu": False, "motivo": "nada a mexer no codigo",
                    "resumo": resumo[-600:]}
        fora = [a for a in alvos if not no_escopo(a)]
        if fora:
            # Ninguem mandou mexer em saida, credencial ou arquivo que nao e
            # codigo. Nada vira commit.
            return {"mexeu": False, "desfeito": True, "arquivos": alvos,
                    "motivo": "mexeu fora das fontes permitidas: "
                              + ", ".join(fora[:4]),
                    "resumo": resumo[-600:]}
        testes = [a for a in alvos if e_teste(a)]
        if testes:
            return {"mexeu": False, "desfeito": True, "arquivos": alvos,
                    "motivo": "mexeu em teste (a suite executaria codigo "
                              "escrito pelo agente): " + ", ".join(testes[:4]),
                    "resumo": resumo[-600:]}

        log(f"[apurador] {len(alvos)} arquivo(s) mexido(s); suite na "
            "worktree...")
        passou, ultima = _testar(pasta)
        if not passou:
            return {"mexeu": False, "desfeito": True, "arquivos": alvos,
                    "motivo": f"os testes reprovaram ({ultima}); nada entrou "
                              "na arvore principal",
                    "resumo": resumo[-600:]}

        _git(["add", "-A"], cwd=pasta)
        feito = _git(["commit", "-m",
                      f"Conserto automatico {carimbo} (apurador)\n\n"
                      + diagnostico[:1500]], cwd=pasta)
        if feito.returncode != 0:
            return {"mexeu": False,
                    "motivo": f"a suite passou mas o commit falhou: "
                              f"{feito.stderr[:160]}"}
        commit = _git(["rev-parse", "--short", "HEAD"], cwd=pasta).stdout.strip()
        destino = RAIZ / "outputs" / "_apuracoes"
        destino.mkdir(parents=True, exist_ok=True)
        arquivo = destino / f"conserto_{carimbo}.patch"
        arquivo.write_text(_git(["show", "HEAD"], cwd=pasta).stdout,
                           encoding="utf-8")
        entregue = True
        return {"mexeu": True, "ramo": ramo, "commit": commit,
                "arquivos": alvos, "remendo": str(arquivo), "testes": ultima,
                "resumo": resumo[-600:]}
    finally:
        _git_com_retomada(["worktree", "remove", "--force", str(pasta)])
        if not entregue:
            _git_com_retomada(["branch", "-D", ramo])


def limpar_orfaos(log=print) -> int:
    """Worktrees e pastas de conserto que ficaram para tras. Nunca levanta.

    Chamada na subida do bot: um conserto interrompido (maquina desligada,
    processo morto) deixa a pasta temporaria e o registro da worktree.
    """
    removidas = 0
    with contextlib.suppress(Exception):
        _git(["worktree", "prune"])
    raiz_tmp = Path(tempfile.gettempdir())
    with contextlib.suppress(OSError):
        for pasta in raiz_tmp.glob(f"{PREFIXO_TEMPORARIO}*"):
            if not pasta.is_dir():
                continue
            with contextlib.suppress(Exception):
                import shutil
                shutil.rmtree(pasta)
                removidas += 1
    if removidas:
        log(f"[apurador] {removidas} pasta(s) de conserto orfa(s) removida(s).")
    return removidas


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
        # FALHA FECHADO: so `true` explicito liga. Arquivo ilegivel, chave
        # ausente ou qualquer outro valor = desligado.
        if config.carregar().get("consertar") is True:
            # As guardas vem ANTES do conserto, da mais barata para a mais
            # cara. A primeira e a de 14/09/2026, 13:45: uma rodada da agenda
            # morreu com AttributeError por codigo que mudou no meio dela.
            valem = erros_que_valem(erros) if not travas.ocupada(
                TRAVA_DA_AGENDA) else erros
            motivo = motivo_para_nao_consertar(valem)
            if motivo:
                log(f"[apurador] so diagnostico: {motivo}.")
                saida["conserto"] = {"mexeu": False, "motivo": motivo}
            else:
                saida["conserto"] = consertar(valem, texto, log=log)
        return saida


# O nome da trava de `historias/contos/pipeline/agenda.py` (TRAVA). Escrito
# aqui para o bot nao importar a pipeline de historias inteira a cada volta.
TRAVA_DA_AGENDA = "historias__auto"
