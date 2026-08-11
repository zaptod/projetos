class BestOfSeries:
    """Estado puro de uma série melhor-de-N entre os slots p1 e p2."""

    SLOTS = ("p1", "p2")

    def __init__(self, best_of=1):
        if type(best_of) is not int or best_of <= 0 or best_of % 2 == 0:
            raise ValueError("best_of deve ser um inteiro ímpar positivo")

        self.best_of = best_of
        self.required_wins = best_of // 2 + 1
        self.wins = {slot: 0 for slot in self.SLOTS}
        self.round_number = 1
        self.winner = None
        self.round_closed = False
        self.round_winner = None
        self.round_draw = False

    @property
    def finished(self):
        return self.winner is not None

    def record_win(self, slot):
        if slot not in self.SLOTS:
            raise ValueError(f"slot inválido: {slot}")
        if self.finished or self.round_closed:
            return False

        self.wins[slot] += 1
        self.round_winner = slot
        self.round_draw = False
        self.round_closed = True

        if self.wins[slot] >= self.required_wins:
            self.winner = slot
        return True

    def record_draw(self):
        if self.finished or self.round_closed:
            return False

        self.round_winner = None
        self.round_draw = True
        self.round_closed = True
        return True

    def reset_round(self):
        """Abre o próximo round; empates e resets manuais repetem o número."""
        if self.finished:
            return False

        if self.round_closed and not self.round_draw:
            self.round_number += 1

        self.round_closed = False
        self.round_winner = None
        self.round_draw = False
        return True

    def reset_series(self):
        self.wins = {slot: 0 for slot in self.SLOTS}
        self.round_number = 1
        self.winner = None
        self.round_closed = False
        self.round_winner = None
        self.round_draw = False
