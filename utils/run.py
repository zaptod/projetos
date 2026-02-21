#!/usr/bin/env python3
"""
NEURAL FIGHTS - Ponto de Entrada Principal
Execute este arquivo para iniciar o jogo.

Uso:
    python run.py           # Inicia o launcher (UI)
    python run.py --sim     # Inicia a simulacao diretamente
    python run.py --test    # Modo de teste manual (controle por teclado)
    python run.py --help    # Mostra ajuda
"""
import sys
import os

# Adiciona o diretorio do projeto ao path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

def mostrar_ajuda():
    """Mostra informacoes de uso"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    NEURAL FIGHTS v2.0                        ║
╠══════════════════════════════════════════════════════════════╣
║  Uso:                                                        ║
║    python run.py           Inicia o launcher (UI)            ║
║    python run.py --sim     Simulacao automatica (IA vs IA)   ║
║    python run.py --test    Modo de teste manual              ║
║    python run.py --help    Mostra esta ajuda                 ║
╠══════════════════════════════════════════════════════════════╣
║  Modo de Teste Manual (--test):                              ║
║    WASD/Setas  = Mover                                       ║
║    SPACE       = Pular                                       ║
║    J/Z         = Atacar                                      ║
║    1-5         = Usar Skills                                 ║
║    T           = Trocar controle (P1/P2)                     ║
║    R           = Resetar luta                                ║
║    F1          = Toggle Debug                                ║
║    F2          = Vida Infinita                               ║
║    F3          = Mana Infinita                               ║
║    F4          = Cooldowns Zero                              ║
║    ESC         = Sair                                        ║
╚══════════════════════════════════════════════════════════════╝
    """)

def main():
    """Ponto de entrada principal."""
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg == '--sim':
            # Executa simulacao diretamente
            from simulation import Simulador
            sim = Simulador()
            sim.executar()
        
        elif arg == '--test':
            # Modo de teste manual
            from test_manual import SimuladorManual
            sim = SimuladorManual()
            sim.executar()
        
        elif arg in ['--help', '-h', '/?']:
            mostrar_ajuda()
        
        else:
            print(f"Argumento desconhecido: {arg}")
            mostrar_ajuda()
    else:
        # Executa o launcher (UI)
        from ui.main import main as run_launcher
        run_launcher()

if __name__ == '__main__':
    main()
