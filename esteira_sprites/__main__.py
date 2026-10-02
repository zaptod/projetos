"""CLI idempotente para o coordenador chamar periodicamente."""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

import numpy as np
from ias import correio
from PIL import Image

from . import animacao, config, ficha, prompt
from .aprovar import aprovar, descartar, refazer
from .colher import colher
from .juiz import colher as colher_juiz
from .juiz import perguntar
from .limpar import limpar
from .pedir import pedir
from .portao import passar, validar


MESTRA_COMPARTILHADA = ("a Vila usa a imagem-mestra do Neural (decisao painel-e-vila/"
                        "vila-estilo-novo): gere e aprove pelo perfil palco")


def mestra() -> dict:
    if config.PERFIL != "palco":
        raise ValueError(MESTRA_COMPARTILHADA)
    texto = ("Imagem-mestra aprovada para sprites pixel-art de Neural Fights: "
             "bolinha com rosto, arma, projetil e impacto; contorno #14141A, "
             "cel de 2 tons, luz superior esquerda, fundo magenta #FF00FF.")
    return correio.pedir_imagem("chatgpt", texto, proporcao="1:1")


def mestra_aprovar(caminho: str) -> Path:
    if config.PERFIL != "palco":
        raise ValueError(MESTRA_COMPARTILHADA)
    origem = Path(caminho)
    if not origem.is_file():
        raise ValueError("imagem-mestra inexistente")
    destino = config.mestra()
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origem, destino)
    return destino


# Grupos cujo desenho depende de uma escolha do Adrian no Grimório: sem ela,
# o lote não gasta imagem num formato que pode ser trocado.
ESPERA_DECISAO = {"habitantes": ("painel-e-vila", "vila-habitante-forma")}
DECISOES = Path(__file__).resolve().parents[1] / "decisoes"


