"""
NEURAL FIGHTS - Módulo Data
Sistema de persistência de dados.
"""

from data.database import (
    carregar_json,
    salvar_json,
    carregar_armas,
    carregar_personagens,
    carregar_match_config,
    salvar_lista_armas,
    salvar_lista_chars,
    salvar_match_config,
    ARQUIVO_CHARS,
    ARQUIVO_ARMAS,
    ARQUIVO_MATCH,
)

# Re-exporta o módulo database inteiro para compatibilidade
from data import database

__all__ = [
    'database',
    'carregar_json',
    'salvar_json',
    'carregar_armas',
    'carregar_personagens',
    'carregar_match_config',
    'salvar_lista_armas',
    'salvar_lista_chars',
    'salvar_match_config',
    'ARQUIVO_CHARS',
    'ARQUIVO_ARMAS',
    'ARQUIVO_MATCH',
]
