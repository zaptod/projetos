"""PROTOTIPO (scratchpad, nao e codigo de producao): monta o manifesto de slots
a partir da engine e conta. Serve para provar que cada lista sai do codigo.

Uso: python gerar_manifesto.py <saida_exemplo.json>
"""
from __future__ import annotations

import collections
import json
import sys
import unicodedata

sys.path.insert(0, r"E:\projetos")

from neural_fights.core.skills import SKILL_DB  # noqa: E402
from neural_fights.core.status_runtime import STATUS_VISUAL  # noqa: E402
from neural_fights.core.arena import ARENAS  # noqa: E402
from neural_fights.core.agarrao import DESFECHOS  # noqa: E402
from neural_fights.models import constants as C  # noqa: E402
from neural_fights.utils.palette import ELEMENT_PALETTES  # noqa: E402
from neural_fights.effects.character_flair import EXPRESSOES as EXPR_DICT  # noqa: E402
from neural_fights.recording import timeline as T  # noqa: E402
from neural_fights.tools.gerador_database import ESTILOS_ARMA  # noqa: E402


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    out, prev = [], ""
    for ch in t.strip():
        if ch.isalnum():
            out.append(ch)
            prev = ch
        elif out and prev != "_":
            out.append("_")
            prev = "_"
    return "".join(out).strip("_")


def sem_parenteses(t: str) -> str:
    return t.split("(")[0].strip()


# ------------------------------------------------------------------ eixos
EXPRESSOES = list(T.EXPRESSOES)
assert EXPRESSOES == list(EXPR_DICT.keys()), "timeline e character_flair divergem"
# proposta: 6 representantes; os outros caem no representante da familia
FAMILIA = {
    "neutro": "neutro", "focado": "neutro", "glacial": "neutro", "concentrado": "neutro",
    "firmeza": "neutro", "tedio": "neutro",
    "furia": "furia", "determinado": "furia", "berserk": "furia", "esforco": "furia", "limite": "furia",
    "animado": "animado", "confiante": "animado", "euforico": "animado", "extase": "animado",
    "panico": "panico", "nervoso": "panico", "desespero": "panico", "alerta": "panico", "confuso": "panico",
    "dor": "dor", "tonto": "dor", "tristeza": "dor",
    "morto": "morto",
}
assert set(FAMILIA) == set(EXPRESSOES), set(EXPRESSOES) ^ set(FAMILIA)
EXTRAS_ROSTO = ["panico", "nervoso", "desespero", "limite", "tristeza", "furia", "berserk",
                "alerta", "extase"]

FLAGS = list(T.FLAGS)
# como cada flag aparece: camada (sprite sobreposto) ou godot (so tinta/alfa/pose)
TRATAMENTO_FLAG = {
    "atacando": "godot", "morto": "godot", "atordoado": "camada", "congelado": "camada",
    "invencivel": "godot", "canalizando": "godot", "adrenalina": "camada", "agarrado": "camada",
    "dash": "godot", "intangivel": "godot", "super_armor": "camada", "bloqueando": "camada",
    "tempo_parado": "camada", "dormindo": "camada", "transformado": "godot", "lancado": "godot",
    "oculto": "godot", "no_ar": "godot",
}
assert set(TRATAMENTO_FLAG) == set(FLAGS), set(FLAGS) ^ set(TRATAMENTO_FLAG)

CLASSES = list(C.LISTA_CLASSES)
ELEMENTOS = [e for e in ELEMENT_PALETTES if e != "DEFAULT"]
SKILLS = {n: v for n, v in SKILL_DB.items() if v.get("tipo") != "NADA"}

# O manifesto nao le o banco de personagens: a contagem mudava a cada
# personagem novo e quebrava a comparacao com o manifesto commitado.

# ------------------------------------------------------------------ moldes
# grupo, parte, niveis permitidos, eixo de estado, z, quadro, ancora, px, tingir, papel
LUTADOR = [
    ("sombra", ["comum"], None, 0, "mundo", "centro", (512, 256), "nenhum", "recomendado"),
    ("acessorio_costas", ["classe", "personagem"], None, 10, "olhar", "centro", (512, 512), "nenhum", "opcional"),
    ("pele", ["comum", "classe", "personagem"], None, 20, "tela", "centro", (512, 512), "cor_personagem", "obrigatorio"),
    ("marcas", ["classe", "personagem"], None, 25, "olhar", "centro", (512, 512), "nenhum", "opcional"),
    ("olhos", ["comum", "classe", "personagem"], "expressao", 40, "olhar", "centro_do_rosto", (512, 256), "nenhum", "obrigatorio"),
    ("sobrancelhas", ["comum", "classe", "personagem"], "expressao", 45, "olhar", "centro_do_rosto", (512, 256), "nenhum", "opcional"),
    ("boca", ["comum", "classe", "personagem"], "expressao", 50, "olhar", "centro_da_boca", (256, 128), "nenhum", "obrigatorio"),
    ("detalhe_rosto", ["comum"], "expressao_extra", 55, "olhar", "centro_do_rosto", (512, 512), "nenhum", "opcional"),
    ("acessorio_cabeca", ["classe", "personagem"], None, 60, "olhar", "centro", (512, 512), "nenhum", "opcional"),
]

