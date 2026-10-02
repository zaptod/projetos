# -*- coding: utf-8 -*-
"""A Assembleia das IAs: delibera pelo correio, sem decidir pelo Adrian.

O estado fica ao lado das caixas do correio.  `avancar` e intencionalmente
pequeno e idempotente: o supervisor pode chama-lo varias vezes entre entregas
do carteiro sem mandar a mesma rodada duas vezes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from . import correio

PARTICIPANTES = ("gemini", "chatgpt", "deepseek", "grok")
PRAZO = timedelta(minutes=20)
CONTEXTO_MIN = 80
PROJETO_FIXO = ("Neural Fights e uma vila de IAs que ajuda Adrian a construir, "
                "avaliar e organizar projetos; as pessoas continuam no controle "
                "das decisoes registradas no Grimorio.")


class Recusa(ValueError):
    """Pedido de assembleia incompleto ou invalido."""


def _agora():
    return datetime.now()


def _iso(quando=None):
    return (quando or _agora()).isoformat(timespec="seconds")


def _pasta() -> Path:
    return correio.raiz() / "assembleias"


def _arquivo(ident: str) -> Path:
    return _pasta() / f"{ident}.json"


def _gravar(dados: dict) -> None:
    alvo = _arquivo(dados["id"])
    alvo.parent.mkdir(parents=True, exist_ok=True)
    temporario = alvo.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporario, alvo)


def _ler(ident: str) -> dict | None:
    try:
        dados = json.loads(_arquivo(ident).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def listar() -> list[dict]:
    saida = []
    try:
        arquivos = sorted(_pasta().glob("*.json"), key=lambda p: p.name)
    except OSError:
        return []
    for arquivo in arquivos:
        dados = _ler(arquivo.stem)
        if dados:
            saida.append(dados)
    return sorted(saida, key=lambda d: str(d.get("criada_em") or ""), reverse=True)


def ver(ident: str) -> dict | None:
    return _ler(ident)


def _limpo_id(texto: str, usados=()) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", str(texto).lower()).strip("-")[:30] or "opcao"
    candidato, n = base, 2
    while candidato in usados:
        sufixo = f"-{n}"
        candidato = base[:30 - len(sufixo)] + sufixo
        n += 1
    return candidato


def _opcoes(brutas) -> list[dict]:
    saida, usados = [], set()
    for bruta in brutas or []:
        if isinstance(bruta, dict):
            ident, rotulo = bruta.get("id"), bruta.get("rotulo", bruta.get("titulo"))
            descricao = bruta.get("descricao", "")
        else:
            texto = str(bruta)
            ident, sep, texto = texto.partition("=")
            if not sep:
                ident, texto = "", ident
            rotulo, _, descricao = texto.partition("|")
        rotulo = str(rotulo or "").strip()
        if not rotulo:
            raise Recusa("opcao sem rotulo")
        ident = _limpo_id(ident or rotulo, usados)
        usados.add(ident)
        saida.append({"id": ident, "rotulo": rotulo[:160], "descricao": str(descricao or "")[:500]})
    if len(saida) > 4:
        raise Recusa("a assembleia aceita no maximo 4 opcoes")
    return saida


def _resumo_projeto(projeto: str) -> str:
    alvo = Path(__file__).resolve().parents[1] / "docs" / "sessoes" / f"{projeto}.md"
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError:
        return ""
    blocos = re.split(r"\n\s*\n", texto)
    for bloco in blocos:
        limpo = re.sub(r"^\s*#+\s*", "", bloco).strip()
        if limpo and not limpo.startswith("<!--"):
            return re.sub(r"\s+", " ", limpo)[:600]
    return ""


def _texto_base(dados: dict, opcoes: list[dict], rodada: int, outras="") -> str:
    linhas = [
        "PEDIDO DE TEXTO.",
        "QUEM VOCE E AQUI: um dos participantes da assembleia das IAs do projeto Neural Fights. Voces deliberam, e o Adrian decide pelo app.",
        "O PROJETO: " + PROJETO_FIXO + (" " + _resumo_projeto(dados["projeto"]) if _resumo_projeto(dados["projeto"]) else ""),
        "A DECISAO: " + dados["pergunta"] + "\nContexto: " + dados["contexto"],
        "AS OPCOES:",
    ]
    if opcoes:
        linhas.extend(f"- {o['id']}: {o['rotulo']}" + (f" — {o['descricao']}" if o.get("descricao") else "")
                      for o in opcoes)
    else:
        linhas.append("- Ainda nao ha opcoes: proponha ate 2 opcoes concretas.")
    linhas.append("PARA QUE SERVE A SUA RESPOSTA: o voto da maioria vira a recomendacao no Grimorio; o seu porque e o seu risco aparecem para o Adrian ao lado da opcao; seja concreto para este projeto, nao generico.")
    if rodada == 1:
        linhas.append('Responda SOMENTE JSON estrito: {"voto":"<id da opcao>","por_que":"<ate 3 frases>","risco":"<o que pode dar errado>","propostas":[{"id":"...","rotulo":"...","descricao":"..."}]}')
    else:
        linhas.append("POSICOES DOS OUTROS PARTICIPANTES (anonimas):\n" + outras)
        linhas.append('Responda SOMENTE JSON estrito: {"voto":"<id da opcao>","mudou":false,"por_que":"<ate 3 frases>","resposta_ao_mais_forte":"<contra-argumento ao melhor argumento contrario>"}')
    return "\n\n".join(linhas)


def abrir(pergunta, opcoes=None, participantes=None, projeto="geral", contexto="") -> str:
    pergunta, contexto = str(pergunta or "").strip(), str(contexto or "").strip()
    if not pergunta:
        raise Recusa("a pergunta da assembleia esta vazia")
    if len(contexto) < CONTEXTO_MIN:
        raise Recusa("o contexto e obrigatorio e precisa ter ao menos 80 caracteres")
    participantes = participantes or PARTICIPANTES
    participantes = [str(p).lower() for p in participantes if str(p).lower() in correio.CHATS]
    participantes = list(dict.fromkeys(participantes))
    if not participantes:
        raise Recusa("nao ha participantes de texto disponiveis")
    escolhas = _opcoes(opcoes)
    ident = secrets.token_hex(6)
    dados = {"id": ident, "pergunta": pergunta[:2000], "opcoes": escolhas,
             "participantes": participantes, "projeto": str(projeto or "geral"),
             "contexto": contexto[:6000], "criada_em": _iso(), "situacao": "rodada_1",
             "rodada_1": {"aberta_em": _iso(), "mensagens": {}, "respostas": {}},
             "rodada_2": None, "ata": None, "decisao_id": None}
    for ia in participantes:
        mensagem = correio.enviar(ia, _texto_base(dados, escolhas, 1), de="assembleia")
        dados["rodada_1"]["mensagens"][ia] = mensagem["id"]
    _gravar(dados)
    return ident


def _ler_json(texto: str):
    """Extrai o primeiro objeto JSON, aceitando resposta com cercas ou texto."""
    decodificador = json.JSONDecoder()
    for achado in re.finditer(r"\{", str(texto or "")):
        try:
            valor, _ = decodificador.raw_decode(str(texto)[achado.start():])
        except ValueError:
            continue
        if isinstance(valor, dict):
            return valor
    return None


def _resposta(mensagem, rodada, opcoes):
    if not mensagem or mensagem.get("situacao") not in ("respondida", "falhou"):
        return None
    texto = str(mensagem.get("resposta") or "")
    bruto = _ler_json(texto) if mensagem.get("situacao") == "respondida" else None
    if not bruto:
        return {"situacao": "ausente" if mensagem.get("situacao") == "falhou" else "abstencao",
                "texto": texto[:1000], "erro": str(mensagem.get("erro") or "")[:300]}
    voto = str(bruto.get("voto") or "").strip()
    ids = {o["id"] for o in opcoes}
    if voto not in ids and rodada == 2:
        return {"situacao": "abstencao", "texto": texto[:1000]}
    saida = {"situacao": "respondeu", "voto": voto, "por_que": str(bruto.get("por_que") or "")[:700],
             "texto": texto[:1000]}
    if rodada == 1:
        saida["risco"] = str(bruto.get("risco") or "")[:500]
        saida["propostas"] = bruto.get("propostas") if isinstance(bruto.get("propostas"), list) else []
    else:
        saida["mudou"] = bool(bruto.get("mudou"))
        saida["resposta_ao_mais_forte"] = str(bruto.get("resposta_ao_mais_forte") or "")[:700]
    return saida


def _encerrou(rodada: dict, participantes) -> bool:
    if len(rodada.get("respostas", {})) == len(participantes):
        return True
    try:
        return _agora() >= datetime.fromisoformat(rodada["aberta_em"]) + PRAZO
    except (KeyError, ValueError):
        return False


def _colher(dados, nome, rodada):
    estado = dados[nome]
    for ia, mensagem_id in estado["mensagens"].items():
        if ia in estado["respostas"]:
            continue
        resposta = _resposta(correio.uma(ia, mensagem_id), rodada, dados["opcoes"])
        if resposta:
            estado["respostas"][ia] = resposta
    if _encerrou(estado, dados["participantes"]):
        for ia in dados["participantes"]:
            estado["respostas"].setdefault(ia, {"situacao": "ausente", "texto": ""})
        return True
    return False


def _propostas(dados):
    opcoes, vistos = list(dados["opcoes"]), {o["id"] for o in dados["opcoes"]}
    for resposta in dados["rodada_1"]["respostas"].values():
        for proposta in resposta.get("propostas", []) if isinstance(resposta, dict) else []:
            if not isinstance(proposta, dict) or len(opcoes) >= 4:
                continue
            rotulo = str(proposta.get("rotulo") or proposta.get("id") or "").strip()
            palavras = set(re.findall(r"[a-z0-9]{3,}", rotulo.lower()))
            def parecida(opcao):
                outras = set(re.findall(r"[a-z0-9]{3,}", opcao["rotulo"].lower()))
                return palavras == outras or bool(palavras and outras
                    and len(palavras & outras) / len(palavras | outras) >= 0.65)
            if not rotulo or any(parecida(o) for o in opcoes):
                continue
            ident = _limpo_id(proposta.get("id") or rotulo, vistos)
            vistos.add(ident)
            opcoes.append({"id": ident, "rotulo": rotulo[:160],
                           "descricao": str(proposta.get("descricao") or "")[:500]})
    return opcoes


def _abrir_rodada_2(dados):
    dados["opcoes"] = _propostas(dados)
    respostas = dados["rodada_1"]["respostas"]
    mensagens = {}
    for ia in dados["participantes"]:
        outras = []
        n = 0
        for outro in dados["participantes"]:
            if outro == ia or respostas[outro].get("situacao") != "respondeu":
                continue
            letra = chr(ord("A") + n)
            n += 1
            r = respostas[outro]
            outras.append(f"Participante {letra}: voto {r.get('voto') or 'sem voto'}; motivo: {r.get('por_que') or 'nao informado'}")
        mensagem = correio.enviar(ia, _texto_base(dados, dados["opcoes"], 2, "\n".join(outras) or "Nenhuma posicao disponivel."), de="assembleia")
        mensagens[ia] = mensagem["id"]
    dados["rodada_2"] = {"aberta_em": _iso(), "mensagens": mensagens, "respostas": {}}
    dados["situacao"] = "rodada_2"


def _ata(dados):
    respostas = dados["rodada_2"]["respostas"]
    validas = [r for r in respostas.values() if r.get("situacao") == "respondeu" and r.get("voto")]
    votos = {o["id"]: sum(r.get("voto") == o["id"] for r in validas) for o in dados["opcoes"]}
    recomendada = max(votos, key=votos.get) if votos and max(votos.values()) else None
    if len(validas) < 2:
        consenso = "sem quorum"
    elif list(votos.values()).count(max(votos.values())) > 1:
        consenso = "dividido"
        recomendada = None
    elif votos[recomendada] == len(validas):
        consenso = "unanime"
    else:
        consenso = "maioria"
    argumentos = {}
    for voto in votos:
        argumentos[voto] = next((r.get("por_que", "") for r in validas if r.get("voto") == voto), "")
    return {"fechada_em": _iso(), "contagem": votos, "consenso": consenso,
            "recomendada": recomendada, "respostas": len(validas), "argumentos": argumentos,
            "minoria": [ia for ia, r in respostas.items() if recomendada and r.get("voto") and r.get("voto") != recomendada],
            "ausentes": [ia for ia, r in respostas.items() if r.get("situacao") != "respondeu"]}


def _registrar_evento(dados):
    """Ponto pequeno para os testes nunca escreverem no diario real."""
    try:
        from builds import atividade
        atividade.registrar("assembleia", "ok", f"assembleia {dados['id']} fechada", "ias",
                            etapa="assembleia", ref=dados["id"])
    except Exception:
        pass


def _avisar(dados):
    try:
        from ias.carteiro import avisar_telegram
        avisar_telegram(f"Assembleia fechada: {dados['pergunta'][:100]}")
    except Exception:
        pass


def _fechar(dados):
    dados["ata"] = _ata(dados)
    dados["situacao"] = "fechada"
    recomendada = dados["ata"].get("recomendada")
    if dados["opcoes"]:
        opcoes = []
        for opcao in dados["opcoes"]:
            rotulo = opcao["rotulo"]
            if recomendada and opcao["id"] == recomendada:
                rotulo += f" (assembleia {dados['ata']['contagem'][recomendada]} de {dados['ata']['respostas']})"
            opcoes.append({"id": opcao["id"], "rotulo": rotulo, "descricao": opcao.get("descricao", "")})
        contexto = ("Ata da assembleia: consenso " + dados["ata"]["consenso"] + ". " +
                    "; ".join(f"{k}: {v}" for k, v in dados["ata"]["argumentos"].items() if v))[:1500]
        try:
            from remoto import decisoes
            item, _ = decisoes.adicionar_e_commitar(dados["projeto"], "Assembleia: " + dados["pergunta"][:80],
                                                     dados["pergunta"], opcoes, contexto=contexto)
            dados["decisao_id"] = item.get("id")
        except Exception as exc:  # o fechamento e mais importante que o commit
            dados["erro_grimorio"] = f"{type(exc).__name__}: {exc}"[:300]
    _registrar_evento(dados)
    _avisar(dados)


def avancar():
    """Colhe uma resposta ou abre/fecha uma rodada em cada assembleia aberta."""
    for dados in listar():
        if dados.get("situacao") == "rodada_1":
            terminou = _colher(dados, "rodada_1", 1)
            if terminou:
                presentes = sum(r.get("situacao") == "respondeu"
                                for r in dados["rodada_1"]["respostas"].values())
                if not presentes:
                    dados["rodada_2"] = {"aberta_em": _iso(), "mensagens": {}, "respostas": {}}
                    _fechar(dados)
                else:
                    _abrir_rodada_2(dados)
            _gravar(dados)
        elif dados.get("situacao") == "rodada_2":
            terminou = _colher(dados, "rodada_2", 2)
            if terminou:
                _fechar(dados)
            _gravar(dados)


def _mostrar(dados):
    if not dados:
        return "assembleia nao encontrada"
    ata = dados.get("ata") or {}
    linhas = [f"Assembleia {dados['id']}: {dados['pergunta']}", f"Situacao: {dados['situacao']}"]
    if ata:
        linhas.append(f"Ata: {ata.get('consenso')} — {ata.get('contagem')}")
        if ata.get("recomendada"):
            linhas.append("Recomendacao: " + ata["recomendada"])
    return "\n".join(linhas)


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="comando", required=True)
    abrir_p = sub.add_parser("abrir")
    abrir_p.add_argument("--pergunta", required=True)
    abrir_p.add_argument("--opcao", action="append")
    abrir_p.add_argument("--participantes")
    abrir_p.add_argument("--projeto", default="geral")
    abrir_p.add_argument("--contexto", required=True)
    sub.add_parser("avancar")
    ver_p = sub.add_parser("ver"); ver_p.add_argument("id")
    sub.add_parser("listar")
    args = parser.parse_args(argv)
    if args.comando == "abrir":
        print(abrir(args.pergunta, args.opcao, args.participantes.split(",") if args.participantes else None,
                    args.projeto, args.contexto))
    elif args.comando == "avancar":
        avancar()
    elif args.comando == "ver":
        print(_mostrar(ver(args.id)))
    else:
        for dados in listar():
            print(f"{dados['id']} {dados['situacao']} {dados['pergunta']}")


if __name__ == "__main__":
    main()
