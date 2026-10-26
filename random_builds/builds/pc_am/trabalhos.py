# -*- coding: utf-8 -*-
"""Os trabalhos que ja sabem ir ao am. Cada um tem a SUA chave em
`config/pc_am.json -> trabalhos` (padrao desligada = roda aqui como sempre).

  testes    `testar_no_am("coordenador")`: uma suite do pytest no am;
            o que volta e o log e o placar (`N passed, M failed`).
  duelo     `duelo(...)`: o MESMO `main.py duelo --p1 --p2 --seed` que a
            geracao faria aqui. O par e a semente sao escolhidos AQUI (com o
            ledger daqui), o am grava e renderiza, e a pasta volta como o
            proximo `outputs/duelo_XXXXX` daqui, com os caminhos do JSON
            trocados para os daqui e a luta registrada no ledger daqui.
  bluelock  `bluelock_gravar([...])`: o `python -m bluelock.gravar` no
            clone do Blue Lock do am, no commit do espelho daqui.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from . import maquina
from .maquina import RAIZ, RAIZ_RB, URL_BLUE_LOCK, URL_PROJETOS, Trabalho

OUTPUTS = RAIZ_RB / "outputs"
RB = "projetos/random_builds"
REPO_PROJETOS = {"nome": "projetos", "raiz": RAIZ, "url": URL_PROJETOS, "mudancas": True}
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
AMBIENTE_DE_TESTE = {"NEURAL_FIGHTS_RUNTIME_DIR": "{BASE}\\tmp\\testar-runtime",
                     "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy", "PYTHONUTF8": "1"}
# As suites que rodam de DENTRO da pasta do projeto (como no testar.py).
PROJETOS_COM_RAIZ = ("random_builds", "historias", "mimetizar")


def ligado(tipo: str) -> bool:
    return maquina.ligado(tipo)


def _prazo(tipo: str, cfg: dict, padrao: float) -> float:
    return float((cfg.get("prazo_s") or {}).get(tipo) or padrao)


# ------------------------------------------------------------------ testes
def _alvo_dos_testes(pasta: str) -> tuple[str, str]:
    """(cwd relativo ao repo, alvo do pytest). `random_builds` = a suite do
    testar.py (`pytest tests` de dentro de random_builds/)."""
    pasta = pasta.replace("\\", "/").strip("/")
    topo, _, resto = pasta.partition("/")
    if topo in PROJETOS_COM_RAIZ:
        return topo, resto or "tests"
    return "", pasta


def placar(log: str) -> str:
    achado = re.findall(r"^=*\s*((?:\d+ \w+(?:, )?)+) in [\d.]+s", log or "", re.M)
    return achado[-1] if achado else ""


def testar_no_am(pasta: str, extras: list[str] | None = None, *, forcar: bool = False,
                 cfg: dict | None = None, transporte=None, mudancas: bool = True,
                 **kw) -> maquina.Resultado:
    cfg = cfg if cfg is not None else maquina.carregar_config()
    cwd, alvo = _alvo_dos_testes(pasta)
    argumentos = ["-X", "utf8", "-m", "pytest", "-q", "-p", "no:cacheprovider", alvo, *(extras or [])]
    trabalho = Trabalho(tipo="testes", comando=["{PY}", *argumentos],
                        cwd="projetos" + (f"/{cwd}" if cwd else ""), env=dict(AMBIENTE_DE_TESTE),
                        prazo_s=_prazo("testes", cfg, 2400), aceitar_rc=(0, 1, 5),
                        repos=[dict(REPO_PROJETOS, mudancas=mudancas)], fabrica="pc_am",
                        rotulo=f"testes {pasta}")

    def local():
        ambiente = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy", "PYTHONUTF8": "1"}
        if Path(r"E:\tmp_pytest").is_dir():
            ambiente["TEMP"] = ambiente["TMP"] = r"E:\tmp_pytest"
        proc = subprocess.run([sys.executable, *argumentos], cwd=str(RAIZ / cwd) if cwd else str(RAIZ),
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=ambiente, creationflags=NO_WINDOW)
        return {"rc": proc.returncode, "log": (proc.stdout or "") + (proc.stderr or "")}

    resultado = maquina.executar(trabalho, local, cfg=cfg, transporte=transporte, forcar=forcar, **kw)
    if resultado.onde == "aqui":
        resultado.rc = resultado.valor["rc"]
        resultado.log = resultado.valor["log"]
    resultado.ok = resultado.rc == 0
    return resultado


# ------------------------------------------------------------------- duelo
def _arquivos(pasta: Path) -> list[Path]:
    return sorted(p for p in pasta.rglob("*") if p.is_file()) if pasta.is_dir() else []


def entradas_do_duelo(p1: str, p2: str) -> tuple[list, list, list]:
    """(entradas, espelhar, limpar) — tudo que o duelo le e o git nao tem.

    Levantado em 19/10/2026 lendo o caminho do `main.py duelo`: o banco vivo
    (personagens/armas do runtime: o do pacote tem outros 64 nomes), os sons
    do runtime (mudam a cauda pos-K.O.), o ledger da arena (cartel, revanche,
    titulo vao para o fight.json), os `insercao.json` (vencedor_gerado), a
    arte dos dois para a capa e a trilha de `assets/music`."""
    from ..contas import runtime_dir
    from ..publicar.capa import arte_do_personagem
    rt = runtime_dir()
    entradas, espelhar, limpar = [], [], []
    for nome in ("personagens.json", "armas.json"):
        if (rt / nome).is_file():
            entradas.append((rt / nome, f"runtime/{nome}"))
        else:
            limpar.append(f"runtime/{nome}")
    sons = [(f, "runtime/sounds/" + f.relative_to(rt / "sounds").as_posix()) for f in _arquivos(rt / "sounds")]
    entradas += sons
    espelhar.append(("runtime/sounds/*", [rel for _, rel in sons]))
    ledger = OUTPUTS / "_arena" / "ledger.json"
    if ledger.is_file():
        entradas.append((ledger, f"{RB}/outputs/_arena/ledger.json"))
    else:
        limpar.append(f"{RB}/outputs/_arena/ledger.json")
    geracoes = []
    for insercao in sorted(OUTPUTS.glob("generation_*/insercao.json")):
        entradas.append((insercao, f"{RB}/outputs/{insercao.parent.name}/insercao.json"))
        geracoes.append(f"{RB}/outputs/{insercao.parent.name}")
    for nome in (p1, p2):
        arte = arte_do_personagem(nome)
        if arte is not None:
            entradas.append((arte, f"{RB}/outputs/{arte.parent.name}/{arte.name}"))
    espelhar.append((f"{RB}/outputs/generation_*", geracoes))
    musica = [(f, f"{RB}/assets/music/{f.name}") for f in _arquivos(RAIZ_RB / "assets" / "music")
              if f.name != ".gitkeep"]
    entradas += musica
    espelhar.append((f"{RB}/assets/music/*", [rel for _, rel in musica] + [f"{RB}/assets/music/.gitkeep"]))
    # (os duelos de la NAO sao apagados antes: com varios ao mesmo tempo, um
    # apagaria o do outro. Cada um traz o SEU, pelo log, e o apaga la depois.)
    return entradas, espelhar, limpar


def _trocar(valor, trocas: list[tuple[str, str]], ids: tuple[str, str]):
    if isinstance(valor, dict):
        return {k: _trocar(v, trocas, ids) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_trocar(v, trocas, ids) for v in valor]
    if isinstance(valor, str):
        if valor == ids[0]:
            return ids[1]
        for antes, depois in trocas:
            if antes in valor:
                valor = valor.replace(antes, depois)
        return valor
    return valor


def reescrever_caminhos(pasta: Path, remoto: str, local: Path, id_remoto: str, id_local: str) -> int:
    """Troca, em todo .json da pasta, o caminho do am pelo daqui e o id.

    `remoto` e a pasta do duelo no am (C:\\nf\\projetos\\...\\duelo_00001)."""
    remoto_raiz = remoto.split("\\random_builds\\", 1)[0]          # C:\nf\projetos
    trocas = []
    for antes, depois in ((remoto, str(local)), (remoto_raiz, str(RAIZ))):
        trocas.append((antes, depois))
        trocas.append((antes.replace("\\", "/"), depois.replace("\\", "/")))
    mudados = 0
    for arquivo in pasta.rglob("*.json"):
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except ValueError:
            continue
        novo = _trocar(dados, trocas, (id_remoto, id_local))
        if novo != dados:
            arquivo.write_text(json.dumps(novo, ensure_ascii=False, indent=2), encoding="utf-8")
            mudados += 1
    return mudados


def _proximo_numero(prefixo: str) -> int:
    existentes = [int(p.name.split("_")[1]) for p in OUTPUTS.glob(f"{prefixo}_*")
                  if p.name.split("_")[1].isdigit()]
    return max(existentes, default=0) + 1


def instalar_duelo(local: Path, trabalho: Trabalho, base_remota: str = r"C:\nf") -> Path:
    """A pasta veio do am conferida: vira o proximo `outputs/duelo_XXXXX`.

    O `os.rename` para um nome que nao existe e a reserva E a instalacao no
    mesmo passo (outro processo que pegou o numero faz o rename falhar, e o
    proximo numero e tentado)."""
    id_remoto = local.name
    remoto = base_remota + "\\" + RB.replace("/", "\\") + "\\outputs\\" + id_remoto
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    for _ in range(20):
        id_local = f"duelo_{_proximo_numero('duelo'):05d}"
        destino = OUTPUTS / id_local
        reescrever_caminhos(local, remoto, destino, id_remoto, id_local)
        try:
            os.rename(local, destino)
        except FileExistsError:
            remoto, id_remoto = str(destino), id_local           # ja reescrito para este
            continue
        return destino
    raise maquina.FalhaNoAm("nao achei um numero livre para o duelo em 20 tentativas")


def escolher(p1=None, p2=None, seed=None):
    """O par e a semente, como o `controller.duelo` escolheria aqui."""
    from ..arena import rodizio
    from ..arena.ledger import Ledger
    from ..generation.random_engine import RandomEngine
    from ..tournament.runner import fichas_do_banco, personagens_gerados
    seed = seed if seed is not None else RandomEngine.new_seed()
    rng = RandomEngine(seed).fork("duelo:participantes")
    p1, p2 = rodizio.escolher_par(fichas_do_banco(), personagens_gerados(), rng, ledger=Ledger(),
                                  p1=p1, p2=p2)
    if not p1:
        raise ValueError("nao ha personagem no banco para o duelo")
    if not p2:
        raise ValueError("nao ha adversario disponivel no banco")
    return p1, p2, seed


def registrar_no_ledger(pasta: Path) -> dict:
    from ..arena.ledger import Ledger
    fight = json.loads((pasta / "fight.json").read_text(encoding="utf-8"))
    ledger = Ledger()
    for round_ in fight.get("lutas", []):
        ledger.registrar(round_, origem="duelo", video=str(pasta))
    return fight


def duelo(controlador=None, p1=None, p2=None, seed=None, cenario=None, preview=False, *,
          forcar=False, cfg=None, transporte=None, **kw) -> Path:
    """O duelo da geracao. Chave desligada / am fora: `controlador.duelo(...)`
    aqui, com o MESMO par e a mesma semente."""
    cfg = cfg if cfg is not None else maquina.carregar_config()
    p1, p2, seed = escolher(p1, p2, seed)

    def local():
        if controlador is None:
            from ..pipeline.controller import PipelineController
            return PipelineController().duelo(p1=p1, p2=p2, seed=seed, cenario=cenario, preview=preview)
        return controlador.duelo(p1=p1, p2=p2, seed=seed, cenario=cenario, preview=preview)

    if not (forcar or maquina.ligado("duelo", cfg)):
        return local()
    entradas, espelhar, limpar = entradas_do_duelo(p1, p2)
    comando = ["{PY}", "-X", "utf8", "main.py", "duelo", "--p1", p1, "--p2", p2, "--seed", str(seed)]
    if cenario:
        comando += ["--arena", cenario]
    if preview:
        comando.append("--preview")
    base_remota = str(cfg.get("pasta") or "C:/nf").replace("/", "\\")
    trabalho = Trabalho(tipo="duelo", comando=comando, cwd=RB,
                        env={"NEURAL_FIGHTS_RUNTIME_DIR": "{BASE}\\runtime"},
                        entradas=entradas, espelhar=espelhar, limpar_antes=limpar,
                        saida_pelo_log=(r"outputs[\\/](duelo_\d{5})[\\/]", f"{RB}/outputs/{{}}"),
                        destino=OUTPUTS / "duelo_pc_am",
                        instalar=lambda local_, t: instalar_duelo(local_, t, base_remota),
                        prazo_s=_prazo("duelo", cfg, 1200), repos=[dict(REPO_PROJETOS)],
                        fabrica="arena", rotulo=f"duelo {p1} x {p2} seed {seed}")
    resultado = maquina.executar(trabalho, local, cfg=cfg, transporte=transporte, forcar=forcar, **kw)
    if resultado.onde == "aqui":
        return resultado.valor
    pasta = resultado.destino
    fight = registrar_no_ledger(pasta)
    luta = fight.get("luta") or {}
    print(f"[duelo] {pasta.name} (PC am, {resultado.segundos:.0f} s) seed={fight.get('seed')} "
          f"{p1} vs {p2} -> {fight.get('vencedor')} ({luta.get('ko_type')}, {luta.get('duracao')}s)")
    return pasta


# ---------------------------------------------------------------- blue lock
def _espelho_blue_lock() -> Path:
    return Path(os.environ.get("NF_BLUELOCK_ESPELHO") or r"E:\BLUE-Lock-project")


def bluelock_gravar(argumentos: list[str], *, forcar=False, cfg=None, transporte=None, **kw):
    """`python -m bluelock.gravar <argumentos>` no am; o mp4 e o json voltam
    para a pasta do `--saida` daqui. `--espelho` e `--forcar` sao do am (la
    nao ha publicacao nem LoL para respeitar)."""
    cfg = cfg if cfg is not None else maquina.carregar_config()
    argumentos = list(argumentos)
    if "--saida" not in argumentos:
        raise ValueError("bluelock-gravar precisa de --saida")
    i = argumentos.index("--saida")
    saida_local = Path(argumentos[i + 1])
    resultado_local = None
    if "--resultado" in argumentos:
        j = argumentos.index("--resultado")
        resultado_local = Path(argumentos[j + 1])
        del argumentos[j:j + 2]
        i = argumentos.index("--saida")
    remoto_rel = "saida-bluelock"

    def local():
        extra = ["--resultado", str(resultado_local)] if resultado_local else []
        proc = subprocess.run([sys.executable, "-X", "utf8", "-m", "bluelock.gravar", *argumentos, *extra],
                              cwd=str(RAIZ), creationflags=NO_WINDOW)
        return proc.returncode

    if not (forcar or maquina.ligado("bluelock", cfg)):
        return maquina.Resultado(onde="aqui", motivo="chave desligada", rc=local())
    remotos = [a for k, a in enumerate(argumentos) if k not in (i, i + 1)]
    if "--espelho" in remotos:
        k = remotos.index("--espelho")
        del remotos[k:k + 2]
    trabalho = Trabalho(tipo="bluelock", comando=[], cwd="projetos", env={"NEURAL_FIGHTS_RUNTIME_DIR": "{BASE}\\runtime"},
                        prazo_s=_prazo("bluelock", cfg, 1800), fabrica="estudio", canal="bluelock",
                        repos=[dict(REPO_PROJETOS),
                               {"nome": "BLUE-Lock-project", "raiz": _espelho_blue_lock(), "url": URL_BLUE_LOCK,
                                "mudancas": False}],
                        destino=saida_local.parent, modo_destino="arquivos",
                        rotulo=f"Blue Lock {saida_local.name}",
                        # o Vite do gravador numa porta fixa (5199): um por vez
                        recursos=["bluelock-gravar"],
                        # o WebGL precisa da placa: na sessao 0 do SSH so ha SwiftShader
                        # (10 s de partida = 913 s no am, 19/10/2026)
                        sessao_interativa="--software" not in remotos)
    pasta_remota = f"trabalhos/{trabalho.id}/{remoto_rel}"
    trabalho.saida = pasta_remota
    trabalho.comando = ["{PY}", "-X", "utf8", "-m", "bluelock.gravar", *remotos,
                        "--saida", "{BASE}\\" + pasta_remota.replace("/", "\\") + "\\" + saida_local.name,
                        "--espelho", "{BASE}\\BLUE-Lock-project", "--forcar"]
    resultado = maquina.executar(trabalho, local, cfg=cfg, transporte=transporte, forcar=forcar, **kw)
    if resultado.onde == "aqui":
        resultado.rc = resultado.valor
        return resultado
    json_local = saida_local.with_suffix(".json")
    if json_local.is_file():
        # o "arquivo" do JSON aponta para o mp4 la no am: passa a apontar o daqui
        remoto = (str(cfg.get("pasta") or "C:/nf").replace("/", "\\") + "\\"
                  + pasta_remota.replace("/", "\\"))
        dados = json.loads(json_local.read_text(encoding="utf-8"))
        dados = _trocar(dados, [(remoto, str(saida_local.parent))], ("", ""))
        json_local.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    if resultado_local and json_local.is_file() and json_local != resultado_local:
        os.replace(json_local, resultado_local)
    return resultado


# ------------------------------------------------- npm test do Blue Lock
NPM = r"C:\Program Files\nodejs\npm.cmd"


def testar_blue_lock_no_am(sha: str | None = None, *, cfg=None, transporte=None, **kw) -> maquina.Resultado:
    """`npm test -- --testTimeout=60000` no clone do Blue Lock do am.

    `sha` None = o commit do espelho daqui; com `sha` (um ramo do vigia), o
    am busca o commit no GitHub. So no am: nao ha `local()` (o vigia dos
    ramos cai no teste dele daqui, como sempre, se isto falhar)."""
    cfg = cfg if cfg is not None else maquina.carregar_config()
    repo = {"nome": "BLUE-Lock-project", "raiz": _espelho_blue_lock(), "url": URL_BLUE_LOCK, "mudancas": False}
    if sha:
        repo["commit"] = sha
    from bluelock import vigia
    trabalho = Trabalho(tipo="testes", perfil="npm",
                        comando=[NPM, "test", "--", f"--testTimeout={vigia.TEMPO_POR_TESTE_MS}"],
                        cwd="BLUE-Lock-project", env={"CI": "1", "NO_COLOR": "1", "FORCE_COLOR": "0"},
                        prazo_s=vigia.NPM_TEST_PRAZO_S, aceitar_rc=(0, 1), repos=[repo], fabrica="pc_am",
                        canal="bluelock", rotulo=f"npm test Blue Lock {(sha or 'espelho')[:10]}")

    def local():
        raise maquina.AmFora("npm test do Blue Lock so roda no am por aqui")
    kw.setdefault("cair_para_aqui", False)
    kw.setdefault("cair_na_falha", False)
    return maquina.executar(trabalho, local, cfg=cfg, transporte=transporte, forcar=True, **kw)


def ficha_de_ramo(resultado: maquina.Resultado) -> dict:
    """O resultado do am no formato do `VigiaDeRamos._testar_real`."""
    from bluelock import vigia
    ficha = {"rodou": True, "ok": resultado.rc == 0, "onde": "am", "duracao_s": resultado.etapas.get("no_am")}
    ficha.update(vigia.resumo_de_testes(resultado.log))
    estouros = resultado.log.count("Test timed out")
    if estouros:
        ficha["por_tempo"] = estouros
    if resultado.rc != 0:
        ficha["falhas"] = [linha.strip() for linha in vigia._ANSI.sub("", resultado.log).splitlines()
                           if linha.strip().startswith(("FAIL", "×"))][:8]
    return ficha


# ------------------------------------------------- voz das roletas (SAPI)
# Decisao `builds/voz-do-windows-12-a-19-10` (19/10/2026): refazer a voz SO do
# estoque nao publicado. A janela do 403 do edge-tts: 12/10 01:07 a 19/10.
FAIXA_DA_VOZ = (126, 185)
VOZ_SAPI_DE, VOZ_SAPI_ATE = "2026-10-12T01:00:00", "2026-10-19T18:00:00"
MARCA_DA_VOZ = "voz_refeita.json"
TENTATIVAS_DA_VOZ = 2
FORA_DA_VOZ = ("_segments_celular", "_segments_normal")


def _publicadas_como_build() -> set:
    from ..publicar import metricas
    return {linha.get("fonte_id") for linha in metricas.publicados("builds")
            if linha.get("origem") == "build" and linha.get("fonte_id")}


def roletas_da_voz(publicadas: set | None = None) -> list[str]:
    """As roletas da faixa com a voz feita na janela do 403, ainda NAO
    publicadas, sem a voz refeita e sem ter esgotado as tentativas."""
    from datetime import datetime
    publicadas = _publicadas_como_build() if publicadas is None else publicadas
    de, ate = (datetime.fromisoformat(x).timestamp() for x in (VOZ_SAPI_DE, VOZ_SAPI_ATE))
    saida = []
    for numero in range(FAIXA_DA_VOZ[0], FAIXA_DA_VOZ[1] + 1):
        gid = f"generation_{numero:05d}"
        pasta = OUTPUTS / gid
        voz = pasta / "voz.wav"
        if gid in publicadas or not voz.is_file() or not list(pasta.glob("final_*.mp4")):
            continue
        if not de <= voz.stat().st_mtime < ate:
            continue
        try:
            marca = json.loads((pasta / MARCA_DA_VOZ).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            marca = {}
        if marca.get("feita") or int(marca.get("tentativas", 0)) >= TENTATIVAS_DA_VOZ:
            continue
        saida.append(gid)
    return saida


def _marcar_voz(gid: str, **campos) -> None:
    caminho = OUTPUTS / gid / MARCA_DA_VOZ
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    dados.update(campos)
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporario, caminho)


def instalar_voz(local: Path, trabalho: Trabalho, base_remota: str = r"C:\nf") -> Path:
    """Os arquivos refeitos (finais, plano, voz) entram na pasta da geracao
    daqui, um `os.replace` por arquivo, com os caminhos do am trocados."""
    gid = local.name
    destino = OUTPUTS / gid
    remoto_raiz = base_remota + "\\projetos"
    trocas = [(remoto_raiz, str(RAIZ)), (remoto_raiz.replace("\\", "/"), str(RAIZ).replace("\\", "/"))]
    for arquivo in local.glob("*.json"):
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except ValueError:
            continue
        arquivo.write_text(json.dumps(_trocar(dados, trocas, ("", "")), ensure_ascii=False, indent=2),
                           encoding="utf-8")
    # finais por ULTIMO: ate o ultimo replace, a pasta tem o video velho inteiro
    arquivos = sorted(local.iterdir(), key=lambda p: (p.suffix == ".mp4", p.name))
    for arquivo in arquivos:
        if arquivo.is_file():
            os.replace(arquivo, destino / arquivo.name)
    return destino


def refazer_voz(gid: str, *, cfg=None, transporte=None, **kw) -> maquina.Resultado:
    """Refaz a voz de `gid` NO AM (sem `local()`: aqui seria horas de render)."""
    cfg = cfg if cfg is not None else maquina.carregar_config()
    from ..contas import runtime_dir
    pasta = OUTPUTS / gid
    remoto = f"{RB}/outputs/{gid}"
    entradas = []
    for arquivo in sorted(p for p in pasta.rglob("*") if p.is_file()):
        partes = arquivo.relative_to(pasta).parts
        if partes[0] in FORA_DA_VOZ or (len(partes) > 1 and partes[1] in FORA_DA_VOZ):
            continue
        if arquivo.name.startswith("final_") and arquivo.suffix == ".mp4":
            continue
        entradas.append((arquivo, f"{remoto}/{'/'.join(partes)}"))
    reacoes = [(f, f"{RB}/assets/reactions/" + f.relative_to(RAIZ_RB / "assets" / "reactions").as_posix())
               for f in _arquivos(RAIZ_RB / "assets" / "reactions")]
    musica = [(f, f"{RB}/assets/music/{f.name}") for f in _arquivos(RAIZ_RB / "assets" / "music")]
    rt = runtime_dir()
    banco = [(rt / n, f"runtime/{n}") for n in ("personagens.json", "armas.json") if (rt / n).is_file()]
    base_remota = str(cfg.get("pasta") or "C:/nf").replace("/", "\\")
    trabalho = Trabalho(tipo="voz", comando=[], cwd=RB, env={"NEURAL_FIGHTS_RUNTIME_DIR": "{BASE}\\runtime"},
                        entradas=entradas + reacoes + musica + banco,
                        limpar_antes=[f"{remoto}/final_*", f"{remoto}/_segments_*"],
                        destino=pasta, instalar=lambda local_, t: instalar_voz(local_, t, base_remota),
                        prazo_s=_prazo("voz", cfg, 3600), repos=[dict(REPO_PROJETOS, mudancas=False)],
                        fabrica="estudio", rotulo=f"voz refeita {gid}")
    saida = f"trabalhos/{trabalho.id}/saida"
    trabalho.comando = ["{PY}", "-X", "utf8", "-m", "builds.pc_am.refazer_voz", gid,
                        "--saida", "{BASE}\\" + saida.replace("/", "\\")]
    trabalho.saida = f"{saida}/{gid}"
    trabalho.limpar_depois = [remoto]

    def local():
        raise maquina.AmFora("a voz das roletas so e refeita no am")
    kw.setdefault("cair_para_aqui", False)
    kw.setdefault("cair_na_falha", False)
    try:
        resultado = maquina.executar(trabalho, local, cfg=cfg, transporte=transporte, forcar=True, **kw)
    except maquina.FalhaNoAm as exc:
        marca = {}
        try:
            marca = json.loads((pasta / MARCA_DA_VOZ).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        _marcar_voz(gid, tentativas=int(marca.get("tentativas", 0)) + 1, ultimo_erro=str(exc)[:300])
        raise
    from datetime import datetime
    _marcar_voz(gid, feita=True, em=datetime.now().isoformat(timespec="seconds"), onde="am",
                trabalho=trabalho.id)
    return resultado