slots: list[dict] = []
contagem = collections.Counter()


def add(grupo, parte, nivel, alvo, estado, z, quadro, ancora, px, tingir, papel, destino_hoje,
        fonte, extra=None):
    alvo_s = "_" if nivel == "comum" else slug(alvo)
    est = estado or "base"
    sid = f"{grupo}/{parte}/{nivel}/{alvo_s}/{est}"
    s = {"id": sid, "grupo": grupo, "parte": parte,
         "alvo": {"nivel": nivel, "chave": alvo_s, "rotulo": alvo or "comum"},
         "estado": est, "camada_z": z, "quadro": quadro, "ancora": ancora,
         "tamanho_px": list(px), "tingir": tingir, "papel": papel,
         # Lutadores sao colecoes: v01 e a primeira variante, inclusive para
         # artes antigas. Os outros grupos ainda sao arquivos singulares.
         "destino": (f"palco/biblioteca/partes/{grupo}/{parte}/{nivel}/{alvo_s}/v01/{est}.png"
                     if grupo == "lutador" else f"palco/biblioteca/partes/{grupo}/{parte}/{nivel}/{alvo_s}/{est}.png"),
         "godot_le_hoje": destino_hoje, "fonte": fonte}
    if extra:
        s.update(extra)
    slots.append(s)
    contagem[grupo] += 1
    contagem[(grupo, nivel)] += 1
    return s


def cadeia_lutador(parte, niveis, nivel, alvo, estado, eixo):
    """Fallback: dono = nivel mais especifico com arte; dentro dele estado -> familia -> base."""
    ordem = [n for n in ("personagem", "classe", "comum") if n in niveis]
    ordem = ordem[ordem.index(nivel):]
    estados = [estado]
    if eixo == "expressao" and estado:
        if FAMILIA[estado] != estado:
            estados.append(FAMILIA[estado])
        if "neutro" not in estados:
            estados.append("neutro")
    cad = []
    for n in ordem:
        for e in estados:
            cad.append(f"lutador/{parte}/{n}/{'<alvo>' if n != 'comum' else '_'}/{e or 'base'}")
    return cad


for parte, niveis, eixo, z, quadro, ancora, px, tingir, papel in LUTADOR:
    estados = [None]
    if eixo == "expressao":
        estados = EXPRESSOES
    elif eixo == "expressao_extra":
        estados = EXTRAS_ROSTO
    for nivel in niveis:
        alvos = [None] if nivel == "comum" else (CLASSES if nivel == "classe" else [])
        for alvo in alvos:
            for e in estados:
                pap = papel
                if eixo == "expressao":
                    pap = ("obrigatorio" if (e == "neutro" and papel == "obrigatorio" and nivel == "comum")
                           else "recomendado" if (FAMILIA[e] == e and nivel == "comum" and papel == "obrigatorio")
                           else "opcional")
                elif nivel != "comum":
                    pap = "opcional" if papel != "obrigatorio" or nivel != "comum" else pap
                    if parte in ("acessorio_cabeca", "acessorio_costas") and nivel == "classe":
                        pap = "recomendado"
                add("lutador", parte, nivel, alvo, e, z, quadro, ancora, px, tingir, pap,
                    False, "palco/biblioteca/lutadores/lutador_padrao.gd + rosto.gd",
                    {"eixo_estado": eixo, "fallback": cadeia_lutador(parte, niveis, nivel, alvo, e, eixo)[1:]})

# camadas de estado sobre o lutador (o palco JA procura lutadores/<cat>/<nome>.tscn)
for f in FLAGS:
    if TRATAMENTO_FLAG[f] == "camada":
        add("camada_estado", "estado", "comum", None, f, 70, "mundo", "centro", (512, 512), "nenhum",
            "opcional", True, "neural_fights/recording/timeline.py:98 FLAGS",
            {"destino_tscn": f"palco/biblioteca/lutadores/estados/{f}.tscn"})
