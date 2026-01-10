# backend/game.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Tuple
import random
import uuid
from pathlib import Path

LetterState = Literal["correct", "present", "absent"]

DEFAULT_WORD_LEN = 5
DEFAULT_MAX_GUESSES = 6
DEFAULT_SKIP_COOLDOWN_LEVELS = 3

def load_words(path: str) -> List[str]:
    p = Path(path)
    words = []
    for line in p.read_text(encoding="utf-8").splitlines():
        w = line.strip().upper()
        if len(w) == DEFAULT_WORD_LEN and w.isalpha():
            words.append(w)
    if not words:
        raise ValueError("words.txt is empty or invalid.")
    return words

def evaluate_guess(secret: str, guess: str) -> List[LetterState]:
    """
    Wordle-style evaluation that handles duplicate letters correctly.
    """
    secret = secret.upper()
    guess = guess.upper()

    result: List[LetterState] = ["absent"] * len(secret)
    secret_counts: Dict[str, int] = {}

    # Count letters in secret
    for ch in secret:
        secret_counts[ch] = secret_counts.get(ch, 0) + 1

    # First pass: correct letters
    for i, ch in enumerate(guess):
        if ch == secret[i]:
            result[i] = "correct"
            secret_counts[ch] -= 1

    # Second pass: present letters
    for i, ch in enumerate(guess):
        if result[i] == "correct":
            continue
        if secret_counts.get(ch, 0) > 0:
            result[i] = "present"
            secret_counts[ch] -= 1

    return result

@dataclass
class RunState:
    run_id: str
    level: int = 1
    secret: str = ""
    guesses: List[str] = field(default_factory=list)
    feedback: List[List[LetterState]] = field(default_factory=list)

    # skip cooldown
    last_skip_level: int = -999
    skip_cooldown_levels: int = DEFAULT_SKIP_COOLDOWN_LEVELS

    # powerups: after a win we offer 3 choices
    pending_powerups: List[dict] = field(default_factory=list)

    @property
    def won(self) -> bool:
        return any(g == self.secret for g in self.guesses)

    @property
    def failed(self) -> bool:
        return (not self.won) and (len(self.guesses) >= DEFAULT_MAX_GUESSES)

    @property
    def skip_available(self) -> bool:
        return (self.level - self.last_skip_level) >= self.skip_cooldown_levels

    def skip_in_levels(self) -> int:
        remaining = self.skip_cooldown_levels - (self.level - self.last_skip_level)
        return max(0, remaining)

class GameManager:
    def __init__(self, words: List[str]):
        self.words = words
        self.runs: Dict[str, RunState] = {}

    def _new_secret(self) -> str:
        return random.choice(self.words)

    def start_run(self) -> RunState:
        run_id = str(uuid.uuid4())
        rs = RunState(run_id=run_id, secret=self._new_secret())
        self.runs[run_id] = rs
        return rs

    def get_run(self, run_id: str) -> RunState:
        if run_id not in self.runs:
            raise KeyError("Run not found.")
        return self.runs[run_id]

    def submit_guess(self, run_id: str, guess: str) -> RunState:
        rs = self.get_run(run_id)
        guess = guess.strip().upper()

        if rs.pending_powerups:
            # player must choose powerup before continuing
            return rs

        if rs.won or rs.failed:
            # level already ended; ignore guesses
            return rs

        if len(guess) != DEFAULT_WORD_LEN or not guess.isalpha():
            return rs

        rs.guesses.append(guess)
        rs.feedback.append(evaluate_guess(rs.secret, guess))

        # If won, create powerup choices
        if rs.won:
            rs.pending_powerups = self._roll_powerups()

        # If failed, advance immediately (no powerup)
        if rs.failed:
            self._advance_level(rs, reward=False)

        return rs

    def skip_level(self, run_id: str) -> RunState:
        rs = self.get_run(run_id)
        if rs.pending_powerups:
            return rs

        if not rs.skip_available:
            return rs

        rs.last_skip_level = rs.level
        self._advance_level(rs, reward=False)
        return rs

    def choose_powerup(self, run_id: str, powerup_id: str) -> Tuple[RunState, dict]:
        rs = self.get_run(run_id)
        if not rs.pending_powerups:
            return rs, {}

        chosen = next((p for p in rs.pending_powerups if p["id"] == powerup_id), None)
        if not chosen:
            return rs, {}

        rs.pending_powerups = []
        self._advance_level(rs, reward=True)
        return rs, chosen

    def _advance_level(self, rs: RunState, reward: bool):
        rs.level += 1
        rs.secret = self._new_secret()
        rs.guesses = []
        rs.feedback = []
        rs.pending_powerups = []

    def _roll_powerups(self) -> List[dict]:
        pool = [
            {"id": "time_plus_10", "type": "time", "value": 10, "name": "+10 seconds", "desc": "Adds 10 seconds to your run timer."},
            {"id": "reveal_first", "type": "reveal", "value": "first", "name": "Reveal first letter", "desc": "Reveals the first letter of the next word."},
            {"id": "gemini_hint", "type": "hint", "value": "definition", "name": "Gemini hint", "desc": "Get a hint generated by Gemini."},
        ]
        return random.sample(pool, 3)
