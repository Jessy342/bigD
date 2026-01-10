import { useState, useEffect, useCallback, useMemo } from 'react';
import { GameGrid } from './GameGrid';
import { Keyboard } from './Keyboard';
import { GameModal } from './GameModal';
import { StartScreen } from './StartScreen';
import { Trophy, Gamepad2, RotateCcw, SkipForward, Timer, Hash, Lightbulb, Star } from 'lucide-react';
import { getKeyboardLetterStates, type LetterState } from '../utils/gameLogic';
import { toast } from 'sonner';

const DEFAULT_WORD_LENGTH = 5;
const DEFAULT_MAX_GUESSES = 6;
const RUN_TIME_SECONDS = 5 * 60;
const API_BASE = import.meta.env.VITE_API_BASE ?? '';

type Powerup = {
  id: string;
  type: 'time' | 'reveal' | 'hint';
  value: string | number;
  name: string;
  desc: string;
};

type RunState = {
  run_id: string;
  level: number;
  guesses: string[];
  feedback: Array<Array<LetterState>>;
  won: boolean;
  failed: boolean;
  pending_powerups: Powerup[];
  skip_available: boolean;
  skip_in_levels: number;
  word_len: number;
  max_guesses: number;
  score: number;
  last_score_delta: number;
  difficulty: string;
  boss_level: boolean;
};

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    let message = text || `Request failed: ${response.status}`;
    if (text) {
      try {
        const data = JSON.parse(text) as { detail?: string };
        if (data?.detail) {
          message = data.detail;
        }
      } catch {
        // keep original message
      }
    }
    const error = new Error(message) as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return response.json() as Promise<T>;
}

