"""
NEURAL FIGHTS - Módulo Database
Funções de persistência de dados (JSON).
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Personagem, Arma

# Caminhos dos arquivos de dados - agora dentro de data/
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_CHARS = os.path.join(DATA_DIR, "personagens.json")
ARQUIVO_ARMAS = os.path.join(DATA_DIR, "armas.json")
ARQUIVO_MATCH = os.path.join(DATA_DIR, "match_config.json")

def carregar_json(arquivo):
    if not os.path.exists(arquivo): return []
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def salvar_json(arquivo, dados):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def carregar_armas():
    raw = carregar_json(ARQUIVO_ARMAS)
    return [Arma(**item) for item in raw]

def carregar_personagens():
    raw_chars = carregar_json(ARQUIVO_CHARS)
    raw_armas = carregar_json(ARQUIVO_ARMAS)
    
    lista = []
    for item in raw_chars:
        peso_arma = 0
        nome_arma = item.get("nome_arma", "")
        
        # Busca o peso atualizado da arma
        for a in raw_armas:
            if a["nome"] == nome_arma:
                peso_arma = a["peso"]
                break
        
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