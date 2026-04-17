"""Setup Qdrant collection + indexes cho Entity Memory System.

Usage: python scripts/init_memory_collection.py

Script idempotent — chay lai khong loi.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from app.config import QDRANT_URL, QDRANT_API_KEY, MEMORY_COLLECTION, VOYAGE_DIM


def _headers() -> dict:
    return {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}


def setup() -> None:
    base = QDRANT_URL.rstrip("/")

    # Check if collection exists
    r = requests.get(f"{base}/collections/{MEMORY_COLLECTION}", headers=_headers(), timeout=30)
    if r.status_code == 200:
        print(f"Collection '{MEMORY_COLLECTION}' already exists, skipping creation")
    elif r.status_code == 404:
        body = {
            "vectors": {
                "": {
                    "size": VOYAGE_DIM,
                    "distance": "Cosine",
                    "on_disk": False,
                    "datatype": "float32",
                }
            }
        }
        r2 = requests.put(f"{base}/collections/{MEMORY_COLLECTION}", headers=_headers(), json=body, timeout=30)
        r2.raise_for_status()
        print(f"Created collection '{MEMORY_COLLECTION}' (vector size={VOYAGE_DIM})")
    else:
        r.raise_for_status()

    # Create payload indexes (idempotent)
    indexes = [
        ("user_id", "keyword"),
        ("session_id", "keyword"),
        ("category", "keyword"),
        ("status", "keyword"),
        ("created_at", "integer"),
        ("domain", "keyword"),
        ("tags", "keyword"),
    ]
    for field_name, field_schema in indexes:
        try:
            r = requests.put(
                f"{base}/collections/{MEMORY_COLLECTION}/index",
                headers=_headers(),
                json={"field_name": field_name, "field_schema": field_schema},
                timeout=30,
            )
            if r.ok:
                print(f"  Index '{field_name}' ({field_schema}): created")
            else:
                print(f"  Index '{field_name}': may already exist ({r.status_code})")
        except Exception as e:
            print(f"  Index '{field_name}': error — {e}")

    print(f"\nDone. Collection '{MEMORY_COLLECTION}' ready with {len(indexes)} indexes.")


if __name__ == "__main__":
    if not QDRANT_URL or not QDRANT_API_KEY:
        print("ERROR: QDRANT_URL and QDRANT_API_KEY must be set in .env")
        sys.exit(1)
    setup()
