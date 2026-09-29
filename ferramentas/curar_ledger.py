# -*- coding: utf-8 -*-
"""Cura do ledger de publicacoes — passo 2 do contrato do campo `url`.

    python ferramentas/curar_ledger.py                 # A SECO: so relata
    python ferramentas/curar_ledger.py --gravar        # aplica (com copia)

Por que existe (16/09/2026): o `url` do ledger guardava tres coisas — o
link, a frase de estado e, no TikTok, sempre a frase —, e a frase contava
como "saiu". Com isso, 40 linhas do Neural Fights diziam "publicado" para
videos privados (20 deles nunca foram ao ar, e a fila os pula para sempre),
12 linhas de YouTube tinham frase no lugar do link, e cinco ids apareciam em
mais de uma linha. O passo 1 (`metricas.publicado`) fez os leitores
perguntarem a mesma coisa; este passo corrige as RESPOSTAS gravadas.

A SECO E O PADRAO, e nao por timidez: as curas mudam o que a fila considera
publicado — video volta a ser elegivel, video some da conta. Isso e decisao
do Adrian. Sem `--gravar` nada no ledger muda; o relatorio diz, linha por
linha, o que MUDARIA (antes -> depois), com o grau de certeza.

Com `--gravar`: copia o ledger ao lado (`.antes-cura-<carimbo>`) e so entao
reescreve. Cura "a conferir" NUNCA e aplicada; ela so aparece no relatorio.

O nucleo (`calcular_curas`) e puro: recebe as linhas e a lista do canal e
devolve as curas. So `buscar_canal` toca a rede.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "outputs" / "_cura"

from builds.publicar import metricas, titulos                  # noqa: E402

ALTA, MEDIA, A_CONFERIR = "alta", "media", "a_conferir"
FOLGA_ALTA = timedelta(minutes=2)
PEDACO = re.compile(r"\s*\((\d+) de (\d+)\)\s*$")
PRIVADO = ("private", "privado")
ESTADOS_JA_DECIDIDOS = ("rascunho", "privado_de_proposito")


def _linha(texto: str = "") -> None:
    sys.stdout.buffer.write((texto + "\n").encode("utf-8", "replace"))


# --------------------------------------------------------------- nucleo puro
def _link(youtube_id: str) -> str:
    return f"https://youtu.be/{youtube_id}"


def _e_link(url) -> bool:
    return str(url or "").startswith("http")


def _referencia(linha: dict):
    return (metricas._instante(linha.get("agendado_para"))
            or metricas._instante(linha.get("quando")))


def _distancia(linha: dict, video: dict):
    ref, no_ar = _referencia(linha), metricas._instante(video.get("publicado_em"))
    if ref is None or no_ar is None:
        return None
    return abs(no_ar - ref)


def _cura(indice, linha, tipo, certeza, depois, motivo) -> dict:
    campos = sorted(set(depois))
    return {"linha": indice, "tipo": tipo, "certeza": certeza,
            "video_id": linha.get("video_id"), "quando": linha.get("quando"),
            "plataforma": linha.get("plataforma") or "youtube",
            "antes": {c: linha.get(c) for c in campos},
            "depois": depois, "motivo": motivo}


def calcular_curas(linhas: list, videos: list, canal: str = "builds",
                   privadas=()) -> list:
    """As curas de UM canal. Uma linha recebe no maximo uma cura de conteudo.

    Ordem das regras, e ela importa:
      1. ID REPETIDO: dono e a linha mais proxima da hora do video; as outras
         perdem o id (o caso A/B de generation_00081). Sem o video na lista do
         canal nao ha hora para comparar, e a escolha seria arbitraria: "a
         conferir".
      2. FRASE NO URL: um video (titulo e hora) ou todos os pedacos
         "(k de N)" viram link. Vem ANTES do gemeo porque casa pela hora exata
         e reserva o id: a ordem inversa deixava um rascunho tomar o video do
         dono verdadeiro.
      3. VIDEO PRIVADO: sem gemeo, a linha deixa de contar como publicada.
         Gemeo so conta se for ao ar DEPOIS do rascunho, dentro de uma
         semana, e (nas historias) da mesma parte. Medido em 16/09/2026: 11
         dos 12 "gemeos" achados so pelo titulo tinham ido ao ar ~17 dias
         ANTES da linha — eram videos antigos de builds refeitas, com o mesmo
         personagem, classe e nota.
      4. FORMATO: toda linha que sobrar ganha `publicado` explicito, e a
         frase sai do `url` para `estado_texto` (inclui o TikTok, que nunca
         teve link).
    """
    privadas = set(privadas or ())
    # UM video por id. A lista de uploads do canal traz o mesmo video mais de
    # uma vez (medido em 16/09/2026: `U7n1dgQCidA` duas vezes), e sem isto um
    # gemeo unico virava "dois gemeos" e a cura caia em "a conferir".
    unicos: dict = {}
    for v in videos or ():
        if isinstance(v, dict) and v.get("youtube_id"):
            unicos.setdefault(v["youtube_id"], v)
    videos = list(unicos.values())
    por_id = unicos
    curas: list = []
    tocadas: set = set()
    donos = {str(L.get("youtube_id")) for L in linhas
             if isinstance(L, dict) and L.get("youtube_id")}

    def youtube(L):
        return isinstance(L, dict) and (L.get("plataforma") or "youtube") == "youtube"

    # 1. id repetido
    grupos: dict = {}
    for i, L in enumerate(linhas):
        if youtube(L) and L.get("youtube_id"):
            grupos.setdefault(L["youtube_id"], []).append(i)
    for vid, indices in grupos.items():
        if len(indices) < 2:
            continue
        video = por_id.get(vid)
        distancias = {i: (_distancia(linhas[i], video) if video else None)
                      for i in indices}
        if any(d is None for d in distancias.values()):
            # Video fora da lista do canal (a paginacao para em ~200, ou ele
            # foi apagado): sem hora, "o mais proximo" seria sorteio.
            for i in indices:
                curas.append(_cura(
                    i, linhas[i], "id_repetido_sem_video", A_CONFERIR, {},
                    f"o id {vid} esta em {len(indices)} linhas e o video nao "
                    "esta na lista do canal para desempatar"))
                tocadas.add(i)
            continue
        dono = min(indices, key=lambda i: distancias[i])
        for i in indices:
            if i == dono:
                continue
            curas.append(_cura(
                i, linhas[i], "id_repetido", MEDIA,
                {"youtube_id": None, "url": "", "publicado_em": None,
                 "publicado": False, "estado": "nao_confirmado"},
                f"o id {vid} pertence a linha {dono} (mais proxima da hora "
                "do video); esta linha nao tem video proprio no canal"))
            tocadas.add(i)

    # 2. frase no url
    pares = dict(metricas.casar_ids(linhas, videos))
    for i, L in enumerate(linhas):
        if i in tocadas or not youtube(L) or _e_link(L.get("url")):
            continue
        if not L.get("url") or L.get("youtube_id"):
            continue
        video = pares.get(i)
        if video is not None:
            d = _distancia(L, video)
            curas.append(_cura(
                i, L, "link_de_frase",
                ALTA if d is not None and d <= FOLGA_ALTA else MEDIA,
                {"youtube_id": video["youtube_id"],
                 "url": _link(video["youtube_id"]),
                 "publicado_em": video.get("publicado_em"),
                 "publicado": True, "estado": "publicado",
                 "estado_texto": L.get("url")},
                f"titulo igual, no ar a {int(d.total_seconds()) if d else '?'} s "
                "da linha"))
            donos.add(video["youtube_id"])
            tocadas.add(i)
            continue
        pedacos = _pedacos(L, videos, donos)
        if pedacos:
            ids = [v["youtube_id"] for v in pedacos]
            donos.update(ids)
            curas.append(_cura(
                i, L, "link_de_pedacos", ALTA,
                {"youtube_id": ids[0], "youtube_ids": ids,
                 "url": _link(ids[0]),
                 "publicado_em": pedacos[0].get("publicado_em"),
                 "publicado": True, "estado": "publicado",
                 "estado_texto": L.get("url")},
                f"{len(ids)} pedacos \"(k de {len(ids)})\" com o titulo da "
                "parte, no ar a menos de 2 min da linha"))
            tocadas.add(i)

    # 3. video privado
    publicos = [v for v in videos
                if str(v.get("privacidade") or "").lower() == "public"]
    for i, L in enumerate(linhas):
        if i in tocadas or not youtube(L):
            continue
        if L.get("estado") == "privado_de_proposito":
            continue
        video = por_id.get(str(L.get("youtube_id") or ""))
        if not video or str(video.get("privacidade") or "").lower() not in PRIVADO:
            continue
        if L.get("video_id") in privadas:
            # DECISAO DE UMA PESSOA, passada pelo nome: a parte fica privada e
            # a fila nunca a republica (`publicado` continua verdadeiro). Vale
            # tambem para a linha que uma cura anterior ja chamou de rascunho:
            # a decisao chegou depois e manda — ignorar em silencio deixaria a
            # fila republicar o que ele quis privado.
            depois = {"publicado": True, "estado": "privado_de_proposito"}
            if not _e_link(L.get("url")):
                depois["url"] = _link(video["youtube_id"])
            curas.append(_cura(
                i, L, "privado_de_proposito", ALTA, depois,
                f"{video['youtube_id']} esta privado por decisao do Adrian"
                + (" (a linha estava como rascunho)"
                   if L.get("estado") == "rascunho" else "")))
            tocadas.add(i)
            continue
        if L.get("estado") in ESTADOS_JA_DECIDIDOS:
            # Ja curada: o video continua privado, e e isso mesmo. Sem esta
            # saida, cada rodada "curaria" a mesma linha de novo.
            continue
        homonimos = [v for v in publicos if _mesmo_titulo(v, video, canal)
                     and v["youtube_id"] not in donos]
        gemeos = [v for v in homonimos if _depois_do_rascunho(L, v)]
        if canal == "historias" and not gemeos:
            curas.append(_cura(
                i, L, "historia_privada", A_CONFERIR, {},
                f"{video['youtube_id']} esta privado e nao ha publico da "
                "mesma parte depois dele; pode ter sido privado de proposito"))
        elif not gemeos:
            antigos = [v["youtube_id"] for v in homonimos]
            # O `url` e esvaziado: link de rascunho no campo de "saiu" deixava
            # `url` e `publicado` discordando para qualquer leitor que ainda
            # olhe o `url`. O id do rascunho fica em `rascunho_id`.
            curas.append(_cura(
                i, L, "rascunho_sem_gemeo", MEDIA,
                {"publicado": False, "estado": "rascunho", "url": "",
                 "rascunho_id": video["youtube_id"]},
                f"{video['youtube_id']} esta privado e nenhum video publico "
                "de mesmo titulo foi ao ar depois dele"
                + (f" (ha homonimos ANTERIORES, que sao outros videos: "
                   f"{', '.join(antigos[:3])})" if antigos else "")))
        elif len(gemeos) > 1:
            curas.append(_cura(
                i, L, "rascunho_gemeo_ambiguo", A_CONFERIR, {},
                f"{video['youtube_id']} esta privado e ha {len(gemeos)} "
                "publicos de mesmo titulo depois dele: "
                + ", ".join(g["youtube_id"] for g in gemeos)))
        else:
            gemeo = gemeos[0]
            donos.add(gemeo["youtube_id"])
            curas.append(_cura(
                i, L, "rascunho_com_gemeo", MEDIA,
                {"youtube_id": gemeo["youtube_id"],
                 "url": _link(gemeo["youtube_id"]),
                 "publicado_em": gemeo.get("publicado_em"),
                 "publicado": True, "estado": "publicado",
                 "rascunho_id": video["youtube_id"]},
                f"{video['youtube_id']} esta privado; o publico de mesmo "
                f"titulo que foi ao ar depois dele e {gemeo['youtube_id']}"))
        tocadas.add(i)

    # 4. formato
    for i, L in enumerate(linhas):
        if i in tocadas or not isinstance(L, dict) or "publicado" in L:
            continue
        url = L.get("url")
        depois = {"publicado": bool(url), "estado":
                  "publicado" if url else "nao_subiu"}
        if url and not _e_link(url):
            depois["url"] = ""
            depois["estado_texto"] = url
        curas.append(_cura(i, L, "formato", ALTA, depois,
                           "campo `publicado` explicito; frase fora do `url`"))
    return curas


# Quanto tempo DEPOIS do rascunho um reenvio ainda conta como o mesmo video.
JANELA_DO_GEMEO = timedelta(days=7)
PARTE = re.compile(r"\(Parte\s+(\d+)", re.IGNORECASE)


def _titulo_inteiro(texto) -> str:
    """A mesma normalizacao de `titulos.chave`, sem o corte em 60.

    O corte serve para reconciliar titulos que o Studio encurtou; aqui ele
    escondia a parte: "(Parte 3/6)" cai depois do caractere 60 em titulo
    longo, e duas partes diferentes viravam o mesmo titulo.
    """
    limpo = re.sub(r"\s+", " ", str(texto or "")).strip().lower()
    limpo = "".join(c for c in limpo if c.isalnum() or c.isspace())
    return re.sub(r"\s+", " ", limpo).strip()[:100]


def _mesmo_titulo(publico: dict, rascunho: dict, canal: str) -> bool:
    if _titulo_inteiro(publico.get("titulo")) != _titulo_inteiro(
            rascunho.get("titulo")):
        return False
    if canal == "historias":
        a = PARTE.search(str(publico.get("titulo") or ""))
        b = PARTE.search(str(rascunho.get("titulo") or ""))
        return bool(a and b and a.group(1) == b.group(1))
    return True


def _depois_do_rascunho(linha: dict, publico: dict) -> bool:
    """O publico foi ao ar depois do rascunho (com folga), e ate uma semana?"""
    ref = _referencia(linha)
    no_ar = metricas._instante(publico.get("publicado_em"))
    if ref is None or no_ar is None:
        return False
    return ref - FOLGA_ALTA <= no_ar <= ref + JANELA_DO_GEMEO


def _pedacos(linha: dict, videos: list, donos: set) -> list:
    """Os pedacos "(1 de N)".."(N de N)" desta parte, ou `[]`.

    So vale com TODOS os N pedacos achados, cada um a menos de 2 min da
    linha: meia parte nao e publicacao.
    """
    base = titulos.chave(linha.get("titulo"))
    if not base:
        return []
    achados: dict = {}
    total = None
    for v in videos:
        m = PEDACO.search(str(v.get("titulo") or ""))
        if not m or v["youtube_id"] in donos:
            continue
        if titulos.chave(PEDACO.sub("", v["titulo"])) != base:
            continue
        d = _distancia(linha, v)
        if d is None or d > FOLGA_ALTA:
            continue
        k, n = int(m.group(1)), int(m.group(2))
        total = total or n
        if n == total:
            achados.setdefault(k, v)
    if not total or sorted(achados) != list(range(1, total + 1)):
        return []
    return [achados[k] for k in range(1, total + 1)]


def aplicar(linhas: list, curas: list) -> list:
    """As linhas depois das curas aplicaveis. Nunca aplica "a conferir"."""
    novas = [dict(L) if isinstance(L, dict) else L for L in linhas]
    for cura in curas:
        if cura["certeza"] == A_CONFERIR:
            continue
        alvo = novas[cura["linha"]]
        alvo.update(cura["depois"])
        if cura["tipo"] != "formato":
            alvo.setdefault("cura", []).append(
                {"tipo": cura["tipo"], "certeza": cura["certeza"],
                 "antes": cura["antes"],
                 "quando": datetime.now().isoformat(timespec="seconds")})
    return novas


def resumo(curas: list) -> dict:
    contagem: dict = {}
    for c in curas:
        chave = f"{c['tipo']} ({c['certeza']})"
        contagem[chave] = contagem.get(chave, 0) + 1
    return dict(sorted(contagem.items()))


def privadas_sem_efeito(linhas: list, curas: list, privadas) -> list:
    """`[(video_id, motivo)]` dos `--privada-de-proposito` que nao pegaram.

    Um id digitado errado, ou de uma parte cujo video nao esta privado, nao
    pode sumir calado: a pessoa acha que decidiu, e a fila republica.
    """
    curadas = {c["video_id"] for c in curas
               if c["tipo"] == "privado_de_proposito"}
    saida = []
    for vid in dict.fromkeys(privadas or ()):
        if vid in curadas:
            continue
        dele = [L for L in linhas if isinstance(L, dict)
                and L.get("video_id") == vid
                and (L.get("plataforma") or "youtube") == "youtube"]
        if not dele:
            saida.append((vid, "nenhuma linha de YouTube com este video_id"))
        elif any(L.get("estado") == "privado_de_proposito" for L in dele):
            continue
        else:
            saida.append((vid, "o video desta linha nao esta privado no canal "
                               "(ou nao esta na lista do canal)"))
    return saida


# ------------------------------------------------------------------- casca
def buscar_canal(canal: str) -> list:
    """A UNICA funcao com rede: uploads do canal com privacidade e data."""
    token, _ = metricas._token(canal)
    enviados = metricas.enviados(token)
    detalhes = metricas.estatisticas([v["youtube_id"] for v in enviados], token)
    return [{**v, **detalhes.get(v["youtube_id"], {})} for v in enviados]


def ler_bruto(caminho: Path) -> bytes:
    try:
        return caminho.read_bytes()
    except FileNotFoundError:
        return b""


def ler(caminho: Path, bruto: bytes | None = None) -> list:
    texto = (caminho.read_bytes() if bruto is None else bruto).decode("utf-8")
    linhas = []
    for linha in texto.splitlines():
        if linha.strip():
            linhas.append(json.loads(linha))
    return linhas


# ------------------------------------------------------- pre-condicao (B1)
POSTAR = RAIZ / "ferramentas" / "postar.py"
CONTRATO_MINIMO = 2
# Nomes do postar.py cujo `.get("url")` NAO e de linha do ledger: `r` e o
# resultado de uma postagem (aviso e ficha). Qualquer outro nome conta.
NAO_E_LEDGER = frozenset({"r"})
# Uma linha como a cura a deixa: TikTok, frase fora do `url`.
SONDA = "__sonda_da_cura__"


def _linha_curada() -> dict:
    return {"video_id": SONDA, "plataforma": "tiktok", "url": "",
            "estado_texto": "publicado no TikTok", "publicado": True,
            "estado": "publicado", "quando": "2026-09-16T00:00:00"}


def leituras_por_url(fonte: str) -> list:
    """Linhas onde `<nome>.get("url")` decide alguma coisa (teste de verdade).

    Pela arvore do codigo, nao por texto: pega `if`, `and`/`or`, `not`,
    filtro de compreensao e ternario, com qualquer nome de variavel e em
    qualquer formatacao. A regex anterior so via `l`/`linha` depois de
    `if|and|or|not` na mesma linha.
    """
    import ast

    def e_leitura(no) -> bool:
        return (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
                and no.func.attr == "get" and no.args
                and isinstance(no.args[0], ast.Constant)
                and no.args[0].value == "url"
                and not (isinstance(no.func.value, ast.Name)
                         and no.func.value.id in NAO_E_LEDGER))

    testes = []
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, (ast.If, ast.While, ast.IfExp, ast.Assert)):
            testes.append(no.test)
        elif isinstance(no, ast.comprehension):
            testes.extend(no.ifs)
        elif isinstance(no, ast.BoolOp):
            if (isinstance(no.op, ast.Or)
                    and isinstance(no.values[-1], ast.Constant)):
                continue          # `x.get("url") or ""` e valor padrao
            testes.extend(no.values)
        elif isinstance(no, ast.UnaryOp) and isinstance(no.op, ast.Not):
            testes.append(no.operand)
        elif (isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
              and no.func.id in ("bool", "any", "all", "filter")):
            testes.extend(no.args)
    achadas = set()
    for teste in testes:
        for no in ast.walk(teste):
            if e_leitura(no):
                achadas.add(no.lineno)
    return sorted(achadas)


def leitores_entendem_a_cura() -> str:
    """`""` se os leitores de verdade veem a linha curada como publicada.

    Carrega o postar.py (sem rodar o `main`) e pergunta as duas guardas de
    "ja esta no TikTok" com uma linha curada no lugar do ledger. Qualquer
    excecao conta como "nao entendem": a guarda do postar engole erro e
    devolve False, e e exatamente o False que repostaria.
    """
    import importlib.util

    from contos.publicar import serie

    linha = _linha_curada()
    reais = (metricas.publicados, serie.publicados)
    metricas.publicados = lambda canal="builds": [dict(linha)]
    serie.publicados = lambda: [dict(linha)]
    try:
        spec = importlib.util.spec_from_file_location("_postar_da_cura", POSTAR)
        postar = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(postar)
        falhas = []
        if postar._build_ja_no_tiktok(SONDA) is not True:
            falhas.append("postar._build_ja_no_tiktok")
        if not serie.ja_publicado(SONDA, "tiktok"):
            falhas.append("serie.ja_publicado")
    except Exception as exc:                                   # noqa: BLE001
        return f"a sonda do postar.py falhou ({type(exc).__name__}: {exc})"
    finally:
        metricas.publicados, serie.publicados = reais
    if falhas:
        return ("uma linha curada do TikTok NAO conta como publicada para "
                + ", ".join(falhas) + " (repostaria)")
    return ""


def escritores_travados() -> str:
    """`""` se os tres escritores do ledger passam pela trava `ledger__<canal>`.

    Teste de comportamento, com os dois ledgers apontados para um arquivo
    temporario e a escrita trocada por um espiao: se algum escritor fugir do
    caminho comum, ele escreve no temporario, nunca no ledger de verdade.
    """
    import contextlib
    import tempfile

    from builds import travas
    from contos.publicar import serie

    vistos: list = []
    pedidas: list = []

    def espiao(caminho, linha, canal, **_k):
        vistos.append(canal)

    @contextlib.contextmanager
    def ocupada(nome, esperar=0.0):
        pedidas.append(nome)
        yield False

    video = type("Sonda", (), {"id": SONDA, "fonte_id": SONDA, "parte": 1,
                               "partes": 1, "titulo": SONDA})()
    with tempfile.TemporaryDirectory() as pasta:
        falso = Path(pasta) / "publicados.jsonl"
        reais = (metricas.acrescentar_ao_ledger, metricas.REGISTRO,
                 metricas.registro_do_canal, metricas.publicados,
                 metricas._token, metricas.enviados, serie.REGISTRO,
                 travas.trava)
        metricas.acrescentar_ao_ledger = espiao
        metricas.REGISTRO = falso
        metricas.registro_do_canal = lambda canal="builds": falso
        # Uma linha sem id: sem ela o `reconciliar` sai antes da trava.
        metricas.publicados = lambda canal="builds": [
            {"plataforma": "youtube", "titulo": SONDA, "video_id": SONDA}]
        metricas._token = lambda canal="builds": ("sonda", None)
        metricas.enviados = lambda token, quantos=200: []
        serie.REGISTRO = falso
        travas.trava = ocupada
        try:
            metricas.registrar_publicacao(video, "", "tiktok")
            serie.registrar(video, "", "tiktok", None)
            metricas.reconciliar("builds", log=lambda *_a: None)
            metricas.reconciliar("historias", log=lambda *_a: None)
            with trava_do_ledger("builds"):
                pass
        except Exception as exc:                               # noqa: BLE001
            return (f"a sonda dos escritores falhou "
                    f"({type(exc).__name__}: {exc})")
        finally:
            (metricas.acrescentar_ao_ledger, metricas.REGISTRO,
             metricas.registro_do_canal, metricas.publicados,
             metricas._token, metricas.enviados, serie.REGISTRO,
             travas.trava) = reais
        escrito = falso.is_file() and falso.stat().st_size > 0
    faltas = []
    if vistos != ["builds", "historias"]:
        faltas.append(f"acrescentar_ao_ledger viu {vistos}, esperado "
                      "['builds', 'historias']")
    if escrito:
        faltas.append("um escritor gravou fora de acrescentar_ao_ledger")
    esperadas = [metricas.nome_da_trava(c)
                 for c in ("builds", "historias", "builds")]
    if pedidas != esperadas:
        faltas.append(f"travas pedidas {pedidas}, esperado {esperadas}")
    return "; ".join(faltas)


def postar_migrado(fonte: str | None = None) -> str:
    """`""` se o publicador ja decide "saiu?" por `publicado()`; senao, o motivo.

    Medido em 16/09/2026, antes de qualquer gravacao: com o postar.py lendo o
    `url`, a regra de formato (que tira a frase do `url` do TikTok) apagaria
    a guarda de "ja esta no TikTok" de 46 builds e 51 historias, e o
    publicador repostaria. As curas so podem ser gravadas DEPOIS da migracao.

    Tres provas, todas exigidas: a declaracao do contrato, nenhuma decisao
    pelo `url` na arvore do codigo e — so com o arquivo de verdade — a sonda
    que pergunta aos leitores se a linha curada conta como publicada.
    """
    real = fonte is None
    if real:
        try:
            fonte = POSTAR.read_text(encoding="utf-8")
        except OSError as exc:
            return f"nao consegui ler o postar.py ({exc})"
    achado = re.search(r"^CONTRATO_DO_LEDGER\s*=\s*(\d+)", fonte, re.MULTILINE)
    if not achado or int(achado.group(1)) < CONTRATO_MINIMO:
        return (f"o postar.py ainda nao declara CONTRATO_DO_LEDGER = "
                f"{CONTRATO_MINIMO} (a migracao para `publicado()` nao "
                "aconteceu)")
    try:
        restos = leituras_por_url(fonte)
    except SyntaxError as exc:
        return f"o postar.py nao compila ({exc})"
    if restos:
        return (f"o postar.py declara o contrato mas ainda decide 'saiu?' "
                f"pelo url em {len(restos)} ponto(s): linhas "
                + ", ".join(map(str, restos[:8])))
    return leitores_entendem_a_cura() if real else ""


def impedimento_para_gravar() -> str:
    """Tudo o que precisa ser verdade antes de reescrever um ledger."""
    return postar_migrado() or escritores_travados()


# ------------------------------------------------ gravacao segura (B2, B3)
def trava_do_ledger(canal: str):
    """A trava que TODO escritor do ledger deve segurar para reescreve-lo."""
    from builds import travas
    return travas.trava(metricas.nome_da_trava(canal), esperar=60.0)


def gravar(caminho: Path, linhas: list, carimbo: str) -> Path:
    """Copia o antes e troca o arquivo de uma vez (`os.replace`).

    Escrever direto com `open("w")` deixava uma janela em que o ledger
    existia pela metade — e qualquer leitor nesse instante via um ledger
    truncado.
    """
    copia = caminho.with_name(f"{caminho.name}.antes-cura-{carimbo}")
    shutil.copy2(caminho, copia)
    temporario = caminho.with_name(f"{caminho.name}.cura-{carimbo}.tmp")
    with open(temporario, "w", encoding="utf-8") as fh:
        for linha in linhas:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    os.replace(temporario, caminho)
    return copia


def so_dos_tipos(curas: list, tipos=()) -> list:
    """So as curas dos `tipos` pedidos; sem pedido, todas.

    POR QUE (28/09/2026): as cinco duplicatas do canal de builds voltaram a
    privado por decisao do Adrian, e quatro linhas do ledger precisam da
    cura `privado_de_proposito` — sem ela, a proxima gravacao as chamaria
    de `rascunho_sem_gemeo` (os gemeos publicos sao de 27/08, ANTERIORES a
    linha) e a fila as republicaria. So que a gravacao aplicava TODAS as
    curas pendentes (244 outras, entre elas 5 `id_repetido` e 3
    `rascunho_sem_gemeo` que mudam o que a fila ve), e nenhuma delas foi
    decidida. O filtro deixa gravar so a decidida.
    """
    tipos = set(tipos or ())
    return [c for c in curas if not tipos or c["tipo"] in tipos]


def curar_canal(canal: str, videos: list, *, gravar_de_fato: bool,
                privadas=(), carimbo: str = "", tentativas: int = 3,
                tipos=()) -> tuple:
    """(linhas, curas, copia). Le, calcula e grava DENTRO da trava.

    A lista do canal chega pronta: a chamada de rede nao pode acontecer com
    a trava na mao. Antes de trocar o arquivo, ele e relido; se alguem
    escreveu no meio (a postagem acrescenta linhas a cada horario), as curas
    sao recalculadas em cima do novo conteudo. Medido em 16/09/2026: entre a
    primeira rodada a seco e a segunda, os ledgers foram de 137 para 140 e
    de 112 para 113 linhas.

    `tipos`: so essas curas sao relatadas e gravadas (`so_dos_tipos`).
    """
    caminho = metricas.registro_do_canal(canal)
    with trava_do_ledger(canal) as minha:
        if not minha:
            raise RuntimeError(f"o ledger de {canal} esta travado por outro "
                               "escritor; nada foi gravado")
        for _ in range(max(1, tentativas)):
            bruto = ler_bruto(caminho)
            linhas = ler(caminho, bruto)
            curas = so_dos_tipos(
                calcular_curas(linhas, videos, canal, privadas=privadas),
                tipos)
            if not gravar_de_fato:
                return linhas, curas, None
            if ler_bruto(caminho) != bruto:
                continue
            copia = gravar(caminho, aplicar(linhas, curas), carimbo)
            return linhas, curas, copia
    raise RuntimeError(f"o ledger de {canal} mudou {tentativas} vezes durante "
                       "a cura; nada foi gravado")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="curar_ledger",
        description="cura do ledger de publicacoes (a seco por padrao)")
    parser.add_argument("--canal", choices=("builds", "historias"),
                        action="append", help="padrao: os dois")
    parser.add_argument("--gravar", action="store_true",
                        help="APLICA as curas (alta e media), com copia antes")
    parser.add_argument(
        "--privada-de-proposito", dest="privadas", action="append",
        default=[], metavar="VIDEO_ID",
        help="video_id que ficou privado POR DECISAO (repetivel): a linha "
             "vira publicado=true, estado=privado_de_proposito")
    parser.add_argument(
        "--so-tipo", dest="tipos", action="append", default=[],
        metavar="TIPO",
        help="so relata e grava as curas deste tipo (repetivel), p.ex. "
             "privado_de_proposito; sem ele, todas")
    args = parser.parse_args(argv)

    if args.gravar:
        impedimento = impedimento_para_gravar()
        if impedimento:
            _linha(f"RECUSADO: {impedimento}. Nada foi gravado. Rode sem "
                   "--gravar para ver o que mudaria.")
            return 2

    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta = SAIDA / carimbo
    pasta.mkdir(parents=True, exist_ok=True)
    geral = {}
    canais = args.canal or ("builds", "historias")
    # Um id so e aviso se nao pegou em NENHUM canal: o id de uma build nunca
    # vai estar no ledger das historias.
    sem_efeito: dict = {}
    for canal in canais:
        videos = buscar_canal(canal)
        linhas, curas, copia = curar_canal(
            canal, videos, gravar_de_fato=args.gravar,
            privadas=args.privadas, carimbo=carimbo, tipos=args.tipos)
        (pasta / f"{canal}.json").write_text(
            json.dumps(curas, ensure_ascii=False, indent=1), encoding="utf-8")
        geral[canal] = resumo(curas)
        _linha(f"[{canal}] {len(linhas)} linhas, {len(curas)} cura(s):")
        for chave, n in geral[canal].items():
            _linha(f"   {n:4d}  {chave}")
        for vid, motivo in privadas_sem_efeito(linhas, curas, args.privadas):
            sem_efeito.setdefault(vid, {})[canal] = motivo
        if copia:
            _linha(f"[{canal}] GRAVADO. Copia do antes: {copia}")
    for vid, motivos in sem_efeito.items():
        if len(motivos) < len(canais):
            continue
        detalhe = "; ".join(f"{c}: {m}" for c, m in motivos.items())
        _linha(f"AVISO: --privada-de-proposito {vid} nao teve efeito ({detalhe})")
    (pasta / "resumo.json").write_text(
        json.dumps({"gravado": bool(args.gravar), "canais": geral},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    _linha(f"relatorio: {pasta}"
           + ("" if args.gravar else "  (A SECO: nada no ledger mudou)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
