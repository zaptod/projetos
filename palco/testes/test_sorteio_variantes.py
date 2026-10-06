"""Guarda-roupa de variantes: Python e Godot escolhem a MESMA peca.

A regra mora em dois lugares: `neural_fights.tools.manifesto_sprites`
(`resolver_parte`, o que o app mostra no provador) e
`palco/nucleo/partes_lutador.gd` (`PartesLutador.resolver`, o que vai ao
video). Se os dois discordarem, o Adrian fixa/olha um olho no app e o video
sai com outro. Este teste monta uma biblioteca temporaria com varias
variantes por nivel (comum, classe, personagem), lixo de pasta, carinhas
faltando e escolhas fixadas, e compara caso a caso: nivel, variante, carinha
e arquivo.

Os personagens sao os do banco vivo (`%LOCALAPPDATA%\\neural-fights\\
personagens.json`, so LEITURA), completados com ids sinteticos ate 200
(nomes com acento, `#2`, simbolos e vazio). Sem o banco, so os sinteticos.

O lado Godot roda sem janela (~5 s) e so precisa do executavel.
"""
from __future__ import annotations

import json
import os
import re
import random
import subprocess
import sys
from pathlib import Path

import pytest


RAIZ_PALCO = Path(__file__).resolve().parents[1]
RAIZ_REPO = RAIZ_PALCO.parent
# O neural_fights instalado em modo editavel aponta para E:\projetos, nao para
# a worktree: sem isto o teste compararia o Godot daqui com o Python de la.
sys.path.insert(0, str(RAIZ_REPO))
from neural_fights.tools import manifesto_sprites as m  # noqa: E402

GODOT = Path(os.environ.get("NF_GODOT") or "E:/ferramentas/godot/Godot_v4.7.2-stable_win64_console.exe")
TIMEOUT = 300

PARTES = list(m.NIVEIS)
CLASSES = ["Assassino (Crítico)", "Berserker (Fúria)", "Cavaleiro (Defesa)", "Criomante (Gelo)",
           "Druida (Natureza)", "Duelista (Precisão)", "Feiticeiro (Caos)", "Gladiador (Combate)",
           "Guerreiro (Força Bruta)", "Ladino (Evasão)", "Mago (Arcano)", "Monge (Chi)",
           "Necromante (Trevas)", "Ninja (Velocidade)", "Paladino (Sagrado)", "Piromante (Fogo)"]
EXPRESSOES_DO_TESTE = ["neutro", "furia", "animado", "panico", "dor", "morto",
                       "tonto", "berserk", "extase", "alerta"]
DIFICEIS = ["Kuro #2", "Zoë Ærøn", "  Émile  du Pré ", "ÁGUA VIVA", "Nañá (Ç)", "Fênix 🔥",
            "o_o", "123", "Valkyrie a Sábia"]


def test_o_python_testado_e_o_desta_arvore():
    assert Path(m.__file__).resolve().is_relative_to(RAIZ_REPO.resolve()), m.__file__


def _banco() -> list[dict]:
    caminho = Path(os.environ.get("LOCALAPPDATA", "")) / "neural-fights" / "personagens.json"
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [{"nome": str(p["nome"]), "classe": str(p.get("classe", ""))}
            for p in dados if isinstance(p, dict) and p.get("nome")]


def lutadores(n: int = 200) -> list[dict]:
    sorteio = random.Random(7)
    saida = _banco()[:n - len(DIFICEIS)]
    for nome in DIFICEIS:
        saida.append({"nome": nome, "classe": sorteio.choice(CLASSES)})
    i = 0
    while len(saida) < n:
        saida.append({"nome": f"Sintetico {i:03d}", "classe": sorteio.choice(CLASSES)})
        i += 1
    return saida


def _png(caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"")  # a regra so pergunta se existe; ninguem abre


def _estados(sorteio: random.Random, parte: str) -> list[str]:
    if parte not in m.PARTES_DE_EXPRESSAO:
        return ["base"]
    escolhidos = [e for e in m.EXPRESSOES if sorteio.random() < 0.2]
    if sorteio.random() < 0.75:
        escolhidos.append("neutro")
    return sorted(set(escolhidos)) or ["furia"]


