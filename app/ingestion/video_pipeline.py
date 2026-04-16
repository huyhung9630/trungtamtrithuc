from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core import config
from app.core.chunker import chunk_transcript_with_timestamps
from app.core.voyage_embed import VoyageEmbedder
from app.core.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    doc_id: str
    num_chunks: int
    num_pages: int
    source_name: str


def build_video_link(payload: dict) -> str:
    if payload.get("file_source") == "youtube":
        video_id = payload.get("video_id", "")
        start_sec = int(payload.get("start_sec", 0))
        return f"https://www.youtube.com/watch?v={video_id}&t={start_sec}s"
    video_id = payload.get("video_id", "")
    start_sec = int(payload.get("start_sec", 0))
    return f"/files/videos/{video_id}#t={start_sec}"


def ensure_collections() -> None:
    store = QdrantStore(
        url=config.QDRANT_URL,
        api_key=config.QDRANT_API_KEY,
        collection=config.COLLECTION_VIDEOS,
        vector_size=config.VOYAGE_DIM,
    )
    store.ensure_collection()
    logger.info("Ensured collection: %s", config.COLLECTION_VIDEOS)


def _upsert_video_chunks(
    segments: list[dict],
    video_id: str,
    title: str,
    source_url: str | None,
    file_source: str,
    metadata: dict | None,
) -> int:
    uploaded_at = datetime.now(timezone.utc).isoformat()
    chunks = chunk_transcript_with_timestamps(segments, max_tokens=500)

    if not chunks:
        return 0

    embedder = VoyageEmbedder(api_key=config.VOYAGE_API_KEY, model=config.VOYAGE_MODEL)
    store = QdrantStore(
        url=config.QDRANT_URL,
        api_key=config.QDRANT_API_KEY,
        collection=config.COLLECTION_VIDEOS,
        vector_size=config.VOYAGE_DIM,
    )

    texts = [c["text"] for c in chunks]
    vectors = embedder.embed_documents(texts)

    points: list[dict] = []
    for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
        start_sec = chunk["start"]
        end_sec = chunk["end"]
        point_id = str(uuid.uuid5(
            uuid.NAMESPACE_DNS,
            f"{video_id}-{i}",
        ))
        payload: dict = {
            "source_type": "video",
            "video_id": video_id,
            "title": title,
            "source_url": source_url,
            "start_sec": start_sec,
            "end_sec": end_sec,
            "text": chunk["text"],
            "segment_ids": chunk.get("segment_ids", []),
            "uploaded_at": uploaded_at,
            "file_source": file_source,
        }
        if file_source == "youtube" and source_url:
            payload["youtube_url"] = f"https://www.youtube.com/watch?v={video_id}&t={int(start_sec)}s"
        if metadata:
            payload["extra_metadata"] = metadata
        points.append({"id": point_id, "vector": vector, "payload": payload})

    store.upsert(points)
    logger.info(
        "Upserted %d video chunks for video_id=%s title=%s",
        len(points), video_id, title,
    )
    return len(points)


def ingest_video_file(
    local_path: str,
    original_name: str,
    metadata: dict | None = None,
) -> IngestResult:
    from app.ingestion.video_transcriber import WhisperTranscriber

    path = Path(local_path)
    logger.info("Transcribing local video: %s", original_name)

    transcriber = WhisperTranscriber()
    result = transcriber.transcribe(path)
    segments = result["segments"]

    import hashlib
    video_id = hashlib.sha256(str(path).encode()).hexdigest()[:16]

    num_chunks = _upsert_video_chunks(
        segments=segments,
        video_id=video_id,
        title=original_name,
        source_url=None,
        file_source="local",
        metadata=metadata,
    )
    return IngestResult(
        doc_id=video_id,
        num_chunks=num_chunks,
        num_pages=1,
        source_name=original_name,
    )


def ingest_youtube(
    url: str,
    metadata: dict | None = None,
) -> IngestResult:
    from app.ingestion.youtube_fetcher import fetch_youtube_transcript

    logger.info("Ingesting YouTube video: %s", url)
    data = fetch_youtube_transcript(url)

    num_chunks = _upsert_video_chunks(
        segments=data["segments"],
        video_id=data["video_id"],
        title=data["title"],
        source_url=data["source_url"],
        file_source="youtube",
        metadata=metadata,
    )
    return IngestResult(
        doc_id=data["video_id"],
        num_chunks=num_chunks,
        num_pages=1,
        source_name=data["title"] or url,
    )
