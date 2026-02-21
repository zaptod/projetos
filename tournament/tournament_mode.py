"""
NEURAL FIGHTS - Sistema de Torneio v1.0
=======================================
Modo torneio com chaves eliminatórias.
Coloca todos os personagens em brackets e roda lutas automaticamente.
"""

import random
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.characters import Personagem
from models.weapons import Arma
from data.database import carregar_armas, carregar_personagens, carregar_arma_por_nome


class TournamentState(Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    ROUND_COMPLETE = "round_complete"
    FINISHED = "finished"


@dataclass
class TournamentMatch:
    """Representa uma luta no torneio"""
    match_id: int
    round_num: int
    fighter1_name: str
    fighter2_name: str
    winner_name: Optional[str] = None
    loser_name: Optional[str] = None
    duration: float = 0.0
    ko_type: str = ""
    fight_log: List[str] = field(default_factory=list)
    completed: bool = False


@dataclass 
class TournamentRound:
    """Representa uma rodada do torneio"""
    round_num: int
    name: str
    matches: List[TournamentMatch] = field(default_factory=list)
    completed: bool = False


class Tournament:
    """Sistema principal de torneio"""
    
    ROUND_NAMES = {
        1: "Final",
        2: "Semifinais",
        4: "Quartas de Final",
        8: "Oitavas de Final",
        16: "Rodada dos 32",
        32: "Rodada dos 64",
        64: "Rodada dos 128",
        128: "Rodada dos 256"
    }
    
    def __init__(self, name: str = "Torneio Neural Fights"):
        self.name = name
        self.participants: List[str] = []
        self.bracket: List[TournamentRound] = []
        self.state = TournamentState.WAITING
        self.champion: Optional[str] = None
        self.current_round: int = 0
        self.current_match: int = 0
        self.fight_history: List[TournamentMatch] = []
        
        # Estatísticas
        self.stats = {
            "total_fights": 0,
            "total_kos": 0,
            "fastest_ko": None,
            "longest_fight": None,
            "most_aggressive": None,
        }
    
    def load_participants_from_database(self, max_participants: int = 64) -> int:
        """Carrega participantes do banco de dados"""
        try:
            personagens = carregar_personagens()
            
            if not personagens:
                print("❌ Nenhum personagem encontrado no banco de dados!")
                return 0
            
            # personagens são objetos Personagem, não dicionários
            self.participants = [p.nome for p in personagens[:max_participants]]
            
            # Ajusta para potência de 2
            self._adjust_to_power_of_two()
            
            print(f"✅ {len(self.participants)} participantes carregados")
            return len(self.participants)
            
        except Exception as e:
            print(f"❌ Erro ao carregar participantes: {e}")
            return 0
    
    def add_participant(self, name: str) -> bool:
        """Adiciona um participante ao torneio"""
        if name not in self.participants:
            self.participants.append(name)
            return True
        return False
    
    def _adjust_to_power_of_two(self):
        """Ajusta número de participantes para potência de 2"""
        n = len(self.participants)
        if n < 2:
            return
        
        # Encontra próxima potência de 2
        power = 1
        while power < n:
            power *= 2
        
        # Se já é potência de 2, ok
        if power == n:
            return
        
        # Precisa adicionar byes ou truncar
        if n > power // 2:
            # Mais próximo de power - adiciona byes
            byes_needed = power - n
            for i in range(byes_needed):
                self.participants.append(f"BYE_{i+1}")
        else:
            # Trunca para power // 2
            self.participants = self.participants[:power // 2]
    
    def shuffle_participants(self):
        """Embaralha os participantes"""
        random.shuffle(self.participants)
    
    def generate_bracket(self) -> bool:
        """Gera as chaves do torneio"""
        if len(self.participants) < 2:
            print("❌ Mínimo de 2 participantes necessário!")
            return False
        
        self._adjust_to_power_of_two()
        self.shuffle_participants()
        
        n = len(self.participants)
        self.bracket = []
        
        # Calcula número de rodadas
        num_rounds = 0
        temp = n
        while temp > 1:
            num_rounds += 1
            temp //= 2
        
        # Cria rodadas
        matches_in_round = n // 2
        match_id = 0
        
        for round_num in range(num_rounds):
            round_name = self.ROUND_NAMES.get(matches_in_round, f"Rodada {round_num + 1}")
            tournament_round = TournamentRound(
                round_num=round_num,
                name=round_name
            )
            
            if round_num == 0:
                # Primeira rodada - usa participantes
                for i in range(0, n, 2):
                    match = TournamentMatch(
                        match_id=match_id,
                        round_num=round_num,
                        fighter1_name=self.participants[i],
                        fighter2_name=self.participants[i + 1]
                    )
                    tournament_round.matches.append(match)
                    match_id += 1
            else:
                # Rodadas seguintes - placeholders
                for i in range(matches_in_round):
                    match = TournamentMatch(
                        match_id=match_id,
                        round_num=round_num,
                        fighter1_name="TBD",
                        fighter2_name="TBD"
                    )
                    tournament_round.matches.append(match)
                    match_id += 1
            
            self.bracket.append(tournament_round)
            matches_in_round //= 2
        
        self.state = TournamentState.WAITING
        self.current_round = 0
        self.current_match = 0
        
        print(f"✅ Bracket gerado: {len(self.participants)} participantes, {num_rounds} rodadas")
        return True
    
    def get_current_match(self) -> Optional[TournamentMatch]:
        """Retorna a luta atual"""
        if self.state == TournamentState.FINISHED:
            return None
        
        if self.current_round >= len(self.bracket):
            return None
        
        round_obj = self.bracket[self.current_round]
        
        if self.current_match >= len(round_obj.matches):
            return None
        
        return round_obj.matches[self.current_match]
    
    def start_tournament(self) -> bool:
        """Inicia o torneio"""
        if not self.bracket:
            if not self.generate_bracket():
                return False
        
        self.state = TournamentState.IN_PROGRESS
        self.current_round = 0
        self.current_match = 0
        
        # Processa BYEs da primeira rodada
        self._process_byes()
        
        return True
    
    def _process_byes(self):
        """Processa vitórias automáticas (BYEs)"""
        if self.current_round >= len(self.bracket):
            return
        
        round_obj = self.bracket[self.current_round]
        
        for match in round_obj.matches:
            if match.completed:
                continue
            
            if match.fighter1_name.startswith("BYE"):
                match.winner_name = match.fighter2_name
                match.loser_name = match.fighter1_name
                match.completed = True
                match.ko_type = "BYE"
            elif match.fighter2_name.startswith("BYE"):
                match.winner_name = match.fighter1_name
                match.loser_name = match.fighter2_name
                match.completed = True
                match.ko_type = "BYE"
    
    def record_match_result(self, winner_name: str, duration: float = 0.0, 
                           ko_type: str = "KO", fight_log: List[str] = None):
        """Registra o resultado de uma luta"""
        match = self.get_current_match()
        if not match:
            return False
        
        if winner_name not in [match.fighter1_name, match.fighter2_name]:
            print(f"❌ Vencedor '{winner_name}' não está nesta luta!")
            return False
        
        match.winner_name = winner_name
        match.loser_name = match.fighter2_name if winner_name == match.fighter1_name else match.fighter1_name
        match.duration = duration
        match.ko_type = ko_type
        match.fight_log = fight_log or []
        match.completed = True
        
        self.fight_history.append(match)
        self.stats["total_fights"] += 1
        
        if "KO" in ko_type:
            self.stats["total_kos"] += 1
        
        # Atualiza próxima rodada
        self._advance_winner(match)
        
        # Avança para próxima luta
        self._advance_to_next_match()
        
        return True
    
    def _advance_winner(self, match: TournamentMatch):
        """Avança o vencedor para a próxima rodada"""
        if match.round_num + 1 >= len(self.bracket):
            # Era a final!
            self.champion = match.winner_name
            self.state = TournamentState.FINISHED
            return
        
        next_round = self.bracket[match.round_num + 1]
        match_index = match.match_id
        
        # Descobre qual luta da próxima rodada
        # Lutas 0,1 -> Luta 0; Lutas 2,3 -> Luta 1; etc.
        current_round_matches = len(self.bracket[match.round_num].matches)
        matches_before = sum(len(r.matches) for r in self.bracket[:match.round_num])
        local_index = match.match_id - matches_before
        next_match_index = local_index // 2
        
        if next_match_index < len(next_round.matches):
            next_match = next_round.matches[next_match_index]
            if local_index % 2 == 0:
                next_match.fighter1_name = match.winner_name
            else:
                next_match.fighter2_name = match.winner_name
    
    def _advance_to_next_match(self):
        """Avança para a próxima luta não completada"""
        while self.current_round < len(self.bracket):
            round_obj = self.bracket[self.current_round]
            
            while self.current_match < len(round_obj.matches):
                match = round_obj.matches[self.current_match]
                if not match.completed:
                    return
                self.current_match += 1
            
            # Rodada completa
            round_obj.completed = True
            self.current_round += 1
            self.current_match = 0
            
            if self.current_round < len(self.bracket):
                self._process_byes()
        
        # Torneio completo
        self.state = TournamentState.FINISHED
    
    def get_bracket_display(self) -> str:
        """Retorna uma representação visual do bracket"""
        lines = []
        lines.append("=" * 70)
        lines.append(f"  🏆 {self.name}")
        lines.append("=" * 70)
        
        for round_obj in self.bracket:
            lines.append(f"\n📋 {round_obj.name}")
            lines.append("-" * 40)
            
            for match in round_obj.matches:
                status = "✅" if match.completed else "⏳"
                f1 = match.fighter1_name[:20]
                f2 = match.fighter2_name[:20]
                
                if match.completed:
                    winner = "←" if match.winner_name == match.fighter1_name else "→"
                    lines.append(f"  {status} {f1:20} vs {f2:20} [{winner}]")
                else:
                    lines.append(f"  {status} {f1:20} vs {f2:20}")
        
        if self.champion:
            lines.append("\n" + "=" * 70)
            lines.append(f"  🏆 CAMPEÃO: {self.champion}")
            lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def get_progress(self) -> Dict:
        """Retorna progresso do torneio"""
        total_matches = sum(len(r.matches) for r in self.bracket)
        completed_matches = len(self.fight_history)
        
        return {
            "total_participants": len(self.participants),
            "total_rounds": len(self.bracket),
            "current_round": self.current_round,
            "current_round_name": self.bracket[self.current_round].name if self.current_round < len(self.bracket) else "Finalizado",
            "total_matches": total_matches,
            "completed_matches": completed_matches,
            "progress_percent": (completed_matches / total_matches * 100) if total_matches > 0 else 0,
            "champion": self.champion,
            "state": self.state.value
        }
    
    def save_state(self, filename: str = "tournament_state.json"):
        """Salva estado do torneio"""
        state = {
            "name": self.name,
            "participants": self.participants,
            "state": self.state.value,
            "champion": self.champion,
            "current_round": self.current_round,
            "current_match": self.current_match,
            "bracket": [],
            "stats": self.stats
        }
        
        for round_obj in self.bracket:
            round_data = {
                "round_num": round_obj.round_num,
                "name": round_obj.name,
                "completed": round_obj.completed,
                "matches": []
            }
            for match in round_obj.matches:
                match_data = {
                    "match_id": match.match_id,
                    "round_num": match.round_num,
                    "fighter1_name": match.fighter1_name,
                    "fighter2_name": match.fighter2_name,
                    "winner_name": match.winner_name,
                    "loser_name": match.loser_name,
                    "duration": match.duration,
                    "ko_type": match.ko_type,
                    "completed": match.completed
                }
                round_data["matches"].append(match_data)
            state["bracket"].append(round_data)
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(base_dir, "data", filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Estado salvo em {filepath}")
    
    def load_state(self, filename: str = "tournament_state.json") -> bool:
        """Carrega estado do torneio"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(base_dir, "data", filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            self.name = state["name"]
            self.participants = state["participants"]
            self.state = TournamentState(state["state"])
            self.champion = state["champion"]
            self.current_round = state["current_round"]
            self.current_match = state["current_match"]
            self.stats = state.get("stats", self.stats)
            
            self.bracket = []
            for round_data in state["bracket"]:
                round_obj = TournamentRound(
                    round_num=round_data["round_num"],
                    name=round_data["name"],
                    completed=round_data["completed"]
                )
                for match_data in round_data["matches"]:
                    match = TournamentMatch(
                        match_id=match_data["match_id"],
                        round_num=match_data["round_num"],
                        fighter1_name=match_data["fighter1_name"],
                        fighter2_name=match_data["fighter2_name"],
                        winner_name=match_data["winner_name"],
                        loser_name=match_data["loser_name"],
                        duration=match_data["duration"],
                        ko_type=match_data["ko_type"],
                        completed=match_data["completed"]
                    )
                    round_obj.matches.append(match)
                self.bracket.append(round_obj)
            
            print(f"✅ Estado carregado de {filepath}")
            return True
            
        except FileNotFoundError:
            print(f"⚠️ Arquivo não encontrado: {filepath}")
            return False
        except Exception as e:
            print(f"❌ Erro ao carregar estado: {e}")
            return False


class TournamentRunner:
    """Executor de torneio - conecta torneio com simulador visual"""
    
    def __init__(self, tournament: Tournament):
        self.tournament = tournament
        self.simulation_config = {
            "max_duration": 120.0,
            "auto_advance": True,
        }
    
    def setup_match_config(self, fighter1_name: str, fighter2_name: str, cenario: str = "Arena"):
        """Configura o match_config.json para a próxima luta"""
        import json
        import os
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "match_config.json")
        
        config = {
            "p1_nome": fighter1_name,
            "p2_nome": fighter2_name,
            "cenario": cenario,
            "portrait_mode": False
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        
        return config_path
    
    def launch_simulation(self):
        """Lança o simulador Pygame"""
        import subprocess
        import os
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sim_path = os.path.join(base_dir, "simulation", "simulacao.py")
        
        # Executa o simulador
        subprocess.Popen(["python", sim_path], cwd=base_dir)
    
    def run_single_match_visual(self, match: TournamentMatch) -> bool:
        """Configura e lança uma luta visual"""
        # Configura o match
        self.setup_match_config(match.fighter1_name, match.fighter2_name)
        
        # Lança o simulador
        self.launch_simulation()
        
        return True
    
    def run_single_match(self, match: TournamentMatch) -> Dict:
        """Executa uma única luta usando simulação simplificada"""
        from data.database import carregar_armas, carregar_personagens, carregar_arma_por_nome
        from models.constants import CLASSES_DATA
        
        # Carrega dados dos lutadores
        personagens = carregar_personagens()
        armas = carregar_armas()
        
        # Encontra os personagens
        p1_data = next((p for p in personagens if p.nome == match.fighter1_name), None)
        p2_data = next((p for p in personagens if p.nome == match.fighter2_name), None)
        
        if not p1_data or not p2_data:
            print(f"❌ Personagens não encontrados: {match.fighter1_name}, {match.fighter2_name}")
            return {"success": False, "error": "Personagens não encontrados"}
        
        # Simulação simplificada baseada em atributos
        # Calcula poder de combate de cada lutador
        
        def calcular_poder(personagem, arma_data):
            """Calcula poder de combate baseado em atributos"""
            classe = personagem.classe if hasattr(personagem, 'classe') else "Guerreiro"
            class_data = CLASSES_DATA.get(classe, {})
            
            # Stats base
            forca = personagem.forca if hasattr(personagem, 'forca') else 5.0
            mana = personagem.mana if hasattr(personagem, 'mana') else 5.0
            
            # Modificadores de classe
            mod_forca = class_data.get("mod_forca", 1.0)
            mod_mana = class_data.get("mod_mana", 1.0)
            mod_vida = class_data.get("mod_vida", 1.0)
            mod_vel = class_data.get("mod_velocidade", 1.0)
            
            # Poder físico
            poder_fisico = forca * mod_forca * 10
            
            # Poder mágico
            poder_magico = mana * mod_mana * 8
            
            # Poder de arma
            poder_arma = 0
            if arma_data:
                dano = arma_data.dano if hasattr(arma_data, 'dano') else 3.0
                poder_arma = dano * 5
                
                # Bonus de raridade
                raridade_bonus = {
                    "Comum": 1.0, "Incomum": 1.1, "Raro": 1.25,
                    "Épico": 1.4, "Lendário": 1.6, "Mítico": 2.0
                }
                rar = arma_data.raridade if hasattr(arma_data, 'raridade') else "Comum"
                poder_arma *= raridade_bonus.get(rar, 1.0)
                
                # Bonus de encantamentos
                if hasattr(arma_data, 'encantamentos') and arma_data.encantamentos:
                    poder_arma *= 1.0 + len(arma_data.encantamentos) * 0.15
            
            # Poder de vida/resistência
            poder_defesa = mod_vida * 20
            
            # Poder de velocidade (chance de esquiva/crítico)
            poder_agilidade = mod_vel * 15
            
            # Poder total com aleatoriedade
            poder_total = poder_fisico + poder_magico + poder_arma + poder_defesa + poder_agilidade
            poder_total *= random.uniform(0.8, 1.2)  # Variação de ±20%
            
            return poder_total
        
        # Busca armas
        arma1 = next((a for a in armas if a.nome == p1_data.nome_arma), None)
        arma2 = next((a for a in armas if a.nome == p2_data.nome_arma), None)
        
        # Calcula poderes
        poder1 = calcular_poder(p1_data, arma1)
        poder2 = calcular_poder(p2_data, arma2)
        
        # Determina vencedor
        total = poder1 + poder2
        prob_p1 = poder1 / total
        
        roll = random.random()
        
        if roll < prob_p1:
            winner = match.fighter1_name
            margin = poder1 - poder2
        else:
            winner = match.fighter2_name
            margin = poder2 - poder1
        
        # Determina tipo de vitória baseado na margem
        if margin > 50:
            ko_type = "KO Devastador"
            duration = random.uniform(10, 30)
        elif margin > 25:
            ko_type = "KO Técnico"
            duration = random.uniform(30, 60)
        elif margin > 10:
            ko_type = "KO"
            duration = random.uniform(60, 90)
        else:
            ko_type = "Decisão Apertada"
            duration = random.uniform(90, 120)
        
        return {
            "success": True,
            "winner": winner,
            "duration": duration,
            "ko_type": ko_type,
            "stats": {
                "poder_p1": poder1,
                "poder_p2": poder2,
                "margem": margin
            }
        }
    
    def _default_weapon(self):
        """Retorna dados de arma padrão"""
        return {
            "nome": "Espada Padrão",
            "tipo": "Reta",
            "dano": 3.0,
            "peso": 3.0,
            "raridade": "Comum",
            "r": 150, "g": 150, "b": 150,
            "estilo": "Corte (Espada)",
            "habilidades": [],
            "encantamentos": []
        }
    
    def run_tournament_automated(self, delay_between_fights: float = 1.0):
        """Executa o torneio completo automaticamente"""
        if not self.tournament.start_tournament():
            print("❌ Falha ao iniciar torneio")
            return
        
        print(self.tournament.get_bracket_display())
        print("\n" + "=" * 70)
        print("  🎮 INICIANDO TORNEIO AUTOMÁTICO")
        print("=" * 70)
        
        while self.tournament.state != TournamentState.FINISHED:
            match = self.tournament.get_current_match()
            
            if not match:
                break
            
            if match.fighter1_name.startswith("BYE") or match.fighter2_name.startswith("BYE"):
                # BYE já processado
                continue
            
            print(f"\n⚔️  LUTA: {match.fighter1_name} vs {match.fighter2_name}")
            
            # Executa a luta
            result = self.run_single_match(match)
            
            if result["success"]:
                winner = result["winner"]
                self.tournament.record_match_result(
                    winner_name=winner,
                    duration=result["duration"],
                    ko_type=result["ko_type"]
                )
                print(f"   🏆 Vencedor: {winner} ({result['ko_type']} em {result['duration']:.1f}s)")
            else:
                # Decide aleatoriamente em caso de erro
                winner = random.choice([match.fighter1_name, match.fighter2_name])
                self.tournament.record_match_result(winner_name=winner, ko_type="Decisão")
                print(f"   🏆 Vencedor (decisão): {winner}")
            
            time.sleep(delay_between_fights)
        
        print("\n" + self.tournament.get_bracket_display())
        self.tournament.save_state()


if __name__ == "__main__":
    # Teste do sistema de torneio
    print("=" * 70)
    print("  NEURAL FIGHTS - SISTEMA DE TORNEIO")
    print("=" * 70)
    
    tournament = Tournament("Torneio Teste")
    
    # Carrega participantes
    tournament.load_participants_from_database(max_participants=8)
    
    if len(tournament.participants) < 2:
        # Adiciona participantes de teste
        print("\nAdicionando participantes de teste...")
        for i in range(8):
            tournament.add_participant(f"Lutador_{i+1}")
    
    # Gera bracket
    tournament.generate_bracket()
    
    # Mostra bracket
    print(tournament.get_bracket_display())
    
    # Simula algumas lutas manualmente
    tournament.start_tournament()
    
    match = tournament.get_current_match()
    if match:
        print(f"\n🎮 Próxima luta: {match.fighter1_name} vs {match.fighter2_name}")
