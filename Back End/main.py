# backend/main.py
import os
import mimetypes
import random
import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    from google import genai
except Exception:
    genai = None

from game import (
    GameManager,
    load_words,
    load_easy_words,
    MIN_WORD_LEN,
    MAX_WORD_LEN,
    RARE_LETTERS,
    VOWELS,
    RANDOM_THEME_ID,
    is_random_theme,
    normalize_word,
    zipf_frequency,
)
from semantic import SemanticRanker

DEFAULT_THEMES = [
    {
        "id": "nature",
        "name": "Nature",
        "description": "Plants, animals, landscapes",
        "prompt_seed": "nature, outdoors, plants, animals",
    },
    {
        "id": "food",
        "name": "Food",
        "description": "Ingredients and dishes",
        "prompt_seed": "foods, cooking, ingredients",
    },
    {
        "id": "sports",
        "name": "Sports",
        "description": "Games, gear, actions",
        "prompt_seed": "sports, athletics, equipment",
    },
    {
        "id": "tech",
        "name": "Tech",
        "description": "Computers, internet, devices",
        "prompt_seed": "technology, computing, internet",
    },
    {
        "id": "music",
        "name": "Music",
        "description": "Instruments and sound",
        "prompt_seed": "music, instruments, audio",
    },
    {
        "id": "random",
        "name": "Random",
        "description": "Pure Contexto mode (no timer, no powerups)",
        "prompt_seed": "random",
    },
]

