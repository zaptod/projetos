"""Seeded randomness. One master seed -> deterministic, independent sub-streams.

Every subsystem asks for its own namespaced stream so adding a roll in one
place never shifts the results of another (stable rerenders per seed).
"""
from __future__ import annotations

import hashlib
import random


class RandomEngine:
    def __init__(self, seed: int):
        self.seed = int(seed)

    def fork(self, namespace: str) -> random.Random:
        digest = hashlib.sha256(f"{self.seed}:{namespace}".encode("utf-8")).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))

    @staticmethod
    def new_seed() -> int:
        return random.SystemRandom().randrange(1, 2**31)
