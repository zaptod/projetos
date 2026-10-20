# -*- coding: utf-8 -*-
"""O `Vila.exe` e o atalho "Vila" na area de trabalho: abrem a Vila flutuante.

    python -m ferramentas.vila_exe          compila o .exe e cria o atalho

POR QUE EXISTE. 19/10/2026, pedido do Adrian: a Vila no ar o tempo todo
irritava e gastava RAM. Desde entao ela e `sob_demanda` no coordenador
(`coordenador/servicos.json`): fechada, FICA fechada. Reabrir e por aqui.

O .exe so lanca `pythonw -X utf8 -m painel.flutuante --medio` na raiz do
projeto, sem console. Se a Vila ja estiver aberta, ela mesma traz a janela
para a frente (instancia unica, `painel/flutuante/__main__.py`). Compilado
com o `csc` do .NET Framework que vem no Windows; os caminhos (pythonw e
raiz) entram no .exe na hora de compilar, entao rode de novo se o Python
mudar. O .exe e o .ico sao gerados e ficam fora do git.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "ferramentas" / "vila"
EXE = PASTA / "Vila.exe"
ICONE = PASTA / "vila.ico"
DESENHO = RAIZ / "painel" / "flutuante" / "arte_vila" / "predios" / "casa.png"
CSC = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework64" / \
    "v4.0.30319" / "csc.exe"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

FONTE = r"""
using System;
using System.Diagnostics;
using System.Windows.Forms;

static class AbrirVila {
    [STAThread]
    static void Main() {
        try {
            var info = new ProcessStartInfo(@"@PYTHONW@", "-X utf8 -m painel.flutuante --medio");
            info.WorkingDirectory = @"@RAIZ@";
            info.UseShellExecute = false;
            Process.Start(info);
        } catch (Exception erro) {
            MessageBox.Show("Nao consegui abrir a Vila:\n" + erro.Message, "Vila");
        }
    }
}
"""


def pythonw() -> Path:
    alvo = Path(sys.executable).with_name("pythonw.exe")
    if not alvo.is_file():
        raise FileNotFoundError(f"nao achei o pythonw.exe ao lado de {sys.executable}")
    return alvo


def fonte(executavel: Path, raiz: Path) -> str:
    """O C# com os caminhos dentro (`@"..."`: aspas dobradas por dentro)."""
    return (FONTE.replace("@PYTHONW@", str(executavel).replace('"', '""'))
            .replace("@RAIZ@", str(raiz).replace('"', '""')))


def fazer_icone(destino: Path = ICONE) -> Path:
    from PIL import Image
    imagem = Image.open(DESENHO).convert("RGBA")
    imagem = imagem.crop(imagem.getbbox() or (0, 0, *imagem.size))
    lado = max(imagem.size)
    quadrado = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    quadrado.paste(imagem, ((lado - imagem.width) // 2, (lado - imagem.height) // 2))
    quadrado.save(destino, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                  (128, 128), (256, 256)])
    return destino


def compilar() -> Path:
    PASTA.mkdir(parents=True, exist_ok=True)
    fazer_icone()
    codigo = PASTA / "AbrirVila.cs"
    codigo.write_text(fonte(pythonw(), RAIZ), encoding="utf-8")
    feito = subprocess.run([str(CSC), "/nologo", "/target:winexe", f"/out:{EXE}",
                            f"/win32icon:{ICONE}", "/r:System.Windows.Forms.dll", str(codigo)],
                           capture_output=True, text=True, errors="replace",
                           creationflags=NO_WINDOW)
    if feito.returncode != 0:
        raise RuntimeError(f"csc falhou: {(feito.stdout + feito.stderr).strip()}")
    return EXE


def criar_atalho(nome: str = "Vila") -> Path:
    """O atalho na area de trabalho, pelo WScript.Shell do Windows."""
    script = (
        "$ErrorActionPreference = 'Stop'; "
        "$area = [Environment]::GetFolderPath('Desktop'); "
        f"$a = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $area '{nome}.lnk')); "
        f"$a.TargetPath = '{EXE}'; $a.WorkingDirectory = '{RAIZ}'; "
        f"$a.IconLocation = '{EXE},0'; $a.Description = 'Abre a Vila flutuante'; "
        "$a.Save(); Join-Path $area '" + nome + ".lnk'")
    feito = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                           capture_output=True, text=True, errors="replace",
                           creationflags=NO_WINDOW)
    if feito.returncode != 0:
        raise RuntimeError(f"atalho falhou: {feito.stderr.strip()}")
    return Path(feito.stdout.strip())


def main() -> int:
    try:
        print(f"exe: {compilar()}")
        print(f"atalho: {criar_atalho()}")
    except (OSError, RuntimeError) as erro:
        print(f"FALHOU: {erro}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