def montar_biblioteca(raiz: Path, gente: list[dict], semente: int = 2026) -> dict:
    """Biblioteca com 0-5 variantes por (parte, nivel, alvo), ids com buraco
    (v01, v03, v10), pasta de lixo, variante vazia e guarda-roupa fixado.
    Devolve um resumo do que foi montado."""
    sorteio = random.Random(semente)
    lutador = raiz / "partes" / "lutador"
    ids = ["v01", "v02", "v03", "v05", "v07", "v10", "v12"]
    resumo = {"colecoes": 0, "variantes": 0, "arquivos": 0}
    alvos = {"comum": ["_"], "classe": [m.slug(c) for c in CLASSES],
             "personagem": [m.slug(p["nome"]) for p in gente[::3] if m.slug(p["nome"])]}
    for parte, niveis in m.NIVEIS.items():
        for nivel in niveis:
            for alvo in alvos[nivel]:
                chance = {"comum": 0.85, "classe": 0.45, "personagem": 0.35}[nivel]
                if sorteio.random() > chance:
                    continue
                variantes = sorted(sorteio.sample(ids, sorteio.randint(1, 5)))
                resumo["colecoes"] += 1
                for variante in variantes:
                    resumo["variantes"] += 1
                    for estado in _estados(sorteio, parte):
                        _png(lutador / parte / nivel / alvo / variante / f"{estado}.png")
                        resumo["arquivos"] += 1
                pasta = lutador / parte / nivel / alvo
                if sorteio.random() < 0.15:  # lixo que nenhum dos dois pode contar
                    _png(pasta / "rascunho" / "neutro.png")
                    (pasta / "v99").mkdir(parents=True, exist_ok=True)
                    if parte in m.PARTES_DE_EXPRESSAO:
                        _png(pasta / "v98" / "base.png")
    guarda: dict[str, dict] = {}
    for p in gente[::5]:
        chave = m.slug(p["nome"])
        for parte in sorteio.sample(PARTES, 3):
            guarda.setdefault(chave, {})[parte] = sorteio.choice(ids + ["v99", "v98", "nada"])
    guarda["Valkyrie a Sábia"] = {"olhos": "v03"}  # chave crua (nao slug): ninguem le
    (raiz / "partes").mkdir(parents=True, exist_ok=True)
    (raiz / "partes" / "guarda_roupa.json").write_text(json.dumps(guarda, ensure_ascii=False), encoding="utf-8")
    resumo["fixados"] = sum(len(v) for v in guarda.values())
    return resumo


def casos(gente: list[dict]) -> list[list[str]]:
    saida = [[p["nome"], p["classe"], parte, expr]
             for p in gente for parte in PARTES for expr in EXPRESSOES_DO_TESTE]
    # sem personagem: a semente e a classe (a previa por estilo do app)
    saida += [["", classe, parte, expr] for classe in CLASSES for parte in PARTES
              for expr in EXPRESSOES_DO_TESTE]
    return saida


def escolhas_python(biblioteca: Path, lista: list[list[str]]) -> list[dict | None]:
    saida = []
    for personagem, classe, parte, expr in lista:
        achado = m.resolver_no_disco(biblioteca, parte, personagem, classe, expr)
        if achado is None:
            saida.append(None)
            continue
        saida.append({"nivel": achado["nivel"], "variante": achado["variante"], "estado": achado["estado"],
                      "arquivo": achado["arquivo"].relative_to(biblioteca).as_posix()})
    return saida


