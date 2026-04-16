from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.core.claude_client import ClaudeClient
from app.rag.retriever import Retriever
from app.rag.reranker import ScoreReranker
from app.rag.prompt_builder import build_system_prompt, build_context_block


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
        reranker: ScoreReranker,
        claude: ClaudeClient,
        top_k: int = 7,
        rerank_top_k: int = 5,
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
        hits = self.retriever.retrieve(query, top_k=self.top_k, sources=sources_filter)
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

        top_score = hits[0].score if hits else 0.0
        return {
            "answer": answer_text,
            "sources": source_mapping,
            "confidence": _confidence(top_score),
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
