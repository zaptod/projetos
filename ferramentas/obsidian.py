# -*- coding: utf-8 -*-
"""Mantem o cofre do Obsidian legivel sem tocar nas notas pessoais.

Os textos que pertencem ao projeto vivem em ``docs/obsidian/cofre``.  O
subcomando ``instalar`` os leva para o cofre do Adrian; os demais comandos so
escrevem as areas geradas (04, 05 e a nota Agora).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
MODELOS = RAIZ / "docs" / "obsidian" / "cofre"
COFRE_PADRAO = Path(r"E:\Obsidian\Neural Fights")
NOMES = {
    "geral": "Geral", "historias": "Histórias", "builds": "Neural Fights (builds)",
    "publicacao": "Publicação", "metricas": "Métricas", "app-e-bot": "App e bot",
    "painel-e-vila": "Painel e Vila", "jogo-zombie": "Zombie",
}
AVISO = "_Atualizada sozinha às {hora} de {data}. Não edite aqui: comente em 💡 Ideias._"
INICIO = "[[00 Início|← Início]]"


def cofre_padrao() -> Path:
    return Path(os.environ.get("NEURAL_FIGHTS_OBSIDIAN_VAULT", COFRE_PADRAO))


def agora(tempo=None) -> datetime:
    return tempo or datetime.now()


def cabecalho(tempo=None) -> list[str]:
    t = agora(tempo)
    return [AVISO.format(hora=t.strftime("%H:%M"), data=t.strftime("%d/%m")), INICIO, ""]


def escrever_atomico(caminho: Path, texto: str) -> None:
    """Renomear no fim impede o Syncthing de ver uma nota pela metade."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + ".novo")
    temporario.write_text(texto, encoding="utf-8", newline="\n")
    temporario.replace(caminho)


def instalar(cofre=None, modelos=MODELOS) -> bool:
    """Instala apenas o que e do projeto; 01 e 02 jamais entram aqui."""
    cofre = Path(cofre or cofre_padrao())
    modelos = Path(modelos)
    if not cofre.is_dir():
        return False
    shutil.copy2(modelos / "00 Início.md", cofre / "00 Início.md")
    destino_03 = cofre / "03 🗺️ Entender o projeto"
    shutil.copytree(modelos / "03 🗺️ Entender o projeto", destino_03,
                    dirs_exist_ok=True)
    origem_99, destino_99 = modelos / "99 🧩 Modelos", cofre / "99 🧩 Modelos"
    destino_99.mkdir(exist_ok=True)
    estado = _ler_estado_obsidian()
    hashes = estado.get("moldes", {})
    for molde in origem_99.iterdir():
        alvo = destino_99 / molde.name
        chave = str(alvo.relative_to(cofre)).replace("\\", "/")
        antigo = hashes.get(chave)
        instalado_pelo_sistema = antigo and alvo.is_file() and _hash_arquivo(alvo) == antigo
        if not alvo.exists() or instalado_pelo_sistema:
            shutil.copy2(molde, alvo)
            hashes[chave] = _hash_arquivo(molde)
    base_origem = modelos / "01 💡 Ideias" / "Ideias.base"
    base_destino = cofre / "01 💡 Ideias" / "Ideias.base"
    if base_origem.is_file() and not base_destino.exists():
        base_destino.parent.mkdir(exist_ok=True)
        shutil.copy2(base_origem, base_destino)
    ignore = modelos / ".stignore"
    if ignore.is_file():
        atual = (cofre / ".stignore").read_text(encoding="utf-8") if (cofre / ".stignore").exists() else ""
        for linha in ignore.read_text(encoding="utf-8").splitlines():
            if linha and linha not in atual.splitlines():
                atual += ("" if not atual or atual.endswith("\n") else "\n") + linha + "\n"
        escrever_atomico(cofre / ".stignore", atual)
    _favoritar_notas_do_sistema(cofre)
    estado["moldes"] = hashes
    _escrever_estado_obsidian(estado)
    return True