def _normalize_theme_words(raw_words: object) -> list[str]:
    if not isinstance(raw_words, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_words:
        if not isinstance(item, str):
            continue
        word = item.strip().upper()
        if not word or not word.isalpha():
            continue
        if not (MIN_WORD_LEN <= len(word) <= MAX_WORD_LEN):
            continue
        if word in seen:
            continue
        cleaned.append(word)
        seen.add(word)
    return cleaned


def load_themes(path: Path) -> list[dict]:
    themes: list[dict] = []
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = []
        if isinstance(data, list):
            themes = data
    if not themes:
        themes = DEFAULT_THEMES
    seen: set[str] = set()
    cleaned: list[dict] = []
    for item in themes:
        if not isinstance(item, dict):
            continue
        theme_id = str(item.get("id", "")).strip().lower()
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        prompt_seed = str(item.get("prompt_seed", "")).strip()
        words = _normalize_theme_words(item.get("words", []))
        if not theme_id or theme_id in seen:
            continue
        if not name or not description:
            continue
        cleaned.append(
            {
                "id": theme_id,
                "name": name,
                "description": description,
                "prompt_seed": prompt_seed or name,
                "words": words,
            }
        )
        seen.add(theme_id)
    return cleaned


def _collect_theme_words(themes: list[dict]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for theme in themes:
        for word in theme.get("words", []) or []:
            if word in seen:
                continue
            merged.append(word)
            seen.add(word)
    return merged


def _load_random_words(path: Path) -> list[str]:
    if not path.exists():
        return []
    words: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip().upper()
        if not raw or not raw.isalpha():
            continue
        if not (MIN_WORD_LEN <= len(raw) <= MAX_WORD_LEN):
            continue
        if raw in seen:
            continue
        words.append(raw)
        seen.add(raw)
    return words

app = FastAPI()

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/json", ".map")

# Allow the browser frontend to call the backend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
WORDS = load_words(str(BASE_DIR / "words.txt"))
THEMES = load_themes(BASE_DIR / "themes.json")
THEME_WORDS = _collect_theme_words(THEMES)
if THEME_WORDS:
    word_set = set(WORDS)
    for word in THEME_WORDS:
        if word not in word_set:
            WORDS.append(word)
            word_set.add(word)
RANDOM_WORDS = _load_random_words(BASE_DIR / "random.txt")
if RANDOM_WORDS:
    word_set = set(WORDS)
    for word in RANDOM_WORDS:
        if word not in word_set:
            WORDS.append(word)
            word_set.add(word)
EASY_WORDS = load_easy_words(WORDS)
THEMES_BY_ID = {theme["id"]: theme for theme in THEMES}
DEFAULT_THEME_ID = THEMES[0]["id"] if THEMES else ""

LOW_MEMORY_MODE = os.getenv("LOW_MEMORY_MODE", "false").lower() in ("1", "true", "yes")
DEFAULT_EMBEDDING_MODEL = (
    "sentence-transformers/paraphrase-MiniLM-L3-v2"
    if LOW_MEMORY_MODE
    else "sentence-transformers/all-MiniLM-L6-v2"
)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
embedding_error = ""
_ranker = None
try:
    _ranker = SemanticRanker(WORDS, model_name=EMBEDDING_MODEL)
except Exception as exc:
    embedding_error = str(exc)

# Gemini client reads GEMINI_API_KEY from environment variable
gemini_client = None
if genai:
    try:
        gemini_client = genai.Client()
    except Exception:
        gemini_client = None

GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "4"))
LENIENT_WORD_VALIDATION = os.getenv("LENIENT_WORD_VALIDATION", "true").lower() in ("1", "true", "yes")
STREAK_BANK_TIME_PER_STREAK = int(os.getenv("STREAK_BANK_TIME_PER_STREAK", "5"))
STREAK_BANK_SCORE_PER_STREAK = int(os.getenv("STREAK_BANK_SCORE_PER_STREAK", "50"))
GEMINI_MIN_CONFIDENCE = float(os.getenv("GEMINI_MIN_CONFIDENCE", "0.85"))
RANDOM_GEMINI_VALIDATE = os.getenv("RANDOM_GEMINI_VALIDATE", "true").lower() in ("1", "true", "yes")
RANDOM_MIN_ZIPF = float(os.getenv("RANDOM_MIN_ZIPF", "3.6"))
THEME_BANK_MIN = int(os.getenv("THEME_BANK_MIN", "12"))
THEME_BANK_REFILL = int(os.getenv("THEME_BANK_REFILL", "36"))
THEME_CANDIDATE_COUNT = int(os.getenv("THEME_CANDIDATE_COUNT", "40"))
THEME_RECENT_LIMIT = int(os.getenv("THEME_RECENT_LIMIT", "50"))
THEME_MIN_WORD_LEN = int(os.getenv("THEME_MIN_WORD_LEN", os.getenv("MIN_WORD_LEN", "3")))
THEME_MAX_WORD_LEN = int(os.getenv("THEME_MAX_WORD_LEN", os.getenv("MAX_WORD_LEN", "12")))
RANDOM_BLACKLIST = {
    "ABILITY",
    "ABSTRACT",
    "ACTION",
    "ADVICE",
    "ANGER",
    "ANXIETY",
    "ATTITUDE",
    "AWARENESS",
    "BEHAVIOR",
    "BELIEF",
    "CHANGE",
    "CHAOS",
    "CHOICE",
    "CONCEPT",
    "CONFIDENCE",
    "CONFLICT",
    "CONNECTION",
    "COURAGE",
    "DATA",
    "DECISION",
    "DESIRE",
    "DESTINY",
    "DIFFICULTY",
    "DREAM",
    "DUTY",
    "EMOTION",
    "ENERGY",
    "EQUALITY",
    "EVENT",
    "EVIDENCE",
    "EXPERIENCE",
    "FAITH",
    "FEAR",
    "FEELING",
    "FOCUS",
    "FREEDOM",
    "FUTURE",
    "GROWTH",
    "HAPPINESS",
    "HEALTH",
    "HISTORY",
    "HOPE",
    "IDEA",
    "IMAGINATION",
    "INFORMATION",
    "INTELLIGENCE",
    "JOY",
    "JUSTICE",
    "KNOWLEDGE",
    "LOVE",
    "MEMORY",
    "MIND",
    "MOVEMENT",
    "PAIN",
    "PASSION",
    "PEACE",
    "PLAN",
    "POWER",
    "PROCESS",
    "PROGRESS",
    "PURPOSE",
    "QUALITY",
    "RANDOM",
    "REASON",
    "RELATIONSHIP",
    "RESPONSIBILITY",
    "RISK",
    "SCATTER",
    "SCIENCE",
    "SENSE",
    "SKILL",
    "SOCIETY",
    "SOLUTION",
    "SOUND",
    "SPIRIT",
    "STRESS",
    "SUCCESS",
    "SYSTEM",
    "TASK",
    "THEORY",
    "THOUGHT",
    "TIME",
    "TRUTH",
    "VALUE",
    "WORK",
    "RUN",
    "BUILD",
    "CREATE",
    "MAKE",
    "MOVE",
    "THINK",
    "FEEL",
    "LARGE",
    "SMALL",
    "BIG",
    "HUGE",
    "TINY",
    "QUICK",
    "SLOW",
    "FAST",
    "BRIGHT",
    "DARK",
    "GOOD",
    "BAD",
    "BEST",
    "WORST",
    "NEW",
    "OLD",
    "YOUNG",
    "HAPPY",
    "SAD",
    "ANGRY",
    "CALM",
    "LOUD",
    "QUIET",
    "SOFT",
    "HARD",
    "HOT",
    "COLD",
    "WARM",
    "COOL",
    "HIGH",
    "LOW",
    "SHORT",
    "LONG",
    "EARLY",
    "LATE",
    "LEFT",
    "RIGHT",
    "NEAR",
    "FAR",
    "FULL",
    "EMPTY",
    "GO",
    "GONE",
    "COME",
    "CAME",
    "GET",
    "GOT",
    "GIVE",
    "TAKE",
    "MAKE",
    "DO",
    "USE",
    "READ",
    "WRITE",
    "SPEAK",
    "SLEEP",
    "EAT",
    "DRINK",
    "PLAY",
    "WORK",
    "START",
    "STOP",
    "HAPPEN",
    "BREAK",
    "BROKE",
    "BRING",
    "CARRY",
    "AARON",
    "DAVID",
    "JAMES",
    "JOHN",
    "MARY",
    "SARAH",
    "PARIS",
    "LONDON",
    "TOKYO",
    "GOOGLE",
    "NIKE",
    "ADIDAS",
    "MICROSOFT",
    "FACEBOOK",
    "TESLA",
    "ALWAYS",
    "NEVER",
    "SOON",
    "THEN",
    "THERE",
    "HERE",
    "VERY",
    "QUITE",
    "RATHER",
    "FAST",
    "WELL",
    "AWAY",
    "UP",
    "DOWN",
    "IN",
    "OUT",
    "OFF",
    "ON",
    "OVER",
    "UNDER",
}
RANDOM_ABSTRACT_SUFFIXES = (
    "TION",
    "SION",
    "MENT",
    "NESS",
    "ITY",
    "ISM",
    "SHIP",
    "ANCE",
    "ENCE",
    "HOOD",
    "DOM",
    "LOGY",
    "GRAPHY",
    "PHOBIA",
    "PHILIA",
    "CRACY",
    "NOMY",
)
RANDOM_ADVERB_SUFFIXES = ("LY",)
RANDOM_LY_ALLOWLIST = {
    "BELLY",
    "DOLLY",
    "HOLLY",
    "JELLY",
    "LILY",
    "TROLLEY",
}
RANDOM_ING_ALLOWLIST = {
    "BUILDING",
    "CEILING",
    "CLOTHING",
    "EARRING",
    "FLOORING",
    "RAILING",
    "RING",
    "ROOFING",
    "SIDING",
    "WIRING",
}
_gemini_pool = ThreadPoolExecutor(max_workers=2)
_hint_cache = {}
_word_validation_cache = {}
_theme_word_banks: dict[str, list[str]] = {}
_theme_recent: dict[str, list[str]] = {}
WORDS_SET = set(WORDS)
EASY_WORDS_SET = set(EASY_WORDS)
_random_concrete_cache: dict[str, bool] = {}


