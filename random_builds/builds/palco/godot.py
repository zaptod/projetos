"""Rodar o Godot sem atrapalhar ninguem.

Tres jeitos, os tres com o APPDATA trocado SO neste processo (o user:// do
Godot caia no C:, que esta quase cheio; trocar no shell inteiro quebra o
Python):

- `garantir_importado`: `--headless --import` quando algum arquivo do projeto
  mudou (o cache de classes e os imports moram em palco/.godot, fora do git).
- `rodar_script`: `--headless --script` (validacao e testes: sem janela, sem GPU).
- `gravar_filme`: Movie Maker com `--fixed-fps 30` (sem ele sai a 60 fps) e
  `--write-movie`. A janela e de 270x480, SEM FOCO (no_focus no
  project.godot) e fica onde o config/palco.json manda. Minimizada ela NAO
  desenha: a guarda do palco sai com rc 4 em vez de gravar quadro vazio.

Os codigos de saida do palco viram mensagem aqui; qualquer rc != 0 e erro.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

from . import config
from .config import ErroPalco

SEM_JANELA_DE_CONSOLE = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MOTIVOS = {
    2: "job ou timeline invalida (veja os avisos do relatorio)",
    3: "o 1o quadro nao teve delta 1/30: faltou --fixed-fps 30",
    4: "quadro sem desenho: a janela do Godot foi MINIMIZADA (o video sairia com quadros vazios)",
}
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_FONTES = ("*.gd", "*.tscn", "*.tres", "*.gdshader", "*.wav", "*.ogg", "*.mp3", "*.png", "*.svg",
           "*.jpg", "*.webp", "project.godot")
_FORA = {".godot", "_saida", "_logs", "_userdata"}


def ambiente(cfg: dict | None = None) -> dict:
    env = dict(os.environ)
    try:
        env["APPDATA"] = str(config.appdata(cfg))
    except OSError as erro:
        destino = (cfg or {}).get("appdata") or "<projeto do palco>/_userdata"
        raise ErroPalco(f"APPDATA do Godot inacessivel em {destino}: {erro}") from erro
    return env


def _rodar(comando: list, *, timeout: float, cfg: dict) -> tuple[int, str]:
    try:
        processo = subprocess.run(
            [str(c) for c in comando], cwd=str(config.projeto(cfg)), env=ambiente(cfg),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=SEM_JANELA_DE_CONSOLE)
    except subprocess.TimeoutExpired as erro:
        saida = (erro.stdout or "") if isinstance(erro.stdout, str) else ""
        raise ErroPalco(f"o Godot passou de {timeout:.0f} s e foi interrompido\n{saida[-800:]}") from erro
    return processo.returncode, _ANSI.sub("", (processo.stdout or "") + (processo.stderr or ""))


def _mais_novo(pasta: Path) -> float:
    mais_novo = 0.0
    for padrao in _FONTES:
        for arquivo in pasta.rglob(padrao):
            if _FORA.intersection(arquivo.relative_to(pasta).parts):
                continue
            mais_novo = max(mais_novo, arquivo.stat().st_mtime)
    return mais_novo


def garantir_importado(cfg: dict | None = None, *, forcar: bool = False) -> bool:
    """Importa o projeto se algo mudou desde o ultimo import. True = importou."""
    cfg = config.carregar() if cfg is None else cfg
    pasta = config.projeto(cfg)
    marca = pasta / ".godot" / "palco_importado.txt"
    if not forcar and marca.is_file() and marca.stat().st_mtime >= _mais_novo(pasta):
        return False
    rc, saida = _rodar([config.godot(cfg), "--headless", "--path", pasta, "--import"],
                       timeout=float(cfg.get("timeout_s", 900)), cfg=cfg)
    erros = [linha for linha in saida.splitlines() if "SCRIPT ERROR" in linha or "Parse Error" in linha
             or "Failed to load script" in linha]
    if rc != 0 or erros:
        raise ErroPalco("o import do palco falhou (rc %d):\n%s" % (rc, "\n".join(erros[:12]) or saida[-1500:]))
    marca.parent.mkdir(parents=True, exist_ok=True)
    marca.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return True


def rodar_script(script: str, argumentos: list | None = None, *, cfg: dict | None = None,
                 timeout: float = 300) -> tuple[int, str]:
    cfg = config.carregar() if cfg is None else cfg
    garantir_importado(cfg)
    return _rodar([config.godot(cfg), "--headless", "--path", config.projeto(cfg), "--script", script,
                   "--", *(argumentos or [])], timeout=timeout, cfg=cfg)


def _tamanho_da_previa() -> list:
    """A previa em 9:16 com a altura da area util da tela (02/10/2026: abria em
    286x519 no canto e o Adrian "nao conseguia ver o palco")."""
    try:
        import ctypes
        from ctypes import wintypes
        area = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(area), 0)  # SPI_GETWORKAREA
        altura = max(480, area.bottom - area.top - 60)
        largura = int(altura * 9 / 16)
        # sem --position: com ele a janela abria fora da tela (x=-879); o Godot centraliza
        return ["--resolution", f"{largura}x{altura}"]
    except Exception:                                          # noqa: BLE001
        return ["--resolution", "405x720"]


def abrir_previa(timeline, *, cfg: dict | None = None) -> Path:
    """Abre a timeline no palco em loop, com os mesmos sons do render."""
    from . import sons

    cfg = config.carregar() if cfg is None else cfg
    timeline = Path(timeline).resolve()
    if not timeline.is_file():
        raise ErroPalco(f"timeline para previa nao encontrada em {timeline}")
    projeto = config.projeto(cfg)
    exe = config.godot(cfg)
    garantir_importado(cfg)
    try:
        from neural_fights.recording import timeline_arquivo
        documento = timeline_arquivo.carregar(timeline)
    except (OSError, ValueError) as erro:
        raise ErroPalco(f"nao consegui ler a timeline {timeline}: {erro}") from erro
    itens = ((documento.get("sons") or {}).get("itens") or [])
    job = timeline.with_suffix(".previsao.json")
    job.write_text(json.dumps({
        "timeline": str(timeline),
        "preview": True,
        "sons_arquivos": sons.arquivos_de_som(item.get("id") for item in itens),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    janela = exe.with_name(exe.name.replace("_console", ""))
    processo = subprocess.Popen(
        [str(janela if janela.is_file() else exe), "--path", str(projeto),
         *_tamanho_da_previa(), "--", f"--job={job}"],
        cwd=str(projeto), env=ambiente(cfg), creationflags=SEM_JANELA_DE_CONSOLE,
    )
    if processo.poll() is not None:
        raise ErroPalco(f"o Godot nao abriu a previa (codigo {processo.returncode})")
    return job


def abrir_arquivo(caminho) -> None:
    """Abre o mp4 produzido pelo palco no aplicativo padrao do Windows."""
    caminho = Path(caminho).resolve()
    if not caminho.is_file():
        raise ErroPalco(f"mp4 do palco nao encontrado em {caminho}")
    try:
        os.startfile(str(caminho))
    except AttributeError as erro:
        raise ErroPalco(f"nao sei abrir o mp4 fora do Windows: {caminho}") from erro


def gravar_filme(job: Path | None, avi: Path, *, cfg: dict | None = None, posicao=None,
                 timeout: float | None = None, cena: str | None = None, argumentos: list | None = None) -> dict:
    """Grava o AVI (MJPEG + PCM 48 kHz). Devolve rc, saida e segundos; rc != 0
    vira ErroPalco em quem chama, com o motivo de MOTIVOS. `cena` troca a cena
    principal (a vitrine: res://ferramentas/vitrine.tscn)."""
    cfg = config.carregar() if cfg is None else cfg
    garantir_importado(cfg)
    comando = [config.godot(cfg), "--path", config.projeto(cfg)]
    if cena:
        comando.append(cena)
    posicao = posicao if posicao is not None else (cfg.get("janela") or {}).get("posicao")
    if posicao:
        comando += ["--position", f"{int(posicao[0])},{int(posicao[1])}"]
    comando += ["--fixed-fps", str(int(cfg.get("fps", 30))), "--write-movie", str(avi), "--",
                *([f"--job={job}"] if job else []), *(argumentos or [])]
    inicio = time.time()
    rc, saida = _rodar(comando, timeout=float(timeout or cfg.get("timeout_s", 900)), cfg=cfg)
    return {"rc": rc, "saida": saida, "segundos": round(time.time() - inicio, 1),
            "motivo": MOTIVOS.get(rc, "" if rc == 0 else f"o Godot saiu com rc {rc}"),
            "comando": [str(c) for c in comando]}
