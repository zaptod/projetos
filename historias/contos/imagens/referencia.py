# -*- coding: utf-8 -*-
"""A âncora de estilo da história: o que mantém dois geradores parecidos.

Com DOIS sites gerando as imagens da mesma história (PicassoIA e DreamFace),
o risco novo não é a fila travar — é o **estilo trocar no meio**. Dois
modelos diferentes, com o mesmo texto, entregam luzes, cores e traços
diferentes; e o espectador não perdoa uma história em que o rosto muda de
aparência entre uma cena e outra.

Três travas, da mais importante para a menos:

  1. DIVIDIR POR PARTE, NUNCA POR CENA. Cada parte é um vídeo inteiro. Se
     os dois geradores se revezassem cena a cena, a diferença entre eles
     apareceria a cada 15 segundos, dentro do mesmo vídeo — o pior caso
     possível. Dividindo por parte, cada vídeo sai inteiro de um gerador só,
     e a diferença (se houver) cai entre vídeos que a pessoa vê em dias
     diferentes. É a mesma lógica de não trocar de câmera no meio da cena.

  2. ESTILO CONGELADO. O texto de estilo é gravado no primeiro uso e passa a
     vir do disco, não do config. Sem isso, mexer em `imagens.json` no meio
     de uma história de 140 cenas deixaria as cenas antigas com um visual e
     as novas com outro — e ninguém lembraria por quê.

  3. IMAGEM DE REFERÊNCIA. Uma imagem central que os geradores que aceitam
     referência recebem em toda cena. A primeira imagem aprovada da história
     vira essa âncora, a menos que você escolha outra.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"
NOME_REFERENCIA = "referencia.png"
NOME_ESTILO = "estilo.json"

# O que fica congelado. Mudar o config depois NÃO muda a história em
# andamento — muda só as próximas.
CAMPOS = ("estilo", "negativo", "aspect", "reforco_consistencia")


def pasta(historia_id: str) -> Path:
    return OUTPUTS / historia_id


def caminho_estilo(historia_id: str) -> Path:
    return pasta(historia_id) / NOME_ESTILO


def caminho(historia_id: str) -> Path:
    """A imagem-âncora desta história (pode ainda não existir)."""
    return pasta(historia_id) / NOME_REFERENCIA


def tem_referencia(historia_id: str) -> bool:
    alvo = caminho(historia_id)
    return alvo.is_file() and alvo.stat().st_size > 10_000


def estilo(historia_id: str, config: dict | None = None) -> dict:
    """O estilo DESTA história — congelado no primeiro uso.

    Na primeira chamada grava o que o config diz; nas seguintes devolve o
    que está gravado, mesmo que o config tenha mudado.
    """
    alvo = caminho_estilo(historia_id)
    if alvo.is_file():
        try:
            with open(alvo, encoding="utf-8-sig") as fh:
                gravado = json.load(fh)
            if gravado.get("estilo"):
                return gravado
        except (OSError, ValueError):
            pass
    config = config or {}
    congelado = {campo: config.get(campo) for campo in CAMPOS}
    congelado["_comment"] = (
        "Congelado no primeiro uso desta historia. Mexer em config/"
        "imagens.json nao muda o que ja esta aqui — e por isso que as cenas "
        "geradas hoje e as de amanha continuam parecendo do mesmo filme. "
        "Para mudar de proposito, apague este arquivo.")
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps(congelado, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return congelado


def definir(historia_id: str, imagem) -> Path:
    """Elege uma imagem como a âncora da história."""
    origem = Path(imagem)
    if not origem.is_file():
        raise FileNotFoundError(f"imagem inexistente: {origem}")
    destino = caminho(historia_id)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origem.resolve() != destino.resolve():
        shutil.copyfile(origem, destino)
    return destino


def adotar_primeira(historia_id: str, geradas) -> Path | None:
    """Sem âncora ainda? A primeira imagem boa vira a âncora.

    Assim a história ganha referência sozinha, na primeira cena que der
    certo — e da segunda em diante os dois geradores partem do mesmo lugar.
    """
    if tem_referencia(historia_id):
        return caminho(historia_id)
    for arquivo in geradas:
        alvo = Path(arquivo)
        if alvo.is_file() and alvo.stat().st_size > 10_000:
            return definir(historia_id, alvo)
    return None


# ------------------------------------------------------------- a divisao
def dividir_por_parte(pendentes: list, provedores) -> dict:
    """{provedor: [cenas]} — cada PARTE inteira para um gerador só.

    Por que não cena a cena: a diferença de estilo entre dois modelos
    apareceria dentro do mesmo vídeo, a cada troca de imagem. Por parte, o
    vídeo sai coerente e a diferença cai entre vídeos publicados em dias
    diferentes.

    As partes são distribuídas alternadamente (1→A, 2→B, 3→A...) para os
    dois trabalharem ao mesmo tempo, e não um depois do outro.
    """
    provedores = [p for p in (provedores or []) if p]
    if not provedores:
        return {}
    if len(provedores) == 1:
        return {provedores[0]: list(pendentes)}

    partes = sorted({int(linha.get("parte", 1)) for linha in pendentes})
    dono = {parte: provedores[i % len(provedores)]
            for i, parte in enumerate(partes)}
    divisao = {p: [] for p in provedores}
    for linha in pendentes:
        divisao[dono[int(linha.get("parte", 1))]].append(linha)
    return divisao
