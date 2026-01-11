# backend/game.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Literal, Optional, Tuple
import os
import random
import re
import uuid
from pathlib import Path

LetterState = Literal["correct", "present", "absent"]

DEFAULT_WORD_LEN = 5
DEFAULT_MAX_GUESSES = 6
DEFAULT_SKIP_COOLDOWN_LEVELS = 0

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

def _load_words_from_env() -> List[str]:
    extra_path = os.getenv("ENGLISH_WORDS_PATH")
    if not extra_path:
        return []
    try:
        return _load_words_from_file(Path(extra_path))
    except Exception:
        return []

def _load_easy_words_from_frontend(base_dir: Path) -> List[str]:
    word_list_path = (base_dir / ".." / "Front End" / "src" / "utils" / "wordList.ts").resolve()
    if not word_list_path.exists():
        return []
    text = word_list_path.read_text(encoding="utf-8")
    match = re.search(r"EASY_WORDS\\s*=\\s*\\[(.*?)\\];", text, re.S)
    if not match:
        return []
    candidates = re.findall(r"'([A-Z]{5})'", match.group(1))
    return [word.upper() for word in candidates if word.isalpha()]

def load_easy_words(path: str) -> List[str]:
    p = Path(path)
    words = _load_easy_words_from_frontend(p.parent)
    words.extend(DEFAULT_EASY_WORDS)
    return sorted(set(words))

def load_words(path: str) -> List[str]:
    p = Path(path)
    words = _load_words_from_file(p)
    words.extend(_load_words_from_env())
    words.extend(_load_words_from_frontend(p.parent))
    words.extend(DEFAULT_EASY_WORDS)
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
    completed_levels: int = 0
    extra_rows: int = 0
    score_multiplier_levels: int = 0
    score_multiplier: float = 1.0
    double_or_nothing_pending: int = 0
    perfect_clear_pending: int = 0
    clutch_shield: int = 0
    hot_cold_pending: int = 0
    skip_insurance: int = 0
    skip_cooldown_reduction_levels: int = 0
    skip_cooldown_reduction_value: int = 0
    last_effect_messages: List[str] = field(default_factory=list)
    last_time_bonus_seconds: int = 0
    last_time_penalty_seconds: int = 0
    inventory: List[dict] = field(default_factory=list)

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
        return (not self.won) and (len(self.guesses) >= self.max_guesses)

    @property
    def skip_available(self) -> bool:
        return True

    @property
    def max_guesses(self) -> int:
        return DEFAULT_MAX_GUESSES + min(self.extra_rows, 2)

    def skip_in_levels(self) -> int:
        return 0

