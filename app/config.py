from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent

# Voyage
VOYAGE_API_KEY: str = os.getenv("VOYAGE_API_KEY", "")
VOYAGE_MODEL: str = os.getenv("VOYAGE_MODEL", "voyage-3")
VOYAGE_DIM: int = int(os.getenv("VOYAGE_DIM", "1024"))

# Qdrant (main cluster — ttt_*)
QDRANT_URL: str = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")

# Qdrant (vmedia cluster — READ ONLY)
QDRANT_VMEDIA_URL: str = os.getenv("QDRANT_VMEDIA_URL", "")
QDRANT_VMEDIA_API_KEY: str = os.getenv("QDRANT_VMEDIA_API_KEY", "")

COLLECTION_DOCS: str = os.getenv("COLLECTION_DOCS", "ttt_documents")
COLLECTION_VIDEOS: str = os.getenv("COLLECTION_VIDEOS", "ttt_videos")
VMEDIA_COLLECTIONS: list[str] = os.getenv(
    "VMEDIA_COLLECTIONS",
    "vmedia_content,vmedia_design,vmedia_digital,vmedia_documents,vmedia_fonts,vmedia_image,vmedia_media,vmedia_qa,vmedia_ttnb",
).split(",")

# Claude
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
CLAUDE_HAIKU_MODEL: str = os.getenv("CLAUDE_HAIKU_MODEL", "claude-haiku-4-5-20251001")

# Chunking
CHUNK_MAX_TOKENS: int = int(os.getenv("CHUNK_MAX_TOKENS", "700"))
CHUNK_OVERLAP_TOKENS: int = int(os.getenv("CHUNK_OVERLAP_TOKENS", "80"))

# Retrieval
TOP_K: int = int(os.getenv("TOP_K", "7"))
RERANK_TOP_K: int = int(os.getenv("RERANK_TOP_K", "5"))

# API
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))

# Data dirs
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
LOG_DIR = BASE_DIR / "data" / "logs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
