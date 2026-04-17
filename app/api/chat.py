from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks

from app.schemas import ChatRequest, ChatResponse
from app.config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL,
    VOYAGE_API_KEY, VOYAGE_MODEL, VOYAGE_DIM,
    QDRANT_URL, QDRANT_API_KEY,
    QDRANT_VMEDIA_URL, QDRANT_VMEDIA_API_KEY, VMEDIA_COLLECTIONS,
    COLLECTION_DOCS, COLLECTION_VIDEOS,
    TOP_K, RERANK_TOP_K,
    MEMORY_EXTRACTION_EVERY_N_TURNS,
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


async def _background_extract(user_id: str, session_id: str, turns: list[dict], domain: str) -> None:
    """Background task — extract memories + summary. KHONG BAO GIO raise."""
    logger.info("Background extraction started: user=%s session=%s turns=%d", user_id, session_id, len(turns))
    try:
        from app.ingestion.entity_extractor import extract_memories
        entity_mem = _get_entity_memory()

        # Get previous summary for this session (to update, not create new)
        prev_summary = ""
        try:
            user_entities = await entity_mem.get_user_entities(user_id, limit=50)
            for e in user_entities:
                if e.category == "summary" and e.session_id == session_id:
                    prev_summary = e.text
                    break
        except Exception:
            pass

        records, summary = await extract_memories(
            turns, user_id, session_id, domain or "mặc định", prev_summary,
        )

        # Upsert memory records
        for r in records:
            try:
                await entity_mem.upsert(r)
            except Exception:
                logger.error("Failed to upsert memory record", exc_info=True)

        # Upsert summary (supersedes old summary of same session)
        if summary:
            try:
                await entity_mem.upsert(summary)
            except Exception:
                logger.error("Failed to upsert summary", exc_info=True)

        logger.info("Extracted %d memories + %s summary from session=%s",
                     len(records), "1" if summary else "0", session_id)
    except Exception:
        logger.error("Memory extraction failed for session=%s", session_id, exc_info=True)


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks) -> ChatResponse:
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

    # Trigger entity extraction every N turns
    turn_count = len(memory.get_history(request.session_id)) // 2  # pairs
    logger.info("Entity check: session=%s turn_count=%d trigger_every=%d",
                request.session_id, turn_count, MEMORY_EXTRACTION_EVERY_N_TURNS)
    if turn_count > 0 and turn_count % MEMORY_EXTRACTION_EVERY_N_TURNS == 0:
        recent_turns = memory.get_history(request.session_id)[-(MEMORY_EXTRACTION_EVERY_N_TURNS * 2):]
        user_id = getattr(request, "user_id", None) or request.session_id
        background_tasks.add_task(
            _background_extract,
            user_id=user_id,
            session_id=request.session_id,
            turns=recent_turns,
            domain=request.domain or "mặc định",
        )

    return ChatResponse(
        answer=result["answer"],
        sources=result.get("sources", []),
        session_id=request.session_id,
        suggested_questions=result.get("suggested_questions", []),
    )
