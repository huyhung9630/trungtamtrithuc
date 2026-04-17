from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import re

from app.core.claude_client import ClaudeClient
from app.rag.retriever import Retriever
from app.rag.reranker import CrossEncoderReranker
from app.rag.prompt_builder import build_system_prompt, build_context_block

_SUGGESTION_PATTERN = re.compile(
    r"\n*---GỢI Ý---\s*\n(.*)",
    re.DOTALL,
)


def _extract_suggestions(answer: str) -> tuple[str, list[str]]:
    """Split answer into (clean_answer, suggested_questions)."""
    m = _SUGGESTION_PATTERN.search(answer)
    if not m:
        return answer, []
    clean = answer[: m.start()].rstrip()
    raw = m.group(1).strip()
    questions = [
        re.sub(r"^\d+\.\s*", "", line).strip()
        for line in raw.splitlines()
        if line.strip()
    ]
    return clean, [q for q in questions if q]


def _confidence(top_score: float) -> str:
    if top_score >= 0.7:
        return "high"
    if top_score >= 0.4:
        return "medium"
    return "low"


class RAGChain:
    def __init__(
        self,
        retriever: Retriever,
        reranker: CrossEncoderReranker,
        claude: ClaudeClient,
        top_k: int = 10,
        rerank_top_k: int = 3,
    ):
        self.retriever = retriever
        self.reranker = reranker
        self.claude = claude
        self.top_k = top_k
        self.rerank_top_k = rerank_top_k

    def answer(
        self,
        query: str,
        history: list[dict] | None = None,
        expert_domain: str | None = None,
        sources_filter: list[str] | None = None,
    ) -> dict[str, Any]:
        hits = self.retriever.retrieve(
            query, top_k=self.top_k, sources=sources_filter,
            domain_filter=expert_domain,
        )
        hits = self.reranker.rerank(query, hits, top_k=self.rerank_top_k)

        system_prompt = build_system_prompt(expert_domain)
        context_block, source_mapping = build_context_block(hits)

        messages = list(history or [])
        messages.append({"role": "user", "content": query})

        answer_text = self.claude.generate(
            system_prompt=system_prompt,
            context_block=context_block,
            messages=messages,
        )

        clean_answer, suggested_questions = _extract_suggestions(answer_text)

        # If AI didn't cite sources (e.g. casual greeting), hide sources from frontend
        has_sources = "Nguồn:" in clean_answer or "nguồn:" in clean_answer.lower()

        top_score = hits[0].score if hits else 0.0
        return {
            "answer": clean_answer,
            "sources": source_mapping if has_sources else [],
            "confidence": _confidence(top_score),
            "suggested_questions": suggested_questions,
        }

    async def answer_stream(
        self,
        query: str,
        history: list[dict] | None = None,
        expert_domain: str | None = None,
        sources_filter: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        hits = self.retriever.retrieve(query, top_k=self.top_k, sources=sources_filter)
        hits = self.reranker.rerank(query, hits, top_k=self.rerank_top_k)

        system_prompt = build_system_prompt(expert_domain)
        context_block, source_mapping = build_context_block(hits)

        messages = list(history or [])
        messages.append({"role": "user", "content": query})

        yield {"type": "meta", "sources": source_mapping}

        for chunk in self.claude.generate_stream(
            system_prompt=system_prompt,
            context_block=context_block,
            messages=messages,
        ):
            yield {"type": "delta", "text": chunk}

        yield {"type": "done"}
