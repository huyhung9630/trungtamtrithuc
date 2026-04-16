"""Seed ttt_videos collection from videos.json transcripts.

Usage:
    cd /Users/haletrongnghia/Downloads/video_tttt/trungtamtrithuc
    python -m scripts.seed_sample_data
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Allow running as module from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import re
import uuid

from app.core import config
from app.core.chunker import chunk_transcript_with_timestamps
from app.core.voyage_embed import VoyageEmbedder
from app.core.qdrant_store import QdrantStore

VIDEOS_JSON = Path(__file__).parent.parent.parent / "Claude_QA_Video" / "videos.json"

_TS_RE = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s+(.*)")


def _parse_transcript(transcript: str) -> list[dict]:
    """Parse 'MM:SS text' lines into segment dicts with start/end/text."""
    segments: list[dict] = []
    for line in transcript.split("."):
        line = line.strip()
        if not line:
            continue
        m = _TS_RE.match(line)
        if m:
            h_or_m = int(m.group(1))
            mins = int(m.group(2))
            secs = int(m.group(3)) if m.group(3) else 0
            # Format is MM:SS (no hours) based on sample data
            start_sec = h_or_m * 60 + mins + secs / 60 if m.group(3) else h_or_m * 60 + mins
            segments.append({"text": m.group(4).strip(), "start": start_sec, "end": start_sec + 30})
        elif segments:
            segments[-1]["text"] += " " + line
    # Fix end times
    for i in range(len(segments) - 1):
        segments[i]["end"] = segments[i + 1]["start"]
    return segments


def main() -> None:
    print(f"Loading videos from {VIDEOS_JSON}")
    videos = json.loads(VIDEOS_JSON.read_text(encoding="utf-8"))
    print(f"Found {len(videos)} videos")

    embedder = VoyageEmbedder(api_key=config.VOYAGE_API_KEY, model=config.VOYAGE_MODEL)
    store = QdrantStore(
        url=config.QDRANT_URL,
        api_key=config.QDRANT_API_KEY,
        collection=config.COLLECTION_VIDEOS,
        vector_size=config.VOYAGE_DIM,
    )
    store.ensure_collection()

    total_chunks = 0

    for vid in videos:
        transcript = vid.get("transcript") or ""
        if not transcript.strip():
            print(f"  [SKIP] {vid.get('name')} — no transcript")
            continue

        title = vid.get("chu_de") or vid.get("name") or "Untitled"
        nhom = vid.get("nhom") or ""
        source = vid.get("links") or vid.get("file_name") or ""

        segments = _parse_transcript(transcript)
        if not segments:
            print(f"  [SKIP] {title} — no segments parsed")
            continue

        raw_chunks = chunk_transcript_with_timestamps(segments, max_tokens=500)
        if not raw_chunks:
            print(f"  [SKIP] {title} — no chunks produced")
            continue

        payloads = []
        for i, rc in enumerate(raw_chunks):
            ts_start = int(rc["start"])
            mm, ss = divmod(ts_start, 60)
            payloads.append({
                "text": rc["text"],
                "title": title,
                "nhom": nhom,
                "source": source,
                "filename": vid.get("file_name", ""),
                "source_type": "video",
                "timestamp": f"{mm:02d}:{ss:02d}",
                "start": rc["start"],
                "end": rc["end"],
                "chunk_index": i,
            })

        texts = [p["text"] for p in payloads]
        embeddings = None
        for attempt in range(5):
            try:
                embeddings = embedder.embed_documents(texts)
                break
            except Exception as e:
                if attempt < 4:
                    wait = 25 * (attempt + 1)
                    print(f"    [RATE LIMIT] waiting {wait}s... ({e})")
                    time.sleep(wait)
                else:
                    print(f"  [ERROR] {title}: {e}")
        if embeddings is None:
            continue

        points = [
            {"id": str(uuid.uuid4()), "vector": emb, "payload": payload}
            for emb, payload in zip(embeddings, payloads)
        ]
        store.upsert(points)
        total_chunks += len(points)
        print(f"  [OK] {title} — {len(points)} chunks")
        time.sleep(21)  # respect 3 RPM free tier

    print(f"\nDone. Total chunks: {total_chunks} -> '{config.COLLECTION_VIDEOS}'")


if __name__ == "__main__":
    main()
