"""Previa curta de uma folha do Atelie no render real do palco."""
from __future__ import annotations

import hashlib
import unicodedata
from copy import deepcopy
from pathlib import Path

from .cli import render_da_seed


def _chave(valor) -> str:
    """Texto comparavel para os ids do catalogo e as fichas do banco."""
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto.lower() if not unicodedata.combining(c))
    # "Assassino (Crítico)" e "assassino_critico" viram "assassino critico"
    # (08/10: os parenteses deixavam a classe sem nenhuma ficha)
    texto = "".join(c if c.isalnum() or c == "." else " " for c in texto)
    return " ".join(texto.split())


def _arma_da_ficha(ficha: dict, armas: list[dict]) -> dict:
    nome = _chave(ficha.get("nome_arma"))
    return next((arma for arma in armas if _chave(arma.get("nome")) == nome), {})


def _tem_peca(ficha: dict, peca: str, armas: list[dict]) -> bool:
    """Diz se a ficha pode mostrar a peca no palco.

    As fichas antigas nao trazem todos os campos do kit. Por isso efeitos e
    elementos procuram tambem a descricao da skill; se nao houver evidencia,
    o chamador usa qualquer lutador em vez de esconder a previa.
    """
    partes = _chave(peca).split(".")
    if len(partes) < 2 or partes[0] == "lutador":
        return True
    alvo = ".".join(partes[1:])
    if partes[0] == "classe":
        return alvo in _chave(ficha.get("classe"))
    arma = _arma_da_ficha(ficha, armas)
    if partes[:2] == ["arma", "estilo"]:
        return ".".join(partes[2:]) == _chave(arma.get("estilo"))
    if partes[:2] == ["arma", "tipo"]:
        return ".".join(partes[2:]) == _chave(arma.get("tipo"))
    if partes[0] in {"skill", "efeito", "elemento", "estado", "buff"}:
        texto = " ".join(_chave(valor) for skill in ficha.get("kit", [])
                          for valor in skill.values() if isinstance(valor, (str, int, float)))
        return alvo in texto
    return True


def _troca_para_peca(peca: str, armas: list[dict]) -> dict | None:
    """A troca efemera que faz a peca aparecer quando o banco nao a usa."""
    partes = _chave(peca).split(".")
    if partes[:2] == ["arma", "estilo"]:
        alvo = ".".join(partes[2:])
        arma = next((a for a in armas if _chave(a.get("estilo")) == alvo), None)
        return {"arma": arma} if arma else None
    if partes[:2] == ["arma", "tipo"]:
        alvo = ".".join(partes[2:])
        arma = next((a for a in armas if _chave(a.get("tipo")) == alvo), None)
        return {"arma": arma} if arma else None
    if partes[:1] == ["classe"] and len(partes) > 1:
        from neural_fights.models.constants import LISTA_CLASSES
        alvo = ".".join(partes[1:])
        classe = next((c for c in LISTA_CLASSES if alvo in _chave(c)), None)
        return {"classe": classe} if classe else None
    return None


def _provider_da_troca(trocas: dict[str, dict]):
    """Cria fichas somente para a simulacao da previa, sem tocar no banco."""
    from neural_fights.data.database import carregar_armas, carregar_database
    from neural_fights.models.characters import Personagem

    _, fichas = carregar_database()
    por_nome = {ficha["nome"]: ficha for ficha in fichas}
    armas = {arma.nome: arma for arma in carregar_armas()}

    def resolver(nome: str):
        ficha = deepcopy(por_nome[nome])
        troca = trocas.get(nome, {})
        arma = troca.get("arma")
        if arma:
            ficha["nome_arma"] = arma["nome"]
        if troca.get("classe"):
            ficha["classe"] = troca["classe"]
        arma_obj = armas.get(ficha.get("nome_arma", ""))
        pessoa = Personagem(ficha["nome"], ficha["tamanho"], ficha["forca"], ficha["mana"],
                            ficha.get("nome_arma", ""), float(getattr(arma_obj, "peso", 0)),
                            ficha.get("cor_r", 200), ficha.get("cor_g", 50), ficha.get("cor_b", 50),
                            ficha.get("classe", "Guerreiro"), ficha.get("personalidade", "Aleatorio"))
        pessoa.arma_obj = arma_obj
        pessoa.kit_skills = ficha.get("kit_skills")
        return pessoa

    return resolver


def escolher_lutadores_da_peca(peca: str, seed: int, com_trocas: bool = False):
    """Escolhe, de forma estavel, fichas que podem exibir a peca editada."""
    from ..tournament.runner import fichas_do_banco
    try:
        from neural_fights.data.database import carregar_database
        armas, _ = carregar_database()
    except Exception:  # o render ainda sabe escolher qualquer ficha do banco
        armas = []
    fichas = fichas_do_banco()
    nomes = sorted(fichas)
    usados = [nome for nome in nomes if _tem_peca(fichas[nome], peca, armas)]
    # Para efeito/elemento sem metadado conhecido, a previa continua util.
    troca = None
    if not usados:
        troca = _troca_para_peca(peca, armas)
        usados = nomes
    if not usados:
        return (None, None, {}) if com_trocas else (None, None)
    primeiro = usados[seed % len(usados)]
    opcoes = [nome for nome in usados if nome != primeiro] or [nome for nome in nomes if nome != primeiro]
    segundo = opcoes[(seed >> 16) % len(opcoes)] if opcoes else None
    trocas = {primeiro: troca} if troca else {}
    return (primeiro, segundo, trocas) if com_trocas else (primeiro, segundo)


def renderizar_previa(peca: str, estado: str, animacao: str, pasta_saida: Path) -> Path:
    """Renderiza cinco segundos deterministas e devolve o MP4 do Godot.

    A arte ja deve estar em ``biblioteca/animacoes``; o Godot faz a mesma
    resolucao de peca/heranca usada na luta, sem copiar nem importar a folha.
    """
    if not all(isinstance(valor, str) and valor.strip() for valor in (peca, estado, animacao)):
        raise ValueError("peca, estado e animacao sao obrigatorios")
    pasta = Path(pasta_saida)
    pasta.mkdir(parents=True, exist_ok=True)
    seed = int.from_bytes(hashlib.sha256(f"{peca}|{estado}|{animacao}".encode()).digest()[:8], "big")
    p1, p2, trocas = escolher_lutadores_da_peca(peca, seed, com_trocas=True)
    resumo = render_da_seed(p1=p1, p2=p2, seed=seed, arena=None, pasta=pasta,
                            sem_corte=True, quadros=150,
                            roster_provider=_provider_da_troca(trocas) if trocas else None)
    return Path(resumo["saida"])
