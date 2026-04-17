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

try:
    from app.ingestion.video_pipeline import ensure_collections as ensure_video_collections
    ensure_video_collections()
except Exception as exc:
    logger.warning("Could not ensure video collections at startup: %s", exc)


# ---------------------------------------------------------------------------
# Ingest — tài liệu (PDF, DOCX, TXT, MD)
# ---------------------------------------------------------------------------

@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    collection: str = Form(default="ttt_documents"),
) -> IngestResponse:
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".docx", ".doc", ".txt", ".md", ".xlsx"):
        return IngestResponse(
            status="error",
            chunks_added=0,
            message=f"Định dạng '{suffix}' không được hỗ trợ. Chỉ chấp nhận: PDF, DOCX, TXT, MD, XLSX.",
        )

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


# ---------------------------------------------------------------------------
# Ingest — video file upload (MP4, MKV, AVI, MOV)
# ---------------------------------------------------------------------------

VIDEO_SUFFIXES = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv"}


@router.post("/video/file", response_model=IngestResponse)
async def ingest_video_file(
    file: UploadFile = File(...),
    collection: str = Form(default="ttt_videos"),
) -> IngestResponse:
    suffix = Path(file.filename).suffix.lower()
    if suffix not in VIDEO_SUFFIXES:
        return IngestResponse(
            status="error",
            chunks_added=0,
            message=f"Định dạng '{suffix}' không được hỗ trợ. Chỉ chấp nhận: MP4, MKV, AVI, MOV.",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from app.ingestion.video_pipeline import ingest_video_file as _ingest_video
        result = _ingest_video(
            local_path=tmp_path,
            original_name=file.filename,
        )
        return IngestResponse(
            status="ok",
            chunks_added=result.num_chunks,
            message=f"Phiên âm thành công '{file.filename}': {result.num_chunks} đoạn.",
        )
    except ImportError:
        logger.exception("Whisper not installed")
        return IngestResponse(
            status="error",
            chunks_added=0,
            message="openai-whisper chưa được cài đặt. Chạy: pip install openai-whisper",
        )
    except Exception as exc:
        logger.exception("Video ingest error for %s: %s", file.filename, exc)
        return IngestResponse(
            status="error",
            chunks_added=0,
            message=f"Lỗi khi phiên âm '{file.filename}': {exc}",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Ingest — YouTube URL
# ---------------------------------------------------------------------------

def _is_playlist_url(url: str) -> bool:
    """Detect if URL is a YouTube playlist (not a single video with list param)."""
    import re
    # Pure playlist URL: youtube.com/playlist?list=...
    if re.search(r"youtube\.com/playlist\?", url):
        return True
    return False


@router.post("/youtube", response_model=IngestResponse)
async def ingest_youtube(url: str, collection: str = "ttt_videos") -> IngestResponse:
    if not url or not url.strip():
        return IngestResponse(
            status="error",
            chunks_added=0,
            message="Vui lòng nhập URL YouTube.",
        )

    clean_url = url.strip()

    # Auto-detect playlist URLs and route to playlist handler
    if _is_playlist_url(clean_url):
        try:
            from app.ingestion.video_pipeline import ingest_youtube_playlist as _ingest_pl
            results = _ingest_pl(playlist_url=clean_url)
            total_ok = sum(1 for r in results if r["status"] == "ok")
            total_chunks = sum(r["chunks_added"] for r in results)
            failed = [r for r in results if r["status"] == "error"]
            msg = f"Playlist: {total_ok}/{len(results)} video thành công, tổng {total_chunks} đoạn."
            if failed:
                msg += f" ({len(failed)} video lỗi)"
            return IngestResponse(
                status="ok" if total_ok > 0 else "error",
                chunks_added=total_chunks,
                message=msg,
            )
        except Exception as exc:
            logger.exception("Playlist ingest error for %s: %s", clean_url, exc)
            return IngestResponse(
                status="error",
                chunks_added=0,
                message=f"Lỗi khi nạp playlist: {exc}",
            )

    try:
        from app.ingestion.video_pipeline import ingest_youtube as _ingest_yt
        result = _ingest_yt(url=clean_url)
        return IngestResponse(
            status="ok",
            chunks_added=result.num_chunks,
            message=f"Nạp thành công '{result.source_name}': {result.num_chunks} đoạn.",
        )
    except ValueError as exc:
        return IngestResponse(
            status="error",
            chunks_added=0,
            message=f"URL không hợp lệ: {exc}",
        )
    except Exception as exc:
        logger.exception("YouTube ingest error for %s: %s", clean_url, exc)
        return IngestResponse(
            status="error",
            chunks_added=0,
            message=f"Lỗi khi nạp YouTube: {exc}",
        )


# ---------------------------------------------------------------------------
# Ingest — YouTube Playlist
# ---------------------------------------------------------------------------

@router.post("/youtube-playlist")
async def ingest_youtube_playlist(url: str) -> dict:
    if not url or not url.strip():
        return {"status": "error", "message": "Vui lòng nhập URL playlist.", "results": []}

    try:
        from app.ingestion.video_pipeline import ingest_youtube_playlist as _ingest_pl
        results = _ingest_pl(playlist_url=url.strip())
        total_ok = sum(1 for r in results if r["status"] == "ok")
        total_chunks = sum(r["chunks_added"] for r in results)
        return {
            "status": "ok",
            "message": f"Hoàn tất: {total_ok}/{len(results)} video thành công, tổng {total_chunks} đoạn.",
            "total_videos": len(results),
            "success_count": total_ok,
            "total_chunks": total_chunks,
            "results": results,
        }
    except RuntimeError as exc:
        return {"status": "error", "message": f"Lỗi playlist: {exc}", "results": []}
    except Exception as exc:
        logger.exception("Playlist ingest error for %s: %s", url, exc)
        return {"status": "error", "message": f"Lỗi khi nạp playlist: {exc}", "results": []}
