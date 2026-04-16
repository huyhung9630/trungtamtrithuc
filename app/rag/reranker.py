from __future__ import annotations

import logging
import re
from collections import Counter

from app.rag.retriever import Hit

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    return re.findall(r'\w+', text.lower())


def _keyword_overlap_score(query: str, text: str) -> float:
    q_tokens = Counter(_tokenize(query))
    t_tokens = set(_tokenize(text))
    if not q_tokens:
        return 0.0
    overlap = sum(1 for t in q_tokens if t in t_tokens)
    return overlap / len(q_tokens)


class ScoreReranker:
    """Rule-based reranker — NO Claude API calls. Uses cosine score + keyword overlap."""

    def rerank(self, query: str, hits: list[Hit], top_k: int = 5) -> list[Hit]:
        if not hits:
            return hits

        for h in hits:
            keyword_bonus = _keyword_overlap_score(query, h.text) * 0.15
            h.score = h.score + keyword_bonus

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]
