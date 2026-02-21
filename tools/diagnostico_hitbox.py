# diagnostico_hitbox.py - Analisa hitboxes de todas as armas
"""
Script para diagnosticar problemas de hitbox em todas as armas.
Verifica se o tipo de hitbox está correto para cada tipo de arma.
"""

import json
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class DiagnosticoArma:
    nome: str
    tipo: str
    problema: str
    sugestao: str
    valores_relevantes: dict

def carregar_armas():
    with open("armas.json", "r", encoding="utf-8") as f:
        return json.load(f)

def diagnosticar_arma(arma: dict) -> List[DiagnosticoArma]:
    """Analisa uma arma e retorna problemas encontrados"""
    problemas = []
    nome = arma.get("nome", "Sem nome")
    tipo = arma.get("tipo", "Desconhecido")
    
    # Valores importantes
    comp_cabo = arma.get("comp_cabo", 0)
    comp_lamina = arma.get("comp_lamina", 0)
    comp_corrente = arma.get("comp_corrente", 0)
    comp_ponta = arma.get("comp_ponta", 0)
    distancia = arma.get("distancia", 0)
    tamanho_projetil = arma.get("tamanho_projetil", 0)
    quantidade = arma.get("quantidade", 1)
    tamanho_arco = arma.get("tamanho_arco", 0)
    tamanho_flecha = arma.get("tamanho_flecha", 0)
    quantidade_orbitais = arma.get("quantidade_orbitais", 1)
    tamanho = arma.get("tamanho", 0)
    distancia_max = arma.get("distancia_max", 0)
    forma1_cabo = arma.get("forma1_cabo", 0)
    forma1_lamina = arma.get("forma1_lamina", 0)
    forma2_cabo = arma.get("forma2_cabo", 0)
    forma2_lamina = arma.get("forma2_lamina", 0)
    largura = arma.get("largura", 0)
    
    # === DIAGNÓSTICOS POR TIPO ===
    
    if tipo == "Reta":
        # Armas retas precisam de comp_cabo e comp_lamina
        if comp_cabo <= 0 and comp_lamina <= 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma RETA sem comp_cabo ou comp_lamina",
                sugestao="Definir comp_cabo e comp_lamina > 0",
                valores_relevantes={"comp_cabo": comp_cabo, "comp_lamina": comp_lamina}
            ))
        elif comp_cabo + comp_lamina < 20:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma RETA muito curta",
                sugestao="Aumentar comp_cabo + comp_lamina para pelo menos 20",
                valores_relevantes={"total": comp_cabo + comp_lamina}
            ))
    
    elif tipo == "Dupla":
        # Armas duplas também usam cabo + lamina
        if comp_cabo <= 0 and comp_lamina <= 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma DUPLA sem comp_cabo ou comp_lamina",
                sugestao="Definir comp_cabo e comp_lamina > 0",
                valores_relevantes={"comp_cabo": comp_cabo, "comp_lamina": comp_lamina}
            ))
    
    elif tipo == "Corrente":
        # Correntes DEVEM usar comp_corrente, NÃO comp_cabo/comp_lamina
        if comp_corrente <= 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma CORRENTE sem comp_corrente definido",
                sugestao="Definir comp_corrente > 0 (recomendado: 60-150)",
                valores_relevantes={"comp_corrente": comp_corrente}
            ))
        if comp_cabo > 0 or comp_lamina > 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma CORRENTE com comp_cabo/comp_lamina (vai ser ignorado)",
                sugestao="O sistema usa comp_corrente para Correntes",
                valores_relevantes={"comp_corrente": comp_corrente, "comp_cabo": comp_cabo, "comp_lamina": comp_lamina}
            ))
        # Verificar se comp_ponta está definido (bola do mangual)
        if comp_ponta <= 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma CORRENTE sem comp_ponta (tamanho da bola/lâmina)",
                sugestao="Definir comp_ponta > 0 para visualização da ponta",
                valores_relevantes={"comp_ponta": comp_ponta}
            ))
    
    elif tipo == "Arremesso":
        if tamanho_projetil <= 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma ARREMESSO sem tamanho_projetil",
                sugestao="Definir tamanho_projetil > 0",
                valores_relevantes={"tamanho_projetil": tamanho_projetil}
            ))
        if quantidade < 1:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma ARREMESSO sem quantidade",
                sugestao="Definir quantidade >= 1",
                valores_relevantes={"quantidade": quantidade}
            ))
    
    elif tipo == "Arco":
        if tamanho_arco <= 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma ARCO sem tamanho_arco",
                sugestao="Definir tamanho_arco > 0",
                valores_relevantes={"tamanho_arco": tamanho_arco}
            ))
        if tamanho_flecha <= 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma ARCO sem tamanho_flecha",
                sugestao="Definir tamanho_flecha > 0",
                valores_relevantes={"tamanho_flecha": tamanho_flecha}
            ))
    
    elif tipo == "Orbital":
        if distancia <= 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma ORBITAL sem distancia",
                sugestao="Definir distancia > 0 (distância do orbital ao centro)",
                valores_relevantes={"distancia": distancia}
            ))
        if largura <= 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma ORBITAL sem largura (ângulo de cobertura)",
                sugestao="Definir largura > 0 para escudos, ou deixar pequeno para orbes",
                valores_relevantes={"largura": largura}
            ))
    
    elif tipo == "Mágica":
        if tamanho <= 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma MÁGICA sem tamanho",
                sugestao="Definir tamanho > 0",
                valores_relevantes={"tamanho": tamanho}
            ))
        if quantidade < 1:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma MÁGICA sem quantidade de espadas",
                sugestao="Definir quantidade >= 1",
                valores_relevantes={"quantidade": quantidade}
            ))
        if distancia_max <= 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma MÁGICA sem distancia_max",
                sugestao="Definir distancia_max > 0",
                valores_relevantes={"distancia_max": distancia_max}
            ))
    
    elif tipo == "Transformável":
        # Precisa das duas formas
        if forma1_cabo <= 0 and forma1_lamina <= 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma TRANSFORMÁVEL sem forma1",
                sugestao="Definir forma1_cabo e forma1_lamina > 0",
                valores_relevantes={"forma1_cabo": forma1_cabo, "forma1_lamina": forma1_lamina}
            ))
        if forma2_cabo <= 0 and forma2_lamina <= 0:
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma TRANSFORMÁVEL sem forma2",
                sugestao="Definir forma2_cabo e forma2_lamina > 0",
                valores_relevantes={"forma2_cabo": forma2_cabo, "forma2_lamina": forma2_lamina}
            ))
        # Também pode usar comp_cabo/comp_lamina como fallback
        if (forma1_cabo <= 0 and forma1_lamina <= 0) and (comp_cabo <= 0 and comp_lamina <= 0):
            problemas.append(DiagnosticoArma(
                nome=nome, tipo=tipo,
                problema="Arma TRANSFORMÁVEL sem nenhuma forma definida",
                sugestao="Definir pelo menos comp_cabo/comp_lamina ou forma1/forma2",
                valores_relevantes={}
            ))
    
    else:
        problemas.append(DiagnosticoArma(
            nome=nome, tipo=tipo,
            problema=f"Tipo de arma desconhecido: {tipo}",
            sugestao="Usar um dos tipos: Reta, Dupla, Corrente, Arremesso, Arco, Orbital, Mágica, Transformável",
            valores_relevantes={}
        ))
    
    return problemas

