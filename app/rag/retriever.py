from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
from typing import Any

from app.core.voyage_embed import VoyageEmbedder
from app.core.qdrant_store import QdrantStore, VMediaReadOnlyStore


@dataclass
class Hit:
    text: str
    score: float
    source_type: str  # "document" | "video" | "vmedia"
    payload: dict[str, Any] = field(default_factory=dict)
    collection: str = ""


class Retriever:
    def __init__(
        self,
        voyage: VoyageEmbedder,
        qdrant_docs: QdrantStore,
        qdrant_videos: QdrantStore,
        vmedia_store: VMediaReadOnlyStore,
        entity_memory=None,
    ):
        self.voyage = voyage
        self.qdrant_docs = qdrant_docs
        self.qdrant_videos = qdrant_videos
        self.vmedia_store = vmedia_store
        self.entity_memory = entity_memory

    def _search_one(
        self,
        store: QdrantStore | VMediaReadOnlyStore,
        source_type: str,
        query_vec: list[float],
        top_k: int,
        qdrant_filter: dict | None = None,
    ) -> list[Hit]:
        try:
            hits = store.search(query_vec, limit=top_k, filter=qdrant_filter)
            col = getattr(store, "collection", "vmedia")
            return [
                Hit(
                    text=h.get("payload", {}).get("text", ""),
                    score=h.get("score", 0.0),
                    source_type=source_type,
                    payload=h.get("payload", {}),
                    collection=h.get("_vmedia_collection", col) if source_type == "vmedia" else col,
                )
                for h in hits
            ]
        except Exception:
            return []

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        sources: list[str] | None = None,
        domain_filter: str | None = None,
    ) -> list[Hit]:
        if sources is None:
            sources = ["documents", "videos"]

        query_vec = self.voyage.embed_query(query)

        # Build Qdrant filter for domain if specified
        qdrant_filter = None
        if domain_filter:
            qdrant_filter = {
                "should": [
                    {"key": "domain", "match": {"value": domain_filter}},
                    # Also match docs without domain field (backward compat)
                    {"is_empty": {"key": "domain"}},
                ]
            }

        tasks: list[tuple] = []
        if "documents" in sources:
            tasks.append((self.qdrant_docs, "document", query_vec, top_k, qdrant_filter))
        if "videos" in sources:
            tasks.append((self.qdrant_videos, "video", query_vec, top_k, qdrant_filter))
        if "vmedia" in sources and self.vmedia_store.api_key:
            tasks.append((self.vmedia_store, "vmedia", query_vec, top_k, None))

        all_hits: list[Hit] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futures = [ex.submit(self._search_one, *t) for t in tasks]
            for f in concurrent.futures.as_completed(futures):
                all_hits.extend(f.result())

        seen: set[str] = set()
        deduped: list[Hit] = []
        for hit in all_hits:
            key = f"{hit.source_type}::{hit.text[:80]}"
            if key not in seen:
                seen.add(key)
                deduped.append(hit)

        deduped.sort(key=lambda h: h.score, reverse=True)
        return deduped[:top_k]

    async def retrieve_with_memory(
        self,
        query: str,
        user_id: str,
        session_id: str,
        recent_sessions: list[str],
        domain: str | None = None,
        top_k: int = 10,
        sources: list[str] | None = None,
    ) -> dict:
        """Retrieve documents + memory entities in parallel.

        Returns {"documents": list[Hit], "memory": list[Entity]}.
        Memory is optional — graceful degrade if entity_memory unavailable.
        """
        import asyncio
        import logging

        logger = logging.getLogger(__name__)

        # Documents (sync, run in thread)
        loop = asyncio.get_event_loop()
        doc_task = loop.run_in_executor(
            None, lambda: self.retrieve(query, top_k, sources, domain)
        )

        # Memory (async, graceful)
        async def _safe_memory():
            if self.entity_memory is None:
                return []
            try:
                return await self.entity_memory.retrieve(
                    user_id=user_id,
                    query=query,
                    current_session_id=session_id,
                    recent_sessions=recent_sessions,
                    domain=domain,
                )
            except Exception as e:
                logger.error("Memory retrieval failed: %s", e, exc_info=True)
                return []

        docs, memory = await asyncio.gather(doc_task, _safe_memory())
        return {"documents": docs, "memory": memory}
