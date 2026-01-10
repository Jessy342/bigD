import { Delete } from 'lucide-react';
import type { LetterState } from '../utils/gameLogic';

interface KeyboardProps {
  onKeyPress: (key: string) => void;
  letterStates: Map<string, LetterState>;
  disabled?: boolean;
}

const KEYBOARD_ROWS = [
  ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
  ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
  ['ENTER', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', 'BACKSPACE'],
];

export function Keyboard({ onKeyPress, letterStates, disabled = false }: KeyboardProps) {
  const getKeyColor = (key: string) => {
    if (key === 'ENTER' || key === 'BACKSPACE') {
      return 'bg-[#4b5563] hover:bg-[#6b7280]';
    }
    
    const state = letterStates.get(key);
    if (!state) {
      return 'bg-[#374151] hover:bg-[#4b5563]';
    }
    
    switch (state) {
      case 'correct':
        return 'bg-[#10b981] hover:bg-[#059669]';
      case 'present':
        return 'bg-[#f59e0b] hover:bg-[#d97706]';
      case 'absent':
        return 'bg-[#1f2937] hover:bg-[#374151]';
      default:
        return 'bg-[#374151] hover:bg-[#4b5563]';
    }
  };

  return (
    <div className="w-full max-w-xl mx-auto space-y-2">
      {KEYBOARD_ROWS.map((row, rowIndex) => (
        <div key={rowIndex} className="flex gap-1 justify-center">
          {row.map((key) => {
            const isSpecial = key === 'ENTER' || key === 'BACKSPACE';
            
            return (
              <button
                key={key}
                onClick={() => !disabled && onKeyPress(key)}
                disabled={disabled}
                className={`
                  ${isSpecial ? 'px-4 sm:px-6' : 'w-8 sm:w-10'}
                  h-12 sm:h-14
                  rounded-md
                  text-white
                  transition-all
                  active:scale-95
                  disabled:opacity-50 disabled:cursor-not-allowed
                  ${getKeyColor(key)}
                  border border-white/10
                  shadow-[inset_0_2px_4px_rgba(255,255,255,0.1)]
                  relative
                  overflow-hidden
                  group
                `}
              >
                {/* Shine effect on hover */}
                <div className="absolute inset-0 bg-gradient-to-br from-white/0 to-white/0 group-hover:from-white/10 group-hover:to-white/0 transition-all" />
                
                <span className="relative z-10 select-none">
                  {key === 'BACKSPACE' ? (
                    <Delete className="w-5 h-5" />
                  ) : (
                    key
                  )}
                </span>
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}
