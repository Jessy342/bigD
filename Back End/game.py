# backend/game.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
import os
import random
import re
import uuid
import time
from pathlib import Path

try:
    from wordfreq import top_n_list, zipf_frequency
except Exception:
    top_n_list = None
    zipf_frequency = None

DEFAULT_WORD_LEN = 5
DEFAULT_MAX_GUESSES = 6

BOSS_LEVEL_INTERVAL = int(os.getenv("BOSS_LEVEL_INTERVAL", "5"))
DEFAULT_SKIP_COOLDOWN_LEVELS = int(os.getenv("SKIP_COOLDOWN_LEVELS", "3"))
CANDIDATE_WORD_LIMIT = int(os.getenv("CANDIDATE_WORD_LIMIT", "20000"))
MIN_WORD_LEN = int(os.getenv("MIN_WORD_LEN", "3"))
MAX_WORD_LEN = int(os.getenv("MAX_WORD_LEN", "12"))
EASY_WORD_LIMIT = int(os.getenv("EASY_WORD_LIMIT", "800"))

COMMON_LETTERS = set("ETAOINSHRDL")
MID_LETTERS = set("CUMWFGYPB")
RARE_LETTERS = set("VKJXQZ")
VOWELS = set("AEIOU")

DIFFICULTY_LABELS = ["easy", "medium", "hard", "expert", "master", "legend"]

DEFAULT_EASY_WORDS = [
    "ABOUT", "APPLE", "BEACH", "BREAD", "BRAVE", "BROWN", "CHAIR", "CRANE",
    "DANCE", "EARTH", "FRUIT", "GRASS", "GREEN", "HEART", "HOUSE", "LIGHT",
    "MONEY", "MUSIC", "OCEAN", "PAPER", "PARTY", "PHONE", "PLANT", "QUIET",
    "RIVER", "SMILE", "SPACE", "STONE", "SWEET", "TABLE", "TRAIN", "WATER",
    "WHITE", "WORLD", "YOUTH",
]


@dataclass(frozen=True)
class WordEntry:
    word: str
    score: float
    percentile: float


def is_boss_level(level: int) -> bool:
    return level > 0 and (level % BOSS_LEVEL_INTERVAL == 0)


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


def word_frequency_score(word: str) -> float:
    if zipf_frequency:
        return -float(zipf_frequency(word.lower(), "en"))
    return float(word_difficulty_score(word))


def _load_words_from_file(path: Path, min_len: int, max_len: int) -> List[str]:
    if not path.exists():
        return []
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        w = line.strip()
        if not w:
            continue
        if w.isalpha() and min_len <= len(w) <= max_len:
            words.append(w.upper())
    return words


def _load_words_from_wordfreq(min_len: int, max_len: int, limit: int) -> List[str]:
    if not top_n_list:
        return []
    words = []
    for word in top_n_list("en", limit):
        if word.isalpha() and min_len <= len(word) <= max_len:
            words.append(word.upper())
    return words


def _load_words_from_env(min_len: int, max_len: int) -> List[str]:
    extra_path = os.getenv("ENGLISH_WORDS_PATH")
    if not extra_path:
        return []
    try:
        return _load_words_from_file(Path(extra_path), min_len, max_len)
    except Exception:
        return []


def _dedupe_preserve(words: List[str]) -> List[str]:
    seen = set()
    deduped = []
    for word in words:
        if word in seen:
            continue
        deduped.append(word)
        seen.add(word)
    return deduped


def load_easy_words(words: List[str]) -> List[str]:
    if not words:
        return DEFAULT_EASY_WORDS
    limit = max(1, min(EASY_WORD_LIMIT, len(words)))
    return words[:limit]


def load_words(path: str) -> List[str]:
    p = Path(path)
    words: List[str] = []
    words.extend(_load_words_from_wordfreq(MIN_WORD_LEN, MAX_WORD_LEN, CANDIDATE_WORD_LIMIT))
    words.extend(_load_words_from_env(MIN_WORD_LEN, MAX_WORD_LEN))
    words.extend(_load_words_from_file(p, MIN_WORD_LEN, MAX_WORD_LEN))
    words.extend(_load_words_from_file(p.parent / "words_5.txt", MIN_WORD_LEN, MAX_WORD_LEN))
    words.extend(DEFAULT_EASY_WORDS)
    words = _dedupe_preserve(words)
    if not words:
        raise ValueError("No words available. Configure CANDIDATE_WORD_LIMIT or ENGLISH_WORDS_PATH.")
    return words


@dataclass(frozen=True)
class GuessEntry:
    word: str
    rank: int
    similarity: float
    timestamp: float
    show_similarity: bool = False


