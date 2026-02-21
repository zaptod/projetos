"""
NEURAL FIGHTS - Módulo Models
Sistema de dados de armas, personagens, classes e raridades.
"""

# Constantes
from .constants import (
    # Raridades
    RARIDADES, LISTA_RARIDADES,
    # Tipos de Arma
    TIPOS_ARMA, LISTA_TIPOS_ARMA,
    # Encantamentos e Passivas
    ENCANTAMENTOS, LISTA_ENCANTAMENTOS, PASSIVAS_ARMA,
    # Classes
    LISTA_CLASSES, CLASSES_DATA,
    # Helpers
    get_raridade_data, get_tipo_arma_data, get_class_data,
)

# Armas
from .weapons import (
    Arma,
    gerar_passiva_arma,
    calcular_tamanho_arma,
    validar_arma_personagem,
    sugerir_tamanho_arma,
    get_escala_visual_arma,
)

# Personagens
from .characters import Personagem

__all__ = [
    # Constantes
    'RARIDADES', 'LISTA_RARIDADES',
    'TIPOS_ARMA', 'LISTA_TIPOS_ARMA',
    'ENCANTAMENTOS', 'LISTA_ENCANTAMENTOS', 'PASSIVAS_ARMA',
    'LISTA_CLASSES', 'CLASSES_DATA',
    'get_raridade_data', 'get_tipo_arma_data', 'get_class_data',
    # Classes
    'Arma', 'Personagem',
    # Funções
    'gerar_passiva_arma',
    'calcular_tamanho_arma',
    'validar_arma_personagem',
    'sugerir_tamanho_arma',
    'get_escala_visual_arma',
]