def verificar_hitbox_implementacao():
    """Verifica se hitbox.py trata todos os tipos corretamente"""
    print("\n" + "="*60)
    print("VERIFICAÇÃO DA IMPLEMENTAÇÃO DE HITBOX")
    print("="*60)
    
    # Tipos e o que cada um DEVE usar
    mapeamento_esperado = {
        "Reta": {
            "tipo_hitbox": "Linha",
            "usa": "comp_cabo + comp_lamina",
            "escala": "2.0x raio"
        },
        "Dupla": {
            "tipo_hitbox": "Linha (x2)",
            "usa": "comp_cabo + comp_lamina",
            "escala": "1.5x raio"
        },
        "Corrente": {
            "tipo_hitbox": "Linha ondulada",
            "usa": "comp_corrente (NÃO comp_cabo/lamina!)",
            "escala": "3.0x raio"
        },
        "Arremesso": {
            "tipo_hitbox": "Área (projéteis)",
            "usa": "tamanho_projetil, quantidade",
            "escala": "2.0x raio"
        },
        "Arco": {
            "tipo_hitbox": "Área (flecha)",
            "usa": "tamanho_arco, tamanho_flecha",
            "escala": "3.0x raio"
        },
        "Orbital": {
            "tipo_hitbox": "Circular/Arco",
            "usa": "distancia, largura",
            "escala": "1.5x raio"
        },
        "Mágica": {
            "tipo_hitbox": "Área (espadas flutuantes)",
            "usa": "tamanho, quantidade, distancia_max",
            "escala": "2.5x raio"
        },
        "Transformável": {
            "tipo_hitbox": "Linha",
            "usa": "forma1/forma2 ou comp_cabo/comp_lamina",
            "escala": "2.5x raio"
        }
    }
    
    for tipo, info in mapeamento_esperado.items():
        print(f"\n{tipo}:")
        print(f"  Hitbox: {info['tipo_hitbox']}")
        print(f"  Usa: {info['usa']}")
        print(f"  Escala: {info['escala']}")

