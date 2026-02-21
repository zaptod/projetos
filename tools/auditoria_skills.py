"""
=============================================================================
AUDITORIA COMPLETA DE SKILLS - Neural Fights v2.0
=============================================================================
Verifica:
1. Todas as skills no banco de dados
2. Se cada mecanica esta implementada
3. Bugs pendentes
4. Funcionalidade no jogo
=============================================================================
"""
import sys
sys.path.insert(0, '.')

from core.skills import SKILL_DB, contar_skills
from core.combat import Projetil, AreaEffect, Beam, Buff, Summon, Trap, Transform, Channel

# Tipos de skills suportados pelo sistema atual
TIPOS_IMPLEMENTADOS = {"PROJETIL", "AREA", "DASH", "BUFF", "BEAM", "SUMMON", "TRAP", "TRANSFORM", "CHANNEL", "NADA"}

# Tipos que precisam de implementacao adicional
TIPOS_PENDENTES = {}  # Todos implementados agora!

# Efeitos de status implementados (verificar em entities.py)
EFEITOS_IMPLEMENTADOS = {
    "NORMAL", "QUEIMANDO", "CONGELADO", "LENTO", "PARALISIA", "ENVENENADO",
    "SANGRANDO", "DRENAR", "MALDITO", "MEDO", "CEGO", "SILENCIADO",
    "ENRAIZADO", "EMPURRAO", "KNOCK_UP", "EXPLOSAO", "VULNERAVEL", "EXPOSTO",
    "NECROSE", "POSSESSO", "VORTEX", "PUXADO", "EXAUSTO", "CHARME",
    "TEMPO_PARADO", "PERFURAR"
}

# Features avançadas que precisam verificação
FEATURES_AVANCADAS = [
    "homing",           # Projéteis teleguiados
    "perfura",          # Perfuração
    "chain",            # Chain lightning
    "retorna",          # Projétil que volta
    "raio_explosao",    # Explosão no impacto
    "delay_explosao",   # Explosão com delay
    "cone",             # Ataque em cone
    "duplica_apos",     # Duplicação temporal
    "split_aleatorio",  # Split aleatório
    "chance_backfire",  # Chance de errar
    "elemento_aleatorio",  # Elemento random
    "dano_variavel",    # Dano variável
    "efeito_aleatorio", # Efeito random
    "condicao",         # Condições especiais
    "lifesteal",        # Roubo de vida
    "remove_congelamento",  # Shatter
    "contagioso",       # Espalha entre alvos
    "multi_shot",       # Múltiplos projéteis
]

