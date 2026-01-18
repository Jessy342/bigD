import { useState, useEffect, useCallback, useMemo, useRef, type CSSProperties, type KeyboardEvent } from 'react';
import { GameModal } from './GameModal';
import { StartScreen } from './StartScreen';
import { GuessList, type GuessEntry } from './GuessList';
import { Trophy, Gamepad2, RotateCcw, SkipForward, Timer, Lightbulb, Palette, Eye } from 'lucide-react';
import { toast } from 'sonner';

const RUN_TIME_SECONDS = 5 * 60;
const INVENTORY_CAPACITY = 3;
const API_BASE = import.meta.env.VITE_API_BASE ?? '';
const LOOP_MARGIN_MIN_SECONDS = 1.5;
const LOOP_MARGIN_MAX_SECONDS = 4.5;
const LOOP_MARGIN_RATIO = 0.3;
const LOOP_SWAP_TIMEOUT_MS = 450;
const LOOP_RESTART_SECONDS = 0.12;
const THEME_PALETTE: Record<string, { primary: string; border: string; hue: number }> = {
  nature: { primary: '#22c55e', border: 'rgba(34, 197, 94, 0.35)', hue: 130 },
  food: { primary: '#f97316', border: 'rgba(249, 115, 22, 0.35)', hue: 24 },
  sports: { primary: '#38bdf8', border: 'rgba(56, 189, 248, 0.35)', hue: 200 },
  tech: { primary: '#22d3ee', border: 'rgba(34, 211, 238, 0.35)', hue: 190 },
  music: { primary: '#f472b6', border: 'rgba(244, 114, 182, 0.35)', hue: 320 },
  random: { primary: '#94a3b8', border: 'rgba(148, 163, 184, 0.4)', hue: 210 },
  default: { primary: '#6366f1', border: 'rgba(99, 102, 241, 0.35)', hue: 230 },
};

type Powerup = {
  id: string;
  instance_id?: string;
  type: string;
  value: string | number;
  name: string;
  desc: string;
};

type Theme = {
  id: string;
  name: string;
  description: string;
};

