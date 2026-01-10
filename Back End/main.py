
import os
from fastapi import FastAPI
from google import genai

app = FastAPI()

gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Tuple
import random
import uuid
from pathlib import Path
from starlette.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent              # ...\bigD\Back End
FRONTEND_DIR = (BASE_DIR / ".." / "Front end").resolve()  # ...\bigD\Front end

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


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

   
    for ch in secret:
        secret_counts[ch] = secret_counts.get(ch, 0) + 1

   
    for i, ch in enumerate(guess):
        if ch == secret[i]:
            result[i] = "correct"
            secret_counts[ch] -= 1

    
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

    
    last_skip_level: int = -999
    skip_cooldown_levels: int = DEFAULT_SKIP_COOLDOWN_LEVELS

    
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
            
            return rs

        if rs.won or rs.failed:
            
            return rs

        if len(guess) != DEFAULT_WORD_LEN or not guess.isalpha():
            return rs

        rs.guesses.append(guess)
        rs.feedback.append(evaluate_guess(rs.secret, guess))

        
        if rs.won:
            rs.pending_powerups = self._roll_powerups()

        
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

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google import genai

from game import GameManager, load_words, DEFAULT_WORD_LEN, DEFAULT_MAX_GUESSES

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WORDS = load_words("words.txt")
gm = GameManager(WORDS)


gemini_client = genai.Client()

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
app.mount("/", StaticFiles(directory="front end", html=True), name="front end")
