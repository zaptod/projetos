"""Monitor ao vivo das orquestracoes de agentes.

Le os transcritos que o Claude Code grava em ~/.claude/projects/.../subagents/workflows
e mostra, para cada agente: quem ele e, se ainda esta rodando e qual foi a ultima acao.
O rotulo nao vive no metadata; ele e deduzido do prompt inicial do proprio agente.

Uso:   python monitor_agentes.py           (atualiza sozinho a cada 3s)
       python monitor_agentes.py --once    (imprime uma vez e sai)
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

RAIZ = os.path.expanduser(
    r"~\.claude\projects\e--projetos\bc159af8-45ef-4702-a836-61f0eb35ce81"
    r"\subagents\workflows")
REPO = r"e:\projetos\random_builds"

# Cada padrao mapeia um trecho do prompt inicial para o papel do agente. A ordem
# importa: o primeiro que casar ganha.
PAPEIS = [
    (r"VOCE E O AUDITOR FINAL", "auditor final"),
    (r"VOCE E O ATACANTE FINAL", "atacante final"),
    (r"VOCE E O SINTETIZADOR", "sintetizador"),
    (r"VOCE E O INTEGRADOR", "integrador"),
    (r"VOCE E JUIZ.*?LENTE: (\w+)", "juiz"),
    (r"SUA ABORDAGEM: ([^\n]{0,45})", "candidato"),
    (r"Tente QUEBRAR[^\n]{0,60}", "atacante"),
    (r"Implemente o pedido (\d)", "implementa"),
    (r"SUA FRENTE: ([^\n]{0,40})", "pesquisa"),
]


def papel_de(prompt):
    for padrao, nome in PAPEIS:
        m = re.search(padrao, prompt, re.S)
        if m:
            extra = ""
            if m.groups():
                extra = " " + (m.group(1) or "").strip()[:34]
            return (nome + extra).strip()
    return "?"


def ultima_acao(entradas):
    """Ultimo sinal util: nome da ferramenta chamada ou inicio do texto."""
    for e in reversed(entradas):
        msg = e.get("message") or {}
        conteudo = msg.get("content")
        if isinstance(conteudo, list):
            for bloco in reversed(conteudo):
                if not isinstance(bloco, dict):
                    continue
                if bloco.get("type") == "tool_use":
                    alvo = bloco.get("input") or {}
                    dica = (alvo.get("command") or alvo.get("file_path")
                            or alvo.get("pattern") or "")
                    dica = re.sub(r"\s+", " ", str(dica))[:52]
                    return "%s %s" % (bloco.get("name", "?"), dica)
                if bloco.get("type") == "text" and bloco.get("text", "").strip():
                    return "escrevendo: " + re.sub(
                        r"\s+", " ", bloco["text"].strip())[:52]
        elif isinstance(conteudo, str) and conteudo.strip():
            return re.sub(r"\s+", " ", conteudo.strip())[:52]
    return "-"


def ler_agente(caminho):
    entradas = []
    try:
        with open(caminho, encoding="utf-8", errors="replace") as fh:
            for linha in fh:
                try:
                    entradas.append(json.loads(linha))
                except ValueError:
                    pass
    except OSError:
        return None
    if not entradas:
        return None
    primeiro = entradas[0].get("message") or {}
    prompt = primeiro.get("content")
    if isinstance(prompt, list):
        prompt = " ".join(b.get("text", "") for b in prompt
                          if isinstance(b, dict))
    quieto = ""
    marca = entradas[-1].get("timestamp")
    if marca:
        try:
            t = datetime.fromisoformat(marca.replace("Z", "+00:00"))
            quieto = "%ds" % int(
                (datetime.now(timezone.utc) - t).total_seconds())
        except ValueError:
            pass
    return {
        "id": entradas[0].get("agentId", "?"),
        "papel": papel_de(str(prompt or "")),
        "turnos": len(entradas),
        "acao": ultima_acao(entradas),
        "quieto": quieto,
    }


def prontos(pasta):
    """ids que ja devolveram resultado, segundo o journal da orquestracao."""
    feito = set()
    caminho = os.path.join(pasta, "journal.jsonl")
    try:
        with open(caminho, encoding="utf-8", errors="replace") as fh:
            for linha in fh:
                try:
                    e = json.loads(linha)
                except ValueError:
                    continue
                if e.get("type") == "result" and e.get("agentId"):
                    feito.add(e["agentId"])
    except OSError:
        pass
    return feito


def desenhar():
    linhas = []
    try:
        pastas = sorted(
            (os.path.join(RAIZ, d) for d in os.listdir(RAIZ)
             if d.startswith("wf_")),
            key=os.path.getmtime, reverse=True)[:3]
    except OSError:
        return ["nenhuma orquestracao encontrada em:", RAIZ]

    for pasta in pastas:
        feito = prontos(pasta)
        agentes = []
        for arq in sorted(os.listdir(pasta)):
            if arq.startswith("agent-") and arq.endswith(".jsonl"):
                info = ler_agente(os.path.join(pasta, arq))
                if info:
                    info["ok"] = info["id"] in feito
                    agentes.append(info)
        rodando = [a for a in agentes if not a["ok"]]
        linhas.append("")
        linhas.append("=" * 78)
        linhas.append("%s   %d agentes | %d prontos | %d rodando" % (
            os.path.basename(pasta), len(agentes),
            len(agentes) - len(rodando), len(rodando)))
        linhas.append("=" * 78)
        for a in agentes:
            marca = "OK " if a["ok"] else ">> "
            linhas.append("%s%-26s t=%-4d %5s  %s" % (
                marca, a["papel"][:26], a["turnos"], a["quieto"], a["acao"]))
    try:
        saida = subprocess.run(
            ["git", "status", "--short"], cwd=REPO, capture_output=True,
            text=True, timeout=10).stdout.strip()
    except Exception:
        saida = ""
    if saida:
        linhas.append("")
        linhas.append("--- arquivos no repo ---")
        linhas.extend("  " + s for s in saida.splitlines())
    return linhas


def main():
    uma_vez = "--once" in sys.argv
    while True:
        texto = "\n".join(desenhar())
        if not uma_vez:
            os.system("cls" if os.name == "nt" else "clear")
        print(texto)
        print("\n(ctrl+c para sair)  " + time.strftime("%H:%M:%S"))
        if uma_vez:
            return
        time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
