"""
NEURAL FIGHTS - Tema Visual UI
Cores e estilos compartilhados entre todas as telas.
"""

# ============================================================================
# CORES DO TEMA PRINCIPAL
# ============================================================================
COR_BG = "#1a1a2e"
COR_BG_SECUNDARIO = "#16213e"
COR_HEADER = "#0f3460"
COR_ACCENT = "#e94560"
COR_SUCCESS = "#00d9ff"
COR_TEXTO = "#ffffff"
COR_TEXTO_DIM = "#8892b0"
COR_WARNING = "#f39c12"
COR_DANGER = "#e74c3c"

# ============================================================================
# CORES DAS RARIDADES
# ============================================================================
# Passe 2 (arte): fonte única em RGB vive em utils/palette.py; o tema
# Tkinter consome a MESMA verdade convertida para hex.
from neural_fights.utils.palette import (
    CORES_CLASSE as _CORES_CLASSE_RGB,
    CORES_RARIDADE as _CORES_RARIDADE_RGB,
    rgb_to_hex,
)

CORES_RARIDADE = {k: rgb_to_hex(v) for k, v in _CORES_RARIDADE_RGB.items()}

# ============================================================================
# CORES DAS CLASSES POR CATEGORIA
# ============================================================================
CORES_CLASSE = {k: rgb_to_hex(v) for k, v in _CORES_CLASSE_RGB.items()}


# Cores específicas para a tela de luta
COR_P1 = "#3498db"
COR_P2 = "#e94560"

# ============================================================================
# CATEGORIAS DE CLASSES
# ============================================================================
CATEGORIAS_CLASSE = {
    "⚔️ Físicos": ["Guerreiro (Força Bruta)", "Berserker (Fúria)", "Gladiador (Combate)", "Cavaleiro (Defesa)"],
    "🗡️ Ágeis": ["Assassino (Crítico)", "Ladino (Evasão)", "Ninja (Velocidade)", "Duelista (Precisão)"],
    "✨ Mágicos": ["Mago (Arcano)", "Piromante (Fogo)", "Criomante (Gelo)", "Necromante (Trevas)"],
    "⚡ Híbridos": ["Paladino (Sagrado)", "Druida (Natureza)", "Feiticeiro (Caos)", "Monge (Chi)"],
}

__all__ = [
    'COR_BG', 'COR_BG_SECUNDARIO', 'COR_HEADER', 'COR_ACCENT',
    'COR_SUCCESS', 'COR_TEXTO', 'COR_TEXTO_DIM', 'COR_WARNING', 'COR_DANGER',
    'CORES_RARIDADE', 'CORES_CLASSE', 'COR_P1', 'COR_P2', 'CATEGORIAS_CLASSE',
]
