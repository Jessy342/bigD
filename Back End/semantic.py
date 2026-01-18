# backend/semantic.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple

try:
    import numpy as np
except Exception:
    np = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


@dataclass
class SecretIndex:
    secret: str
    secret_embedding: np.ndarray
    sorted_neg_similarities: np.ndarray
    candidate_count: int


class SemanticRanker:
    def __init__(self, candidate_words: List[str], model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        if np is None:
            raise RuntimeError("numpy is required for SemanticRanker.")
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers is required for SemanticRanker.")
        self.model = SentenceTransformer(model_name)
        self.candidate_words = candidate_words
        self._candidate_embeddings = self._normalize_matrix(self._embed_words(candidate_words))
        self._guess_cache: Dict[str, np.ndarray] = {}
        self._secret_cache: Dict[str, SecretIndex] = {}

    def _embed_words(self, words: List[str]) -> np.ndarray:
        embeddings = self.model.encode([w.lower() for w in words], normalize_embeddings=False, show_progress_bar=False)
        return np.array(embeddings, dtype=np.float32)

    def _normalize_matrix(self, mat: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return mat / norms

    def _embed_single(self, word: str) -> np.ndarray:
        key = word.lower()
        cached = self._guess_cache.get(key)
        if cached is not None:
            return cached
        vec = self.model.encode([key], normalize_embeddings=False, show_progress_bar=False)
        arr = np.array(vec[0], dtype=np.float32)
        arr = _normalize(arr)
        self._guess_cache[key] = arr
        return arr

    def _build_secret_index(self, secret: str) -> SecretIndex:
        key = secret.lower()
        cached = self._secret_cache.get(key)
        if cached is not None:
            return cached
        secret_emb = self._embed_single(secret)
        sims = np.dot(self._candidate_embeddings, secret_emb)
        sorted_neg = np.sort(-sims)
        index = SecretIndex(
            secret=secret.upper(),
            secret_embedding=secret_emb,
            sorted_neg_similarities=sorted_neg,
            candidate_count=len(sims),
        )
        self._secret_cache[key] = index
        return index

    def rank_guess(self, guess: str, secret: str) -> Tuple[int, float]:
        if guess.strip().upper() == secret.strip().upper():
            return 1, 1.0
        secret_index = self._build_secret_index(secret)
        guess_emb = self._embed_single(guess)
        similarity = float(np.dot(secret_index.secret_embedding, guess_emb))
        rank = 1 + int(np.searchsorted(secret_index.sorted_neg_similarities, -similarity, side="left"))
        return rank, similarity
