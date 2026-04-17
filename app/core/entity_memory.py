"""Entity Memory CRUD + retrieve cho Qdrant ttt_memory collection.

Xu ly:
  - Upsert voi semantic dedup + conflict resolution
  - Hybrid retrieve: near sessions + long-term profile
  - GDPR delete
  - Graceful degrade (khong raise exception)
"""
from __future__ import annotations

import logging
import math
import time
import uuid
from typing import Optional

import requests

from app.config import (
    QDRANT_URL,
    QDRANT_API_KEY,
    VOYAGE_DIM,
    MEMORY_COLLECTION,
    MEMORY_DUP_THRESHOLD,
    MEMORY_CONFLICT_THRESHOLD,
    MEMORY_RETRIEVE_TOP_K,
    MEMORY_NEAR_SEARCH_LIMIT,
    MEMORY_LONGTERM_SEARCH_LIMIT,
)
from app.core.entity_schema import Entity
from app.core.voyage_embed import VoyageEmbedder

logger = logging.getLogger(__name__)


def _combined_score(
    entity: Entity,
    semantic_score: float,
    now: int,
    current_session_id: str,
) -> float:
    """Rerank score: 50% semantic + 25% recency + 15% session + 10% frequency."""
    s_sem = semantic_score
    age_days = (now - entity.created_at) / 86400
    s_recency = math.exp(-0.099 * age_days)  # half-life 7 days
    s_session = 1.0 if entity.session_id == current_session_id else 0.0
    s_freq = min(entity.access_count / 10, 1.0)
    return 0.50 * s_sem + 0.25 * s_recency + 0.15 * s_session + 0.10 * s_freq


