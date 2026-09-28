# -*- coding: utf-8 -*-
"""A timeline em disco: JSON e o container comprimido que o Godot abre NATIVO.

Dois formatos, o MESMO conteudo (o dict de ``timeline.SondaTimeline``):

- ``.json``: UTF-8, sem espaco. E o que se abre para olhar e o que o palco le
  com ``JSON.parse_string(FileAccess.get_file_as_string(caminho))``.
- ``.gcpf``: o MESMO texto JSON dentro do container de
  ``FileAccess.open_compressed`` do Godot 4. O ``open_compressed`` NAO le
  gzip comum: ele espera o formato do ``FileAccessCompressed`` —

      "GCPF" | modo u32 | tamanho do bloco u32 | total descomprimido u32 |
      tamanho comprimido de cada um dos (total // bloco + 1) blocos, u32 |
      os blocos, cada um comprimido SOZINHO | "GCPF"

  (inteiros little-endian). O modo vem do cabecalho do arquivo: FASTLZ 0,
  DEFLATE 1 (zlib), ZSTD 2, GZIP 3. Aqui escrevemos DEFLATE, ZSTD e GZIP
  (FastLZ nao tem biblioteca no Python). No Godot::

      var f := FileAccess.open_compressed(caminho, FileAccess.READ,
                                          FileAccess.COMPRESSION_ZSTD)
      var doc = JSON.parse_string(f.get_as_text())

Conferido com o Godot 4.7.2 desta maquina (``E:\\ferramentas\\godot``): os tres
modos abrem e o texto sai byte a byte igual (md5). Ver docs/palco/timeline.md.

Tambem moram aqui o que o LEITOR precisa: ``validar`` (o schema, em codigo),
``quadro`` (o estado inteiro num passo) e o mapa de tempo do remapeamento.
"""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

from neural_fights.recording.timeline import (
    CANAIS_EFEITO,
    CANAIS_OBJETO,
    EXPRESSOES,
    FASES,
    FLAGS,
    FORMATO,
    NOMES_CANAIS_CAMERA,
    NOMES_CANAIS_GLOBAIS,
    NOMES_CANAIS_LUTADOR,
    VERSAO,
)

MAGICO = b"GCPF"
MODOS = {"fastlz": 0, "deflate": 1, "zstd": 2, "gzip": 3}
# O Godot escreve em blocos de 4 KiB, mas LE o tamanho do cabecalho. Bloco
# grande comprime muito melhor (cada bloco e comprimido sozinho) e o leitor
# so aloca um buffer desse tamanho.
BLOCO_PADRAO = 256 * 1024


# ------------------------------------------------------------ container GCPF
def _comprimir(dados: bytes, modo: str) -> bytes:
    if modo == "deflate":
        return zlib.compress(dados, 9)
    if modo == "gzip":
        compressor = zlib.compressobj(9, zlib.DEFLATED, 31)
        return compressor.compress(dados) + compressor.flush()
    if modo == "zstd":
        from compression import zstd
        return zstd.compress(dados, level=19)
    raise ValueError(f"compressao sem suporte aqui: {modo!r}")


def _descomprimir(dados: bytes, modo_id: int, tamanho: int) -> bytes:
    if tamanho == 0:
        return b""
    if modo_id == MODOS["deflate"]:
        saida = zlib.decompress(dados)
    elif modo_id == MODOS["gzip"]:
        saida = zlib.decompress(dados, 31)
    elif modo_id == MODOS["zstd"]:
        from compression import zstd
        saida = zstd.decompress(dados)
    else:
        raise ValueError(f"modo de compressao sem suporte aqui: {modo_id}")
    if len(saida) != tamanho:
        raise ValueError(f"bloco com {len(saida)} bytes, o cabecalho diz {tamanho}")
    return saida


