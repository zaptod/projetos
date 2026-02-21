# analise_armas.py - Análise completa de todas as armas
"""
Analisa cada tipo de arma e identifica problemas de implementação.
"""

import json

def carregar_armas():
    with open("armas.json", "r", encoding="utf-8") as f:
        return json.load(f)

def analisar_implementacao():
    """
    Análise da implementação atual vs comportamento esperado
    """
    print("="*70)
    print("ANÁLISE DE IMPLEMENTAÇÃO DE ARMAS - NEURAL FIGHTS")
    print("="*70)
    
    analise = {
        "Reta": {
            "descricao": "Espadas, lanças - armas de lâmina simples",
            "comportamento_esperado": "Swing em arco, acerta na frente",
            "status_hitbox": "✓ OK - Linha com swing",
            "status_visual": "✓ OK - Linha com cabo + lâmina",
            "status_mecanica": "✓ OK - Ataque corpo-a-corpo",
            "problemas": [],
        },
        "Dupla": {
            "descricao": "Adagas duplas - duas lâminas",
            "comportamento_esperado": "Duas linhas com offset angular",
            "status_hitbox": "✓ OK - Duas linhas verificadas",
            "status_visual": "✓ OK - Duas lâminas desenhadas",
            "status_mecanica": "✓ OK - Ataques rápidos",
            "problemas": [],
        },
        "Corrente": {
            "descricao": "Mangual, kusarigama - armas de corrente/chicote",
            "comportamento_esperado": "Bola gira em arco, acerta em distância",
            "status_hitbox": "✓ CORRIGIDO - Arco centrado na bola",
            "status_visual": "✓ OK - Corrente ondulada + bola",
            "status_mecanica": "✓ OK - Ataque com distância média",
            "problemas": [],
        },
        "Arremesso": {
            "descricao": "Facas, shurikens, chakrams - armas arremessáveis",
            "comportamento_esperado": "Arremessa projéteis que voam até o alvo",
            "status_hitbox": "✓ CORRIGIDO - Projéteis com colisão própria",
            "status_visual": "✓ CORRIGIDO - Facas/shurikens/chakrams giram ao voar",
            "status_mecanica": "✓ CORRIGIDO - Dispara projéteis ao atacar",
            "problemas": [],
        },
        "Arco": {
            "descricao": "Arco e flecha - ataque ranged",
            "comportamento_esperado": "Dispara flechas como projéteis",
            "status_hitbox": "✓ CORRIGIDO - Flecha com colisão própria",
            "status_visual": "✓ CORRIGIDO - Flecha desenhada com gravidade",
            "status_mecanica": "✓ CORRIGIDO - Dispara flecha ao atacar",
            "problemas": [],
        },
        "Orbital": {
            "descricao": "Escudos, drones - objetos que orbitam",
            "comportamento_esperado": "Objetos giram ao redor do personagem",
            "status_hitbox": "✓ OK - Colisão circular",
            "status_visual": "✓ OK - Múltiplos orbitais girando",
            "status_mecanica": "✓ OK - Defesa passiva",
            "problemas": [],
        },
        "Mágica": {
            "descricao": "Espadas flutuantes - armas controladas magicamente",
            "comportamento_esperado": "Espadas flutuam e atacam",
            "status_hitbox": "✓ OK - Área de ataque",
            "status_visual": "✓ OK - Espadas flutuando",
            "status_mecanica": "✓ OK - Ataque de área",
            "problemas": [],
        },
        "Transformável": {
            "descricao": "Armas que mudam de forma (espada/bastão)",
            "comportamento_esperado": "Pode alternar entre duas formas",
            "status_hitbox": "✓ OK - Usa forma atual",
            "status_visual": "✓ OK - Visual muda com forma",
            "status_mecanica": "? A VERIFICAR - Comando de transformação",
            "problemas": [
                "⚠️ Verificar se transformação funciona via tecla",
            ],
        },
    }
    
    for tipo, info in analise.items():
        print(f"\n{'='*70}")
        print(f"TIPO: {tipo}")
        print(f"{'='*70}")
        print(f"Descrição: {info['descricao']}")
        print(f"Esperado: {info['comportamento_esperado']}")
        print(f"\nHitbox:    {info['status_hitbox']}")
        print(f"Visual:    {info['status_visual']}")
        print(f"Mecânica:  {info['status_mecanica']}")
        
        if info['problemas']:
            print(f"\nPROBLEMAS IDENTIFICADOS:")
            for p in info['problemas']:
                print(f"  {p}")
    
    return analise

