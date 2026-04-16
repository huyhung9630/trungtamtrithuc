from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core import config
from app.core.chunker import chunk_text
from app.core.voyage_embed import VoyageEmbedder
from app.core.qdrant_store import QdrantStore
from app.ingestion.doc_parser import parse

logger = logging.getLogger(__name__)

_LOG_DIR = config.DATA_DIR / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_file_handler = logging.FileHandler(
    _LOG_DIR / f"ingest-{datetime.now().strftime('%Y%m%d')}.log",
    encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
logging.getLogger().addHandler(_file_handler)


@dataclass
class IngestResult:
    doc_id: str
    num_chunks: int
    num_pages: int
    source_name: str


def ensure_collections() -> None:
    store = QdrantStore(
        url=config.QDRANT_URL,
        api_key=config.QDRANT_API_KEY,
        collection=config.COLLECTION_DOCS,
        vector_size=config.VOYAGE_DIM,
    )
    store.ensure_collection()
    logger.info("Ensured collection: %s", config.COLLECTION_DOCS)


def ingest_document(
    file_path: str,
    original_name: str,
    metadata: dict | None = None,
) -> IngestResult:
    path = Path(file_path)
    logger.info("Ingesting document: %s", original_name)

    parsed = parse(path)
    doc_id = parsed["doc_id"]
    uploaded_at = parsed["uploaded_at"]
    content = parsed["content"]

    # Flatten PDF pages or plain text into list of (page, text) tuples
    if isinstance(content, list):
        page_texts = [(item["page"], item["text"]) for item in content if item["text"].strip()]
    else:
        page_texts = [(1, content)]

    num_pages = len(page_texts)
    embedder = VoyageEmbedder(api_key=config.VOYAGE_API_KEY, model=config.VOYAGE_MODEL)
    store = QdrantStore(
        url=config.QDRANT_URL,
        api_key=config.QDRANT_API_KEY,
        collection=config.COLLECTION_DOCS,
        vector_size=config.VOYAGE_DIM,
    )

    all_points: list[dict] = []
    chunk_index = 0

    for page_num, text in page_texts:
        chunks = chunk_text(text, max_tokens=config.CHUNK_MAX_TOKENS, overlap_tokens=config.CHUNK_OVERLAP_TOKENS)
        texts = [c.text for c in chunks]
        if not texts:
            continue

        vectors = embedder.embed_documents(texts)

        for chunk, vector in zip(chunks, vectors):
            point_id = str(uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{doc_id}-{chunk_index}",
            ))
            payload: dict = {
                "source_type": "document",
                "doc_id": doc_id,
                "source_name": original_name,
                "page": page_num,
                "chunk_index": chunk_index,
                "text": chunk.text,
                "heading_path": chunk.heading_path,
                "uploaded_at": uploaded_at,
            }
            if metadata:
                payload["extra_metadata"] = metadata
            all_points.append({"id": point_id, "vector": vector, "payload": payload})
            chunk_index += 1

        logger.info("Page %d: %d chunks", page_num, len(chunks))

    store.upsert(all_points)
    logger.info(
        "Ingested %s: doc_id=%s pages=%d chunks=%d",
        original_name, doc_id, num_pages, chunk_index,
    )
    return IngestResult(
        doc_id=doc_id,
        num_chunks=chunk_index,
        num_pages=num_pages,
        source_name=original_name,
    )
