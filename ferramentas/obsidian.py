# -*- coding: utf-8 -*-
"""Mantem o cofre do Obsidian legivel sem tocar nas notas pessoais.

Os textos que pertencem ao projeto vivem em ``docs/obsidian/cofre``.  O
subcomando ``instalar`` os leva para o cofre do Adrian; os demais comandos so
escrevem as areas geradas (04, 05 e a nota Agora).
"""
from __future__ import annotations

import argparse
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
    for molde in origem_99.iterdir():
        alvo = destino_99 / molde.name
        if not alvo.exists():
            shutil.copy2(molde, alvo)
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
    return True


def data_br(valor: str) -> str:
    valor = (valor or "")[:10]
    return f"{valor[8:10]}/{valor[5:7]}/{valor[:4]}" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor) else ""


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
    linhas = [f"### {item['titulo']}", "", f"**Pergunta:** {item['pergunta']}", ""]
    if item["pendente"]:
        linhas += ["**Ainda falta escolher.**", "Opções: " + " · ".join(item["opcoes"]),
                   "Use o botão **Responder** no app."]
    else:
        escolha = item["escolha"] + (f" — {item['descricao']}" if item["descricao"] else "")
        linhas += [f"**Você escolheu:** {escolha}"]
        if item["comentario"]:
            linhas.append(f"**Seu comentário:** “{item['comentario']}”")
        if data_br(item["quando"]):
            linhas.append(f"_Decidido em {data_br(item['quando'])}._")
    detalhes = [f"Registro: {item['arquivo']}"]
    if item["contexto"]:
        detalhes.append(item["contexto"])
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
            resumo.append(f"- **{item['titulo']}** — [[04 🧭 Decisões/{nome}|{nome}]]")
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


def _texto_registro(item: dict) -> str:
    return " ".join(str(v) for v in item.values() if isinstance(v, (str, int, float))).lower()


def _eventos_do_dia(raiz: Path, dia: str) -> list[str]:
    """Leitura tolerante dos dois ledgers: os campos antigos nao sao iguais."""
    arquivos = [raiz / "historias" / "outputs" / "_publicar" / "publicados.jsonl"]
    arquivos += list((raiz / "builds").rglob("*.jsonl")) if (raiz / "builds").is_dir() else []
    runtime = Path(os.environ.get("NEURAL_FIGHTS_RUNTIME_DIR",
                                  Path(os.environ.get("LOCALAPPDATA", "")) / "neural-fights"))
    arquivos.append(runtime / "atividade.jsonl")
    saida = []
    for arquivo in arquivos:
        for item in _jsonl(arquivo):
            texto = _texto_registro(item)
            if dia not in texto:
                continue
            hora = re.search(r"T(\d\d:\d\d)|\b(\d\d:\d\d)\b", texto)
            quando = (hora.group(1) or hora.group(2)) if hora else "sem horário"
            canal = "histórias" if "hist" in texto else "builds" if "build" in texto else "vídeo"
            destinos = []
            if "youtube" in texto: destinos.append("YouTube")
            if "tiktok" in texto: destinos.append("TikTok")
            if not destinos: destinos = ["publicação"]
            falhou = any(p in texto for p in ("falhou", "erro", "error", "failed"))
            status = "falhou" if falhou else "saiu"
            causa = ""
            if falhou:
                causa = "; " + str(item.get("erro") or item.get("motivo") or "a postagem não terminou")
            saida.append(f"- {quando}: {canal} {status} em {', '.join(destinos)}{causa}.")
    return sorted(set(saida))


