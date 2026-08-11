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

def mostrar_ajuda():
    """Mostra informacoes de uso"""
    print("""
----------------------------------------------------------------
                    NEURAL FIGHTS v12.0
----------------------------------------------------------------
  Uso:
    python run.py           Inicia o launcher (UI)
    python run.py --sim     Simulacao automatica (IA vs IA)
    python run.py --test    Modo de teste manual
    python run.py --help    Mostra esta ajuda
----------------------------------------------------------------
  Modo de Teste Manual (--test):
    WASD/Setas  = Mover
    SPACE       = Pular
    J/Z         = Atacar
    1-5         = Usar Skills
    T           = Trocar controle (P1/P2)
    R           = Resetar luta
    F1          = Toggle Debug
    F2          = Vida Infinita
    F3          = Mana Infinita
    F4          = Cooldowns Zero
    ESC         = Sair
----------------------------------------------------------------
    """)

def main(argv=None):
    """Executa o ponto de entrada e devolve um codigo de saida de processo."""
    argumentos = list(sys.argv[1:] if argv is None else argv)

    if len(argumentos) > 1:
        print("Erro: informe apenas uma opcao por execucao.", file=sys.stderr)
        mostrar_ajuda()
        return 2

    if argumentos:
        arg = argumentos[0].lower()
        
        if arg == '--sim':
            # Executa simulacao diretamente
            from simulation import Simulador
            try:
                match_config = Simulador.criar_match_config_padrao()
            except RuntimeError as exc:
                print(f"Erro: {exc}", file=sys.stderr)
                return 1
            sim = Simulador(match_config=match_config)
            sim.run()
            return 0
        
        elif arg == '--test':
            # Modo de teste manual
            from test_manual import SimuladorManual
            try:
                sim = SimuladorManual()
            except RuntimeError as exc:
                print(f"Erro: {exc}", file=sys.stderr)
                return 1
            sim.executar()
            return 0
        
        elif arg in ['--help', '-h', '/?']:
            mostrar_ajuda()
            return 0
        
        else:
            print(f"Argumento desconhecido: {arg}", file=sys.stderr)
            mostrar_ajuda()
            return 2
    else:
        # Executa o launcher (UI)
        from ui.main import main as run_launcher
        run_launcher()
        return 0

if __name__ == '__main__':
    raise SystemExit(main())