def escrever_gcpf(dados: bytes, modo: str = "zstd", bloco: int = BLOCO_PADRAO) -> bytes:
    """Bytes no formato de ``FileAccessCompressed`` (Godot 4)."""
    if modo not in MODOS or modo == "fastlz":
        raise ValueError(f"modo invalido: {modo!r}")
    bloco = int(bloco)
    if bloco <= 0:
        raise ValueError("bloco precisa ser positivo")
    total = len(dados)
    quantidade = total // bloco + 1   # a MESMA conta do Godot (ultimo pode ser vazio)
    blocos = [_comprimir(dados[k * bloco:(k + 1) * bloco], modo) for k in range(quantidade)]
    cabecalho = MAGICO + struct.pack("<III", MODOS[modo], bloco, total)
    tabela = b"".join(struct.pack("<I", len(b)) for b in blocos)
    return cabecalho + tabela + b"".join(blocos) + MAGICO


def ler_gcpf(conteudo: bytes) -> bytes:
    """Inverso de ``escrever_gcpf``, com a mesma leitura do Godot."""
    if conteudo[:4] != MAGICO:
        raise ValueError("nao e um arquivo GCPF (magico ausente)")
    modo_id, bloco, total = struct.unpack_from("<III", conteudo, 4)
    if bloco == 0:
        raise ValueError("bloco de tamanho zero: arquivo corrompido")
    quantidade = total // bloco + 1
    tamanhos = struct.unpack_from(f"<{quantidade}I", conteudo, 16)
    posicao = 16 + 4 * quantidade
    partes = []
    for k, tamanho_c in enumerate(tamanhos):
        esperado = bloco if k < quantidade - 1 else total % bloco
        partes.append(_descomprimir(conteudo[posicao:posicao + tamanho_c], modo_id, esperado))
        posicao += tamanho_c
    if conteudo[posicao:posicao + 4] != MAGICO:
        raise ValueError("magico do fim ausente: arquivo truncado")
    return b"".join(partes)


