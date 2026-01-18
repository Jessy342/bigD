import { Trophy, TrendingUp, Zap, RotateCcw, Timer, Hash, Target } from 'lucide-react';
import { motion } from 'motion/react';

interface GameModalProps {
  isOpen: boolean;  guesses: number;
  level: number;
  totalGuesses: number;
  elapsedTime: number;
  bestRank: number | null;
  stats: {
    gamesPlayed: number;
    gamesWon: number;
    currentStreak: number;
  };
  onPlayAgain: () => void;
}

export function GameModal({
  isOpen,  guesses,
  level,
  totalGuesses,
  elapsedTime,
  bestRank,
  stats,
  onPlayAgain,
}: GameModalProps) {
  if (!isOpen) return null;

  const winRate = stats.gamesPlayed > 0
    ? Math.round((stats.gamesWon / stats.gamesPlayed) * 100)
    : 0;

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ scale: 0.8, opacity: 0, y: 20 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        className="bg-gradient-to-br from-[#1a1f3a] to-[#0a0e27] border-2 border-primary/50 rounded-2xl p-8 max-w-md w-full shadow-2xl shadow-primary/20"
      >
        <div className="flex flex-col items-center mb-6">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
            className="w-20 h-20 rounded-full flex items-center justify-center mb-4 bg-gradient-to-br from-[#ef4444] to-[#dc2626] shadow-lg shadow-[#ef4444]/50"
          >
            <img src="/gameover.png" alt="Game over" className="w-12 h-12 object-contain" />
          </motion.div>

          <motion.h2
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-white mb-2"
          >
            Run Over!
          </motion.h2>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="text-gray-400 text-center"
          >
            You reached Level {level}
          </motion.p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="space-y-3 mb-6"
        >
          <div className="bg-card/50 rounded-lg p-4 border border-primary/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Trophy className="w-5 h-5 text-primary" />
                <span className="text-gray-400">Level Reached</span>
              </div>
              <span className="text-white">{level}</span>
            </div>
          </div>

          <div className="bg-card/50 rounded-lg p-4 border border-primary/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Target className="w-5 h-5 text-indigo-300" />
                <span className="text-gray-400">Best Rank</span>
              </div>
              <span className="text-white">{bestRank ? `#${bestRank}` : '--'}</span>
            </div>
          </div>

          <div className="bg-card/50 rounded-lg p-4 border border-primary/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Timer className="w-5 h-5 text-green-500" />
                <span className="text-gray-400">Total Time</span>
              </div>
              <span className="text-white">{formatTime(elapsedTime)}</span>
            </div>
          </div>

          <div className="bg-card/50 rounded-lg p-4 border border-primary/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Hash className="w-5 h-5 text-blue-500" />
                <span className="text-gray-400">Total Guesses</span>
              </div>
              <span className="text-white">{totalGuesses || guesses}</span>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="grid grid-cols-3 gap-4 mb-6"
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

        <motion.button
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          onClick={onPlayAgain}
          className="w-full bg-gradient-to-r from-primary to-indigo-600 hover:from-primary/90 hover:to-indigo-600/90 text-white py-4 rounded-lg transition-all active:scale-95 shadow-lg shadow-primary/30 flex items-center justify-center gap-2"
        >
          <RotateCcw className="w-5 h-5" />
          Start New Run
        </motion.button>
      </motion.div>
    </div>
  );
}

