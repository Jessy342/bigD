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
INVENTORY_CAPACITY = int(os.getenv("INVENTORY_CAPACITY", "3"))
ALLOW_DUPLICATE_POWERUPS: set[str] = set()

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

RANDOM_THEME_ID = "random"
IRREGULAR_PLURALS = {
    "MICE": "MOUSE",
    "GEESE": "GOOSE",
    "TEETH": "TOOTH",
    "FEET": "FOOT",
    "CHILDREN": "CHILD",
    "MEN": "MAN",
    "WOMEN": "WOMAN",
    "PEOPLE": "PERSON",
    "WOLVES": "WOLF",
    "LEAVES": "LEAF",
    "KNIVES": "KNIFE",
}
PLURAL_EXCEPTIONS = {"NEWS", "SERIES", "SPECIES"}
PLURAL_S_ENDINGS = ("SS", "US", "IS")
PLURAL_ES_ENDINGS = ("CHES", "SHES", "XES", "ZES", "SES")


def is_random_theme(theme_id: str) -> bool:
    return (theme_id or "").strip().lower() == RANDOM_THEME_ID


def normalize_word(word: str, word_set: Optional[set[str]] = None) -> str:
    cleaned = word.strip().upper()
    if not cleaned:
        return cleaned
    irregular = IRREGULAR_PLURALS.get(cleaned)
    if irregular:
        return irregular
    if cleaned in PLURAL_EXCEPTIONS:
        return cleaned
    candidates: List[str] = []
    if len(cleaned) > 3:
        if cleaned.endswith("IES"):
            candidates.append(cleaned[:-3] + "Y")
        if cleaned.endswith("VES"):
            candidates.append(cleaned[:-3] + "F")
            candidates.append(cleaned[:-3] + "FE")
        if cleaned.endswith(PLURAL_ES_ENDINGS):
            candidates.append(cleaned[:-2])
        if cleaned.endswith("S") and not cleaned.endswith(PLURAL_S_ENDINGS):
            candidates.append(cleaned[:-1])
        if cleaned.endswith("ES"):
            candidates.append(cleaned[:-2])
    candidates.append(cleaned)

    deduped: List[str] = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    if word_set and len(deduped) > 1:
        for candidate in deduped:
            if candidate == cleaned:
                continue
            if candidate in word_set:
                return candidate
    return deduped[0]


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
    failed_flag: bool = False
    no_powerup_reward: bool = False
    anchor_word: str = ""
    anchor_rank: Optional[int] = None
    momentum_bonus_active: bool = False
    momentum_bonus_value: int = 0
    skip_insurance_active: bool = False
    safety_net_levels: int = 0
    expanded_choice_levels: int = 0

    # skip cooldown
    last_skip_level: int = -999
    skip_cooldown_levels: int = DEFAULT_SKIP_COOLDOWN_LEVELS

    @property
    def won(self) -> bool:
        return any(entry.word == self.secret for entry in self.guesses)

    @property
    def failed(self) -> bool:
        return self.failed_flag

    @property
    def is_random_mode(self) -> bool:
        return is_random_theme(self.theme_id)

    @property
    def skip_available(self) -> bool:
        if self.is_random_mode:
            return True
        if self.boss_level:
            return False
        return self.skip_in_levels() == 0

    def skip_in_levels(self) -> int:
        if self.is_random_mode:
            return 0
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
        self.normalized_word_set: set[str] = set()
        self._rebuild_normalized_word_set()
        self.word_entries = self._build_word_entries(self.words)
        self.word_provider = word_provider
        self.theme_options_provider = theme_options_provider
        self.rank_guess = rank_guess
        self.runs: Dict[str, RunState] = {}

    def _is_random_run(self, rs: RunState) -> bool:
        return rs.is_random_mode

    def _build_word_entries(self, words: List[str]) -> List[WordEntry]:
        scored = sorted(((word, word_frequency_score(word)) for word in words), key=lambda x: x[1])
        total = len(scored)
        entries: List[WordEntry] = []
        for idx, (word, score) in enumerate(scored):
            percentile = (idx / (total - 1)) if total > 1 else 1.0
            entries.append(WordEntry(word=word, score=score, percentile=percentile))
        return entries

    def _rebuild_normalized_word_set(self) -> None:
        self.normalized_word_set = {normalize_word(word, self.word_set) for word in self.word_set}

    def _difficulty_level(self, rs: RunState) -> int:
        if self._is_random_run(rs):
            return 1
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
                normalized = normalize_word(candidate, self.word_set)
                self.add_word(normalized)
                return normalized
        return normalize_word(self._select_word_for_level(level), self.word_set)

    def _apply_level_settings(self, rs: RunState) -> None:
        if self._is_random_run(rs):
            rs.difficulty = "random"
            rs.boss_level = False
            rs.skip_cooldown_levels = 0
            rs.skip_cooldown_reduction_levels = 0
            rs.skip_cooldown_reduction_value = 0
            return
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

        normalized_guess = normalize_word(guess, self.word_set)
        if not normalized_guess.isalpha():
            return rs
        if normalized_guess not in self.normalized_word_set:
            return rs
        if any(entry.word == normalized_guess for entry in rs.guesses):
            rs.last_effect_messages = ["Already guessed. Try a different word."]
            return rs

        rank, similarity = self.rank_guess(normalized_guess, rs.secret)
        show_similarity = rs.similarity_reveal_remaining > 0
        if show_similarity:
            rs.similarity_reveal_remaining -= 1

        entry = GuessEntry(
            word=normalized_guess,
            rank=rank,
            similarity=similarity,
            timestamp=time.time(),
            show_similarity=show_similarity,
        )
        rs.guesses.append(entry)

        if rs.anchor_rank is not None and rs.anchor_word:
            if normalized_guess == rs.anchor_word:
                rs.last_effect_messages.append("Anchor guess selected.")
            elif rank < rs.anchor_rank:
                rs.last_effect_messages.append("Closer than your anchor.")
            elif rank > rs.anchor_rank:
                rs.last_effect_messages.append("Farther than your anchor.")
            else:
                rs.last_effect_messages.append("Matched your anchor.")

        if rs.best_rank is None or rank < rs.best_rank:
            rs.best_rank = rank

        if rs.won:
            if self._is_random_run(rs):
                return rs
            if rs.no_powerup_reward:
                rs.no_powerup_reward = False
                if rs.boss_level:
                    rs.pending_powerups = []
                    rs.pending_theme_choice = True
                    if self.theme_options_provider:
                        rs.theme_options = self.theme_options_provider(rs.theme_id)
                    return rs
                self._advance_level(rs, completed=True)
                return rs
            difficulty_level = self._difficulty_level(rs)
            base_score = self._score_for_win(difficulty_level, len(rs.guesses))
            rs.last_score_delta = base_score
            rs.score += rs.last_score_delta
            rs.pending_powerups = self._roll_powerups(rs)
            if rs.boss_level:
                rs.pending_theme_choice = True
                if self.theme_options_provider:
                    rs.theme_options = self.theme_options_provider(rs.theme_id)

        return rs

    def _reset_random_round(self, rs: RunState) -> None:
        rs.level = 1
        rs.completed_levels = 0
        rs.secret = self._new_secret(rs, 1)
        rs.guesses = []
        rs.best_rank = None
        rs.pending_powerups = []
        rs.pending_theme_choice = False
        rs.theme_options = []
        rs.last_score_delta = 0
        rs.last_effect_messages = []
        rs.similarity_reveal_remaining = 0
        rs.score = 0
        rs.failed_flag = False
        rs.no_powerup_reward = False
        rs.anchor_word = ""
        rs.anchor_rank = None
        rs.momentum_bonus_active = False
        rs.momentum_bonus_value = 0
        rs.skip_insurance_active = False
        rs.safety_net_levels = 0
        rs.expanded_choice_levels = 0
        rs.last_skip_level = -999
        rs.skip_cooldown_levels = 0
        rs.skip_cooldown_reduction_levels = 0
        rs.skip_cooldown_reduction_value = 0
        rs.boss_level = False
        rs.difficulty = "random"

    def skip_level(self, run_id: str) -> RunState:
        rs = self.get_run(run_id)
        if self._is_random_run(rs):
            self._reset_random_round(rs)
            return rs
        if rs.pending_powerups or rs.won or rs.failed or not rs.skip_available:
            return rs

        rs.last_skip_level = rs.level
        self._advance_level(rs, completed=False)
        return rs

    def choose_powerup(self, run_id: str, powerup_id: str) -> Tuple[RunState, dict, str | None]:
        rs = self.get_run(run_id)
        if self._is_random_run(rs):
            rs.pending_powerups = []
            return rs, {}, "Powerups are disabled in random mode."
        if not rs.pending_powerups:
            return rs, {}, "No powerup reward available."

        chosen = next(
            (
                p
                for p in rs.pending_powerups
                if p.get("instance_id") == powerup_id or p.get("id") == powerup_id
            ),
            None,
        )
        if not chosen:
            return rs, {}, "Powerup not available."

        powerup_key = chosen.get("id") or ""
        inventory_ids = {item.get("id") for item in rs.inventory}
        if powerup_key in inventory_ids and powerup_key not in ALLOW_DUPLICATE_POWERUPS:
            rs.pending_powerups = []
            if rs.pending_theme_choice:
                return rs, {}, "Duplicate powerup. Reward skipped."
            self._advance_level(rs, completed=True)
            return rs, {}, "Duplicate powerup. Reward skipped."
        if len(rs.inventory) >= INVENTORY_CAPACITY:
            rs.pending_powerups = []
            if rs.pending_theme_choice:
                return rs, {}, "Inventory full. Reward skipped."
            self._advance_level(rs, completed=True)
            return rs, {}, "Inventory full. Reward skipped."

        rs.inventory.append(chosen)
        rs.pending_powerups = []
        if rs.pending_theme_choice:
            return rs, chosen, None
        self._advance_level(rs, completed=True)
        return rs, chosen, None

    def use_powerup(self, run_id: str, powerup_id: str) -> Tuple[RunState, dict]:
        rs = self.get_run(run_id)
        if self._is_random_run(rs):
            rs.pending_powerups = []
            rs.inventory = []
            return rs, {}
        if (rs.pending_powerups and powerup_id != "reroll_rewards") or rs.failed or not rs.inventory:
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
        if self._is_random_run(rs):
            self._reset_random_round(rs)
            return
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
        rs.failed_flag = False
        rs.no_powerup_reward = False
        rs.anchor_word = ""
        rs.anchor_rank = None
        rs.momentum_bonus_active = False
        rs.momentum_bonus_value = 0
        rs.skip_insurance_active = False if completed else rs.skip_insurance_active
        if rs.safety_net_levels > 0:
            rs.safety_net_levels -= 1
        rs.expanded_choice_levels = max(0, rs.expanded_choice_levels)
        if rs.skip_cooldown_reduction_levels > 0:
            rs.skip_cooldown_reduction_levels -= 1
            if rs.skip_cooldown_reduction_levels <= 0:
                rs.skip_cooldown_reduction_levels = 0
                rs.skip_cooldown_reduction_value = 0
        self._apply_level_settings(rs)

    def reroll_target(self, rs: RunState) -> None:
        rs.secret = self._new_secret(rs, self._difficulty_level(rs))
        rs.guesses = []
        rs.best_rank = None
        rs.anchor_word = ""
        rs.anchor_rank = None
        rs.no_powerup_reward = True

    def _powerup_with_instance(self, powerup: dict) -> dict:
        return {**powerup, "instance_id": uuid.uuid4().hex}

    def _powerup_pool(self) -> List[dict]:
        return [
            {"id": "semantic_direction", "type": "insight", "value": 1, "name": "Semantic Direction", "desc": "Reveal if the word is abstract or concrete."},
            {"id": "concept_neighbor", "type": "insight", "value": 1, "name": "Concept Neighbor", "desc": "Reveal a related concept (not a synonym)."},
            {"id": "functional_hint", "type": "insight", "value": 1, "name": "Functional Hint", "desc": "Reveal what the word is used for."},
            {"id": "descriptor_hint", "type": "insight", "value": 1, "name": "Descriptor Hint", "desc": "Reveal a common adjective that describes it."},
            {"id": "undo_guess", "type": "control", "value": 1, "name": "Undo Guess", "desc": "Remove your most recent guess."},
            {"id": "reroll_target", "type": "control", "value": 1, "name": "Reroll Target", "desc": "Replace the secret word (no reward for this level)."},
            {"id": "anchor_guess", "type": "control", "value": 1, "name": "Anchor Guess", "desc": "Set a guess as your baseline reference."},
            {"id": "similarity_reveal", "type": "rank", "value": 3, "name": "Similarity Reveal", "desc": "Show similarity % for the next 3 guesses."},
            {"id": "comparator", "type": "rank", "value": 1, "name": "Comparator", "desc": "Compare two guesses to see which is closer."},
            {"id": "gradient_scan", "type": "rank", "value": 1, "name": "Gradient Scan", "desc": "Reveal if the target is near top, middle, or bottom."},
            {"id": "micro_freeze", "type": "time", "value": 2, "name": "Micro Freeze", "desc": "Freeze the timer for 2 seconds."},
            {"id": "slow_drain", "type": "time", "value": 10, "name": "Slow Drain", "desc": "Timer drains at half speed for 10 seconds."},
            {"id": "momentum_bonus", "type": "time", "value": 6, "name": "Momentum Bonus", "desc": "Beat your best rank to gain time."},
            {"id": "skip_refresh", "type": "skip", "value": 1, "name": "Skip Refresh", "desc": "Reset skip cooldown instantly."},
            {"id": "skip_insurance", "type": "skip", "value": 1, "name": "Skip Insurance", "desc": "If you fail the next level, skip cooldown resets."},
            {"id": "skip_cooldown_reducer", "type": "skip", "value": 1, "name": "Cooldown Reducer", "desc": "Reduce skip cooldown for the next 5 levels."},
            {"id": "expanded_choice", "type": "run", "value": 1, "name": "Expanded Choice", "desc": "Next reward offers 4 options."},
            {"id": "reroll_rewards", "type": "run", "value": 1, "name": "Reroll Rewards", "desc": "Reroll the current reward selection once."},
            {"id": "safety_net", "type": "run", "value": 3, "name": "Safety Net", "desc": "First failure in the next 3 levels is ignored."},
        ]

    def _roll_powerups(self, rs: RunState, count: Optional[int] = None, consume_expanded: bool = True) -> List[dict]:
        pool = self._powerup_pool()
        exclude = {item.get("id") for item in rs.inventory}
        pool = [item for item in pool if item.get("id") not in exclude]
        if count is None:
            count = 4 if rs.expanded_choice_levels > 0 else 3
        if consume_expanded and rs.expanded_choice_levels > 0:
            rs.expanded_choice_levels = max(0, rs.expanded_choice_levels - 1)
        picks = random.sample(pool, min(count, len(pool)))
        return [self._powerup_with_instance(powerup) for powerup in picks]

    def is_valid_guess(self, guess: str) -> bool:
        normalized = normalize_word(guess, self.word_set)
        return normalized in self.normalized_word_set

    def add_word(self, word: str) -> None:
        cleaned = word.strip().upper()
        if not cleaned.isalpha():
            return
        if cleaned in self.word_set:
            return
        self.word_set.add(cleaned)
        self._rebuild_normalized_word_set()

    def _score_for_win(self, level: int, guesses_used: int) -> int:
        base = 100
        multiplier = difficulty_multiplier(level)
        guess_bonus = max(0, (DEFAULT_MAX_GUESSES - guesses_used)) * 10
        return (base * multiplier) + (guess_bonus * multiplier)

    def apply_theme_choice(self, run_id: str, theme_id: str) -> RunState:
        rs = self.get_run(run_id)
        if self._is_random_run(rs):
            rs.pending_theme_choice = False
            rs.theme_options = []
            return rs
        rs.theme_id = theme_id
        rs.pending_theme_choice = False
        rs.theme_options = []
        self._advance_level(rs, completed=True)
        return rs