# ------------------------------------------------------------ salvar/carregar
def para_bytes(doc: dict) -> bytes:
    """O JSON canonico: UTF-8, sem espaco, chaves na ordem do documento."""
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def salvar(doc: dict, caminho, *, compressao: str | None = None,
           bloco: int = BLOCO_PADRAO) -> int:
    """Grava a timeline. ``compressao`` None = JSON puro; ``zstd``, ``deflate``
    ou ``gzip`` = o JSON dentro do container GCPF. Devolve o tamanho em bytes."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados = para_bytes(doc)
    if compressao:
        dados = escrever_gcpf(dados, compressao, bloco)
    temporario = caminho.with_name(caminho.name + ".tmp")
    temporario.write_bytes(dados)
    temporario.replace(caminho)
    return len(dados)


def carregar(caminho) -> dict:
    """Le ``.json`` ou ``.gcpf`` (reconhece pelo magico, nao pela extensao)."""
    conteudo = Path(caminho).read_bytes()
    if conteudo[:4] == MAGICO:
        conteudo = ler_gcpf(conteudo)
    return json.loads(conteudo.decode("utf-8"))


# ------------------------------------------------------------ o schema
def validar(doc: dict) -> list[str]:
    """Problemas do documento contra o schema v1 (lista vazia = valido)."""
    problemas: list[str] = []
    if not isinstance(doc, dict):
        return ["o documento nao e um objeto"]
    if doc.get("formato") != FORMATO:
        problemas.append(f"formato {doc.get('formato')!r} != {FORMATO!r}")
    versao = doc.get("versao")
    if not isinstance(versao, int) or versao < 1 or versao > VERSAO:
        problemas.append(f"versao {versao!r} fora de 1..{VERSAO}")
    hz = doc.get("hz")
    n = doc.get("n")
    if not isinstance(hz, int) or hz <= 0:
        problemas.append(f"hz invalido: {hz!r}")
    if not isinstance(n, int) or n < 0:
        return problemas + [f"n invalido: {n!r}"]

    tabelas = doc.get("tabelas") or {}
    if list(tabelas.get("expressoes") or ()) != list(EXPRESSOES):
        problemas.append("tabelas.expressoes nao sao as 24 do jogo")
    if list(tabelas.get("fases") or ()) != list(FASES):
        problemas.append("tabelas.fases diferente de FASES")
    if list(tabelas.get("flags") or ())[:len(FLAGS)] != list(FLAGS):
        problemas.append("tabelas.flags nao comeca por FLAGS")
    if len(tabelas.get("planos") or ()) != len(tabelas.get("planos_tipo") or ()):
        problemas.append("tabelas.planos e planos_tipo com tamanhos diferentes")

    trilhas = doc.get("trilhas") or {}

    def conferir_canais(onde: str, canais, nomes, tamanho: int) -> None:
        if not isinstance(canais, dict):
            problemas.append(f"{onde}: ausente")
            return
        for nome in nomes:
            valores = canais.get(nome)
            if not isinstance(valores, list):
                problemas.append(f"{onde}.{nome}: ausente")
            elif len(valores) != tamanho:
                problemas.append(f"{onde}.{nome}: {len(valores)} valores, esperado {tamanho}")

    conferir_canais("trilhas.global", trilhas.get("global"), NOMES_CANAIS_GLOBAIS, n)
    conferir_canais("trilhas.camera", trilhas.get("camera"), NOMES_CANAIS_CAMERA, n)
    lutadores = trilhas.get("lutadores") or {}
    limites = {
        "expr": len(tabelas.get("expressoes") or ()),
        "acao": len(tabelas.get("acoes") or ()),
        "plano": len(tabelas.get("planos") or ()),
        "tell": len(tabelas.get("tells") or ()),
        "golpe_fase": len(FASES),
        "anim_fase": len(FASES),
    }
    for slot in ("p1", "p2"):
        canais = lutadores.get(slot)
        conferir_canais(f"trilhas.lutadores.{slot}", canais, NOMES_CANAIS_LUTADOR, n)
        if not isinstance(canais, dict):
            continue
        for nome, limite in limites.items():
            for valor in canais.get(nome) or ():
                if not isinstance(valor, int) or valor < -1 or valor >= max(limite, 0):
                    if not (valor == -1 and nome in ("acao", "plano", "tell")):
                        problemas.append(f"{slot}.{nome}: indice {valor!r} fora da tabela")
                        break

    ids = set()
    for grupo, canais_por_tipo in (("objetos", CANAIS_OBJETO), ("efeitos", CANAIS_EFEITO)):
        for trilha in trilhas.get(grupo) or ():
            ident = trilha.get("id")
            if ident in ids:
                problemas.append(f"{grupo}: id repetido {ident!r}")
            ids.add(ident)
            i0, i1 = trilha.get("i0"), trilha.get("i1")
            if not (isinstance(i0, int) and isinstance(i1, int) and 0 <= i0 <= i1 < n):
                problemas.append(f"{grupo} {ident}: intervalo [{i0}, {i1}] fora de [0, {n})")
                continue
            tipo = trilha.get("tipo")
            if tipo not in canais_por_tipo:
                problemas.append(f"{grupo} {ident}: tipo desconhecido {tipo!r}")
                continue
            for nome in canais_por_tipo[tipo]:
                valores = trilha.get(nome)
                if not isinstance(valores, list) or len(valores) != i1 - i0 + 1:
                    problemas.append(f"{grupo} {ident}.{nome}: nao tem {i1 - i0 + 1} valores")

    anterior = -1
    for evento in doc.get("eventos") or ():
        i = evento.get("i")
        if not isinstance(i, int) or not 0 <= i < n:
            problemas.append(f"evento fora da luta: {evento!r}")
            continue
        if i < anterior:
            problemas.append(f"eventos fora de ordem no passo {i}")
        anterior = i
        if not isinstance(evento.get("tipo"), str):
            problemas.append(f"evento sem tipo no passo {i}")

    sons = doc.get("sons")
    if sons is not None:
        itens = sons.get("itens") if isinstance(sons, dict) else None
        if not isinstance(itens, list):
            problemas.append("sons.itens ausente")
        else:
            tempos = [float(item.get("t", 0.0)) for item in itens]
            if tempos != sorted(tempos):
                problemas.append("sons fora de ordem de tempo")

    remapeamento = doc.get("remapeamento")
    if remapeamento is not None:
        fim_anterior = -1e9
        for trecho in remapeamento.get("trechos") or ():
            if len(trecho) != 3 or trecho[1] <= 0 or trecho[2] <= 0:
                problemas.append(f"trecho invalido: {trecho!r}")
                continue
            if trecho[0] < fim_anterior - 1e-6:
                problemas.append(f"trechos sobrepostos em {trecho!r}")
            fim_anterior = trecho[0] + trecho[1]
    return problemas


# ------------------------------------------------------------ leitura
def quadro(doc: dict, i: int) -> dict:
    """O estado inteiro no passo ``i``: o que o palco tem na mao para desenhar."""
    trilhas = doc["trilhas"]

    def fatia(canais: dict) -> dict:
        return {nome: valores[i] for nome, valores in canais.items()}

    vivos = []
    for grupo in ("objetos", "efeitos"):
        for trilha in trilhas.get(grupo) or ():
            if trilha["i0"] <= i <= trilha["i1"]:
                k = i - trilha["i0"]
                vivos.append({nome: (valor[k] if isinstance(valor, list)
                                     and nome not in ("pilares", "pontos", "de", "ate",
                                                      "a", "b", "origem", "segmento")
                                     else valor)
                              for nome, valor in trilha.items()})
    return {
        "i": i,
        "t": round(i / doc["hz"], 4),
        "global": fatia(trilhas["global"]),
        "camera": fatia(trilhas["camera"]),
        "p1": fatia(trilhas["lutadores"]["p1"]),
        "p2": fatia(trilhas["lutadores"]["p2"]),
        "vivos": vivos,
        "eventos": [e for e in doc.get("eventos") or () if e["i"] == i],
    }


def flags_ligadas(valor: int) -> list[str]:
    return [nome for bit, nome in enumerate(FLAGS) if valor & (1 << bit)]


# ------------------------------------------------------------ remapeamento
def duracao_do_clipe(remapeamento: dict | None, duracao_total: float) -> float:
    if not remapeamento:
        return duracao_total
    return sum(dur / vel for _ini, dur, vel in remapeamento.get("trechos") or ())


def tempo_no_clipe(remapeamento: dict | None, t: float) -> float | None:
    """Relogio da gravacao -> relogio do clipe (None se ``t`` caiu num corte).

    Com velocidade 1 e a mesma conta de ``highlights.mapear_tempo``.
    """
    if not remapeamento:
        return t
    acumulado = 0.0
    for inicio, duracao, velocidade in remapeamento.get("trechos") or ():
        if t < inicio - 1e-6:
            return None
        if t <= inicio + duracao + 1e-6:
            return acumulado + (t - inicio) / velocidade
        acumulado += duracao / velocidade
    return None


def tempo_na_gravacao(remapeamento: dict | None, t_clipe: float) -> float | None:
    """Relogio do clipe -> relogio da gravacao: o que o palco consulta para
    cada quadro que renderiza (``passo = t * hz``). None depois do fim."""
    if not remapeamento:
        return t_clipe
    acumulado = 0.0
    for inicio, duracao, velocidade in remapeamento.get("trechos") or ():
        dentro = duracao / velocidade
        if t_clipe <= acumulado + dentro + 1e-9:
            return inicio + (max(0.0, t_clipe - acumulado)) * velocidade
        acumulado += dentro
    return None
