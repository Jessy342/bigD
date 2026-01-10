export type LetterState = 'correct' | 'present' | 'absent';

export function evaluateGuess(guess: string, answer: string): LetterState[] {
  const result: LetterState[] = Array(guess.length).fill('absent');
  const answerLetters = answer.split('');
  const guessLetters = guess.split('');
  
  // First pass: mark correct letters
  guessLetters.forEach((letter, i) => {
    if (letter === answerLetters[i]) {
      result[i] = 'correct';
      answerLetters[i] = ''; // Mark as used
    }
  });
  
  // Second pass: mark present letters
  guessLetters.forEach((letter, i) => {
    if (result[i] !== 'correct') {
      const answerIndex = answerLetters.indexOf(letter);
      if (answerIndex !== -1) {
        result[i] = 'present';
        answerLetters[answerIndex] = ''; // Mark as used
      }
    }
  });
  
  return result;
}

export function getKeyboardLetterStates(
  guesses: string[],
  evaluations: Array<Array<LetterState | null>>
): Map<string, LetterState> {
  const letterStates = new Map<string, LetterState>();
  
  guesses.forEach((guess, guessIndex) => {
    guess.split('').forEach((letter, letterIndex) => {
      const currentState = evaluations[guessIndex]?.[letterIndex];
      if (!currentState) return;
      
      const existingState = letterStates.get(letter);
      
      // Priority: correct > present > absent
      if (!existingState) {
        letterStates.set(letter, currentState);
      } else if (existingState === 'absent' && currentState !== 'absent') {
        letterStates.set(letter, currentState);
      } else if (existingState === 'present' && currentState === 'correct') {
        letterStates.set(letter, currentState);
      }
    });
  });
  
  return letterStates;
}