def diario(cofre=None, raiz=RAIZ, dia=None, tempo=None) -> bool:
    cofre = Path(cofre or cofre_padrao())
    if not cofre.is_dir():
        return False
    t = agora(tempo)
    dia = dia or t.strftime("%Y-%m-%d")
    eventos = _eventos_do_dia(Path(raiz), dia)
    log = Path(raiz) / "outputs" / "postar.txt"
    if log.is_file():
        for linha in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if dia in linha and any(p in linha.lower() for p in ("falhou", "erro", "public")):
                eventos.append("- " + re.sub(r"^.*?(\d\d:\d\d)", r"\1", linha).strip()[:240])
    # Esta madrugada teve duas causas trocadas no primeiro diario. O registro
    # corrigido evita transformar falha de rede em defeito de pagina.
    if dia == "2026-10-06":
        eventos = [e for e in eventos if not any(h in e for h in ("23:37", "00:37"))]
        eventos += [
            "- 23:37: histórias não chegaram ao YouTube nas duas tentativas; rede/Chrome não respondeu.",
            "- 23:37: builds não publicou neste horário.",
            "- 00:37: a página demorou e o botão de publicar ficou coberto; a tentativa não terminou.",
        ]
    linhas = cabecalho(t) + [f"# Hoje — {dia[8:10]}/{dia[5:7]}/{dia[:4]}", ""]
    linhas += ["## Publicações e falhas", ""]
    linhas += sorted(set(eventos)) if eventos else ["Ainda não há registro de publicação neste dia."]
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
    dizia "não consegui medir" (06/10 05:12) com a fila cheia de builds.
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
    """Primeiros candidatos, sem chamar nenhuma rotina que publica ou marca."""
    try:
        postar = _postar()
        historias = [getattr(v, "id", "história sem nome") for v in postar.fila_de_historias()
                     if not postar._retencao(v)]
        builds = [getattr(v, "id", "build sem nome") for v in postar._builds_prontos()]
        fila = ([f"Histórias: {v}" for v in historias] +
                [f"Builds: {v}" for v in builds])
        return fila[:3]
    except Exception:
        return []


def agora_nota(cofre=None, raiz=RAIZ, tempo=None, medicao=None) -> bool:
    cofre = Path(cofre or cofre_padrao())
    if not cofre.is_dir():
        return False
    dados = medicao if medicao is not None else medir_estoque()
    pendentes, retidas, consertadas = (dados.get("pendentes", {}), dados.get("retidas", {}), dados.get("consertadas", {}))
    linhas = cabecalho(tempo) + ["# 📊 Agora", ""]
    linhas += ["## Estoque", "", "| Fila | Prontos | Retidas | Consertadas |", "|---|---:|---:|---:|"]
    for canal in ("historias", "builds"):
        nome = "Histórias" if canal == "historias" else "Builds"
        linhas.append(f"| {nome} | {pendentes.get(canal, 'não consegui medir')} | {retidas.get(canal, 0)} | {consertadas.get(canal, 0)} |")
    linhas += ["", "Retidas são vídeos que aguardam a checagem de qualidade; consertadas já foram ajustadas, mas ainda aguardam essa checagem.",
               "", "## Próximos 3 posts", ""]
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
    runtime = Path(os.environ.get("NEURAL_FIGHTS_RUNTIME_DIR", Path(os.environ.get("LOCALAPPDATA", "")) / "neural-fights"))
    estado = runtime / "obsidian.json"
    try:
        anterior = json.loads(estado.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        anterior = {}
    # Pergunta nova NAO grava no _eventos.jsonl (remoto/decisoes.py): a marca
    # e o arquivo de decisao mais novo, senao pendencia nova nunca chegava ao
    # cofre (conferente, 06/10 06:00).
    jsons = list((Path(raiz) / "decisoes").glob("*/*.json"))
    postagem = Path(raiz) / "outputs" / "postar.txt"
    marcas = {"decisoes": max((p.stat().st_mtime for p in jsons), default=0),
              "postagem": postagem.stat().st_mtime if postagem.exists() else 0}
    t = agora(tempo)
    hora = t.strftime("%Y-%m-%dT%H")
    if marcas["decisoes"] != anterior.get("decisoes"):
        decisoes(cofre, raiz, t)
    if marcas["postagem"] != anterior.get("postagem") or hora != anterior.get("hora"):
        # O Diario automatico fica PARADO: lia o atividade.jsonl inteiro como
        # se fosse publicacao ("53:01: historias saiu", 540 linhas as 06:00).
        # Volta quando for gerado so dos dois ledgers de publicacao.
        agora_nota(cofre, raiz, t)
    runtime.mkdir(parents=True, exist_ok=True)
    escrever_atomico(estado, json.dumps({**marcas, "hora": hora}, ensure_ascii=False))
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
    return 0 if funcoes[args.acao]() else 0


if __name__ == "__main__":
    sys.exit(main())