type RunState = {
  run_id: string;
  level: number;
  guesses: GuessEntry[];
  best_rank: number | null;
  won: boolean;
  failed: boolean;
  pending_powerups: Powerup[];
  skip_available: boolean;
  skip_in_levels: number;
  score: number;
  last_score_delta: number;
  difficulty: string;
  boss_level: boolean;
  theme_id: string;
  theme_name: string;
  theme_description: string;
  pending_theme_choice: boolean;
  theme_options: Theme[];
  inventory: Powerup[];
  similarity_reveal_remaining: number;
  random_mode: boolean;
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
  const [revealOpen, setRevealOpen] = useState(false);
  const [revealWord, setRevealWord] = useState('');
  const [revealLoading, setRevealLoading] = useState(false);
  const [timerFreezeSeconds, setTimerFreezeSeconds] = useState(0);
  const [timerSlowSeconds, setTimerSlowSeconds] = useState(0);
  const [startLoading, setStartLoading] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [randomWinLoading, setRandomWinLoading] = useState(false);
  const [powerupSelectOpen, setPowerupSelectOpen] = useState(false);
  const [powerupSelectPowerup, setPowerupSelectPowerup] = useState<Powerup | null>(null);
  const [powerupSelectChoices, setPowerupSelectChoices] = useState<string[]>([]);
  const backgroundVideoPrimaryRef = useRef<HTMLVideoElement | null>(null);
  const backgroundVideoSecondaryRef = useRef<HTMLVideoElement | null>(null);
  const [activeBackgroundVideo, setActiveBackgroundVideo] = useState<'primary' | 'secondary'>('primary');
  const activeBackgroundVideoRef = useRef<'primary' | 'secondary'>('primary');
  const loopSwapInProgressRef = useRef(false);
  const swapTimeoutRef = useRef<number | null>(null);
  const [stats, setStats] = useState({
    gamesPlayed: 0,
    gamesWon: 0,
    currentStreak: 0,
    score: 0,
  });
  const [themes, setThemes] = useState<Theme[]>([]);
  const [selectedThemeId, setSelectedThemeId] = useState<string | null>(null);
  const [randomBackgrounds, setRandomBackgrounds] = useState<string[]>([]);
  const [randomBackgroundUrl, setRandomBackgroundUrl] = useState('');
  const isRandomMode = Boolean(run?.random_mode || (run?.theme_id ?? selectedThemeId) === 'random');
  const attemptBackgroundPlay = useCallback(() => {
    if (isRandomMode) {
      return;
    }
    const primary = backgroundVideoPrimaryRef.current;
    const secondary = backgroundVideoSecondaryRef.current;
    const active = activeBackgroundVideoRef.current === 'primary' ? primary : secondary;
    const target = active ?? primary ?? secondary;
    if (!target) {
      return;
    }
    target.muted = true;
    target.defaultMuted = true;
    target.playsInline = true;
    target.autoplay = true;
    const result = target.play();
    if (result && typeof result.catch === 'function') {
      result.catch(() => {});
    }
  }, [isRandomMode]);

  const guesses = run?.guesses ?? [];
  const level = run?.level ?? 1;
  const pendingPowerups = run?.pending_powerups ?? [];
  const powerupPending = pendingPowerups.length > 0;
  const inventory = run?.inventory ?? [];
  const rerollRewardPowerup = inventory.find((item) => item.id === 'reroll_rewards') ?? null;
  const elapsedTime = Math.max(0, RUN_TIME_SECONDS - remainingSeconds);
  const powerupNeedsSingle = useMemo(() => new Set(['anchor_guess']), []);
  const powerupNeedsDouble = useMemo(() => new Set(['comparator']), []);
  const difficulty = run?.difficulty ?? 'easy';
  const bossLevel = run?.boss_level ?? false;
  const themePending = run?.pending_theme_choice ?? false;
  const themeOptions = run?.theme_options ?? [];
  const themeId = run?.theme_id ?? selectedThemeId ?? '';
  const showTimer = !isRandomMode;
  const showTheme = !isRandomMode;
  const showPowerups = !isRandomMode;
  const showHintButton = !isRandomMode;
  const showRevealButton = true;
  const themeName =
    run?.theme_name ||
    themes.find((theme) => theme.id === themeId)?.name ||
    '';
  const themeDescription =
    run?.theme_description ||
    themes.find((theme) => theme.id === themeId)?.description ||
    '';
  const randomWinOpen = Boolean(isRandomMode && run?.won);
  const themeChoicesSource = themeOptions.length
    ? themeOptions
    : themes.filter((theme) => theme.id !== 'random');
  const themeChoices = themeChoicesSource.slice(0, 3);
  const runPaused = (showPowerups ? powerupPending || themePending : false) || randomWinOpen || powerupSelectOpen;
  const timeRatio = showTimer
    ? Math.max(0, Math.min(1, remainingSeconds / RUN_TIME_SECONDS))
    : 1;
  const urgency = showTimer ? Math.max(0, Math.min(1, (0.35 - timeRatio) / 0.35)) : 0;
  const timerHue = Math.round(210 - 210 * urgency);
  const themeTokens = useMemo(
    () => THEME_PALETTE[themeId] ?? THEME_PALETTE.default,
    [themeId],
  );
  const themeClass = useMemo(() => {
    const safe = (themeId || 'default').replace(/[^a-z0-9_-]/gi, '');
    return `theme-${safe || 'default'}`;
  }, [themeId]);
  const timerStyle = useMemo(
    () =>
      ({
        ['--timer-progress' as const]: timeRatio,
        ['--timer-hue' as const]: timerHue,
        ['--timer-urgency' as const]: urgency,
        ['--theme-hue' as const]: themeTokens.hue,
        ['--primary' as const]: themeTokens.primary,
        ['--border' as const]: themeTokens.border,
        ...(isRandomMode
          ? {
              ['--game-art' as const]: randomBackgroundUrl ? `url("${randomBackgroundUrl}")` : 'none',
              ['--game-art-opacity' as const]: randomBackgroundUrl ? '0.22' : '0',
            }
          : null),
      }) as CSSProperties,
    [timeRatio, timerHue, urgency, themeTokens, isRandomMode, randomBackgroundUrl],
  );

  const pickRandomBackground = useCallback((list: string[]) => {
    if (!list.length) {
      return '';
    }
    const choice = list[Math.floor(Math.random() * list.length)];
    return choice || '';
  }, []);

  useEffect(() => {
    const savedStats = localStorage.getItem('wordle-stats');
    if (savedStats) {
      try {
        const parsed = JSON.parse(savedStats) as Partial<typeof stats>;
        setStats({
          gamesPlayed: Number(parsed.gamesPlayed) || 0,
          gamesWon: Number(parsed.gamesWon) || 0,
          currentStreak: Number(parsed.currentStreak) || 0,
          score: Number(parsed.score) || 0,
        });
      } catch {
        setStats({
          gamesPlayed: 0,
          gamesWon: 0,
          currentStreak: 0,
          score: 0,
        });
      }
    }
  }, []);

  useEffect(() => {
    if (!gameStarted || !isRandomMode || randomBackgrounds.length) {
      return;
    }
    let cancelled = false;
    const loadRandomBackgrounds = async () => {
      try {
        const data = await api<{ backgrounds: string[] }>('/api/random/backgrounds');
        if (cancelled) {
          return;
        }
        const list = data.backgrounds ?? [];
        setRandomBackgrounds(list);
      } catch {
        if (!cancelled) {
          setRandomBackgrounds([]);
        }
      }
    };
    loadRandomBackgrounds();
    return () => {
      cancelled = true;
    };
  }, [gameStarted, isRandomMode, randomBackgrounds.length]);

  useEffect(() => {
    if (!gameStarted || !isRandomMode || randomBackgroundUrl || !randomBackgrounds.length) {
      return;
    }
    setRandomBackgroundUrl(pickRandomBackground(randomBackgrounds));
  }, [gameStarted, isRandomMode, randomBackgroundUrl, randomBackgrounds, pickRandomBackground]);

  useEffect(() => {
    activeBackgroundVideoRef.current = activeBackgroundVideo;
  }, [activeBackgroundVideo]);

  useEffect(() => {
    const primary = backgroundVideoPrimaryRef.current;
    const secondary = backgroundVideoSecondaryRef.current;
    if (!gameStarted || isRandomMode || !primary || !secondary) {
      return;
    }
    const prepareVideo = (video: HTMLVideoElement) => {
      video.muted = true;
      video.defaultMuted = true;
      video.playsInline = true;
      video.autoplay = true;
    };
    prepareVideo(primary);
    prepareVideo(secondary);
    const handleCanPlay = () => attemptBackgroundPlay();
    const handleVisibility = () => {
      if (!document.hidden) {
        attemptBackgroundPlay();
      }
    };
    primary.addEventListener('canplay', handleCanPlay);
    secondary.addEventListener('canplay', handleCanPlay);
    document.addEventListener('visibilitychange', handleVisibility);
    document.addEventListener('pointerdown', attemptBackgroundPlay, { once: true });
    document.addEventListener('keydown', attemptBackgroundPlay, { once: true });
    attemptBackgroundPlay();
    return () => {
      primary.removeEventListener('canplay', handleCanPlay);
      secondary.removeEventListener('canplay', handleCanPlay);
      document.removeEventListener('visibilitychange', handleVisibility);
      document.removeEventListener('pointerdown', attemptBackgroundPlay);
      document.removeEventListener('keydown', attemptBackgroundPlay);
    };
  }, [attemptBackgroundPlay, gameStarted, isRandomMode]);

  useEffect(() => {
    attemptBackgroundPlay();
  }, [attemptBackgroundPlay, activeBackgroundVideo, themeId]);

  useEffect(() => {
    let cancelled = false;
    const loadThemes = async () => {
      try {
        const data = await api<{ themes: Theme[] }>('/api/themes');
        if (cancelled) {
          return;
        }
        const list = data.themes ?? [];
        setThemes(list);
        if (!selectedThemeId && list.length) {
          setSelectedThemeId(list[0].id);
        }
      } catch (error) {
        if (!cancelled) {
          toast.error('Failed to load themes.');
          setStartError('Backend not reachable. Start the server on port 8000.');
        }
      }
    };
    loadThemes();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (run?.theme_id) {
      setSelectedThemeId(run.theme_id);
    }
  }, [run?.theme_id]);

  useEffect(() => {
    const handleVisibility = () => {
      setIsTabActive(!document.hidden);
    };
    handleVisibility();
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  useEffect(() => {
    const primary = backgroundVideoPrimaryRef.current;
    const secondary = backgroundVideoSecondaryRef.current;
    if (!gameStarted || isRandomMode || !primary || !secondary) {
      return;
    }
    let rafId = 0;

    const getLoopMargin = (duration: number) => {
      if (!Number.isFinite(duration) || duration <= 0) {
        return LOOP_MARGIN_MAX_SECONDS;
      }
      return Math.min(
        LOOP_MARGIN_MAX_SECONDS,
        Math.max(LOOP_MARGIN_MIN_SECONDS, duration * LOOP_MARGIN_RATIO),
      );
    };

    const setStartTime = (video: HTMLVideoElement) => {
      if (Number.isFinite(video.duration) && video.duration > LOOP_RESTART_SECONDS) {
        video.currentTime = LOOP_RESTART_SECONDS;
      } else {
        video.currentTime = Math.max(0, LOOP_RESTART_SECONDS);
      }
    };

    const safePlay = (video: HTMLVideoElement) => {
      const result = video.play();
      if (result && typeof result.catch === 'function') {
        result.catch(() => {});
      }
    };

    const primeActive = (video: HTMLVideoElement) => {
      setStartTime(video);
      safePlay(video);
    };

    const parkVideo = (video: HTMLVideoElement) => {
      setStartTime(video);
      video.pause();
    };

    const handlePrimaryLoaded = () => {
      const active = activeBackgroundVideoRef.current === 'primary' ? primary : secondary;
      const standby = active === primary ? secondary : primary;
      primeActive(active);
      parkVideo(standby);
    };

    const handleSecondaryLoaded = () => {
      parkVideo(secondary);
    };

    if (primary.readyState >= 1) {
      handlePrimaryLoaded();
    } else {
      primary.addEventListener('loadedmetadata', handlePrimaryLoaded);
    }

    if (secondary.readyState >= 1) {
      handleSecondaryLoaded();
    } else {
      secondary.addEventListener('loadedmetadata', handleSecondaryLoaded);
    }

    const waitForFrame = (video: HTMLVideoElement, onReady: () => void) => {
      const withFrame = video as HTMLVideoElement & {
        requestVideoFrameCallback?: (callback: () => void) => number;
      };
      if (typeof withFrame.requestVideoFrameCallback === 'function') {
        withFrame.requestVideoFrameCallback(() => {
          onReady();
        });
        return;
      }
      if (video.readyState >= 2) {
        onReady();
        return;
      }
      const handleCanPlay = () => {
        video.removeEventListener('canplay', handleCanPlay);
        onReady();
      };
      video.addEventListener('canplay', handleCanPlay);
    };

    const clearSwapTimeout = () => {
      if (swapTimeoutRef.current) {
        window.clearTimeout(swapTimeoutRef.current);
        swapTimeoutRef.current = null;
      }
    };

    const swapTo = (next: HTMLVideoElement, current: HTMLVideoElement) => {
      if (loopSwapInProgressRef.current) {
        return;
      }
      loopSwapInProgressRef.current = true;
      current.pause();
      setStartTime(next);
      safePlay(next);
      let finalized = false;
      const finalizeSwap = () => {
        if (finalized) {
          return;
        }
        finalized = true;
        clearSwapTimeout();
        setActiveBackgroundVideo(next === primary ? 'primary' : 'secondary');
        parkVideo(current);
        loopSwapInProgressRef.current = false;
        attemptBackgroundPlay();
      };
      waitForFrame(next, finalizeSwap);
      clearSwapTimeout();
      swapTimeoutRef.current = window.setTimeout(finalizeSwap, LOOP_SWAP_TIMEOUT_MS);
    };

    const handleEnded = (endedVideo: HTMLVideoElement) => {
      const active = activeBackgroundVideoRef.current === 'primary' ? primary : secondary;
      if (endedVideo !== active) {
        return;
      }
      const standby = active === primary ? secondary : primary;
      swapTo(standby, active);
    };

    const handlePrimaryEnded = () => handleEnded(primary);
    const handleSecondaryEnded = () => handleEnded(secondary);

    const handlePause = (pausedVideo: HTMLVideoElement) => {
      if (document.hidden || loopSwapInProgressRef.current) {
        return;
      }
      const active = activeBackgroundVideoRef.current === 'primary' ? primary : secondary;
      if (pausedVideo !== active) {
        return;
      }
      const duration = pausedVideo.duration;
      if (Number.isFinite(duration) && duration > 0) {
        const endMargin = getLoopMargin(duration);
        if (pausedVideo.currentTime >= duration - endMargin) {
          const standby = active === primary ? secondary : primary;
          swapTo(standby, active);
          return;
        }
      }
      safePlay(pausedVideo);
    };

    const handlePrimaryPause = () => handlePause(primary);
    const handleSecondaryPause = () => handlePause(secondary);

    const handleTimeUpdate = (video: HTMLVideoElement) => {
      if (loopSwapInProgressRef.current) {
        return;
      }
      const active = activeBackgroundVideoRef.current === 'primary' ? primary : secondary;
      if (video !== active) {
        return;
      }
      const duration = video.duration;
      if (Number.isFinite(duration) && duration > 0) {
        const endMargin = getLoopMargin(duration);
        if (video.currentTime >= duration - endMargin) {
          const standby = active === primary ? secondary : primary;
          swapTo(standby, active);
        }
      }
    };

    const handlePrimaryTimeUpdate = () => handleTimeUpdate(primary);
    const handleSecondaryTimeUpdate = () => handleTimeUpdate(secondary);

    const tick = () => {
      const active = activeBackgroundVideoRef.current === 'primary' ? primary : secondary;
      const standby = active === primary ? secondary : primary;
      const duration = active.duration;
      if (!loopSwapInProgressRef.current && Number.isFinite(duration) && duration > 0) {
        const endMargin = getLoopMargin(duration);
        if (active.currentTime >= duration - endMargin) {
          swapTo(standby, active);
        }
      }
      rafId = window.requestAnimationFrame(tick);
    };

    primary.addEventListener('ended', handlePrimaryEnded);
    secondary.addEventListener('ended', handleSecondaryEnded);
    primary.addEventListener('pause', handlePrimaryPause);
    secondary.addEventListener('pause', handleSecondaryPause);
    primary.addEventListener('timeupdate', handlePrimaryTimeUpdate);
    secondary.addEventListener('timeupdate', handleSecondaryTimeUpdate);
    rafId = window.requestAnimationFrame(tick);
    return () => {
      primary.removeEventListener('loadedmetadata', handlePrimaryLoaded);
      secondary.removeEventListener('loadedmetadata', handleSecondaryLoaded);
      primary.removeEventListener('ended', handlePrimaryEnded);
      secondary.removeEventListener('ended', handleSecondaryEnded);
      primary.removeEventListener('pause', handlePrimaryPause);
      secondary.removeEventListener('pause', handleSecondaryPause);
      primary.removeEventListener('timeupdate', handlePrimaryTimeUpdate);
      secondary.removeEventListener('timeupdate', handleSecondaryTimeUpdate);
      clearSwapTimeout();
      window.cancelAnimationFrame(rafId);
    };
  }, [attemptBackgroundPlay, gameStarted, isRandomMode]);

  useEffect(() => {
    if (!showTimer) {
      return;
    }
    if (!gameStarted || gameStatus !== 'playing' || runPaused || remainingSeconds <= 0 || !isTabActive) {
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
    runPaused,
    remainingSeconds,
    isTabActive,
    timerFreezeSeconds,
    timerSlowSeconds,
    showTimer,
  ]);

  useEffect(() => {
    if (!run) {
      return;
    }
    setHintOpen(false);
    setHintText('');
    setHintLoading(false);
    setRevealOpen(false);
    setRevealWord('');
    setRevealLoading(false);
  }, [run?.level]);

  const startGame = useCallback(async () => {
    try {
      setStartLoading(true);
      setStartError(null);
      setRandomBackgroundUrl('');
      const payload = selectedThemeId ? { theme_id: selectedThemeId } : undefined;
      const data = await api<RunState>('/api/run/start', {
        method: 'POST',
        body: payload ? JSON.stringify(payload) : undefined,
      });
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
      setRevealOpen(false);
      setRevealWord('');
      setRevealLoading(false);
      setPowerupSelectOpen(false);
      setPowerupSelectPowerup(null);
      setPowerupSelectChoices([]);
      setRandomWinLoading(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to start run.';
      if (/failed to fetch|network/i.test(message)) {
        setStartError('Backend not reachable. Start the server on port 8000.');
        toast.error('Backend not reachable. Start the server on port 8000.');
      } else {
        setStartError(message);
        toast.error(message);
      }
    } finally {
      setStartLoading(false);
    }
  }, [selectedThemeId]);

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
    setRevealOpen(false);
    setRevealWord('');
    setRevealLoading(false);
    setStartError(null);
    setStartLoading(false);
    setRandomBackgroundUrl('');
    setRandomWinLoading(false);
    setPowerupSelectOpen(false);
    setPowerupSelectPowerup(null);
    setPowerupSelectChoices([]);
  }, []);

  const saveScore = useCallback(() => {
    localStorage.setItem('wordle-stats', JSON.stringify(stats));
    toast.success('Score saved.');
  }, [stats]);

  const resetScore = useCallback(() => {
    setStats((prev) => {
      const next = {
        ...prev,
        score: 0,
        gamesPlayed: 0,
        gamesWon: 0,
        currentStreak: 0,
      };
      localStorage.setItem('wordle-stats', JSON.stringify(next));
      return next;
    });
    toast.success('Stats reset.');
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

  useEffect(() => {
    if (!showTimer) {
      return;
    }
    if (remainingSeconds > 0 || gameStatus === 'lost') {
      return;
    }
    if (!run) {
      return;
    }
    const endRun = async () => {
      try {
        const data = await api<{
          state: RunState;
          saved: boolean;
          messages?: string[];
        }>(`/api/run/${run.run_id}/fail`, { method: 'POST' });
        setRun(data.state);
        pushMessages(data.messages);
        if (data.saved) {
          setGameStatus('playing');
          setRemainingSeconds(RUN_TIME_SECONDS);
          setTimerFreezeSeconds(0);
          setTimerSlowSeconds(0);
          setCurrentGuess('');
          return;
        }
        setGameStatus('lost');
        setStats((prev) => {
          const next = {
            ...prev,
            gamesPlayed: prev.gamesPlayed + 1,
            gamesWon: prev.gamesWon,
            currentStreak: 0,
          };
          localStorage.setItem('wordle-stats', JSON.stringify(next));
          return next;
        });
        toast.error("Time's up! Run over.");
      } catch (error) {
        handleRunError(error, 'Failed to end run.');
        setGameStatus('lost');
      }
    };
    endRun();
  }, [remainingSeconds, gameStatus, showTimer, run, handleRunError, pushMessages]);

  const startRandomRound = useCallback(async () => {
    if (!run || !isRandomMode) {
      return;
    }
    setRandomWinLoading(true);
    try {
      const data = await api<RunState>(`/api/run/${run.run_id}/skip`, { method: 'POST' });
      setRun(data);
      setCurrentGuess('');
      setTotalGuesses(0);
      setGameStatus('playing');
      setRandomBackgroundUrl('');
      setHintOpen(false);
      setHintText('');
      setRevealOpen(false);
      setRevealWord('');
      setRevealLoading(false);
    } catch (error) {
      handleRunError(error, 'Failed to start new word.');
    } finally {
      setRandomWinLoading(false);
    }
  }, [run, isRandomMode, handleRunError]);

  const skipLevel = useCallback(async () => {
    if (!run || runPaused || gameStatus !== 'playing') {
      return;
    }
    const previousLevel = run.level;
    try {
      const data = await api<RunState>(`/api/run/${run.run_id}/skip`, { method: 'POST' });
      setRun(data);
      if (data.level === previousLevel) {
        const remaining = data.skip_in_levels;
        if (remaining > 0) {
          toast.error(`Skip available in ${remaining} level${remaining === 1 ? '' : 's'}.`);
        } else {
          toast.error('Skip not available yet.');
        }
      } else {
        toast.info('Level skipped.');
      }
    } catch (error) {
      handleRunError(error, 'Failed to skip level.');
    }
  }, [run, runPaused, gameStatus, handleRunError]);

  const choosePowerup = useCallback(
    async (powerupId: string) => {
      if (!run) {
        return;
      }
      if (isRandomMode) {
        return;
      }
      try {
        const data = await api<{
          state: RunState;
          added: Powerup | null;
          message?: string | null;
        }>(`/api/run/${run.run_id}/choose_powerup`, {
          method: 'POST',
          body: JSON.stringify({ powerup_id: powerupId }),
        });
        setRun(data.state);
        if (data.added) {
          toast.success(`Added to inventory: ${data.added.name}`, { duration: 4000 });
        } else {
          toast.error(data.message || 'Powerup not added.');
        }
        if (data.message && data.added) {
          toast.info(data.message, { duration: 4000 });
        }
      } catch (error) {
        handleRunError(error, 'Failed to choose powerup.');
      }
    },
    [run, handleRunError, isRandomMode],
  );

  const chooseTheme = useCallback(
    async (themeId: string) => {
      if (!run) {
        return;
      }
      try {
        const data = await api<RunState>(`/api/run/${run.run_id}/choose_theme`, {
          method: 'POST',
          body: JSON.stringify({ theme_id: themeId }),
        });
        setRun(data);
        if (data.theme_name) {
          toast.success(`Theme selected: ${data.theme_name}`, { duration: 4000 });
        }
      } catch (error) {
        handleRunError(error, 'Failed to choose theme.');
      }
    },
    [run, handleRunError],
  );

  const useInventoryPowerup = useCallback(
    async (powerup: Powerup, options?: { choice?: string; choices?: string[] }) => {
      if (!run || gameStatus !== 'playing' || isRandomMode) {
        return;
      }
      if (runPaused && powerup.id !== 'reroll_rewards') {
        return;
      }
      const inventoryId = powerup.instance_id ?? powerup.id;
      try {
        const data = await api<{
          state: RunState;
          used: Powerup | null;
          messages?: string[];
          hint: string | null;
          related_word: string | null;
          time_bonus_seconds: number | null;
          time_penalty_seconds: number | null;
          timer_freeze_seconds: number | null;
          timer_slow_seconds: number | null;
        }>(`/api/run/${run.run_id}/use_powerup`, {
          method: 'POST',
          body: JSON.stringify({
            inventory_id: inventoryId,
            choice: options?.choice,
            choices: options?.choices,
          }),
        });
        setRun(data.state);
        if (!data.used) {
          toast.error('Powerup not available.');
          return;
        }
        const hasMessages = Boolean(data.messages?.length);
        pushMessages(data.messages);
        if (!hasMessages && data.hint) {
          toast.success(data.hint, { duration: 6000 });
        }
        if (!hasMessages && data.related_word) {
          toast.success(`Related word: ${data.related_word}`, { duration: 6000 });
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
    [run, runPaused, gameStatus, handleRunError, pushMessages, isRandomMode],
  );

  const openPowerupSelection = useCallback(
    (powerup: Powerup) => {
      const required = powerupNeedsDouble.has(powerup.id) ? 2 : 1;
      if (guesses.length < required) {
        toast.error(`Need at least ${required} guess${required === 1 ? '' : 'es'} first.`);
        return;
      }
      setPowerupSelectPowerup(powerup);
      setPowerupSelectChoices([]);
      setPowerupSelectOpen(true);
    },
    [guesses.length, powerupNeedsDouble],
  );

  const handlePowerupUse = useCallback(
    (powerup: Powerup) => {
      if (powerupNeedsSingle.has(powerup.id) || powerupNeedsDouble.has(powerup.id)) {
        openPowerupSelection(powerup);
        return;
      }
      useInventoryPowerup(powerup);
    },
    [powerupNeedsSingle, powerupNeedsDouble, openPowerupSelection, useInventoryPowerup],
  );

  const togglePowerupChoice = useCallback(
    (word: string) => {
      if (!powerupSelectPowerup) {
        return;
      }
      const limit = powerupNeedsDouble.has(powerupSelectPowerup.id) ? 2 : 1;
      setPowerupSelectChoices((prev) => {
        if (prev.includes(word)) {
          return prev.filter((item) => item !== word);
        }
        if (prev.length >= limit) {
          return limit === 1 ? [word] : [...prev.slice(1), word];
        }
        return [...prev, word];
      });
    },
    [powerupSelectPowerup, powerupNeedsDouble],
  );

  const confirmPowerupSelection = useCallback(() => {
    if (!powerupSelectPowerup) {
      return;
    }
    const isDouble = powerupNeedsDouble.has(powerupSelectPowerup.id);
    if (isDouble && powerupSelectChoices.length !== 2) {
      toast.error('Select two guesses.');
      return;
    }
    if (!isDouble && powerupSelectChoices.length !== 1) {
      toast.error('Select one guess.');
      return;
    }
    useInventoryPowerup(powerupSelectPowerup, {
      choice: powerupSelectChoices[0],
      choices: powerupSelectChoices,
    });
    setPowerupSelectOpen(false);
    setPowerupSelectPowerup(null);
    setPowerupSelectChoices([]);
  }, [powerupSelectPowerup, powerupSelectChoices, powerupNeedsDouble, useInventoryPowerup]);

  const closePowerupSelection = useCallback(() => {
    setPowerupSelectOpen(false);
    setPowerupSelectPowerup(null);
    setPowerupSelectChoices([]);
  }, []);

  const requestHint = useCallback(async () => {
    if (!run || runPaused || gameStatus !== 'playing') {
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
  }, [run, runPaused, gameStatus, handleRunError]);

  const requestReveal = useCallback(async () => {
    if (!run || runPaused || gameStatus !== 'playing') {
      return;
    }
    setRevealLoading(true);
    try {
      const data = await api<{ word: string }>(`/api/run/${run.run_id}/reveal`);
      const word = (data.word || '').trim().toUpperCase();
      setRevealWord(word || 'Unknown');
      setRevealOpen(true);
    } catch (error) {
      handleRunError(error, 'Failed to reveal word.');
    } finally {
      setRevealLoading(false);
    }
  }, [run, runPaused, gameStatus, handleRunError]);

  const handleGuessSubmit = useCallback(async () => {
    if (!run || runPaused || gameStatus !== 'playing') {
      return;
    }

    const guess = currentGuess.trim().toUpperCase();
    if (!guess) {
      toast.error('Enter a word to guess.');
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
        }
      >(`/api/run/${run.run_id}/guess`, {
        method: 'POST',
        body: JSON.stringify({ guess_word: guess }),
      });
      setRun(data);
      setCurrentGuess('');
      const delta = data.guesses.length - prevGuessCount;
      if (delta <= 0) {
        pushMessages(data.effect_messages);
        if (!data.effect_messages?.length) {
          toast.error('Guess not accepted.');
        }
        return;
      }
      pushMessages(data.effect_messages);
      if (data.time_bonus_seconds) {
        setRemainingSeconds((prev) => prev + Number(data.time_bonus_seconds));
        toast.info(`+${data.time_bonus_seconds} seconds`);
      }
      if (!isRandomMode) {
        setStats((prev) => {
          const next = { ...prev, score: prev.score + delta };
          localStorage.setItem('wordle-stats', JSON.stringify(next));
          return next;
        });
      }
      setTotalGuesses((prev) => prev + delta);

      if (data.won && data.pending_powerups?.length) {
        setStats((prev) => {
          const next = {
            ...prev,
            gamesPlayed: prev.gamesPlayed + 1,
            gamesWon: prev.gamesWon + 1,
            currentStreak: prev.currentStreak + 1,
          };
          localStorage.setItem('wordle-stats', JSON.stringify(next));
          return next;
        });
        toast.success(`Level ${data.level} complete! Choose a powerup.`);
      }
    } catch (error) {
      setCurrentGuess('');
      handleRunError(error, 'Guess failed.');
    }
  }, [run, runPaused, gameStatus, currentGuess, handleRunError, pushMessages, isRandomMode]);

  const handleGuessKeyDown = useCallback(
    (event: KeyboardEvent<HTMLInputElement>) => {
      if (event.key === 'Enter') {
        handleGuessSubmit();
      }
    },
    [handleGuessSubmit],
  );

  const bestRankDisplay = run?.best_rank ?? null;

  if (!gameStarted) {
    return (
      <StartScreen
        onStart={startGame}
        stats={stats}
        themes={themes}
        selectedThemeId={selectedThemeId}
        onSelectTheme={setSelectedThemeId}
        startError={startError}
        startLoading={startLoading}
        onSaveScore={saveScore}
        onResetScore={resetScore}
      />
    );
  }

  return (
    <div className={`game-shell ${themeClass}`} style={timerStyle}>
      {!isRandomMode && (
        <>
          <video
            className={`game-background-video ${activeBackgroundVideo === 'primary' ? 'is-active' : ''}`}
            ref={backgroundVideoPrimaryRef}
            autoPlay
            muted
            playsInline
            preload="auto"
            poster="/game-bg-nature-clean.png"
            aria-hidden="true"
            tabIndex={-1}
          >
            <source src="/game-bg-nature-clean.mp4" type="video/mp4" />
          </video>
          <video
            className={`game-background-video ${activeBackgroundVideo === 'secondary' ? 'is-active' : ''}`}
            ref={backgroundVideoSecondaryRef}
            autoPlay
            muted
            playsInline
            preload="auto"
            poster="/game-bg-nature-clean.png"
            aria-hidden="true"
            tabIndex={-1}
          >
            <source src="/game-bg-nature-clean.mp4" type="video/mp4" />
          </video>
        </>
      )}
      <div className="game-main">
        <div className="game-panel">
          <header className="game-topbar">
            <div className="game-brand">
              <div className="game-brand-badge">
                <Gamepad2 className="game-brand-icon" />
              </div>
              <div className="game-brand-text">
                <h1>ROUGLE</h1>
                <p>Guess the word by its context</p>
              </div>
            </div>

            <div className="game-actions">
              {showHintButton && (
                <button
                  onClick={requestHint}
                  className="game-action game-action--hint"
                  title="Get a hint"
              disabled={!run || runPaused || gameStatus !== 'playing' || hintLoading}
                >
                  <Lightbulb className="game-action-icon" />
                  <span>{hintLoading ? 'Thinking...' : 'Hint'}</span>
                </button>
              )}

              {showRevealButton && (
                <button
                  onClick={requestReveal}
                  className="game-action game-action--reveal"
                  title="Reveal Word"
              disabled={!run || runPaused || gameStatus !== 'playing' || revealLoading}
                >
                  <Eye className="game-action-icon" />
                  <span>{revealLoading ? 'Revealing...' : 'Reveal'}</span>
                </button>
              )}

              <button
                onClick={skipLevel}
                className="game-action game-action--skip"
                title="Skip Level"
                disabled={!run || runPaused || gameStatus !== 'playing' || !run.skip_available}
              >
                <SkipForward className="game-action-icon" />
                <span>
                  {run?.skip_available ? 'Skip' : `Skip ${run?.skip_in_levels ?? 0}`}
                </span>
              </button>

              <button
                onClick={restartRun}
                className="game-action game-action--restart"
                title="Restart Run"
              >
                <RotateCcw className="game-action-icon" />
                <span>Restart</span>
              </button>
            </div>
          </header>

          {isRandomMode && (
            <div className="game-random-meta">
              <span className="game-random-meta-label">Guesses</span>
              <span className="game-random-meta-value">{guesses.length}</span>
            </div>
          )}

          {showTheme && (
            <section className="game-stats">
              <div className="game-stat-card game-stat-card--level">
                <div className="game-stat-row">
                  <Trophy className="game-stat-icon" />
                  <span className="game-stat-value">LV {level}</span>
                </div>
                <div className="game-stat-meta">
                  <span className={`game-stat-meta-item ${bossLevel ? 'game-stat-meta-item--boss' : ''}`}>
                    {(bossLevel ? 'Boss' : difficulty).toUpperCase()}
                  </span>
                  <span className="game-stat-meta-item">
                    BEST {bestRankDisplay ? `#${bestRankDisplay}` : '--'}
                  </span>
                  <span className="game-stat-meta-item">{guesses.length} GUESSES</span>
                </div>
              </div>

              <div className="game-stat-card game-stat-card--theme">
                <div className="game-stat-row">
                  <Palette className="game-stat-icon" />
                  <span className="game-stat-value">{(themeName || 'Theme').toUpperCase()}</span>
                </div>
                <span className="game-stat-sub">
                  {(themeDescription || 'Pick a theme to start.').toUpperCase()}
                </span>
              </div>
            </section>
          )}

          {showPowerups && (
            <section className="inventory-panel">
              <div className="inventory-header">
                <span className="inventory-title">Inventory</span>
                <span className="inventory-count">
                  {inventory.length}/{INVENTORY_CAPACITY} item{inventory.length === 1 ? '' : 's'}
                </span>
              </div>
              {inventory.length ? (
                <div className="inventory-list">
                  {inventory.map((powerup, index) => {
                    const inventoryId = powerup.instance_id ?? powerup.id;
                    const inventoryKey = powerup.instance_id ?? `${powerup.id}-${index}`;
                    return (
                      <div key={inventoryKey} className="inventory-card">
                        <div className="inventory-text">
                          <div className="inventory-name">{powerup.name}</div>
                          <div className="inventory-desc">{powerup.desc}</div>
                        </div>
                        <button
                          className="inventory-use"
                          onClick={() => handlePowerupUse(powerup)}
                          disabled={!run || runPaused || gameStatus !== 'playing'}
                        >
                          Use
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="inventory-empty">No powerups yet. Win a level to earn one.</div>
              )}
            </section>
          )}

          <section className="game-guess-board">
            <GuessList guesses={guesses} />
          </section>

          <div className="game-input-bar">
            <input
              type="text"
              value={currentGuess}
              onChange={(event) => setCurrentGuess(event.target.value)}
              onKeyDown={handleGuessKeyDown}
              placeholder="enter word here"
              className="game-input"
              disabled={!run || runPaused || gameStatus !== 'playing'}
            />
            <button
              className="game-input-submit"
              onClick={handleGuessSubmit}
              disabled={!run || runPaused || gameStatus !== 'playing'}
            >
              Enter
            </button>
          </div>
        </div>
      </div>

      {showTimer && (
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
      )}

      {showPowerups && powerupPending && (
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
            {rerollRewardPowerup && (
              <button
                className="powerup-reroll"
                onClick={() => useInventoryPowerup(rerollRewardPowerup)}
              >
                Reroll Rewards
              </button>
            )}
          </div>
        </div>
      )}

      {showTheme && themePending && !powerupPending && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gradient-to-br from-[#1a1f3a] to-[#0a0e27] border-2 border-primary/50 rounded-2xl p-8 max-w-md w-full shadow-2xl shadow-primary/20">
            <div className="text-center mb-6">
              <h2 className="text-white mb-2">Choose a Theme</h2>
              <p className="text-gray-400 text-sm">Boss cleared. Pick your next theme.</p>
            </div>
            <div className="theme-grid theme-grid-choice">
              {themeChoices.map((theme, index) => (
                <button
                  key={theme.id}
                  onClick={() => chooseTheme(theme.id)}
                  className="theme-card theme-card-animate"
                  style={{ animationDelay: `${index * 120}ms` }}
                >
                  <div className="text-white mb-1">{theme.name}</div>
                  <div className="text-xs text-gray-400">{theme.description}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <GameModal
        isOpen={gameStatus === 'lost'}
        guesses={guesses.length}
        level={level}
        totalGuesses={totalGuesses}
        elapsedTime={elapsedTime}
        bestRank={bestRankDisplay}
        stats={stats}
        onPlayAgain={restartRun}
      />

      {powerupSelectOpen && powerupSelectPowerup && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gradient-to-br from-[#1a1f3a] to-[#0a0e27] border-2 border-primary/50 rounded-2xl p-6 max-w-md w-full shadow-2xl shadow-primary/20">
            <div className="text-center mb-4">
              <h2 className="text-white mb-2">{powerupSelectPowerup.name}</h2>
              <p className="text-gray-400 text-sm">
                {powerupNeedsDouble.has(powerupSelectPowerup.id)
                  ? 'Select two guesses to compare.'
                  : 'Select one guess to anchor.'}
              </p>
            </div>
            <div className="powerup-select-list">
              {guesses.map((guess) => {
                const active = powerupSelectChoices.includes(guess.word);
                return (
                  <button
                    key={guess.word}
                    type="button"
                    onClick={() => togglePowerupChoice(guess.word)}
                    className={`powerup-select-item ${active ? 'powerup-select-item--active' : ''}`}
                  >
                    <span className="powerup-select-word">{guess.word}</span>
                    <span className="powerup-select-rank">#{guess.rank}</span>
                  </button>
                );
              })}
            </div>
            <div className="powerup-select-actions">
              <button
                type="button"
                onClick={confirmPowerupSelection}
                className="powerup-select-confirm"
              >
                Use Powerup
              </button>
              <button
                type="button"
                onClick={closePowerupSelection}
                className="powerup-select-cancel"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {randomWinOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gradient-to-br from-[#1a1f3a] to-[#0a0e27] border-2 border-primary/50 rounded-2xl p-8 max-w-md w-full shadow-2xl shadow-primary/20">
            <div className="text-center mb-6">
              <h2 className="text-white mb-2">Correct!</h2>
              <p className="text-gray-400 text-sm">You found the word.</p>
            </div>
            <div className="flex flex-col gap-3">
              <button
                onClick={startRandomRound}
                disabled={randomWinLoading}
                className="w-full bg-gradient-to-r from-primary to-indigo-600 hover:from-primary/90 hover:to-indigo-600/90 text-white py-3 rounded-lg transition-all active:scale-95 shadow-lg shadow-primary/30 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                Generate New Word
              </button>
              <button
                onClick={restartRun}
                disabled={randomWinLoading}
                className="w-full bg-slate-900/70 hover:bg-slate-900 text-white py-3 rounded-lg transition-all active:scale-95 shadow-lg shadow-black/30 border border-slate-700 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                Return to Menu
              </button>
            </div>
          </div>
        </div>
      )}

      {showHintButton && hintOpen && (
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

      {showRevealButton && revealOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gradient-to-br from-[#1a1f3a] to-[#0a0e27] border-2 border-primary/50 rounded-2xl p-8 max-w-md w-full shadow-2xl shadow-primary/20">
            <div className="text-center mb-4">
              <h2 className="text-white mb-2">Secret Word</h2>
              <p className="text-gray-400 text-sm">Revealed for this run.</p>
            </div>
            <div className="bg-card/50 rounded-lg p-4 border border-primary/30 text-white text-center text-lg tracking-[0.2em]">
              {revealWord}
            </div>
            <button
              onClick={() => setRevealOpen(false)}
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

function formatTime(seconds: number) {
  const safeSeconds = Math.max(0, Math.ceil(seconds));
  const mins = Math.floor(safeSeconds / 60);
  const secs = safeSeconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}




