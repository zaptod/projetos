# -*- coding: utf-8 -*-
"""Da folha limpa para a biblioteca do palco, no formato que ele ja le.

O formato NAO e desta pasta: e o da `palco/biblioteca/efeitos/folha_animada.gd`
e da secao "Folha de sprite animada" de `docs/palco/COMO-EDITAR.md` (16E).
A peca aparece no palco sem catalogo, pela descoberta por NOME da
`palco/nucleo/biblioteca.gd`:

    objeto   skills/<skill> > objetos/<tipo>/<elemento> > ...
    evento   eventos/<tipo>_<tier> > eventos/<tipo> > ...

Cada exportacao escreve:

    efeitos/folhas/<nome>.png    a folha: grade de celulas iguais, px inteiros
    efeitos/folhas/<nome>.json   origem, autor, licenca, prova, a receita e
                                 as medidas da limpeza
    efeitos/<destino>.tscn       a cena com o `folha_animada.gd`
    LICENCAS.md                  a linha obrigatoria, num bloco proprio

SpriteFrames (.tres) nao: o palco nao le SpriteFrames -- a cena com o
`folha_animada.gd` e o que ele descobre, e anda pelo relogio do JOGO
(congela no hitstop), coisa que um AnimatedSprite2D nao faz sozinho.

Arte de IA so entra com PROVA de origem (a conta pode ser compartilhada):
sem `prova`, a exportacao recusa.
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from PIL import Image

# Os tipos de OBJETO que a folha serve (a trilha de `neural_fights/recording/
# timeline.py`, CANAIS_OBJETO). O beam e um traco entre dois pontos e ainda
# nao aceita folha (docs/palco/COMO-EDITAR.md): fica de fora de proposito.
OBJETOS = ("projetil", "orbe", "area", "trap", "summon", "portal")
# Os EVENTOS com efeito no palco (`palco.gd`, EVENTOS_COM_VFX).
EVENTOS = ("acerto", "dano", "cura", "bloqueio", "parry", "esquiva",
           "desvio", "dash", "parede", "wall_splat", "ko", "escudo_quebrou",
           "skill", "agarrao_desfecho", "obstaculo")
TIERS = ("", "light", "medium", "heavy", "colossal")
TIPOS = OBJETOS + EVENTOS

ROTULOS_DE_TIPO = {
    "projetil": "projétil", "orbe": "orbe", "area": "área", "trap": "armadilha",
    "summon": "invocação", "portal": "portal", "acerto": "acerto (evento)",
    "dano": "dano (evento)", "cura": "cura (evento)",
    "bloqueio": "bloqueio (evento)", "parry": "parry (evento)",
    "esquiva": "esquiva (evento)", "desvio": "desvio (evento)",
    "dash": "dash (evento)", "parede": "parede (evento)",
    "wall_splat": "wall splat (evento)", "ko": "KO (evento)",
    "escudo_quebrou": "escudo quebrou (evento)", "skill": "skill (evento)",
    "agarrao_desfecho": "agarrão (evento)", "obstaculo": "obstáculo (evento)",
}

INICIO_LICENCAS = "<!-- oficina:inicio (gerado pela Oficina de sprites) -->"
FIM_LICENCAS = "<!-- oficina:fim -->"
SCRIPT = "res://biblioteca/efeitos/folha_animada.gd"


def elementos() -> list:
    """Os 12 elementos do jogo (`ELEMENT_PALETTES`), sem o DEFAULT."""
    try:
        from neural_fights.utils.palette import ELEMENT_PALETTES
        nomes = [n for n in ELEMENT_PALETTES if n != "DEFAULT"]
    except Exception:                                        # noqa: BLE001
        nomes = ["FOGO", "GELO", "RAIO", "TREVAS", "LUZ", "NATUREZA",
                 "ARCANO", "CAOS", "SANGUE", "VOID", "TEMPO", "GRAVITACAO"]
    return nomes


def slug(texto: str) -> str:
    """O mesmo de `UtilPalco.slug` (palco/nucleo/util.gd): minusculas, sem
    acento, e `_` no lugar de qualquer outra coisa."""
    sem_acento = unicodedata.normalize("NFKD", str(texto or "").strip().lower())
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    saida = ""
    for c in sem_acento:
        if ("a" <= c <= "z") or ("0" <= c <= "9"):
            saida += c
        elif saida and not saida.endswith("_"):
            saida += "_"
    return saida.rstrip("_")


def biblioteca_padrao() -> Path:
    from painel.janelas import RAIZ
    return RAIZ / "palco" / "biblioteca"


@dataclass
class Identidade:
    nome: str = ""
    tipo: str = "projetil"
    elemento: str = ""
    skill: str = ""
    tier: str = ""
    fps: float = 24.0
    laco: bool = True
    girar: bool = True
    aditivo: bool = False
    tingir: str = ""
    escala_raio: float = 0.0
    tamanho_m: float = 1.0
    duracao_s: float = 0.0
    ancora: list | None = None       # None = a do alinhamento
    origem: str = "ChatGPT (imagem)"
    autor: str = "Adrian"
    licenca: str = "arte gerada por IA para o projeto"
    prova: str = ""
    fonte: str = ""                  # o arquivo de origem
    notas: list = field(default_factory=list)

    @classmethod
    def de_dict(cls, dados: dict) -> "Identidade":
        conhecidos = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in (dados or {}).items() if k in conhecidos})


def destino_da_cena(ident: Identidade) -> str:
    """O caminho da cena dentro de `efeitos/`, sem extensao. '' = sem lugar."""
    if ident.skill.strip():
        return f"skills/{slug(ident.skill)}"
    if ident.tipo in EVENTOS:
        tier = ident.tier if ident.tier in TIERS else ""
        return f"eventos/{ident.tipo}" + (f"_{tier}" if tier else "")
    if ident.tipo in OBJETOS and slug(ident.elemento):
        return f"objetos/{ident.tipo}/{slug(ident.elemento)}"
    return ""


def problemas(ident: Identidade, quadros: int, celula=(0, 0)) -> list:
    """O que impede de exportar (vazio = pode)."""
    erros = []
    if not slug(ident.nome):
        erros.append("falta o NOME da peça (vira o nome do arquivo)")
    if ident.tipo == "beam":
        erros.append("o beam ainda não aceita folha no palco (é um traço "
                     "entre dois pontos): use o objeto_cc0")
    elif ident.tipo not in TIPOS:
        erros.append(f"tipo desconhecido: {ident.tipo}")
    elif not destino_da_cena(ident):
        erros.append("objeto sem ELEMENTO nem SKILL: o palco não saberia "
                     "quando usar (escolha um dos 12 elementos ou dê o nome "
                     "da skill)")
    if not quadros:
        erros.append("nenhum quadro achado")
    if not str(ident.prova).strip():
        erros.append("falta a PROVA de origem (a conversa ou o histórico com "
                     "o nosso prompt): arte de IA só entra com ela")
    if not (1.0 <= float(ident.fps) <= 60.0):
        erros.append("fps fora de 1 a 60")
    return erros


def avisos(ident: Identidade, celula=(0, 0)) -> list:
    saida = []
    if celula and celula[0] > 512:
        saida.append(f"quadro de {celula[0]} px de largura: acima de ~512 só "
                     "pesa (a bolinha de 408 px é o maior uso)")
    if ident.tipo in OBJETOS and not ident.skill and ident.elemento:
        saida.append(f"vale para TODO {ident.tipo} de "
                     f"{ident.elemento.lower()} sem cena própria")
    return saida


def _nome_do_no(texto: str) -> str:
    return "".join(p.capitalize() for p in slug(texto).split("_")) or "Folha"


def _num(valor: float) -> str:
    valor = float(valor)
    return f"{valor:.1f}" if valor == int(valor) else f"{valor:g}"


def texto_da_cena(ident: Identidade, arquivo_da_folha: str, colunas: int,
                  linhas: int, quadros: int, ancora) -> str:
    """A cena `.tscn`, como o exemplo de docs/palco/COMO-EDITAR.md."""
    res = f"res://biblioteca/efeitos/folhas/{arquivo_da_folha}"
    linhas_txt = [
        "[gd_scene load_steps=3 format=3]",
        "",
        f'[ext_resource type="Script" path="{SCRIPT}" id="1_folha"]',
        f'[ext_resource type="Texture2D" path="{res}" id="2_folha"]',
        "",
        f'[node name="{_nome_do_no(ident.nome)}" type="Node2D"]',
        'script = ExtResource("1_folha")',
        'folha = ExtResource("2_folha")',
        f"colunas = {int(colunas)}",
        f"linhas = {int(linhas)}",
        f"quadros = {int(quadros)}",
        f"fps = {_num(ident.fps)}",
        f"laco = {'true' if ident.laco else 'false'}",
        f"ancora = Vector2({int(round(ancora[0]))}, {int(round(ancora[1]))})",
        f"girar = {'true' if ident.girar else 'false'}",
    ]
    if float(ident.escala_raio) > 0:
        linhas_txt.append(f"escala_raio = {_num(ident.escala_raio)}")
    else:
        linhas_txt.append(f"tamanho_m = {_num(ident.tamanho_m)}")
    if ident.aditivo:
        linhas_txt.append("aditivo = true")
    if ident.tingir:
        linhas_txt.append(f'tingir = "{ident.tingir}"')
    if float(ident.duracao_s) > 0:
        linhas_txt.append(f"duracao_s = {_num(ident.duracao_s)}")
    return "\n".join(linhas_txt) + "\n"


def _linha_de_licenca(caminho_rel: str, ident: Identidade) -> str:
    def limpo(t):
        return str(t or "").replace("|", "/").replace("\n", " ").strip()
    origem = limpo(ident.origem)
    if ident.fonte:
        origem += f", `{limpo(Path(ident.fonte).name)}` limpo pela Oficina"
    return (f"| `{caminho_rel}` | {origem} | {limpo(ident.autor)} | "
            f"{limpo(ident.licenca)} | {limpo(ident.prova)} |")


def anotar_licenca(licencas: Path, caminho_rel: str, ident: Identidade) -> None:
    """Uma linha por folha, num bloco PROPRIO (o `efeitos_cc0` tem o dele e
    o regera inteiro). Exportar de novo troca a linha, nao duplica."""
    texto = licencas.read_text(encoding="utf-8") if licencas.exists() else \
        "# Licenças da biblioteca do palco\n"
    linha = _linha_de_licenca(caminho_rel, ident)
    if INICIO_LICENCAS not in texto:
        texto = texto.rstrip("\n") + (
            f"\n\n{INICIO_LICENCAS}\n\nFolhas de sprite limpas pela Oficina "
            "de sprites (painel):\n\n| arquivo no palco | origem | autor | "
            f"licença | prova |\n|---|---|---|---|---|\n{FIM_LICENCAS}\n")
    antes, resto = texto.split(INICIO_LICENCAS, 1)
    meio, depois = resto.split(FIM_LICENCAS, 1)
    marca = f"| `{caminho_rel}` |"
    linhas = [ln for ln in meio.split("\n") if not ln.startswith(marca)]
    while linhas and not linhas[-1].strip():
        linhas.pop()
    linhas.append(linha)
    meio = "\n".join(linhas) + "\n"
    licencas.write_text(antes + INICIO_LICENCAS + meio + FIM_LICENCAS + depois,
                        encoding="utf-8")


def caminhos(ident: Identidade, biblioteca: Path) -> dict:
    nome = slug(ident.nome)
    efeitos = Path(biblioteca) / "efeitos"
    destino = destino_da_cena(ident)
    return {"folha": efeitos / "folhas" / f"{nome}.png",
            "metadados": efeitos / "folhas" / f"{nome}.json",
            "cena": (efeitos / f"{destino}.tscn") if destino else None,
            "licencas": Path(biblioteca) / "LICENCAS.md"}


def ja_existem(ident: Identidade, biblioteca: Path) -> list:
    return [str(p) for chave, p in caminhos(ident, biblioteca).items()
            if chave != "licencas" and p is not None and p.exists()]


def exportar(res, ident: Identidade, receita=None, medidas: dict | None = None,
             biblioteca: Path | None = None, substituir: bool = False) -> dict:
    """Escreve tudo. Levanta ValueError com a lista de problemas, e
    FileExistsError se algo ja existe e `substituir` e falso."""
    biblioteca = Path(biblioteca or biblioteca_padrao())
    n = len(res.alinhado.quadros)
    erros = problemas(ident, n, res.alinhado.celula)
    if erros:
        raise ValueError("; ".join(erros))
    existentes = ja_existem(ident, biblioteca)
    if existentes and not substituir:
        raise FileExistsError(", ".join(existentes))

    alvo = caminhos(ident, biblioteca)
    ancora = list(ident.ancora) if ident.ancora else list(res.alinhado.ancora)
    alvo["folha"].parent.mkdir(parents=True, exist_ok=True)
    alvo["cena"].parent.mkdir(parents=True, exist_ok=True)

    temporario = alvo["folha"].with_suffix(".tmp.png")
    Image.fromarray(res.folha, "RGBA").save(temporario, "PNG", optimize=True)
    temporario.replace(alvo["folha"])

    meta = {
        "nome": slug(ident.nome), "tipo": ident.tipo,
        "elemento": ident.elemento, "skill": ident.skill, "tier": ident.tier,
        "origem": ident.origem, "autor": ident.autor,
        "licenca": ident.licenca, "prova": ident.prova,
        "fonte": Path(ident.fonte).name if ident.fonte else "",
        "data": datetime.now().isoformat(timespec="seconds"),
        "cena": str(alvo["cena"].relative_to(biblioteca)).replace("\\", "/"),
        "grade": {"colunas": res.colunas, "linhas": res.linhas,
                  "quadros": n, "celula": list(res.alinhado.celula)},
        "ancora": ancora, "fps": ident.fps, "laco": ident.laco,
        "limpeza": receita.para_dict() if receita is not None else None,
        "medidas": medidas,
        "notas": list(ident.notas),
    }
    alvo["metadados"].write_text(json.dumps(meta, ensure_ascii=False,
                                            indent=2), encoding="utf-8")
    alvo["cena"].write_text(
        texto_da_cena(ident, alvo["folha"].name, res.colunas, res.linhas, n,
                      ancora), encoding="utf-8")
    rel = str(alvo["folha"].relative_to(biblioteca)).replace("\\", "/")
    anotar_licenca(alvo["licencas"], rel, ident)
    return {k: str(v) for k, v in alvo.items() if v is not None}


__all__ = ["EVENTOS", "Identidade", "OBJETOS", "ROTULOS_DE_TIPO", "TIERS",
           "TIPOS", "anotar_licenca", "avisos", "biblioteca_padrao",
           "caminhos", "destino_da_cena", "elementos", "exportar",
           "ja_existem", "problemas", "slug", "texto_da_cena"]
