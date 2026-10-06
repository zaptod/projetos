"""Pecas modulares do lutador no palco Godot, conferidas em PIXEL na folha do
"Ver no Godot" (palco/ferramentas/previa_sprites.gd).

Rodam so com NF_TESTE_GODOT=1 (abrem o Godot com janela: no modo headless a
leitura do viewport nao fecha). Cada prevista leva ~7 s.

A geometria da folha (2 colunas x 3 linhas, raio 170 px) e a mesma de
`previa_sprites.gd::centro_celula`; o rosto segue `rosto.gd` (olhos em
(0,20R, +-0,36R), boca em (0,66R, 0), +x = para onde o lutador olha).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


RAIZ = Path(__file__).resolve().parents[1]
GODOT = Path("E:/ferramentas/godot/Godot_v4.7.2-stable_win64_console.exe")
TIMEOUT = 60

pytestmark = pytest.mark.skipif(not GODOT.is_file() or os.environ.get("NF_TESTE_GODOT") != "1",
                                reason="Godot nao encontrado ou teste visual nao solicitado")

# previa_sprites.gd
RAIO = 170.0
CORES = [0xD86565, 0xBD78E8, 0x5DBB8A, 0x6D9BE8, 0xE8B35F, 0xDC7AA3]


def _centro(k: int) -> tuple[float, float]:
    return ((k % 2 + 0.5) * 540.0, 190.0 + (k // 2) * 576.0 + 330.0)


def _peca(caminho: Path, desenhar) -> None:
    Image = pytest.importorskip("PIL.Image")
    ImageDraw = pytest.importorskip("PIL.ImageDraw")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    desenhar(ImageDraw.Draw(im))
    im.save(caminho)


def _biblioteca(tmp_path: Path, pecas: dict) -> Path:
    """`pecas`: {(parte, nivel, alvo, estado): funcao de desenho no gabarito 1024}.
    O manifesto aponta o destino de cada uma, como o painel grava."""
    biblioteca = tmp_path / "biblioteca"
    slots = []
    for (parte, nivel, alvo, estado), desenhar in pecas.items():
        rel = f"partes/lutador/{parte}/{nivel}/{alvo}/v01/{estado}.png"
        _peca(biblioteca / rel, desenhar)
        slots.append({"grupo": "lutador", "parte": parte, "alvo": {"nivel": nivel, "chave": alvo},
                      "estado": estado, "destino": "palco/biblioteca/" + rel})
    biblioteca.mkdir(parents=True, exist_ok=True)
    (biblioteca / "manifesto_slots.json").write_text(json.dumps({"slots": slots}), encoding="utf-8")
    return biblioteca


def _env(tmp_path: Path) -> dict:
    """APPDATA so do processo do Godot (user:// e cache de shader fora do C:)."""
    env = dict(os.environ)
    env["APPDATA"] = str(tmp_path / "appdata_godot")
    return env


def _previa(tmp_path: Path, biblioteca: Path, *extra: str):
    Image = pytest.importorskip("PIL.Image")
    saida = tmp_path / "folha.png"
    cmd = [str(GODOT), "--path", str(RAIZ), "res://ferramentas/previa_sprites.tscn", "--",
           f"--biblioteca={biblioteca.as_posix()}", f"--saida={saida.as_posix()}", *extra]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT,
                       env=_env(tmp_path))
    assert p.returncode == 0, p.stdout + p.stderr
    assert saida.is_file()
    return saida, Image.open(saida).convert("RGB")