add("camada_estado", "estado", "comum", None, "escudo_bolha", 70, "mundo", "centro", (512, 512), "nenhum",
    "opcional", True, "lutador_padrao.gd:69", {"destino_tscn": "palco/biblioteca/lutadores/estados/escudo_bolha.tscn"})
for st in STATUS_VISUAL:
    add("camada_estado", "status", "comum", None, slug(st), 72, "mundo", "centro", (512, 512), "nenhum",
        "opcional", True, "neural_fights/core/status_runtime.py:117 STATUS_VISUAL",
        {"destino_tscn": f"palco/biblioteca/lutadores/status/{slug(st)}.tscn"})
for nome, v in SKILLS.items():
    cat = {"BUFF": "buffs", "CHANNEL": "canais", "TRANSFORM": "transformacoes"}.get(v["tipo"])
    if cat:
        add("camada_estado", cat, "skill", nome, None, 74, "mundo", "centro", (512, 512), "nenhum",
            "opcional", True, "neural_fights/core/skills.py SKILL_DB",
            {"destino_tscn": f"palco/biblioteca/lutadores/{cat}/{slug(nome)}.tscn"})

# armas
for tipo in C.TIPOS_ARMA:
    add("arma", "arma", "tipo", tipo, None, 30, "arma", "empunhadura", (1024, 256), "nenhum",
        "recomendado", True, "neural_fights/models/constants.py:111 TIPOS_ARMA",
        {"destino_tscn": f"palco/biblioteca/armas/tipos/{slug(tipo)}.tscn"})
n_estilos = 0
for tipo, bloco in ESTILOS_ARMA.items():
    for var in bloco["variantes"]:
        nome = var.get("nome") if isinstance(var, dict) else var
        n_estilos += 1
        add("arma", "arma", "estilo", nome, None, 30, "arma", "empunhadura", (1024, 256), "nenhum",
            "opcional", True, "neural_fights/tools/gerador_database.py:79 ESTILOS_ARMA",
            {"tipo_arma": tipo, "destino_tscn": f"palco/biblioteca/armas/estilos/{slug(nome)}.tscn"})
for parte in ("corrente_cabo", "corrente_elos", "corrente_couro", "corrente_corda"):
    add("arma", parte, "tipo", "Corrente", None, 29, "arma", "empunhadura", (256, 128), "nenhum",
        "opcional", False, "neural_fights/recording/timeline.py:245 CABECA/MATERIAL")
for cab in sorted(set(T.CABECA_POR_ESTILO.values())):
    add("arma", "corrente_cabeca", "estilo", cab, None, 31, "arma", "centro", (256, 256), "nenhum",
        "opcional", False, "neural_fights/recording/timeline.py:245 CABECA_POR_ESTILO")
for forma in ("faca", "flecha", "shuriken", "chakram"):
    add("arma", "projetil_arma", "forma", forma, None, 35, "objeto", "centro", (512, 128), "nenhum",
        "opcional", False, "docs/palco/timeline.md:203 projetil_arma.forma")
for rar, d in C.RARIDADES.items():
    if d.get("efeito_visual"):
        add("arma", "brilho_raridade", "raridade", d["efeito_visual"], None, 32, "arma", "empunhadura",
            (1024, 256), "branco_tingido", "opcional", False, "neural_fights/models/constants.py:10 RARIDADES")
for enc in C.ENCANTAMENTOS:
    add("arma", "encantamento", "encantamento", enc, None, 33, "arma", "empunhadura", (1024, 256),
        "branco_tingido", "opcional", False, "neural_fights/models/constants.py:237 ENCANTAMENTOS")
for arq in ("corte", "estocada", "esmagamento", "chicote", "puxada"):
    add("arma", "rastro", "arquetipo", arq, None, 28, "arma", "empunhadura", (1024, 128), "cor_arma",
        "opcional", False, "neural_fights/effects/weapon_animations.py:744 ARQUETIPO_POR_ESTILO")

