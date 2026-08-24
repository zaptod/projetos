"""Resposta unica para "o arquivo daquele slot existe e presta?".

Modulo proprio, e nao mais um metodo em status.py, por um motivo mecanico: a
FILA precisa desta resposta dentro do `claim` — e o claim ja segura o lock da
fila quando pergunta. `status.inventario()` chama `queue.listar()`, que toma
esse mesmo lock, e `_bloqueio()` abre um handle NOVO a cada chamada com
`msvcrt.locking(LK_NBLCK)`: no Windows ele NAO e reentrante. Perguntar para o
status de dentro do claim travaria 30 s e levantaria TimeoutError em todo
claim da fila.

Por isso a regra e dura: este modulo importa `config` e `slots`, e mais nada.
"""
from __future__ import annotations

from pathlib import Path

from . import config, slots

# Assinaturas de arquivo. Imagem e validada por MAGIC BYTES, nao por tamanho:
# o piso de bytes foi calibrado para mp4, e um PNG legitimo de arma numa
# paleta curta pode pesar menos que ele — reprovar por tamanho descartaria uma
# imagem boa e mandaria gerar de novo, gastando credito.
ASSINATURAS = (
    (b"\x89PNG\r\n\x1a\n", slots.IMAGEM),
    (b"\xff\xd8\xff", slots.IMAGEM),          # JPEG
    (b"GIF87a", slots.IMAGEM),
    (b"GIF89a", slots.IMAGEM),
)

# Piso so para VIDEO: mp4 nao tem assinatura util nos primeiros bytes (o box
# `ftyp` vem depois de um tamanho variavel) e um download truncado costuma ser
# HTML de erro salvo com nome de mp4.
BYTES_MINIMOS_VIDEO = 10_000

# Piso de imagem, deliberadamente BAIXO. Quem responde "isto e imagem?" e a
# assinatura, nao o tamanho: um PNG legitimo de paleta curta comprime para
# poucos KB, e um piso alto o descartaria e mandaria gerar de novo, gastando
# credito por nada. Aqui so cai o que e absurdo — arquivo vazio ou truncado
# nos primeiros bytes. PNG incompleto que passe daqui e pego mais adiante, na
# hora de abrir: o renderer cai na placa em vez de derrubar o video.
BYTES_MINIMOS_IMAGEM = 512


def caminho(generation_id: str, slot: str) -> Path:
    """Onde o artefato daquele slot esta DE FATO.

    Varre os candidatos em ordem (canonico, outras extensoes, formatos
    anteriores). Sem nenhum no disco devolve o CANONICO: e onde o proximo
    download vai gravar.
    """
    base = config.build_dir(generation_id)
    for nome in slots.nomes_aceitos(slot):
        candidato = base / nome
        if candidato.is_file():
            return candidato
    return config.artefato_path(generation_id, slot)


def midia_do_arquivo(caminho_do_arquivo) -> str | None:
    """IMAGEM, VIDEO ou None — decidido pela EXTENSAO, nao pelo slot.

    O slot diz o que se PEDE hoje; o arquivo diz o que ha para tocar. Uma
    geracao feita antes desta mudanca tem mp4 no slot de personagem e continua
    entrando no video como video.
    """
    nome = str(caminho_do_arquivo).lower()
    if nome.endswith(slots.EXTENSOES_IMAGEM):
        return slots.IMAGEM
    if nome.endswith(slots.EXTENSOES_VIDEO):
        return slots.VIDEO
    return None


def presta(caminho_do_arquivo: Path, midia: str | None = None) -> bool:
    """O arquivo e midia de verdade, ou e download truncado?"""
    if not caminho_do_arquivo.is_file():
        return False
    midia = midia or midia_do_arquivo(caminho_do_arquivo)
    tamanho = caminho_do_arquivo.stat().st_size
    if midia == slots.IMAGEM:
        if tamanho < BYTES_MINIMOS_IMAGEM:
            return False
        try:
            with open(caminho_do_arquivo, "rb") as arquivo:
                inicio = arquivo.read(12)
        except OSError:
            return False
        if any(inicio.startswith(assinatura) for assinatura, _ in ASSINATURAS):
            return True
        # WebP nao tem assinatura no byte zero: e "RIFF" + 4 bytes de tamanho.
        return inicio[:4] == b"RIFF" and inicio[8:12] == b"WEBP"
    return tamanho >= BYTES_MINIMOS_VIDEO


def duplicado_de(caminho: Path, generation_id: str, slot: str) -> str | None:
    """Este arquivo e identico ao artefato de OUTRO slot da mesma build?

    Guarda final contra o provedor devolver a imagem errada. Aconteceu de
    verdade: a imagem do personagem carregou no historico da conta depois da
    foto de referencia, o job da arma a viu como "nova", ela era retrato como
    qualquer outra, e a arma foi gravada como copia byte a byte do personagem.
    Nenhuma checagem de tela pega isso — so comparar o conteudo.
    """
    if not caminho.is_file():
        return None
    try:
        alvo = caminho.read_bytes()
    except OSError:
        return None
    for outro in slots.JOBS:
        if outro == slot:
            continue
        vizinho = config.build_dir(generation_id) / slots.ARQUIVO[outro]
        if not vizinho.is_file() or vizinho == caminho:
            continue
        try:
            if vizinho.stat().st_size == len(alvo) and vizinho.read_bytes() == alvo:
                return outro
        except OSError:
            continue
    return None


def utilizavel(generation_id: str, slot: str) -> bool:
    """Existe artefato que presta para este slot?"""
    encontrado = caminho(generation_id, slot)
    return presta(encontrado, midia_do_arquivo(encontrado))
