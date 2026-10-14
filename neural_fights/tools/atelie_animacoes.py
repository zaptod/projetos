"""Dados do Atelie novo: folhas, contrato, ajustes e fatiamento."""
from __future__ import annotations

import io
import json
import math
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from neural_fights.tools import catalogo_animacoes
from neural_fights.tools import catalogo_vila
from neural_fights.tools import consumo_atelie


RAIZ = Path(__file__).resolve().parents[2]
BIBLIOTECA = RAIZ / "palco" / "biblioteca"
CATALOGO = BIBLIOTECA / "catalogo_animacoes.json"
AJUSTES = BIBLIOTECA / "catalogo_ajustes.json"
ANIMACOES = BIBLIOTECA / "animacoes"
VERSAO = 1
_ID = re.compile(r"[a-z0-9][a-z0-9_.-]{0,100}")


def _id(valor: object, nome: str) -> str:
    valor = str(valor or "")
    if valor in (".", "..") or not _ID.fullmatch(valor):
        raise ValueError(f"{nome} invalido")
    return valor


def _json(caminho: Path, padrao: dict) -> dict:
    try:
        valor = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao
    return valor if isinstance(valor, dict) else padrao


def _atomico(caminho: Path, bruto: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=caminho.parent, delete=False) as tmp:
        tmp.write(bruto)
        nome = tmp.name
    os.replace(nome, caminho)


def caminho(peca: object, estado: object, animacao: object) -> Path:
    return ANIMACOES / _id(peca, "peca") / _id(estado, "estado") / _id(animacao, "animacao")


