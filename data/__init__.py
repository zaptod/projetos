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
    carregar_database,
    validar_database,
    atualizar_arma,
    renomear_arma,
    remover_arma,
    resolver_database_paths,
    resolver_match_config_path,
    resolver_runtime_data_dir,
    salvar_lista_armas,
    salvar_lista_chars,
    salvar_match_config,
    DataValidationError,
    ARQUIVO_CHARS,
    ARQUIVO_ARMAS,
    ARQUIVO_CHARS_RUNTIME,
    ARQUIVO_ARMAS_RUNTIME,
    ARQUIVO_MATCH,
    ARQUIVO_MATCH_DEFAULT,
    MATCH_CONFIG_ENV,
    RUNTIME_DATA_DIR_ENV,
    RUNTIME_DIR,
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
    'carregar_database',
    'validar_database',
    'atualizar_arma',
    'renomear_arma',
    'remover_arma',
    'resolver_database_paths',
    'resolver_match_config_path',
    'resolver_runtime_data_dir',
    'salvar_lista_armas',
    'salvar_lista_chars',
    'salvar_match_config',
    'DataValidationError',
    'ARQUIVO_CHARS',
    'ARQUIVO_ARMAS',
    'ARQUIVO_CHARS_RUNTIME',
    'ARQUIVO_ARMAS_RUNTIME',
    'ARQUIVO_MATCH',
    'ARQUIVO_MATCH_DEFAULT',
    'MATCH_CONFIG_ENV',
    'RUNTIME_DATA_DIR_ENV',
    'RUNTIME_DIR',
]
