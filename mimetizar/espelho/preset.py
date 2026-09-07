# -*- coding: utf-8 -*-
"""Etapa 5: a biblia vira config que o `historias/` sabe ler — e o diagnostico.

A biblia responde "como esse canal e feito". O preset responde a pergunta
seguinte, que e a que interessa: "o que eu precisaria para fazer igual".

Sai em cinco arquivos:

  roteiro.json      no formato de `historias/config/roteiro.json`
  modelo.txt        no formato de `historias/modelos/*.txt`
  imagens.json      o `estilo` derivado da paleta MEDIDA do canal
  publicacao.json   a cadencia observada nas datas do catalogo
  lacunas.md        o diagnostico: o que a stack ja faz, e o que falta

Nada e copiado por cima da configuracao de producao. O preset fica na pasta
do canal e a copia e um ato humano — sobrescrever `historias/config/` sem
alguem olhar seria trocar o formato de um canal que ja funciona pelo formato
de outro, em silencio.

O diagnostico de lacuna e CODIGO, comparado contra `config/capacidades.json`.
Perguntar a um LLM "o que falta na stack dele" produziria uma lista plausivel
e errada — ele nao conhece este repositorio. A lista de capacidades conhece,
e quando ela envelhecer, envelhece num arquivo que da para editar.
"""
from __future__ import annotations

import json
import re
import unicodedata

from . import analise
from . import biblia as _biblia
from . import config, estado

# Cenas mais curtas que isto ninguem le; mais longas que isto entedia. Sao os
# mesmos limites que o `historias/` ja usa no render.
CENA_MIN_S, CENA_MAX_S = 3.0, 8.0


class NaoGerou(RuntimeError):
    """Erro humano: o que se tentou, e o que fazer."""


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto))
                   if unicodedata.category(c) != "Mn")


def _palavras(texto: str) -> set:
    return set(_sem_acento(texto).lower().replace("-", " ").split())


# ------------------------------------------------------- diagnostico
def classificar(item: str, capacidades: dict) -> dict:
    """Onde este item cai: ja da, da com trabalho, ou exige uma pessoa."""
    palavras = _palavras(item)
    for sinal in capacidades.get("exige_pessoa") or []:
        if _palavras(sinal) <= palavras:
            return {"item": item, "onde": "pessoa", "motivo": sinal}
    for capacidade in capacidades.get("capacidades") or []:
        for chave in capacidade.get("palavras") or []:
            if _palavras(chave) <= palavras:
                return {"item": item, "onde": "pronto",
                        "capacidade": capacidade["nome"],
                        "modulo": capacidade["onde"]}
    return {"item": item, "onde": "construir"}


def mapear_lacunas(agregado: dict, capacidades: dict | None = None) -> dict:
    """As tres listas do diagnostico, a partir do que as fichas apontaram."""
    capacidades = capacidades or config.carregar("capacidades")
    vistos, pronto, construir, pessoa = set(), [], [], []
    fontes = (("ja_automatizavel", agregado.get("ja_automatizavel") or []),
              ("dificil", agregado.get("dificil") or []),
              ("exige_pessoa", agregado.get("exige_pessoa") or []))
    for origem, itens in fontes:
        for entrada in itens:
            texto = str(entrada.get("valor") if isinstance(entrada, dict)
                        else entrada).strip()
            marca = _sem_acento(texto).lower()[:60]
            if not texto or marca in vistos:
                continue
            vistos.add(marca)
            achado = classificar(texto, capacidades)
            achado["vezes"] = (entrada.get("vezes")
                               if isinstance(entrada, dict) else 1)
            # A ficha dizendo "exige pessoa" pesa mais que a palavra-chave:
            # quem viu o video sabe se o rosto e essencial.
            if origem == "exige_pessoa" and achado["onde"] != "pessoa":
                achado = {**achado, "onde": "pessoa",
                          "motivo": "as fichas classificaram como humano"}
            {"pronto": pronto, "construir": construir,
             "pessoa": pessoa}[achado["onde"]].append(achado)
    return {"pronto": pronto, "construir": construir, "pessoa": pessoa,
            "capacidades": [c["nome"] for c in
                            capacidades.get("capacidades") or []]}


