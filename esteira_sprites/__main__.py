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

from . import animacao, config, ficha, ja_feito, prompt
from .aprovar import aprovar, descartar, refazer
from .colher import colher
from .juiz import colher as colher_juiz
from .juiz import perguntar
from .limpar import limpar
from .pedir import GERADOR, pedir
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


# 02/10/2026 o Adrian desligou as folhas ("achei suas animacoes um lixo... eu
# mesmo vou fazer esses sprites"). 14/10/2026 ele mandou voltar: "Agora que tudo
# ja esta mais limpo e organizado quero que voce volte a utilizar o ChatGPT para
# os sprites". Pecas paradas E folhas animadas voltam a ser pedidas, todas ao
# ChatGPT; o que ele ja fez pelo Atelie nunca e pedido (`ja_feito.py`).
FOLHAS_POR_IA = True

# Estados em que a ficha ja esta na esteira (o `refazer` o `avancar` repede).
JA_NA_ESTEIRA = ("pedido", "gerado", "limpo", "medido", "julgado", "a_conferir",
                 "aprovado", "na_biblioteca", "refazer")
# Descarte: os de antes do religamento foram a PARADA da esteira (02/10/2026,
# 01:03 e 16:42, tudo o que estava em voo), nao um "nao quero" do Adrian: o item
# volta a fila com a contagem de tentativas zerada. O que ele descartar pela tela
# de conferencia daqui em diante fica fora (antes, o ciclo seguinte repedia).
RELIGADA_EM = "2026-10-14"


def _descarte_do_adrian(dados: dict) -> bool:
    descartes = [str(e.get("em") or "") for e in dados.get("historico", []) if e.get("tipo") == "descartado"]
    return bool(descartes) and descartes[-1] >= RELIGADA_EM


def lote(prioridade: str, n: int, seco: bool = False) -> list[str]:
    """Pede ate `n` itens da prioridade. `seco`: so diz quais pediria (nada e gravado)."""
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
        if existente and existente.get("estado") in JA_NA_ESTEIRA:
            continue
        if existente and existente.get("estado") == "descartado" and _descarte_do_adrian(existente):
            continue
        if ja_feito.motivo(item):
            # o Adrian fez pelo Atelie, ou a arte ja esta na biblioteca
            continue
        if not seco:
            if existente and existente.get("tentativas"):
                # volta da parada: as tentativas de antes nao gastam o teto de agora
                existente["contar_desde"] = len(existente["tentativas"])
                ficha.registrar(existente, "volta_a_fila", de=existente.get("estado"))
                ficha.gravar(existente)
            pedir(item["id"])
        escolhidos.append(item["id"])
        if len(escolhidos) >= n:
            break
    return escolhidos


EM_VOO = ("pedido", "gerado", "limpo", "medido", "julgado")
# Quantos itens ficam em producao ao mesmo tempo POR PERFIL (14/10/2026: 2).
# O ChatGPT tambem faz as imagens das historias pelo rodizio e o carteiro
# entrega um pedido por vez por conta: com 2 por perfil a esteira tem no maximo
# 4 imagens na fila dele, e as historias continuam passando entre elas.
ALVO_EM_VOO = 2


def _ultima(dados: dict) -> dict:
    return (dados.get("tentativas") or [{}])[-1]


def _de_outro_gerador(dados: dict) -> bool:
    """Ficha em producao cuja imagem saiu (ou sairia) de outra IA: o Gemini de antes de 14/10."""
    if dados.get("estado") not in EM_VOO or not dados.get("tentativas"):
        return False
    # sem `caixa` e ficha antiga do ChatGPT (o `colher` assume o mesmo)
    return str(_ultima(dados).get("caixa") or GERADOR) != GERADOR


def _parar_outro_gerador(dados: dict) -> bool:
    """Cancela no correio o que a outra IA ainda nao fez (gerar ou julgar). Idempotente."""
    t = _ultima(dados)
    parou = False
    for caixa, mid in ((t.get("caixa"), t.get("correio_id")), (t.get("juiz_caixa"), t.get("juiz_id"))):
        if not caixa or not mid:
            continue
        mensagem = correio.uma(caixa, mid) or {}
        if mensagem.get("situacao") == "pendente":
            correio.atualizar(caixa, mid, situacao="falhou", categoria="interrompida",
                              erro="a esteira so usa o ChatGPT desde 14/10/2026 (ordem do Adrian)")
            parou = True
    return parou