class GameManager:
    def __init__(
        self,
        words: List[str],
        word_provider: Optional[Callable[[int, str], str]] = None,
        easy_words: Optional[List[str]] = None,
    ):
        self.easy_words = sorted(set(easy_words or []))
        merged_words = sorted(set(words).union(self.easy_words))
        self.words = merged_words
        self.word_set = set(self.words)
        self.word_entries = self._build_word_entries(self.words)
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
        difficulty_level = self._difficulty_level(rs)
        rs.difficulty = difficulty_label(difficulty_level)
        rs.boss_level = is_boss_level(difficulty_level)

    def start_run(self) -> RunState:
        run_id = str(uuid.uuid4())
        rs = RunState(run_id=run_id)
        rs.secret = self._new_secret(self._difficulty_level(rs))
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
        rs.last_time_bonus_seconds = 0
        rs.last_time_penalty_seconds = 0

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

        if rs.hot_cold_pending:
            overlap = len(set(guess) & set(rs.secret))
            rs.last_effect_messages.append(
                f"Hot/Cold rating: {overlap} letter{'' if overlap == 1 else 's'} overlap."
            )
            rs.hot_cold_pending = 0

        # If won, create powerup choices
        if rs.won:
            difficulty_level = self._difficulty_level(rs)
            base_score = self._score_for_win(difficulty_level, len(rs.guesses))
            score_delta = base_score
            if rs.score_multiplier_levels > 0:
                score_delta = int(round(score_delta * rs.score_multiplier))
                rs.last_effect_messages.append(
                    f"Score multiplier applied ({rs.score_multiplier}x)."
                )
                rs.score_multiplier_levels -= 1
                if rs.score_multiplier_levels <= 0:
                    rs.score_multiplier_levels = 0
                    rs.score_multiplier = 1.0
            if rs.double_or_nothing_pending > 0:
                bonus = 150 * difficulty_multiplier(difficulty_level)
                score_delta += bonus
                rs.last_effect_messages.append(f"Double or Nothing bonus: +{bonus} score.")
                rs.double_or_nothing_pending = 0
            if rs.perfect_clear_pending > 0:
                if len(rs.guesses) <= 3:
                    rs.last_time_bonus_seconds += 15
                    rs.last_effect_messages.append("Perfect Clear! +15 seconds.")
                rs.perfect_clear_pending = 0
            if rs.skip_insurance > 0:
                rs.skip_insurance -= 1
            rs.last_score_delta = score_delta
            rs.score += rs.last_score_delta
            rs.pending_powerups = self._roll_powerups()

        # If failed, end the run on this level.
        if rs.failed:
            if rs.double_or_nothing_pending > 0:
                rs.last_time_penalty_seconds += 8
                rs.last_effect_messages.append("Double or Nothing failed: -8 seconds.")
                rs.double_or_nothing_pending = 0
            if rs.perfect_clear_pending > 0:
                rs.perfect_clear_pending = 0
            if rs.skip_insurance > 0:
                rs.skip_insurance -= 1
                rs.last_effect_messages.append("Skip Insurance activated. Level skipped.")
                self._advance_level(rs, completed=False)
                return rs
            return rs

        return rs

    def skip_level(self, run_id: str) -> RunState:
        rs = self.get_run(run_id)
        if rs.pending_powerups or rs.won or rs.failed:
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
        rs.secret = self._new_secret(self._difficulty_level(rs))
        rs.guesses = []
        rs.feedback = []
        rs.pending_powerups = []
        rs.last_score_delta = 0
        rs.extra_rows = 0
        rs.last_effect_messages = []
        rs.last_time_bonus_seconds = 0
        rs.last_time_penalty_seconds = 0
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
            {"id": "time_plus_20", "type": "time", "value": 20, "name": "+20 seconds", "desc": "Adds 20 seconds to your run timer."},
            {"id": "time_plus_30", "type": "time", "value": 30, "name": "+30 seconds", "desc": "Adds 30 seconds to your run timer."},
            {"id": "micro_pause", "type": "timer", "value": 2, "name": "Micro Pause", "desc": "Freeze the timer for 2 seconds."},
            {"id": "slow_time", "type": "timer", "value": 10, "name": "Slow Time", "desc": "Timer drains at half speed for 10 seconds."},
            {"id": "extra_row", "type": "utility", "value": 1, "name": "Extra Row", "desc": "+1 guess this level (cap +2)."},
            {"id": "perfect_clear_bonus", "type": "utility", "value": 15, "name": "Perfect Clear Bonus", "desc": "Win next level in 3 guesses for +15 seconds."},
            {"id": "clutch_shield", "type": "utility", "value": 5, "name": "Clutch Shield", "desc": "If time hits 0 next level, set to 5 seconds."},
            {"id": "letter_exclusion_scan", "type": "scan", "value": 3, "name": "Letter Exclusion Scan", "desc": "Reveal 3 letters NOT in the word."},
            {"id": "letter_inclusion_scan", "type": "scan", "value": 1, "name": "Letter Inclusion Scan", "desc": "Reveal 1 letter that IS in the word."},
            {"id": "position_reveal", "type": "reveal", "value": "position", "name": "Position Reveal", "desc": "Reveal 1 correct letter position."},
            {"id": "hot_cold_rating", "type": "scan", "value": 1, "name": "Hot/Cold Rating", "desc": "Next guess shows unique letter overlap."},
            {"id": "skip_cooldown_reducer", "type": "skip", "value": 1, "name": "Skip Cooldown Reducer", "desc": "Reduce skip cooldown for 5 levels."},
            {"id": "skip_refresh", "type": "skip", "value": 1, "name": "Skip Refresh", "desc": "Make Skip available immediately."},
            {"id": "skip_insurance", "type": "skip", "value": 1, "name": "Skip Insurance", "desc": "Failing next level triggers a skip."},
            {"id": "score_multiplier", "type": "score", "value": 1.5, "name": "Score Multiplier", "desc": "1.5x score for the next 2 levels."},
            {"id": "double_or_nothing", "type": "score", "value": 1, "name": "Double or Nothing", "desc": "Win for bonus; fail for -8 seconds."},
            {"id": "streak_bank", "type": "score", "value": 1, "name": "Streak Bank", "desc": "Convert streak into time or score."},
            {"id": "reveal_first", "type": "reveal", "value": "first", "name": "Reveal first letter", "desc": "Reveals the first letter of the next word."},
            {"id": "reveal_last", "type": "reveal", "value": "last", "name": "Reveal last letter", "desc": "Reveals the last letter of the next word."},
            {"id": "reveal_vowel", "type": "reveal", "value": "vowel", "name": "Reveal a vowel", "desc": "Reveals one vowel in the next word."},
            {"id": "reveal_random", "type": "reveal", "value": "random", "name": "Reveal a random letter", "desc": "Reveals one random letter in the next word."},
            {"id": "gemini_hint_definition", "type": "hint", "value": "definition", "name": "Gemini definition", "desc": "Get a concise definition hint."},
            {"id": "gemini_hint_usage", "type": "hint", "value": "usage", "name": "Gemini usage", "desc": "Get a short usage example."},
            {"id": "gemini_hint_rhyme", "type": "hint", "value": "rhyme", "name": "Gemini rhyme", "desc": "Get a rhyming clue."},
            {"id": "gemini_hint_context", "type": "hint", "value": "context", "name": "Gemini clue", "desc": "Get a subtle contextual hint."},
        ]
        picks = random.sample(pool, 3)
        return [self._powerup_with_instance(powerup) for powerup in picks]

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