def _is_random_concrete_word(word: str) -> bool:
    if not word or not word.isalpha():
        return False
    if word in RANDOM_BLACKLIST:
        return False
    if not (MIN_WORD_LEN <= len(word) <= MAX_WORD_LEN):
        return False
    if any(word.endswith(suffix) for suffix in RANDOM_ADVERB_SUFFIXES):
        if word not in RANDOM_LY_ALLOWLIST:
            return False
    if word.endswith("ING") and word not in RANDOM_ING_ALLOWLIST:
        return False
    if len(word) > 4 and word.endswith("ED"):
        return False
    for suffix in RANDOM_ABSTRACT_SUFFIXES:
        if word.endswith(suffix):
            return False
    if zipf_frequency:
        freq = float(zipf_frequency(word.lower(), "en"))
        if freq < RANDOM_MIN_ZIPF:
            return False
    elif EASY_WORDS_SET and word not in EASY_WORDS_SET:
        return False
    return True


def _build_random_word_pool(words: list[str]) -> list[str]:
    pool: list[str] = []
    seen: set[str] = set()
    for raw in words:
        cleaned = raw.strip().upper()
        if not cleaned:
            continue
        if not _is_random_concrete_word(cleaned):
            continue
        normalized = normalize_word(cleaned, WORDS_SET)
        if not normalized or normalized in seen:
            continue
        if not _is_random_concrete_word(normalized):
            continue
        pool.append(normalized)
        seen.add(normalized)
    return pool


RANDOM_WORD_POOL = _build_random_word_pool(RANDOM_WORDS or WORDS)


def _gemini_is_concrete_noun(word: str) -> bool:
    if not gemini_client or not RANDOM_GEMINI_VALIDATE:
        return True
    key = word.strip().upper()
    cached = _random_concrete_cache.get(key)
    if cached is not None:
        return cached
    prompt = (
        "Answer with YES or NO only.\n"
        "Is the following English word a concrete, physical noun for a tangible object you can see and touch?\n"
        "Reject abstract concepts, actions/verbs, adjectives, emotions, processes, intangible nouns, or proper nouns/names.\n"
        f"Word: {word}\n"
        "Answer:"
    )
    response = (gemini_generate_text(prompt) or "").strip().upper()
    if response.startswith("YES"):
        result = True
    elif response.startswith("NO"):
        result = False
    else:
        result = False
    _random_concrete_cache[key] = result
    return result


def _choose_random_concrete_word(words: list[str]) -> str:
    if not words:
        return ""
    candidates = [word for word in words if _is_random_concrete_word(word)]
    if not candidates:
        return ""
    attempts = min(50, len(candidates))
    for _ in range(attempts):
        candidate = random.choice(candidates)
        if not _gemini_is_concrete_noun(candidate):
            continue
        return candidate
    return random.choice(candidates)


def rank_guess(guess: str, secret: str):
    if not _ranker:
        raise RuntimeError("Embedding model unavailable. Install sentence-transformers and its dependencies.")
    return _ranker.rank_guess(guess, secret)


def gemini_generate_text(prompt: str) -> str:
    if not gemini_client:
        return ""

    def call_model() -> str:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return (response.text or "").strip()

    future = _gemini_pool.submit(call_model)
    try:
        return future.result(timeout=GEMINI_TIMEOUT_SECONDS)
    except TimeoutError:
        return ""
    except Exception:
        return ""


def _theme_public(theme: dict) -> dict:
    return {
        "id": theme.get("id", ""),
        "name": theme.get("name", ""),
        "description": theme.get("description", ""),
    }


def _theme_options(current_theme_id: str, count: int = 3) -> list[dict]:
    options = [
        _theme_public(theme)
        for theme in THEMES
        if theme.get("id") not in (current_theme_id, RANDOM_THEME_ID)
    ]
    if len(options) <= count:
        return options
    return random.sample(options, count)


def _record_theme_recent(theme_id: str, word: str) -> None:
    recent = _theme_recent.setdefault(theme_id, [])
    recent.append(word)
    if len(recent) > THEME_RECENT_LIMIT:
        del recent[:-THEME_RECENT_LIMIT]


def _is_valid_word(word: str) -> bool:
    if "gm" in globals():
        try:
            return gm.is_valid_guess(word)
        except Exception:
            return False
    return word in WORDS


def _generate_theme_candidates(theme: dict, difficulty: str, boss: bool) -> list[str]:
    if not gemini_client:
        return []
    difficulty_label = "boss" if boss else (difficulty or "easy")
    difficulty_hint = {
        "easy": "common everyday",
        "medium": "common",
        "hard": "less common",
        "expert": "obscure",
        "master": "rare",
        "legend": "very rare",
        "boss": "rare",
    }.get(difficulty_label, "common")
    prompt = (
        f"Generate {THEME_CANDIDATE_COUNT} English words between {THEME_MIN_WORD_LEN} and {THEME_MAX_WORD_LEN} letters long.\n"
        f"Theme: {theme.get('name')} ({theme.get('description')})\n"
        f"Focus: {theme.get('prompt_seed')}\n"
        f"Difficulty: {difficulty_label} ({difficulty_hint})\n"
        "Rules:\n"
        "- Output ONLY the words, one per line.\n"
        "- No proper nouns or acronyms.\n"
        "- No punctuation, numbering, or extra text."
    )
    text = gemini_generate_text(prompt)
    if not text:
        return []
    pattern = rf"[A-Za-z]{{{THEME_MIN_WORD_LEN},{THEME_MAX_WORD_LEN}}}"
    tokens = re.findall(pattern, text)
    results: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        word = token.upper()
        if word in seen:
            continue
        seen.add(word)
        if _is_valid_word(word):
            results.append(word)
    return results


