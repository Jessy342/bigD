import { useState, useEffect, useCallback, useMemo, type CSSProperties } from 'react';
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
  instance_id?: string;
  type: string;
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
  inventory: Powerup[];
  clutch_shield: number;
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
  const [timerFreezeSeconds, setTimerFreezeSeconds] = useState(0);
  const [timerSlowSeconds, setTimerSlowSeconds] = useState(0);
  const [streakBankOpen, setStreakBankOpen] = useState(false);
  const [pendingStreakBankId, setPendingStreakBankId] = useState<string | null>(null);
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
  const inventory = run?.inventory ?? [];
  const elapsedTime = Math.max(0, RUN_TIME_SECONDS - remainingSeconds);
  const score = run?.score ?? 0;
  const difficulty = run?.difficulty ?? 'easy';
  const bossLevel = run?.boss_level ?? false;
  const clutchShield = run?.clutch_shield ?? 0;
  const timeRatio = Math.max(0, Math.min(1, remainingSeconds / RUN_TIME_SECONDS));
  const urgency = Math.max(0, Math.min(1, (0.35 - timeRatio) / 0.35));
  const timerHue = Math.round(210 - 210 * urgency);
  const timerStyle = useMemo(
    () =>
      ({
        ['--timer-progress' as const]: timeRatio,
        ['--timer-hue' as const]: timerHue,
        ['--timer-urgency' as const]: urgency,
      }) as CSSProperties,
    [timeRatio, timerHue, urgency],
  );

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
      setTimerFreezeSeconds((prev) => (prev > 0 ? prev - 1 : prev));
      setTimerSlowSeconds((prev) => (prev > 0 ? prev - 1 : prev));
      setRemainingSeconds((prev) => {
        if (timerFreezeSeconds > 0) {
          return prev;
        }
        const drain = timerSlowSeconds > 0 ? 0.5 : 1;
        return Math.max(0, prev - drain);
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [
    gameStarted,
    gameStatus,
    powerupPending,
    remainingSeconds,
    isTabActive,
    timerFreezeSeconds,
    timerSlowSeconds,
  ]);

  useEffect(() => {
    if (!run || !run.failed || gameStatus === 'lost') {
      return;
    }
    setGameStatus('lost');
    setStats((prev) => {
      const next = {
        gamesPlayed: prev.gamesPlayed + 1,
        gamesWon: prev.gamesWon,
        currentStreak: 0,
      };
      localStorage.setItem('wordle-stats', JSON.stringify(next));
      return next;
    });
    toast.error('No guesses left. Run over.');
  }, [run, gameStatus]);

  useEffect(() => {
    if (!run) {
      return;
    }
    setHintOpen(false);
    setHintText('');
    setHintLoading(false);
    setStreakBankOpen(false);
    setPendingStreakBankId(null);
  }, [run?.level]);

  const startGame = useCallback(async () => {
    try {
      const data = await api<RunState>('/api/run/start', { method: 'POST' });
      setRun(data);
      setGameStarted(true);
      setGameStatus('playing');
      setCurrentGuess('');
      setTotalGuesses(0);
      setRemainingSeconds(RUN_TIME_SECONDS);
      setTimerFreezeSeconds(0);
      setTimerSlowSeconds(0);
      setHintOpen(false);
      setHintText('');
      setStreakBankOpen(false);
      setPendingStreakBankId(null);
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
    setTimerFreezeSeconds(0);
    setTimerSlowSeconds(0);
    setHintOpen(false);
    setHintText('');
    setStreakBankOpen(false);
    setPendingStreakBankId(null);
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

  const pushMessages = useCallback((messages?: string[]) => {
    if (!messages?.length) {
      return;
    }
    messages.forEach((message) => {
      const cleaned = message?.trim();
      if (cleaned) {
        toast.info(cleaned, { duration: 5000 });
      }
    });
  }, []);

  const consumeClutchShield = useCallback(async () => {
    if (!run) {
      return;
    }
    try {
      const data = await api<{ state: RunState }>(`/api/run/${run.run_id}/consume_clutch`, {
        method: 'POST',
      });
      setRun(data.state);
    } catch (error) {
      handleRunError(error, 'Failed to consume clutch shield.');
    }
  }, [run, handleRunError]);

  useEffect(() => {
    if (remainingSeconds > 0 || gameStatus === 'lost') {
      return;
    }
    if (clutchShield > 0) {
      setRemainingSeconds(5);
      setTimerFreezeSeconds(0);
      setTimerSlowSeconds(0);
      consumeClutchShield();
      toast.info('Clutch Shield activated. +5 seconds.');
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
  }, [remainingSeconds, gameStatus, stats, clutchShield, consumeClutchShield]);

  const skipLevel = useCallback(async () => {
    if (!run || powerupPending || gameStatus !== 'playing') {
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
  }, [run, powerupPending, gameStatus, handleRunError]);

  const choosePowerup = useCallback(
    async (powerupId: string) => {
      if (!run) {
        return;
      }
      try {
        const data = await api<{
          state: RunState;
          added: Powerup | null;
        }>(`/api/run/${run.run_id}/choose_powerup`, {
          method: 'POST',
          body: JSON.stringify({ powerup_id: powerupId }),
        });
        setRun(data.state);
        if (data.added) {
          toast.success(`Added to inventory: ${data.added.name}`, { duration: 4000 });
        } else {
          toast.error('Powerup not added.');
        }
      } catch (error) {
        handleRunError(error, 'Failed to choose powerup.');
      }
    },
    [run, handleRunError],
  );

  const useInventoryPowerup = useCallback(
    async (inventoryId: string, options?: { choice?: string; streak?: number }) => {
      if (!run || powerupPending || gameStatus !== 'playing') {
        return;
      }
      try {
        const data = await api<{
          state: RunState;
          used: Powerup | null;
          messages?: string[];
          hint: string | null;
          reveal_letter: string | null;
          reveal_message: string | null;
          time_bonus_seconds: number | null;
          time_penalty_seconds: number | null;
          timer_freeze_seconds: number | null;
          timer_slow_seconds: number | null;
        }>(`/api/run/${run.run_id}/use_powerup`, {
          method: 'POST',
          body: JSON.stringify({
            inventory_id: inventoryId,
            choice: options?.choice,
            streak: options?.streak,
          }),
        });
        setRun(data.state);
        if (!data.used) {
          toast.error('Powerup not available.');
          return;
        }
        if (data.used.id === 'streak_bank' && options?.streak) {
          const nextStats = { ...stats, currentStreak: 0 };
          setStats(nextStats);
          localStorage.setItem('wordle-stats', JSON.stringify(nextStats));
        }
        pushMessages(data.messages);
        if (data.hint) {
          toast.success(data.hint, { duration: 5000 });
        }
        if (data.reveal_message) {
          toast.success(data.reveal_message, { duration: 5000 });
        } else if (data.reveal_letter) {
          toast.success(`Revealed letter: ${data.reveal_letter}`, { duration: 5000 });
        }
        if (data.time_bonus_seconds) {
          setRemainingSeconds((prev) => prev + Number(data.time_bonus_seconds));
          toast.info(`+${data.time_bonus_seconds} seconds`);
        }
        if (data.time_penalty_seconds) {
          setRemainingSeconds((prev) => Math.max(0, prev - Number(data.time_penalty_seconds)));
          toast.error(`-${data.time_penalty_seconds} seconds`);
        }
        if (data.timer_freeze_seconds) {
          setTimerFreezeSeconds((prev) => prev + Number(data.timer_freeze_seconds));
        }
        if (data.timer_slow_seconds) {
          setTimerSlowSeconds((prev) => prev + Number(data.timer_slow_seconds));
        }
      } catch (error) {
        handleRunError(error, 'Failed to use powerup.');
      }
    },
    [run, powerupPending, gameStatus, handleRunError, pushMessages, stats],
  );

  const requestHint = useCallback(async () => {
    if (!run || powerupPending || gameStatus !== 'playing') {
      return;
    }
    setHintLoading(true);
    try {
      const data = await api<{ hint: string }>(`/api/run/${run.run_id}/hint`, {
        method: 'POST',
        body: JSON.stringify({ hint_type: 'context' }),
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
      const data = await api<
        RunState & {
          effect_messages?: string[];
          time_bonus_seconds?: number;
          time_penalty_seconds?: number;
        }
      >(`/api/run/${run.run_id}/guess`, {
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
      if (data.time_bonus_seconds) {
        setRemainingSeconds((prev) => prev + Number(data.time_bonus_seconds));
        toast.info(`+${data.time_bonus_seconds} seconds`);
      }
      if (data.time_penalty_seconds) {
        setRemainingSeconds((prev) => Math.max(0, prev - Number(data.time_penalty_seconds)));
        toast.error(`-${data.time_penalty_seconds} seconds`);
      }
      pushMessages(data.effect_messages);
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
  }, [run, powerupPending, gameStatus, currentGuess, wordLength, stats, handleRunError, pushMessages]);

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

  const handleStreakBankChoice = useCallback(
    (choice: 'time' | 'score') => {
      if (!pendingStreakBankId) {
        setStreakBankOpen(false);
        return;
      }
      if (stats.currentStreak <= 0) {
        toast.error('No streak to bank yet.');
        setStreakBankOpen(false);
        setPendingStreakBankId(null);
        return;
      }
      useInventoryPowerup(pendingStreakBankId, { choice, streak: stats.currentStreak });
      setStreakBankOpen(false);
      setPendingStreakBankId(null);
    },
    [pendingStreakBankId, stats.currentStreak, useInventoryPowerup],
  );

  const formatTime = (seconds: number) => {
    const safeSeconds = Math.max(0, Math.ceil(seconds));
    const mins = Math.floor(safeSeconds / 60);
    const secs = safeSeconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (!gameStarted) {
    return <StartScreen onStart={startGame} stats={stats} />;
  }

  return (
    <div className="game-shell" style={timerStyle}>
      <div className="game-main">
        <div className="game-panel">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-primary rounded-lg flex items-center justify-center shadow-lg shadow-primary/50">
                <Gamepad2 className="w-7 h-7 text-white" />
              </div>
              <div>
                <h1 className="text-white">ROUGLE</h1>
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
                disabled={!run || powerupPending || gameStatus !== 'playing' || !run.skip_available}
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

          <div className="flex flex-wrap justify-center gap-3 mb-6">
            <div className="flex-1 min-w-[180px] max-w-[210px] bg-card/50 rounded-lg p-3 border border-primary/30 text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <Trophy className="w-4 h-4 text-primary" />
                <span className="text-white">Lv {level}</span>
              </div>
              <p className="text-xs text-gray-400">Level</p>
            </div>

            <div className="flex-1 min-w-[180px] max-w-[210px] bg-card/50 rounded-lg p-3 border border-primary/30 text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <Hash className="w-4 h-4 text-orange-500" />
                <span className="text-white">{guesses.length}/{maxGuesses}</span>
              </div>
              <p className="text-xs text-gray-400">Guesses</p>
            </div>

            <div className="flex-1 min-w-[180px] max-w-[210px] bg-card/50 rounded-lg p-3 border border-primary/30 text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <Star className="w-4 h-4 text-green-500" />
                <span className="text-white">{score}</span>
              </div>
              <p className="text-xs text-gray-400">Score</p>
            </div>

            <div className="flex-1 min-w-[180px] max-w-[210px] bg-card/50 rounded-lg p-3 border border-primary/30 text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <Trophy className={`w-4 h-4 ${bossLevel ? 'text-red-500' : 'text-primary'}`} />
                <span className="text-white">{bossLevel ? 'Boss' : difficulty}</span>
              </div>
              <p className="text-xs text-gray-400">Difficulty</p>
            </div>
          </div>

          <div className="inventory-panel">
            <div className="inventory-header">
              <span className="inventory-title">Inventory</span>
              <span className="inventory-count">{inventory.length} item{inventory.length === 1 ? '' : 's'}</span>
            </div>
            {inventory.length ? (
              <div className="inventory-list">
                {inventory.map((powerup, index) => {
                  const inventoryId = powerup.instance_id ?? powerup.id;
                  const inventoryKey = powerup.instance_id ?? `${powerup.id}-${index}`;
                  const isStreakBank = powerup.id === 'streak_bank';
                  return (
                    <div key={inventoryKey} className="inventory-card">
                      <div className="inventory-text">
                        <div className="inventory-name">{powerup.name}</div>
                        <div className="inventory-desc">{powerup.desc}</div>
                      </div>
                      <button
                        className="inventory-use"
                        onClick={() => {
                          if (isStreakBank) {
                            setPendingStreakBankId(inventoryId);
                            setStreakBankOpen(true);
                            return;
                          }
                          useInventoryPowerup(inventoryId);
                        }}
                        disabled={!run || powerupPending || gameStatus !== 'playing'}
                      >
                        {isStreakBank ? 'Bank' : 'Use'}
                      </button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="inventory-empty">No powerups yet. Win a level to earn one.</div>
            )}
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

        <div className="game-panel game-keyboard">
          <Keyboard
            onKeyPress={handleKeyPress}
            letterStates={letterStates}
            disabled={gameStatus !== 'playing' || powerupPending}
          />
        </div>
      </div>

      <aside className="timer-pane" aria-live="polite">
        <div className="timer-label">
          <Timer className="timer-icon" />
          <span>Time</span>
        </div>
        <div className="timer-rail">
          <div className="timer-fill" />
        </div>
        <div className="timer-count">{formatTime(remainingSeconds)}</div>
      </aside>

      {powerupPending && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gradient-to-br from-[#1a1f3a] to-[#0a0e27] border-2 border-primary/50 rounded-2xl p-8 max-w-md w-full shadow-2xl shadow-primary/20">
            <div className="text-center mb-6">
              <h2 className="text-white mb-2">Choose a Powerup</h2>
              <p className="text-gray-400 text-sm">Pick one reward to continue.</p>
            </div>
            <div className="powerup-grid">
              {pendingPowerups.map((powerup, index) => (
                <button
                  key={powerup.instance_id ?? powerup.id}
                  onClick={() => choosePowerup(powerup.instance_id ?? powerup.id)}
                  className="powerup-card powerup-card-animate"
                  style={{ animationDelay: `${index * 120}ms` }}
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

      {streakBankOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gradient-to-br from-[#1a1f3a] to-[#0a0e27] border-2 border-primary/50 rounded-2xl p-8 max-w-md w-full shadow-2xl shadow-primary/20">
            <div className="text-center mb-4">
              <h2 className="text-white mb-2">Streak Bank</h2>
              <p className="text-gray-400 text-sm">
                Bank your streak of {stats.currentStreak} into time or score.
              </p>
            </div>
            <div className="streak-bank-actions">
              <button
                onClick={() => handleStreakBankChoice('time')}
                className="streak-bank-button"
              >
                Bank to Time
              </button>
              <button
                onClick={() => handleStreakBankChoice('score')}
                className="streak-bank-button"
              >
                Bank to Score
              </button>
            </div>
            <button
              onClick={() => {
                setStreakBankOpen(false);
                setPendingStreakBankId(null);
              }}
              className="streak-bank-cancel"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
