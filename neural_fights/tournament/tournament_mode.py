"""
NEURAL FIGHTS - Sistema de Torneio v1.0
=======================================
Modo torneio com chaves eliminatórias.
Coloca todos os personagens em brackets e roda lutas automaticamente.
"""

import random
import math
import os
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

from neural_fights.data import database
from neural_fights.data.database import carregar_personagens
from neural_fights.utils.console import safe_print as _console_print


TOURNAMENT_STATE_ENV = "NEURAL_FIGHTS_TOURNAMENT_STATE"
DEFAULT_TOURNAMENT_STATE = os.path.join(
    database.RUNTIME_DIR,
    "tournament_state.json",
)


_VISUAL_CONFIG_PREFIX = "neural-fights-match-"
_VISUAL_CONFIG_SUFFIX = ".json"


def _validated_generated_visual_config_path(path) -> str | None:
    """Resolve apenas nomes UUID criados diretamente no diretório temporário."""

    if not isinstance(path, (str, os.PathLike)):
        return None
    try:
        raw_path = os.fspath(path)
        if not isinstance(raw_path, str) or not raw_path:
            return None
        resolved = os.path.realpath(os.path.abspath(raw_path))
        temp_dir = os.path.realpath(tempfile.gettempdir())
    except (OSError, TypeError, ValueError):
        return None

    if os.path.normcase(os.path.dirname(resolved)) != os.path.normcase(temp_dir):
        return None

    basename = os.path.basename(resolved)
    if not (
        basename.startswith(_VISUAL_CONFIG_PREFIX)
        and basename.endswith(_VISUAL_CONFIG_SUFFIX)
    ):
        return None
    token = basename[
        len(_VISUAL_CONFIG_PREFIX) : -len(_VISUAL_CONFIG_SUFFIX)
    ]
    if len(token) != 32 or any(char not in "0123456789abcdef" for char in token):
        return None
    return resolved


