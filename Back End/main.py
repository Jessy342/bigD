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
    DEFAULT_WORD_LEN,
    RARE_LETTERS,
    VOWELS,
)

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
]


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
            }
        )
        seen.add(theme_id)
    return cleaned

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
EASY_WORDS = load_easy_words(str(BASE_DIR / "words.txt"))
THEMES = load_themes(BASE_DIR / "themes.json")
THEMES_BY_ID = {theme["id"]: theme for theme in THEMES}
DEFAULT_THEME_ID = THEMES[0]["id"] if THEMES else ""

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
THEME_BANK_MIN = int(os.getenv("THEME_BANK_MIN", "12"))
THEME_BANK_REFILL = int(os.getenv("THEME_BANK_REFILL", "36"))
THEME_CANDIDATE_COUNT = int(os.getenv("THEME_CANDIDATE_COUNT", "40"))
THEME_RECENT_LIMIT = int(os.getenv("THEME_RECENT_LIMIT", "50"))
_gemini_pool = ThreadPoolExecutor(max_workers=2)
_hint_cache = {}
_word_validation_cache = {}
_theme_word_banks: dict[str, list[str]] = {}
_theme_recent: dict[str, list[str]] = {}
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


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


def _theme_options(current_theme_id: str, count: int = 2) -> list[dict]:
    options = [_theme_public(theme) for theme in THEMES if theme.get("id") != current_theme_id]
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
        f"Generate {THEME_CANDIDATE_COUNT} English words that are exactly 5 letters long.\n"
        f"Theme: {theme.get('name')} ({theme.get('description')})\n"
        f"Focus: {theme.get('prompt_seed')}\n"
        f"Difficulty: {difficulty_label} ({difficulty_hint})\n"
        "Rules:\n"
        "- Output ONLY the words, one per line.\n"
        "- No proper nouns or acronyms.\n"
        "- Avoid plurals ending in S if possible.\n"
        "- No punctuation, numbering, or extra text."
    )
    text = gemini_generate_text(prompt)
    if not text:
        return []
    tokens = re.findall(r"[A-Za-z]{5}", text)
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


def get_theme_word(theme_id: str, level: int, difficulty: str, boss: bool) -> str:
    if not theme_id or theme_id not in THEMES_BY_ID:
        return ""
    bank = _theme_word_banks.setdefault(theme_id, [])
    if len(bank) < THEME_BANK_MIN:
        _refill_theme_bank(theme_id, difficulty, boss)
    if bank:
        choice = random.choice(bank)
        bank.remove(choice)
        _record_theme_recent(theme_id, choice)
        return choice
    return ""


class GuessIn(BaseModel):
    guess: str


class PowerupChoiceIn(BaseModel):
    powerup_id: str


class HintIn(BaseModel):
    word: str
    hint_type: str = "definition"  # could be: definition, usage, category, context


class RunHintIn(BaseModel):
    hint_type: str = "context"

class UsePowerupIn(BaseModel):
    inventory_id: str
    choice: str | None = None
    streak: int | None = None


class StartRunIn(BaseModel):
    theme_id: str | None = None


class ThemeChoiceIn(BaseModel):
    theme_id: str


def run_state_to_dict(rs):
    theme = THEMES_BY_ID.get(rs.theme_id) if rs.theme_id else None
    return {
        "run_id": rs.run_id,
        "level": rs.level,
        "guesses": rs.guesses,
        "feedback": rs.feedback,
        "won": rs.won,
        "failed": rs.failed,
        "pending_powerups": rs.pending_powerups,
        "skip_available": rs.skip_available,
        "skip_in_levels": rs.skip_in_levels(),
        "word_len": DEFAULT_WORD_LEN,
        "max_guesses": rs.max_guesses,
        "score": rs.score,
        "last_score_delta": rs.last_score_delta,
        "difficulty": rs.difficulty,
        "boss_level": rs.boss_level,
        "theme_id": rs.theme_id,
        "theme_name": theme.get("name") if theme else "",
        "theme_description": theme.get("description") if theme else "",
        "pending_theme_choice": rs.pending_theme_choice,
        "theme_options": rs.theme_options,
        "inventory": rs.inventory,
        "clutch_shield": rs.clutch_shield,
    }