export function GameBoard() {
  const [gameStarted, setGameStarted] = useState(false);
  const [run, setRun] = useState<RunState | null>(null);
  const [currentGuess, setCurrentGuess] = useState('');
  const [gameStatus, setGameStatus] = useState<'playing' | 'lost'>('playing');
  const [totalGuesses, setTotalGuesses] = useState(0);
  const [remainingSeconds, setRemainingSeconds] = useState(RUN_TIME_SECONDS);
  const [isTabActive, setIsTabActive] = useState(true);
  const [hintOpen, setHintOpen] = useState(false);
  const [hintText, setHintText] = useState('');
  const [hintLoading, setHintLoading] = useState(false);
  const [stats, setStats] = useState({
    gamesPlayed: 0,
    gamesWon: 0,
    currentStreak: 0,
  });

  const wordLength = run?.word_len ?? DEFAULT_WORD_LENGTH;
  const maxGuesses = run?.max_guesses ?? DEFAULT_MAX_GUESSES;
  const guesses = run?.guesses ?? [];
  const evaluations = run?.feedback ?? [];
  const level = run?.level ?? 1;
  const pendingPowerups = run?.pending_powerups ?? [];
  const powerupPending = pendingPowerups.length > 0;
  const elapsedTime = RUN_TIME_SECONDS - remainingSeconds;
  const score = run?.score ?? 0;
  const difficulty = run?.difficulty ?? 'easy';
  const bossLevel = run?.boss_level ?? false;

  const letterStates = useMemo(
    () => getKeyboardLetterStates(guesses, evaluations),
    [guesses, evaluations],
  );

  useEffect(() => {
    const savedStats = localStorage.getItem('wordle-stats');
    if (savedStats) {
      setStats(JSON.parse(savedStats));
    }
  }, []);

  useEffect(() => {
    const handleVisibility = () => {
      setIsTabActive(!document.hidden);
    };
    handleVisibility();
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  useEffect(() => {
    if (!gameStarted || gameStatus !== 'playing' || powerupPending || remainingSeconds <= 0 || !isTabActive) {
      return;
    }
    const interval = setInterval(() => {
      setRemainingSeconds((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [gameStarted, gameStatus, powerupPending, remainingSeconds, isTabActive]);

  useEffect(() => {
    if (remainingSeconds > 0 || gameStatus === 'lost') {
      return;
    }
    setGameStatus('lost');
    const newStats = {
      gamesPlayed: stats.gamesPlayed + 1,
      gamesWon: stats.gamesWon,
      currentStreak: 0,
    };
    setStats(newStats);
    localStorage.setItem('wordle-stats', JSON.stringify(newStats));
    toast.error("Time's up! Run over.");
  }, [remainingSeconds, gameStatus, stats]);

  const startGame = useCallback(async () => {
    try {
      const data = await api<RunState>('/api/run/start', { method: 'POST' });
      setRun(data);
      setGameStarted(true);
      setGameStatus('playing');
      setCurrentGuess('');
      setTotalGuesses(0);
      setRemainingSeconds(RUN_TIME_SECONDS);
      setHintOpen(false);
      setHintText('');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to start run.');
    }
  }, []);

  const restartRun = useCallback(() => {
    setGameStarted(false);
    setRun(null);
    setCurrentGuess('');
    setGameStatus('playing');
    setTotalGuesses(0);
    setRemainingSeconds(RUN_TIME_SECONDS);
    setHintOpen(false);
    setHintText('');
  }, []);

  const handleRunError = useCallback(
    (error: unknown, fallbackMessage: string) => {
      const message = error instanceof Error ? error.message : fallbackMessage;
      const status = (error as { status?: number }).status;
      if (status === 404 || /run not found/i.test(message)) {
        toast.error('Run expired. Start a new run.');
        restartRun();
        return;
      }
      if (/failed to fetch|network/i.test(message)) {
        toast.error('Backend not reachable. Start the server on port 8000.');
        return;
      }
      toast.error(message);
    },
    [restartRun],
  );

  const skipLevel = useCallback(async () => {
    if (!run || powerupPending) {
      return;
    }
    const previousLevel = run.level;
    try {
      const data = await api<RunState>(`/api/run/${run.run_id}/skip`, { method: 'POST' });
      setRun(data);
      if (data.level === previousLevel) {
        toast.error('Skip not available yet.');
      } else {
        toast.info('Level skipped.');
      }
    } catch (error) {
      handleRunError(error, 'Failed to skip level.');
    }
  }, [run, powerupPending, handleRunError]);

  const choosePowerup = useCallback(
    async (powerupId: string) => {
      if (!run) {
        return;
      }
      try {
        const data = await api<{
          state: RunState;
          chosen: Powerup;
          hint: string | null;
          reveal_letter: string | null;
          time_bonus_seconds: number | null;
        }>(`/api/run/${run.run_id}/choose_powerup`, {
          method: 'POST',
          body: JSON.stringify({ powerup_id: powerupId }),
        });
        setRun(data.state);
        if (data.hint) {
          toast.success(data.hint, { duration: 5000 });
        }
        if (data.reveal_letter) {
          toast.success(`First letter: ${data.reveal_letter}`, { duration: 5000 });
        }
        if (data.time_bonus_seconds) {
          setRemainingSeconds((prev) => prev + Number(data.time_bonus_seconds));
          toast.info(`+${data.time_bonus_seconds} seconds`);
        }
      } catch (error) {
        handleRunError(error, 'Failed to choose powerup.');
      }
    },
    [run, handleRunError],
  );

  const requestHint = useCallback(async () => {
    if (!run || powerupPending || gameStatus !== 'playing') {
      return;
    }
    setHintLoading(true);
    try {
      const data = await api<{ hint: string }>(`/api/run/${run.run_id}/hint`, {
        method: 'POST',
        body: JSON.stringify({ hint_type: 'definition' }),
      });
      const hint = data.hint?.trim();
      setHintText(hint || 'Hint unavailable. Try again.');
      setHintOpen(true);
    } catch (error) {
      handleRunError(error, 'Failed to get hint.');
    } finally {
      setHintLoading(false);
    }
  }, [run, powerupPending, gameStatus, handleRunError]);

  const handleGuessSubmit = useCallback(async () => {
    if (!run || powerupPending || gameStatus !== 'playing') {
      return;
    }

    const guess = currentGuess.trim().toUpperCase();
    if (guess.length !== wordLength) {
      toast.error('Not enough letters!');
      return;
    }
    if (!/^[A-Z]+$/.test(guess)) {
      toast.error('Letters only!');
      return;
    }

    try {
      const prevGuessCount = run.guesses.length;
      const data = await api<RunState>(`/api/run/${run.run_id}/guess`, {
        method: 'POST',
        body: JSON.stringify({ guess }),
      });
      setRun(data);
      setCurrentGuess('');
      const delta = data.guesses.length - prevGuessCount;
      if (delta <= 0) {
        toast.error('Guess not accepted.');
        return;
      }
      setTotalGuesses((prev) => prev + delta);

      if (data.won && data.pending_powerups?.length) {
        const newStats = {
          gamesPlayed: stats.gamesPlayed + 1,
          gamesWon: stats.gamesWon + 1,
          currentStreak: stats.currentStreak + 1,
        };
        setStats(newStats);
        localStorage.setItem('wordle-stats', JSON.stringify(newStats));
        toast.success(`Level ${data.level} complete! Choose a powerup.`);
      }
    } catch (error) {
      setCurrentGuess('');
      handleRunError(error, 'Guess failed.');
    }
  }, [run, powerupPending, gameStatus, currentGuess, wordLength, stats, handleRunError]);

  const handleKeyPress = useCallback(
    (key: string) => {
      if (gameStatus !== 'playing' || powerupPending) {
        return;
      }

      if (key === 'ENTER') {
        handleGuessSubmit();
        return;
      }

      if (key === 'BACKSPACE') {
        setCurrentGuess((prev) => prev.slice(0, -1));
        return;
      }

      if (currentGuess.length < wordLength) {
        setCurrentGuess((prev) => prev + key);
      }
    },
    [gameStatus, powerupPending, handleGuessSubmit, currentGuess.length, wordLength],
  );

  useEffect(() => {
    const handlePhysicalKeyPress = (e: KeyboardEvent) => {
      if (!gameStarted || gameStatus !== 'playing' || powerupPending) {
        return;
      }

      if (e.key === 'Enter') {
        handleKeyPress('ENTER');
      } else if (e.key === 'Backspace') {
        handleKeyPress('BACKSPACE');
      } else if (/^[a-zA-Z]$/.test(e.key)) {
        handleKeyPress(e.key.toUpperCase());
      }
    };

    window.addEventListener('keydown', handlePhysicalKeyPress);
    return () => window.removeEventListener('keydown', handlePhysicalKeyPress);
  }, [handleKeyPress, gameStarted, gameStatus, powerupPending]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (!gameStarted) {
    return <StartScreen onStart={startGame} stats={stats} />;
  }

  return (
    <div className="flex flex-col items-center gap-8 p-4">
      <div className="w-full max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-primary rounded-lg flex items-center justify-center shadow-lg shadow-primary/50">
              <Gamepad2 className="w-7 h-7 text-white" />
            </div>
            <div>
              <h1 className="text-white">HACKATHON WORDLE</h1>
              <p className="text-sm text-gray-400">Guess the 5-letter word</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={requestHint}
              className="px-4 py-2 bg-purple-600/20 hover:bg-purple-600/30 rounded-lg border border-purple-600/50 transition-colors flex items-center gap-2"
              title="Get a hint"
              disabled={!run || powerupPending || gameStatus !== 'playing' || hintLoading}
            >
              <Lightbulb className="w-4 h-4 text-purple-500" />
              <span className="text-sm text-purple-500">{hintLoading ? 'Thinking...' : 'Hint'}</span>
            </button>

            <button
              onClick={skipLevel}
              className="px-4 py-2 bg-yellow-600/20 hover:bg-yellow-600/30 rounded-lg border border-yellow-600/50 transition-colors flex items-center gap-2"
              title="Skip Level"
              disabled={!run || powerupPending || !run.skip_available}
            >
              <SkipForward className="w-4 h-4 text-yellow-500" />
              <span className="text-sm text-yellow-500">Skip</span>
            </button>

            <button
              onClick={restartRun}
              className="px-4 py-2 bg-red-600/20 hover:bg-red-600/30 rounded-lg border border-red-600/50 transition-colors flex items-center gap-2"
              title="Restart Run"
            >
              <RotateCcw className="w-4 h-4 text-red-500" />
              <span className="text-sm text-red-500">Restart</span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="bg-card/50 rounded-lg p-3 border border-primary/30 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <Trophy className="w-4 h-4 text-primary" />
              <span className="text-white">Lv {level}</span>
            </div>
            <p className="text-xs text-gray-400">Level</p>
          </div>

          <div className="bg-card/50 rounded-lg p-3 border border-primary/30 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <Timer className="w-4 h-4 text-green-500" />
              <span className="text-white">{formatTime(remainingSeconds)}</span>
            </div>
            <p className="text-xs text-gray-400">Time</p>
          </div>

          <div className="bg-card/50 rounded-lg p-3 border border-primary/30 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <Hash className="w-4 h-4 text-blue-500" />
              <span className="text-white">{totalGuesses}</span>
            </div>
            <p className="text-xs text-gray-400">Total</p>
          </div>

          <div className="bg-card/50 rounded-lg p-3 border border-primary/30 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <Hash className="w-4 h-4 text-orange-500" />
              <span className="text-white">{guesses.length}/{maxGuesses}</span>
            </div>
            <p className="text-xs text-gray-400">Guesses</p>
          </div>

          <div className="bg-card/50 rounded-lg p-3 border border-primary/30 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <Star className="w-4 h-4 text-green-500" />
              <span className="text-white">{score}</span>
            </div>
            <p className="text-xs text-gray-400">Score</p>
          </div>

          <div className="bg-card/50 rounded-lg p-3 border border-primary/30 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <Trophy className={`w-4 h-4 ${bossLevel ? 'text-red-500' : 'text-primary'}`} />
              <span className="text-white">{bossLevel ? 'Boss' : difficulty}</span>
            </div>
            <p className="text-xs text-gray-400">Difficulty</p>
          </div>
        </div>

        <div>
          <GameGrid
            guesses={guesses}
            currentGuess={currentGuess}
            evaluations={evaluations}
            maxGuesses={maxGuesses}
            wordLength={wordLength}
          />
        </div>
      </div>

      <Keyboard
        onKeyPress={handleKeyPress}
        letterStates={letterStates}
        disabled={gameStatus !== 'playing' || powerupPending}
      />

      {powerupPending && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gradient-to-br from-[#1a1f3a] to-[#0a0e27] border-2 border-primary/50 rounded-2xl p-8 max-w-md w-full shadow-2xl shadow-primary/20">
            <div className="text-center mb-6">
              <h2 className="text-white mb-2">Choose a Powerup</h2>
              <p className="text-gray-400 text-sm">Pick one reward to continue.</p>
            </div>
            <div className="space-y-3">
              {pendingPowerups.map((powerup) => (
                <button
                  key={powerup.id}
                  onClick={() => choosePowerup(powerup.id)}
                  className="w-full text-left bg-card/50 hover:bg-card/70 border border-primary/30 rounded-xl p-4 transition-colors"
                >
                  <div className="text-white mb-1">{powerup.name}</div>
                  <div className="text-xs text-gray-400">{powerup.desc}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <GameModal
        isOpen={gameStatus === 'lost'}
        gameStatus={gameStatus}
        answer="?????"
        guesses={guesses.length}
        level={level}
        totalGuesses={totalGuesses}
        elapsedTime={elapsedTime}
        stats={stats}
        onPlayAgain={restartRun}
      />

      {hintOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gradient-to-br from-[#1a1f3a] to-[#0a0e27] border-2 border-primary/50 rounded-2xl p-8 max-w-md w-full shadow-2xl shadow-primary/20">
            <div className="text-center mb-4">
              <h2 className="text-white mb-2">Hint</h2>
              <p className="text-gray-400 text-sm">A clue for the current word.</p>
            </div>
            <div className="bg-card/50 rounded-lg p-4 border border-primary/30 text-white text-center">
              {hintText}
            </div>
            <button
              onClick={() => setHintOpen(false)}
              className="w-full mt-3 bg-gradient-to-r from-primary to-indigo-600 hover:from-primary/90 hover:to-indigo-600/90 text-white py-3 rounded-lg transition-all active:scale-95 shadow-lg shadow-primary/30"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
