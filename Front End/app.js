
// Global run timer (client-side MVP)
let timeRemaining = 300; // 5 minutes
let timerOn = false;
let timerInterval = null;

function startTimer() {
  if (timerInterval) clearInterval(timerInterval);
  timerOn = true;
  timerInterval = setInterval(() => {
    if (!timerOn) return;
    timeRemaining -= 1;
    document.getElementById("time").textContent = timeRemaining;
    if (timeRemaining <= 0) {
      timerOn = false;
      alert("Game Over: Time's up!");
    }
  }, 1000);
}

function pauseTimer() { timerOn = false; }
function resumeTimer() { if (timeRemaining > 0) timerOn = true; }

async function api(path, body = null) {
  const res = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: body ? JSON.stringify(body) : null
  });
  return await res.json();
}

function renderGrid() {
  const grid = document.getElementById("grid");
  grid.innerHTML = "";

  // show past guesses
  for (let r = 0; r < state.feedback.length; r++) {
    const row = document.createElement("div");
    row.className = "row";
    const guess = state.guesses[r];
    const fb = state.feedback[r];
    for (let c = 0; c < state.word_len; c++) {
      const tile = document.createElement("div");
      tile.className = "tile " + fb[c];
      tile.textContent = guess[c];
      row.appendChild(tile);
    }
    grid.appendChild(row);
  }

  // show empty rows
  for (let r = state.feedback.length; r < state.max_guesses; r++) {
    const row = document.createElement("div");
    row.className = "row";
    for (let c = 0; c < state.word_len; c++) {
      const tile = document.createElement("div");
      tile.className = "tile";
      tile.textContent = "";
      row.appendChild(tile);
    }
    grid.appendChild(row);
  }

  // skip UI
  const skipBtn = document.getElementById("skipBtn");
  const skipInfo = document.getElementById("skipInfo");
  skipBtn.disabled = !state.skip_available;
  skipInfo.textContent = state.skip_available ? "Skip available" : `Skip in ${state.skip_in_levels} level(s)`;

  // powerups UI
  const powerupsDiv = document.getElementById("powerups");
  if (state.pending_powerups && state.pending_powerups.length > 0) {
    powerupsDiv.classList.remove("hidden");
    powerupsDiv.innerHTML = "<h3>Choose 1 power-up</h3>";
    pauseTimer();

    state.pending_powerups.forEach(p => {
      const btn = document.createElement("button");
      btn.textContent = `${p.name} — ${p.desc}`;
      btn.onclick = () => choosePowerup(p.id);
      powerupsDiv.appendChild(btn);
      powerupsDiv.appendChild(document.createElement("br"));
    });
  } else {
    powerupsDiv.classList.add("hidden");
    powerupsDiv.innerHTML = "";
    resumeTimer();
  }
}

async function startRun() {
  state = await api("/api/run/start");
  renderGrid();
  document.getElementById("time").textContent = timeRemaining;
  startTimer();
}

async function submitGuess() {
  if (!state || timeRemaining <= 0) return;
  const guess = document.getElementById("guessInput").value.trim();
  document.getElementById("guessInput").value = "";

  state = await api(`/api/run/${state.run_id}/guess`, {guess});
  renderGrid();
}

async function doSkip() {
  if (!state || timeRemaining <= 0) return;
  state = await api(`/api/run/${state.run_id}/skip`);
  renderGrid();
}

async function choosePowerup(powerupId) {
  const out = await api(`/api/run/${state.run_id}/choose_powerup`, {powerup_id: powerupId});
  const chosen = out.chosen;
  state = out.state;

  // Apply powerup effects on the client (MVP)
  if (chosen.type === "time") {
    timeRemaining += chosen.value;
  } else if (chosen.type === "reveal") {
    alert("Next word first letter revealed: (you can implement showing this on UI)");
  } else if (chosen.type === "hint") {
    // Ask server to generate hint with Gemini (uses next word on server, but we don't expose it)
    // For MVP: ask for a hint about the *current* word only when needed.
    // To keep it simple, you can add a "Hint" button later.
    alert("Gemini hint power-up chosen. Add a Hint button next!");
  }

  renderGrid();
}

document.getElementById("guessBtn").onclick = submitGuess;
document.getElementById("skipBtn").onclick = doSkip;

startRun();
