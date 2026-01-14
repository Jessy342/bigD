import type { CSSProperties } from 'react';
import { ArrowDownRight, ArrowUpRight, Minus, Sparkles } from 'lucide-react';

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

const formatSimilarity = (similarity: number) => {
  if (!Number.isFinite(similarity)) {
    return '--';
  }
  const clamped = Math.max(0, Math.min(1, similarity));
  const percent = Math.round(clamped * 1000) / 10;
  return `${percent}%`;
};

const MAX_RANK_FOR_BAR = 20000;

const rankToFill = (rank: number) => {
  if (!Number.isFinite(rank) || rank <= 1) {
    return 1;
  }
  const clamped = Math.max(1, Math.min(MAX_RANK_FOR_BAR, rank));
  const ratio = Math.log(clamped) / Math.log(MAX_RANK_FOR_BAR);
  return Math.max(0.03, Math.min(1, 1 - ratio));
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
  const byTimeAsc = [...guesses].sort((a, b) => a.timestamp - b.timestamp);
  let bestRankAtTime = Number.POSITIVE_INFINITY;
  const trendByKey = new Map<string, 'up' | 'down' | 'same' | 'first'>();
  for (const entry of byTimeAsc) {
    let trend: 'up' | 'down' | 'same' | 'first' = 'same';
    if (bestRankAtTime === Number.POSITIVE_INFINITY) {
      trend = 'first';
    } else if (entry.rank < bestRankAtTime) {
      trend = 'up';
    } else if (entry.rank > bestRankAtTime) {
      trend = 'down';
    }
    if (entry.rank < bestRankAtTime) {
      bestRankAtTime = entry.rank;
    }
    trendByKey.set(guessKey(entry), trend);
  }
  const orderedGuesses = [
    bestEntry,
    ...(recentEntry ? [recentEntry] : []),
    ...byRecent.filter((entry) => {
      const key = guessKey(entry);
      return key !== bestKey && key !== recentKey;
    }),
  ];

  return (
    <div className="guess-list">
      {orderedGuesses.map((guess, index) => {
        const isBest = guessKey(guess) === bestKey;
        const trend = trendByKey.get(guessKey(guess)) ?? 'same';

        const trendIcon =
          trend === 'up' ? (
            <ArrowUpRight className="guess-trend-icon guess-trend-up" />
          ) : trend === 'down' ? (
            <ArrowDownRight className="guess-trend-icon guess-trend-down" />
          ) : trend === 'first' ? (
            <Sparkles className="guess-trend-icon guess-trend-first" />
          ) : (
            <Minus className="guess-trend-icon guess-trend-same" />
          );

        const fill = rankToFill(guess.rank);
        const hue = Math.round(6 + (120 * fill));
        const fillColor = `hsl(${hue} 65% 45% / 0.85)`;
        const accentColor = `hsl(${hue} 70% 55% / 0.95)`;
        const barStyle = {
          ['--fill' as const]: fill,
          ['--fill-color' as const]: fillColor,
          ['--accent-color' as const]: accentColor,
        } as CSSProperties;

        return (
          <div
            key={`${guess.word}-${guess.timestamp}-${index}`}
            className={`guess-row ${guess.rank === 1 ? 'guess-row-win' : ''}`}
            style={barStyle}
          >
            <div className="guess-fill" />
            <div className="guess-word">{guess.word}</div>
            <div className="guess-meta">
              {guess.show_similarity && (
                <span className="guess-similarity">{formatSimilarity(guess.similarity)}</span>
              )}
              <span className="guess-trend">{trendIcon}</span>
              <span className={`guess-rank ${isBest ? 'guess-rank-best' : ''}`}>
                {guess.rank}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
