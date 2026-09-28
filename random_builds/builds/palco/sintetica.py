"""Uma timeline v1 de MENTIRA, pequena e deterministica, no schema da 16C
(docs/palco/timeline.md): dois lutadores circulando, um golpe com as cinco
fases, acertos, dash, parede, projetil, area, beam, um status e sons no
formato da 16A. Serve aos testes (render de 2 s, validacao) e ao exemplo que
o editor toca com F5 (palco/exemplos/exemplo.timeline.json).

Nada aqui passa pelo motor de luta: e so geometria. Para a luta de verdade,
`fonte.timeline_da_luta`.
"""
from __future__ import annotations

import math

CANAIS_LUTADOR = (
    "x", "y", "z", "ang", "vx", "vy", "hp", "mp", "est", "expr", "acao", "plano", "plano_p", "tell",
    "flags", "golpe_fase", "golpe_p", "golpe_d", "golpe_id", "golpe_janela", "anim_fase", "anim_p",
    "arma_ang", "arma_lunge", "arma_gx", "arma_gy", "arma_px", "arma_py", "arma_puxada", "hb_on",
    "hb_ang", "hb_larg", "escudo", "combo", "flash", "flash_cor", "esc_x", "esc_y",
)
EXPRESSOES = ("neutro", "focado", "glacial", "determinado", "furia", "berserk", "confiante", "animado",
              "euforico", "extase", "panico", "nervoso", "desespero", "tedio", "tristeza", "morto", "tonto",
              "dor", "esforco", "firmeza", "alerta", "confuso", "limite", "concentrado")
FASES = ("", "anticipation", "attack", "impact", "follow", "recovery")
DURACOES = (0.12, 0.17, 0.06, 0.12, 0.17)   # WEAPON_PROFILES["Reta"]-like
FLAGS = ("atacando", "morto", "atordoado", "congelado", "invencivel", "canalizando", "adrenalina",
         "agarrado", "dash", "intangivel", "super_armor", "bloqueando", "tempo_parado", "dormindo",
         "transformado", "lancado", "oculto", "no_ar")


def _fase(decorrido: float) -> tuple[int, float, float]:
    acumulado = 0.0
    for indice, duracao in enumerate(DURACOES, start=1):
        if decorrido < acumulado + duracao:
            return indice, (decorrido - acumulado) / duracao, duracao
        acumulado += duracao
    return 5, 1.0, DURACOES[-1]


