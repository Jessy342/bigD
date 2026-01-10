/**
 * Gemini AI API Integration
 * 
 * To use this:
 * 1. Get an API key from https://makersuite.google.com/app/apikey
 * 2. Replace 'YOUR_GEMINI_API_KEY_HERE' below with your actual key
 */

const GEMINI_API_KEY = 'YOUR_GEMINI_API_KEY_HERE';
const GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent';

export async function getHintFromGemini(word: string, guesses: string[]): Promise<string> {
  // If no API key is set, return a mock hint
  if (GEMINI_API_KEY === 'YOUR_GEMINI_API_KEY_HERE') {
    return getMockHint(word, guesses);
  }

  try {
    const prompt = `You are helping with a Wordle game. The secret word is "${word}". 
The player has made these guesses so far: ${guesses.join(', ') || 'none yet'}.
Give a helpful but not too obvious hint about the word. Keep it under 20 words. Don't reveal the word directly.
Focus on things like: the word's meaning, category, or a subtle clue about its letters.`;

    const response = await fetch(`${GEMINI_API_URL}?key=${GEMINI_API_KEY}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        contents: [{
          parts: [{
            text: prompt
          }]
        }]
      })
    });

    if (!response.ok) {
      throw new Error('Gemini API request failed');
    }

    const data = await response.json();
    const hint = data.candidates[0]?.content?.parts[0]?.text;
    
    return hint || getMockHint(word, guesses);
  } catch (error) {
    console.error('Error calling Gemini API:', error);
    return getMockHint(word, guesses);
  }
}

// Mock hint system for when API key is not configured
function getMockHint(word: string, guesses: string[]): string {
  const firstLetter = word[0];
  const lastLetter = word[word.length - 1];
  const vowels = word.split('').filter(c => 'AEIOU'.includes(c)).length;
  
  const hints = [
    `💡 Try words with ${vowels} vowel${vowels !== 1 ? 's' : ''}`,
    `💡 The word starts with "${firstLetter}"`,
    `💡 The word ends with "${lastLetter}"`,
    `💡 It's a ${word.length}-letter word with common letters`,
    `💡 Think about everyday words you use`,
  ];
  
  // Return hints in order based on number of guesses
  const hintIndex = Math.min(guesses.length, hints.length - 1);
  return hints[hintIndex];
}