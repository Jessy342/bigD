interface LetterTileProps {
  letter: string;
  state: 'empty' | 'filled' | 'correct' | 'present' | 'absent';
  animate?: boolean;
  delay?: number;
}

export function LetterTile({ letter, state, animate = false, delay = 0 }: LetterTileProps) {
  const getBackgroundColor = () => {
    switch (state) {
      case 'correct':
        return 'bg-[#10b981]';
      case 'present':
        return 'bg-[#f59e0b]';
      case 'absent':
        return 'bg-[#374151]';
      case 'filled':
        return 'bg-[#1f2937] border-primary';
      default:
        return 'bg-[#1f2937] border-[#374151]';
    }
  };

  const animationClass = animate ? 'animate-flip-in' : '';
  
  return (
    <div
      className={`
        letter-tile
        w-14 h-14 sm:w-16 sm:h-16 
        border-2 rounded-lg
        flex items-center justify-center
        transition-all duration-300
        ${getBackgroundColor()}
        ${animationClass}
        ${state === 'filled' ? 'scale-105' : ''}
        relative
      `}
      style={{
        animationDelay: `${delay}ms`,
      }}
    >
      {/* Retro pixel effect border */}
      {state !== 'empty' && (
        <div className="absolute inset-0 rounded-lg shadow-[inset_0_2px_4px_rgba(255,255,255,0.1)]" />
      )}
      
      <span className="text-white select-none z-10">
        {letter}
      </span>
    </div>
  );
}
