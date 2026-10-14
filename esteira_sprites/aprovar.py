"""Saidas humanas da esteira e exportacao com prova obrigatoria."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image
from painel.sprites import exportar, fundo_auto, receita

from . import base, config, ficha, prompt
from .pedir import marcar


# Base refeito que ja estava na biblioteca (14/10/2026, decisao do
# coordenador): o `aprovar` do base NOVO sobrescreve o arquivo do base, e o
# velho fica ao lado em `_versoes_antigas/<nome>.v<N>.<ext>`, fora do que o jogo
# carrega (o Godot pula a pasta pelo `.gdignore`; a Vila so le o `nome_arquivo`
# do inventario). Vale SO para ficha de base com `versao_rejeitada`; peca comum
# continua nunca sobrescrevendo.
VERSOES_ANTIGAS = "_versoes_antigas"


def _base_refeito(dados: dict) -> bool:
    """A ficha e de um base que o Adrian rejeitou e a tentativa de agora e a nova."""
    rejeitada = base.versao_rejeitada(dados)
    return rejeitada > 0 and base.versao(dados) > rejeitada


def _versao_exportada(dados: dict) -> int:
    """Qual versao do base esta na biblioteca: a ultima tentativa exportada."""
    tentativas = dados.get("tentativas") or []
    for numero in range(len(tentativas) - 1, 0, -1):     # a de agora (a ultima) nao conta
        if tentativas[numero - 1].get("exportacao"):
            return numero
    return base.versao_rejeitada(dados)


def _guardar_versao_antiga(arquivos: list[Path], numero: int) -> list[str]:
    """Copia o que vai ser sobrescrito para `_versoes_antigas/` (nunca apaga nada)."""
    guardados = []
    for arquivo in arquivos:
        if not arquivo.is_file():
            continue
        pasta = arquivo.parent / VERSOES_ANTIGAS
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / ".gdignore").touch(exist_ok=True)
        destino = pasta / f"{arquivo.stem}.v{numero}{arquivo.suffix}"
        extra = 2
        while destino.exists():
            destino = pasta / f"{arquivo.stem}.v{numero}-{extra}{arquivo.suffix}"
            extra += 1
        shutil.copy2(arquivo, destino)
        guardados.append(str(destino))
    return guardados


def _anotar_versao_antiga(dados: dict, guardados: list[str]) -> None:
    if guardados:
        dados["tentativas"][-1]["versao_antiga"] = guardados
        ficha.registrar(dados, "versao_antiga_guardada", caminhos=guardados,
                        versao=_versao_exportada(dados))


def _exportar_vila(dados: dict, prova: str, biblioteca: str | Path | None) -> dict:
    """Exporta a arte da Vila reduzida, com metadados ao lado. Nunca sobrescreve,
    menos o base refeito (`_base_refeito`): o velho vai a `_versoes_antigas/`."""
    item = dados["item"]
    raiz = Path(biblioteca or config.PERFIS["vila"].biblioteca)
    destino = raiz / item["nome_arquivo"]
    meta = destino.with_suffix(".json")
    existentes = [p for p in (destino, meta) if p.exists()]
    if existentes and not _base_refeito(dados):
        raise FileExistsError(", ".join(str(p) for p in existentes))
    _anotar_versao_antiga(dados, _guardar_versao_antiga(existentes, _versao_exportada(dados)))
    tentativa = dados["tentativas"][-1]
    destino.parent.mkdir(parents=True, exist_ok=True)
    # A folha da IA vem em resolucao de trabalho; a Vila so precisa de 256 px
    # por celula. Guardar o original na ficha basta para auditoria, sem inflar
    # o repositorio a cada aprovacao.
    with Image.open(tentativa["caminhos"]["limpo"]) as origem:
        tamanho_original = list(origem.size)
        imagem = origem.copy()
    limite = 1024 if item.get("tipo") == "folha" else 512
    imagem.thumbnail((limite, limite), Image.LANCZOS)
    imagem.save(destino, format="PNG", optimize=True)
    try:
        conteudo_prova = json.loads(Path(prova).read_text(encoding="utf-8"))
    except ValueError:
        conteudo_prova = None
    meta.write_text(json.dumps({
        "id": item["id"], "tipo": item.get("tipo"), "quadros": item.get("quadros"),
        "grade": list(prompt.grade(item)) if item.get("tipo") == "folha" else None,
        "animacao": prompt.animacao(item), "medidas": tentativa.get("medidas"),
        "tamanho_original": tamanho_original,
        "fonte": tentativa["caminhos"]["limpo"], "prova": prova, "prova_conteudo": conteudo_prova,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"folha": str(destino), "metadados": str(meta)}


def _identidade(dados: dict, prova: str) -> exportar.Identidade:
    item = dados["item"]
    # A Oficina exige um destino de efeito. A adaptacao preserva o id como
    # skill, que e um destino valido mesmo para pecas do inventario.
    return exportar.Identidade(nome=item["id"], tipo="skill", skill=item["id"],
                               prova=prova, fonte=dados["tentativas"][-1]["caminhos"]["limpo"])


def aprovar(item_id: str, biblioteca: str | Path | None = None) -> dict:
    dados = ficha.ler(item_id)
    if not dados:
        raise ValueError("ficha inexistente")
    if dados.get("estado") not in ("a_conferir", "aprovado"):
        raise ValueError("item ainda nao esta para conferencia")
    tentativa = dados["tentativas"][-1]
    prova = tentativa.get("caminhos", {}).get("prova")
    if not prova or not Path(prova).is_file():
        raise ValueError("recusa sem prova do carteiro")
    if not prompt.opaco(dados.get("item") or {}):
        # nunca exporta com o fundo grudado (02/10/2026: 7 passaram e foram a Vila)
        with Image.open(tentativa["caminhos"]["limpo"]) as imagem:
            sobra = fundo_auto.sobra_de_fundo(np.asarray(imagem.convert("RGBA")))
        if sobra > 0.02:
            raise ValueError(f"fundo grudado: {sobra:.0%} da borda continua opaca; limpe antes")
    if dados.get("perfil", config.PERFIL) == "vila":
        saida = _exportar_vila(dados, prova, biblioteca)
        dados["estado"] = "na_biblioteca"
        tentativa["exportacao"] = saida
        ficha.registrar(dados, "na_biblioteca", caminhos=saida)
        ficha.gravar(dados)
        marcar(item_id, "pronto")
        return saida
    r = receita.Receita(fundo="nenhum", fatiar="componentes")
    with Image.open(tentativa["caminhos"]["limpo"]) as imagem:
        resultado = receita.processar(imagem, r)
    identidade = _identidade(dados, prova)
    substituir = False
    if _base_refeito(dados):
        # a folha, os metadados e a cena do base velho vao a `_versoes_antigas/`
        # ANTES (copia: se o exportar recusar, o velho continua no lugar)
        raiz = Path(biblioteca or exportar.biblioteca_padrao())
        velhos = [Path(p) for p in exportar.ja_existem(identidade, raiz)]
        _anotar_versao_antiga(dados, _guardar_versao_antiga(velhos, _versao_exportada(dados)))
        substituir = bool(velhos)
    saida = exportar.exportar(resultado, identidade, receita=r,
                              medidas=tentativa.get("medidas"), biblioteca=biblioteca,
                              substituir=substituir)
    dados["estado"] = "na_biblioteca"
    tentativa["exportacao"] = saida
    ficha.registrar(dados, "na_biblioteca", caminhos=saida)
    ficha.gravar(dados)
    marcar(item_id, "pronto")
    return saida


def refazer(item_id: str, motivo: str) -> dict:
    dados = ficha.ler(item_id)
    if not dados:
        raise ValueError("ficha inexistente")
    # O proximo `pedir` cria uma tentativa nova. Ela nao deve herdar o teto
    # das imagens anteriores quando foi o Adrian quem pediu outra mudanca.
    dados["contar_desde"] = len(dados.get("tentativas", []))
    if dados.get("tentativas"):
        dados["tentativas"][-1]["motivo"] = motivo
    dados["estado"] = "refazer"
    ficha.registrar(dados, "refazer", motivo=motivo)
    ficha.gravar(dados)
    # um sprite-base refeito depois que folhas sairam dele: as que o Adrian nao
    # aprovou esperam o base novo (decisao builds/base-rejeitado-depois)
    base.rejeitar(dados, "refazer")
    return dados


def descartar(item_id: str) -> dict:
    dados = ficha.ler(item_id)
    if not dados:
        raise ValueError("ficha inexistente")
    dados["estado"] = "descartado"
    ficha.registrar(dados, "descartado")
    ficha.gravar(dados)
    base.rejeitar(dados, "descartar")
    return dados