def lacunas_md(canal_nome: str, mapa: dict, numeros: dict) -> str:
    """O diagnostico, para ler."""
    linhas = [f"# O que falta para fazer um canal como {canal_nome}", "",
              "Cruzamento entre o que as fichas apontaram e o que esta stack "
              "já faz hoje (`mimetizar/config/capacidades.json`).", ""]

    linhas += ["## Dá para automatizar já", ""]
    if mapa["pronto"]:
        linhas.append("| o que o canal faz | com o quê, aqui |")
        linhas.append("|---|---|")
        for achado in mapa["pronto"]:
            linhas.append(f"| {achado['item']} | **{achado['capacidade']}** "
                          f"— `{achado['modulo']}` |")
    else:
        linhas.append("_Nada do que as fichas apontaram casou com uma "
                      "capacidade existente. Vale reler `capacidades.json`._")
    linhas.append("")

    linhas += ["## Dá, mas precisa ser construído", ""]
    if mapa["construir"]:
        for achado in mapa["construir"]:
            vezes = achado.get("vezes", 1)
            marca = f" _(apontado em {vezes} fichas)_" if vezes > 1 else ""
            linhas.append(f"- {achado['item']}{marca}")
    else:
        linhas.append("_Nada. O formato cabe no que já existe._")
    linhas.append("")

    linhas += ["## Exige uma pessoa", "",
               "Isto não é lacuna de software. Um canal que finge ter estas "
               "coisas soa falso, e o espectador percebe antes de saber "
               "explicar o quê.", ""]
    if mapa["pessoa"]:
        for achado in mapa["pessoa"]:
            linhas.append(f"- {achado['item']} "
                          f"_({achado.get('motivo', 'humano')})_")
    else:
        linhas.append("_Nada — o formato deste canal é reproduzível sem "
                      "rosto nem voz própria._")
    linhas.append("")

    if numeros.get("medidos"):
        linhas += ["## O alvo, em números", "",
                   "Para soar como este canal, o vídeo precisa acertar:", "",
                   f"- **duração**: ~{(numeros.get('duracao_mediana_s') or 0) / 60:.1f} min",
                   f"- **ritmo de corte**: ~{numeros.get('cortes_por_min_mediana')} por minuto "
                   f"(plano médio de {numeros.get('plano_medio_s')}s)",
                   f"- **loudness**: {numeros.get('lufs_mediana')} LUFS",
                   f"- **proporção de fala**: {numeros.get('fala_pct_mediana')}%",
                   f"- **formato**: "
                   f"{'vertical' if (numeros.get('verticais') or 0) > (numeros.get('horizontais') or 0) else 'horizontal'}",
                   "",
                   f"Medido em {numeros['medidos']} vídeo(s) do canal.", ""]
    return "\n".join(linhas)


# ------------------------------------------------------------ o prompt
def prompt_preset(biblia_dados: dict, numeros: dict) -> str:
    """Um turno: a formula vira estrutura executavel, a voz vira regras."""
    esqueleto = biblia_dados.get("esqueleto") or {}
    secoes = biblia_dados.get("secoes") or {}
    duracao = numeros.get("duracao_mediana_s") or 60
    cenas = _cenas_alvo(numeros)

    linhas = []
    add = linhas.append
    add("Ultima etapa: transformar a biblia em CONFIGURACAO EXECUTAVEL.")
    add("")
    add(f"Formula que voce definiu: {esqueleto.get('formula', '')}")
    add(f"Publico: {esqueleto.get('publico', '')}")
    add("")
    add("Secao VOZ que voce escreveu:")
    add(str(secoes.get("voz", ""))[:2500])
    add("")
    add("Secao EDICAO que voce escreveu:")
    add(str(secoes.get("edicao", ""))[:1800])
    add("")
    add(f"ALVO MEDIDO: video de ~{duracao / 60:.1f} minutos, dividido em "
        f"cerca de {cenas} cenas de {CENA_MIN_S:.0f} a {CENA_MAX_S:.0f} "
        "segundos cada.")
    add("")
    add("Responda EXATAMENTE nestes quatro blocos, sem nada em volta:")
    add("")
    add("ESTRUTURA")
    add(f"<uma linha por bloco do video, somando ~{cenas} cenas. Formato:")
    add(" NOME DO BLOCO (N cenas): o que entra nele, em uma frase imperativa.")
    add(" Entre 4 e 8 blocos. As cenas somadas tem que dar aproximadamente "
        f"{cenas}.>")
    add("")
    add("NARRACAO")
    add("<entre 8 e 14 regras de escrita, uma por linha comecando com '- '. "
        "Regras ACIONAVEIS, do tipo que da para obedecer ou desobedecer: "
        "'frases de no maximo 12 palavras', nao 'seja envolvente'. "
        "Elas descrevem COMO escrever no formato deste canal — nunca o "
        "assunto de nenhum video especifico dele.>")
    add("")
    add("IMAGEM")
    add("<uma frase densa EM INGLES descrevendo o visual, coerente com a "
        "paleta medida (brilho "
        f"{numeros.get('brilho_mediano')}, saturacao "
        f"{numeros.get('saturacao_mediana')}). Termos de fotografia e "
        "iluminacao, separados por virgula. Sem nome de marca, sem nome de "
        "pessoa, sem nome do canal.>")
    add("")
    add("NEGATIVO")
    add("<uma frase em ingles com o que NAO deve aparecer nas imagens.>")
    return "\n".join(linhas)


