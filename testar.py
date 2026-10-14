# -*- coding: utf-8 -*-
"""Roda TUDO e diz, numa linha, se dá para confiar no estado do projeto.

    python testar.py             tudo (o que importa antes de mexer em algo)
    python testar.py --rapido    só os testes, sem abrir janela nem rede
    python testar.py --lista     o que existe, sem executar

Por que existe: o projeto virou seis bases de código (neural_fights,
random_builds, historias, mimetizar, remoto), o agregador de métricas mais o painel, cada uma com o seu
jeito de rodar teste. "Testar tudo" virava cinco comandos em cinco pastas —
e, na prática, ou se esquecia um ou não se testava. Um comando que falha em
vermelho é a diferença entre confiar e torcer.

Até 01/09/2026 havia DOIS mundos de teste disjuntos: este arquivo rodava
random_builds + historias + remoto (933 testes) e o CI rodava só `tests/`
(928). Os 11 da vila não rodavam em lugar nenhum. Nenhum comando rodava
tudo — que é exatamente a situação em que um refactor quebra algo e
ninguém fica sabendo.

O que ele cobre, e por que cada parte está aqui:

  SUÍTES        os contratos de cada projeto. É o grosso.
  SMOKE         o painel MONTA todas as páginas das três janelas. Nenhuma suíte pega um erro de
                layout, e o painel é por onde tudo é operado.
  ARQUITETURA   os numeros da bagunca (cirurgias de sys.path, nomes de
                pacote repetidos) subiram? Catraca: falha se PIORAR.
  INTEGRIDADE   byte de controle no fonte. Já quebrou uma regex em silêncio
                (o heredoc do shell converte `\\b` em 0x08) e nada acusou.
  FERRAMENTAS   ffmpeg/ffprobe existem? Metade do projeto depende deles, e a
                falta só aparece no meio de um render de 20 minutos.

Tudo roda com o runtime apontado para uma pasta descartável. Sem isso a
suíte do neural_fights escreveria no banco DE VERDADE (armas.json,
personagens.json, live.sqlite3) — testar não pode custar o estado do jogo.

Sai com 0 quando tudo passa, 1 quando algo falha — serve em agendador.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PY = sys.executable
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# A suite do neural_fights ESCREVE no diretorio de execucao (armas.json,
# personagens.json, live.sqlite3). Rodada sem isolamento, ela mexeria no
# banco de verdade do jogo. O CI ja resolve isso apontando o runtime para
# uma pasta descartavel; aqui e a mesma receita, com as mesmas variaveis.
# No E: quando existe (SCR-10, 14/10/2026): o C: deste PC vive cheio, e o
# temporario padrao e no C:.
_TEMP_DO_E = Path(r"E:\tmp_pytest")
PASTA_DESCARTAVEL = ((_TEMP_DO_E if _TEMP_DO_E.is_dir()
                      else Path(tempfile.gettempdir()))
                     / "neural-fights-testar")
AMBIENTE_ISOLADO = {
    "NEURAL_FIGHTS_RUNTIME_DIR": str(PASTA_DESCARTAVEL),
    # pygame sem tela nem placa de som: o smoke roda em maquina sem monitor
    # e o som travaria a suite esperando um dispositivo.
    "SDL_VIDEODRIVER": "dummy",
    "SDL_AUDIODRIVER": "dummy",
    "PYTHONUTF8": "1",
}

def _pytest(pasta: str) -> list:
    """O comando de uma suite: PYTEST, e nao `unittest discover` (SCR-2).

    Ate 14/10/2026 era tudo `unittest discover`, que nao coleta FUNCAO de
    teste nem carrega `conftest.py`: os testes do app, do delegar e do
    orquestrador (funcoes pytest) e o `coordenador/`, a `esteira_sprites/` e
    o `palco/testes/` inteiros nunca entravam no "TUDO VERDE". O pytest
    roda os `unittest.TestCase` do mesmo jeito.
    """
    return [PY, "-X", "utf8", "-m", "pytest", "-q", "-p", "no:cacheprovider",
            pasta]


# (nome, pasta, comando). A ordem é do mais barato para o mais caro: quem
# roda isto quer o primeiro erro rápido. Toda pasta com `test_*.py` fora de
# `IGNORAR` tem uma suíte aqui — `tests/test_testar_cobre_tudo_regressions.py`
# cobra isso (um teste novo numa pasta nova nascia invisível).
SUITES = (
    ("mimetizar", RAIZ / "mimetizar", _pytest("tests")),
    ("random_builds", RAIZ / "random_builds", _pytest("tests")),
    ("historias", RAIZ / "historias", _pytest("tests")),
    # A pasta, e nao o modulo pelo nome: nomear um arquivo so faz com que
    # todo teste novo ao lado dele nasca invisivel. Aconteceu em 11/09/2026 —
    # cinco testes entraram, o total do repositorio nao mexeu, e o unico
    # sinal foi a conta nao bater.
    ("remoto (bot)", RAIZ, _pytest("remoto")),
    # As fichas das IAs (Vila das IAs, fase 1, 29/09/2026).
    ("ias (fichas)", RAIZ, _pytest("ias")),
    # A `vila/` foi aposentada em 28/09/2026; a Oficina de sprites nova mora
    # no painel (`painel/test_oficina_sprites.py`) e entra aqui.
    ("painel (novo)", RAIZ, _pytest("painel")),
    ("panorama (metricas)", RAIZ, _pytest("visao/tests")),
    # Nunca tinham entrado (SCR-2, 14/10/2026).
    ("coordenador", RAIZ, _pytest("coordenador")),
    ("esteira de sprites", RAIZ, _pytest("esteira_sprites")),
    ("palco", RAIZ, _pytest("palco/testes")),
    ("ferramentas", RAIZ, _pytest("ferramentas")),
    # A maior suite do repositorio. Vem por ultimo por ser a mais cara.
    ("neural_fights", RAIZ, _pytest("tests")),
)

# Pastas com `test_*.py` que NAO sao suite, com o motivo.
IGNORAR_NO_TESTAR = {
    "neural_fights": "testes do motor moram em `tests/` (os 2 avulsos sao "
                     "do pacote e rodam la)",
}
SMOKE = ("painel (páginas)", RAIZ, [PY, "-X", "utf8", "-m", "painel",
                                       "--smoke"])

VERDE, VERMELHO, AMARELO, FIM = "\033[92m", "\033[91m", "\033[93m", "\033[0m"


def _cor(texto: str, cor: str) -> str:
    return f"{cor}{texto}{FIM}" if sys.stdout.isatty() else texto


def _rodar(nome: str, cwd: Path, comando: list, tempo: int = 900) -> dict:
    inicio = time.monotonic()
    ambiente = {**os.environ, **AMBIENTE_ISOLADO}
    try:
        PASTA_DESCARTAVEL.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(comando, cwd=str(cwd), capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=tempo, creationflags=NO_WINDOW,
                              env=ambiente)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"nome": nome, "ok": False, "resumo": f"não rodou: {exc}",
                "segundos": time.monotonic() - inicio, "saida": ""}
    saida = (proc.stdout or "") + (proc.stderr or "")
    # O placar: `N passed` do pytest (desde 14/10, SCR-2) ou o `Ran N` do
    # unittest.
    achado = (re.search(r"(\d+) passed", saida)
              or re.search(r"^Ran (\d+) test", saida, re.M))
    quantos = int(achado.group(1)) if achado else 0
    falhas = (re.findall(r"^FAILED (\S+)", saida, re.M)
              + re.findall(r"^ERROR (\S+)", saida, re.M)
              + re.findall(r"^(?:FAIL|ERROR): (\S+)", saida, re.M))
    ok = proc.returncode == 0
    resumo = (f"{quantos} testes" if quantos else "ok") if ok else (
        f"{len(falhas)} falha(s)" if falhas else
        f"código {proc.returncode}")
    return {"nome": nome, "ok": ok, "resumo": resumo, "falhas": falhas[:8],
            "segundos": time.monotonic() - inicio, "saida": saida}


def ferramentas() -> dict:
    faltando = [f for f in ("ffmpeg", "ffprobe") if not shutil.which(f)]
    return {"nome": "ferramentas externas", "ok": not faltando,
            "resumo": "ffmpeg e ffprobe no PATH" if not faltando
                      else f"FALTA: {', '.join(faltando)}",
            "falhas": faltando, "segundos": 0.0, "saida": ""}


# Onde procurar byte de controle. Os `.bat` entraram em 01/09/2026 porque o
# defeito aconteceu num deles: o heredoc do shell comeu a barra invertida do
# caminho `ferramentas\abrir.py`, a sequencia barra-a virou o byte 0x07 (BEL)
# e o lancador passou a dizer "Invalid argument" com um nome de arquivo
# impossivel de ler. A checagem so olhava .py e nao viu nada.
#
# (Escrever este comentario introduziu o mesmo byte, e a propria checagem
#  acusou. E o melhor argumento possivel a favor dela.)
EXTENSOES_VIGIADAS = ("*.py", "*.bat", "*.cmd")
# Pastas da raiz que nao sao fonte (SCR-10): saida, perfis de navegador,
# copias de worktree e dependencias.
IGNORAR = {"__pycache__", ".git", ".claude", ".venv", "venv", "node_modules",
           "outputs", ".browser_profile", ".pytest_cache", ".ruff_cache",
           "build", "dist", "videos_onda8"}


def _ignorado(arquivo: Path, raiz: Path | None = None) -> bool:
    try:
        partes = arquivo.relative_to(raiz or RAIZ).parts
    except ValueError:
        partes = arquivo.parts
    return any(p in IGNORAR for p in partes)


def integridade(raiz: Path | None = None) -> dict:
    """Byte de controle no fonte — o defeito que não aparece em teste nenhum.

    Desde 14/10/2026 (SCR-10) varre TODAS as pastas da raiz (menos
    `IGNORAR`) e tambem os `.cmd`: `coordenador/`, `ias/` e `palco/` ficavam
    de fora, e um byte de controle num `.cmd` passava sem ser visto.
    """
    raiz = Path(raiz) if raiz is not None else RAIZ
    permitidos = {9, 10, 13}
    sujos = []
    alvos = []
    for padrao in EXTENSOES_VIGIADAS:
        alvos += [a for a in raiz.rglob(padrao) if not _ignorado(a, raiz)]

    for _ in (1,):
        for arquivo in alvos:
            if "__pycache__" in str(arquivo) or not arquivo.is_file():
                continue
            bruto = arquivo.read_bytes()
            if any(b < 32 and b not in permitidos for b in bruto):
                posicao = next(i for i, b in enumerate(bruto)
                               if b < 32 and b not in permitidos)
                sujos.append(f"{arquivo.name}:{bruto[:posicao].count(10) + 1}")
    return {"nome": "integridade do fonte", "ok": not sujos,
            "resumo": "nenhum byte de controle" if not sujos
                      else f"{len(sujos)} arquivo(s) corrompido(s)",
            "falhas": sujos[:8], "segundos": 0.0, "saida": ""}


def arquitetura() -> dict:
    """A arquitetura piorou desde a ultima medicao?

    E uma catraca, nao uma meta: ela nao exige que os numeros sejam zero,
    exige que nao AUMENTEM. Roda aqui dentro porque ferramenta que so roda
    quando alguem lembra nao protege nada durante um refactor de seis
    etapas.
    """
    ferramenta = RAIZ / "ferramentas" / "auditoria_arquitetura.py"
    if not ferramenta.is_file():
        return {"nome": "arquitetura", "ok": True, "resumo": "sem auditoria",
                "falhas": [], "segundos": 0.0, "saida": ""}
    inicio = time.monotonic()
    proc = subprocess.run([PY, "-X", "utf8", str(ferramenta), "--strict"],
                          cwd=str(RAIZ), capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          creationflags=NO_WINDOW)
    saida = (proc.stdout or "") + (proc.stderr or "")
    piorou = [l.strip() for l in saida.splitlines() if "[PIOR]" in l]
    return {"nome": "arquitetura", "ok": proc.returncode == 0,
            "resumo": "nada piorou" if proc.returncode == 0
                      else f"{len(piorou)} indicador(es) pioraram",
            "falhas": piorou[:8], "segundos": time.monotonic() - inicio,
            "saida": saida}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="testar", description="roda todos os testes do projeto")
    parser.add_argument("--rapido", action="store_true",
                        help="só as suítes (sem o smoke do painel)")
    parser.add_argument("--lista", action="store_true",
                        help="mostra o que seria rodado e sai")
    parser.add_argument("--verboso", action="store_true",
                        help="despeja a saída de quem falhou")
    args = parser.parse_args(argv)

    etapas = [("suite", nome, pasta, cmd) for nome, pasta, cmd in SUITES]
    if not args.rapido:
        etapas.append(("smoke", *SMOKE))

    if args.lista:
        print("verificações rápidas: ferramentas externas, "
              "integridade do fonte, arquitetura")
        for _tipo, nome, pasta, cmd in etapas:
            print(f"  {nome:22} em {pasta.name or '.'}: {' '.join(cmd[-3:])}")
        return 0

    print("=" * 68)
    resultados = [ferramentas(), integridade(), arquitetura()]
    for resultado in resultados:
        marca = _cor("  ok  ", VERDE) if resultado["ok"] else _cor(" FALHA", VERMELHO)
        print(f"[{marca}] {resultado['nome']:24} {resultado['resumo']}")

    for _tipo, nome, pasta, comando in etapas:
        print(f"[ .... ] {nome:24} rodando...", end="\r", flush=True)
        resultado = _rodar(nome, pasta, comando)
        resultados.append(resultado)
        marca = _cor("  ok  ", VERDE) if resultado["ok"] else _cor(" FALHA", VERMELHO)
        print(f"[{marca}] {nome:24} {resultado['resumo']:22} "
              f"{resultado['segundos']:5.1f}s")
        for falha in resultado.get("falhas") or []:
            print(f"           {_cor('x ' + str(falha), VERMELHO)}")
        if args.verboso and not resultado["ok"]:
            print(resultado["saida"][-2500:])

    print("=" * 68)
    ruins = [r for r in resultados if not r["ok"]]
    total = sum(int(re.sub(r"\D", "", r["resumo"]) or 0)
                for r in resultados if r["ok"] and "teste" in r["resumo"])
    segundos = sum(r["segundos"] for r in resultados)
    if ruins:
        print(_cor(f"FALHOU: {', '.join(r['nome'] for r in ruins)}", VERMELHO))
        print("        rode de novo com --verboso para ver a saída.")
        return 1
    print(_cor(f"TUDO VERDE — {total} testes + smoke do painel "
               f"em {segundos:.0f}s", VERDE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
