from __future__ import annotations

from app.rag.retriever import Hit

DOMAIN_PRESETS: dict[str, str] = {
    "mặc định": (
        "Bạn là trợ lý tri thức chuyên nghiệp. Trả lời chính xác, đầy đủ bằng tiếng Việt. "
        "Luôn đính kèm nguồn ở cuối câu trả lời trong mục 'Nguồn:'. Không bịa thông tin."
    ),
    "kỹ thuật": (
        "Bạn là kỹ sư kỹ thuật cao cấp. Trả lời kỹ thuật chính xác bằng tiếng Việt, "
        "kèm ví dụ code hoặc sơ đồ khi cần. Luôn có mục 'Nguồn:' ở cuối."
    ),
    "pháp lý": (
        "Bạn là chuyên gia pháp lý. Trả lời dựa trên văn bản pháp luật và quy định, "
        "bằng tiếng Việt. Luôn trích dẫn điều khoản cụ thể. Mục 'Nguồn:' bắt buộc ở cuối."
    ),
    "nhân sự": (
        "Bạn là chuyên gia nhân sự (HR). Trả lời về chính sách, quy trình tuyển dụng, "
        "phúc lợi bằng tiếng Việt. Luôn có mục 'Nguồn:' ở cuối."
    ),
    "y tế": (
        "Bạn là chuyên gia y tế. Cung cấp thông tin y học chính xác bằng tiếng Việt. "
        "Lưu ý: không thay thế tư vấn bác sĩ trực tiếp. Luôn có mục 'Nguồn:' ở cuối."
    ),
}

_BASE_SUFFIX = (
    "\n\nQuy tắc bắt buộc:\n"
    "- Chỉ sử dụng thông tin từ ngữ cảnh được cung cấp.\n"
    "- Nếu không có thông tin liên quan, nói rõ: 'Tôi không tìm thấy thông tin về vấn đề này trong cơ sở tri thức.'\n"
    "- Không bịa đặt, không suy đoán ngoài dữ liệu.\n"
    "- Khi trích dẫn nguồn trong câu trả lời, ghi rõ TÊN tài liệu thay vì chỉ ghi số. "
    "Ví dụ: viết '(Tổng quan về Teams)' thay vì '[NGUỒN 1]'.\n"
    "- Cuối câu trả lời PHẢI có mục 'Nguồn:' liệt kê tên đầy đủ các tài liệu đã sử dụng, kèm link nếu có."
)


def build_system_prompt(expert_domain: str | None = None) -> str:
    domain = (expert_domain or "mặc định").lower().strip()
    base = DOMAIN_PRESETS.get(domain, f"Bạn là chuyên gia về '{expert_domain}'. Trả lời bằng tiếng Việt, chính xác, có nguồn gốc rõ ràng.")
    return base + _BASE_SUFFIX


def _parse_timestamp(ts) -> tuple[int | None, str | None]:
    """Parse timestamp to (seconds, 'MM:SS' string)."""
    if ts is None:
        return None, None
    ts_str = str(ts)
    try:
        if ":" in ts_str:
            parts = ts_str.split(":")
            secs = int(parts[0]) * 60 + int(parts[1])
            return secs, ts_str
        secs = int(float(ts_str))
        return secs, f"{secs // 60}:{secs % 60:02d}"
    except (ValueError, TypeError):
        return None, str(ts)


def _build_youtube_url_with_timestamp(base_url: str, seconds: int | None) -> str:
    """Append ?t=XXs to YouTube URL for deep linking."""
    if not base_url or seconds is None or seconds <= 0:
        return base_url or ""
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}t={seconds}s"


def build_context_block(hits: list[Hit]) -> tuple[str, list[dict]]:
    """Return (context_markdown, deduplicated source_mapping).

    Context block contains all hits (with numbering) for the LLM.
    Source mapping is deduplicated by (title + url), keeping the highest score,
    and merging timestamps/pages from different chunks of the same source.
    """
    lines: list[str] = []

    # Build context for the LLM (all hits, not deduplicated)
    for n, hit in enumerate(hits, 1):
        payload = hit.payload
        title = payload.get("title") or payload.get("source_name") or payload.get("filename") or payload.get("source", "Không rõ nguồn")
        page = payload.get("page")
        raw_ts = payload.get("start") or payload.get("timestamp")
        base_url = payload.get("url") or payload.get("source") or payload.get("youtube_url")
        ts_secs, ts_display = _parse_timestamp(raw_ts)

        meta_parts = [f"[NGUỒN {n}] {title}"]
        if base_url:
            meta_parts.append(_build_youtube_url_with_timestamp(base_url, ts_secs))
        if page is not None:
            meta_parts.append(f"trang {page}")
        if ts_display is not None:
            meta_parts.append(ts_display)

        lines.append(" — ".join(meta_parts))
        lines.append(hit.text)
        lines.append("")

    # Build deduplicated source mapping for the frontend
    seen: dict[str, dict] = {}  # key: "title||base_url"
    for hit in hits:
        payload = hit.payload
        title = payload.get("title") or payload.get("source_name") or payload.get("filename") or payload.get("source", "Không rõ nguồn")
        page = payload.get("page")
        raw_ts = payload.get("start") or payload.get("timestamp")
        base_url = payload.get("url") or payload.get("source") or payload.get("youtube_url") or ""
        ts_secs, ts_display = _parse_timestamp(raw_ts)

        dedup_key = f"{title}||{base_url}"

        if dedup_key not in seen:
            seen[dedup_key] = {
                "source_type": hit.source_type,
                "title": title,
                "url": _build_youtube_url_with_timestamp(base_url, ts_secs),
                "base_url": base_url,
                "page": page,
                "timestamp": ts_display,
                "timestamp_secs": ts_secs,
                "score": hit.score,
                "positions": [],
            }
        entry = seen[dedup_key]
        # Keep highest score
        if hit.score > entry["score"]:
            entry["score"] = hit.score
        # Collect all positions (timestamps / pages)
        if ts_display is not None:
            pos = {"timestamp": ts_display, "url": _build_youtube_url_with_timestamp(base_url, ts_secs)}
            if pos not in entry["positions"]:
                entry["positions"].append(pos)
        if page is not None:
            pos = {"page": page}
            if pos not in entry["positions"]:
                entry["positions"].append(pos)

    mapping: list[dict] = []
    for idx, entry in enumerate(seen.values(), 1):
        # Use the first position's URL (with timestamp) as the main link
        first_pos_url = entry["positions"][0]["url"] if entry["positions"] and "url" in entry["positions"][0] else entry["base_url"]
        mapping.append({
            "index": idx,
            "source_type": entry["source_type"],
            "title": entry["title"],
            "url": first_pos_url or entry["base_url"],
            "page": entry.get("page"),
            "timestamp": entry.get("timestamp"),
            "score": entry["score"],
            "positions": entry["positions"],
        })

    return "\n".join(lines), mapping