def _refill_theme_bank(theme_id: str, difficulty: str, boss: bool) -> None:
    theme = THEMES_BY_ID.get(theme_id)
    if not theme:
        return
    candidates = _generate_theme_candidates(theme, difficulty, boss)
    if not candidates:
        return
    recent = set(_theme_recent.get(theme_id, []))
    bank = _theme_word_banks.setdefault(theme_id, [])
    for word in candidates:
        if len(bank) >= THEME_BANK_REFILL:
            break
        if word in recent or word in bank:
            continue
        bank.append(word)


def _refill_theme_bank_static(theme_id: str, allow_repeat: bool = False) -> None:
    theme = THEMES_BY_ID.get(theme_id)
    if not theme:
        return
    words = theme.get("words") or []
    if not words:
        return
    bank = _theme_word_banks.setdefault(theme_id, [])
    recent = set(_theme_recent.get(theme_id, []))
    candidates = [w for w in words if w not in bank and (allow_repeat or w not in recent)]
    if not candidates and not allow_repeat:
        candidates = [w for w in words if w not in bank]
    if not candidates:
        return
    random.shuffle(candidates)
    for word in candidates:
        if len(bank) >= THEME_BANK_REFILL:
            break
        bank.append(word)


def get_theme_word(theme_id: str, level: int, difficulty: str, boss: bool) -> str:
    if not theme_id or theme_id not in THEMES_BY_ID:
        return ""
    bank = _theme_word_banks.setdefault(theme_id, [])
    if len(bank) < THEME_BANK_MIN:
        _refill_theme_bank(theme_id, difficulty, boss)
        _refill_theme_bank_static(theme_id)
    if not bank:
        _refill_theme_bank_static(theme_id, allow_repeat=True)
    if bank:
        choice = random.choice(bank)
        bank.remove(choice)
        _record_theme_recent(theme_id, choice)
        return choice
    return ""


class GuessIn(BaseModel):
    guess_word: str | None = None
    guess: str | None = None


class PowerupChoiceIn(BaseModel):
    powerup_id: str


class HintIn(BaseModel):
    word: str
    hint_type: str = "definition"  # could be: definition, category, context


class RunHintIn(BaseModel):
    hint_type: str = "context"


class UsePowerupIn(BaseModel):
    inventory_id: str
    choice: str | None = None
    streak: int | None = None
    choices: list[str] | None = None


class StartRunIn(BaseModel):
    theme_id: str | None = None


class ThemeChoiceIn(BaseModel):
    theme_id: str


def _guess_entry_to_dict(entry) -> dict:
    return {
        "word": entry.word,
        "rank": entry.rank,
        "similarity": entry.similarity,
        "timestamp": entry.timestamp,
        "show_similarity": entry.show_similarity,
    }


def run_state_to_dict(rs):
    theme = None
    if rs.theme_id and not rs.is_random_mode:
        theme = THEMES_BY_ID.get(rs.theme_id)
    pending_theme_choice = rs.pending_theme_choice
    theme_options = rs.theme_options
    inventory = rs.inventory
    pending_powerups = rs.pending_powerups
    if rs.is_random_mode:
        pending_theme_choice = False
        theme_options = []
        inventory = []
        pending_powerups = []
    return {
        "run_id": rs.run_id,
        "level": rs.level,
        "guesses": [_guess_entry_to_dict(entry) for entry in rs.guesses],
        "best_rank": rs.best_rank,
        "won": rs.won,
        "failed": rs.failed,
        "pending_powerups": pending_powerups,
        "skip_available": rs.skip_available,
        "skip_in_levels": rs.skip_in_levels(),
        "score": rs.score,
        "last_score_delta": rs.last_score_delta,
        "difficulty": rs.difficulty,
        "boss_level": rs.boss_level,
        "theme_id": rs.theme_id,
        "theme_name": theme.get("name") if theme else "",
        "theme_description": theme.get("description") if theme else "",
        "pending_theme_choice": pending_theme_choice,
        "theme_options": theme_options,
        "inventory": inventory,
        "similarity_reveal_remaining": rs.similarity_reveal_remaining,
        "random_mode": rs.is_random_mode,
    }


def generate_word(level: int, difficulty: str, theme_id: str | None = None, boss: bool = False) -> str:
    if theme_id and is_random_theme(theme_id):
        pool = RANDOM_WORD_POOL or WORDS
        return _choose_random_concrete_word(pool) if pool else ""
    if theme_id:
        themed = get_theme_word(theme_id, level, difficulty, boss)
        if themed:
            return themed
    return ""


def _fallback_hint(word: str) -> str:
    word = word.strip().upper()
    vowel_count = sum(1 for ch in word if ch in VOWELS)
    has_repeat = len(set(word)) < len(word)
    rare_count = sum(1 for ch in word if ch in RARE_LETTERS)

    details = [f"{vowel_count} vowel{'s' if vowel_count != 1 else ''}"]
    details.append("a repeated letter" if has_repeat else "no repeated letters")
    if rare_count:
        details.append("a rare letter")

    return f"It is a {len(word)}-letter word with " + ", ".join(details) + "."


def _fallback_usage(word: str) -> str:
    cleaned = word.strip().lower()
    return f'Example: "{cleaned}" appears in this sentence.'


