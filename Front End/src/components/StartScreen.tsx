import { motion } from 'motion/react';
import { Trophy, TrendingUp, Zap } from 'lucide-react';

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
  };
}

export function StartScreen({
  onStart,
  stats,
  themes,
  selectedThemeId,
  onSelectTheme,
  startError,
  startLoading,
}: StartScreenProps) {
  const winRate = stats.gamesPlayed > 0
    ? Math.round((stats.gamesWon / stats.gamesPlayed) * 100)
    : 0;
  const requiresTheme = themes.length > 0;
  const canStart = !requiresTheme || Boolean(selectedThemeId);

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
            autoPlay
            muted
            loop
            playsInline
            poster="/menu-bg.png"
          >
            <source src="/menu-bg.mp4" type="video/mp4" />
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

        {stats.gamesPlayed > 0 && (
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
          </motion.div>
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
