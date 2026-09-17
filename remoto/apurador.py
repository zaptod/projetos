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
FABRICAS_SEM_APURACAO = frozenset({"conferencia"})


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


# ------------------------------------------------ protecoes do conserto
# Desenho de 16/09/2026, depois de um conserto automatico ter editado codigo
# por causa de um ACHADO DE DADOS (rascunhos no canal) com tres sessoes
# trabalhando na mesma arvore. O conserto antigo editava a arvore principal,
# rodava a suite ali e, se ela reprovasse, restaurava uma "foto" — e a foto
# pegava junto o que outra sessao tivesse escrito no meio. O novo nunca toca
# a arvore principal:
#
#   1. so comeca com a arvore LIMPA (sem alteracao pendente);
#   2. trabalha numa WORKTREE propria, e a suite roda LA;
#   3. entrega um COMMIT numa branch `conserto/<carimbo>`, e nao mudanca solta
#      no disco — quem decide o merge e uma pessoa;
#   4. so gasta um `claude -p` com erro que vale: fabrica de codigo, ref com
#      cara de video que existe, e erro que se REPETIU;
#   5. tem teto proprio por dia, e espera a rodada da agenda e qualquer sessao
#      que segure a trava de edicao.
#
# "consertar" continua FALSE no remoto.json: religar e decisao do Adrian.

TETO_CONSERTOS_DIA = 3
TRAVA_DE_SESSAO = "sessao_editando"
REPETICOES_MINIMAS = 2
# Onde moram os pacotes instalados em modo editavel. A suite da worktree tem
# de importar DAQUI: sem isto, `import builds` acharia a arvore PRINCIPAL e a
# suite aprovaria um conserto sem nunca te-lo testado.
PACOTES_DA_ARVORE = ("random_builds", "historias", "visao", "mimetizar", "")
ID_DE_VIDEO = re.compile(r"^(?:generation|historia|duelo|tournament)_\d+")


def no_escopo(relativo: str) -> bool:
    """O arquivo esta numa fonte permitida e e texto de codigo?"""
    caminho = str(relativo).replace("\\", "/").strip('"')
    return (caminho.startswith(tuple(f"{f}/" for f in FONTES))
            and Path(caminho).suffix in EXTENSOES)


def _git(args: list, cwd=None, timeout: int = 120):
    return subprocess.run(["git", *args], cwd=str(cwd or RAIZ),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout,
                          creationflags=NO_WINDOW)


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


def _ids_do_catalogo() -> set:
    """Os ids de video que existem de verdade. Nunca levanta."""
    ids = set()
    for modulo in ("builds.publicar.catalogo", "contos.publicar.catalogo"):
        try:
            catalogo = __import__(modulo, fromlist=["listar"])
            ids.update(str(v.id) for v in catalogo.listar())
        except Exception:                                      # noqa: BLE001
            continue
    return ids


def _assinatura(evento: dict) -> tuple:
    """O mesmo erro, mesmo com numero e hora diferentes no texto."""
    detalhe = re.sub(r"\d+", "#", str(evento.get("detalhe") or "").lower())
    return (evento.get("fabrica"), detalhe[:120])


def erros_que_valem(erros: list, recentes=None, ids=None) -> list:
    """Os erros que justificam gastar um `claude -p` com permissao de editar.

      - fabrica de codigo (a de dados, `conferencia`, ja sai em `pendentes`);
      - `ref`, quando existe, com cara de video E presente num catalogo —
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
        ref = str(erro.get("ref") or "")
        if ref:
            if not ID_DE_VIDEO.match(ref):
                continue
            if ids is None:
                ids = _ids_do_catalogo()
            if ref not in ids:
                continue
        if contagem.get(_assinatura(erro), 0) < REPETICOES_MINIMAS:
            continue
        valem.append(erro)
    return valem


def _consertos_hoje(estado: dict) -> int:
    return int((estado.get("consertos_por_dia") or {})
               .get(date.today().isoformat(), 0))


def _somar_conserto() -> None:
    estado = _ler_estado()
    dias = estado.setdefault("consertos_por_dia", {})
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
    if _consertos_hoje(_ler_estado()) >= TETO_CONSERTOS_DIA:
        return f"teto de {TETO_CONSERTOS_DIA} consertos por dia atingido"
    if not valem:
        return ("nenhum erro vale um conserto (dado, duble de teste ou "
                "ocorrencia unica)")
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


def _testar(pasta: Path | None = None) -> tuple:
    """A suite inteira, na pasta dada. E o unico juiz de um conserto."""
    pasta = pasta or RAIZ
    try:
        proc = subprocess.run([sys.executable, "testar.py"], cwd=str(pasta),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=1800,
                              env=ambiente_da_worktree(pasta),
                              creationflags=NO_WINDOW)
    except Exception as exc:                                   # noqa: BLE001
        return False, f"nao consegui rodar a suite: {exc}"
    saida = (proc.stdout or "") + (proc.stderr or "")
    ultima = [l for l in saida.splitlines() if l.strip()][-1:] or [""]
    return proc.returncode == 0, ultima[0].strip()[:200]


def _rodar_claude(comando: list, pasta: Path):
    return subprocess.run(comando, cwd=str(pasta), capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=LIMITE_S * 2, creationflags=NO_WINDOW)


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

    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    ramo = f"conserto/{carimbo}"
    pasta = Path(tempfile.mkdtemp(prefix="conserto-")) / "arvore"
    try:
        criada = _git(["worktree", "add", "-b", ramo, str(pasta), "HEAD"])
    except Exception as exc:                                   # noqa: BLE001
        return {"mexeu": False, "motivo": f"nao criei a worktree: {exc}"}
    if criada.returncode != 0:
        return {"mexeu": False,
                "motivo": f"nao criei a worktree: {criada.stderr[:160]}"}

    entregue = False
    try:
        comando = [
            executavel, "-p", prompt_de_conserto(erros, diagnostico),
            # Edit/Write SIM, Bash NAO. Rodar comando e o que transforma um
            # engano em estrago; a suite quem roda e o `_testar()`, que o
            # agente nao alcanca.
            "--allowedTools", "Read", "Grep", "Glob", "Edit", "Write",
            "--permission-mode", "acceptEdits",
            "--model", MODELO,
        ]
        log(f"[apurador] consertando numa worktree ({ramo})...")
        try:
            proc = _rodar_claude(comando, pasta)
        except subprocess.TimeoutExpired:
            return {"mexeu": False,
                    "motivo": "o conserto passou do tempo; nada entrou"}
        except OSError as exc:
            return {"mexeu": False, "motivo": f"nao rodou: {exc}"}
        resumo = (proc.stdout or "").strip()

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
        _somar_conserto()
        entregue = True
        return {"mexeu": True, "ramo": ramo, "commit": commit,
                "arquivos": alvos, "remendo": str(arquivo), "testes": ultima,
                "resumo": resumo[-600:]}
    finally:
        with contextlib.suppress(Exception):
            _git(["worktree", "remove", "--force", str(pasta)])
        if not entregue:
            with contextlib.suppress(Exception):
                _git(["branch", "-D", ramo])


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
