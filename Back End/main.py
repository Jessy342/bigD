# backend/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google import genai

from game import GameManager, load_words, DEFAULT_WORD_LEN, DEFAULT_MAX_GUESSES

app = FastAPI(AIzaSyAS-aSNkZnuAqwVEc5IE5tZ3gVo2_n9ctM)

# Allow the browser frontend to call the backend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WORDS = load_words("backend/words.txt")
gm = GameManager(WORDS)

# Gemini client reads GEMINI_API_KEY from environment variable
# (official quickstart shows this pattern) :contentReference[oaicite:3]{index=3}
gemini_client = genai.Client(AIzaSyAS-aSNkZnuAqwVEc5IE5tZ3gVo2_n9ctM)

class GuessIn(BaseModel):
    guess: str

class PowerupChoiceIn(BaseModel):
    powerup_id: str

class HintIn(BaseModel):
    word: str
    hint_type: str = "definition"  # could be: definition, category, context

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
    }

@app.post("/api/run/start")
def start_run():
    rs = gm.start_run()
    return run_state_to_dict(rs)

@app.post("/api/run/{run_id}/guess")
def submit_guess(run_id: str, payload: GuessIn):
    rs = gm.submit_guess(run_id, payload.guess)
    return run_state_to_dict(rs)

@app.post("/api/run/{run_id}/skip")
def skip_level(run_id: str):
    rs = gm.skip_level(run_id)
    return run_state_to_dict(rs)

@app.post("/api/run/{run_id}/choose_powerup")
def choose_powerup(run_id: str, payload: PowerupChoiceIn):
    rs, chosen = gm.choose_powerup(run_id, payload.powerup_id)
    return {"state": run_state_to_dict(rs), "chosen": chosen}

@app.post("/api/hint")
def get_hint(payload: HintIn):
    word = payload.word.strip().upper()
    hint_type = payload.hint_type

    prompt = (
        "You are generating hints for a Wordle-style game.\n"
        f"Target word: {word}\n"
        f"Hint style: {hint_type}\n"
        "Rules:\n"
        "- Do NOT say the target word.\n"
        "- Do NOT reveal letters or positions.\n"
        "- Do NOT give an anagram.\n"
        "- Keep it to ONE short sentence.\n"
        "Return only the hint."
    )

    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    hint = (response.text or "").strip()

    # Simple spoiler guard
    if word in hint.upper():
        hint = "It’s a common English word. Try thinking of everyday usage."

    return {"hint": hint}

# Serve frontend files
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
