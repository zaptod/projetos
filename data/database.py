"""
NEURAL FIGHTS - Módulo Database
Funções de persistência de dados (JSON).
"""
import json
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Personagem, Arma, get_raridade_data

# Caminhos dos arquivos de dados - agora dentro de data/
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(DATA_DIR)
ARQUIVO_CHARS = os.path.join(DATA_DIR, "personagens.json")
ARQUIVO_ARMAS = os.path.join(DATA_DIR, "armas.json")
ARQUIVO_MATCH = os.path.join(PROJECT_DIR, "match_config.json")

def carregar_json(arquivo):
    if not os.path.exists(arquivo): return []
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def salvar_json(arquivo, dados):
    """Salva JSON atomicamente, preservando o arquivo anterior em caso de falha."""
    destino = os.path.abspath(arquivo)
    diretorio = os.path.dirname(destino)
    temporario = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=diretorio,
            prefix=f".{os.path.basename(destino)}.",
            suffix=".tmp",
            delete=False,
        ) as f:
            temporario = f.name
            json.dump(dados, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temporario, destino)
        temporario = None
    finally:
        if temporario and os.path.exists(temporario):
            os.unlink(temporario)


def carregar_match_config():
    """Carrega a configuração compartilhada por todos os pontos de entrada."""
    config = carregar_json(ARQUIVO_MATCH)
    if not isinstance(config, dict):
        raise ValueError(f"Configuração de luta inválida: {ARQUIVO_MATCH}")
    return config


def salvar_match_config(config, preservar_existente=True):
    """Atualiza a configuração canônica sem apagar opções de outros fluxos."""
    if not isinstance(config, dict):
        raise TypeError("A configuração de luta precisa ser um dicionário")

    dados_finais = {}
    if preservar_existente and os.path.exists(ARQUIVO_MATCH):
        dados_finais.update(carregar_match_config())
    dados_finais.update(config)
    salvar_json(ARQUIVO_MATCH, dados_finais)

def carregar_armas():
    raw = carregar_json(ARQUIVO_ARMAS)
    return [Arma(**item) for item in raw]

def carregar_personagens():
    raw_chars = carregar_json(ARQUIVO_CHARS)
    raw_armas = carregar_json(ARQUIVO_ARMAS)
    pesos_por_nome = {
        item["nome"]: float(item.get("peso", 0))
        * get_raridade_data(item.get("raridade", "Comum"))["mod_peso"]
        for item in raw_armas
    }
    
    lista = []
    for item in raw_chars:
        nome_arma = item.get("nome_arma", "")
        peso_arma = pesos_por_nome.get(nome_arma, 0)
        
        p = Personagem(
            item["nome"], item["tamanho"], item["forca"], item["mana"],
            nome_arma, peso_arma,
            item.get("cor_r", 200), item.get("cor_g", 50), item.get("cor_b", 50),
            item.get("classe", "Guerreiro (Força Bruta)"),
            item.get("personalidade", "Aleatório")  # Carrega personalidade!
        )
        lista.append(p)
    return lista

def salvar_lista_armas(lista):
    salvar_json(ARQUIVO_ARMAS, [a.to_dict() for a in lista])

def salvar_lista_chars(lista):
    salvar_json(ARQUIVO_CHARS, [p.to_dict() for p in lista])


def carregar_arma_por_nome(nome_arma):
    """Carrega uma arma específica pelo nome"""
    armas = carregar_armas()
    for arma in armas:
        if arma.nome == nome_arma:
            return arma
    return None
