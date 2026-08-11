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
CORES_RARIDADE = {
    "Comum": "#B4B4B4",
    "Incomum": "#64C864",
    "Raro": "#508CFF",
    "Épico": "#B450DC",
    "Lendário": "#FFB432",
    "Mítico": "#FF6464"
}

# ============================================================================
# CORES DAS CLASSES POR CATEGORIA
# ============================================================================
CORES_CLASSE = {
    # Físicos
    "Guerreiro (Força Bruta)": "#cd7f32",
    "Berserker (Fúria)": "#ff4444",
    "Gladiador (Combate)": "#b8860b",
    "Cavaleiro (Defesa)": "#4682b4",
    # Ágeis
    "Assassino (Crítico)": "#800080",
    "Ladino (Evasão)": "#505050",
    "Ninja (Velocidade)": "#2f2f2f",
    "Duelista (Precisão)": "#ffd700",
    # Mágicos
    "Mago (Arcano)": "#6495ed",
    "Piromante (Fogo)": "#ff6600",
    "Criomante (Gelo)": "#87ceeb",
    "Necromante (Trevas)": "#4b0082",
    # Híbridos
    "Paladino (Sagrado)": "#ffcc00",
    "Druida (Natureza)": "#228b22",
    "Feiticeiro (Caos)": "#9932cc",
    "Monge (Chi)": "#f5f5dc",
}

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
