# -*- coding: utf-8 -*-
"""Etapa 4: as fichas viram o manual do canal.

A agregacao e CODIGO, nao um agente. Contar quantas fichas dizem "corte
seco" e uma contagem — pedir isso a um LLM e trocar um numero exato por uma
impressao, e ainda pagar o contexto de 177 fichas para receber ela. O que se
manda para o modelo e o digesto: as medianas medidas, as contagens por
categoria, os bordoes que se repetem, e uma amostra de fichas inteiras.

Duas etapas no mesmo chat, como a serie longa do `historias/`:

  ESQUELETO  as apostas do canal, a formula, o publico. Nada escrito ainda.
  SECOES     cada secao escrita com o esqueleto inteiro em contexto.

Pedir "escreva a biblia deste canal" num prompt so devolve oito paragrafos
que serviriam para qualquer canal do YouTube. A separacao existe porque a
segunda etapa precisa saber o que a primeira decidiu.

CONSENSO: o ChatGPT e o Gemini leram os mesmos dossies, separados. Onde os
dois dizem a mesma coisa, vira regra. Onde divergem, vira hipotese marcada —
e isso e informacao, nao ruido: divergencia costuma marcar o ponto em que o
canal faz duas coisas diferentes em videos diferentes.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import date

from . import analise
from . import canal as _canal
from . import config, estado, medidas

PROVEDORES = ("chatgpt", "gemini")


class NaoEscreveu(RuntimeError):
    """Erro humano: o que se tentou, e o que fazer."""


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto))
                   if unicodedata.category(c) != "Mn")


def _chave(texto: str) -> str:
    """Normaliza para comparar respostas de dois modelos diferentes."""
    limpo = _sem_acento(str(texto or "")).lower().strip()
    return re.sub(r"[^a-z0-9 ]+", "", limpo)


def _mediana(valores):
    limpos = sorted(v for v in valores if isinstance(v, (int, float)))
    if not limpos:
        return None
    meio = len(limpos) // 2
    if len(limpos) % 2:
        return round(float(limpos[meio]), 2)
    return round((limpos[meio - 1] + limpos[meio]) / 2.0, 2)


def _campo(ficha: dict, secao: str, chave: str) -> str:
    valor = ficha.get(secao)
    if isinstance(valor, dict):
        return str(valor.get(chave) or "").strip()
    return ""


def _contagem(fichas: list, secao: str, chave: str, quantas: int = 6) -> list:
    """As respostas mais repetidas para um campo, com quantas vezes."""
    contador = Counter()
    original = {}
    for ficha in fichas:
        texto = _campo(ficha, secao, chave)
        if not texto:
            continue
        marca = _chave(texto)[:70]
        if not marca:
            continue
        contador[marca] += 1
        original.setdefault(marca, texto)
    return [{"valor": original[m], "vezes": n}
            for m, n in contador.most_common(quantas)]


def _lista_frequente(fichas: list, secao: str, chave: str,
                     quantas: int = 10) -> list:
    """Frequencia dos itens de um campo que e lista (bordoes, por exemplo)."""
    contador = Counter()
    original = {}
    for ficha in fichas:
        valor = ficha.get(secao)
        itens = valor.get(chave) if isinstance(valor, dict) else None
        if not isinstance(itens, list):
            continue
        for item in itens:
            marca = _chave(item)[:50]
            if not marca:
                continue
            contador[marca] += 1
            original.setdefault(marca, str(item).strip())
    return [{"valor": original[m], "vezes": n}
            for m, n in contador.most_common(quantas)]


def _cadencia(videos: list) -> dict:
    """Com que frequencia o canal publica, lido das datas do catalogo."""
    datas = sorted(v["data"] for v in videos if v.get("data"))
    exatas = [v for v in videos if v.get("data") and not v.get("data_aproximada")]
    if len(datas) < 2:
        return {"videos_com_data": len(datas)}
    primeira, ultima = date.fromisoformat(datas[0]), date.fromisoformat(datas[-1])
    dias = max((ultima - primeira).days, 1)
    por_semana = len(datas) * 7.0 / dias
    por_mes = Counter(d[:7] for d in datas)
    return {
        "videos_com_data": len(datas),
        "datas_exatas": len(exatas),
        "primeiro": datas[0],
        "ultimo": datas[-1],
        "por_semana": round(por_semana, 2),
        "intervalo_medio_dias": round(dias / max(len(datas) - 1, 1), 1),
        "meses_mais_ativos": [{"mes": m, "videos": n}
                              for m, n in por_mes.most_common(3)],
        "ultimos_meses": [{"mes": m, "videos": por_mes[m]}
                          for m in sorted(por_mes)[-6:]],
    }


def _numeros_do_acervo(todas: list) -> dict:
    if not todas:
        return {"medidos": 0}
    verticais = sum(1 for m in todas if m.get("vertical"))
    return {
        "medidos": len(todas),
        "duracao_mediana_s": _mediana([m.get("duracao_s") for m in todas]),
        "duracao_min_s": min((m.get("duracao_s") or 0) for m in todas),
        "duracao_max_s": max((m.get("duracao_s") or 0) for m in todas),
        "cortes_por_min_mediana": _mediana([m.get("cortes_por_min")
                                            for m in todas]),
        "plano_medio_s": _mediana([m.get("plano_medio_s") for m in todas]),
        "lufs_mediana": _mediana([(m.get("audio") or {}).get("lufs")
                                  for m in todas]),
        "fala_pct_mediana": _mediana([m.get("fala_pct") for m in todas]),
        "brilho_mediano": _mediana([(m.get("cor") or {}).get("brilho")
                                    for m in todas]),
        "saturacao_mediana": _mediana([(m.get("cor") or {}).get("saturacao")
                                       for m in todas]),
        "verticais": verticais,
        "horizontais": len(todas) - verticais,
        # Quanto o canal usa transicao em vez de corte seco: a diferenca
        # entre o que o detector viu cru e o que sobrou depois de juntar.
        "transicoes_por_corte": _mediana([
            (m.get("deteccoes_cruas") or m.get("cortes") or 1)
            / max(m.get("cortes") or 1, 1) for m in todas]),
    }


def _consenso(por_provedor: dict) -> dict:
    """Onde os dois modelos concordam, e onde nao.

    Compara por video, campo a campo. "Concordam" aqui e frouxo de proposito
    (uma palavra em comum ja conta): o que se quer marcar e leitura
    OPOSTA — um dizendo "didatico" e o outro "indignado" —, nao sinonimo.
    """
    presentes = {p: {f["video_id"]: f for f in fichas}
                 for p, fichas in por_provedor.items() if fichas}
    if len(presentes) < 2:
        return {"comparaveis": 0,
                "aviso": "so um provedor tem fichas; sem consenso a medir"}

    (nome_a, fichas_a), (nome_b, fichas_b) = list(presentes.items())[:2]
    comuns = sorted(set(fichas_a) & set(fichas_b))
    campos = [("gancho", "tecnica"), ("fala", "tom"), ("publico", "quem"),
              ("edicao", "corte"), ("cta", "pede")]
    acordos, divergencias = Counter(), []
    for video_id in comuns:
        for secao, chave in campos:
            a = _campo(fichas_a[video_id], secao, chave)
            b = _campo(fichas_b[video_id], secao, chave)
            if not a or not b:
                continue
            palavras_a = set(_chave(a).split()) - _VAZIAS
            palavras_b = set(_chave(b).split()) - _VAZIAS
            if palavras_a & palavras_b:
                acordos[f"{secao}.{chave}"] += 1
            else:
                divergencias.append({"video_id": video_id,
                                     "campo": f"{secao}.{chave}",
                                     nome_a: a[:110], nome_b: b[:110]})
    total = max(len(comuns) * len(campos), 1)
    return {
        "provedores": [nome_a, nome_b],
        "comparaveis": len(comuns),
        "acordo_pct": round(100.0 * sum(acordos.values()) / total, 1),
        "acordo_por_campo": dict(acordos),
        "divergencias": divergencias[:20],
        "n_divergencias": len(divergencias),
    }


# Palavras que casariam por acaso e fariam qualquer par "concordar".
_VAZIAS = {"o", "a", "os", "as", "de", "do", "da", "e", "que", "em", "um",
           "uma", "para", "com", "no", "na", "por", "se", "the", "of", "and",
           "to", "is", "video", "canal"}


def agregar(canal_id: str) -> dict:
    """O digesto do acervo — tudo que e contagem, contado aqui."""
    pasta = config.pasta_do_canal(canal_id)
    cabecalho = _canal.cabecalho(pasta)
    videos = _canal.videos(pasta)
    todas = medidas.todas(pasta)
    por_provedor = {p: analise.carregar_fichas(pasta, p) for p in PROVEDORES}
    fichas = [f for lista in por_provedor.values() for f in lista]
    if not fichas:
        raise NaoEscreveu(
            f"nao ha nenhuma ficha em {canal_id}. "
            f"Rode antes: python main.py analisar {canal_id} --provedor ambos")

    mais_vistos = sorted(videos, key=lambda v: v.get("views") or 0,
                         reverse=True)[:10]
    return {
        "canal": {k: cabecalho.get(k) for k in
                  ("nome", "url", "youtube_id", "inscritos", "n_videos")},
        "fichas_por_provedor": {p: len(f) for p, f in por_provedor.items()},
        "numeros": _numeros_do_acervo(todas),
        "cadencia": _cadencia(videos),
        "gancho_tecnica": _contagem(fichas, "gancho", "tecnica"),
        "fala_tom": _contagem(fichas, "fala", "tom"),
        "fala_pessoa": _contagem(fichas, "fala", "pessoa"),
        "fala_vocabulario": _contagem(fichas, "fala", "vocabulario"),
        "bordoes": _lista_frequente(fichas, "fala", "bordoes"),
        "edicao_corte": _contagem(fichas, "edicao", "corte"),
        "edicao_b_roll": _contagem(fichas, "edicao", "b_roll"),
        "edicao_texto": _contagem(fichas, "edicao", "texto_na_tela"),
        "edicao_som": _contagem(fichas, "edicao", "som"),
        "publico_quem": _contagem(fichas, "publico", "quem"),
        "publico_dor": _contagem(fichas, "publico", "dor"),
        "publico_por_que_fica": _contagem(fichas, "publico", "por_que_fica"),
        "cta_pede": _contagem(fichas, "cta", "pede"),
        "cta_onde": _contagem(fichas, "cta", "onde"),
        "titulo_formula": _contagem(fichas, "promessa", "titulo_formula"),
        "ja_automatizavel": _lista_frequente(fichas, "reproduzivel",
                                             "ja_automatizavel", 12),
        "exige_pessoa": _lista_frequente(fichas, "reproduzivel",
                                         "exige_pessoa", 12),
        "dificil": _lista_frequente(fichas, "reproduzivel", "dificil", 12),
        "consenso": _consenso(por_provedor),
        "mais_vistos": [{"titulo": v["titulo"], "views": v["views"],
                         "duracao_s": v["duracao_s"]} for v in mais_vistos],
        "total_fichas": len(fichas),
    }


def amostra_de_fichas(canal_id: str, quantas: int = 12) -> list:
    """Fichas inteiras para o prompt — as dos videos mais vistos.

    O digesto diz o que se repete; as fichas inteiras dao ao modelo o TEXTURA
    de uma analise boa, para ele nao escrever a biblia so com adjetivos.
    """
    pasta = config.pasta_do_canal(canal_id)
    ordem = {v["id"]: (v.get("views") or 0) for v in _canal.videos(pasta)}
    escolhidas, vistos = [], set()
    for provedor in PROVEDORES:
        for ficha in analise.carregar_fichas(pasta, provedor):
            if ficha.get("video_id") in vistos:
                continue
            vistos.add(ficha.get("video_id"))
            escolhidas.append(ficha)
    escolhidas.sort(key=lambda f: ordem.get(f.get("video_id"), 0), reverse=True)
    magras = []
    for ficha in escolhidas[:quantas]:
        magras.append({k: v for k, v in ficha.items()
                       if k not in ("bruto", "problemas", "provedor")})
    return magras


# ------------------------------------------------------------- os prompts
def prompt_esqueleto(agregado: dict, amostra: list, cfg: dict) -> str:
    """Etapa 1: as apostas do canal. Nenhuma secao escrita ainda."""
    canal_nome = (agregado.get("canal") or {}).get("nome") or "este canal"
    linhas = []
    add = linhas.append
    add("Voce e analista de formato. Vamos escrever, em DUAS etapas, a "
        f"BIBLIA do canal \"{canal_nome}\": o manual de como ele e feito, "
        "para alguem produzir conteudo PROPRIO no mesmo formato.")
    add("")
    add("ETAPA 1 (agora): so o esqueleto. Nao escreva nenhuma secao ainda.")
    add("")
    add("O que voce tem em maos, e de onde veio cada coisa:")
    add("  - NUMEROS: medidos por software (ffmpeg) no acervo. Sao fato.")
    add("  - CONTAGENS: quantas fichas de video disseram cada coisa. "
        "Vieram de duas IAs lendo os videos separadamente.")
    add("  - CONSENSO: onde as duas concordaram e onde divergiram.")
    add("  - AMOSTRA: fichas inteiras dos videos mais vistos.")
    add("")
    add("DIGESTO DO ACERVO:")
    add("```json")
    add(json.dumps(agregado, ensure_ascii=False, indent=2)[:14000])
    add("```")
    add("")
    add(f"AMOSTRA DE FICHAS ({len(amostra)} videos mais vistos):")
    add("```json")
    add(json.dumps(amostra, ensure_ascii=False, indent=2)[:16000])
    add("```")
    add("")
    add("REGRAS (valem para as duas etapas):")
    add("  - Toda afirmacao precisa de NUMERO medido ou CITACAO com instante. "
        "Afirmacao sem lastro nao entra.")
    add("  - Nada de conselho generico de YouTube. Se a frase serviria para "
        "qualquer canal, ela nao pertence a esta biblia.")
    add("  - Descreva o FORMATO, nao o conteudo. O objetivo e alguem produzir "
        "material proprio no mesmo molde, nao refazer os videos deles.")
    add("  - Onde as duas IAs divergiram, diga que e hipotese e explique as "
        "duas leituras. Divergencia costuma marcar canal que faz duas coisas "
        "diferentes em videos diferentes.")
    add("")
    add("FORMATO DA RESPOSTA (exatamente assim, sem nada em volta):")
    add("")
    add("UMA FRASE: <o canal inteiro numa frase>")
    add("PUBLICO: <a quem fala, em uma linha>")
    add("FORMULA: <o esqueleto do video em uma linha, com os blocos na ordem>")
    add("DURACAO ALVO: <segundos, coerente com a mediana medida>")
    for numero in range(1, 6):
        add(f"APOSTA {numero}: <a decisao> | <a evidencia que a sustenta>")
    add("RISCO: <o que um imitador preguicoso faria de errado>")
    return "\n".join(linhas)


def parse_esqueleto(texto: str) -> dict:
    """Texto da etapa 1 -> {frase, publico, formula, apostas, risco}."""
    campos = {"frase": "", "publico": "", "formula": "", "duracao_alvo": "",
              "risco": ""}
    rotulos = {"uma frase": "frase", "frase": "frase", "publico": "publico",
               "formula": "formula", "duracao alvo": "duracao_alvo",
               "risco": "risco"}
    apostas = []
    for bruta in str(texto or "").splitlines():
        linha = re.sub(r"^\s*[-*+]\s+", "", str(bruta).replace("**", "")).strip()
        linha = re.sub(r"^#{1,4}\s*", "", linha)
        if ":" not in linha:
            continue
        rotulo, _, valor = linha.partition(":")
        chave = _sem_acento(rotulo).strip().lower()
        valor = valor.strip()
        if not valor:
            continue
        aposta = re.match(r"^aposta\s*(\d+)$", chave)
        if aposta:
            decisao, _, evidencia = valor.partition("|")
            apostas.append({"n": int(aposta.group(1)),
                            "decisao": decisao.strip(),
                            "evidencia": evidencia.strip()})
            continue
        if chave in rotulos:
            campos[rotulos[chave]] = valor
    apostas.sort(key=lambda a: a["n"])
    return {**campos, "apostas": apostas, "bruto": str(texto or "")}


def problemas_do_esqueleto(esqueleto: dict) -> list:
    faltando = []
    if not esqueleto.get("frase"):
        faltando.append("sem UMA FRASE")
    if not esqueleto.get("formula"):
        faltando.append("sem FORMULA (e dela que sai o modelo de roteiro)")
    if not esqueleto.get("publico"):
        faltando.append("sem PUBLICO")
    apostas = esqueleto.get("apostas") or []
    if len(apostas) < 3:
        faltando.append(f"so {len(apostas)} aposta(s) de 5")
    sem_lastro = [a["n"] for a in apostas if not a.get("evidencia")]
    if sem_lastro:
        faltando.append(f"apostas sem evidencia: {sem_lastro}")
    return faltando


def prompt_secao(secao: dict, esqueleto: dict, ordem: int, total: int) -> str:
    """Etapa 2: uma secao, com o esqueleto ja no contexto do chat."""
    return (
        f"ETAPA 2 — secao {ordem} de {total}: \"{secao['titulo']}\".\n\n"
        f"O que esta secao precisa entregar: {secao['pede']}.\n\n"
        "Escreva em markdown, comecando pelo titulo em `## `. Entre 150 e 400 "
        "palavras. Cada afirmacao com o numero medido ou a citacao (com "
        "instante) que a sustenta — entre parenteses, no meio do texto.\n"
        "Nada de introducao nem de fecho: so a secao.")


def problemas_da_biblia(biblia: dict, cfg: dict | None = None) -> list:
    """O que separa uma biblia de um texto generico sobre YouTube."""
    cfg = cfg or {}
    exige = set(cfg.get("exige_evidencia") or [])
    faltando = []
    secoes = biblia.get("secoes") or {}
    if not secoes:
        return ["nenhuma secao foi escrita"]
    for chave, texto in secoes.items():
        corpo = str(texto or "").strip()
        if len(corpo.split()) < 60:
            faltando.append(f"a secao {chave} veio curta demais "
                            f"({len(corpo.split())} palavras)")
            continue
        if chave in exige and not _tem_lastro(corpo):
            faltando.append(f"a secao {chave} nao cita nenhum numero nem "
                            "instante — e opiniao, nao biblia")
    if not (biblia.get("esqueleto") or {}).get("apostas"):
        faltando.append("sem as apostas do canal")
    return faltando


# Um numero com unidade, ou um instante `m:ss`. E o lastro minimo.
_LASTRO = re.compile(
    r"\d+\s*(?:s\b|seg|segundo|min|LUFS|%|palavras|cortes|dB)|\d+:\d{2}",
    re.I)


def _tem_lastro(texto: str) -> bool:
    return bool(_LASTRO.search(texto))


def para_markdown(biblia: dict) -> str:
    """A biblia para ler. O JSON ao lado e a mesma coisa para a maquina."""
    canal_dados = biblia.get("canal") or {}
    esqueleto = biblia.get("esqueleto") or {}
    numeros = (biblia.get("agregado") or {}).get("numeros") or {}
    consenso = (biblia.get("agregado") or {}).get("consenso") or {}

    linhas = [f"# Bíblia — {canal_dados.get('nome') or 'canal'}", ""]
    if esqueleto.get("frase"):
        linhas += [f"> {esqueleto['frase']}", ""]
    linhas += [
        f"- **canal**: {canal_dados.get('url', '')}",
        f"- **vídeos catalogados**: {canal_dados.get('n_videos', 0)}",
        f"- **fichas**: {biblia.get('total_fichas', 0)} "
        f"({', '.join(f'{p}: {n}' for p, n in (biblia.get('fichas_por_provedor') or {}).items())})",
        f"- **escrita por**: {biblia.get('provedor', '?')} "
        f"em {biblia.get('escrita_em', '')}",
        "",
    ]
    if numeros.get("medidos"):
        linhas += ["## Os números medidos", "",
                   "| medida | valor |", "|---|---|"]
        rotulos = [
            ("duracao_mediana_s", "duração mediana", "s"),
            ("cortes_por_min_mediana", "cortes por minuto", ""),
            ("plano_medio_s", "plano médio", "s"),
            ("lufs_mediana", "loudness", " LUFS"),
            ("fala_pct_mediana", "proporção de fala", "%"),
            ("brilho_mediano", "brilho médio", ""),
        ]
        for chave, rotulo, unidade in rotulos:
            if numeros.get(chave) is not None:
                linhas.append(f"| {rotulo} | {numeros[chave]}{unidade} |")
        linhas.append(f"| formato | {numeros.get('verticais', 0)} vertical(is), "
                      f"{numeros.get('horizontais', 0)} horizontal(is) |")
        linhas.append(f"| vídeos medidos | {numeros['medidos']} |")
        linhas.append("")

    for chave, texto in (biblia.get("secoes") or {}).items():
        corpo = str(texto or "").strip()
        if not corpo.startswith("#"):
            corpo = f"## {chave}\n\n{corpo}"
        linhas += [corpo, ""]

    if esqueleto.get("apostas"):
        linhas += ["## As apostas, em uma linha cada", ""]
        for aposta in esqueleto["apostas"]:
            linhas.append(f"{aposta['n']}. **{aposta['decisao']}** — "
                          f"{aposta.get('evidencia', '')}")
        linhas.append("")
    if esqueleto.get("risco"):
        linhas += ["## O erro do imitador preguiçoso", "",
                   esqueleto["risco"], ""]

    if consenso.get("comparaveis"):
        linhas += [
            "## Onde as duas IAs discordaram", "",
            f"Concordância de **{consenso.get('acordo_pct', 0)}%** em "
            f"{consenso['comparaveis']} vídeos lidos pelos dois. "
            f"{consenso.get('n_divergencias', 0)} divergência(s) — cada uma é "
            "uma hipótese, não um erro: costumam marcar vídeos em que o canal "
            "faz algo diferente do padrão.", ""]
        for divergencia in (consenso.get("divergencias") or [])[:8]:
            provedores = consenso.get("provedores") or list(PROVEDORES)
            linhas.append(
                f"- `{divergencia['video_id']}` **{divergencia['campo']}** — "
                f"{provedores[0]}: _{divergencia.get(provedores[0], '')}_ · "
                f"{provedores[1]}: _{divergencia.get(provedores[1], '')}_")
        linhas.append("")
    return "\n".join(linhas)


def escrever(canal_id: str, *, provedor: str = "chatgpt",
             headless: bool = False, log=print) -> dict:
    """As duas etapas, no mesmo chat. Grava biblia.json e biblia.md."""
    from contos.llm.cliente import LLMFalhou, abrir_cliente

    pasta = config.pasta_do_canal(canal_id)
    cfg = config.carregar("biblia")
    agregado = agregar(canal_id)
    amostra = amostra_de_fichas(canal_id,
                                int(cfg.get("fichas_no_prompt") or 12))
    secoes_pedidas = cfg.get("secoes") or []
    timeout = float(cfg.get("resposta_timeout_s") or 900)
    conversa = pasta / "conversa" / "biblia"
    conversa.mkdir(parents=True, exist_ok=True)

    log(f"[biblia] {agregado['total_fichas']} ficha(s), "
        f"{agregado['numeros'].get('medidos', 0)} video(s) medido(s).")
    analise._diario("inicio", f"biblia de {canal_id} por {provedor}", canal_id)

    try:
        with abrir_cliente(provedor, headless=headless, log=log) as cliente:
            cliente.abrir(novo_chat=True)
            log("[biblia] etapa 1: o esqueleto (as apostas do canal)...")
            resposta = cliente.perguntar(
                prompt_esqueleto(agregado, amostra, cfg), timeout=timeout)
            (conversa / "esqueleto.txt").write_text(resposta, encoding="utf-8")
            esqueleto = parse_esqueleto(resposta)

            problemas = problemas_do_esqueleto(esqueleto)
            if problemas:
                log(f"[biblia] esqueleto incompleto ({problemas[0]}); "
                    "repergunto uma vez.")
                lista = "\n".join(f"  - {p}" for p in problemas)
                resposta = cliente.perguntar(
                    "O esqueleto veio incompleto. Devolva-o inteiro, no mesmo "
                    "formato, corrigindo:\n" + lista, timeout=timeout)
                (conversa / "esqueleto_conserto.txt").write_text(
                    resposta, encoding="utf-8")
                candidato = parse_esqueleto(resposta)
                if not problemas_do_esqueleto(candidato):
                    esqueleto = candidato
                problemas = problemas_do_esqueleto(esqueleto)
            if problemas:
                raise NaoEscreveu(
                    "o esqueleto da biblia nao saiu utilizavel: "
                    + "; ".join(problemas)
                    + f".\n  A resposta crua esta em {conversa}.")
            log(f"[biblia] esqueleto: {len(esqueleto['apostas'])} aposta(s). "
                f"{esqueleto['frase'][:80]}")

            escritas = {}
            for ordem, secao in enumerate(secoes_pedidas, 1):
                log(f"[biblia] etapa 2: {ordem}/{len(secoes_pedidas)} "
                    f"{secao['titulo']}")
                texto = cliente.perguntar(
                    prompt_secao(secao, esqueleto, ordem, len(secoes_pedidas)),
                    timeout=timeout)
                (conversa / f"secao_{secao['chave']}.txt").write_text(
                    texto, encoding="utf-8")
                escritas[secao["chave"]] = texto.strip()
    except LLMFalhou as exc:
        analise._diario("erro", f"biblia de {canal_id}: {exc}", canal_id)
        raise NaoEscreveu(str(exc)) from exc

    biblia = {
        "canal_id": canal_id,
        "canal": agregado["canal"],
        "provedor": provedor,
        "escrita_em": date.today().isoformat(),
        "total_fichas": agregado["total_fichas"],
        "fichas_por_provedor": agregado["fichas_por_provedor"],
        "esqueleto": esqueleto,
        "secoes": escritas,
        "agregado": agregado,
    }
    problemas = problemas_da_biblia(biblia, cfg)
    biblia["problemas"] = problemas

    (pasta / "biblia.json").write_text(
        json.dumps(biblia, ensure_ascii=False, indent=2), encoding="utf-8")
    (pasta / "biblia.md").write_text(para_markdown(biblia), encoding="utf-8")
    estado.marcar(pasta, "biblia", secoes=len(escritas),
                  problemas=len(problemas), provedor=provedor)
    analise._diario("ok", f"biblia de {canal_id}: {len(escritas)} secoes",
                    canal_id)

    log(f"\n[biblia] {len(escritas)} secao(oes) escritas.")
    if problemas:
        log(f"[biblia] {len(problemas)} pendencia(s):")
        for problema in problemas[:6]:
            log(f"    ! {problema}")
    log(f"[biblia] {pasta / 'biblia.md'}")
    return {"secoes": len(escritas), "problemas": problemas,
            "caminho": str(pasta / "biblia.md")}


def carregar(canal_id: str) -> dict:
    """A biblia gravada daquele canal."""
    pasta = config.pasta_do_canal(canal_id)
    caminho = pasta / "biblia.json"
    if not caminho.is_file():
        raise NaoEscreveu(
            f"nao ha biblia em {canal_id}. "
            f"Rode antes: python main.py biblia {canal_id}")
    return json.loads(caminho.read_text(encoding="utf-8-sig"))
