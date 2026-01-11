# backend/main.py
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
    DEFAULT_MAX_GUESSES,
    RARE_LETTERS,
    VOWELS,
)

app = FastAPI()

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

# Gemini client reads GEMINI_API_KEY from environment variable
gemini_client = None
if genai:
    try:
        gemini_client = genai.Client()
    except Exception:
        gemini_client = None

GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "4"))
_gemini_pool = ThreadPoolExecutor(max_workers=2)
_hint_cache = {}
_word_validation_cache = {}


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


class GuessIn(BaseModel):
    guess: str


class PowerupChoiceIn(BaseModel):
    powerup_id: str


class HintIn(BaseModel):
    word: str
    hint_type: str = "definition"  # could be: definition, usage, category, context


class RunHintIn(BaseModel):
    hint_type: str = "context"


def run_state_to_dict(rs):
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
        "max_guesses": DEFAULT_MAX_GUESSES,
        "score": rs.score,
        "last_score_delta": rs.last_score_delta,
        "difficulty": rs.difficulty,
        "boss_level": rs.boss_level,
    }


def generate_word(level: int, difficulty: str) -> str:
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


def generate_hint(word: str, hint_type: str) -> str:
    normalized = (hint_type or "context").strip().lower()
    cache_key = (word.strip().upper(), normalized)
    cached = _hint_cache.get(cache_key)
    if cached:
        return cached

    if normalized == "usage":
        if not gemini_client:
            hint = _fallback_usage(word)
            _hint_cache[cache_key] = hint
            return hint

        prompt = (
            "You are generating a usage example for a Wordle-style game.\n"
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

    if not gemini_client:
        hint = _fallback_hint(word)
        _hint_cache[cache_key] = hint
        return hint

    if normalized == "definition":
        prompt = (
            "You are a dictionary.\n"
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
        "Reply with ONLY YES or NO. Is this a valid English word?"
    )
    text = gemini_generate_text(prompt)
    if not text:
        return None
    normalized = text.strip().upper()
    result = None
    if normalized.startswith("YES"):
        result = True
    elif normalized.startswith("NO"):
        result = False
    else:
        has_yes = "YES" in normalized
        has_no = "NO" in normalized
        if has_yes and not has_no:
            result = True
        elif has_no and not has_yes:
            result = False
    if result is not None:
        _word_validation_cache[cleaned] = result
    return result


gm = GameManager(WORDS, word_provider=generate_word, easy_words=EASY_WORDS)


@app.post("/api/run/start")
def start_run():
    rs = gm.start_run()
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
    if gemini_client:
        gemini_result = gemini_validates_word(guess)
        if gemini_result is False:
            raise HTTPException(status_code=400, detail="Not in dictionary.")
        if gemini_result is True:
            if not gm.is_valid_guess(guess):
                gm.add_word(guess)
        elif not gm.is_valid_guess(guess):
            raise HTTPException(status_code=400, detail="Not in dictionary.")
    elif not gm.is_valid_guess(guess):
        raise HTTPException(status_code=400, detail="Not in dictionary.")

    rs = gm.submit_guess(run_id, guess)
    return run_state_to_dict(rs)


@app.post("/api/run/{run_id}/skip")
def skip_level(run_id: str):
    rs = gm.skip_level(run_id)
    return run_state_to_dict(rs)


@app.post("/api/run/{run_id}/choose_powerup")
def choose_powerup(run_id: str, payload: PowerupChoiceIn):
    rs, chosen = gm.choose_powerup(run_id, payload.powerup_id)
    hint = None
    reveal_letter = None
    time_bonus_seconds = None
    if chosen and chosen.get("type") == "hint":
        hint_type = chosen.get("value") or "definition"
        if hint_type == "definition_or_usage":
            hint_type = "definition"
        hint = generate_hint(rs.secret, hint_type)
    if chosen and chosen.get("type") == "reveal":
        reveal_letter = rs.secret[:1]
    if chosen and chosen.get("type") == "time":
        time_bonus_seconds = chosen.get("value")
    return {
        "state": run_state_to_dict(rs),
        "chosen": chosen,
        "hint": hint,
        "reveal_letter": reveal_letter,
        "time_bonus_seconds": time_bonus_seconds,
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
    hint = generate_hint(rs.secret, "context")
    return {"hint": hint}


# Serve frontend files if built assets are present
frontend_candidates = [
    (BASE_DIR / ".." / "Front End" / "dist").resolve(),
    (BASE_DIR / ".." / "Front End" / "build").resolve(),
]
frontend_dir = next((path for path in frontend_candidates if path.exists()), None)
if frontend_dir:
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