class EntityMemory:
    """CRUD + retrieve cho entity memory trong Qdrant."""

    def __init__(self, embedder: VoyageEmbedder | None = None):
        self.url = QDRANT_URL.rstrip("/")
        self.api_key = QDRANT_API_KEY
        self.collection = MEMORY_COLLECTION
        self.embedder = embedder
        self._vector_name = ""

    def _headers(self) -> dict:
        return {"api-key": self.api_key, "Content-Type": "application/json"}

    def _req(self, method: str, path: str, json_body=None) -> dict:
        resp = requests.request(
            method, f"{self.url}{path}",
            headers=self._headers(), json=json_body, timeout=60,
        )
        if not resp.ok:
            logger.error("qdrant %s %s -> %s: %s", method, path, resp.status_code, resp.text[:200])
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    def _get_embedder(self) -> VoyageEmbedder:
        if self.embedder is None:
            from app.config import VOYAGE_API_KEY, VOYAGE_MODEL
            self.embedder = VoyageEmbedder(api_key=VOYAGE_API_KEY, model=VOYAGE_MODEL)
        return self.embedder

    def _embed(self, text: str) -> list[float]:
        return self._get_embedder().embed_query(text)

    def _search(
        self,
        query_vec: list[float],
        must_filters: list[dict],
        limit: int = 5,
        score_threshold: float | None = None,
    ) -> list[dict]:
        body: dict = {
            "vector": {"name": self._vector_name, "vector": query_vec},
            "limit": limit,
            "with_payload": True,
            "filter": {"must": must_filters},
        }
        if score_threshold is not None:
            body["score_threshold"] = score_threshold
        result = self._req("POST", f"/collections/{self.collection}/points/search", body)
        return result.get("result", [])

    async def upsert(self, entity: Entity) -> None:
        """Insert hoac update entity, xu ly dedup + conflict.

        Summary: luon supersede summary cu cua cung session
        Entity: Score >= 0.88 duplicate, 0.75-0.88 conflict, < 0.75 new
        """
        try:
            vec = self._embed(entity.text)

            # Summary: supersede old summary of same session
            if entity.category == "summary":
                old_summaries = self._search(
                    query_vec=vec,
                    must_filters=[
                        {"key": "user_id", "match": {"value": entity.user_id}},
                        {"key": "session_id", "match": {"value": entity.session_id}},
                        {"key": "category", "match": {"value": "summary"}},
                        {"key": "status", "match": {"value": "active"}},
                    ],
                    limit=5,
                )
                for old in old_summaries:
                    old_id = old.get("id")
                    if old_id:
                        self._req("PUT",
                            f"/collections/{self.collection}/points/payload?wait=true",
                            {"payload": {"status": "superseded", "superseded_by": entity.memory_id}, "points": [old_id]},
                        )
                        logger.info("Superseded old summary id=%s for session=%s", old_id, entity.session_id)

                # Insert new summary
                point = {
                    "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, entity.memory_id)),
                    "vector": {self._vector_name: vec},
                    "payload": entity.model_dump(),
                }
                self._req("PUT", f"/collections/{self.collection}/points?wait=true", {"points": [point]})
                logger.info("Summary upserted: session=%s turns=%d", entity.session_id, entity.turn_count)
                return

            # Non-summary: dedup + conflict
            similar = self._search(
                query_vec=vec,
                must_filters=[
                    {"key": "user_id", "match": {"value": entity.user_id}},
                    {"key": "category", "match": {"value": entity.category}},
                    {"key": "status", "match": {"value": "active"}},
                ],
                limit=3,
                score_threshold=MEMORY_CONFLICT_THRESHOLD,
            )

            now = int(time.time())

            if similar:
                top_score = similar[0].get("score", 0)
                top_id = similar[0].get("id")

                if top_score >= MEMORY_DUP_THRESHOLD:
                    # Duplicate — just touch
                    old_payload = similar[0].get("payload", {})
                    self._req("PUT",
                        f"/collections/{self.collection}/points/payload?wait=true",
                        {
                            "payload": {
                                "last_accessed": now,
                                "access_count": old_payload.get("access_count", 0) + 1,
                            },
                            "points": [top_id],
                        },
                    )
                    logger.info("Entity duplicate (score=%.3f), touched id=%s", top_score, top_id)
                    return

                # Conflict — supersede old
                self._req("PUT",
                    f"/collections/{self.collection}/points/payload?wait=true",
                    {
                        "payload": {
                            "status": "superseded",
                            "superseded_by": entity.memory_id,
                        },
                        "points": [top_id],
                    },
                )
                entity.supersedes = [str(top_id)]
                logger.info("Entity conflict (score=%.3f), superseded id=%s", top_score, top_id)

            # Insert new entity
            point = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, entity.memory_id)),
                "vector": {self._vector_name: vec},
                "payload": entity.model_dump(),
            }
            self._req("PUT",
                f"/collections/{self.collection}/points?wait=true",
                {"points": [point]},
            )
            logger.info("Entity upserted: id=%s cat=%s text='%s'",
                        entity.memory_id, entity.category, entity.text[:50])

        except Exception:
            logger.error("Entity upsert failed", exc_info=True)

    async def retrieve(
        self,
        user_id: str,
        query: str,
        current_session_id: str,
        recent_sessions: list[str],
        domain: Optional[str] = None,
        k: int | None = None,
    ) -> list[Entity]:
        """Hybrid retrieve: near sessions + long-term profile/preference."""
        if k is None:
            k = MEMORY_RETRIEVE_TOP_K

        try:
            vec = self._embed(query)

            base_filter = [
                {"key": "user_id", "match": {"value": user_id}},
                {"key": "status", "match": {"value": "active"}},
            ]
            if domain:
                base_filter.append(
                    {"key": "domain", "match": {"any": [domain, "mặc định"]}}
                )

            # Query 1: Near context (recent sessions)
            near_filter = base_filter.copy()
            if recent_sessions:
                near_filter.append(
                    {"key": "session_id", "match": {"any": recent_sessions}}
                )
            near = self._search(vec, near_filter, limit=MEMORY_NEAR_SEARCH_LIMIT)

            # Query 2: Long-term (persistent + preference)
            longterm_filter = base_filter.copy()
            longterm_filter.append(
                {"key": "category", "match": {"any": ["persistent", "preference"]}}
            )
            longterm = self._search(vec, longterm_filter, limit=MEMORY_LONGTERM_SEARCH_LIMIT)

            # Merge + dedup by memory_id
            seen: set[str] = set()
            merged: list[tuple[Entity, float]] = []
            for hit in near + longterm:
                payload = hit.get("payload", {})
                eid = payload.get("memory_id", "")
                if eid in seen:
                    continue
                seen.add(eid)
                try:
                    entity = Entity(**payload)
                    score = hit.get("score", 0.0)
                    merged.append((entity, score))
                except Exception:
                    continue

            # Rerank by combined score
            now = int(time.time())
            merged.sort(
                key=lambda pair: _combined_score(pair[0], pair[1], now, current_session_id),
                reverse=True,
            )
            top_k = [e for e, _ in merged[:k]]

            # Touch top-k (update last_accessed)
            if top_k:
                point_ids = [
                    str(uuid.uuid5(uuid.NAMESPACE_DNS, e.memory_id))
                    for e in top_k
                ]
                try:
                    self._req("PUT",
                        f"/collections/{self.collection}/points/payload?wait=false",
                        {
                            "payload": {"last_accessed": now},
                            "points": point_ids,
                        },
                    )
                except Exception:
                    pass  # non-critical

            logger.info("Memory retrieve: user=%s query='%s' near=%d longterm=%d → top%d",
                        user_id, query[:30], len(near), len(longterm), len(top_k))
            return top_k

        except Exception:
            logger.error("Memory retrieve failed", exc_info=True)
            return []

    async def delete_by_user(self, user_id: str) -> int:
        """GDPR: xoa moi entity cua user."""
        try:
            self._req("POST",
                f"/collections/{self.collection}/points/delete",
                {"filter": {"must": [{"key": "user_id", "match": {"value": user_id}}]}},
            )
            logger.info("Deleted all entities for user=%s", user_id)
            return 1  # success
        except Exception:
            logger.error("Delete by user failed", exc_info=True)
            return 0

    async def get_user_entities(self, user_id: str, limit: int = 100) -> list[Entity]:
        """Lay moi entity active cua user."""
        try:
            result = self._req("POST",
                f"/collections/{self.collection}/points/scroll",
                {
                    "filter": {
                        "must": [
                            {"key": "user_id", "match": {"value": user_id}},
                            {"key": "status", "match": {"value": "active"}},
                        ]
                    },
                    "limit": limit,
                    "with_payload": True,
                },
            )
            points = result.get("result", {}).get("points", [])
            entities = []
            for p in points:
                try:
                    entities.append(Entity(**p.get("payload", {})))
                except Exception:
                    continue
            return entities
        except Exception:
            logger.error("Get user entities failed", exc_info=True)
            return []