def _fallback_rhyme(word: str) -> str:
    cleaned = word.strip().lower()
    ending = cleaned[-2:] if len(cleaned) >= 2 else cleaned
    return f"It rhymes with a word ending in '{ending}'."


def _fallback_function(word: str) -> str:
    return "It is commonly used for everyday tasks."


def _fallback_descriptor(word: str) -> str:
    return "practical"


def generate_related_word(word: str, theme: dict | None = None) -> str:
    if not gemini_client:
        return ""
    theme_line = ""
    if theme:
        theme_line = f"Theme: {theme.get('name')} ({theme.get('description')})\n"
    prompt = (
        "Provide ONE English word that is closely related to the target word.\n"
        f"{theme_line}"
        f"Target word: {word}\n"
        "Rules:\n"
        "- Return only the related word.\n"
        "- Do NOT return the target word.\n"
        "- Do NOT return a synonym or a plural/singular form of the word.\n"
        "- 3 to 12 letters."
    )
    related_text = gemini_generate_text(prompt)
    tokens = []
    for part in (related_text or "").split():
        cleaned = "".join(ch for ch in part if ch.isalpha())
        if cleaned:
            tokens.append(cleaned)
    target_norm = normalize_word(word, WORDS_SET)
    candidate = ""
    for token in tokens:
        if normalize_word(token, WORDS_SET) == target_norm:
            continue
        candidate = token
        break
    if candidate:
        return candidate.upper()
    return ""


def generate_hint(word: str, hint_type: str, theme: dict | None = None) -> str:
    normalized = (hint_type or "context").strip().lower()
    theme_id = theme.get("id") if theme else ""
    cache_key = (word.strip().upper(), normalized, theme_id)
    cached = _hint_cache.get(cache_key)
    if cached:
        return cached
    theme_line = ""
    if theme:
        theme_line = f"Theme: {theme.get('name')} ({theme.get('description')})\n"

    if normalized == "usage":
        if not gemini_client:
            hint = _fallback_usage(word)
            _hint_cache[cache_key] = hint
            return hint

        prompt = (
            "You are generating a usage example for a Wordle-style game.\n"
            f"{theme_line}"
            f"Target word: {word}\n"
            "Rules:\n"
            "- Write ONE short sentence that uses the target word.\n"
            "- Keep it under 12 words.\n"
            "- Return only the sentence."
        )
        hint = gemini_generate_text(prompt)
        if not hint:
            hint = _fallback_usage(word)
        _hint_cache[cache_key] = hint
        return hint

    if normalized in ("functional", "function", "purpose"):
        if not gemini_client:
            hint = _fallback_function(word)
            _hint_cache[cache_key] = hint
            return hint
        prompt = (
            "Provide ONE short sentence about what the word is commonly used for.\n"
            f"{theme_line}"
            f"Word: {word}\n"
            "Rules:\n"
            "- Do NOT include the word itself.\n"
            "- Do NOT include direct synonyms.\n"
            "- Keep it under 12 words.\n"
            "Return only the sentence."
        )
        hint = gemini_generate_text(prompt)
        if not hint or word in hint.upper():
            hint = _fallback_function(word)
        _hint_cache[cache_key] = hint
        return hint

    if normalized in ("descriptor", "adjective", "describe"):
        if not gemini_client:
            hint = _fallback_descriptor(word)
            _hint_cache[cache_key] = hint
            return hint
        prompt = (
            "Provide ONE common adjective that describes the word.\n"
            f"{theme_line}"
            f"Word: {word}\n"
            "Rules:\n"
            "- Return ONLY the adjective, one word.\n"
            "- Do NOT return the target word or synonyms."
        )
        descriptor = gemini_generate_text(prompt)
        token = ""
        for part in (descriptor or "").split():
            cleaned = "".join(ch for ch in part if ch.isalpha())
            if cleaned:
                token = cleaned
                break
        if token and token.upper() != word.strip().upper():
            hint = f"Often described as {token.lower()}."
        else:
            hint = _fallback_descriptor(word)
        _hint_cache[cache_key] = hint
        return hint

    if normalized == "rhyme":
        if not gemini_client:
            hint = _fallback_rhyme(word)
            _hint_cache[cache_key] = hint
            return hint

        prompt = (
            "Provide ONE English word that rhymes with the target word.\n"
            f"{theme_line}"
            f"Target word: {word}\n"
            "Rules:\n"
            "- Return only the rhyming word.\n"
            "- Do NOT return the target word.\n"
            "- 3 to 7 letters."
        )
        rhyme_text = gemini_generate_text(prompt)
        tokens = []
        for part in (rhyme_text or "").split():
            cleaned = "".join(ch for ch in part if ch.isalpha())
            if cleaned:
                tokens.append(cleaned)
        stop_words = {"IT", "RHYMES", "WITH", "THE", "WORD", "A", "AN"}
        candidate = ""
        for token in reversed(tokens):
            if token.upper() not in stop_words:
                candidate = token
                break
        if not candidate and tokens:
            candidate = tokens[-1]
        if candidate and candidate.upper() != word.strip().upper():
            hint = f"It rhymes with {candidate.lower()}."
        else:
            hint = _fallback_rhyme(word)
        _hint_cache[cache_key] = hint
        return hint

    if not gemini_client:
        hint = _fallback_hint(word)
        _hint_cache[cache_key] = hint
        return hint

    if normalized == "definition":
        prompt = (
            "You are a dictionary.\n"
            f"{theme_line}"
            f"Target word: {word}\n"
            "Rules:\n"
            "- Provide ONE sentence with a concise definition.\n"
            "- Do NOT use the target word in the definition.\n"
            "- Keep it under 12 words.\n"
            "Return only the definition."
        )
    elif normalized == "category":
        prompt = (
            "You are providing a category label for a word guessing game.\n"
            f"{theme_line}"
            f"Target word: {word}\n"
            "Rules:\n"
            "- Provide a 1 to 3 word category or type.\n"
            "- Do NOT include the target word.\n"
            "Return only the category."
        )
    else:
        prompt = (
            "You are generating a subtle clue for a word guessing game.\n"
            f"{theme_line}"
            f"Target word: {word}\n"
            "Rules:\n"
            "- Do NOT say the target word.\n"
            "- Do NOT reveal letters or positions.\n"
            "- Do NOT give an anagram.\n"
            "- Keep it to ONE short sentence.\n"
            "Return only the hint."
        )

    hint = gemini_generate_text(prompt)
    if not hint or word in hint.upper():
        retry_prompt = (
            prompt
            + "\nImportant: The hint must NOT include the target word. Try again."
        )
        hint = gemini_generate_text(retry_prompt)

    if not hint or word in hint.upper():
        hint = _fallback_hint(word)

    _hint_cache[cache_key] = hint
    return hint


