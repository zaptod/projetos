"""Saidas humanas da esteira e exportacao com prova obrigatoria."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from painel.sprites import exportar, receita

from . import config, ficha, prompt
from .pedir import marcar


def _exportar_vila(dados: dict, prova: str, biblioteca: str | Path | None) -> dict:
    """Exporta a arte da Vila reduzida, com metadados ao lado. Nunca sobrescreve."""
    item = dados["item"]
    raiz = Path(biblioteca or config.PERFIS["vila"].biblioteca)
    destino = raiz / item["nome_arquivo"]
    meta = destino.with_suffix(".json")
    existentes = [str(p) for p in (destino, meta) if p.exists()]
    if existentes:
        raise FileExistsError(", ".join(existentes))
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
    saida = exportar.exportar(resultado, _identidade(dados, prova), receita=r,
                              medidas=tentativa.get("medidas"), biblioteca=biblioteca,
                              substituir=False)
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
    return dados


def descartar(item_id: str) -> dict:
    dados = ficha.ler(item_id)
    if not dados:
        raise ValueError("ficha inexistente")
    dados["estado"] = "descartado"
    ficha.registrar(dados, "descartado")
    ficha.gravar(dados)
    return dados