def _no_disco(im, cx: float, cy: float, r: float):
    for y in range(int(cy - r), int(cy + r) + 1):
        for x in range(int(cx - r), int(cx + r) + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                yield im.getpixel((x, y))


def _escuros(im, cx: float, cy: float, r: float) -> int:
    """Pixels do traco do rosto (#14141A): nenhuma cor de corpo da folha e tao escura."""
    return sum(1 for p in _no_disco(im, cx, cy, r) if max(p) < 70)


def test_previa_sobrepoe_olhos_a_pele_da_biblioteca_temporaria(tmp_path):
    """O mesmo destino do manifesto que a API grava e o que o Godot le; a pele
    vermelha (embaixo) e os olhos azuis (por cima) aparecem os DOIS."""
    olho = lambda d: [d.ellipse((523, 380, 603, 460), fill=(0, 0, 255, 255)),  # noqa: E731
                      d.ellipse((523, 564, 603, 644), fill=(0, 0, 255, 255))]
    biblioteca = _biblioteca(tmp_path, {
        ("pele", "comum", "_", "base"): lambda d: d.ellipse((256, 256, 768, 768), fill=(255, 0, 0, 255)),
        ("olhos", "comum", "_", "neutro"): olho,
    })
    saida, _im = _previa(tmp_path, biblioteca)
    p = subprocess.run([str(GODOT), "--headless", "--path", str(RAIZ), "--script",
                        "res://testes/verificar_previa.gd", "--", f"--png={saida.as_posix()}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT,
                       env=_env(tmp_path))
    assert p.returncode == 0, p.stdout + p.stderr


def test_peca_de_olhos_apaga_os_olhos_antigos_e_deixa_a_boca(tmp_path):
    """Com peca de olhos, nenhum pixel dos olhos Kenney antigos fica por baixo
    (a peca azul esta na nuca, longe dos olhos); a boca, sem peca, continua."""
    biblioteca = _biblioteca(tmp_path, {
        ("olhos", "comum", "_", "neutro"): lambda d: d.rectangle((300, 482, 360, 542), fill=(0, 0, 255, 255)),
    })
    _saida, im = _previa(tmp_path, biblioteca)
    for k in range(6):
        cx, cy = _centro(k)
        azul = sum(1 for p in _no_disco(im, cx - 0.70 * RAIO, cy, 0.12 * RAIO) if p[2] > 200 and p[0] < 60)
        assert azul > 50, f"celula {k}: a peca azul nao apareceu ({azul})"
        for lado in (-1, 1):
            n = _escuros(im, cx + 0.20 * RAIO, cy + lado * 0.36 * RAIO, 0.18 * RAIO)
            assert n == 0, f"celula {k}: {n} pixels do olho antigo sob a peca (lado {lado})"
    # neutro: boca_sorriso do rosto antigo continua (a boca nao tem peca)
    cx, cy = _centro(0)
    assert _escuros(im, cx + 0.66 * RAIO, cy, 0.14 * RAIO) > 30


def _caixa_do_corpo(im, k: int):
    """Caixa dos pixels da cor do corpo (D86565 e o tom de sombra dela) na celula k."""
    cx, cy = _centro(k)
    xs, ys = [], []
    for y in range(int(cy - 300), int(cy + 250)):
        for x in range(int(cx - 265), int(cx + 265)):
            r, g, b = im.getpixel((x, y))
            if r > 140 and r - g > 60 and r - b > 60:
                xs.append(x)
                ys.append(y)
    assert xs, "corpo nao encontrado"
    return min(xs), min(ys), max(xs), max(ys)


@pytest.mark.parametrize("com_costas", [False, True], ids=["sem_pecas", "com_acessorio_costas"])
def test_corpo_por_codigo_segue_pulo_e_squash(tmp_path, com_costas):
    """Regressao (rodada 1 dos sprites): sem pele modular o corpo ficava no
    chao e sem squash (perdeu o draw_set_transform(centro, 0, esc)); com
    acessorio de costas ele herdava o quadro daquela peca e encolhia."""
    pecas = {}
    extra = []
    if com_costas:
        pecas[("acessorio_costas", "classe", "teste_classe", "base")] = \
            lambda d: d.ellipse((150, 462, 250, 562), fill=(0, 200, 0, 255))
        extra.append("--classe=teste_classe")
    biblioteca = _biblioteca(tmp_path, pecas)
    z, ex, ey = 0.6, 1.25, 0.8
    _saida, im = _previa(tmp_path, biblioteca, f"--z={z}", f"--esc_x={ex}", f"--esc_y={ey}", *extra)
    x0, y0, x1, y1 = _caixa_do_corpo(im, 0)
    cx, cy = _centro(0)
    meio = ((x0 + x1) / 2, (y0 + y1) / 2)
    assert abs(meio[0] - cx) <= 4 and abs(meio[1] - (cy - z * 100)) <= 4, (meio, (cx, cy - z * 100))
    # o contorno (3,5 px no quadro do squash) cobre a borda do corpo
    meia_l, meia_a = (x1 - x0) / 2, (y1 - y0) / 2
    assert RAIO * ex - 9 <= meia_l <= RAIO * ex + 2, meia_l
    assert RAIO * ey - 9 <= meia_a <= RAIO * ey + 2, meia_a


def _media(im, x: float, y: float, r: int = 3) -> float:
    """Brilho medio (0..255) de um quadradinho em volta de (x, y)."""
    px = [im.getpixel((int(x) + dx, int(y) + dy)) for dx in range(-r, r + 1) for dy in range(-r, r + 1)]
    return sum(sum(p) / 3.0 for p in px) / len(px)


@pytest.mark.parametrize("brilho_proprio", [False, True], ids=["brilho_do_codigo", "brilho_proprio"])
def test_brilho_do_codigo_continua_sobre_a_pele_modular(tmp_path, brilho_proprio):
    """Contrato §2: o brilho segue por codigo por cima da pele modular; so sai
    quando o .json da pele diz "brilho_proprio": true."""
    biblioteca = _biblioteca(tmp_path, {
        ("pele", "classe", "teste_classe", "base"): lambda d: d.ellipse((256, 256, 768, 768), fill=(110, 110, 110, 255)),
    })
    if brilho_proprio:
        (biblioteca / "partes/lutador/pele/classe/teste_classe/v01/base.json").write_text(
            json.dumps({"tingir": "nenhum", "brilho_proprio": True}), encoding="utf-8")
    _saida, im = _previa(tmp_path, biblioteca, "--classe=teste_classe")
    cx, cy = _centro(0)  # neutro: nada do rosto no alto-esquerda nem no espelho dele
    brilho = _media(im, cx - 0.40 * RAIO, cy - 0.44 * RAIO)
    espelho = _media(im, cx - 0.40 * RAIO, cy + 0.44 * RAIO)
    assert abs(espelho - 110) <= 4, espelho  # a pele cinza chegou sem tinta
    if brilho_proprio:
        assert abs(brilho - espelho) <= 4, (brilho, espelho)
    else:
        assert brilho - espelho >= 50, (brilho, espelho)  # 0,55 de branco: ~190


@pytest.mark.parametrize("z", [0.0, 1.0, 3.0])
def test_sombra_modular_encolhe_com_o_pulo_como_a_de_codigo(tmp_path, z):
    """A peca de sombra (verde, a elipse de codigo no gabarito: 512x215 em
    (512, 640)) encolhe pelo fator da sombra de codigo, max(0,4; 1 - z/4 m),
    em volta do mesmo ponto 0,5R abaixo do centro."""
    biblioteca = _biblioteca(tmp_path, {
        ("sombra", "comum", "_", "base"): lambda d: d.ellipse((256, 532, 768, 748), fill=(0, 200, 0, 255)),
    })
    _saida, im = _previa(tmp_path, biblioteca, f"--z={z}")
    cx, cy = _centro(0)
    pe_y = cy + 0.5 * RAIO
    xs = [x for x in range(int(cx - 265), int(cx + 265))
          if (lambda p: p[1] > 150 and p[0] < 60 and p[2] < 60)(im.getpixel((x, int(pe_y))))]
    fator = max(0.4, 1.0 - z / 4.0)
    assert xs, "sombra nao apareceu na linha do pe"
    largura = max(xs) - min(xs) + 1
    assert abs(largura - 2 * RAIO * fator) <= 6, (largura, 2 * RAIO * fator)
    assert abs((max(xs) + min(xs)) / 2 - cx) <= 3