def generate_word(level: int, difficulty: str, theme_id: str | None = None, boss: bool = False) -> str:
    if theme_id:
        themed = get_theme_word(theme_id, level, difficulty, boss)
        if themed:
            return themed

    if not gemini_client:
        return ""

    prompt = (
        "Generate one random 5-letter English word for a Wordle-style game.\n"
        f"Difficulty: {difficulty}.\n"
        "Easy should be common everyday words. Hard should be more obscure words.\n"
        "Boss should be rare/uncommon words that are still valid English.\n"
        "Rules:\n"
        "- Return only the word.\n"
        "- Exactly 5 letters.\n"
        "- No punctuation or extra text."
    )

    text = gemini_generate_text(prompt).upper()
    if not text:
        return ""

    cleaned = "".join(ch if ch.isalpha() else " " for ch in text)
    for token in cleaned.split():
        if len(token) == DEFAULT_WORD_LEN and token.isalpha():
            return token
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
    else:
        prompt = (
            "You are generating a subtle clue for a Wordle-style game.\n"
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


def _reveal_for_mode(secret: str, mode: str):
    if not secret:
        return None, None
    normalized = (mode or "first").strip().lower()
    length = len(secret)
    if normalized == "first":
        return secret[0], f"First letter: {secret[0]}"
    if normalized == "last":
        return secret[-1], f"Last letter: {secret[-1]}"
    if normalized == "random":
        idx = random.randrange(length)
        return secret[idx], f"Letter at position {idx + 1}: {secret[idx]}"
    if normalized == "vowel":
        vowel_indices = [i for i, ch in enumerate(secret) if ch in VOWELS]
        if vowel_indices:
            idx = random.choice(vowel_indices)
            return secret[idx], f"Vowel at position {idx + 1}: {secret[idx]}"
        idx = random.randrange(length)
        return secret[idx], f"Letter at position {idx + 1}: {secret[idx]}"
    idx = random.randrange(length)
    return secret[idx], f"Letter at position {idx + 1}: {secret[idx]}"


gm = GameManager(
    WORDS,
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
    rs = gm.start_run(theme_id=theme_id)
    return run_state_to_dict(rs)


@app.post("/api/run/{run_id}/guess")
def submit_guess(run_id: str, payload: GuessIn):
    try:
        rs = gm.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc

    if rs.pending_powerups or rs.won or rs.failed:
        return run_state_to_dict(rs)

    guess = payload.guess.strip().upper()
    if len(guess) != DEFAULT_WORD_LEN:
        raise HTTPException(status_code=400, detail=f"Guess must be {DEFAULT_WORD_LEN} letters.")
    if not guess.isalpha():
        raise HTTPException(status_code=400, detail="Letters only.")
    if not gm.is_valid_guess(guess):
        if gemini_client:
            gemini_result = gemini_validates_word(guess)
            if gemini_result is True:
                gm.add_word(guess)
            else:
                raise HTTPException(status_code=400, detail="Not in dictionary.")
        else:
            raise HTTPException(status_code=400, detail="Not in dictionary.")

    rs = gm.submit_guess(run_id, guess)
    response = run_state_to_dict(rs)
    if rs.last_effect_messages:
        response["effect_messages"] = rs.last_effect_messages
    if rs.last_time_bonus_seconds:
        response["time_bonus_seconds"] = rs.last_time_bonus_seconds
    if rs.last_time_penalty_seconds:
        response["time_penalty_seconds"] = rs.last_time_penalty_seconds
    rs.last_effect_messages = []
    rs.last_time_bonus_seconds = 0
    rs.last_time_penalty_seconds = 0
    return response


@app.post("/api/run/{run_id}/skip")
def skip_level(run_id: str):
    rs = gm.skip_level(run_id)
    return run_state_to_dict(rs)


@app.post("/api/run/{run_id}/choose_powerup")
def choose_powerup(run_id: str, payload: PowerupChoiceIn):
    rs, chosen = gm.choose_powerup(run_id, payload.powerup_id)
    return {
        "state": run_state_to_dict(rs),
        "added": chosen,
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
    reveal_letter = None
    reveal_message = None
    time_bonus_seconds = None
    time_penalty_seconds = None
    timer_freeze_seconds = None
    timer_slow_seconds = None
    messages = []
    if not chosen:
        return {"state": run_state_to_dict(rs), "used": None}

    powerup_id = chosen.get("id") or ""
    powerup_type = chosen.get("type") or ""

    if powerup_id == "extra_row":
        if rs.extra_rows < 2:
            rs.extra_rows += 1
            messages.append("Extra Row added (+1 guess).")
        else:
            messages.append("Extra Row already maxed (+2).")
    elif powerup_id == "micro_pause":
        timer_freeze_seconds = 2
        messages.append("Micro Pause activated.")
    elif powerup_id == "slow_time":
        timer_slow_seconds = 10
        messages.append("Slow Time activated.")
    elif powerup_id == "perfect_clear_bonus":
        rs.perfect_clear_pending += 1
        messages.append("Perfect Clear armed for your next win.")
    elif powerup_id == "clutch_shield":
        rs.clutch_shield += 1
        messages.append("Clutch Shield armed.")
    elif powerup_id == "letter_exclusion_scan":
        secret_letters = set(rs.secret)
        options = [ch for ch in ALPHABET if ch not in secret_letters]
        reveal = random.sample(options, k=min(3, len(options)))
        messages.append(f"Not in word: {', '.join(reveal)}.")
    elif powerup_id == "letter_inclusion_scan":
        letter = random.choice(list(set(rs.secret)))
        messages.append(f"Contains letter: {letter}.")
    elif powerup_id == "position_reveal":
        idx = random.randrange(len(rs.secret))
        reveal_letter = rs.secret[idx]
        reveal_message = f"Position {idx + 1}: {rs.secret[idx]}."
        messages.append(reveal_message)
    elif powerup_id == "hot_cold_rating":
        rs.hot_cold_pending = 1
        messages.append("Hot/Cold rating armed for your next guess.")
    elif powerup_id == "skip_cooldown_reducer":
        rs.skip_cooldown_reduction_value = max(rs.skip_cooldown_reduction_value, 1)
        rs.skip_cooldown_reduction_levels = max(rs.skip_cooldown_reduction_levels, 5)
        messages.append("Skip cooldown reduced for the next 5 levels.")
    elif powerup_id == "skip_refresh":
        messages.append("Skip is ready.")
    elif powerup_id == "skip_insurance":
        rs.skip_insurance += 1
        messages.append("Skip Insurance armed.")
    elif powerup_id == "score_multiplier":
        rs.score_multiplier = max(rs.score_multiplier, 1.5)
        rs.score_multiplier_levels += 2
        messages.append("Score multiplier armed for the next 2 wins.")
    elif powerup_id == "double_or_nothing":
        rs.double_or_nothing_pending = 1
        messages.append("Double or Nothing armed for the next level.")
    elif powerup_id == "streak_bank":
        choice = (payload.choice or "").strip().lower()
        streak = max(0, int(payload.streak or 0))
        if choice not in ("time", "score"):
            raise HTTPException(status_code=400, detail="Streak Bank requires choice: time or score.")
        if choice == "time":
            time_bonus_seconds = streak * STREAK_BANK_TIME_PER_STREAK
            if time_bonus_seconds:
                messages.append(f"Streak banked: +{time_bonus_seconds} seconds.")
            else:
                messages.append("No streak to bank yet.")
        else:
            score_bonus = streak * STREAK_BANK_SCORE_PER_STREAK
            rs.score += score_bonus
            if score_bonus:
                messages.append(f"Streak banked: +{score_bonus} score.")
            else:
                messages.append("No streak to bank yet.")

    if chosen and chosen.get("type") == "hint":
        hint_type = chosen.get("value") or "definition"
        if hint_type == "definition_or_usage":
            hint_type = "definition"
        hint = generate_hint(rs.secret, hint_type, THEMES_BY_ID.get(rs.theme_id))
    if chosen and chosen.get("type") == "reveal" and reveal_message is None:
        reveal_letter, reveal_message = _reveal_for_mode(rs.secret, chosen.get("value"))
    if chosen and chosen.get("type") == "time" and time_bonus_seconds is None:
        time_bonus_seconds = chosen.get("value")
        if time_bonus_seconds:
            messages.append(f"+{time_bonus_seconds} seconds.")
    return {
        "state": run_state_to_dict(rs),
        "used": chosen,
        "messages": messages,
        "hint": hint,
        "reveal_letter": reveal_letter,
        "reveal_message": reveal_message,
        "time_bonus_seconds": time_bonus_seconds,
        "time_penalty_seconds": time_penalty_seconds,
        "timer_freeze_seconds": timer_freeze_seconds,
        "timer_slow_seconds": timer_slow_seconds,
    }


@app.post("/api/run/{run_id}/consume_clutch")
def consume_clutch(run_id: str):
    try:
        rs = gm.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    if rs.clutch_shield > 0:
        rs.clutch_shield -= 1
    return {"state": run_state_to_dict(rs)}


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
    hint = generate_hint(rs.secret, payload.hint_type or "context", THEMES_BY_ID.get(rs.theme_id))
    return {"hint": hint}


@app.get("/api/validation", include_in_schema=False)
def validation_status():
    return {
        "gemini_available": bool(gemini_client),
        "min_confidence": GEMINI_MIN_CONFIDENCE,
        "lenient": LENIENT_WORD_VALIDATION,
    }


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