def _trocar_para_chatgpt(item_id: str, dados: dict) -> bool:
    """A ficha de outro gerador volta a ser pedida, igual, ao ChatGPT.

    A tentativa da outra IA fica na ficha (auditoria), mas nao gasta o teto de
    MAX_TENTATIVAS: `contar_desde` anda uma casa."""
    _parar_outro_gerador(dados)
    t = _ultima(dados)
    t["trocado_para"] = GERADOR
    dados["contar_desde"] = int(dados.get("contar_desde") or 0) + 1
    ficha.registrar(dados, "gerador_trocado", de=t.get("caixa"), para=GERADOR)
    ficha.gravar(dados)
    # o motivo do pedido (nao o que o portao achou na imagem da outra IA)
    pedidos = [h for h in dados.get("historico", []) if h.get("tipo") == "pedido"]
    motivo = str((pedidos[-1].get("motivo") if pedidos else "") or "")
    pronto = str(t.get("prompt") or "") if t.get("prompt_do_juiz") else ""
    pedir(item_id, motivo, prompt_pronto=pronto)
    return True


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


# 02/10/2026 o Adrian desligou a esteira inteira ("por que voce ainda esta
# gerando os sprites quando eu ja disse pra parar"). 14/10/2026 ele mandou
# religar com o ChatGPT gerando todos os sprites (ordem no chat, ver o FOLHAS_POR_IA
# acima). A aprovacao final continua dele: nada sai de `a_conferir` para a
# biblioteca sem o `aprovar` (tela de conferencia do app ou comando).
ESTEIRA_LIGADA = True


def _em_voo_chatgpt() -> int:
    return sum(1 for i in config.itens()
               if (d := ficha.ler(i["id"])) and d.get("estado") in EM_VOO and not _de_outro_gerador(d))


def ciclo() -> dict:
    """Uma passada da producao continua: anda tudo e completa o que esta em voo."""
    if not ESTEIRA_LIGADA:
        return {"perfil": config.PERFIL, "andou": 0, "em_voo": 0, "novos": [],
                "desligada": "a esteira esta desligada (ESTEIRA_LIGADA)"}
    andou = avancar()
    em_voo = _em_voo_chatgpt()
    novos = []
    # primeiro as fichas que outra IA tinha comecado, dentro do mesmo teto
    for item in config.itens():
        if em_voo + len(novos) >= ALVO_EM_VOO:
            break
        dados = ficha.ler(item["id"])
        if dados and _de_outro_gerador(dados) and _trocar_para_chatgpt(item["id"], dados):
            novos.append(item["id"])
    for prioridade in ("P1", "P2", "P3"):
        falta = ALVO_EM_VOO - em_voo - len(novos)
        if falta <= 0:
            break
        novos += lote(prioridade, falta)
    return {"perfil": config.PERFIL, "andou": andou, "em_voo": em_voo + len(novos), "novos": novos}


def avancar() -> int:
    feitos = 0
    for item in config.itens():
        dados = ficha.ler(item["id"])
        if not dados:
            continue
        estado = dados.get("estado")
        if _de_outro_gerador(dados):
            # imagem de outra IA nao anda: espera o `ciclo` refazer no ChatGPT
            # quando houver vaga; o que ela ainda nao fez e cancelado ja
            feitos += bool(_parar_outro_gerador(dados))
            continue
        # ChatGPT ocupado (a criacao de historias segura a conta): a ficha ESPERA
        # em "pedido"; nao ha mais cobertura pelo Gemini (14/10/2026)
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
    p_lote.add_argument("--seco", action="store_true",
                        help="so lista o que pediria: nao grava ficha nem manda ao correio")
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
        print("\n".join(lote(args.prioridade, args.n, seco=args.seco)))
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
