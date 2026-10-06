from __future__ import annotations

import os
import shutil
import struct
import subprocess
import zlib
from pathlib import Path

import pytest


RAIZ = Path(__file__).resolve().parents[1]
GODOT = Path("E:/ferramentas/godot/Godot_v4.7.2-stable_win64_console.exe")


def _png_solido(caminho: Path, cor: tuple[int, int, int, int]) -> None:
    largura = altura = 1024
    linha = bytes(cor) * largura
    bruto = b"".join(b"\0" + linha for _ in range(altura))
    def bloco(nome: bytes, dados: bytes) -> bytes:
        return struct.pack(">I", len(dados)) + nome + dados + struct.pack(">I", zlib.crc32(nome + dados) & 0xFFFFFFFF)
    caminho.write_bytes(b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", largura, altura, 8, 6, 0, 0, 0)) + bloco(b"IDAT", zlib.compress(bruto)) + bloco(b"IEND", b""))


@pytest.mark.skipif(not GODOT.is_file(), reason="Godot nao encontrado")
def test_previa_sobrepoe_olhos_a_pele():
    raiz = RAIZ / "biblioteca" / "partes" / "lutador"
    saida = RAIZ / ".godot" / "previa_partes_teste.png"
    pele = raiz / "pele" / "personagem" / "teste_previa" / "base.png"
    olhos = raiz / "olhos" / "personagem" / "teste_previa" / "neutro.png"
    try:
        pele.parent.mkdir(parents=True, exist_ok=True)
        olhos.parent.mkdir(parents=True, exist_ok=True)
        _png_solido(pele, (255, 0, 0, 255))
        _png_solido(olhos, (0, 0, 255, 255))
        cmd = [str(GODOT), "--path", str(RAIZ), "res://ferramentas/previa_sprites.tscn", "--",
               "--personagem=Teste Previa", f"--saida={saida.as_posix()}"]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        assert p.returncode == 0, p.stdout + p.stderr
        assert saida.is_file()
        p = subprocess.run([str(GODOT), "--headless", "--path", str(RAIZ), "--script",
                            "res://testes/verificar_previa.gd", "--", f"--png={saida.as_posix()}"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        assert p.returncode == 0, p.stdout + p.stderr
    finally:
        for caminho in [pele, olhos]:
            caminho.unlink(missing_ok=True)
        if not os.environ.get("MANTER_FOLHA_TESTE"):
            saida.unlink(missing_ok=True)
        shutil.rmtree(raiz / "pele" / "personagem" / "teste_previa", ignore_errors=True)
        shutil.rmtree(raiz / "olhos" / "personagem" / "teste_previa", ignore_errors=True)