# skills: parte por tipo
PARTES_SKILL = {
    "PROJETIL": [("projetil", "objetos/projetil")],
    "AREA": [("area_chao", "objetos/area"), ("area_borda", "objetos/area")],
    "BEAM": [("feixe_corpo", "objetos/beam"), ("feixe_ponta", "objetos/beam")],
    "SUMMON": [("invocacao", "objetos/summon")],
    "TRAP": [("estrutura", "objetos/trap")],
    "DASH": [("portal", "objetos/portal")],
    "BUFF": [], "CHANNEL": [], "TRANSFORM": [],
}
for tipo, partes in PARTES_SKILL.items():
    for parte, pasta in partes:
        add("skill", parte, "comum", None, None, 35, "objeto", "centro", (512, 512), "elemento",
            "recomendado", True, "palco/nucleo/biblioteca.gd:101 objeto()")
        for el in ELEMENTOS:
            add("skill", parte, "elemento", el, None, 35, "objeto", "centro", (512, 512), "nenhum",
                "opcional", tipo in ("PROJETIL", "AREA", "BEAM"), "neural_fights/utils/palette.py:23 ELEMENT_PALETTES",
                {"tipo_skill": tipo})
for nome, v in SKILLS.items():
    for parte, pasta in PARTES_SKILL[v["tipo"]]:
        if v["tipo"] == "DASH" and not v.get("cria_portal"):
            continue  # so o Portal Arcano cria objeto portal (entities.py:1370)
        add("skill", parte, "skill", nome, None, 35, "objeto", "centro", (512, 512), "nenhum",
            "opcional", parte not in ("feixe_corpo", "feixe_ponta", "area_borda"),
            "neural_fights/core/skills.py:24 SKILL_DB",
            {"tipo_skill": v["tipo"], "elemento": v.get("elemento")})
# orbe da arma Magica (timeline.py:1216; estados_orbe)
for est in T.ESTADOS_ORBE:
    add("arma", "orbe", "tipo", "Mágica", est, 35, "objeto", "centro", (256, 256), "nenhum",
        "opcional", True, "neural_fights/recording/timeline.py:128 ESTADOS_ORBE",
        {"fallback": [] if est == "orbitando" else ["arma/orbe/tipo/magica/orbitando"]})
# conjuracao por elemento (evento skill) e impacto por elemento (evento explosao)
for ev in ("conjuracao", "impacto"):
    add("efeito", ev, "comum", None, None, 80, "evento", "centro", (512, 512), "elemento", "recomendado",
        True, "palco/nucleo/palco.gd:599 bib.evento")
    for el in ELEMENTOS:
        add("efeito", ev, "elemento", el, None, 80, "evento", "centro", (512, 512), "nenhum", "opcional",
            True, "palco/nucleo/biblioteca.gd:110 candidatos_evento")

# eventos com VFX (+ variantes reais)
EVENTOS = [e for e in ("acerto", "dano", "cura", "bloqueio", "parry", "esquiva", "desvio", "dash",
                       "parede", "wall_splat", "ko", "escudo_quebrou", "agarrao_desfecho", "obstaculo",
                       "choque", "movimento", "projetil_fim")]
for ev in EVENTOS:
    add("efeito", "evento", "tipo", ev, None, 80, "evento", "centro", (512, 512), "nenhum",
        "recomendado" if ev in ("acerto", "ko", "desvio", "dash") else "opcional", True,
        "palco/nucleo/timeline.gd:19 EVENTOS_COM_VFX")
VARIANTES = {
    "acerto": list(T.TIERS) + ["critico", "projetil_arma", "corte", "estocada", "esmagamento", "chicote", "puxada"],
    "agarrao_desfecho": list(DESFECHOS),
    "movimento": list(T.GATILHOS_MOVIMENTO),
    "projetil_fim": list(T.MOTIVOS_FIM),
}
for ev, vs in VARIANTES.items():
    for v in vs:
        add("efeito", "evento", "variante", f"{ev}_{v}", None, 80, "evento", "centro", (512, 512), "nenhum",
            "opcional", True, "palco/nucleo/palco.gd:585-598 variante")

# arena
for chave, cfg in ARENAS.items():
    add("arena", "chao", "arena", cfg.nome, None, -100, "mundo", "canto", (1024, 1024), "nenhum",
        "opcional", False, "neural_fights/core/arena.py:53 ARENAS")
    add("arena", "parede", "arena", cfg.nome, None, -90, "mundo", "canto", (1024, 256), "nenhum",
        "opcional", False, "neural_fights/core/arena.py:53 ARENAS")
tipos_obst = sorted({o.tipo for cfg in ARENAS.values() for o in cfg.obstaculos})
for t in tipos_obst:
    add("arena", "obstaculo", "tipo", t, None, -50, "mundo", "centro", (512, 512), "nenhum", "opcional",
        False, "neural_fights/core/arena.py Obstaculo")
    add("arena", "obstaculo_quebrado", "tipo", t, None, -50, "mundo", "centro", (512, 512), "nenhum",
        "opcional", False, "evento obstaculo (timeline.md:239)")