@dataclass
class RunState:
    run_id: str
    level: int = 1
    secret: str = ""
    theme_id: str = ""
    pending_theme_choice: bool = False
    theme_options: List[dict] = field(default_factory=list)
    guesses: List[GuessEntry] = field(default_factory=list)
    best_rank: Optional[int] = None
    score: int = 0
    last_score_delta: int = 0
    difficulty: str = "easy"
    boss_level: bool = False
    completed_levels: int = 0
    inventory: List[dict] = field(default_factory=list)
    pending_powerups: List[dict] = field(default_factory=list)
    similarity_reveal_remaining: int = 0
    skip_cooldown_reduction_levels: int = 0
    skip_cooldown_reduction_value: int = 0
    last_effect_messages: List[str] = field(default_factory=list)

    # skip cooldown
    last_skip_level: int = -999
    skip_cooldown_levels: int = DEFAULT_SKIP_COOLDOWN_LEVELS

    @property
    def won(self) -> bool:
        return any(entry.word == self.secret for entry in self.guesses)

    @property
    def failed(self) -> bool:
        return False

    @property
    def skip_available(self) -> bool:
        if self.boss_level:
            return False
        return self.skip_in_levels() == 0

    def skip_in_levels(self) -> int:
        cooldown = max(0, self.skip_cooldown_levels - self.skip_cooldown_reduction_value)
        diff = self.level - self.last_skip_level
        remaining = cooldown - diff + 1
        return max(0, remaining)


