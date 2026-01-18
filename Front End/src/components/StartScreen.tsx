import { useEffect, useRef } from 'react';
import { motion } from 'motion/react';
import { Hash, Trophy, TrendingUp, Zap } from 'lucide-react';

type Theme = {
  id: string;
  name: string;
  description: string;
};

interface StartScreenProps {
  onStart: () => void;
  themes: Theme[];
  selectedThemeId: string | null;
  onSelectTheme: (themeId: string) => void;
  startError?: string | null;
  startLoading?: boolean;
  stats: {
    gamesPlayed: number;
    gamesWon: number;
    currentStreak: number;
    score: number;
  };
  onSaveScore: () => void;
  onResetScore: () => void;
}

export function StartScreen({
  onStart,
  stats,
  themes,
  selectedThemeId,
  onSelectTheme,
  startError,
  startLoading,
  onSaveScore,
  onResetScore,
}: StartScreenProps) {
  const winRate = stats.gamesPlayed > 0
    ? Math.round((stats.gamesWon / stats.gamesPlayed) * 100)
    : 0;
  const requiresTheme = themes.length > 0;
  const canStart = !requiresTheme || Boolean(selectedThemeId);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const menuVideoSrc = '/menu-bg.mp4';

  const attemptPlay = () => {
    const video = videoRef.current;
    if (!video) {
      return;
    }
    video.muted = true;
    video.defaultMuted = true;
    video.playsInline = true;
    video.autoplay = true;
    video.loop = true;
    const result = video.play();
    if (result && typeof result.catch === 'function') {
      result.catch(() => {});
    }
  };

  useEffect(() => {
    const video = videoRef.current;
    if (video) {
      video.muted = true;
      video.defaultMuted = true;
      video.playsInline = true;
      video.autoplay = true;
    }
    const handleCanPlay = () => attemptPlay();
    video?.addEventListener('canplay', handleCanPlay);
    attemptPlay();
    const handleUserGesture = () => attemptPlay();
    document.addEventListener('pointerdown', handleUserGesture, { once: true });
    document.addEventListener('keydown', handleUserGesture, { once: true });
    return () => {
      video?.removeEventListener('canplay', handleCanPlay);
      document.removeEventListener('pointerdown', handleUserGesture);
      document.removeEventListener('keydown', handleUserGesture);
    };
  }, []);

  return (
    <div className="menu-screen">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="menu-overlay"
      >
        <div className="menu-art">
          <video
            className="menu-art-media"
            ref={videoRef}
            autoPlay
            muted
            loop
            playsInline
            preload="auto"
            >
            <source src={menuVideoSrc} type="video/mp4" />
          </video>
          <button
            onClick={onStart}
            disabled={!canStart || startLoading}
            className="menu-start-hotspot"
            aria-label="Start"
            title={canStart ? 'Start' : 'Select a theme to start'}
          >
            {startLoading ? 'Loading...' : 'Start'}
          </button>
        </div>

        {startError && <div className="menu-error">{startError}</div>}

        {(stats.gamesPlayed > 0 || stats.score > 0) && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="menu-stats"
          >
            <div className="bg-card/50 rounded-lg p-4 border border-primary/30 text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <TrendingUp className="w-4 h-4 text-primary" />
                <span className="text-white">{stats.gamesPlayed}</span>
              </div>
              <p className="text-xs text-gray-400">Runs</p>
            </div>

            <div className="bg-card/50 rounded-lg p-4 border border-primary/30 text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <Trophy className="w-4 h-4 text-[#10b981]" />
                <span className="text-white">{winRate}%</span>
              </div>
              <p className="text-xs text-gray-400">Win Rate</p>
            </div>

            <div className="bg-card/50 rounded-lg p-4 border border-primary/30 text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <Zap className="w-4 h-4 text-[#f59e0b]" />
                <span className="text-white">{stats.currentStreak}</span>
              </div>
              <p className="text-xs text-gray-400">Streak</p>
            </div>

            <div className="bg-card/50 rounded-lg p-4 border border-primary/30 text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <Hash className="w-4 h-4 text-sky-400" />
                <span className="text-white">{stats.score}</span>
              </div>
              <p className="text-xs text-gray-400">Completed Guesses</p>
            </div>
          </motion.div>
        )}

        {(stats.gamesPlayed > 0 || stats.score > 0) && (
          <div className="menu-score-actions">
            <button type="button" className="menu-score-button" onClick={onSaveScore}>
              Save Score
            </button>
            <button type="button" className="menu-score-button menu-score-button--reset" onClick={onResetScore}>
              Reset Score
            </button>
          </div>
        )}

        {themes.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.45 }}
            className="menu-themes"
          >
            <div className="menu-section-title">Choose a Theme</div>
            <div className="menu-theme-grid">
              {themes.map((theme) => {
                const isActive = theme.id === selectedThemeId;
                return (
                  <button
                    key={theme.id}
                    onClick={() => onSelectTheme(theme.id)}
                    className={`menu-theme-card ${isActive ? 'menu-theme-card-active' : ''}`}
                  >
                    <div className="menu-theme-name">{theme.name}</div>
                    <div className="menu-theme-desc">{theme.description}</div>
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}

        <div className="menu-footer">{canStart ? 'Ready for launch.' : 'Select a theme to start.'}</div>
      </motion.div>
    </div>
  );
}