def main():
    print("="*60)
    print("DIAGNÓSTICO DE HITBOXES - NEURAL FIGHTS")
    print("="*60)
    
    armas = carregar_armas()
    print(f"\nTotal de armas: {len(armas)}")
    
    # Conta por tipo
    tipos_count = {}
    for arma in armas:
        t = arma.get("tipo", "Desconhecido")
        tipos_count[t] = tipos_count.get(t, 0) + 1
    
    print("\nArmas por tipo:")
    for t, c in sorted(tipos_count.items()):
        print(f"  {t}: {c}")
    
    # Diagnóstico
    todos_problemas = []
    for arma in armas:
        problemas = diagnosticar_arma(arma)
        todos_problemas.extend(problemas)
    
    if todos_problemas:
        print("\n" + "="*60)
        print(f"PROBLEMAS ENCONTRADOS: {len(todos_problemas)}")
        print("="*60)
        
        # Agrupa por tipo
        por_tipo = {}
        for p in todos_problemas:
            if p.tipo not in por_tipo:
                por_tipo[p.tipo] = []
            por_tipo[p.tipo].append(p)
        
        for tipo, probs in sorted(por_tipo.items()):
            print(f"\n--- {tipo} ({len(probs)} problemas) ---")
            for p in probs:
                print(f"\n  [{p.nome}]")
                print(f"    Problema: {p.problema}")
                print(f"    Sugestão: {p.sugestao}")
                if p.valores_relevantes:
                    print(f"    Valores: {p.valores_relevantes}")
    else:
        print("\n✓ Nenhum problema encontrado!")
    
    verificar_hitbox_implementacao()
    
    print("\n" + "="*60)
    print("ANÁLISE ESPECÍFICA: ARMAS DO TIPO CORRENTE")
    print("="*60)
    
    for arma in armas:
        if arma.get("tipo") == "Corrente":
            print(f"\n[{arma['nome']}]")
            print(f"  comp_corrente: {arma.get('comp_corrente', 0)}")
            print(f"  comp_ponta: {arma.get('comp_ponta', 0)}")
            print(f"  largura_ponta: {arma.get('largura_ponta', 0)}")
            print(f"  comp_cabo: {arma.get('comp_cabo', 0)} (deve ser 0)")
            print(f"  comp_lamina: {arma.get('comp_lamina', 0)} (deve ser 0)")

if __name__ == "__main__":
    main()