class GameManager:
    def __init__(
        self,
        words: List[str],
        rank_guess: Callable[[str, str], Tuple[int, float]],
        word_provider: Optional[Callable[..., str]] = None,
        easy_words: Optional[List[str]] = None,
        theme_options_provider: Optional[Callable[[str], List[dict]]] = None,
    ):
        self.easy_words = _dedupe_preserve(easy_words or [])
        merged_words = _dedupe_preserve(words)
        self.words = merged_words
        self.word_set = set(self.words)
        self.word_entries = self._build_word_entries(self.words)
        self.word_provider = word_provider
        self.theme_options_provider = theme_options_provider
        self.rank_guess = rank_guess
        self.runs: Dict[str, RunState] = {}

    def _build_word_entries(self, words: List[str]) -> List[WordEntry]:
        scored = sorted(((word, word_frequency_score(word)) for word in words), key=lambda x: x[1])
        total = len(scored)
        entries: List[WordEntry] = []
        for idx, (word, score) in enumerate(scored):
            percentile = (idx / (total - 1)) if total > 1 else 1.0
            entries.append(WordEntry(word=word, score=score, percentile=percentile))
        return entries

    def _difficulty_level(self, rs: RunState) -> int:
        return rs.completed_levels + 1

    def _select_word_for_level(self, level: int) -> str:
        if not self.word_entries:
            raise ValueError("No words available.")
        if difficulty_label(level) == "easy" and self.easy_words:
            return random.choice(self.easy_words)
        if is_boss_level(level):
            top_count = max(1, int(round(len(self.word_entries) * 0.1)))
            candidates = [entry.word for entry in self.word_entries[-top_count:]]
            return random.choice(candidates)
        low, high = difficulty_band(level)
        candidates = [entry.word for entry in self.word_entries if low <= entry.percentile <= high]
        if not candidates:
            candidates = [entry.word for entry in self.word_entries]
        return random.choice(candidates)

    def _new_secret(self, rs: RunState, level: int) -> str:
        if self.word_provider:
            try:
                candidate = (
                    self.word_provider(
                        level=level,
                        difficulty=difficulty_label(level),
                        theme_id=rs.theme_id,
                        boss=is_boss_level(level),
                    )
                    or ""
                ).strip().upper()
            except TypeError:
                try:
                    candidate = (self.word_provider(level, difficulty_label(level)) or "").strip().upper()
                except TypeError:
                    candidate = (self.word_provider() or "").strip().upper()
            except Exception:
                candidate = ""
            if candidate and candidate.isalpha():
                self.add_word(candidate)
                return candidate
        return self._select_word_for_level(level)

    def _apply_level_settings(self, rs: RunState) -> None:
        difficulty_level = self._difficulty_level(rs)
        rs.difficulty = difficulty_label(difficulty_level)
        rs.boss_level = is_boss_level(difficulty_level)

    def start_run(self, theme_id: str = "") -> RunState:
        run_id = str(uuid.uuid4())
        rs = RunState(run_id=run_id, theme_id=theme_id or "")
        rs.secret = self._new_secret(rs, self._difficulty_level(rs))
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
        rs.last_effect_messages = []

        if rs.pending_powerups:
            return rs

        if rs.won or rs.failed:
            return rs

        if not guess.isalpha():
            return rs
        if guess not in self.word_set:
            return rs

        rank, similarity = self.rank_guess(guess, rs.secret)
        show_similarity = rs.similarity_reveal_remaining > 0
        if show_similarity:
            rs.similarity_reveal_remaining -= 1

        entry = GuessEntry(
            word=guess,
            rank=rank,
            similarity=similarity,
            timestamp=time.time(),
            show_similarity=show_similarity,
        )
        rs.guesses.append(entry)

        if rs.best_rank is None or rank < rs.best_rank:
            rs.best_rank = rank

        if rs.won:
            difficulty_level = self._difficulty_level(rs)
            base_score = self._score_for_win(difficulty_level, len(rs.guesses))
            rs.last_score_delta = base_score
            rs.score += rs.last_score_delta
            rs.pending_powerups = self._roll_powerups()
            if rs.boss_level:
                rs.pending_theme_choice = True
                if self.theme_options_provider:
                    rs.theme_options = self.theme_options_provider(rs.theme_id)

        return rs

    def skip_level(self, run_id: str) -> RunState:
        rs = self.get_run(run_id)
        if rs.pending_powerups or rs.won or rs.failed or not rs.skip_available:
            return rs

        rs.last_skip_level = rs.level
        self._advance_level(rs, completed=False)
        return rs

    def choose_powerup(self, run_id: str, powerup_id: str) -> Tuple[RunState, dict]:
        rs = self.get_run(run_id)
        if not rs.pending_powerups:
            return rs, {}

        chosen = next(
            (
                p
                for p in rs.pending_powerups
                if p.get("instance_id") == powerup_id or p.get("id") == powerup_id
            ),
            None,
        )
        if not chosen:
            return rs, {}

        rs.inventory.append(chosen)
        rs.pending_powerups = []
        if rs.pending_theme_choice:
            return rs, chosen
        self._advance_level(rs, completed=True)
        return rs, chosen

    def use_powerup(self, run_id: str, powerup_id: str) -> Tuple[RunState, dict]:
        rs = self.get_run(run_id)
        if rs.pending_powerups or rs.failed or not rs.inventory:
            return rs, {}
        idx = next(
            (
                i
                for i, p in enumerate(rs.inventory)
                if p.get("instance_id") == powerup_id or p.get("id") == powerup_id
            ),
            None,
        )
        if idx is None:
            return rs, {}
        chosen = rs.inventory.pop(idx)
        return rs, chosen

    def _advance_level(self, rs: RunState, completed: bool):
        if completed:
            rs.completed_levels += 1
        rs.level += 1
        rs.secret = self._new_secret(rs, self._difficulty_level(rs))
        rs.guesses = []
        rs.best_rank = None
        rs.pending_powerups = []
        rs.pending_theme_choice = False
        rs.theme_options = []
        rs.last_score_delta = 0
        rs.last_effect_messages = []
        if rs.skip_cooldown_reduction_levels > 0:
            rs.skip_cooldown_reduction_levels -= 1
            if rs.skip_cooldown_reduction_levels <= 0:
                rs.skip_cooldown_reduction_levels = 0
                rs.skip_cooldown_reduction_value = 0
        self._apply_level_settings(rs)

    def _powerup_with_instance(self, powerup: dict) -> dict:
        return {**powerup, "instance_id": uuid.uuid4().hex}

    def _roll_powerups(self) -> List[dict]:
        pool = [
            {"id": "time_burst", "type": "time", "value": 8, "name": "Time Burst", "desc": "+8 seconds immediately."},
            {"id": "micro_pause", "type": "timer", "value": 2, "name": "Micro Pause", "desc": "Freeze the timer for 2 seconds."},
            {"id": "slow_time", "type": "timer", "value": 10, "name": "Slow Time", "desc": "Timer drains at half speed for 10 seconds."},
            {"id": "gemini_hint_definition", "type": "hint", "value": "definition", "name": "Definition hint", "desc": "Get a concise definition hint."},
            {"id": "gemini_hint_category", "type": "hint", "value": "category", "name": "Category hint", "desc": "Get the general category."},
            {"id": "gemini_hint_context", "type": "hint", "value": "context", "name": "Context hint", "desc": "Get a subtle contextual hint."},
            {"id": "related_word", "type": "hint", "value": "related", "name": "Related word", "desc": "Reveal a nearby concept."},
            {"id": "similarity_reveal", "type": "utility", "value": 3, "name": "Similarity Scanner", "desc": "Show similarity % for the next 3 guesses."},
            {"id": "skip_cooldown_reducer", "type": "skip", "value": 1, "name": "Skip Cooldown Reducer", "desc": "Reduce skip cooldown for 5 levels."},
            {"id": "skip_refresh", "type": "skip", "value": 1, "name": "Skip Refresh", "desc": "Make Skip available immediately."},
            {"id": "undo_last_guess", "type": "utility", "value": 1, "name": "Undo Guess", "desc": "Remove your most recent guess."},
        ]
        picks = random.sample(pool, 3)
        return [self._powerup_with_instance(powerup) for powerup in picks]

    def is_valid_guess(self, guess: str) -> bool:
        return guess.strip().upper() in self.word_set

    def add_word(self, word: str) -> None:
        cleaned = word.strip().upper()
        if not cleaned.isalpha():
            return
        if cleaned in self.word_set:
            return
        self.word_set.add(cleaned)

    def _score_for_win(self, level: int, guesses_used: int) -> int:
        base = 100
        multiplier = difficulty_multiplier(level)
        guess_bonus = max(0, (DEFAULT_MAX_GUESSES - guesses_used)) * 10
        return (base * multiplier) + (guess_bonus * multiplier)

    def apply_theme_choice(self, run_id: str, theme_id: str) -> RunState:
        rs = self.get_run(run_id)
        rs.theme_id = theme_id
        rs.pending_theme_choice = False
        rs.theme_options = []
        self._advance_level(rs, completed=True)
        return rs

