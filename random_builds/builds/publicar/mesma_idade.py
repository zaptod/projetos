# -*- coding: utf-8 -*-
"""A medida da semana na MESMA IDADE (21/10/2026).

O PLANO muda UMA coisa por semana e mede "views por video e % que assistiu
x semana anterior". Comparar o total de hoje engana: o duelo de semana
passada esta ha 7 dias no ar e o de ontem ha 1. Aqui cada video NOVO (da
semana da mudanca) e comparado com os ANTIGOS (os 7 dias antes dela) na
MESMA IDADE: views com 6, 12, 24, 48, 72 h e 7 dias de vida.

O CRITERIO, escrito antes de medir (e no config, nao no codigo):

- a semana comeca na HORA em que a mudanca foi ao ar
  (`config/medida_da_semana.json`, `inicio`) e vai 7 dias; "antigos" sao os
  7 dias antes do inicio. Mesmo canal, mesmo formato, cada plataforma por si;
- a idade de um video e a hora do NUMERO menos a hora da postagem (o
  `quando` do ledger, local);
- "views na idade X" e a observacao mais perto de X dentro de +-5 h, SEM
  interpolar. Fora da tolerancia, o video nao tem numero naquela idade e
  e CONTADO ("sem leitura nessa idade"), nunca estimado;
- de onde vem cada observacao: a leitura de hora em hora (`hora_a_hora`,
  so YouTube, so videos com menos de 48 h), a fotografia diaria
  (`_analise/historico`, uma por dia, com a hora da parte) e o arquivo de
  hoje de cada video;
- YouTube so com video PUBLICO (privado e "sem status" ficam fora e sao
  contados); mediana por video; o rotulo de certeza e o da analise
  (`analise.confianca`: claro / provavel / incerto, Mann-Whitney).

CASO ZERO: semana sem video novo e "nao ha comparacao" (estado
`sem_novos`), nunca "sem efeito"; sem config, `sem_semana`. Um lado vazio
numa idade = "nao ha comparacao nessa idade". Video que ainda nao chegou
na idade e "ainda juntando".

As fotografias de 19 a 21/10 nasceram SEM a hora (o campo entrou hoje). Para
elas a hora sai do log do servico do dia (`historias/outputs/_logs/
auto_AAAAMMDD.txt`, a linha de fim de cada parte) — hora MEDIDA de quando o
numero foi gravado; no YouTube as views foram lidas ate ~20 min antes dela.
Fotografia sem hora nenhuma nao entra (e e contada).
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from . import metricas

IDADES_H = (6, 12, 24, 48, 72, 168)
TOLERANCIA_H = 5.0
DIAS_DE_CADA_LADO = 7
MADURO_DIAS = 3
MIN_VIEWS_RETENCAO = 20

# `None` = `<random_builds>/config/medida_da_semana.json` (os testes trocam).
CONFIG = None


def caminho_do_config() -> Path:
    return Path(CONFIG) if CONFIG else Path(metricas.RAIZ) / "config" / "medida_da_semana.json"


def _instante(texto) -> datetime | None:
    if not texto:
        return None
    try:
        valor = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError:
        return None
    if valor.tzinfo is not None:
        valor = valor.astimezone().replace(tzinfo=None)
    return valor


# ------------------------------------------------------------------ config
def semana_vigente(agora: datetime, config: dict | None = None) -> tuple:
    """`(semana, erro)`. A semana e a de `inicio` mais recente que ja
    comecou. `(None, "")` = config sem semana nenhuma comecada;
    `(None, motivo)` = config ilegivel ou torto (vira aviso)."""
    if config is None:
        try:
            config = json.loads(caminho_do_config().read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            return None, ""
        except (OSError, ValueError) as exc:
            return None, f"config da medida da semana ilegível: {type(exc).__name__}: {exc}"
    escolhida = None
    for bloco in (config or {}).get("semanas") or []:
        if not isinstance(bloco, dict):
            continue
        inicio = _instante(bloco.get("inicio"))
        if inicio is None:
            return None, f"semana {bloco.get('semana')!r} sem 'inicio' legível"
        if inicio <= agora and (escolhida is None or inicio > escolhida["inicio"]):
            escolhida = {**bloco, "inicio": inicio}
    if escolhida is None:
        return None, ""
    dias = int(config.get("dias_de_cada_lado") or DIAS_DE_CADA_LADO)
    escolhida["fim"] = escolhida["inicio"] + timedelta(days=dias)
    escolhida["antes_de"] = escolhida["inicio"] - timedelta(days=dias)
    escolhida.setdefault("canal", "builds")
    escolhida.setdefault("formato", "duelo")
    escolhida.setdefault("plataformas", ["youtube", "tiktok"])
    escolhida["idades_h"] = [float(x) for x in (config.get("idades_h") or IDADES_H)]
    escolhida["tolerancia_h"] = float(config.get("tolerancia_h") or TOLERANCIA_H)
    return escolhida, ""


# ------------------------------------------------- a hora das fotografias
_LINHA_YT = re.compile(r"^(\d{2}:\d{2}:\d{2}) \d+ video\(s\) atualizados em (.+)$")
_LINHA_TK = re.compile(r"^(\d{2}:\d{2}:\d{2}) \[tiktok-metricas\] (\w+): \d+ video\(s\) gravados em")


def _parte_do_caminho(caminho: str) -> str | None:
    pedacos = [p.lower() for p in re.split(r"[\\/]", caminho.strip()) if p]
    if "random_builds" in pedacos:
        return "builds"
    if "historias" in pedacos:
        return "historias"
    return None


def horas_pelo_log(dias: list, limites: dict | None = None,
                   pasta_dos_logs: Path | None = None) -> dict:
    """`{dia: {parte: "AAAA-MM-DDTHH:MM:SS"}}` — a hora em que cada parte da
    coleta GRAVOU o numero naquele dia, lida do log do servico do dia.

    `limites[dia]` (a hora em que a fotografia foi escrita): so vale linha
    de antes dela, e a ultima delas — a fotografia foi tirada do disco que
    essa coleta deixou. Sem linha, a parte fica sem hora (nao entra)."""
    pasta_dos_logs = Path(pasta_dos_logs or (metricas.OUTRAS_RAIZES["historias"]
                                             / "outputs" / "_logs"))
    saida: dict = {}
    for dia in dias:
        try:
            texto = (pasta_dos_logs / f"auto_{dia.replace('-', '')}.txt").read_text(
                encoding="utf-8", errors="replace")
        except OSError:
            continue
        limite = (limites or {}).get(dia)
        horas: dict = {}
        for linha in texto.splitlines():
            m = _LINHA_YT.match(linha)
            if m:
                parte = _parte_do_caminho(m.group(2))
            else:
                m = _LINHA_TK.match(linha)
                parte = f"{m.group(2)}_tiktok" if m else None
            if not m or not parte:
                continue
            instante = f"{dia}T{m.group(1)}"
            if limite and instante > limite:
                continue
            horas[parte] = instante          # a ULTIMA antes do limite
        if horas:
            saida[dia] = horas
    return saida


# ------------------------------------------------------------ observacoes
def observacoes(regs: list, fotos: dict | None = None, leituras: list | None = None,
                horas_das_fotos: dict | None = None) -> tuple:
    """`({(parte, id): [(instante, views, fonte)]}, sem_hora)`.

    `sem_hora` conta os videos de fotografia que ficaram de fora por nao
    se saber a hora do numero."""
    obs: dict = {}
    sem_hora = 0

    def junta(parte, vid, instante, views, fonte):
        if instante is None or views is None or not vid:
            return
        obs.setdefault((parte, str(vid)), []).append((instante, int(views), fonte))

    for r in regs or []:
        parte = metricas.nome_da_parte(r["canal"], r["plataforma"])
        junta(parte, r.get("id"), _instante(r.get("medido_em")), r.get("views"), "coleta do dia")
    for dia, foto in sorted((fotos or {}).items()):
        if not isinstance(foto, dict):
            continue
        das_partes = foto.get("quando_das_partes") or {}
        do_log = (horas_das_fotos or {}).get(dia) or {}
        for parte in ("builds", "builds_tiktok", "historias", "historias_tiktok"):
            videos = foto.get(parte)
            if not isinstance(videos, dict):
                continue
            hora_da_parte = _instante(das_partes.get(parte))
            fonte = "fotografia diária"
            if hora_da_parte is None and do_log.get(parte):
                hora_da_parte = _instante(do_log[parte])
                fonte = "fotografia diária (hora do log)"
            for vid, valor in videos.items():
                if not (isinstance(valor, list) and valor
                        and isinstance(valor[0], (int, float))):
                    continue
                instante = (_instante(valor[3]) if len(valor) > 3 and valor[3]
                            else hora_da_parte)
                if instante is None:
                    sem_hora += 1
                    continue
                junta(parte, vid, instante, valor[0], fonte)
    for leitura in leituras or []:
        if not isinstance(leitura, dict) or leitura.get("estado") != "ok":
            continue
        parte = metricas.nome_da_parte(str(leitura.get("canal") or "builds"), "youtube")
        instante = _instante(leitura.get("quando"))
        for vid, v in (leitura.get("videos") or {}).items():
            if isinstance(v, dict):
                junta(parte, vid, instante, v.get("views"), "leitura de hora em hora")
    return obs, sem_hora


def views_na_idade(pontos: list, nasceu: datetime, idade_h: float,
                   tolerancia_h: float = TOLERANCIA_H):
    """`(views, idade_real_h, fonte)` da observacao mais perto de `idade_h`
    dentro da tolerancia, ou `None`. Sem interpolar."""
    melhor = None
    for instante, views, fonte in pontos or []:
        idade = (instante - nasceu).total_seconds() / 3600.0
        if idade < 0:
            continue
        distancia = abs(idade - idade_h)
        if distancia <= tolerancia_h and (melhor is None or distancia < melhor[0]):
            melhor = (distancia, views, round(idade, 1), fonte)
    return None if melhor is None else melhor[1:]


# -------------------------------------------------------------- comparacao
def _mediana(valores):
    from .analise import mediana
    return mediana(valores)


def _confianca(a, b):
    from .analise import confianca
    return confianca(a, b)


def _sentido(novos: list, antigos: list, conf: str) -> str:
    if not novos or not antigos:
        return "sem_comparacao"
    if conf == "incerto":
        return "incerto"
    mn, ma = _mediana(novos), _mediana(antigos)
    if mn > ma:
        return "subiu"
    if mn < ma:
        return "caiu"
    return "igual"


def _lado(regs: list, de: datetime, ate: datetime, agora: datetime,
          plataforma: str) -> tuple:
    """Os videos postados em [de, ate) ate agora: `(entram, fora)`."""
    entram, fora = [], {"privados": 0, "sem_status": 0}
    for r in regs:
        quando = _instante(r.get("quando"))
        if quando is None or not (de <= quando < ate) or quando > agora:
            continue
        if plataforma == "youtube" and r.get("publico") is not True:
            fora["privados" if r.get("publico") is False else "sem_status"] += 1
            continue
        entram.append(r)
    return entram, fora


def _bloco_da_plataforma(regs, plataforma, semana, agora, obs, series) -> dict:
    canal, formato = semana["canal"], semana["formato"]
    parte = metricas.nome_da_parte(canal, plataforma)
    proprios = [r for r in regs if r["canal"] == canal and r["plataforma"] == plataforma
                and r.get("formato") == formato]
    novos, fora_n = _lado(proprios, semana["inicio"], semana["fim"], agora, plataforma)
    antigos, fora_a = _lado(proprios, semana["antes_de"], semana["inicio"], agora, plataforma)
    tol = semana["tolerancia_h"]

    def na_idade(r, x):
        nasceu = _instante(r["quando"])
        return views_na_idade(obs.get((parte, r["id"])) or [], nasceu, x, tol)

    def idade_agora(r):
        return (agora - _instante(r["quando"])).total_seconds() / 3600.0

    idades = []
    for x in semana["idades_h"]:
        pares_n = [(r, na_idade(r, x)) for r in novos]
        pares_a = [(r, na_idade(r, x)) for r in antigos]
        vn = [p[1][0] for p in pares_n if p[1]]
        va = [p[1][0] for p in pares_a if p[1]]
        juntando = sum(1 for r, p in pares_n if not p and idade_agora(r) < x - tol)
        conf = _confianca(vn, va)
        idades.append({
            "idade_h": x,
            "novos": {"n": len(vn), "mediana": _mediana(vn), "zeros": sum(1 for v in vn if v == 0),
                      "juntando": juntando,
                      "sem_leitura": len(novos) - len(vn) - juntando},
            "antigos": {"n": len(va), "mediana": _mediana(va),
                        "zeros": sum(1 for v in va if v == 0),
                        "sem_leitura": len(antigos) - len(va)},
            "razao": (round(_mediana(vn) / _mediana(va), 2)
                      if vn and va and _mediana(va) else None),
            "confianca": conf, "sentido": _sentido(vn, va, conf)})
    por_video = []
    for r in sorted(novos, key=lambda r: r["quando"]):
        pontos = {}
        for item in idades:
            p = na_idade(r, item["idade_h"])
            if p:
                pontos[str(int(item["idade_h"]))] = {
                    "views": p[0], "idade_real_h": p[1], "fonte": p[2],
                    "mediana_dos_antigos": item["antigos"]["mediana"],
                    "n_antigos": item["antigos"]["n"]}
        por_video.append({"id": r["id"], "titulo": r.get("titulo", ""), "quando": r["quando"],
                          "idade_h_agora": round(idade_agora(r), 1),
                          "views_agora": r.get("views"), "pontos": pontos})

    def maduros(lado):
        return [r for r in lado if idade_agora(r) >= MADURO_DIAS * 24]

    def retencoes(lado):
        return [r["retencao"] for r in maduros(lado) if r.get("retencao") is not None]

    rn, ra = retencoes(novos), retencoes(antigos)
    retencao = {"novos": {"n": len(rn), "mediana": _mediana(rn), "maduros": len(maduros(novos))},
                "antigos": {"n": len(ra), "mediana": _mediana(ra),
                            "maduros": len(maduros(antigos))},
                "confianca": _confianca(rn, ra)}
    retencao["sentido"] = _sentido(rn, ra, retencao["confianca"])
    bloco = {"plataforma": plataforma, "parte": parte,
             "novos": len(novos), "antigos": len(antigos),
             "fora": {"novos": fora_n, "antigos": fora_a},
             "idades": idades, "por_video": por_video, "retencao": retencao}
    if plataforma == "youtube":
        en = [r["engaged_views"] for r in maduros(novos) if r.get("engaged_views") is not None]
        ea = [r["engaged_views"] for r in maduros(antigos) if r.get("engaged_views") is not None]
        bloco["engajadas"] = {"novos": {"n": len(en), "mediana": _mediana(en)},
                              "antigos": {"n": len(ea), "mediana": _mediana(ea)},
                              "confianca": _confianca(en, ea)}
        bloco["inscritos_por_mil"] = inscritos_por_mil(
            (series or {}).get(canal), semana, agora)
    return bloco


def inscritos_por_mil(serie: dict | None, semana: dict, agora: datetime) -> dict:
    """Inscritos liquidos por mil views do CANAL, nos dias que a Analytics
    ja tem (atraso de ~3 dias). Dia sem linha nao e dia de zero: e contado
    em `dias_sem_dado`."""
    linhas = {str(l[0]): l for l in ((serie or {}).get("dias") or [])
              if isinstance(l, list) and len(l) >= 5}

    def lado(de: date, ate: date) -> dict:
        views = ganhos = perdidos = com = sem = 0
        d = de
        while d < ate and d <= agora.date():
            l = linhas.get(d.isoformat())
            if l is None:
                sem += 1
            else:
                com += 1
                views += int(l[1] or 0)
                ganhos += int(l[3] or 0)
                perdidos += int(l[4] or 0)
            d += timedelta(days=1)
        return {"dias_com_dado": com, "dias_sem_dado": sem, "views": views,
                "inscritos_liquidos": ganhos - perdidos,
                "por_mil": round((ganhos - perdidos) / views * 1000, 2) if views else None}

    if not linhas:
        return {"estado": "sem_serie"}
    return {"estado": "ok",
            "semana": lado(semana["inicio"].date(), semana["fim"].date()),
            "anterior": lado(semana["antes_de"].date(), semana["inicio"].date())}


def comparar(regs: list, agora: datetime, semana: dict | None, *, fotos=None,
             leituras=None, horas_das_fotos=None, series=None, erro_do_config: str = "") -> dict:
    """A comparacao inteira, sem disco nem rede."""
    if semana is None:
        saida = {"estado": "sem_semana",
                 "erro": erro_do_config,
                 "motivo": erro_do_config or "nenhuma semana começada em "
                                             "config/medida_da_semana.json"}
        saida["texto"] = texto(saida)
        return saida
    obs, sem_hora = observacoes(regs, fotos, leituras, horas_das_fotos)
    blocos = {p: _bloco_da_plataforma(regs, p, semana, agora, obs, series)
              for p in semana["plataformas"]}
    total_novos = sum(b["novos"] for b in blocos.values())
    total_antigos = sum(b["antigos"] for b in blocos.values())
    estado = ("sem_novos" if not total_novos else
              "sem_antigos" if not total_antigos else "ok")
    leituras_24h = [l for l in leituras or [] if isinstance(l, dict)
                    and (_instante(l.get("quando")) or datetime.min) > agora - timedelta(hours=24)]
    saida = {"estado": estado,
             "semana": {k: (v.isoformat(timespec="minutes") if isinstance(v, datetime) else v)
                        for k, v in semana.items()},
             "criterio": (f"novos = {semana['formato']}s do canal {semana['canal']} postados de "
                          f"{semana['inicio']:%d/%m %H:%M} a {semana['fim']:%d/%m %H:%M}; "
                          f"antigos = de {semana['antes_de']:%d/%m %H:%M} até o início. "
                          f"Views na idade X = a leitura mais perto de X dentro de "
                          f"±{semana['tolerancia_h']:g} h, sem interpolar; mediana por vídeo; "
                          f"YouTube só público."),
             "plataformas": blocos,
             "fotos_sem_hora": sem_hora,
             "leituras_hora_24h": {"ok": sum(1 for l in leituras_24h if l.get("estado") == "ok"),
                                   "vazio": sum(1 for l in leituras_24h if l.get("estado") == "vazio"),
                                   "erro": sum(1 for l in leituras_24h if l.get("estado") == "erro")},
             "gerado_em": agora.isoformat(timespec="minutes")}
    saida["avisos"] = avisos(saida, regs, semana, agora)
    saida["texto"] = texto(saida)
    return saida


def avisos(c: dict, regs: list, semana: dict, agora: datetime) -> list:
    """O que a medida da semana nao pode deixar passar calado."""
    saida = []
    yt = (c.get("plataformas") or {}).get("youtube")
    novos_48h = [r for r in regs if r["canal"] == semana["canal"] and r["plataforma"] == "youtube"
                 and (_instante(r.get("quando")) or datetime.min) > agora - timedelta(hours=48)]
    lidas = c["leituras_hora_24h"]
    if yt is not None and novos_48h and not lidas["ok"]:
        saida.append(f"leitura de hora em hora PARADA: {len(novos_48h)} vídeo(s) do YouTube com "
                     f"menos de 48 h e nenhuma leitura boa nas últimas 24 h "
                     f"({lidas['erro']} com erro)")
    if c.get("fotos_sem_hora"):
        saida.append(f"{c['fotos_sem_hora']} número(s) de fotografias sem hora ficaram fora da "
                     "comparação na mesma idade")
    return saida


# ------------------------------------------------------------------ texto
def _n(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float) and not v.is_integer():
        return f"{v:.1f}".replace(".", ",")
    return str(int(v))


def _pct(v) -> str:
    return "—" if v is None else f"{_n(v)}%"


ROTULO = {"claro":"certeza clara", "provavel": "certeza provável",
          "incerto": "INCERTO (poucos vídeos ou diferença pequena)"}
SENTIDO = {"subiu": "SUBIU", "caiu": "CAIU", "igual": "igual",
           "incerto": "ainda não dá para dizer", "sem_comparacao": "não há comparação"}


def _idade(h: float) -> str:
    return f"{int(h // 24)} dias" if h >= 72 and h % 24 == 0 else f"{int(h)} h"


def texto(c: dict) -> str:
    """O texto que o `--ver`, a pagina e o Telegram mostram. Simples."""
    if c.get("estado") == "sem_semana":
        return ("Medida da semana: " + (c.get("motivo") or "sem semana marcada") +
                ". Sem a data da mudança não há comparação.")
    s = c["semana"]
    inicio = _instante(s["inicio"])
    linhas = [f"Medida da semana {s.get('semana', '?')} — {s.get('mudanca', '')}".rstrip(" —"),
              f"desde {inicio:%d/%m %H:%M}, {s['formato']}s do canal {s['canal']}, na MESMA idade "
              f"(±{s['tolerancia_h']:g} h, sem interpolar)"]
    if c["estado"] == "sem_novos":
        linhas.append("Nenhum vídeo novo desde o início: NÃO há comparação (não é 'sem efeito').")
    elif c["estado"] == "sem_antigos":
        linhas.append("Nenhum vídeo antigo para comparar: NÃO há comparação.")
    for plataforma, b in (c.get("plataformas") or {}).items():
        nome = "YouTube" if plataforma == "youtube" else "TikTok"
        fora = b["fora"]["novos"]
        extra = (f"; fora: {fora['privados']} privado(s), {fora['sem_status']} sem status"
                 if fora["privados"] or fora["sem_status"] else "")
        linhas.append(f"{nome}: {b['novos']} novo(s) × {b['antigos']} antigo(s){extra}")
        for i in b["idades"]:
            n, a = i["novos"], i["antigos"]
            if not n["n"] and n["juntando"] == b["novos"] and b["novos"]:
                linhas.append(f"  {_idade(i['idade_h'])}: ainda juntando "
                              f"(nenhum novo chegou nessa idade)")
                continue
            if not n["n"] and not a["n"]:
                linhas.append(f"  {_idade(i['idade_h'])}: sem leitura nessa idade nos dois lados")
                continue
            texto_i = (f"  {_idade(i['idade_h'])}: novos {_n(n['mediana'])} (n={n['n']}) × "
                       f"antigos {_n(a['mediana'])} (n={a['n']})")
            if i["razao"] is not None:
                texto_i += f" = {_n(i['razao'])}x"
            texto_i += f" → {SENTIDO[i['sentido']]}"
            if i["sentido"] not in ("sem_comparacao",):
                texto_i += f" [{ROTULO.get(i['confianca'], i['confianca'])}]"
            pend = []
            if n["juntando"]:
                pend.append(f"{n['juntando']} novo(s) ainda juntando")
            if n["sem_leitura"]:
                pend.append(f"{n['sem_leitura']} novo(s) sem leitura nessa idade")
            if a["sem_leitura"]:
                pend.append(f"{a['sem_leitura']} antigo(s) sem leitura nessa idade")
            if pend:
                texto_i += " (" + "; ".join(pend) + ")"
            linhas.append(texto_i)
        r = b["retencao"]
        linhas.append(f"  % assistido (vídeos com 3+ dias): novos {_pct(r['novos']['mediana'])} "
                      f"(n={r['novos']['n']} de {r['novos']['maduros']} maduros) × antigos "
                      f"{_pct(r['antigos']['mediana'])} (n={r['antigos']['n']}) → "
                      f"{SENTIDO[r['sentido']]}")
        if "engajadas" in b:
            e = b["engajadas"]
            linhas.append(f"  views engajadas (3+ dias): novos {_n(e['novos']['mediana'])} "
                          f"(n={e['novos']['n']}) × antigos {_n(e['antigos']['mediana'])} "
                          f"(n={e['antigos']['n']}); vídeo sem o número = não medido")
        ipm = b.get("inscritos_por_mil") or {}
        if ipm.get("estado") == "ok":
            se, an = ipm["semana"], ipm["anterior"]
            linhas.append(f"  inscritos por mil views (canal): semana {_n(se['por_mil'])} "
                          f"({se['dias_com_dado']} dia(s) com dado, {se['dias_sem_dado']} ainda "
                          f"sem) × anterior {_n(an['por_mil'])} ({an['dias_com_dado']} dia(s))")
        elif "inscritos_por_mil" in b:
            linhas.append("  inscritos por mil views: série do canal não lida (não medi)")
        for v in b["por_video"]:
            # A idade REAL da leitura vai junto: com uma leitura so, a mesma
            # pode servir a 6 h e a 12 h (+-5 h), e isso tem de estar a vista.
            pontos = "; ".join(f"{_idade(float(x))}: {p['views']} aos {_n(p['idade_real_h'])} h "
                               f"(antigos {_n(p['mediana_dos_antigos'])}, n={p['n_antigos']})"
                               for x, p in v["pontos"].items())
            linhas.append(f"    {v['id']} {v['titulo'][:40]} — {_n(v['idade_h_agora'])} h no ar"
                          + (f" — {pontos}" if pontos else " — sem leitura em nenhuma idade ainda"))
    lidas = c.get("leituras_hora_24h") or {}
    linhas.append(f"Leituras de hora em hora nas últimas 24 h: {lidas.get('ok', 0)} boas, "
                  f"{lidas.get('vazio', 0)} sem vídeo novo, {lidas.get('erro', 0)} com erro.")
    linhas += [f"! {a}" for a in c.get("avisos") or []]
    return "\n".join(linhas)