def _cenas_alvo(numeros: dict) -> int:
    duracao = float(numeros.get("duracao_mediana_s") or 60)
    plano = float(numeros.get("plano_medio_s") or 5) or 5.0
    # O plano medido e de CAMERA; uma cena de imagem gerada aguenta mais que
    # um plano de corte. Usa-se o plano como piso, dentro dos limites.
    por_cena = min(max(plano, CENA_MIN_S), CENA_MAX_S)
    return max(4, min(40, round(duracao / por_cena)))


_BLOCOS = ("estrutura", "narracao", "imagem", "negativo")


def parse_preset(texto: str) -> dict:
    """Os quatro blocos da resposta. Tolerante a rotulo com acento e markdown."""
    atual, colhido = None, {chave: [] for chave in _BLOCOS}
    for bruta in str(texto or "").splitlines():
        linha = re.sub(r"^#{1,4}\s*", "", str(bruta).replace("**", "")).strip()
        marca = _sem_acento(linha).strip().lower().rstrip(":")
        if marca in _BLOCOS:
            atual = marca
            continue
        if atual and linha:
            colhido[atual].append(linha)

    estrutura = [re.sub(r"^\s*[-*+]\s+", "", linha).strip()
                 for linha in colhido["estrutura"] if ":" in linha]
    narracao = [re.sub(r"^\s*[-*+]\s+", "", linha).strip()
                for linha in colhido["narracao"]]
    return {
        "estrutura": [linha for linha in estrutura if linha],
        "narracao": [linha for linha in narracao if len(linha) > 8],
        "imagem": " ".join(colhido["imagem"]).strip(),
        "negativo": " ".join(colhido["negativo"]).strip(),
        "bruto": str(texto or ""),
    }


def problemas_do_preset(lido: dict) -> list:
    faltando = []
    if len(lido.get("estrutura") or []) < 3:
        faltando.append(f"a ESTRUTURA veio com "
                        f"{len(lido.get('estrutura') or [])} bloco(s); "
                        "precisa de pelo menos 3, no formato "
                        "'NOME (N cenas): o que entra'")
    if len(lido.get("narracao") or []) < 6:
        faltando.append(f"so {len(lido.get('narracao') or [])} regra(s) de "
                        "NARRACAO; precisa de pelo menos 6")
    if len(lido.get("imagem") or "") < 30:
        faltando.append("a frase de IMAGEM veio curta demais (ou vazia)")
    return faltando


def _cenas_da_estrutura(estrutura: list) -> int:
    total = 0
    for linha in estrutura:
        achado = re.search(r"\((\d+)\s*cena", _sem_acento(linha).lower())
        if achado:
            total += int(achado.group(1))
    return total


# -------------------------------------------------------- os arquivos
def _slug(nome: str) -> str:
    limpo = re.sub(r"[^a-z0-9]+", "_", _sem_acento(nome).lower()).strip("_")
    return limpo[:24] or "canal"