def _runtime_dir() -> Path:
    return Path(os.environ.get("NEURAL_FIGHTS_RUNTIME_DIR",
                               Path(os.environ.get("LOCALAPPDATA", "")) / "neural-fights"))


def _caminho_estado_obsidian() -> Path:
    return _runtime_dir() / "obsidian.json"


def _ler_estado_obsidian() -> dict:
    try:
        dados = json.loads(_caminho_estado_obsidian().read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def _escrever_estado_obsidian(estado: dict) -> None:
    caminho = _caminho_estado_obsidian()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    escrever_atomico(caminho, json.dumps(estado, ensure_ascii=False))


def _hash_arquivo(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _favoritar_notas_do_sistema(cofre: Path) -> None:
    """Acrescenta os atalhos sem mexer nos favoritos pessoais."""
    caminho = cofre / ".obsidian" / "bookmarks.json"
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {"items": []}
    itens = dados.get("items") if isinstance(dados, dict) else None
    if not isinstance(itens, list):
        itens = []
        dados = {"items": itens}
    existentes = {item.get("path") for item in itens if isinstance(item, dict)}
    for nota in ("00 Início.md", "📊 Agora.md"):
        if nota not in existentes:
            itens.append({"type": "file", "path": nota})
    escrever_atomico(caminho, json.dumps(dados, ensure_ascii=False, indent=2) + "\n")


def data_br(valor: str) -> str:
    valor = (valor or "")[:10]
    return f"{valor[8:10]}/{valor[5:7]}/{valor[:4]}" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor) else ""


def texto_para_leitor(texto) -> str:
    """Tira identificadores de sistema da parte que aparece aberta."""
    texto = re.sub(r"`[^`]+`", "", str(texto or ""))
    texto = re.sub(r"\b(?:PID\s+\d+|generation_\d+|(?:branch|commit)\s+\S+|\d{2}[A-Z])\b",
                   "", texto, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", texto).strip(" —:;,")


def ler_decisoes(raiz=RAIZ) -> dict[str, list[dict]]:
    saida = {}
    for projeto, nome in NOMES.items():
        itens = []
        for arquivo in sorted((Path(raiz) / "decisoes" / projeto).glob("*.json")):
            try:
                bruto = json.loads(arquivo.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            vigente = bruto.get("vigente") or {}
            opcoes = {str(o.get("id")): o for o in bruto.get("opcoes") or []}
            opcao = opcoes.get(str(vigente.get("opcao")), {})
            itens.append({
                "titulo": bruto.get("titulo") or arquivo.stem,
                "pergunta": bruto.get("pergunta") or "",
                "contexto": bruto.get("contexto") or "",
                "pendente": not bool(vigente) or bruto.get("situacao") == "pendente",
                "escolha": opcao.get("rotulo") or "",
                "descricao": opcao.get("descricao") or "",
                "comentario": (vigente.get("comentario") or "").strip(),
                "quando": vigente.get("em") or "",
                "opcoes": [str(o.get("rotulo") or "") for o in bruto.get("opcoes") or []],
                "arquivo": arquivo.name,
            })
        if itens:
            saida[nome] = itens
    return saida


def bloco_decisao(item: dict) -> list[str]:
    titulo = texto_para_leitor(item["titulo"])
    linhas = [f"### {titulo}", "", f"**Pergunta:** {texto_para_leitor(item['pergunta'])}", ""]
    if item["pendente"]:
        opcoes = [texto_para_leitor(opcao) for opcao in item["opcoes"]]
        linhas += ["**Ainda falta escolher.**", "Opções: " + " · ".join(opcoes),
                   "No app, abra **📖 Decidir → Responder**."]
    else:
        escolha = texto_para_leitor(item["escolha"])
        if item["descricao"]:
            escolha += f" — {texto_para_leitor(item['descricao'])}"
        linhas += [f"**Você escolheu:** {escolha}"]
        if data_br(item["quando"]):
            linhas.append(f"_Decidido em {data_br(item['quando'])}._")
    detalhes = [f"Registro: {item['arquivo']}"]
    if item["contexto"]:
        detalhes.append(item["contexto"])
    if item["comentario"]:
        detalhes.append("Comentário: " + item["comentario"])
    linhas += ["", "> [!info]- Detalhes do sistema (toque para abrir)"]
    for detalhe in detalhes:
        for linha in detalhe.splitlines() or [""]:
            linhas.append("> " + linha)
    return linhas + [""]


def decisoes(cofre=None, raiz=RAIZ, tempo=None) -> bool:
    cofre = Path(cofre or cofre_padrao())
    if not cofre.is_dir():
        return False
    pasta = cofre / "04 🧭 Decisões"
    grupos = ler_decisoes(raiz)
    pendentes = [(nome, item) for nome, itens in grupos.items() for item in itens if item["pendente"]]
    resumo = cabecalho(tempo) + ["# 🧭 Decisões", ""]
    resumo += [f"## ⏳ Esperando você ({len(pendentes)})", ""]
    if pendentes:
        for nome, item in pendentes:
            resumo.append(f"- **{texto_para_leitor(item['titulo'])}** — [[04 🧭 Decisões/{nome}|{nome}]]")
    else:
        resumo.append("Nada esperando você agora. 🎉")
    resumo += ["", "## Por assunto", "", "| Assunto | Escolhidas | Esperando |", "|---|---:|---:|"]
    for nome, itens in grupos.items():
        resumo.append(f"| [[04 🧭 Decisões/{nome}|{nome}]] | {sum(not i['pendente'] for i in itens)} | {sum(i['pendente'] for i in itens)} |")
    escrever_atomico(pasta / "Decisões.md", "\n".join(resumo) + "\n")
    for nome, itens in grupos.items():
        espera = [i for i in itens if i["pendente"]]
        feitas = sorted((i for i in itens if not i["pendente"]), key=lambda i: i["quando"], reverse=True)
        linhas = cabecalho(tempo) + [f"# 🧭 Decisões — {nome}", ""]
        linhas += [f"## ⏳ Esperando você ({len(espera)})", ""]
        for item in espera:
            linhas += bloco_decisao(item)
        linhas += [f"## ✅ Escolhidas ({len(feitas)})", ""]
        for item in feitas:
            linhas += bloco_decisao(item)
        escrever_atomico(pasta / f"{nome}.md", "\n".join(linhas) + "\n")
    return True


def _jsonl(caminho: Path) -> list[dict]:
    if not caminho.is_file():
        return []
    itens = []
    for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(linha)
        except ValueError:
            continue
        if isinstance(item, dict):
            itens.append(item)
    return itens


def _instante_local(valor) -> datetime | None:
    """Converte o `quando` do ledger para a hora local do computador."""
    try:
        instante = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return instante.astimezone().replace(tzinfo=None) if instante.tzinfo else instante


def _grade():
    """A grade de horarios pelo caminho do arquivo.

    Mesmo defeito do `_postar`: `python ferramentas/obsidian.py` nao tem a
    raiz no sys.path e `from random_builds.builds import grade` caia com
    ModuleNotFoundError (06/10, prova do Diario no real).
    """
    try:
        from random_builds.builds import grade
        return grade
    except ImportError:
        pass
    if "_nf_grade" in sys.modules:
        return sys.modules["_nf_grade"]
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_nf_grade", RAIZ / "random_builds" / "builds" / "grade.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_nf_grade"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _chave_do_horario(instante: datetime) -> tuple[str, str]:
    """Dia de grade e horario que uma tentativa cobriu, em hora local."""
    grade = _grade()
    minutos = instante.hour * 60 + instante.minute
    grade_minutos = [hora * 60 + minuto for hora, minuto in grade.GRADE]
    if minutos < grade_minutos[0]:
        indice = len(grade.GRADE) - 1
        dia = instante.date().fromordinal(instante.date().toordinal() - 1)
    else:
        dia = instante.date()
        indice = max(i for i, valor in enumerate(grade_minutos) if valor <= minutos)
    hora, minuto = grade.GRADE[indice]
    return dia.isoformat(), f"{hora:02d}:{minuto:02d}"


def _publicado(item: dict) -> bool:
    return bool(item.get("publicado")) if "publicado" in item else bool(item.get("url"))


def _causas_do_log(raiz: Path, dia: str) -> dict[tuple[str, str, str], str]:
    """Motivos humanos do log, sem usa-lo como prova de publicacao."""
    caminho = Path(raiz) / "outputs" / "postar.txt"
    causas = {}
    if not caminho.is_file():
        return causas
    padrao = re.compile(r"(\d{4}-\d{2}-\d{2})[^0-9]{0,3}(\d{2}:\d{2})")
    for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
        achado = padrao.search(linha)
        if not achado:
            continue
        instante = _instante_local(f"{achado.group(1)}T{achado.group(2)}")
        if instante is None:
            continue
        dia_grade, horario = _chave_do_horario(instante)
        if dia_grade != dia:
            continue
        baixo = linha.lower()
        canal = "historias" if "historia" in baixo else "builds" if "build" in baixo else ""
        destino = "youtube" if "youtube" in baixo else "tiktok" if "tiktok" in baixo else ""
        if not canal or not any(palavra in baixo for palavra in ("falhou", "erro", "nao subiu", "não subiu", "nao ha", "não há")):
            continue
        motivo = re.sub(r"^.*?\]\s*", "", linha).strip().rstrip(".")
        for plataforma in ((destino,) if destino else ("youtube", "tiktok")):
            causas.setdefault((horario, canal, plataforma), motivo[:220])
    return causas


def _eventos_grade_do_dia(raiz: Path, dia: str, ate: datetime | None = None) -> list[str]:
    """Cada horario da grade, pelos dois unicos ledgers de publicacao.

    Horario que ainda nao chegou (depois de `ate`) nao e "nao saiu": o diario
    roda de hora em hora e as 10:00 acusava o 12:07 como falha (06/10).
    """
    saidas = {}
    ledgers = {
        "historias": Path(raiz) / "historias" / "outputs" / "_publicar" / "publicados.jsonl",
        "builds": Path(raiz) / "random_builds" / "outputs" / "_publicar" / "publicados.jsonl",
    }
    for canal, caminho in ledgers.items():
        for item in _jsonl(caminho):
            instante = _instante_local(item.get("quando"))
            plataforma = str(item.get("plataforma") or "youtube").lower()
            if instante is None or plataforma not in ("youtube", "tiktok"):
                continue
            dia_grade, horario = _chave_do_horario(instante)
            if dia_grade == dia and _publicado(item):
                saidas[(horario, canal, plataforma)] = (instante, item)

    causas = _causas_do_log(raiz, dia)
    linhas = []
    for hora, minuto in _grade().GRADE:
        horario = f"{hora:02d}:{minuto:02d}"
        linhas += [f"### {horario}", ""]
        futuro = ate is not None and datetime.fromisoformat(f"{dia}T{horario}") > ate
        if futuro and not any(chave[0] == horario for chave in saidas):
            linhas += ["- Ainda não chegou.", ""]
            continue
        for canal, nome in (("historias", "Histórias"), ("builds", "Builds")):
            for plataforma, destino in (("youtube", "YouTube"), ("tiktok", "TikTok")):
                saida = saidas.get((horario, canal, plataforma))
                if saida:
                    instante, item = saida
                    titulo = str(item.get("titulo") or "vídeo sem título no registro")
                    linhas.append(f"- {nome} — {destino}: saiu às {instante:%H:%M} — {titulo}.")
                else:
                    causa = causas.get((horario, canal, plataforma))
                    linhas.append(f"- {nome} — {destino}: não saiu" + (f" — {causa}." if causa else "."))
        linhas.append("")
    return linhas


def diario(cofre=None, raiz=RAIZ, dia=None, tempo=None) -> bool:
    cofre = Path(cofre or cofre_padrao())
    if not cofre.is_dir():
        return False
    t = agora(tempo)
    dia = dia or t.strftime("%Y-%m-%d")
    eventos = _eventos_grade_do_dia(Path(raiz), dia, ate=t)
    linhas = cabecalho(t) + [f"# Hoje — {dia[8:10]}/{dia[5:7]}/{dia[:4]}", ""]
    linhas += ["## Publicações e falhas", ""]
    linhas += eventos if eventos else ["Ainda não há registro de publicação neste dia."]
    linhas += ["", "## Decisões do dia", ""]
    escolhas = []
    for itens in ler_decisoes(raiz).values():
        escolhas.extend(i for i in itens if not i["pendente"] and i["quando"].startswith(dia))
    linhas += [f"- **{i['titulo']}**: {i['escolha']}." for i in escolhas] or ["Nenhuma decisão registrada neste dia."]
    escrever_atomico(cofre / "05 📅 Diário do sistema" / f"{dia}.md", "\n".join(linhas) + "\n")
    return True


def _postar():
    """O `ferramentas/postar.py` pelo caminho do arquivo.

    `python ferramentas/obsidian.py` roda com a pasta `ferramentas/` no
    sys.path, sem a raiz: `from ferramentas import postar` falhava e o Agora
    dizia "não consegui medir" com a fila cheia de builds.
    """
    if "postar" in sys.modules:
        return sys.modules["postar"]
    import importlib.util
    spec = importlib.util.spec_from_file_location("postar", RAIZ / "ferramentas" / "postar.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["postar"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def medir_estoque() -> dict:
    try:
        postar = _postar()
        pendentes = postar.pendentes_por_canal()
        return {"pendentes": pendentes, "retidas": postar.retidos_por_canal(),
                "consertadas": postar.consertadas_por_canal()}
    except Exception:
        return {"pendentes": {}, "retidas": {}, "consertadas": {}}


def proximos_posts() -> list[str]:
    """A escolha que o ``postar.py --ver`` faria, sem marcar nem publicar."""
    try:
        postar = _postar()
        historia, _recusadas = postar.proxima_historia()
        build = postar.proximo_build(marcar=False)
        fila = []
        for nome, alvo in (("Histórias", historia), ("Builds", build)):
            if alvo is None:
                fila.append(f"{nome}: nenhum vídeo pode sair agora.")
                continue
            titulo = str(getattr(alvo, "titulo", "vídeo sem título"))
            texto = f"{nome}: {titulo}"
            if nome == "Histórias" and postar._retencao(alvo):
                texto += " — retida; sai só para o horário não ficar vazio."
            fila.append(texto)
        return fila
    except Exception:
        return []


def agora_nota(cofre=None, raiz=RAIZ, tempo=None, medicao=None) -> bool:
    cofre = Path(cofre or cofre_padrao())
    if not cofre.is_dir():
        return False
    dados = medicao if medicao is not None else medir_estoque()
    pendentes, retidas, consertadas = (dados.get("pendentes", {}), dados.get("retidas", {}), dados.get("consertadas", {}))
    linhas = cabecalho(tempo) + ["# 📊 Agora", ""]
    linhas += ["## Estoque", "", "| Fila | Prontos |", "|---|---:|"]
    for canal in ("historias", "builds"):
        nome = "Histórias" if canal == "historias" else "Builds"
        linhas.append(f"| {nome} | {pendentes.get(canal, 'não consegui medir')} |")
    retidas_historias = retidas.get("historias", 0)
    consertadas_historias = consertadas.get("historias", 0)
    linhas += ["", f"Histórias retidas: {retidas_historias}. Destas, {consertadas_historias} foram consertadas; a decisão é uma passada só, então ninguém vai assistir de novo. Elas só saem para o horário não ficar vazio."]
    if isinstance(pendentes.get("historias"), int) and pendentes["historias"] < 20:
        linhas += ["", "> [!warning] Histórias abaixo do piso", "> Há menos de 20 vídeos prontos; a reposição precisa agir."]
    linhas += ["", "## Próximos posts", ""]
    proximos = proximos_posts()
    linhas += [f"{n}. {post}" for n, post in enumerate(proximos, 1)] or ["Não consegui ler a fila agora."]
    escrever_atomico(cofre / "📊 Agora.md", "\n".join(linhas) + "\n")
    return True


def tudo(cofre=None, raiz=RAIZ, tempo=None) -> bool:
    return decisoes(cofre, raiz, tempo) and diario(cofre, raiz, tempo=tempo) and agora_nota(cofre, raiz, tempo)


def atualizar_automaticamente(raiz=RAIZ, cofre=None, tempo=None) -> bool:
    """Chamado pelo coordenador: uma vez por hora e ao mudar decisões/postagem."""
    cofre = Path(cofre or cofre_padrao())
    if not cofre.is_dir():
        return False
    anterior = _ler_estado_obsidian()
    # Pergunta nova NAO grava no _eventos.jsonl (remoto/decisoes.py): a marca
    # e o arquivo de decisao mais novo, senao pendencia nova nunca chegava ao
    # cofre.
    jsons = list((Path(raiz) / "decisoes").glob("*/*.json"))
    # So os dois ledgers marcam a postagem, nao o postar.txt: o log cresce a
    # cada poucos segundos durante uma postagem e cada pulso refaria o Agora,
    # que pergunta ao postar.py a proxima historia (ate 6 ffprobe + decode de
    # audio, ~7 s medidos em 06/10) — no meio do upload.
    postagem = [Path(raiz) / "historias" / "outputs" / "_publicar" / "publicados.jsonl",
                Path(raiz) / "random_builds" / "outputs" / "_publicar" / "publicados.jsonl"]
    marcas = {"decisoes": max((p.stat().st_mtime for p in jsons), default=0),
              "postagem": max((p.stat().st_mtime for p in postagem if p.exists()), default=0)}
    t = agora(tempo)
    hora = t.strftime("%Y-%m-%dT%H")
    if marcas["decisoes"] != anterior.get("decisoes"):
        decisoes(cofre, raiz, t)
    if marcas["postagem"] != anterior.get("postagem") or hora != anterior.get("hora"):
        diario(cofre, raiz, tempo=t)
        agora_nota(cofre, raiz, t)
    _escrever_estado_obsidian({**anterior, **marcas, "hora": hora})
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cofre", type=Path, default=None)
    parser.add_argument("--raiz", type=Path, default=RAIZ)
    sub = parser.add_subparsers(dest="acao", required=True)
    sub.add_parser("instalar")
    sub.add_parser("decisoes")
    diario_p = sub.add_parser("diario")
    diario_p.add_argument("--dia")
    sub.add_parser("agora")
    sub.add_parser("tudo")
    args = parser.parse_args(argv)
    funcoes = {"instalar": lambda: instalar(args.cofre), "decisoes": lambda: decisoes(args.cofre, args.raiz),
               "diario": lambda: diario(args.cofre, args.raiz, args.dia), "agora": lambda: agora_nota(args.cofre, args.raiz),
               "tudo": lambda: tudo(args.cofre, args.raiz)}
    # SCR-F3 (14/10/2026): era `else 0` — a falha saia com 0
    return 0 if funcoes[args.acao]() else 1


if __name__ == "__main__":
    sys.exit(main())