def timeline_sintetica(duracao: float = 2.0, *, hz: int = 60, com_sons: bool = True) -> dict:
    n = int(round(duracao * hz))
    cx, cy = 5.06, 9.0
    lutadores = {s: {c: [] for c in CANAIS_LUTADOR} for s in ("p1", "p2")}
    raio = {"p1": 0.74, "p2": 0.93}
    camera = {c: [] for c in ("x", "y", "zoom", "lv", "av", "ox", "oy")}
    glob = {c: [] for c in ("tj", "escala", "hitstop", "letterbox", "fim")}
    eventos: list[dict] = []
    periodo = 1.0                       # um golpe do p1 por segundo
    total_golpe = sum(DURACOES)
    for i in range(n):
        t = i / hz
        pos = {}
        for slot, fase0 in (("p1", 0.0), ("p2", math.pi)):
            a = 0.9 * t + fase0
            pos[slot] = (cx + 1.35 * math.cos(a), cy + 1.35 * math.sin(a))
        for slot, outro in (("p1", "p2"), ("p2", "p1")):
            x, y = pos[slot]
            ox, oy = pos[outro]
            olhar = math.degrees(math.atan2(oy - y, ox - x))
            fase, prog, dur = 0, 0.0, 0.0
            swing = 0.0
            if slot == "p1" and (t % periodo) < total_golpe:
                fase, prog, dur = _fase(t % periodo)
                swing = {1: -35 * prog, 2: -35 + 95 * prog, 3: 60, 4: 60 - 20 * prog, 5: 40 * (1 - prog)}[fase]
            arma_ang = olhar + swing
            r = raio[slot]
            comprimento = r * 2.5 - r * 0.9
            gx = x + math.cos(math.radians(arma_ang)) * r * 0.9
            gy = y + math.sin(math.radians(arma_ang)) * r * 0.9
            c = lutadores[slot]
            valores = {
                "x": round(x, 3), "y": round(y, 3), "z": 0.0, "ang": round(olhar, 1), "vx": 0.0, "vy": 0.0,
                "hp": round(max(0.2, 1.0 - 0.15 * int(t / periodo)) if slot == "p2" else 1.0, 3),
                "mp": 1.0, "est": 1.0,
                "expr": EXPRESSOES.index("esforco" if fase else ("determinado" if slot == "p1" else "alerta")),
                "acao": 0, "plano": -1, "plano_p": 0.0, "tell": -1, "flags": 1 if fase else 0,
                "golpe_fase": fase, "golpe_p": round(prog, 3), "golpe_d": dur, "golpe_id": int(t / periodo),
                "golpe_janela": 1 if fase in (2, 3) else 0, "anim_fase": fase, "anim_p": round(prog, 3),
                "arma_ang": round(arma_ang, 1), "arma_lunge": 0.0, "arma_gx": round(gx, 3),
                "arma_gy": round(gy, 3),
                "arma_px": round(gx + math.cos(math.radians(arma_ang)) * comprimento, 3),
                "arma_py": round(gy + math.sin(math.radians(arma_ang)) * comprimento, 3),
                "arma_puxada": 0.0, "hb_on": 1, "hb_ang": round(arma_ang, 1), "hb_larg": 60.0,
                "escudo": 0.0, "combo": 0, "flash": 0.0, "flash_cor": 0xFFFFFF, "esc_x": 1.0, "esc_y": 1.0,
            }
            for chave, valor in valores.items():
                c[chave].append(valor)
            anterior = c["golpe_fase"][-2] if len(c["golpe_fase"]) > 1 else 0
            if slot == "p1" and fase == 3 and anterior != 3:
                eventos.append({"i": i, "t": round(t, 4), "tipo": "acerto", "alvo": "p2", "autor": "p1",
                                "dano": 42.0, "dano_pct": 0.05, "golpes": 1, "categoria": "ataque_corpo_a_corpo",
                                "tier": "heavy", "critico": False, "x": round(pos["p2"][0], 3),
                                "y": round(pos["p2"][1], 3), "z": 0.0,
                                "dir": round(math.degrees(math.atan2(pos["p2"][1] - y, pos["p2"][0] - x)), 1)})
        mx = (pos["p1"][0] + pos["p2"][0]) / 2
        my = (pos["p1"][1] + pos["p2"][1]) / 2
        for chave, valor in (("x", round(mx, 3)), ("y", round(my, 3)), ("zoom", 3.6), ("lv", 6.0),
                             ("av", 10.667), ("ox", 0.0), ("oy", 0.0)):
            camera[chave].append(valor)
        for chave, valor in (("tj", round(t, 4)), ("escala", 1.0), ("hitstop", 0.0),
                             ("letterbox", 0.3 if t > duracao - 0.3 else 0.0), ("fim", 0)):
            glob[chave].append(valor)

    def q(t: float) -> int:
        """O roteiro e escrito para 2 s; outra duracao estica/encolhe junto."""
        return min(n - 1, int(round(t * duracao / 2.0 * hz)))

    def trilha(ident, i0, i1, fixos, canais):
        i1 = min(i1, n - 1)
        doc = {"id": ident, **fixos, "i0": i0, "i1": i1}
        for nome, funcao in canais.items():
            doc[nome] = [funcao((i - i0) / max(1, i1 - i0)) for i in range(i0, i1 + 1)]
        return doc

    objetos = [
        trilha(1, q(0.2), q(0.8), {"tipo": "projetil", "nome": "Bola de Fogo", "dono": "p2",
                                                 "elemento": "FOGO", "cor": 0xFF7800, "efeito": "QUEIMAR", "vida0": 2.0},
               {"x": lambda f: round(cx + 2.0 - 3.5 * f, 3), "y": lambda f: round(cy - 1.0 + 1.5 * f, 3),
                "r": lambda f: 0.3, "ang": lambda f: 180.0, "prog": lambda f: round(f * 0.3, 3)}),
        trilha(2, q(0.9), q(1.7), {"tipo": "area", "nome": "Pilar de Gelo", "dono": "p1",
                                                 "elemento": "GELO", "cor": 0x64C8FF, "efeito": "CONGELAR", "raio_max": 1.2},
               {"x": lambda f: cx - 1.0, "y": lambda f: cy + 1.8, "r": lambda f: 1.2,
                "ativ": lambda f: 0 if f < 0.35 else 1, "prog": lambda f: round(f, 3)}),
        trilha(3, q(1.2), q(1.35), {"tipo": "beam", "nome": "Relampago", "dono": "p2",
                                                  "elemento": "RAIO", "cor": 0xFFFF64, "efeito": "ATORDOAR",
                                                  "de": [cx + 1.5, cy - 2.0], "ate": [cx - 1.0, cy + 0.5],
                                                  "pontos": [[cx + 1.5, cy - 2.0], [cx + 0.9, cy - 1.1],
                                                             [cx + 0.4, cy - 0.9], [cx - 1.0, cy + 0.5]],
                                                  "vida0": 0.15},
               {"larg": lambda f: 8.0, "prog": lambda f: round(f, 3)}),
    ]
    efeitos = [trilha(4, q(1.0), q(1.6), {"tipo": "status", "alvo": "p2", "status": "ATORDOADO",
                                                        "cor": 0xFFE65A, "glifo": "*", "estilo": "anel",
                                                        "prioridade": 9, "duracao": 0.6},
                      {"rest": lambda f: round(0.6 * (1 - f), 3)})]
    eventos += [
        {"i": 0, "t": 0.0, "tipo": "skill", "slot": "p2", "nome": "Bola de Fogo", "tipo_skill": "PROJETIL", "elemento": "FOGO"},
        {"i": q(0.4), "tipo": "dash", "slot": "p2", "x": cx, "y": cy, "vx": 8.0, "vy": -2.0},
        {"i": q(0.7), "tipo": "parede", "slot": "p2", "x": cx + 2.2, "y": cy - 1.0, "intensidade": 9.0},
        {"i": q(1.2), "tipo": "skill", "slot": "p2", "nome": "Relampago", "tipo_skill": "BEAM", "elemento": "RAIO"},
    ]
    for ev in eventos:
        ev["t"] = round(ev["i"] / hz, 4)
    eventos.sort(key=lambda e: e["i"])
    sons = None
    if com_sons:
        itens = [{"t": 0.0, "id": "arena_start", "volume": 0.0134, "pitch": 1.0}]
        mapa = {"acerto": "slash_heavy", "dash": "dash_whoosh", "parede": "wall_impact_light"}
        for ev in eventos:
            t = math.ceil(ev["i"] / 2) / 30
            if ev["tipo"] == "skill":
                itens.append({"t": round(t, 3), "id": "fireball_cast" if ev["tipo_skill"] == "PROJETIL" else "beam_fire",
                              "volume": 0.56, "pitch": 1.0})
            elif ev["tipo"] in mapa:
                itens.append({"t": round(t, 3), "id": mapa[ev["tipo"]], "volume": 0.6, "pitch": 1.0})
                if ev["tipo"] == "acerto":
                    itens.append({"t": round(t, 3), "id": "clash_swords", "volume": 0.3, "pitch": 1.05})
        itens.sort(key=lambda s: s["t"])
        sons = {"versao": 1, "relogio": "video", "itens": itens}
    arma1 = {"nome": "Espada de Teste", "tipo": "Reta", "estilo": "Espada Longa", "raridade": "Comum",
             "cor": 0xC0C8D8, "empunhadura": {"avanco_r": 0.9, "lateral_r": 0.0}, "comprimento_m": 1.184}
    arma2 = {"nome": "Machado de Teste", "tipo": "Transformável", "estilo": "Machado-Martelo",
             "raridade": "Comum", "cor": 0xAB9DA5, "empunhadura": {"avanco_r": 0.9, "lateral_r": 0.0},
             "comprimento_m": 1.488}
    return {
        "formato": "neural-fights/timeline", "versao": 1, "hz": hz, "n": n, "duracao": round(n / hz, 4),
        "unidades": {"distancia": "m", "angulo": "graus (0 = +x, horario na tela)", "tempo": "s", "cor": "0xRRGGBB"},
        "ppm_motor": 50,
        "luta": {"seed": 0, "p1": "Teste Azul", "p2": "Teste Vermelho", "cenario": "Torre", "camera_modo": "DIRETOR",
                 "sintetica": True},
        "tela_referencia": [1080, 1920],
        "arena": {"nome": "Salao da Torre", "formato": "retangular", "largura": 10.125, "altura": 18.0,
                  "min": [0.0, 0.0], "max": [10.125, 18.0], "centro": [5.062, 9.0], "raio": None,
                  "tem_paredes": True, "espessura_parede": 0.3, "cor_chao": 2498590, "cor_parede": 5127728,
                  "cor_borda": 9860678, "cor_ambiente": 1971728, "tema": "castelo", "efeitos": [],
                  "obstaculos": [{"tipo": "pilar", "x": 1.8, "y": 5.5, "largura": 1.2, "altura": 1.2,
                                  "cor": 6578005, "solido": True, "destrutivel": False, "hp": 100.0}]},
        "lutadores": [
            {"slot": "p1", "nome": "Teste Azul", "rotulo": "Teste Azul", "classe": "Guerreiro (Teste)",
             "cor": 0x3C78D8, "cor_lado": 0x3498DB, "tamanho": 1.48, "raio_corpo": 0.74, "raio_fisico": 0.37,
             "tier_impacto": "heavy", "arma": arma1},
            {"slot": "p2", "nome": "Teste Vermelho", "rotulo": "Teste Vermelho", "classe": "Piromante (Fogo)",
             "cor": 0xD84A3C, "cor_lado": 0xE74C3C, "tamanho": 1.86, "raio_corpo": 0.93, "raio_fisico": 0.465,
             "tier_impacto": "light", "arma": arma2},
        ],
        "tabelas": {"expressoes": list(EXPRESSOES), "acoes": ["COMBATE"], "planos": [], "planos_tipo": [],
                    "tells": [], "estados_orbe": ["orbitando", "carregando", "disparando"], "fases": list(FASES),
                    "flags": list(FLAGS)},
        "trilhas": {"global": glob, "camera": camera, "lutadores": lutadores, "objetos": objetos, "efeitos": efeitos},
        "eventos": eventos, "sons": sons, "remapeamento": None,
        "resultado": {"vencedor": None, "vencedor_slot": None, "empate": True, "motivo": "sintetica",
                      "duracao_jogo": round(n / hz, 4), "duracao_video": round(n / hz, 4), "ko_em_video": None,
                      "passos": n, "quadros_video": n // 2, "passos_por_quadro": 2, "hp_final": {}, "seed": 0},
    }
