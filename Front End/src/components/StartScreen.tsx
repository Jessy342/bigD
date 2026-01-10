import { motion } from 'motion/react';
import { Play, Trophy, TrendingUp, Zap, Sparkles } from 'lucide-react';

interface StartScreenProps {
  onStart: () => void;
  stats: {
    gamesPlayed: number;
    gamesWon: number;
    currentStreak: number;
  };
}

export function StartScreen({ onStart, stats }: StartScreenProps) {
  const winRate = stats.gamesPlayed > 0 
    ? Math.round((stats.gamesWon / stats.gamesPlayed) * 100) 
    : 0;

  return (
    <div className="w-full max-w-2xl mx-auto px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-center gap-8"
      >
        {/* Logo/Title Section */}
        <div className="text-center">
          <motion.div
            initial={{ scale: 0.8 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200 }}
            className="inline-flex items-center justify-center w-24 h-24 bg-gradient-to-br from-primary to-indigo-600 rounded-2xl mb-6 shadow-2xl shadow-primary/50"
          >
            <Sparkles className="w-12 h-12 text-white" />
          </motion.div>
          
          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-white mb-3"
          >
            HACKATHON WORDLE
          </motion.h1>
          
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="text-gray-400 max-w-md mx-auto"
          >
            Guess 5-letter words to progress through levels. 
            Use AI hints when you're stuck. How far can you go?
          </motion.p>
        </div>

        {/* Game Rules */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="w-full bg-card/50 border border-primary/30 rounded-xl p-6"
        >
          <h3 className="text-white mb-4 text-center">How to Play</h3>
          
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-[#10b981] flex items-center justify-center flex-shrink-0">
                <span className="text-white">A</span>
              </div>
              <div>
                <p className="text-white mb-1">Green</p>
                <p className="text-sm text-gray-400">Letter is correct and in the right position</p>
              </div>
            </div>
            
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-[#f59e0b] flex items-center justify-center flex-shrink-0">
                <span className="text-white">B</span>
              </div>
              <div>
                <p className="text-white mb-1">Orange</p>
                <p className="text-sm text-gray-400">Letter is in the word but wrong position</p>
              </div>
            </div>
            
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-[#374151] flex items-center justify-center flex-shrink-0">
                <span className="text-white">C</span>
              </div>
              <div>
                <p className="text-white mb-1">Gray</p>
                <p className="text-sm text-gray-400">Letter is not in the word</p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Stats Preview */}
        {stats.gamesPlayed > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="w-full grid grid-cols-3 gap-4"
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

        {/* Start Button */}
        <motion.button
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.6, type: 'spring', stiffness: 200 }}
          onClick={onStart}
          className="w-full max-w-xs bg-gradient-to-r from-primary to-indigo-600 hover:from-primary/90 hover:to-indigo-600/90 text-white py-4 px-8 rounded-xl transition-all active:scale-95 shadow-2xl shadow-primary/30 flex items-center justify-center gap-3 group"
        >
          <Play className="w-6 h-6 group-hover:scale-110 transition-transform" />
          <span>Start Game</span>
        </motion.button>

        {/* AI Feature Badge */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7 }}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600/20 border border-purple-600/50 rounded-full"
        >
          <Sparkles className="w-4 h-4 text-purple-400" />
          <span className="text-sm text-purple-300">Powered by Gemini AI</span>
        </motion.div>
      </motion.div>
    </div>
  );
}