def listar_armas_por_tipo():
    armas = carregar_armas()
    por_tipo = {}
    
    for arma in armas:
        t = arma.get("tipo", "?")
        if t not in por_tipo:
            por_tipo[t] = []
        por_tipo[t].append({
            "nome": arma["nome"],
            "dano": arma.get("dano", 0),
            "raridade": arma.get("raridade", "?"),
            # Atributos específicos por tipo
            "quantidade": arma.get("quantidade", 1),
            "tamanho_projetil": arma.get("tamanho_projetil", 0),
            "distancia_max": arma.get("distancia_max", 0),
        })
    
    print("\n" + "="*70)
    print("ARMAS NO JOGO")
    print("="*70)
    
    for tipo, lista in sorted(por_tipo.items()):
        print(f"\n--- {tipo} ({len(lista)} armas) ---")
        for a in lista:
            extra = ""
            if tipo == "Arremesso":
                extra = f" [qtd={a['quantidade']}, tam_proj={a['tamanho_projetil']}]"
            elif tipo == "Mágica":
                extra = f" [qtd={a['quantidade']}, dist_max={a['distancia_max']}]"
            print(f"  • {a['nome']} ({a['raridade']}) - Dano: {a['dano']}{extra}")
    
    return por_tipo

def plano_de_correcao():
    print("\n" + "="*70)
    print("PLANO DE CORREÇÃO")
    print("="*70)
    
    print("""
    
PRIORIDADE 1: ARREMESSO (Crítico - não funciona)
================================================
O QUE FAZER:
1. Quando atacar com arma de Arremesso:
   - Criar projéteis (classe Projetil ou nova classe ArmaProjetil)
   - Projéteis voam na direção do ataque
   - Cada projétil causa dano ao acertar
   - Visual: faca/shuriken girando enquanto voa
   
2. Sistema de munição/recarga:
   - "quantidade" = projéteis por ataque OU munição total
   - Cooldown entre arremessos
   - Opção: projéteis voltam após X segundos

IMPLEMENTAÇÃO:
- Modificar checar_ataque() para Arremesso
- Criar ArmaProjetil em combat.py
- Atualizar hitbox.py para não usar área estática


PRIORIDADE 2: ARCO (Crítico - não funciona)
===========================================
O QUE FAZER:
1. Mecânica de carga:
   - Segurar ataque = carregar
   - Soltar = disparar flecha
   
2. Projétil flecha:
   - Viaja em linha reta (ou com gravidade)
   - Dano baseado em tempo de carga
   
3. Visual:
   - Arco dobra ao carregar
   - Flecha aparece ao carregar
   - Flecha voa ao disparar

IMPLEMENTAÇÃO:
- Adicionar estado "carregando" no lutador
- Criar FlechaProjetil em combat.py
- Modificar animação de ataque para arco


PRIORIDADE 3: ORBITAL (Verificar)
=================================
VERIFICAR:
- Orbitais giram ao redor do personagem?
- Colisão funciona?
- Múltiplos orbitais?


PRIORIDADE 4: MÁGICA (Verificar)
================================
VERIFICAR:
- Espadas flutuam?
- Atacam automaticamente ou manualmente?
- Visual correto?


PRIORIDADE 5: TRANSFORMÁVEL (Verificar)
=======================================
VERIFICAR:
- Comando de transformação existe?
- AI usa transformação?
- Visual muda?
    """)

if __name__ == "__main__":
    analisar_implementacao()
    listar_armas_por_tipo()
    plano_de_correcao()