def _is_generated_visual_config(path) -> bool:
    """Indica se o caminho possui o formato isolado aceito para cleanup."""

    return _validated_generated_visual_config_path(path) is not None


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
    fighter1_is_bye: bool = False
    fighter2_is_bye: bool = False
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
        self._generated_byes: set[str] = set()
        
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
        self._generated_byes.intersection_update(self.participants)
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
                counter = i + 1
                bye_name = f"BYE_{counter}"
                while bye_name in self.participants:
                    counter += 1
                    bye_name = f"BYE_{counter}"
                self.participants.append(bye_name)
                self._generated_byes.add(bye_name)
        else:
            # Trunca para power // 2
            self.participants = self.participants[:power // 2]
    
    def shuffle_participants(self):
        """Embaralha os participantes"""
        random.shuffle(self.participants)
        if not self._generated_byes:
            return

        # Distribui cada bye contra um participante real. Um pareamento
        # bye-vs-bye propagaria um placeholder como se fosse lutador.
        real = [
            name for name in self.participants if name not in self._generated_byes
        ]
        byes = [
            name for name in self.participants if name in self._generated_byes
        ]
        pairs = []
        for bye_name in byes:
            pairs.append([real.pop(), bye_name])
        while real:
            pairs.append([real.pop(), real.pop()])
        random.shuffle(pairs)
        self.participants = [name for pair in pairs for name in pair]
    
    def generate_bracket(self) -> bool:
        """Gera uma chave nova e descarta todo progresso da chave anterior."""
        if len(self.participants) < 2:
            _console_print("ERRO: Minimo de 2 participantes necessario!")
            return False

        # Regenerar é uma nova competição com os mesmos participantes. Nenhum
        # resultado derivado da chave anterior pode sobreviver à operação.
        self.bracket = []
        self.state = TournamentState.WAITING
        self.champion = None
        self.current_round = 0
        self.current_match = 0
        self.fight_history = []
        self.stats = {
            "total_fights": 0,
            "total_kos": 0,
            "fastest_ko": None,
            "longest_fight": None,
            "most_aggressive": None,
        }
        
        self._adjust_to_power_of_two()
        self.shuffle_participants()
        
        n = len(self.participants)
        
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
                        fighter2_name=self.participants[i + 1],
                        fighter1_is_bye=(
                            self.participants[i] in self._generated_byes
                        ),
                        fighter2_is_bye=(
                            self.participants[i + 1] in self._generated_byes
                        ),
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
            
            if match.fighter1_is_bye:
                match.winner_name = match.fighter2_name
                match.loser_name = match.fighter1_name
                match.completed = True
                match.ko_type = "BYE"
                self._advance_winner(match)
            elif match.fighter2_is_bye:
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

        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not math.isfinite(float(duration))
            or duration < 0
        ):
            raise ValueError("duration precisa ser finita e nao negativa")
        if not isinstance(ko_type, str):
            raise TypeError("ko_type precisa ser uma string")
        if fight_log is not None and (
            not isinstance(fight_log, list)
            or not all(isinstance(item, str) for item in fight_log)
        ):
            raise TypeError("fight_log precisa ser uma lista de strings")
        
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
            "fighter1_is_bye": match.fighter1_is_bye,
            "fighter2_is_bye": match.fighter2_is_bye,
            "winner_name": match.winner_name,
            "loser_name": match.loser_name,
            "duration": match.duration,
            "ko_type": match.ko_type,
            "fight_log": list(match.fight_log),
            "completed": match.completed,
        }

    @staticmethod
    def _deserialize_match(match_data: Dict) -> TournamentMatch:
        """Restaura uma luta somente depois de validar seu contrato inteiro."""

        try:
            match_id = match_data["match_id"]
            round_num = match_data["round_num"]
            fighter1 = match_data["fighter1_name"]
            fighter2 = match_data["fighter2_name"]
        except KeyError as exc:
            raise database.DataValidationError(
                f"luta sem campo obrigatorio: {exc.args[0]}"
            ) from exc

        for field_name, value in (("match_id", match_id), ("round_num", round_num)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise database.DataValidationError(
                    f"{field_name} deve ser um inteiro nao negativo"
                )
        if not all(isinstance(name, str) and name for name in (fighter1, fighter2)):
            raise database.DataValidationError(
                "fighter1_name e fighter2_name devem ser strings nao vazias"
            )

        fighter1_is_bye = match_data.get("fighter1_is_bye", False)
        fighter2_is_bye = match_data.get("fighter2_is_bye", False)
        if not isinstance(fighter1_is_bye, bool) or not isinstance(
            fighter2_is_bye, bool
        ):
            raise database.DataValidationError("flags de BYE devem ser booleanas")
        if fighter1_is_bye and fighter2_is_bye:
            raise database.DataValidationError("uma luta nao pode conter dois BYEs")

        duration = match_data.get("duration", 0.0)
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not math.isfinite(float(duration))
            or duration < 0
        ):
            raise database.DataValidationError(
                "duration deve ser numerica, finita e nao negativa"
            )
        ko_type = match_data.get("ko_type", "")
        completed = match_data.get("completed", False)
        fight_log = match_data.get("fight_log", [])
        winner = match_data.get("winner_name")
        loser = match_data.get("loser_name")
        if not isinstance(ko_type, str):
            raise database.DataValidationError("ko_type deve ser uma string")
        if not isinstance(completed, bool):
            raise database.DataValidationError("completed deve ser booleano")
        if fight_log is None:  # compatibilidade com saves legados
            fight_log = []
        if not isinstance(fight_log, list) or not all(
            isinstance(item, str) for item in fight_log
        ):
            raise database.DataValidationError(
                "fight_log deve ser uma lista de strings"
            )
        for field_name, value in (("winner_name", winner), ("loser_name", loser)):
            if value is not None and (not isinstance(value, str) or not value):
                raise database.DataValidationError(
                    f"{field_name} deve ser nulo ou uma string nao vazia"
                )
        fighters = {fighter1, fighter2}
        if completed:
            if winner not in fighters or loser not in fighters or winner == loser:
                raise database.DataValidationError(
                    "luta concluida precisa de vencedor e perdedor coerentes"
                )
        elif winner is not None or loser is not None:
            raise database.DataValidationError(
                "luta pendente nao pode possuir vencedor ou perdedor"
            )
        elif duration != 0 or ko_type or fight_log:
            raise database.DataValidationError(
                "luta pendente nao pode possuir resultado parcial"
            )

        return TournamentMatch(
            match_id=match_id,
            round_num=round_num,
            fighter1_name=fighter1,
            fighter2_name=fighter2,
            fighter1_is_bye=fighter1_is_bye,
            fighter2_is_bye=fighter2_is_bye,
            winner_name=winner,
            loser_name=loser,
            duration=float(duration),
            ko_type=ko_type,
            fight_log=list(fight_log),
            completed=completed,
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
            "generated_byes": sorted(self._generated_byes),
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

            has_explicit_generated_byes = "generated_byes" in state
            generated_byes_data = state.get("generated_byes", [])
            if not isinstance(generated_byes_data, list) or not all(
                isinstance(name, str) and name for name in generated_byes_data
            ):
                raise database.DataValidationError(
                    "generated_byes deve ser uma lista de nomes"
                )
            if len(generated_byes_data) != len(set(generated_byes_data)):
                raise database.DataValidationError(
                    "generated_byes contem nomes duplicados"
                )
            explicit_generated_byes = set(generated_byes_data)
            for bye_name in explicit_generated_byes:
                suffix = bye_name.removeprefix("BYE_")
                if (
                    bye_name not in participants
                    or not bye_name.startswith("BYE_")
                    or not suffix.isdigit()
                    or int(suffix) < 1
                    or str(int(suffix)) != suffix
                ):
                    raise database.DataValidationError(
                        "generated_byes deve referenciar sentinelas BYE_N validas"
                    )

            tournament_state = TournamentState(state["state"])
            champion = state.get("champion")
            if champion is not None and (
                not isinstance(champion, str) or not champion
            ):
                raise database.DataValidationError(
                    "champion deve ser nulo ou uma string nao vazia"
                )
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
            unknown_stats = set(stats_data) - set(self.stats)
            if unknown_stats:
                raise database.DataValidationError(
                    "stats contem campos desconhecidos: "
                    + ", ".join(sorted(unknown_stats))
                )
            stats = dict(self.stats)
            stats.update(stats_data)
            for field_name in ("total_fights", "total_kos"):
                value = stats[field_name]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise database.DataValidationError(
                        f"stats.{field_name} deve ser inteiro nao negativo"
                    )
            if stats["total_kos"] > stats["total_fights"]:
                raise database.DataValidationError(
                    "stats.total_kos nao pode exceder total_fights"
                )
            for field_name in ("fastest_ko", "longest_fight"):
                value = stats[field_name]
                if value is not None and (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    or value < 0
                ):
                    raise database.DataValidationError(
                        f"stats.{field_name} deve ser nulo ou numero nao negativo"
                    )
            most_aggressive = stats["most_aggressive"]
            if most_aggressive is not None and (
                not isinstance(most_aggressive, str) or not most_aggressive
            ):
                raise database.DataValidationError(
                    "stats.most_aggressive deve ser nulo ou string nao vazia"
                )

            bracket_data = state["bracket"]
            if not isinstance(bracket_data, list):
                raise database.DataValidationError("bracket deve ser uma lista")
            bracket = []
            matches_by_id = {}
            next_match_id = 0
            for expected_round_num, round_data in enumerate(bracket_data):
                if not isinstance(round_data, dict) or not isinstance(
                    round_data.get("matches"), list
                ):
                    raise database.DataValidationError("rodada invalida no bracket")
                round_num = round_data.get("round_num")
                round_name = round_data.get("name")
                round_completed = round_data.get("completed")
                if round_num != expected_round_num or isinstance(round_num, bool):
                    raise database.DataValidationError(
                        "round_num deve ser sequencial a partir de zero"
                    )
                if not isinstance(round_name, str) or not round_name:
                    raise database.DataValidationError(
                        "nome da rodada deve ser uma string nao vazia"
                    )
                if not isinstance(round_completed, bool):
                    raise database.DataValidationError(
                        "completed da rodada deve ser booleano"
                    )
                round_obj = TournamentRound(
                    round_num=round_num,
                    name=round_name,
                    completed=round_completed,
                )
                for match_data in round_data["matches"]:
                    if not isinstance(match_data, dict):
                        raise database.DataValidationError("luta invalida no bracket")
                    match = self._deserialize_match(match_data)
                    if match.round_num != round_num:
                        raise database.DataValidationError(
                            "round_num da luta diverge da rodada"
                        )
                    if match.match_id in matches_by_id:
                        raise database.DataValidationError(
                            f"match_id duplicado: {match.match_id}"
                        )
                    if match.match_id != next_match_id:
                        raise database.DataValidationError(
                            "match_id deve ser sequencial na ordem do bracket"
                        )
                    round_obj.matches.append(match)
                    matches_by_id[match.match_id] = match
                    next_match_id += 1
                if round_obj.completed != all(
                    match.completed for match in round_obj.matches
                ):
                    raise database.DataValidationError(
                        "estado completed da rodada diverge de suas lutas"
                    )
                bracket.append(round_obj)

            bracket_generated_byes = set()
            if bracket:
                participant_count = len(participants)
                if (
                    participant_count < 2
                    or participant_count & (participant_count - 1)
                ):
                    raise database.DataValidationError(
                        "bracket exige uma quantidade de participantes "
                        "que seja potencia de dois"
                    )

                expected_rounds = participant_count.bit_length() - 1
                if len(bracket) != expected_rounds:
                    raise database.DataValidationError(
                        "quantidade de rodadas diverge dos participantes"
                    )

                expected_matches = participant_count // 2
                for round_obj in bracket:
                    if len(round_obj.matches) != expected_matches:
                        raise database.DataValidationError(
                            "quantidade de lutas da rodada diverge do bracket"
                        )
                    expected_matches //= 2

                first_round_names = [
                    fighter_name
                    for match in bracket[0].matches
                    for fighter_name in (
                        match.fighter1_name,
                        match.fighter2_name,
                    )
                ]
                if len(first_round_names) != len(participants) or set(
                    first_round_names
                ) != set(participants):
                    raise database.DataValidationError(
                        "primeira rodada diverge da lista de participantes"
                    )

                for round_index, round_obj in enumerate(bracket):
                    for match in round_obj.matches:
                        fighters_and_flags = (
                            (match.fighter1_name, match.fighter1_is_bye),
                            (match.fighter2_name, match.fighter2_is_bye),
                        )
                        if round_index > 0 and any(
                            is_bye for _, is_bye in fighters_and_flags
                        ):
                            raise database.DataValidationError(
                                "flags de BYE so podem existir na primeira rodada"
                            )

                        for fighter_name, is_bye in fighters_and_flags:
                            if is_bye:
                                suffix = fighter_name.removeprefix("BYE_")
                                if (
                                    not fighter_name.startswith("BYE_")
                                    or not suffix.isdigit()
                                    or int(suffix) < 1
                                    or str(int(suffix)) != suffix
                                ):
                                    raise database.DataValidationError(
                                        "flag de BYE exige sentinela BYE_N valida"
                                    )
                                bracket_generated_byes.add(fighter_name)
                            elif (
                                round_index > 0
                                and fighter_name not in participants
                                and fighter_name != "TBD"
                            ):
                                raise database.DataValidationError(
                                    "bracket referencia lutador desconhecido"
                                )

                        has_bye = any(
                            is_bye for _, is_bye in fighters_and_flags
                        )
                        if has_bye and sum(
                            bool(is_bye) for _, is_bye in fighters_and_flags
                        ) != 1:
                            raise database.DataValidationError(
                                "luta de BYE exige exatamente uma sentinela"
                            )
                        if match.completed and "TBD" in (
                            match.fighter1_name,
                            match.fighter2_name,
                        ):
                            raise database.DataValidationError(
                                "luta concluida nao pode conter vaga TBD"
                            )
                        if has_bye:
                            bye_name = next(
                                fighter_name
                                for fighter_name, is_bye in fighters_and_flags
                                if is_bye
                            )
                            real_name = next(
                                fighter_name
                                for fighter_name, is_bye in fighters_and_flags
                                if not is_bye
                            )
                            if match.completed and (
                                match.winner_name != real_name
                                or match.loser_name != bye_name
                                or match.ko_type != "BYE"
                            ):
                                raise database.DataValidationError(
                                    "resultado de BYE diverge de sua sentinela"
                                )
                        elif match.ko_type == "BYE":
                            raise database.DataValidationError(
                                "ko_type BYE exige uma sentinela marcada"
                            )

                for round_index in range(1, len(bracket)):
                    previous_round = bracket[round_index - 1]
                    current = bracket[round_index]
                    for match_index, match in enumerate(current.matches):
                        predecessors = previous_round.matches[
                            match_index * 2 : match_index * 2 + 2
                        ]
                        expected_fighters = tuple(
                            predecessor.winner_name
                            if predecessor.completed
                            else "TBD"
                            for predecessor in predecessors
                        )
                        actual_fighters = (
                            match.fighter1_name,
                            match.fighter2_name,
                        )
                        if actual_fighters != expected_fighters:
                            raise database.DataValidationError(
                                "propagacao de vencedores diverge entre rodadas"
                            )

            if has_explicit_generated_byes:
                if bracket and explicit_generated_byes != bracket_generated_byes:
                    raise database.DataValidationError(
                        "generated_byes diverge das flags de BYE do bracket"
                    )
                generated_byes = explicit_generated_byes
            else:
                # Saves legados com bracket permitem inferência pelas flags
                # canônicas. Sem bracket, BYE_N pode ser um nome real e não é
                # promovido implicitamente a sentinela.
                generated_byes = bracket_generated_byes

            if generated_byes and not bracket:
                participant_count = len(participants)
                if (
                    participant_count < 2
                    or participant_count & (participant_count - 1)
                    or len(generated_byes) >= participant_count // 2
                ):
                    raise database.DataValidationError(
                        "generated_byes pre-bracket exige padding valido"
                    )

            history_data = state.get("fight_history")
            completed_real_matches = [
                match
                for round_obj in bracket
                for match in round_obj.matches
                if match.completed and match.ko_type != "BYE"
            ]
            if history_data is None:
                # Saves antigos não persistiam o histórico. Reconstrói as
                # lutas reais concluídas, sem incluir avanços automáticos.
                fight_history = completed_real_matches
            else:
                if not isinstance(history_data, list):
                    raise database.DataValidationError("fight_history deve ser uma lista")
                fight_history = []
                history_ids = set()
                for match_data in history_data:
                    if not isinstance(match_data, dict):
                        raise database.DataValidationError("historico contem luta invalida")
                    history_match = self._deserialize_match(match_data)
                    match = matches_by_id.get(history_match.match_id)
                    if match is None:
                        raise database.DataValidationError(
                            "historico referencia luta ausente do bracket"
                        )
                    if history_match != match:
                        raise database.DataValidationError(
                            "historico diverge da luta no bracket"
                        )
                    if match.match_id in history_ids:
                        raise database.DataValidationError(
                            f"historico repete match_id: {match.match_id}"
                        )
                    if not match.completed or match.ko_type == "BYE":
                        raise database.DataValidationError(
                            "historico contem luta pendente ou BYE"
                        )
                    history_ids.add(match.match_id)
                    fight_history.append(match)
                if [match.match_id for match in fight_history] != [
                    match.match_id for match in completed_real_matches
                ]:
                    raise database.DataValidationError(
                        "fight_history nao corresponde as lutas concluidas do bracket"
                    )

            if current_round > len(bracket):
                raise database.DataValidationError("current_round esta fora do bracket")
            if current_round < len(bracket) and current_match >= len(
                bracket[current_round].matches
            ):
                raise database.DataValidationError("current_match esta fora da rodada")
            if current_round == len(bracket) and current_match != 0:
                raise database.DataValidationError(
                    "current_match deve ser zero ao final do bracket"
                )
            pending_positions = [
                (round_index, match_index)
                for round_index, round_obj in enumerate(bracket)
                for match_index, match in enumerate(round_obj.matches)
                if not match.completed
            ]
            if tournament_state == TournamentState.WAITING:
                if (
                    any(match.completed for match in matches_by_id.values())
                    or fight_history
                    or current_round != 0
                    or current_match != 0
                ):
                    raise database.DataValidationError(
                        "torneio aguardando nao pode conter progresso"
                    )
            elif tournament_state in {
                TournamentState.IN_PROGRESS,
                TournamentState.ROUND_COMPLETE,
            }:
                if (
                    not bracket
                    or not pending_positions
                    or (current_round, current_match) != pending_positions[0]
                ):
                    raise database.DataValidationError(
                        "ponteiro ativo deve indicar a primeira luta pendente"
                    )
            if tournament_state == TournamentState.FINISHED:
                if (
                    not bracket
                    or current_round != len(bracket)
                    or champion not in participants
                    or not all(round_obj.completed for round_obj in bracket)
                    or not bracket[-1].matches[0].completed
                    or champion != bracket[-1].matches[0].winner_name
                ):
                    raise database.DataValidationError(
                        "torneio finalizado precisa de final e campeao coerentes"
                    )
            elif (bracket and current_round == len(bracket)) or champion is not None:
                raise database.DataValidationError(
                    "torneio ativo nao pode possuir estado final"
                )
            if stats["total_fights"] != len(fight_history):
                raise database.DataValidationError(
                    "stats.total_fights diverge do fight_history"
                )
            expected_kos = sum("KO" in match.ko_type for match in fight_history)
            if stats["total_kos"] != expected_kos:
                raise database.DataValidationError(
                    "stats.total_kos diverge do fight_history"
                )

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
            self._generated_byes = generated_byes
            
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
        self._generated_visual_configs: set[str] = set()
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
            config_path = self._reserve_visual_config()
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
        except BaseException:
            if self._owns_visual_config(config_path):
                self._remove_visual_config(config_path)
            raise

        if self._isolated_visual_config:
            expected_path = _validated_generated_visual_config_path(config_path)
            returned_path = _validated_generated_visual_config_path(saved_path)
            if returned_path != expected_path:
                self._remove_visual_config(config_path)
                raise RuntimeError(
                    "salvar_match_config retornou caminho diferente do temporario reservado"
                )
            self.match_config_path = expected_path
        else:
            self.match_config_path = saved_path

        return self.match_config_path

    def _reserve_visual_config(self) -> str:
        """Reserva exclusivamente um caminho temporário pertencente ao runner."""

        for _ in range(16):
            candidate = os.path.join(
                tempfile.gettempdir(),
                f"{_VISUAL_CONFIG_PREFIX}{uuid.uuid4().hex}{_VISUAL_CONFIG_SUFFIX}",
            )
            normalized = _validated_generated_visual_config_path(candidate)
            if normalized is None:
                raise RuntimeError("diretorio temporario gerou caminho inseguro")
            try:
                descriptor = os.open(
                    normalized,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
            except FileExistsError:
                continue
            os.close(descriptor)
            self._generated_visual_configs.add(normalized)
            return normalized
        raise RuntimeError("nao foi possivel reservar match config temporaria")

    def _owns_visual_config(self, config_path) -> bool:
        normalized = _validated_generated_visual_config_path(config_path)
        return (
            normalized is not None
            and normalized in self._generated_visual_configs
        )

    def _remove_visual_config(self, config_path) -> bool:
        normalized = _validated_generated_visual_config_path(config_path)
        if (
            normalized is None
            or normalized not in self._generated_visual_configs
        ):
            return False
        try:
            os.remove(normalized)
        except FileNotFoundError:
            pass
        except OSError:
            return False
        self._generated_visual_configs.discard(normalized)
        return True
    
    def launch_simulation(self, config_path: str | None = None):
        """Lança o simulador Pygame"""
        import subprocess
        import os

        # O subprocesso precisa enxergar o diretório que contém o pacote
        # ``neural_fights`` tanto no checkout quanto em uma instalação.
        package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base_dir = os.path.dirname(package_dir)
        config_path = config_path or self.match_config_path

        env = os.environ.copy()
        env.pop(database.MATCH_CONFIG_ENV, None)
        env.pop(self._DELETE_MATCH_CONFIG_ENV, None)
        if config_path:
            env[database.MATCH_CONFIG_ENV] = config_path
        owned_config_path = (
            _validated_generated_visual_config_path(config_path)
            if self._owns_visual_config(config_path)
            else None
        )
        if owned_config_path:
            env[self._DELETE_MATCH_CONFIG_ENV] = "1"

        # Usa o mesmo interpretador e o mesmo estado isolado do processo pai.
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "neural_fights.simulation.simulacao"],
                cwd=base_dir,
                env=env,
            )
        except BaseException:
            if owned_config_path:
                self._remove_visual_config(owned_config_path)
            raise

        if owned_config_path:
            import threading

            def cleanup_config():
                try:
                    process.wait()
                except Exception:
                    # A remoção continua obrigatória mesmo se wait() falhar.
                    pass
                finally:
                    self._remove_visual_config(owned_config_path)

            threading.Thread(target=cleanup_config, daemon=True).start()
        return process
    
    def run_single_match_visual(self, match: TournamentMatch) -> bool:
        """Configura e lança uma luta visual"""
        # Configura o match
        config_path = self.setup_match_config(
            match.fighter1_name,
            match.fighter2_name,
        )
        
        # Lança o simulador
        self.launch_simulation(config_path)
        
        return True
    
    def run_single_match(self, match: TournamentMatch) -> Dict:
        """Executa uma luta no mesmo motor usado pela apresentação visual."""
        from neural_fights.simulation.headless import run_headless_match

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
            
            if match.fighter1_is_bye or match.fighter2_is_bye:
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
