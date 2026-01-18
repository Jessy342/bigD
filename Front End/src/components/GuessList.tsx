import type { CSSProperties } from 'react';

export type GuessEntry = {
  word: string;
  rank: number;
  similarity: number;
  timestamp: number;
  show_similarity?: boolean;
};

interface GuessListProps {
  guesses: GuessEntry[];
}

const MAX_RANK_FOR_BAR = 20000;
const MIN_FILL = 0.06;

const lerp = (start: number, end: number, t: number) => start + (end - start) * t;
const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const FILL_POINTS = [
  { rank: 1, fill: 1 },
  { rank: 30, fill: 0.95 },
  { rank: 150, fill: 0.78 },
  { rank: 600, fill: 0.5 },
  { rank: 1000, fill: 0.34 },
  { rank: 5000, fill: 0.12 },
  { rank: MAX_RANK_FOR_BAR, fill: MIN_FILL },
];

const rankToFill = (rank: number) => {
  if (!Number.isFinite(rank)) {
    return MIN_FILL;
  }
  const capped = clamp(rank, 1, MAX_RANK_FOR_BAR);
  for (let i = 0; i < FILL_POINTS.length - 1; i += 1) {
    const start = FILL_POINTS[i];
    const end = FILL_POINTS[i + 1];
    if (capped <= end.rank) {
      const t = (capped - start.rank) / (end.rank - start.rank);
      return Math.max(MIN_FILL, lerp(start.fill, end.fill, t));
    }
  }
  return MIN_FILL;
};

type Hsl = { h: number; s: number; l: number };

const COLOR_STOPS: Array<{ rank: number; color: Hsl }> = [
  { rank: 1, color: { h: 128, s: 70, l: 48 } },
  { rank: 200, color: { h: 120, s: 72, l: 50 } },
  { rank: 800, color: { h: 36, s: 85, l: 55 } },
  { rank: 5000, color: { h: 8, s: 62, l: 46 } },
  { rank: MAX_RANK_FOR_BAR, color: { h: 8, s: 35, l: 40 } },
];

const hslToCss = (color: Hsl, alpha: number) =>
  `hsl(${Math.round(color.h)} ${Math.round(color.s)}% ${Math.round(color.l)}% / ${alpha})`;

const rankToColors = (rank: number) => {
  const capped = clamp(Number.isFinite(rank) ? rank : MAX_RANK_FOR_BAR, 1, MAX_RANK_FOR_BAR);
  let start = COLOR_STOPS[0];
  let end = COLOR_STOPS[COLOR_STOPS.length - 1];
  for (let i = 0; i < COLOR_STOPS.length - 1; i += 1) {
    if (capped <= COLOR_STOPS[i + 1].rank) {
      start = COLOR_STOPS[i];
      end = COLOR_STOPS[i + 1];
      break;
    }
  }
  const t = (capped - start.rank) / (end.rank - start.rank || 1);
  const base = {
    h: lerp(start.color.h, end.color.h, t),
    s: lerp(start.color.s, end.color.s, t),
    l: lerp(start.color.l, end.color.l, t),
  };
  const accent = {
    h: base.h,
    s: clamp(base.s + 8, 0, 95),
    l: clamp(base.l + 6, 0, 70),
  };
  return {
    fill: hslToCss(base, 0.9),
    accent: hslToCss(accent, 0.95),
  };
};

const guessKey = (guess: GuessEntry) => `${guess.word}-${guess.timestamp}`;

export function GuessList({ guesses }: GuessListProps) {
  if (!guesses.length) {
    return <div className="guess-list-empty">No guesses yet. Try something bold.</div>;
  }

  let bestEntry = guesses[0];
  for (const entry of guesses) {
    if (entry.rank < bestEntry.rank) {
      bestEntry = entry;
      continue;
    }
    if (entry.rank === bestEntry.rank && entry.timestamp < bestEntry.timestamp) {
      bestEntry = entry;
    }
  }
  const bestKey = guessKey(bestEntry);
  const byRecent = [...guesses].sort((a, b) => b.timestamp - a.timestamp);
  const recentEntry = byRecent.find((entry) => guessKey(entry) !== bestKey);
  const recentKey = recentEntry ? guessKey(recentEntry) : null;
  const remaining = guesses.filter((entry) => {
    const key = guessKey(entry);
    return key !== bestKey && key !== recentKey;
  });
  remaining.sort((a, b) => {
    if (a.rank !== b.rank) {
      return a.rank - b.rank;
    }
    return a.timestamp - b.timestamp;
  });
  const orderedGuesses = [bestEntry, ...(recentEntry ? [recentEntry] : []), ...remaining];

  return (
    <div className="guess-list">
      {orderedGuesses.map((guess) => {
        const isBest = guessKey(guess) === bestKey;
        const fill = rankToFill(guess.rank);
        const { fill: fillColor, accent: accentColor } = rankToColors(guess.rank);
        const barStyle = {
          ['--fill' as const]: fill,
          ['--fill-color' as const]: fillColor,
          ['--accent-color' as const]: accentColor,
        } as CSSProperties;

        return (
          <div
            key={guessKey(guess)}
            className={`guess-row ${guess.rank === 1 ? 'guess-row-win' : ''}`}
            style={barStyle}
          >
            <div className="guess-bar">
              <div className="guess-bar-track">
                <div className="guess-bar-fill" />
              </div>
              <div className="guess-word">{guess.word}</div>
            </div>
            <div className={`guess-rank ${isBest ? 'guess-rank-best' : ''}`}>
              <span className="guess-rank-value">{guess.rank}</span>
              {guess.show_similarity && (
                <span className="guess-similarity">{Math.round(guess.similarity * 100)}%</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