def _decisao_tomada(item: dict) -> bool:
    chave = ESPERA_DECISAO.get(str(item.get("grupo") or ""))
    if not chave:
        return True
    try:
        dados = json.loads((DECISOES / chave[0] / f"{chave[1]}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return dados.get("situacao") == "decidida"


# 02/10/2026, o Adrian: "achei suas animacoes um lixo... eu mesmo vou fazer
# esses sprites". As FOLHAS animadas nao sao mais pedidas a IA; ele importa as
# dele pelo Atelie do app. Pecas paradas (predios, chao) continuam.
FOLHAS_POR_IA = False


def lote(prioridade: str, n: int) -> list[str]:
    escolhidos = []
    if config.perfil().exige_mestra and not config.mestra().is_file():
        # sem a mestra, cada pedido sairia num estilo; nada e pedido
        print(f"perfil {config.PERFIL}: espera a imagem-mestra aprovada ({config.mestra()})")
        return escolhidos
    itens = sorted(config.itens(), key=lambda i: (i.get("ordem") is None, i.get("ordem") or 999999))
    for item in itens:
        if (item.get("prioridade") != prioridade or item.get("bloqueio") or item.get("opcional")
                or item.get("externo") or item["id"] == "imagem_mestra"
                or (item.get("tipo") == "folha" and not FOLHAS_POR_IA)
                or not _decisao_tomada(item)):
            continue
        existente = ficha.ler(item["id"])
        if existente and existente.get("estado") in ("pedido", "gerado", "limpo", "medido", "julgado", "a_conferir", "aprovado", "na_biblioteca"):
            continue
        pedir(item["id"])
        escolhidos.append(item["id"])
        if len(escolhidos) >= n:
            break
    return escolhidos


EM_VOO = ("pedido", "gerado", "limpo", "medido", "julgado")
# quantos itens ficam em producao ao mesmo tempo por perfil: o carteiro faz um
# por vez por conta, entao mais que isso so enche a fila
ALVO_EM_VOO = 4


def _repedir(item_id: str, dados: dict) -> bool:
    """`refazer` (falha do correio, imagem sem prova, ou pedido manual) volta a pedir."""
    from .juiz import MAX_TENTATIVAS, tentativas_contadas
    if tentativas_contadas(dados) >= MAX_TENTATIVAS:
        dados["estado"] = "a_conferir"
        ficha.registrar(dados, "tentativas_esgotadas")
        ficha.gravar(dados)
        return True
    ultima = (dados.get("tentativas") or [{}])[-1]
    motivo = str(ultima.get("erro") or ultima.get("motivo") or "")
    if ultima.get("erro") and ultima.get("prompt"):
        # o gerador falhou: o mesmo prompt de novo, igual (memoria imagem-estouro-de-espera)
        pedir(item_id, motivo, prompt_pronto=ultima["prompt"])
    else:
        pedir(item_id, motivo)
    return True


# 02/10/2026, o Adrian: "por que voce ainda esta gerando os sprites quando eu ja
# disse pra parar". A esteira inteira esta DESLIGADA: ele faz os sprites dele e
# importa pelo Atelie. Ligar de novo so com ordem dele.
ESTEIRA_LIGADA = False


def ciclo() -> dict:
    """Uma passada da producao continua: anda tudo e completa o que esta em voo."""
    if not ESTEIRA_LIGADA:
        return {"perfil": config.PERFIL, "andou": 0, "em_voo": 0, "novos": [],
                "desligada": "o Adrian mandou parar (02/10/2026)"}
    andou = avancar()
    em_voo = sum(1 for i in config.itens() if (d := ficha.ler(i["id"])) and d.get("estado") in EM_VOO)
    novos = []
    for prioridade in ("P1", "P2", "P3"):
        falta = ALVO_EM_VOO - em_voo - len(novos)
        if falta <= 0:
            break
        novos += lote(prioridade, falta)
    return {"perfil": config.PERFIL, "andou": andou, "em_voo": em_voo + len(novos), "novos": novos}


# Decisao painel-e-vila/folhas-chatgpt-ocupado (Adrian, 02/10/2026): folha
# espera ate COBERTURA_MIN pelo ChatGPT; se ele continuar ocupado (a criacao de
# historias segura a conta por horas), o Gemini faz. Se o juiz reprovar, o
# proximo pedido volta ao ChatGPT (o gerador padrao da folha).
COBERTURA_MIN = 20


def _cobrir_chatgpt_ocupado(item_id: str, dados: dict) -> bool:
    from datetime import datetime
    t = (dados.get("tentativas") or [{}])[-1]
    if t.get("caixa") != "chatgpt" or t.get("cobertura"):
        return False
    m = correio.uma("chatgpt", t.get("correio_id") or "") or {}
    if m.get("situacao") != "pendente":
        return False                       # ja entregue ou respondida: segue
    try:
        idade = (datetime.now() - datetime.fromisoformat(str(m.get("em"))[:19])).total_seconds() / 60
    except ValueError:
        return False
    if idade < COBERTURA_MIN:
        return False
    correio.atualizar("chatgpt", t["correio_id"], situacao="falhou", categoria="interrompida",
                      erro=f"o ChatGPT ficou ocupado {idade:.0f} min; o Gemini cobre (decisao "
                           "folhas-chatgpt-ocupado)")
    ficha.registrar(dados, "cobertura", de="chatgpt", para="gemini", espera_min=round(idade))
    ficha.gravar(dados)
    # a tentativa que nunca saiu nao conta: o pedido vai igual ao Gemini
    dados = ficha.ler(item_id)
    dados["tentativas"].pop()
    ficha.gravar(dados)
    pedir(item_id, str(t.get("motivo") or ""), prompt_pronto=str(t.get("prompt") or ""),
          caixa="gemini", cobertura=True)
    return True


def avancar() -> int:
    feitos = 0
    for item in config.itens():
        dados = ficha.ler(item["id"])
        if not dados:
            continue
        estado = dados.get("estado")
        if estado == "pedido" and _cobrir_chatgpt_ocupado(item["id"], dados):
            feitos += 1
            continue
        if estado == "refazer":
            feitos += bool(_repedir(item["id"], dados))
        elif estado == "pedido":
            feitos += bool(colher(item["id"]))
        elif estado == "gerado":
            feitos += bool(limpar(item["id"]))
        elif estado == "limpo":
            feitos += bool(passar(item["id"]))
        elif estado == "medido":
            feitos += bool(perguntar(item["id"]))
        elif estado == "julgado":
            feitos += bool(colher_juiz(item["id"]))
    return feitos


def status() -> Counter:
    return Counter(d.get("estado", "sem_ficha") for i in config.itens()
                   if (d := ficha.ler(i["id"])))


def medir(item_id: str, png: str) -> dict:
    """O portao num png solto, com a previa ao lado (`<nome>_previa.gif`)."""
    item = config.item(item_id)
    resultado = validar(item, png)
    if prompt.animacao(item) is not None:
        arr = np.asarray(Image.open(png).convert("RGBA"))
        resultado["previa"] = animacao.previa(arr, item, Path(png).with_name(Path(png).stem + "_previa"))
    return resultado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Esteira de sprites")
    parser.add_argument("--perfil", choices=sorted(config.PERFIS), default="palco",
                        help="biblia de estilo, pasta das fichas e destino (padrao: palco)")
    parser.add_argument("--inventario", default=None,
                        help="outro inventario JSON (padrao: o do perfil)")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_medir = sub.add_parser("medir", help="passa um png pelo portao sem ficha (calibrar)")
    p_medir.add_argument("item")
    p_medir.add_argument("png")
    sub.add_parser("mestra")
    mestre = sub.add_parser("mestra-aprovar")
    mestre.add_argument("caminho")
    p_pedir = sub.add_parser("pedir")
    p_pedir.add_argument("item")
    p_lote = sub.add_parser("lote")
    p_lote.add_argument("--prioridade", required=True)
    p_lote.add_argument("--n", type=int, default=5)
    sub.add_parser("avancar")
    sub.add_parser("ciclo", help="anda tudo e mantem a producao cheia (o coordenador chama)")
    sub.add_parser("status")
    p_aprovar = sub.add_parser("aprovar")
    p_aprovar.add_argument("item")
    p_refazer = sub.add_parser("refazer")
    p_refazer.add_argument("item")
    p_refazer.add_argument("--motivo", required=True)
    p_descartar = sub.add_parser("descartar")
    p_descartar.add_argument("item")
    args = parser.parse_args(argv)
    config.usar(args.perfil, args.inventario)
    if args.comando == "medir":
        print(json.dumps(medir(args.item, args.png), ensure_ascii=False, indent=2))
    elif args.comando == "mestra":
        print(mestra()["id"])
    elif args.comando == "mestra-aprovar":
        print(mestra_aprovar(args.caminho))
    elif args.comando == "pedir":
        pedir(args.item)
    elif args.comando == "lote":
        print("\n".join(lote(args.prioridade, args.n)))
    elif args.comando == "avancar":
        print(avancar())
    elif args.comando == "ciclo":
        print(json.dumps(ciclo(), ensure_ascii=False))
    elif args.comando == "status":
        for estado, quantidade in sorted(status().items()):
            print(f"{estado}: {quantidade}")
    elif args.comando == "aprovar":
        aprovar(args.item)
    elif args.comando == "refazer":
        refazer(args.item, args.motivo)
    else:
        descartar(args.item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
