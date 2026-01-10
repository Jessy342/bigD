import { LetterTile } from './LetterTile';

interface GameGridProps {
  guesses: string[];
  currentGuess: string;
  evaluations: Array<Array<'correct' | 'present' | 'absent' | null>>;
  maxGuesses: number;
  wordLength: number;
}

export function GameGrid({ guesses, currentGuess, evaluations, maxGuesses, wordLength }: GameGridProps) {
  const rows = Array.from({ length: maxGuesses }, (_, i) => {
    if (i < guesses.length) {
      // Completed guess
      return {
        letters: guesses[i].split(''),
        states: evaluations[i],
        isComplete: true,
      };
    } else if (i === guesses.length) {
      // Current guess being typed
      const letters = currentGuess.split('');
      const paddedLetters = [...letters, ...Array(wordLength - letters.length).fill('')];
      return {
        letters: paddedLetters,
        states: paddedLetters.map(() => null),
        isComplete: false,
      };
    } else {
      // Empty rows
      return {
        letters: Array(wordLength).fill(''),
        states: Array(wordLength).fill(null),
        isComplete: false,
      };
    }
  });

  return (
    <div className="flex flex-col gap-2">
      {rows.map((row, rowIndex) => (
        <div key={rowIndex} className="flex gap-2 justify-center">
          {row.letters.map((letter, colIndex) => {
            const state = row.isComplete && row.states[colIndex]
              ? row.states[colIndex]
              : letter
              ? 'filled'
              : 'empty';
            
            const shouldAnimate = row.isComplete && rowIndex === guesses.length - 1;
            
            return (
              <LetterTile
                key={colIndex}
                letter={letter}
                state={state as 'empty' | 'filled' | 'correct' | 'present' | 'absent'}
                animate={shouldAnimate}
                delay={colIndex * 100}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}