climas = sorted({e for cfg in ARENAS.values() for e in cfg.efeitos_especiais})
for c in climas:
    add("arena", "clima", "clima", c, None, 90, "tela", "centro", (256, 256), "nenhum", "opcional", False,
        "neural_fights/core/arena.py efeitos_especiais")

# hud
for parte in ("placa_nome", "moldura_vida", "barra_vida", "selo_plano"):
    add("hud", parte, "comum", None, None, 200, "tela", "canto", (1024, 128), "cor_lado", "opcional",
        False, "palco/biblioteca/hud/hud_padrao.gd")

# ------------------------------------------------------------------ saida
por_grupo = {g: n for g, n in contagem.items() if isinstance(g, str)}
por_nivel = {f"{g}/{n}": v for (g, n), v in ((k, c) for k, c in contagem.items() if isinstance(k, tuple))}
moldes_lutador = sum(len(EXPRESSOES) if e == "expressao" else len(EXTRAS_ROSTO) if e == "expressao_extra" else 1
                     for _p, _n, e, *_ in LUTADOR)
minimo = [s["id"] for s in slots if s["papel"] == "obrigatorio"]
recomendado = [s["id"] for s in slots if s["papel"] == "recomendado" and s["grupo"] == "lutador"]
por_classe = collections.Counter(s["parte"] for s in slots
                                 if s["grupo"] == "lutador" and s["alvo"]["chave"] == "berserker_furia")
resumo = {
    "total_slots": len(slots), "por_grupo": por_grupo, "por_grupo_nivel": por_nivel,
    "lutador_moldes_por_alvo": moldes_lutador,
    "lutador_slots_por_classe": sum(por_classe.values()),
    "lutador_slots_por_personagem_se_aberto": sum(por_classe.values()),
    "minimo_obrigatorio": minimo, "lutador_recomendado_comum": recomendado,
    "contagens_engine": {
        "classes": len(CLASSES), "elementos": len(ELEMENTOS), "expressoes": len(EXPRESSOES),
        "flags": len(FLAGS), "skills": len(SKILLS),
        "skills_por_tipo": dict(collections.Counter(v["tipo"] for v in SKILLS.values())),
        "tipos_arma": len(C.TIPOS_ARMA), "estilos_arma": n_estilos, "status": len(STATUS_VISUAL),
        "arenas": len(ARENAS), "tipos_obstaculo": len(tipos_obst), "climas": len(climas),
        "eventos_com_vfx": len(EVENTOS),
    },
}
print(json.dumps({k: v for k, v in resumo.items() if k not in ("minimo_obrigatorio",)}, ensure_ascii=False, indent=1))
print("minimo:", minimo)
ids=[x["id"] for x in slots]; print("ids unicos:", len(ids)==len(set(ids)), len(ids)-len(set(ids)))

if len(sys.argv) > 1:
    def pega(pred, n):
        return [s for s in slots if pred(s)][:n]
    amostra = (
        pega(lambda s: s["grupo"] == "lutador" and s["alvo"]["nivel"] == "comum" and s["estado"] in ("base", "neutro", "furia", "berserk"), 12)
        + pega(lambda s: s["grupo"] == "lutador" and s["alvo"]["chave"] == "berserker_furia" and s["estado"] in ("base", "neutro", "berserk"), 10)
        + pega(lambda s: s["grupo"] == "camada_estado" and s["estado"] in ("atordoado", "queimando"), 2)
        + pega(lambda s: s["grupo"] == "camada_estado" and s["parte"] == "transformacoes", 1)
        + pega(lambda s: s["grupo"] == "arma" and s["alvo"]["chave"] in ("reta", "katana", "kusarigama", "bola_espinhos"), 4)
        + pega(lambda s: s["grupo"] == "skill" and s["alvo"]["chave"] in ("_", "fogo", "bola_de_fogo") and s["parte"] == "projetil", 3)
        + pega(lambda s: s["grupo"] == "skill" and s["alvo"]["chave"] == "nevasca", 2)
        + pega(lambda s: s["grupo"] == "efeito" and s["alvo"]["chave"] in ("acerto", "acerto_heavy", "fogo"), 3)
        + pega(lambda s: s["grupo"] == "arena" and s["alvo"]["chave"] in ("salao_da_torre", "pilar"), 3)
        + pega(lambda s: s["grupo"] == "hud", 1)
    )
    json.dump({"resumo": resumo, "amostra": amostra}, open(sys.argv[1], "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
