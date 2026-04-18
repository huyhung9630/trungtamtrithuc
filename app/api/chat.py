from __future__ import annotations

import logging

from fastapi import APIRouter

from app.schemas import ChatRequest, ChatResponse
from app.config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL,
    VOYAGE_API_KEY, VOYAGE_MODEL, VOYAGE_DIM,
    QDRANT_URL, QDRANT_API_KEY,
    QDRANT_VMEDIA_URL, QDRANT_VMEDIA_API_KEY, VMEDIA_COLLECTIONS,
    COLLECTION_DOCS, COLLECTION_VIDEOS,
    TOP_K, RERANK_TOP_K,
)
from app.core.claude_client import ClaudeClient
from app.core.voyage_embed import VoyageEmbedder
from app.core.qdrant_store import QdrantStore, VMediaReadOnlyStore
from app.core.session_memory import memory
from app.core.entity_memory import EntityMemory
from app.rag.retriever import Retriever
from app.rag.reranker import CrossEncoderReranker
from app.rag.chain import RAGChain

logger = logging.getLogger(__name__)

router = APIRouter()

_chain: RAGChain | None = None
_entity_memory: EntityMemory | None = None


def _get_entity_memory() -> EntityMemory:
    global _entity_memory
    if _entity_memory is None:
        _entity_memory = EntityMemory()
    return _entity_memory


def _get_chain() -> RAGChain:
    global _chain
    if _chain is not None:
        return _chain

    voyage = VoyageEmbedder(api_key=VOYAGE_API_KEY, model=VOYAGE_MODEL)
    claude = ClaudeClient(api_key=ANTHROPIC_API_KEY, model=CLAUDE_MODEL)

    qdrant_docs = QdrantStore(
        url=QDRANT_URL, api_key=QDRANT_API_KEY,
        collection=COLLECTION_DOCS, vector_size=VOYAGE_DIM,
    )
    qdrant_videos = QdrantStore(
        url=QDRANT_URL, api_key=QDRANT_API_KEY,
        collection=COLLECTION_VIDEOS, vector_size=VOYAGE_DIM,
    )
    vmedia_store = VMediaReadOnlyStore(
        url=QDRANT_VMEDIA_URL, vmedia_api_key=QDRANT_VMEDIA_API_KEY,
        collections=VMEDIA_COLLECTIONS,
    )

    entity_mem = _get_entity_memory()

    retriever = Retriever(
        voyage=voyage,
        qdrant_docs=qdrant_docs,
        qdrant_videos=qdrant_videos,
        vmedia_store=vmedia_store,
        entity_memory=entity_mem,
    )
    reranker = CrossEncoderReranker()

    _chain = RAGChain(
        retriever=retriever,
        reranker=reranker,
        claude=claude,
        top_k=10,
        rerank_top_k=3,
    )
    return _chain


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    chain = _get_chain()

    history = memory.get_history(request.session_id)

    domain = request.domain if request.domain and request.domain not in ("general", "mặc định") else None

    try:
        result = chain.answer(
            query=request.message,
            history=history,
            expert_domain=domain,
        )
    except Exception as exc:
        logger.exception("RAG chain error: %s", exc)
        return ChatResponse(
            answer=f"Lỗi xử lý: {exc}",
            sources=[],
            session_id=request.session_id,
        )

    memory.add_turn(request.session_id, request.message, result["answer"])

    return ChatResponse(
        answer=result["answer"],
        sources=result.get("sources", []),
        session_id=request.session_id,
        suggested_questions=result.get("suggested_questions", []),
    )
