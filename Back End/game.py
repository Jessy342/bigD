# backend/game.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Literal, Optional, Tuple
import random
import re
import uuid
from pathlib import Path

LetterState = Literal["correct", "present", "absent"]

DEFAULT_WORD_LEN = 5
DEFAULT_MAX_GUESSES = 6
DEFAULT_SKIP_COOLDOWN_LEVELS = 3

COMMON_LETTERS = set("ETAOINSHRDL")
MID_LETTERS = set("CUMWFGYPB")
RARE_LETTERS = set("VKJXQZ")
VOWELS = set("AEIOU")

DIFFICULTY_LABELS = ["easy", "medium", "hard", "expert", "master", "legend"]

@dataclass(frozen=True)
class WordEntry:
    word: str
    score: int
    percentile: float

def is_boss_level(level: int) -> bool:
    return level > 0 and (level % 10 == 0)

def level_tier(level: int) -> int:
    return max(0, (level - 1) // 3)

def difficulty_label(level: int) -> str:
    if is_boss_level(level):
        return "boss"
    tier = level_tier(level)
    return DIFFICULTY_LABELS[min(tier, len(DIFFICULTY_LABELS) - 1)]

def difficulty_multiplier(level: int) -> int:
    tier = level_tier(level)
    base = 1 + min(tier, 5)
    if is_boss_level(level):
        return base + 4
    return base

def difficulty_band(level: int) -> Tuple[float, float]:
    if is_boss_level(level):
        return (0.9, 1.0)
    tier = level_tier(level)
    target = min(0.2 + (tier * 0.12), 0.85)
    width = 0.35 if tier < 3 else 0.25
    low = max(0.0, target - (width / 2))
    high = min(1.0, target + (width / 2))
    return (low, high)

def word_difficulty_score(word: str) -> int:
    score = 0
    unique = set()
    vowel_count = 0
    for ch in word.upper():
        if ch in VOWELS:
            vowel_count += 1
        if ch in RARE_LETTERS:
            score += 3
        elif ch in MID_LETTERS:
            score += 2
        else:
            score += 1
        if ch in unique:
            score += 2
        unique.add(ch)
    if vowel_count <= 1:
        score += 2
    elif vowel_count >= 4:
        score += 1
    return score

def _load_words_from_file(path: Path) -> List[str]:
    if not path.exists():
        return []
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        w = line.strip().upper()
        if len(w) == DEFAULT_WORD_LEN and w.isalpha():
            words.append(w)
    return words

def _load_words_from_frontend(base_dir: Path) -> List[str]:
    word_list_path = (base_dir / ".." / "Front End" / "src" / "utils" / "wordList.ts").resolve()
    if not word_list_path.exists():
        return []
    text = word_list_path.read_text(encoding="utf-8")
    candidates = re.findall(r"'([A-Z]{5})'", text)
    return [word.upper() for word in candidates if word.isalpha()]

def load_words(path: str) -> List[str]:
    p = Path(path)
    words = _load_words_from_file(p)
    words.extend(_load_words_from_frontend(p.parent))
    words = sorted(set(words))
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
    score: int = 0
    last_score_delta: int = 0
    difficulty: str = "easy"
    boss_level: bool = False

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
    def __init__(self, words: List[str], word_provider: Optional[Callable[[int, str], str]] = None):
        self.words = words
        self.word_set = set(words)
        self.word_entries = self._build_word_entries(words)
        self.word_provider = word_provider
        self.runs: Dict[str, RunState] = {}

    def _build_word_entries(self, words: List[str]) -> List[WordEntry]:
        scored = sorted(((word, word_difficulty_score(word)) for word in words), key=lambda x: x[1])
        total = len(scored)
        entries: List[WordEntry] = []
        for idx, (word, score) in enumerate(scored):
            percentile = (idx / (total - 1)) if total > 1 else 1.0
            entries.append(WordEntry(word=word, score=score, percentile=percentile))
        return entries

    def _select_word_for_level(self, level: int) -> str:
        if not self.word_entries:
            raise ValueError("No words available.")
        if is_boss_level(level):
            top_count = max(1, int(round(len(self.word_entries) * 0.1)))
            candidates = [entry.word for entry in self.word_entries[-top_count:]]
            return random.choice(candidates)
        low, high = difficulty_band(level)
        candidates = [entry.word for entry in self.word_entries if low <= entry.percentile <= high]
        if not candidates:
            candidates = [entry.word for entry in self.word_entries]
        return random.choice(candidates)

    def _new_secret(self, level: int) -> str:
        if self.word_provider:
            try:
                candidate = (self.word_provider(level, difficulty_label(level)) or "").strip().upper()
            except TypeError:
                candidate = (self.word_provider() or "").strip().upper()
            except Exception:
                candidate = ""
            if len(candidate) == DEFAULT_WORD_LEN and candidate.isalpha():
                self.add_word(candidate)
                return candidate
        return self._select_word_for_level(level)

    def _apply_level_settings(self, rs: RunState) -> None:
        rs.difficulty = difficulty_label(rs.level)
        rs.boss_level = is_boss_level(rs.level)

    def start_run(self) -> RunState:
        run_id = str(uuid.uuid4())
        rs = RunState(run_id=run_id)
        rs.secret = self._new_secret(rs.level)
        self._apply_level_settings(rs)
        self.runs[run_id] = rs
        return rs

    def get_run(self, run_id: str) -> RunState:
        if run_id not in self.runs:
            raise KeyError("Run not found.")
        return self.runs[run_id]

    def submit_guess(self, run_id: str, guess: str) -> RunState:
        rs = self.get_run(run_id)
        guess = guess.strip().upper()
        rs.last_score_delta = 0

        if rs.pending_powerups:
            # player must choose powerup before continuing
            return rs

        if rs.won or rs.failed:
            # level already ended; ignore guesses
            return rs

        if len(guess) != DEFAULT_WORD_LEN or not guess.isalpha():
            return rs
        if guess not in self.word_set:
            return rs

        rs.guesses.append(guess)
        rs.feedback.append(evaluate_guess(rs.secret, guess))

        # If won, create powerup choices
        if rs.won:
            rs.last_score_delta = self._score_for_win(rs.level, len(rs.guesses))
            rs.score += rs.last_score_delta
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
        rs.secret = self._new_secret(rs.level)
        rs.guesses = []
        rs.feedback = []
        rs.pending_powerups = []
        rs.last_score_delta = 0
        self._apply_level_settings(rs)

    def _roll_powerups(self) -> List[dict]:
        pool = [
            {"id": "time_plus_10", "type": "time", "value": 10, "name": "+10 seconds", "desc": "Adds 10 seconds to your run timer."},
            {"id": "reveal_first", "type": "reveal", "value": "first", "name": "Reveal first letter", "desc": "Reveals the first letter of the next word."},
            {"id": "gemini_hint", "type": "hint", "value": "definition", "name": "Gemini hint", "desc": "Get a hint generated by Gemini."},
        ]
        return random.sample(pool, 3)

    def is_valid_guess(self, guess: str) -> bool:
        return guess.strip().upper() in self.word_set

    def add_word(self, word: str) -> None:
        cleaned = word.strip().upper()
        if len(cleaned) != DEFAULT_WORD_LEN or not cleaned.isalpha():
            return
        if cleaned in self.word_set:
            return
        self.words.append(cleaned)
        self.word_set.add(cleaned)
        self.word_entries = self._build_word_entries(self.words)

    def _score_for_win(self, level: int, guesses_used: int) -> int:
        base = 100
        multiplier = difficulty_multiplier(level)
        guess_bonus = max(0, (DEFAULT_MAX_GUESSES - guesses_used)) * 10
        return (base * multiplier) + (guess_bonus * multiplier)
