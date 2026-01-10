const state = {
  runId: null,
  wordLen: 5,
  maxGuesses: 6,
  pendingPowerups: [],
  remainingSeconds: 300,
  timerId: null,
  gameOver: false,
  lastLevel: null,
};

const els = {
  level: document.getElementById('level'),
  timer: document.getElementById('timer'),
  hint: document.getElementById('hint'),
  guessCount: document.getElementById('guess-count'),
  guessMax: document.getElementById('guess-max'),
  message: document.getElementById('message'),
  board: document.getElementById('board'),
  powerups: document.getElementById('powerups'),
  guessForm: document.getElementById('guess-form'),
  guessInput: document.getElementById('guess-input'),
  guessSubmit: document.querySelector('#guess-form button'),
  startBtn: document.getElementById('start-btn'),
  skipBtn: document.getElementById('skip-btn'),
};

if (!els.timer) {
  const status = document.querySelector('.status');
  if (status) {
    const block = document.createElement('div');
    const label = document.createElement('span');
    const value = document.createElement('span');
    label.className = 'label';
    label.textContent = 'Timer';
    value.id = 'timer';
    value.textContent = '00:00';
    block.appendChild(label);
    block.appendChild(value);
    status.appendChild(block);
    els.timer = value;
  }
}

function setMessage(text) {
  if (els.message) {
    els.message.textContent = text;
  }
}

function setHint(text) {
  if (els.hint) {
    els.hint.textContent = text;
  }
}

function formatTime(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function startTimer() {
  if (state.timerId) {
    return;
  }
  state.timerId = setInterval(() => {
    if (state.gameOver) {
      return;
    }
    state.remainingSeconds = Math.max(0, state.remainingSeconds - 1);
    if (els.timer) {
      els.timer.textContent = formatTime(state.remainingSeconds);
    }
    if (state.remainingSeconds <= 0) {
      state.gameOver = true;
      stopTimer();
      renderGameOver();
    }
  }, 1000);
}

function stopTimer() {
  if (state.timerId) {
    clearInterval(state.timerId);
    state.timerId = null;
  }
}

function resetTimer() {
  stopTimer();
  state.remainingSeconds = 300;
  if (els.timer) {
    els.timer.textContent = formatTime(state.remainingSeconds);
  }
}

async function api(path, options) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json();
}

function updateState(next) {
  state.runId = next.run_id;
  state.wordLen = next.word_len;
  state.maxGuesses = next.max_guesses;
  state.pendingPowerups = next.pending_powerups || [];
  if (state.lastLevel !== null && next.level !== state.lastLevel) {
    setHint('');
  }
  state.lastLevel = next.level;
  render(next);
}

function renderGameOver() {
  setMessage("Time's up. Game over. Press Start to restart.");
  if (els.guessInput) {
    els.guessInput.disabled = true;
  }
  if (els.guessSubmit) {
    els.guessSubmit.disabled = true;
  }
  if (els.skipBtn) {
    els.skipBtn.disabled = true;
  }
}

function render(run) {
  if (state.gameOver) {
    renderGameOver();
    return;
  }
  if (els.level) {
    els.level.textContent = run.level;
  }
  if (els.guessCount) {
    els.guessCount.textContent = run.guesses.length;
  }
  if (els.guessMax) {
    els.guessMax.textContent = run.max_guesses;
  }
  if (els.guessInput) {
    els.guessInput.maxLength = run.word_len;
  }
  if (els.startBtn) {
    els.startBtn.textContent = run.run_id ? 'Restart Run' : 'Start';
  }

  const waitingOnPowerup = Boolean(run.pending_powerups && run.pending_powerups.length);
  if (els.guessInput) {
    els.guessInput.disabled = waitingOnPowerup;
  }
  if (els.guessSubmit) {
    els.guessSubmit.disabled = waitingOnPowerup;
  }
  if (els.skipBtn) {
    els.skipBtn.disabled = waitingOnPowerup || !run.skip_available;
  }
  if (waitingOnPowerup) {
    stopTimer();
  } else if (state.runId) {
    startTimer();
  }

  if (run.won) {
    setMessage('Nice! Pick a powerup to continue.');
  } else if (run.failed) {
    setMessage('Out of guesses. New level started.');
  } else {
    setMessage('Enter a word and submit.');
  }

  renderBoard(run);
  renderPowerups(run);
}

function renderBoard(run) {
  els.board.innerHTML = '';
  run.guesses.forEach((guess, idx) => {
    const row = document.createElement('div');
    row.className = 'row';
    const feedback = run.feedback[idx] || [];
    for (let i = 0; i < run.word_len; i += 1) {
      const tile = document.createElement('div');
      tile.className = `tile ${feedback[i] || ''}`.trim();
      tile.textContent = guess[i] || '';
      row.appendChild(tile);
    }
    els.board.appendChild(row);
  });
}

function renderPowerups(run) {
  els.powerups.innerHTML = '';
  if (!run.pending_powerups || run.pending_powerups.length === 0) {
    return;
  }
  run.pending_powerups.forEach((power) => {
    const card = document.createElement('div');
    card.className = 'powerup-card';
    card.innerHTML = `
      <strong>${power.name}</strong>
      <span>${power.desc}</span>
    `;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Choose';
    button.addEventListener('click', () => choosePowerup(power.id));
    card.appendChild(button);
    els.powerups.appendChild(card);
  });
}

async function startRun() {
  resetTimer();
  setHint('');
  state.gameOver = false;
  const data = await api('/api/run/start', { method: 'POST' });
  updateState(data);
}

async function submitGuess(guess) {
  if (!state.runId || state.gameOver) {
    return;
  }
  const data = await api(`/api/run/${state.runId}/guess`, {
    method: 'POST',
    body: JSON.stringify({ guess }),
  });
  updateState(data);
}

async function skipLevel() {
  if (!state.runId || state.gameOver) {
    return;
  }
  const data = await api(`/api/run/${state.runId}/skip`, {
    method: 'POST' },
  );
  updateState(data);
}

async function choosePowerup(powerupId) {
  if (!state.runId || state.gameOver) {
    return;
  }
  const data = await api(`/api/run/${state.runId}/choose_powerup`, {
    method: 'POST',
    body: JSON.stringify({ powerup_id: powerupId }),
  });
  updateState(data.state);
  if (data.hint) {
    setHint(`Hint: ${data.hint}`);
  }
  if (data.reveal_letter) {
    setHint(`First letter: ${data.reveal_letter}`);
  }
  if (data.time_bonus_seconds) {
    state.remainingSeconds += Number(data.time_bonus_seconds) || 0;
    if (els.timer) {
      els.timer.textContent = formatTime(state.remainingSeconds);
    }
  }
}

els.guessForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const guess = els.guessInput.value.trim().toUpperCase();
  if (guess.length !== state.wordLen) {
    setMessage(`Guess must be ${state.wordLen} letters.`);
    return;
  }
  els.guessInput.value = '';
  submitGuess(guess).catch((err) => setMessage(err.message));
});

els.startBtn.addEventListener('click', () => {
  if (state.runId) {
    const confirmed = window.confirm('Restart the run from level 1?');
    if (!confirmed) {
      return;
    }
  }
  startRun().catch((err) => setMessage(err.message));
});

els.skipBtn.addEventListener('click', () => {
  skipLevel().catch((err) => setMessage(err.message));
});

resetTimer();
setHint('');
setMessage('Press Start to begin.');
