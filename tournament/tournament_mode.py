"""
NEURAL FIGHTS - Sistema de Torneio v1.0
=======================================
Modo torneio com chaves eliminatórias.
Coloca todos os personagens em brackets e roda lutas automaticamente.
"""

import random
import os
import sys
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

from data import database
from data.database import carregar_personagens


TOURNAMENT_STATE_ENV = "NEURAL_FIGHTS_TOURNAMENT_STATE"
DEFAULT_TOURNAMENT_STATE = os.path.join(
    database.RUNTIME_DIR,
    "tournament_state.json",
)


def _console_print(*values, sep=" ", end="\n", file=None, flush=False):
    """Imprime dados livres sem quebrar consoles de encoding limitado."""

    destination = file or sys.stdout
    encoding = getattr(destination, "encoding", None)
    if encoding:
        safe_values = [
            str(value).encode(encoding, "backslashreplace").decode(encoding)
            for value in values
        ]
    else:
        safe_values = [str(value) for value in values]
    print(*safe_values, sep=sep, end=end, file=destination, flush=flush)


def _resolver_caminho_estado(filename=None):
    if filename is not None:
        caminho = filename
        base_relativa = os.getcwd()
    else:
        caminho = os.environ.get(TOURNAMENT_STATE_ENV) or DEFAULT_TOURNAMENT_STATE
        base_relativa = database.RUNTIME_DIR
    if not os.path.isabs(caminho):
        caminho = os.path.join(base_relativa, caminho)
    return os.path.abspath(caminho)


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
                _console_print("ERRO: Nenhum personagem encontrado no banco de dados!")
                return 0
            
            # personagens são objetos Personagem, não dicionários
            self.participants = [p.nome for p in personagens[:max_participants]]
            
            # Ajusta para potência de 2
            self._adjust_to_power_of_two()
            
            _console_print(f"OK: {len(self.participants)} participantes carregados")
            return len(self.participants)
            
        except Exception as e:
            _console_print(f"ERRO: Falha ao carregar participantes: {e}")
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
            _console_print("ERRO: Minimo de 2 participantes necessario!")
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
        
        _console_print(
            f"OK: Bracket gerado: {len(self.participants)} participantes, "
            f"{num_rounds} rodadas"
        )
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
        self._advance_to_next_match()
        
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
                self._advance_winner(match)
            elif match.fighter2_name.startswith("BYE"):
                match.winner_name = match.fighter1_name
                match.loser_name = match.fighter2_name
                match.completed = True
                match.ko_type = "BYE"
                self._advance_winner(match)
    
    def record_match_result(self, winner_name: str, duration: float = 0.0, 
                           ko_type: str = "KO", fight_log: List[str] = None):
        """Registra o resultado de uma luta"""
        match = self.get_current_match()
        if not match:
            return False
        
        if winner_name not in [match.fighter1_name, match.fighter2_name]:
            _console_print(f"ERRO: Vencedor '{winner_name}' nao esta nesta luta!")
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
        # Descobre qual luta da próxima rodada
        # Lutas 0,1 -> Luta 0; Lutas 2,3 -> Luta 1; etc.
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
        lines.append(f"  [TORNEIO] {self.name}")
        lines.append("=" * 70)
        
        for round_obj in self.bracket:
            lines.append(f"\n[RODADA] {round_obj.name}")
            lines.append("-" * 40)
            
            for match in round_obj.matches:
                status = "[OK]" if match.completed else "[PENDENTE]"
                f1 = match.fighter1_name[:20]
                f2 = match.fighter2_name[:20]
                
                if match.completed:
                    winner = "<-" if match.winner_name == match.fighter1_name else "->"
                    lines.append(f"  {status} {f1:20} vs {f2:20} [{winner}]")
                else:
                    lines.append(f"  {status} {f1:20} vs {f2:20}")
        
        if self.champion:
            lines.append("\n" + "=" * 70)
            lines.append(f"  [CAMPEAO] {self.champion}")
            lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def get_progress(self) -> Dict:
        """Retorna progresso do torneio"""
        total_matches = sum(len(r.matches) for r in self.bracket)
        completed_matches = sum(
            1
            for round_obj in self.bracket
            for match in round_obj.matches
            if match.completed
        )
        
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

    @staticmethod
    def _serialize_match(match: TournamentMatch) -> Dict:
        """Converte uma luta para o formato persistido."""
        return {
            "match_id": match.match_id,
            "round_num": match.round_num,
            "fighter1_name": match.fighter1_name,
            "fighter2_name": match.fighter2_name,
            "winner_name": match.winner_name,
            "loser_name": match.loser_name,
            "duration": match.duration,
            "ko_type": match.ko_type,
            "fight_log": list(match.fight_log),
            "completed": match.completed,
        }

    @staticmethod
    def _deserialize_match(match_data: Dict) -> TournamentMatch:
        """Restaura uma luta, aceitando saves anteriores ao fight_log."""
        return TournamentMatch(
            match_id=match_data["match_id"],
            round_num=match_data["round_num"],
            fighter1_name=match_data["fighter1_name"],
            fighter2_name=match_data["fighter2_name"],
            winner_name=match_data.get("winner_name"),
            loser_name=match_data.get("loser_name"),
            duration=match_data.get("duration", 0.0),
            ko_type=match_data.get("ko_type", ""),
            fight_log=list(match_data.get("fight_log") or []),
            completed=match_data.get("completed", False),
        )
    
    def save_state(self, filename: str | None = None):
        """Salva o estado atomicamente, sem truncar o save anterior."""
        state = {
            "name": self.name,
            "participants": self.participants,
            "state": self.state.value,
            "champion": self.champion,
            "current_round": self.current_round,
            "current_match": self.current_match,
            "bracket": [],
            "fight_history": [
                self._serialize_match(match) for match in self.fight_history
            ],
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
                round_data["matches"].append(self._serialize_match(match))
            state["bracket"].append(round_data)
        
        filepath = _resolver_caminho_estado(filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        database.salvar_json(filepath, state)
        
        _console_print(f"OK: Estado salvo em {filepath}")
    
    def load_state(self, filename: str | None = None) -> bool:
        """Carrega e valida todo o save antes de alterar o torneio atual."""
        filepath = _resolver_caminho_estado(filename)
        
        try:
            if not os.path.exists(filepath):
                raise FileNotFoundError(filepath)
            state = database.carregar_json(filepath)
            if not isinstance(state, dict):
                raise database.DataValidationError("save de torneio deve ser um objeto JSON")

            name = state["name"]
            participants = state["participants"]
            if not isinstance(name, str) or not name.strip():
                raise database.DataValidationError("name deve ser uma string nao vazia")
            if not isinstance(participants, list) or not all(
                isinstance(nome, str) and nome for nome in participants
            ):
                raise database.DataValidationError("participants deve conter somente nomes")
            if len(participants) != len(set(participants)):
                raise database.DataValidationError("participants contem nomes duplicados")

            tournament_state = TournamentState(state["state"])
            champion = state.get("champion")
            current_round = state["current_round"]
            current_match = state["current_match"]
            if (
                isinstance(current_round, bool)
                or not isinstance(current_round, int)
                or current_round < 0
                or isinstance(current_match, bool)
                or not isinstance(current_match, int)
                or current_match < 0
            ):
                raise database.DataValidationError(
                    "current_round e current_match devem ser inteiros nao negativos"
                )

            stats_data = state.get("stats", {})
            if not isinstance(stats_data, dict):
                raise database.DataValidationError("stats deve ser um objeto JSON")
            stats = dict(self.stats)
            stats.update(stats_data)

            bracket_data = state["bracket"]
            if not isinstance(bracket_data, list):
                raise database.DataValidationError("bracket deve ser uma lista")
            bracket = []
            matches_by_id = {}
            for round_data in bracket_data:
                if not isinstance(round_data, dict) or not isinstance(
                    round_data.get("matches"), list
                ):
                    raise database.DataValidationError("rodada invalida no bracket")
                round_obj = TournamentRound(
                    round_num=round_data["round_num"],
                    name=round_data["name"],
                    completed=round_data["completed"]
                )
                for match_data in round_data["matches"]:
                    if not isinstance(match_data, dict):
                        raise database.DataValidationError("luta invalida no bracket")
                    match = self._deserialize_match(match_data)
                    if match.match_id in matches_by_id:
                        raise database.DataValidationError(
                            f"match_id duplicado: {match.match_id}"
                        )
                    round_obj.matches.append(match)
                    matches_by_id[match.match_id] = match
                bracket.append(round_obj)

            history_data = state.get("fight_history")
            if history_data is None:
                # Saves antigos não persistiam o histórico. Reconstrói as
                # lutas reais concluídas, sem incluir avanços automáticos.
                fight_history = [
                    match
                    for round_obj in bracket
                    for match in round_obj.matches
                    if match.completed and match.ko_type != "BYE"
                ]
            else:
                if not isinstance(history_data, list):
                    raise database.DataValidationError("fight_history deve ser uma lista")
                fight_history = []
                for match_data in history_data:
                    if not isinstance(match_data, dict):
                        raise database.DataValidationError("historico contem luta invalida")
                    match = matches_by_id.get(match_data["match_id"])
                    if match is None:
                        match = self._deserialize_match(match_data)
                    elif "fight_log" in match_data:
                        match.fight_log = list(match_data.get("fight_log") or [])
                    fight_history.append(match)

            if current_round > len(bracket):
                raise database.DataValidationError("current_round esta fora do bracket")
            if current_round < len(bracket) and current_match > len(
                bracket[current_round].matches
            ):
                raise database.DataValidationError("current_match esta fora da rodada")

            # Commit em memoria: nenhuma validacao posterior pode deixar o
            # objeto parcialmente restaurado.
            self.name = name
            self.participants = participants
            self.state = tournament_state
            self.champion = champion
            self.current_round = current_round
            self.current_match = current_match
            self.stats = stats
            self.bracket = bracket
            self.fight_history = fight_history
            
            _console_print(f"OK: Estado carregado de {filepath}")
            return True
            
        except FileNotFoundError:
            _console_print(f"AVISO: Arquivo nao encontrado: {filepath}")
            return False
        except Exception as e:
            _console_print(f"ERRO: Falha ao carregar estado: {e}")
            return False


class TournamentRunner:
    """Executor de torneio - conecta torneio com simulador visual"""

    _DELETE_MATCH_CONFIG_ENV = "NEURAL_FIGHTS_DELETE_MATCH_CONFIG"
    
    def __init__(self, tournament: Tournament, match_config_path: str | None = None):
        self.tournament = tournament
        self.match_config_path = match_config_path
        self._isolated_visual_config = match_config_path is None
        self.simulation_config = {
            "max_duration": 120.0,
            "fixed_dt": 1.0 / 60.0,
            "seed": 0,
            "draw_retry_limit": 2,
            "auto_advance": True,
        }
    
    def setup_match_config(self, fighter1_name: str, fighter2_name: str, cenario: str = "Arena"):
        """Configura o match_config.json para a próxima luta"""
        config_path = self.match_config_path
        if self._isolated_visual_config:
            import tempfile
            import uuid

            config_path = os.path.join(
                tempfile.gettempdir(),
                f"neural-fights-match-{uuid.uuid4().hex}.json",
            )
        config = {
            "p1_nome": fighter1_name,
            "p2_nome": fighter2_name,
            "cenario": cenario,
            "best_of": 1,
            "portrait_mode": False
        }
        
        try:
            saved_path = database.salvar_match_config(
                config,
                preservar_existente=False,
                arquivo=config_path,
            )
        except Exception:
            if self._isolated_visual_config and config_path:
                self._remove_visual_config(config_path)
            raise

        self.match_config_path = saved_path

        return self.match_config_path

    @staticmethod
    def _remove_visual_config(config_path: str) -> None:
        try:
            os.remove(config_path)
        except FileNotFoundError:
            pass
    
    def launch_simulation(self):
        """Lança o simulador Pygame"""
        import subprocess
        import os

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = self.match_config_path

        env = os.environ.copy()
        if config_path:
            env[database.MATCH_CONFIG_ENV] = config_path
        if self._isolated_visual_config and config_path:
            env[self._DELETE_MATCH_CONFIG_ENV] = "1"

        # Usa o mesmo interpretador e o mesmo estado isolado do processo pai.
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "simulation.simulacao"],
                cwd=base_dir,
                env=env,
            )
        except Exception:
            if self._isolated_visual_config and config_path:
                self._remove_visual_config(config_path)
            raise

        if self._isolated_visual_config and config_path:
            import threading

            def cleanup_config():
                try:
                    process.wait()
                except Exception:
                    # A remoção continua obrigatória mesmo se wait() falhar.
                    pass
                finally:
                    self._remove_visual_config(config_path)

            threading.Thread(target=cleanup_config, daemon=True).start()
        return process
    
    def run_single_match_visual(self, match: TournamentMatch) -> bool:
        """Configura e lança uma luta visual"""
        # Configura o match
        self.setup_match_config(match.fighter1_name, match.fighter2_name)
        
        # Lança o simulador
        self.launch_simulation()
        
        return True
    
    def run_single_match(self, match: TournamentMatch) -> Dict:
        """Executa uma luta no mesmo motor usado pela apresentação visual."""
        from simulation.headless import run_headless_match

        config = {
            "p1_nome": match.fighter1_name,
            "p2_nome": match.fighter2_name,
            "cenario": "Arena",
            "best_of": 1,
            "portrait_mode": False,
        }
        retry_limit = int(self.simulation_config.get("draw_retry_limit", 2))
        if retry_limit < 0:
            return {
                "success": False,
                "error": "draw_retry_limit precisa ser maior ou igual a zero",
                "reason": "invalid_configuration",
            }

        initial_seed = int(self.simulation_config.get("seed", 0)) + int(match.match_id)
        engine_results = []
        result = None
        for attempt in range(retry_limit + 1):
            attempt_seed = initial_seed + attempt
            result = run_headless_match(
                config,
                fixed_dt=float(self.simulation_config.get("fixed_dt", 1.0 / 60.0)),
                max_duration=float(self.simulation_config.get("max_duration", 120.0)),
                seed=attempt_seed,
            )
            engine_results.append(result.to_dict())

            # Erros reais do motor são terminais; somente empates são refeitos.
            if not result.success:
                return {
                    "success": False,
                    "error": result.error or "Falha desconhecida no simulador",
                    "reason": "engine_error",
                    "attempts": attempt + 1,
                    "engine_result": result.to_dict(),
                    "engine_results": engine_results,
                }
            if result.winner is not None:
                break
        else:
            return {
                "success": False,
                "error": (
                    "Luta permaneceu empatada após "
                    f"{retry_limit + 1} tentativa(s) determinísticas"
                ),
                "reason": "draw_retry_exhausted",
                "attempts": retry_limit + 1,
                "engine_result": result.to_dict(),
                "engine_results": engine_results,
            }

        ko_type = (
            "Duplo KO" if result.reason == "double_ko"
            else "KO" if result.reason == "knockout"
            else "Decisão por HP"
        )
        return {
            "success": True,
            "winner": result.winner,
            "duration": result.duration,
            "ko_type": ko_type,
            "stats": {
                "frames": result.frames,
                "seed": result.seed,
                "p1_hp": result.p1_hp,
                "p2_hp": result.p2_hp,
                "p1_hp_ratio": result.p1_hp_ratio,
                "p2_hp_ratio": result.p2_hp_ratio,
                "reason": result.reason,
                "attempts": len(engine_results),
            },
            "engine_result": result.to_dict(),
            "engine_results": engine_results,
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
            _console_print("ERRO: Falha ao iniciar torneio")
            return
        
        _console_print(self.tournament.get_bracket_display())
        _console_print("\n" + "=" * 70)
        _console_print("  INICIANDO TORNEIO AUTOMATICO")
        _console_print("=" * 70)
        
        while self.tournament.state != TournamentState.FINISHED:
            match = self.tournament.get_current_match()
            
            if not match:
                break
            
            if match.fighter1_name.startswith("BYE") or match.fighter2_name.startswith("BYE"):
                # BYE já processado
                continue
            
            _console_print(f"\nLUTA: {match.fighter1_name} vs {match.fighter2_name}")
            
            # Executa a luta
            result = self.run_single_match(match)
            
            if result["success"]:
                winner = result["winner"]
                self.tournament.record_match_result(
                    winner_name=winner,
                    duration=result["duration"],
                    ko_type=result["ko_type"]
                )
                _console_print(
                    f"   Vencedor: {winner} "
                    f"({result['ko_type']} em {result['duration']:.1f}s)"
                )
            else:
                raise RuntimeError(
                    "Falha ao executar luta real do torneio: "
                    + str(result.get("error", "erro desconhecido"))
                )
            
            time.sleep(delay_between_fights)
        
        _console_print("\n" + self.tournament.get_bracket_display())
        self.tournament.save_state()


if __name__ == "__main__":
    # Teste do sistema de torneio
    _console_print("=" * 70)
    _console_print("  NEURAL FIGHTS - SISTEMA DE TORNEIO")
    _console_print("=" * 70)
    
    tournament = Tournament("Torneio Teste")
    
    # Carrega participantes
    tournament.load_participants_from_database(max_participants=8)
    
    if len(tournament.participants) < 2:
        # Adiciona participantes de teste
        _console_print("\nAdicionando participantes de teste...")
        for i in range(8):
            tournament.add_participant(f"Lutador_{i+1}")
    
    # Gera bracket
    tournament.generate_bracket()
    
    # Mostra bracket
    _console_print(tournament.get_bracket_display())
    
    # Simula algumas lutas manualmente
    tournament.start_tournament()
    
    match = tournament.get_current_match()
    if match:
        _console_print(f"\nProxima luta: {match.fighter1_name} vs {match.fighter2_name}")
