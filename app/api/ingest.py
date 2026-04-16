from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from app.schemas import IngestResponse
from app.ingestion.doc_pipeline import ingest_document, ensure_collections

logger = logging.getLogger(__name__)

router = APIRouter()

# Ensure Qdrant collections exist on first import
try:
    ensure_collections()
except Exception as exc:
    logger.warning("Could not ensure collections at startup: %s", exc)


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    collection: str = Form(default="ttt_documents"),
) -> IngestResponse:
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".docx", ".doc", ".txt", ".md"):
        return IngestResponse(
            status="error",
            chunks_added=0,
            message=f"Định dạng '{suffix}' không được hỗ trợ. Chỉ chấp nhận: PDF, DOCX, TXT, MD.",
        )

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = ingest_document(
            file_path=tmp_path,
            original_name=file.filename,
        )
        return IngestResponse(
            status="ok",
            chunks_added=result.num_chunks,
            message=f"Nạp thành công '{file.filename}': {result.num_chunks} đoạn từ {result.num_pages} trang.",
        )
    except Exception as exc:
        logger.exception("Ingest error for %s: %s", file.filename, exc)
        return IngestResponse(
            status="error",
            chunks_added=0,
            message=f"Lỗi khi nạp '{file.filename}': {exc}",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/youtube", response_model=IngestResponse)
async def ingest_youtube(url: str, collection: str = "ttt_videos") -> IngestResponse:
    return IngestResponse(
        status="pending",
        chunks_added=0,
        message="Chức năng nạp YouTube đang được triển khai.",
    )