def montar_roteiro_json(canal_nome: str, lido: dict, numeros: dict) -> dict:
    """No formato de `historias/config/roteiro.json`."""
    chave = _slug(canal_nome)
    cenas = _cenas_da_estrutura(lido["estrutura"]) or _cenas_alvo(numeros)
    duracao = int(numeros.get("duracao_mediana_s") or cenas * 5)
    return {
        "_comment": (f"Gerado por `mimetizar` a partir do canal {canal_nome}. "
                     "Copie para historias/config/roteiro.json (ou junte os "
                     "modelos) DEPOIS de ler — isto substitui o formato de um "
                     "canal que ja funciona."),
        "modelo_padrao": chave,
        "modelos": {
            chave: {
                "rotulo": f"{canal_nome} (formato absorvido)",
                "duracao_alvo": duracao,
                "cenas_alvo": cenas,
                "estrutura": lido["estrutura"],
            }
        },
        "regras": {
            "narracao": lido["narracao"],
            "imagem": [
                "Escreva o prompt de imagem em INGLES, uma frase densa, sem lista.",
                "Repita a descricao fisica do protagonista em toda cena.",
                "Nada de texto dentro da imagem.",
            ],
            "tempo": [
                f"`TEMPO` e uma estimativa em segundos do tempo de tela da "
                f"cena ({CENA_MIN_S:.0f} a {CENA_MAX_S:.0f}).",
                f"A soma dos tempos deve ficar perto de {duracao} segundos.",
            ],
        },
        "limites": {
            "cenas_min": max(4, cenas // 2),
            "cenas_max": min(40, cenas * 2),
            "titulo_max_chars": 110,
            "narracao_max_chars": 220,
            "imagem_min_chars": 25,
        },
    }


def gerar(canal_id: str, *, provedor: str = "chatgpt", headless: bool = False,
          log=print) -> dict:
    """A biblia -> preset + diagnostico. Grava em `preset/`."""
    from contos.llm.cliente import LLMFalhou, abrir_cliente

    pasta = config.pasta_do_canal(canal_id)
    dados = _biblia.carregar(canal_id)
    agregado = dados.get("agregado") or {}
    numeros = agregado.get("numeros") or {}
    canal_nome = (dados.get("canal") or {}).get("nome") or canal_id
    destino = pasta / "preset"
    destino.mkdir(parents=True, exist_ok=True)

    log(f"[preset] a partir da biblia de {canal_nome}.")
    try:
        with abrir_cliente(provedor, headless=headless, log=log) as cliente:
            cliente.abrir(novo_chat=True)
            resposta = cliente.perguntar(prompt_preset(dados, numeros),
                                         timeout=900)
            (pasta / "conversa" / "biblia" / "preset.txt").write_text(
                resposta, encoding="utf-8")
            lido = parse_preset(resposta)
            problemas = problemas_do_preset(lido)
            if problemas:
                log(f"[preset] resposta incompleta ({problemas[0]}); "
                    "repergunto uma vez.")
                lista = "\n".join(f"  - {p}" for p in problemas)
                resposta = cliente.perguntar(
                    "Faltou isto. Devolva os QUATRO blocos inteiros de novo, "
                    "corrigindo:\n" + lista, timeout=900)
                (pasta / "conversa" / "biblia" / "preset_conserto.txt"
                 ).write_text(resposta, encoding="utf-8")
                candidato = parse_preset(resposta)
                if not problemas_do_preset(candidato):
                    lido = candidato
                problemas = problemas_do_preset(lido)
    except LLMFalhou as exc:
        raise NaoGerou(str(exc)) from exc

    if problemas:
        raise NaoGerou(
            "o preset nao saiu utilizavel: " + "; ".join(problemas)
            + f".\n  A resposta crua esta em "
              f"{pasta / 'conversa' / 'biblia' / 'preset.txt'}.")

    roteiro = montar_roteiro_json(canal_nome, lido, numeros)
    (destino / "roteiro.json").write_text(
        json.dumps(roteiro, ensure_ascii=False, indent=2), encoding="utf-8")
    (destino / "modelo.txt").write_text("\n".join(lido["estrutura"]) + "\n",
                                        encoding="utf-8")
    (destino / "imagens.json").write_text(json.dumps({
        "_comment": f"Estilo visual derivado da paleta medida de {canal_nome}.",
        "estilo": lido["imagem"],
        "negativo": lido["negativo"] or "text, watermark, logo, blurry",
        "_medido": {k: numeros.get(k) for k in
                    ("brilho_mediano", "saturacao_mediana", "verticais",
                     "horizontais")},
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    cadencia = agregado.get("cadencia") or {}
    (destino / "publicacao.json").write_text(json.dumps({
        "_comment": f"Cadencia observada em {canal_nome}, lida das datas do "
                    "catalogo.",
        "videos_por_semana": cadencia.get("por_semana"),
        "intervalo_medio_dias": cadencia.get("intervalo_medio_dias"),
        "intervalo_h": round(float(cadencia.get("intervalo_medio_dias") or 1)
                             * 24, 1),
        "observado_de": cadencia.get("primeiro"),
        "observado_ate": cadencia.get("ultimo"),
        "ultimos_meses": cadencia.get("ultimos_meses"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    mapa = mapear_lacunas(agregado)
    (destino / "lacunas.md").write_text(
        lacunas_md(canal_nome, mapa, numeros), encoding="utf-8")

    estado.marcar(pasta, "preset", cenas=roteiro["modelos"][
        list(roteiro["modelos"])[0]]["cenas_alvo"],
        pronto=len(mapa["pronto"]), construir=len(mapa["construir"]),
        pessoa=len(mapa["pessoa"]))
    analise._diario("ok", f"preset de {canal_id}", canal_id)

    log(f"\n[preset] {len(lido['estrutura'])} bloco(s), "
        f"{len(lido['narracao'])} regra(s) de narracao")
    log(f"[preset] lacunas: {len(mapa['pronto'])} ja da, "
        f"{len(mapa['construir'])} a construir, "
        f"{len(mapa['pessoa'])} exigem uma pessoa")
    log(f"[preset] {destino}")
    return {"pasta": str(destino), "estrutura": len(lido["estrutura"]),
            "narracao": len(lido["narracao"]), "lacunas": mapa}
