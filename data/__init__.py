"""
NEURAL FIGHTS - Módulo Data
Sistema de persistência de dados.
"""

from data.database import (
    carregar_json,
    salvar_json,
    carregar_armas,
    carregar_personagens,
    salvar_lista_armas,
    salvar_lista_chars,
    ARQUIVO_CHARS,
    ARQUIVO_ARMAS,
)

# Re-exporta o módulo database inteiro para compatibilidade
from data import database

__all__ = [
    'database',
    'carregar_json',
    'salvar_json',
    'carregar_armas',
    'carregar_personagens',
    'salvar_lista_armas',
    'salvar_lista_chars',
    'ARQUIVO_CHARS',
    'ARQUIVO_ARMAS',
]