def auditar_todas_skills():
    """Auditoria completa de todas as skills"""
    
    print("=" * 80)
    print("AUDITORIA COMPLETA DE SKILLS - NEURAL FIGHTS v2.0")
    print("=" * 80)
    
    # Contagem por tipo
    contagem = contar_skills()
    print(f"\n📊 TOTAL: {len(SKILL_DB)} skills")
    print("\nPor tipo:")
    for tipo, qtd in sorted(contagem.items()):
        status = "✅" if tipo in TIPOS_IMPLEMENTADOS else "❌ NÃO IMPLEMENTADO"
        print(f"  {tipo}: {qtd} {status}")
    
    # Skills por categoria de problema
    skills_ok = []
    skills_tipo_pendente = []
    skills_feature_nao_processada = []
    skills_efeito_desconhecido = []
    
    print("\n" + "=" * 80)
    print("ANÁLISE DETALHADA POR SKILL")
    print("=" * 80)
    
    for nome, data in SKILL_DB.items():
        if nome == "Nenhuma":
            continue
            
        tipo = data.get("tipo", "DESCONHECIDO")
        efeito = data.get("efeito", "NORMAL")
        problemas = []
        avisos = []
        
        # Verifica tipo
        if tipo in TIPOS_PENDENTES:
            problemas.append(f"Tipo '{tipo}' não implementado no loop de jogo")
            skills_tipo_pendente.append(nome)
        elif tipo not in TIPOS_IMPLEMENTADOS:
            problemas.append(f"Tipo '{tipo}' desconhecido")
        
        # Verifica efeito
        if efeito and efeito not in EFEITOS_IMPLEMENTADOS:
            avisos.append(f"Efeito '{efeito}' pode não estar implementado")
            skills_efeito_desconhecido.append((nome, efeito))
        
        # Verifica features avançadas
        features_usadas = []
        for feature in FEATURES_AVANCADAS:
            if feature in data:
                features_usadas.append(feature)
        
        # Features especiais que precisam verificação
        if "canalizavel" in data:
            avisos.append("Canalização requer implementação especial")
        if "summon_vida" in data:
            avisos.append("Summon requer sistema de invocações")
        if "cria_portal" in data:
            avisos.append("Portal requer sistema de teleporte bidirecional")
        if "reverte_estado" in data:
            avisos.append("Reverter tempo requer snapshot de estado")
        if "stats_aleatorios" in data:
            avisos.append("Stats aleatórios requer implementação")
        if "bloqueia_movimento" in data:
            avisos.append("Bloqueio de movimento requer sistema de colisão")
        if "reflete_projeteis" in data:
            avisos.append("Reflexão de projéteis precisa verificação")
        if "reflete_skills" in data:
            avisos.append("Contrafeitiço precisa implementação")
        if "sem_cooldown" in data:
            avisos.append("Sem cooldown temporário precisa implementação")
        if "duracao_controle" in data:
            avisos.append("Controle mental precisa implementação")
        if "revive_hp_percent" in data:
            avisos.append("Ressurreição precisa sistema de morte/revive")
        if "ativa_ao_morrer" in data:
            avisos.append("Trigger ao morrer precisa hook especial")
        if "copia_caster" in data:
            avisos.append("Cópia sombria precisa sistema de clones")
        if "link_percent" in data:
            avisos.append("Link de alma precisa sistema de conexão")
        if "rouba_buff" in data:
            avisos.append("Roubo de buff precisa implementação")
        if "bonus_vs_trevas" in data:
            avisos.append("Bônus vs elemento precisa verificação no dano")
        if "intangivel" in data:
            avisos.append("Intangibilidade precisa sistema de colisão")
        if "voo" in data:
            avisos.append("Voo precisa sistema de altura/layers")
        if "trocar_pos" in data or "TROCAR_POS" in str(data.get("efeito", "")):
            avisos.append("Troca de posição precisa implementação")
        
        # Classifica
        if problemas:
            pass
        elif avisos:
            skills_feature_nao_processada.append((nome, avisos))
        else:
            skills_ok.append(nome)
    
    # Relatório
    print("\n" + "=" * 80)
    print("📋 RELATÓRIO FINAL")
    print("=" * 80)
    
    print(f"\n✅ SKILLS FUNCIONANDO ({len(skills_ok)}):")
    for nome in skills_ok[:20]:  # Mostra primeiras 20
        print(f"   • {nome}")
    if len(skills_ok) > 20:
        print(f"   ... e mais {len(skills_ok) - 20} skills")
    
    print(f"\n❌ TIPOS NÃO IMPLEMENTADOS ({len(skills_tipo_pendente)}):")
    for nome in skills_tipo_pendente:
        tipo = SKILL_DB[nome].get("tipo")
        print(f"   • {nome} [{tipo}]")
    
    print(f"\n⚠️  SKILLS COM FEATURES PENDENTES ({len(skills_feature_nao_processada)}):")
    for nome, avisos in skills_feature_nao_processada[:15]:
        print(f"   • {nome}")
        for aviso in avisos[:2]:
            print(f"      - {aviso}")
    
    if skills_efeito_desconhecido:
        print(f"\n🔶 EFEITOS POSSIVELMENTE NÃO IMPLEMENTADOS:")
        efeitos_unicos = set(e for _, e in skills_efeito_desconhecido)
        for efeito in efeitos_unicos:
            skills_com_efeito = [n for n, e in skills_efeito_desconhecido if e == efeito]
            print(f"   • {efeito}: {', '.join(skills_com_efeito)}")
    
    # Resumo de ações necessárias
    print("\n" + "=" * 80)
    print("🔧 AÇÕES NECESSÁRIAS")
    print("=" * 80)
    
    print("""
1. IMPLEMENTAR TIPOS FALTANTES:
   - SUMMON: Sistema de invocações (Fênix, Treant, Espírito, Cópia Sombria)
   - CHANNEL: Skills canalizáveis (Chamas do Dragão, Fotossíntese, Desintegrar)
   - TRAP: Estruturas/armadilhas (Muralha de Gelo)
   - TRANSFORM: Transformações (Avatar de Gelo, Forma Relâmpago)

2. IMPLEMENTAR FEATURES ESPECIAIS:
   - Reflexão de projéteis/skills (Escudo Arcano, Contrafeitiço)
   - Roubo de buffs (Roubar Magia)
   - Portais bidirecionais (Portal Arcano)
   - Reverter tempo (Reverter)
   - Controle mental (Possessão)
   - Sistema de clones (Cópia Sombria)
   - Voo/Levitação (Levitar)
   - Troca de posição (Troca de Almas)
   - Trigger ao morrer (Último Suspiro)
   - Stats aleatórios (Mutação)

3. VERIFICAR EFEITOS:
   - BOMBA_RELOGIO, LINK_ALMA, ACELERADO, REGENERANDO
   - DETERMINADO, FURIA, ABENÇOADO, IMORTAL
""")
    
    return {
        "ok": len(skills_ok),
        "tipo_pendente": len(skills_tipo_pendente),
        "feature_pendente": len(skills_feature_nao_processada),
        "total": len(SKILL_DB) - 1
    }