def _finito(valor: object, campo: str) -> float:
    """``float(valor)`` exigindo numero finito (MOT-111)."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{campo} precisa ser um numero finito") from None
    if not math.isfinite(numero):
        raise ValueError(f"{campo} precisa ser um numero finito")
    return numero


def validar(dados: dict, tamanho: tuple[int, int]) -> dict:
    if not isinstance(dados, dict):
        raise ValueError("animacao.json precisa ser um objeto")
    quadros = dados.get("quadros")
    if not isinstance(quadros, list) or not quadros:
        raise ValueError("quadros precisa ter ao menos um retangulo")
    largura, altura = tamanho
    normalizados = []
    for indice, quadro in enumerate(quadros):
        if not isinstance(quadro, dict):
            raise ValueError(f"quadro {indice} invalido")
        try:
            x, y, w, h = (int(quadro[chave]) for chave in ("x", "y", "w", "h"))
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"quadro {indice} precisa de x, y, w e h") from None
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > largura or y + h > altura:
            raise ValueError(f"quadro {indice} fora da folha")
        normalizados.append({"x": x, "y": y, "w": w, "h": h})
    try:
        fps = float(dados.get("fps"))
    except (TypeError, ValueError):
        raise ValueError("fps precisa ser maior que zero") from None
    # MOT-111: NaN passava em ``fps <= 0`` e o JSON saia com NaN, que o
    # JSON.parse do app e o Godot recusam.
    if not math.isfinite(fps):
        raise ValueError("fps precisa ser um numero finito")
    if fps <= 0:
        raise ValueError("fps precisa ser maior que zero")
    ancora = dados.get("ancora", {})
    if not isinstance(ancora, dict) or not all(isinstance(ancora.get(k), (int, float)) for k in ("x", "y")):
        raise ValueError("ancora precisa ter x e y")
    for chave in ("x", "y"):
        _finito(ancora[chave], f"ancora.{chave}")
    duracoes = dados.get("duracao_por_quadro")
    if duracoes is not None:
        if not isinstance(duracoes, dict):
            raise ValueError("duracao_por_quadro invalida")
        for k, v in duracoes.items():
            valor = _finito(v, f"duracao_por_quadro[{k}]")
            if not str(k).isdigit() or int(k) >= len(quadros) or valor <= 0:
                raise ValueError("duracao_por_quadro invalida")
    escala = _finito(dados.get("escala", 1), "escala")
    rotacao = _finito(dados.get("rotacao", 0), "rotacao")
    resultado = dict(dados)
    resultado.update({"quadros": normalizados, "fps": fps, "loop": bool(dados.get("loop")),
                      "ida_e_volta": bool(dados.get("ida_e_volta")), "ancora": ancora,
                      "escala": escala, "rotacao": rotacao,
                      "espelho": bool(dados.get("espelho")), "gatilho": str(dados.get("gatilho", "")),
                      "versao": int(dados.get("versao", VERSAO))})
    return resultado


def _carimbo() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def salvar(peca: object, estado: object, animacao: object, folha: bytes, dados: dict) -> dict:
    try:
        imagem = Image.open(io.BytesIO(folha))
        imagem.verify()
        tamanho = Image.open(io.BytesIO(folha)).size
    except Exception as exc:
        raise ValueError("folha.png invalida") from exc
    contrato = validar(dados, tamanho)
    pasta = caminho(peca, estado, animacao)
    if (pasta / "animacao.json").is_file() or (pasta / "folha.png").is_file():
        destino = pasta / "historico" / _carimbo()
        destino.mkdir(parents=True)
        for nome in ("folha.png", "animacao.json"):
            origem = pasta / nome
            if origem.is_file():
                shutil.copy2(origem, destino / nome)
    _atomico(pasta / "folha.png", folha)
    _atomico(pasta / "animacao.json", json.dumps(contrato, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8"))
    return contrato


def ler(peca: object, estado: object, animacao: object) -> dict | None:
    pasta = caminho(peca, estado, animacao)
    dados = _json(pasta / "animacao.json", {})
    return dados or None


def desfazer(peca: object, estado: object, animacao: object) -> dict:
    pasta = caminho(peca, estado, animacao)
    anteriores = sorted((p for p in (pasta / "historico").glob("*") if p.is_dir()), reverse=True)
    if not anteriores:
        raise ValueError("nao ha versao anterior")
    anterior = anteriores[0]
    atual = pasta / "historico" / _carimbo()
    atual.mkdir(parents=True)
    for nome in ("folha.png", "animacao.json"):
        shutil.copy2(pasta / nome, atual / nome)
        os.replace(anterior / nome, pasta / nome)
    anterior.rmdir()
    return ler(peca, estado, animacao) or {}


FUNDOS_CHAVE = {"magenta": (255, 0, 255), "verde": (0, 255, 0)}
CHAVE_PERTO = 110    # distancia RGB: fundo (o magenta das IAs varia ~(233..252, 3..36, 235..252))
CHAVE_BORDA = 170    # ate aqui a orla do desenho fica semitransparente (sem franja)
CHAVE_PURA = 40      # buraco fechado desta cor dentro do desenho tambem e fundo
FUNDO_LISO_PERTO = 6    # fundo liso de outra cor: folga apertada (o contorno escuro fica)
FUNDO_LISO_BORDA = 14


def limpar_fundo(folha: bytes) -> tuple[bytes, str | None]:
    """Folha com fundo magenta/verde liso (sem transparencia) -> PNG transparente.

    08/10/2026: o Adrian subiu o Bot andando com fundo magenta (RGB, sem alfa)
    e o fundo entrou na animacao. O fundo sai por CONEXAO COM A BORDA (como o
    recortador antigo): o rosa da bochecha nao e apagado. Folha que ja tem
    transparencia volta igual. Devolve (png, "magenta"|"verde"|None)."""
    import numpy as np
    from PIL import ImageDraw

    imagem = Image.open(io.BytesIO(folha)).convert("RGBA")
    arr = np.array(imagem)
    if (arr[:, :, 3] < 16).mean() > 0.01:
        return folha, None
    rgb = arr[:, :, :3].astype(np.int32)
    borda = np.concatenate((rgb[:3].reshape(-1, 3), rgb[-3:].reshape(-1, 3),
                            rgb[:, :3].reshape(-1, 3), rgb[:, -3:].reshape(-1, 3)))
    nome, cor, fracao = None, None, 0.0
    perto_lim, borda_lim, pura_lim = CHAVE_PERTO, CHAVE_BORDA, CHAVE_PURA
    for candidato, chave in FUNDOS_CHAVE.items():
        perto = (np.sqrt(((borda - chave) ** 2).sum(axis=1)) <= CHAVE_PERTO).mean()
        if perto > fracao:
            nome, cor, fracao = candidato, chave, float(perto)
    if fracao < 0.6:
        # Fundo liso de OUTRA cor (08/10: a Arena veio em cinza-escuro 37,40,43):
        # a cor mediana da borda, com folga apertada para nao comer o contorno
        # escuro do desenho (o contorno do Neural e #14141A).
        # Ate 3 cores dominantes da borda (fundo preto + linhas de grade cinza).
        # faixa larga: a borda de uma folha em grade pode ser so a linha da grade,
        # e o fundo de verdade (o preto da Arena) comeca logo depois dela
        borda = np.concatenate((rgb[:14].reshape(-1, 3), rgb[-14:].reshape(-1, 3),
                                rgb[:, :14].reshape(-1, 3), rgb[:, -14:].reshape(-1, 3)))
        bins = (borda // 16).astype(np.int64)
        codigos = bins[:, 0] * 256 + bins[:, 1] * 16 + bins[:, 2]
        valores, contagens = np.unique(codigos, return_counts=True)
        ordem = np.argsort(-contagens)
        cores, coberto = [], 0
        for k in ordem[:6]:              # fundo, grade e as faixas de transicao entre eles
            cores.append(borda[codigos == valores[k]].mean(axis=0))
            coberto += contagens[k]
            if coberto >= 0.98 * len(borda):
                break
        if coberto < 0.85 * len(borda):
            return folha, None
        nome = "liso"
        dist = np.min([np.sqrt(((rgb - c) ** 2).sum(axis=2)) for c in cores], axis=0)
        perto_lim, borda_lim, pura_lim = FUNDO_LISO_PERTO, FUNDO_LISO_BORDA, -1
    else:
        dist = np.sqrt(((rgb - np.array(cor)) ** 2).sum(axis=2))
    # .copy(): a imagem que sai do numpy e somente-leitura e o floodfill do
    # Pillow 12 pintava uma copia e jogava fora (o balde nao fazia nada)
    mascara = Image.fromarray(np.where(dist <= perto_lim, 255, 0).astype(np.uint8)).copy()
    h, w = dist.shape
    pixels = mascara.load()
    for x, y in [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] + \
                [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]:
        if pixels[x, y] == 255:
            ImageDraw.floodfill(mascara, (x, y), 128)
    # Area GRANDE da cor do fundo e fundo mesmo sem tocar a borda (a Arena: o
    # preto de cada celula fica isolado da grade por uma faixa de transicao);
    # area pequena (pupila, brilho) e desenho. 08/10/2026.
    minimo = 0.004 * w * h
    for y in range(0, h, 16):
        for x in range(0, w, 16):
            if pixels[x, y] != 255:
                continue
            ImageDraw.floodfill(mascara, (x, y), 77)
            vetor = np.array(mascara)
            area = int((vetor == 77).sum())
            ImageDraw.floodfill(mascara, (x, y), 128 if area >= minimo else 50)
            pixels = mascara.load()
    fundo = (np.array(mascara) == 128) | (dist <= pura_lim)
    if nome == "liso":
        # Linhas de GRADE (a Arena: cinza entre os quadros, picadas pela faixa de
        # transicao): linha/coluna inteira que e quase so fundo + cor de fundo sai.
        perto_da_cor = dist <= 3 * FUNDO_LISO_BORDA
        for y in np.where((fundo | perto_da_cor).mean(axis=1) > 0.97)[0]:
            fundo[y] |= perto_da_cor[y]
        for x in np.where((fundo | perto_da_cor).mean(axis=0) > 0.97)[0]:
            fundo[:, x] |= perto_da_cor[:, x]
    alfa = arr[:, :, 3].astype(np.float32)
    # orla = so o que ENCOSTA no fundo (antes: todo pixel escuro, e as pupilas e o
    # contorno preto da Arena sumiam, 08/10)
    from PIL import ImageFilter
    vizinho = np.array(Image.fromarray((fundo * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0
    orla = ~fundo & vizinho & (dist < borda_lim)
    alfa[orla] *= np.clip((dist[orla] - perto_lim) / (borda_lim - perto_lim), 0, 1)
    alfa[fundo] = 0
    saida = arr.copy()
    saida[:, :, 3] = alfa.astype(np.uint8)
    saida[fundo, :3] = 0
    bruto = io.BytesIO()
    Image.fromarray(saida).save(bruto, "PNG")
    return bruto.getvalue(), nome


ALFA_TINTA = 24      # abaixo disto e veu de remocao de fundo, nao desenho
RUIDO = 2            # pixels soltos numa faixa que nao fazem desenho


def fatiar_automatico(folha: bytes | Image.Image) -> list[dict]:
    """Quadros de uma folha com transparencia, na ordem de leitura.

    08/10/2026, folha real do Adrian (1942x809, 6x5 com 26 desenhos): o
    corte antigo usava alfa > 0 e o veu quase invisivel que sobra da remocao
    de fundo virava UM quadro do tamanho da folha. Agora: tinta = alfa acima
    de ALFA_TINTA em mais de RUIDO pixels da faixa; se as faixas cabem numa
    grade de celulas iguais (o jeito que as folhas sao feitas), os quadros sao
    essas celulas (mesmo tamanho = a animacao nao treme); celula sem tinta
    (fim da ultima linha) sai."""
    imagem = folha if isinstance(folha, Image.Image) else Image.open(io.BytesIO(folha))
    alfa = imagem.convert("RGBA").getchannel("A")
    w, h = imagem.size
    tinta = alfa.point(lambda v: 255 if v > ALFA_TINTA else 0)
    px = tinta.load()
    por_coluna = [sum(1 for y in range(h) if px[x, y]) for x in range(w)]
    por_linha = [sum(1 for x in range(w) if px[x, y]) for y in range(h)]

    def faixas(contagens):
        inicio, saida = None, []
        for i, valor in enumerate([*contagens, 0]):
            if valor > RUIDO and inicio is None: inicio = i
            if valor <= RUIDO and inicio is not None:
                saida.append((inicio, i)); inicio = None
        return saida

    xs, ys = faixas(por_coluna), faixas(por_linha)
    if not xs or not ys:
        return []

    def celulas(bandas, total):
        n = len(bandas); passo = total / n
        cabem = all(int(i * passo) <= a and b <= int((i + 1) * passo) + 1 for i, (a, b) in enumerate(bandas))
        if cabem:
            return [(int(i * passo), int(passo)) for i in range(n)]     # todas do mesmo tamanho
        lado = max(b - a for a, b in bandas)              # faixas irregulares: caixa igual centrada
        return [(max(0, min(total - lado, (a + b) // 2 - lado // 2)), lado) for a, b in bandas]

    quadros = []
    for y0, ah in celulas(ys, h):
        for x0, lw in celulas(xs, w):
            recorte = tinta.crop((x0, y0, x0 + lw, y0 + ah))
            if recorte.getbbox() is None:
                continue
            quadros.append({"x": x0, "y": y0, "w": lw, "h": ah})
    return quadros


def fatiar_grade(largura: int, altura: int, linhas: int, colunas: int, margem: int = 0, espaco: int = 0) -> list[dict]:
    if linhas <= 0 or colunas <= 0 or margem < 0 or espaco < 0:
        raise ValueError("linhas, colunas, margem e espaco invalidos")
    w = (largura - 2 * margem - (colunas - 1) * espaco) // colunas
    h = (altura - 2 * margem - (linhas - 1) * espaco) // linhas
    if w <= 0 or h <= 0: raise ValueError("grade fora da folha")
    return [{"x": margem + c * (w + espaco), "y": margem + r * (h + espaco), "w": w, "h": h}
            for r in range(linhas) for c in range(colunas)]


def ajustes() -> dict:
    dados = _json(AJUSTES, {"novas": [], "escondidas": []})
    if not isinstance(dados, dict):
        dados = {}
    # MOT-112: um arquivo ja estragado (item que nao e dict/str) derrubava a
    # arvore inteira com AttributeError; a leitura filtra em silencio.
    novas = dados.get("novas") if isinstance(dados.get("novas"), list) else []
    escondidas = dados.get("escondidas") if isinstance(dados.get("escondidas"), list) else []
    dados["novas"] = [n for n in novas if isinstance(n, dict) and n.get("peca") and n.get("estado") and n.get("id")]
    dados["escondidas"] = [e for e in escondidas if isinstance(e, str)]
    return dados


def salvar_ajustes(dados: dict) -> dict:
    if not isinstance(dados, dict): raise ValueError("ajustes invalidos")
    novas = list(dados.get("novas") or [])
    escondidas = list(dados.get("escondidas") or [])
    # MOT-112: o endpoint aceitava qualquer item e o GET da arvore passava a
    # dar 500 em toda abertura do Atelie.
    for item in novas:
        if not isinstance(item, dict):
            raise ValueError("ajustes invalidos")
        try:
            _id(item.get("peca"), "peca"); _id(item.get("estado"), "estado"); _id(item.get("id"), "animacao")
        except ValueError:
            raise ValueError("ajustes invalidos") from None
    if not all(isinstance(e, str) for e in escondidas):
        raise ValueError("ajustes invalidos")
    dados = {"novas": novas, "escondidas": escondidas}
    _atomico(AJUSTES, json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8"))
    return dados


def criar_animacao(peca: object, estado: object, animacao: dict) -> dict:
    item = {"peca": _id(peca, "peca"), "estado": _id(estado, "estado"), **dict(animacao)}
    item["id"] = _id(item.get("id"), "animacao")
    item["gatilho"] = str(item.get("gatilho") or "")
    dados = ajustes(); dados["novas"] = [n for n in dados["novas"] if not (n.get("peca") == item["peca"] and n.get("estado") == item["estado"] and n.get("id") == item["id"])] + [item]
    salvar_ajustes(dados); return item


def esconder_animacao(peca: object, estado: object, animacao: object) -> None:
    chave = "/".join((_id(peca, "peca"), _id(estado, "estado"), _id(animacao, "animacao")))
    dados = ajustes(); dados["escondidas"] = sorted(set(dados["escondidas"]) | {chave}); salvar_ajustes(dados)


def mostrar_animacao(peca: object, estado: object, animacao: object) -> None:
    """Desfaz o esconder (08/10: escondida nao tinha volta pela tela)."""
    chave = "/".join((_id(peca, "peca"), _id(estado, "estado"), _id(animacao, "animacao")))
    dados = ajustes(); dados["escondidas"] = sorted(set(dados["escondidas"]) - {chave}); salvar_ajustes(dados)


def gatilhos() -> list[dict]:
    catalogo = _json(CATALOGO, {})
    valores = {a.get("gatilho", "") for p in [*catalogo.get("pecas", []), *catalogo_vila.catalogo()] for e in p.get("estados", []) for a in e.get("animacoes", [])}
    return [{"id": v, "rotulo": catalogo_animacoes._rotulo(v)} for v in sorted(valores) if v]


def arvore() -> list[dict]:
    catalogo = _json(CATALOGO, {}); dados = ajustes(); ocultas = set(dados["escondidas"])
    pecas = {p.get("id"): json.loads(json.dumps(p)) for p in [*catalogo.get("pecas", []), *catalogo_vila.catalogo()] if p.get("id")}
    for nova in dados["novas"]:
        p = pecas.get(nova.get("peca"));
        if not p: continue
        estado = next((e for e in p.get("estados", []) if e.get("id") == nova.get("estado")), None)
        if estado is None: estado = {"id": nova["estado"], "rotulo": nova["estado"], "animacoes": []}; p.setdefault("estados", []).append(estado)
        estado.setdefault("animacoes", []).append({k: v for k, v in nova.items() if k not in ("peca", "estado")})
    for p in pecas.values():
        p["aparece_em"] = consumo_atelie.aparece_em(p["id"], p.get("grupo", ""))
        p["consumidores"] = consumo_atelie.consumidores(p["id"], p.get("grupo", ""))
        p["motivo_sem_consumidor"] = consumo_atelie.motivo_sem_consumidor(
            p["id"], p.get("grupo", "")) if not p["consumidores"] else ""
        for e in p.get("estados", []):
            e["escondidas"] = [{"id": a["id"], "rotulo": a.get("rotulo") or a["id"]} for a in e.get("animacoes", [])
                               if "/".join((p["id"], e["id"], a["id"])) in ocultas]
            e["animacoes"] = [a for a in e.get("animacoes", []) if "/".join((p["id"], e["id"], a["id"])) not in ocultas]
            for a in e["animacoes"]:
                if (caminho(p["id"], e["id"], a["id"]) / "folha.png").is_file(): a["tem_arte"] = True
                else:
                    a["tem_arte"] = False
                    for herdada in p.get("heranca", []):
                        if (caminho(herdada, e["id"], a["id"]) / "folha.png").is_file(): a["usa_a_de"] = herdada; break
    grupos = {}
    for p in pecas.values(): grupos.setdefault(p.get("grupo", "outros"), []).append(p)
    return [{"grupo": g, "pecas": sorted(v, key=lambda p: p["id"])} for g, v in sorted(grupos.items())]


# A previsualizacao do app e deliberadamente calculada aqui, e nao em JS: o
# ponto de uma folha e a ancora do Godot (`Rect2(-ancora, tamanho)`).  `posicao`
# e o ponto da ancora no palco 320x180; `escala` transforma o maior lado do
# quadro no tamanho indicado pelo catalogo (em corpos de 80 px).
def montagem(editar: dict | None = None) -> dict:
    """Camadas ociosas de um lutador de exemplo, no mesmo contrato do Godot."""
    catalogo = _json(CATALOGO, {}).get("pecas", [])
    por_id = {p.get("id"): p for p in catalogo if isinstance(p, dict)}
    escolhidas = []
    # Uma base e uma peca de cada familia visual; a editada sempre a substitui.
    grupos = ("lutador", "arma", "skill", "efeito", "estado_personagem", "buff")
    for grupo in grupos:
        peca = next((p for p in catalogo if p.get("grupo") == grupo), None)
        if peca: escolhidas.append(peca)
    if editar and por_id.get(editar.get("peca")):
        peca = por_id[editar["peca"]]
        escolhidas = [p for p in escolhidas if p.get("grupo") != peca.get("grupo")] + [peca]
    camadas = []
    for peca in escolhidas:
        estado = next((e for e in peca.get("estados", []) if any(a.get("gatilho") == "ocioso" for a in e.get("animacoes", []))), None)
        estado = estado or (peca.get("estados") or [{}])[0]
        animacao = next((a for a in estado.get("animacoes", []) if a.get("gatilho") == "ocioso"), None)
        animacao = animacao or (estado.get("animacoes") or [{}])[0]
        if editar and peca.get("id") == editar.get("peca"):
            estado = {"id": editar.get("estado", estado.get("id"))}
            animacao = {**animacao, **editar}
        fonte = peca.get("id")
        for candidato in [fonte] + list(peca.get("heranca", [])):
            if (caminho(candidato, estado.get("id"), animacao.get("id")) / "folha.png").is_file():
                fonte = candidato; break
        else: fonte = None
        segue = animacao.get("segue", "lutador")
        posicao = {"mao do lutador": {"x": 205, "y": 112}, "mao": {"x": 205, "y": 112},
                    "lutador": {"x": 160, "y": 100}, "corrente": {"x": 225, "y": 115}}.get(segue, {"x": 160, "y": 100})
        try: tamanho = float(str(animacao.get("tamanho_padrao", "1")).replace(",", ".").split()[0])
        except ValueError: tamanho = 1.0
        camadas.append({"peca": peca.get("id"), "estado": estado.get("id"), "animacao": animacao.get("id"),
                        "fonte": fonte, "camada": int(animacao.get("camada", 20)), "segue": segue,
                        "posicao": posicao, "tamanho": tamanho * 80, "marcador": fonte is None,
                        "categoria_marcador": {"lutador": "lutadores", "arma": "armas"}.get(peca.get("grupo"), "efeitos"),
                        "folha_url": f"/api/animacoes/{fonte}/{estado.get('id')}/{animacao.get('id')}/folha" if fonte else None,
                        "animacao_url": f"/api/animacoes/{fonte}/{estado.get('id')}/{animacao.get('id')}" if fonte else None})
    return {"largura": 320, "altura": 180, "camadas": sorted(camadas, key=lambda c: c["camada"])}