def escolhas_godot(biblioteca: Path, lista: list[list[str]], pasta: Path) -> tuple[list, float]:
    entrada, saida = pasta / "casos.json", pasta / "escolhas_godot.json"
    entrada.write_text(json.dumps({"biblioteca": biblioteca.as_posix(), "casos": lista},
                                  ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ)
    env["APPDATA"] = str(pasta / "appdata_godot")  # user:// fora do C:, so neste processo
    p = subprocess.run([str(GODOT), "--headless", "--path", str(RAIZ_PALCO), "--script",
                        "res://testes/sorteio_variantes.gd", "--",
                        f"--casos={entrada.as_posix()}", f"--saida={saida.as_posix()}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=TIMEOUT, env=env)
    assert p.returncode == 0, p.stdout + p.stderr
    dados = json.loads(saida.read_text(encoding="utf-8"))
    return dados["escolhas"], float(dados["ms"])


def test_slug_do_python_e_o_do_palco():
    """O slug escolhe a pasta do personagem, a chave do guarda-roupa e a
    semente do sorteio: e copia de UtilPalco.slug (palco/nucleo/util.gd)."""
    assert m.slug("Berserker (Fúria)") == "berserker_furia"
    assert m.slug("  Émile  du Pré ") == "emile_du_pre"
    assert m.slug("Kuro #2") == "kuro_2"
    assert m.slug("Zoë Ærøn") == "zoe_r_n"  # æ e ø nao estao na tabela do palco
    assert m.slug("Fênix 🔥") == "fenix"
    assert m.slug("_") == ""
    gd = (RAIZ_PALCO / "nucleo" / "util.gd").read_text(encoding="utf-8")
    de, para = re.search(r'var de := "(.*?)"\s*var para := "(.*?)"', gd).groups()
    assert all(m.slug(a) == b for a, b in zip(de, para)), (de, para)


def test_sorteio_e_fnv1a_explicito_e_espalha():
    """FNV-1a 32 bits sobre o UTF-8 de `semente:parte`, dobrado em 16 bits.
    Medido em 06/10/2026 com 200 lutadores x 9 pecas: sem a dobra, com 2
    variantes, duas pecas do mesmo lutador caem iguais 44% das vezes (o bit
    baixo do FNV e a paridade dos bytes); com a dobra, 50%."""
    assert m.fnv1a32("") == 0x811C9DC5
    assert m.fnv1a32("a") == 0xE40C292C
    assert m.fnv1a32("foobar") == 0xBF9CF968
    gente = [m.slug(p["nome"]) for p in lutadores()]
    for n in (2, 3, 5):
        opcoes = [f"v{i:02d}" for i in range(1, n + 1)]
        contagem = {v: 0 for v in opcoes}
        iguais = pares = 0
        for g in gente:
            escolha = [m._sorteio_variante(g, parte, opcoes) for parte in PARTES]
            for v in escolha:
                contagem[v] += 1
            for i in range(len(escolha)):
                for j in range(i + 1, len(escolha)):
                    pares += 1
                    iguais += escolha[i] == escolha[j]
        esperado = len(gente) * len(PARTES) / n
        assert all(abs(c - esperado) / esperado < 0.2 for c in contagem.values()), (n, contagem)
        assert abs(iguais / pares - 1 / n) < 0.03, (n, iguais / pares)


@pytest.mark.skipif(not GODOT.is_file(), reason="Godot nao encontrado")
def test_python_e_godot_escolhem_igual(tmp_path):
    gente = lutadores()
    biblioteca = tmp_path / "biblioteca"
    resumo = montar_biblioteca(biblioteca, gente)
    lista = casos(gente)
    py = escolhas_python(biblioteca, lista)
    gd, ms = escolhas_godot(biblioteca, lista, tmp_path)
    assert len(gd) == len(py) == len(lista)
    divergencias = [(c, a, b) for c, a, b in zip(lista, py, gd) if a != b]
    achados = sum(1 for a in py if a)
    print(f"\n[paridade] {len(lista)} casos, {achados} com peca, {len(divergencias)} divergencias; "
          f"biblioteca {resumo}; Godot {ms:.0f} ms")
    assert not divergencias, divergencias[:10]
    # o teste so vale se exercitar o que importa
    niveis = {a["nivel"] for a in py if a}
    assert niveis == {"comum", "classe", "personagem"}, niveis
    assert len({a["variante"] for a in py if a}) >= 5
    assert any(a and a["estado"] != c[3] and c[2] in m.PARTES_DE_EXPRESSAO for c, a in zip(lista, py))
    assert any(a is None for a in py)
    # a fixada vence o sorteio sempre que existe no dono da peca
    guarda = json.loads((biblioteca / "partes" / "guarda_roupa.json").read_text(encoding="utf-8"))
    venceu = 0
    for (personagem, classe, parte, _expr), achado in zip(lista, py):
        fixada = guarda.get(m.slug(personagem), {}).get(parte) if personagem else None
        dono = m.dono_da_parte(parte, classe, m.variantes_no_disco(biblioteca), personagem)
        if achado and fixada and dono and fixada in dono[2]:
            assert achado["variante"] == fixada, (personagem, parte, fixada, achado)
            venceu += 1
    print(f"[paridade] fixada venceu o sorteio em {venceu} casos")
    assert venceu >= 50, venceu