def testar_skill_basica(nome):
    """Testa se uma skill basica pode ser criada"""
    try:
        data = SKILL_DB.get(nome)
        if not data:
            return False, "Skill nao encontrada"
        
        tipo = data.get("tipo")
        
        # Mock de dono
        class FakeDono:
            def __init__(self):
                self.pos = [0, 0]
                self.morto = False
                self.angulo_olhar = 0
                self.vida_max = 100
                self.vida = 100
                self.velocidade = 5.0
                self.cor = (255, 255, 255)
        
        dono = FakeDono()
        
        if tipo == "PROJETIL":
            p = Projetil(nome, 0, 0, 0, dono)
            return True, f"OK - dano={p.dano}, vel={p.vel}, homing={p.homing}"
        elif tipo == "AREA":
            a = AreaEffect(nome, 0, 0, dono)
            return True, f"OK - dano={a.dano}, raio={a.raio}, vortex={a.vortex}"
        elif tipo == "BEAM":
            b = Beam(nome, 0, 0, 5, 0, dono)
            return True, f"OK - dano={b.dano}, alcance={b.alcance}"
        elif tipo == "BUFF":
            bf = Buff(nome, dono)
            return True, f"OK - duracao={bf.duracao}"
        elif tipo == "SUMMON":
            s = Summon(nome, 0, 0, dono)
            return True, f"OK - vida={s.vida}, dano={s.dano}, tipo={s.summon_tipo}"
        elif tipo == "TRAP":
            t = Trap(nome, 0, 0, dono)
            return True, f"OK - vida={t.vida}, bloqueia={t.bloqueia_movimento}"
        elif tipo == "TRANSFORM":
            tr = Transform(nome, dono)
            return True, f"OK - duracao={tr.duracao}, bonus_vel={tr.bonus_velocidade}"
        elif tipo == "CHANNEL":
            ch = Channel(nome, dono)
            return True, f"OK - duracao={ch.duracao_max}, dps={ch.dano_por_segundo}"
        else:
            return False, f"Tipo '{tipo}' nao testavel diretamente"
            
    except Exception as e:
        return False, f"ERRO: {str(e)}"


if __name__ == "__main__":
    resultado = auditar_todas_skills()
    
    print("\n" + "=" * 80)
    print("🧪 TESTES DE CRIAÇÃO DE SKILLS")
    print("=" * 80)
    
    # Testa algumas skills específicas
    skills_testar = [
        "Bola de Fogo", "Mísseis Arcanos", "Buraco Negro", 
        "Corrente em Cadeia", "Fênix", "Avatar de Gelo"
    ]
    
    for nome in skills_testar:
        ok, msg = testar_skill_basica(nome)
        status = "✅" if ok else "❌"
        print(f"{status} {nome}: {msg}")