def _extract_json_object(text: str):
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    snippet = text[start : end + 1]
    try:
        return json.loads(snippet)
    except Exception:
        return None


def gemini_validates_word(word: str):
    if not gemini_client:
        return None
    cleaned = word.strip().upper()
    cached = _word_validation_cache.get(cleaned)
    if cached is not None:
        return cached
    prompt = (
        "You are a strict English dictionary validator.\n"
        f"Word: {cleaned}\n"
        "Return ONLY JSON with keys: is_word, confidence, definition.\n"
        "- is_word: true/false\n"
        "- confidence: number 0 to 1 (only use >= 0.85 if certain)\n"
        "- definition: short definition (do NOT include the word itself)\n"
        "If you are unsure or the word is not in a standard dictionary, set is_word=false and confidence<=0.5.\n"
        "Return ONLY the JSON object."
    )
    text = gemini_generate_text(prompt)
    data = _extract_json_object(text)
    if not isinstance(data, dict):
        return None
    is_word = bool(data.get("is_word"))
    try:
        confidence = float(data.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    definition = str(data.get("definition", "")).strip()
    blocked_terms = ("abbreviation", "acronym", "initialism", "proper noun", "surname", "name", "brand")
    if (
        is_word
        and confidence >= GEMINI_MIN_CONFIDENCE
        and definition
        and cleaned not in definition.upper()
        and not any(term in definition.lower() for term in blocked_terms)
    ):
        _word_validation_cache[cleaned] = True
        return True
    _word_validation_cache[cleaned] = False
    return False


gm = GameManager(
    WORDS,
    rank_guess=rank_guess,
    word_provider=generate_word,
    easy_words=EASY_WORDS,
    theme_options_provider=_theme_options,
)


@app.get("/api/themes")
def list_themes():
    return {"themes": [_theme_public(theme) for theme in THEMES]}


@app.post("/api/run/start")
def start_run(payload: StartRunIn | None = None):
    theme_id = (payload.theme_id if payload else DEFAULT_THEME_ID) or DEFAULT_THEME_ID
    theme_id = theme_id.strip().lower() if theme_id else ""
    if theme_id and theme_id not in THEMES_BY_ID:
        theme_id = DEFAULT_THEME_ID
    try:
        rs = gm.start_run(theme_id=theme_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start run: {exc}") from exc
    return run_state_to_dict(rs)


@app.post("/api/run/{run_id}/guess")
def submit_guess(run_id: str, payload: GuessIn):
    try:
        rs = gm.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc

    if rs.pending_powerups or rs.won or rs.failed:
        return run_state_to_dict(rs)

    guess = (payload.guess_word or payload.guess or "").strip().upper()
    if not guess:
        raise HTTPException(status_code=400, detail="Guess required.")
    if not guess.isalpha():
        raise HTTPException(status_code=400, detail="Letters only.")
    if not gm.is_valid_guess(guess):
        if gemini_client and LENIENT_WORD_VALIDATION:
            gemini_result = gemini_validates_word(guess)
            if gemini_result is True:
                gm.add_word(guess)
            else:
                raise HTTPException(status_code=400, detail="Not in dictionary.")
        else:
            raise HTTPException(status_code=400, detail="Not in dictionary.")

    if not _ranker:
        raise HTTPException(status_code=503, detail="Embedding model unavailable.")

    prev_best_rank = rs.best_rank
    prev_guess_count = len(rs.guesses)
    rs = gm.submit_guess(run_id, guess)
    response = run_state_to_dict(rs)
    if rs.momentum_bonus_active and len(rs.guesses) > prev_guess_count:
        improved = prev_best_rank is None or (
            rs.best_rank is not None and rs.best_rank < prev_best_rank
        )
        if improved:
            time_bonus = int(rs.momentum_bonus_value or 0)
            if time_bonus > 0:
                response["time_bonus_seconds"] = time_bonus
                if rs.last_effect_messages is None:
                    rs.last_effect_messages = []
                rs.last_effect_messages.append(f"+{time_bonus} seconds (momentum bonus).")
        rs.momentum_bonus_active = False
        rs.momentum_bonus_value = 0
    if rs.last_effect_messages:
        response["effect_messages"] = rs.last_effect_messages
    rs.last_effect_messages = []
    return response


@app.post("/api/run/{run_id}/skip")
def skip_level(run_id: str):
    rs = gm.skip_level(run_id)
    return run_state_to_dict(rs)


@app.post("/api/run/{run_id}/fail")
def fail_run(run_id: str):
    try:
        rs = gm.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    messages = []
    if rs.skip_insurance_active:
        rs.last_skip_level = -999
        rs.skip_insurance_active = False
        messages.append("Skip cooldown reset.")
    if rs.safety_net_levels > 0:
        rs.safety_net_levels = 0
        gm._advance_level(rs, completed=False)
        messages.append("Safety Net saved your run.")
        return {
            "state": run_state_to_dict(rs),
            "saved": True,
            "messages": messages,
        }
    rs.failed_flag = True
    return {
        "state": run_state_to_dict(rs),
        "saved": False,
        "messages": messages,
    }


@app.post("/api/run/{run_id}/choose_powerup")
def choose_powerup(run_id: str, payload: PowerupChoiceIn):
    rs, chosen, message = gm.choose_powerup(run_id, payload.powerup_id)
    return {
        "state": run_state_to_dict(rs),
        "added": chosen if chosen else None,
        "message": message,
    }


@app.post("/api/run/{run_id}/choose_theme")
def choose_theme(run_id: str, payload: ThemeChoiceIn):
    try:
        rs = gm.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    if not rs.pending_theme_choice:
        return run_state_to_dict(rs)
    theme_id = payload.theme_id.strip().lower()
    if theme_id not in THEMES_BY_ID:
        raise HTTPException(status_code=400, detail="Invalid theme.")
    allowed = {opt.get("id") for opt in rs.theme_options}
    if allowed and theme_id not in allowed:
        raise HTTPException(status_code=400, detail="Theme not available.")
    rs = gm.apply_theme_choice(run_id, theme_id)
    return run_state_to_dict(rs)


@app.post("/api/run/{run_id}/use_powerup")
def use_powerup(run_id: str, payload: UsePowerupIn):
    rs, chosen = gm.use_powerup(run_id, payload.inventory_id)
    hint = None
    related_word = None
    time_bonus_seconds = None
    time_penalty_seconds = None
    timer_freeze_seconds = None
    timer_slow_seconds = None
    messages = []
    if not chosen:
        return {"state": run_state_to_dict(rs), "used": None}

    powerup_id = chosen.get("id") or ""
    if powerup_id == "semantic_direction":
        if _is_random_concrete_word(rs.secret):
            messages.append("This word represents something physical and tangible.")
        else:
            messages.append("This word is more abstract than physical.")
    elif powerup_id == "concept_neighbor":
        related_word = generate_related_word(rs.secret, THEMES_BY_ID.get(rs.theme_id))
        if related_word:
            messages.append(f"Related concept: {related_word}.")
        else:
            messages.append("No related concept available.")
    elif powerup_id == "functional_hint":
        hint = generate_hint(rs.secret, "functional", THEMES_BY_ID.get(rs.theme_id))
        if hint:
            messages.append(hint)
        else:
            messages.append("No functional hint available.")
    elif powerup_id == "descriptor_hint":
        hint = generate_hint(rs.secret, "descriptor", THEMES_BY_ID.get(rs.theme_id))
        if hint:
            messages.append(hint)
        else:
            messages.append("No descriptor hint available.")
    elif powerup_id == "undo_guess":
        if rs.guesses:
            rs.guesses.pop()
            rs.best_rank = min((entry.rank for entry in rs.guesses), default=None)
            messages.append("Last guess removed.")
        else:
            messages.append("No guesses to undo.")
    elif powerup_id == "reroll_target":
        gm.reroll_target(rs)
        messages.append("Target rerolled. No reward for this level.")
    elif powerup_id == "anchor_guess":
        choice = (payload.choice or "").strip().upper()
        if not choice:
            messages.append("Select a guess to anchor.")
        else:
            match = next((entry for entry in rs.guesses if entry.word == choice), None)
            if not match:
                messages.append("Anchor must be one of your guesses.")
            else:
                rs.anchor_word = match.word
                rs.anchor_rank = match.rank
                messages.append(f"Anchor set to {match.word}.")
    elif powerup_id == "similarity_reveal":
        count = int(chosen.get("value") or 0)
        if count > 0:
            rs.similarity_reveal_remaining = max(rs.similarity_reveal_remaining, count)
            messages.append(f"Similarity revealed for the next {count} guesses.")
    elif powerup_id == "comparator":
        choices = payload.choices or []
        normalized = [choice.strip().upper() for choice in choices if choice]
        unique = []
        for choice in normalized:
            if choice not in unique:
                unique.append(choice)
        if len(unique) != 2:
            messages.append("Select two guesses to compare.")
        else:
            first = next((entry for entry in rs.guesses if entry.word == unique[0]), None)
            second = next((entry for entry in rs.guesses if entry.word == unique[1]), None)
            if not first or not second:
                messages.append("Both selections must be previous guesses.")
            elif first.rank < second.rank:
                messages.append(f"{first.word} is closer than {second.word}.")
            elif first.rank > second.rank:
                messages.append(f"{second.word} is closer than {first.word}.")
            else:
                messages.append(f"{first.word} and {second.word} are equally close.")
    elif powerup_id == "gradient_scan":
        if rs.best_rank is None:
            messages.append("Make a guess to scan the gradient.")
        else:
            total = max(1, len(WORDS))
            ratio = rs.best_rank / total
            if ratio <= 0.1:
                messages.append("Target feels near the top of your semantic space.")
            elif ratio <= 0.4:
                messages.append("Target feels closer to the middle of your semantic space.")
            else:
                messages.append("Target feels deeper toward the bottom of your semantic space.")
    elif powerup_id == "micro_freeze":
        timer_freeze_seconds = 2
        messages.append("Micro Freeze activated.")
    elif powerup_id == "slow_drain":
        timer_slow_seconds = 10
        messages.append("Slow Drain activated.")
    elif powerup_id == "momentum_bonus":
        rs.momentum_bonus_active = True
        rs.momentum_bonus_value = int(chosen.get("value") or 0)
        messages.append("Momentum Bonus armed. Beat your best rank to gain time.")
    elif powerup_id == "skip_cooldown_reducer":
        rs.skip_cooldown_reduction_value = max(rs.skip_cooldown_reduction_value, 1)
        rs.skip_cooldown_reduction_levels = max(rs.skip_cooldown_reduction_levels, 5)
        messages.append("Skip cooldown reduced for the next 5 levels.")
    elif powerup_id == "skip_refresh":
        rs.last_skip_level = -999
        messages.append("Skip is ready.")
    elif powerup_id == "skip_insurance":
        rs.skip_insurance_active = True
        messages.append("Skip insurance armed for the next level.")
    elif powerup_id == "expanded_choice":
        rs.expanded_choice_levels = max(rs.expanded_choice_levels, 1)
        messages.append("Next reward will offer 4 options.")
    elif powerup_id == "reroll_rewards":
        if rs.pending_powerups:
            desired = len(rs.pending_powerups)
            rs.pending_powerups = gm._roll_powerups(rs, count=desired, consume_expanded=False)
            messages.append("Reward options rerolled.")
        else:
            messages.append("No rewards to reroll.")
    elif powerup_id == "safety_net":
        rs.safety_net_levels = max(rs.safety_net_levels, 3)
        messages.append("Safety Net armed for the next 3 levels.")

    return {
        "state": run_state_to_dict(rs),
        "used": chosen,
        "messages": messages,
        "hint": hint,
        "related_word": related_word,
        "time_bonus_seconds": time_bonus_seconds,
        "time_penalty_seconds": time_penalty_seconds,
        "timer_freeze_seconds": timer_freeze_seconds,
        "timer_slow_seconds": timer_slow_seconds,
    }


@app.post("/api/hint")
def get_hint(payload: HintIn):
    word = payload.word.strip().upper()
    hint_type = payload.hint_type
    hint = generate_hint(word, hint_type)
    return {"hint": hint}


@app.post("/api/run/{run_id}/hint")
def get_run_hint(run_id: str, payload: RunHintIn):
    try:
        rs = gm.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    theme = None if rs.is_random_mode else THEMES_BY_ID.get(rs.theme_id)
    hint = generate_hint(rs.secret, payload.hint_type or "context", theme)
    return {"hint": hint}


@app.get("/api/run/{run_id}/reveal")
def reveal_run_word(run_id: str):
    try:
        rs = gm.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    return {"word": rs.secret}


@app.get("/api/validation", include_in_schema=False)
def validation_status():
    return {
        "gemini_available": bool(gemini_client),
        "min_confidence": GEMINI_MIN_CONFIDENCE,
        "lenient": LENIENT_WORD_VALIDATION,
        "embedding_ready": bool(_ranker),
        "embedding_model": EMBEDDING_MODEL,
        "embedding_error": embedding_error,
    }


@app.get("/api/random/backgrounds")
def list_random_backgrounds():
    candidates = [
        (BASE_DIR / ".." / "Front End" / "public" / "random").resolve(),
        (BASE_DIR / ".." / "static" / "random").resolve(),
        (BASE_DIR / "static" / "random").resolve(),
    ]
    random_dir = next((path for path in candidates if path.exists()), None)
    if not random_dir:
        return {"backgrounds": []}
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    files = [
        p.name
        for p in random_dir.iterdir()
        if p.is_file() and p.suffix.lower() in exts
    ]
    files.sort()
    return {"backgrounds": [f"/random/{name}" for name in files]}


# Serve frontend files if built assets are present
frontend_candidates = [
    (BASE_DIR / "static").resolve(),
    (BASE_DIR / ".." / "static").resolve(),
    (BASE_DIR / ".." / "Front End" / "dist").resolve(),
    (BASE_DIR / ".." / "Front End" / "build").resolve(),
]


def resolve_frontend_dir() -> Path | None:
    for path in frontend_candidates:
        if path.exists():
            return path
    return None


@app.get("/", include_in_schema=False)
def serve_frontend_index():
    frontend_dir = resolve_frontend_dir()
    if not frontend_dir:
        raise HTTPException(status_code=404, detail="Frontend build not found. Run npm run build.")
    index_path = (frontend_dir / "index.html").resolve()
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend index not found.")
    return FileResponse(str(index_path))


@app.get("/__debug/frontend", include_in_schema=False)
def debug_frontend():
    frontend_dir = resolve_frontend_dir()
    assets = []
    if frontend_dir:
        assets_dir = frontend_dir / "assets"
        if assets_dir.exists():
            assets = sorted([p.name for p in assets_dir.iterdir() if p.is_file()])
    return {
        "frontend_dir": str(frontend_dir) if frontend_dir else None,
        "candidates": [str(path) for path in frontend_candidates],
        "index_exists": bool(frontend_dir and (frontend_dir / "index.html").exists()),
        "assets": assets,
    }


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend_fallback(full_path: str):
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="Not Found")
    frontend_dir = resolve_frontend_dir()
    if not frontend_dir:
        raise HTTPException(status_code=404, detail="Frontend build not found. Run npm run build.")
    safe_path = Path(full_path)
    if safe_path.is_absolute() or ".." in safe_path.parts:
        raise HTTPException(status_code=404, detail="Not Found")
    candidate = (frontend_dir / safe_path).resolve()
    if candidate.is_file():
        media_type, _ = mimetypes.guess_type(str(candidate))
        return FileResponse(str(candidate), media_type=media_type)
    index_path = (frontend_dir / "index.html").resolve()
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend index not found.")
    return FileResponse(str(index_path))

