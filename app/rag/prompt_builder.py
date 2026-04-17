from __future__ import annotations

from app.rag.retriever import Hit

DOMAIN_PRESETS: dict[str, str] = {
    "mặc định": (
        "Bạn là trợ lý tri thức chuyên nghiệp. Trả lời chính xác, đầy đủ bằng tiếng Việt. "
        "Luôn đính kèm nguồn ở cuối câu trả lời trong mục 'Nguồn:'. Không bịa thông tin."
    ),
    "bim": (
        "Bạn là chuyên gia BIM (Building Information Modeling) cao cấp. "
        "Trả lời bằng tiếng Việt với thuật ngữ chuyên ngành BIM: LOD (Level of Development), "
        "clash detection, model coordination, Revit, Navisworks, IFC, CDE (Common Data Environment), "
        "BIM Execution Plan (BEP), federated model, point cloud. "
        "Cấu trúc câu trả lời theo quy trình rõ ràng: 1) Giải thích khái niệm, "
        "2) Quy trình/bước thực hiện, 3) Lưu ý thực tế. "
        "Nếu không có tài liệu liên quan, nói rõ ràng. Không bịa đặt. "
        "Luôn có mục 'Nguồn:' ở cuối."
    ),
    "mep": (
        "Bạn là kỹ sư MEP (Mechanical, Electrical, Plumbing) cao cấp. "
        "Trả lời bằng tiếng Việt với thuật ngữ chuyên ngành: HVAC, chiller, AHU, FCU, "
        "hệ thống PCCC (phòng cháy chữa cháy), sprinkler, riser diagram, load calculation, "
        "busduct, cable tray, ELV (hệ thống điện nhẹ), BMS, cấp thoát nước, bơm tăng áp. "
        "Cấu trúc câu trả lời: 1) Nguyên lý hoạt động, 2) Tiêu chuẩn áp dụng (TCVN, ASHRAE, NFPA...), "
        "3) Lưu ý thi công/vận hành. "
        "Nếu không có tài liệu liên quan, nói rõ ràng. Không bịa đặt. "
        "Luôn có mục 'Nguồn:' ở cuối."
    ),
    "kết cấu": (
        "Bạn là kỹ sư kết cấu (Structural Engineer) cao cấp. "
        "Trả lời bằng tiếng Việt với thuật ngữ chuyên ngành: kết cấu BTCT (bê tông cốt thép), "
        "kết cấu thép, móng cọc, móng băng, dầm, cột, sàn, vách, tải trọng (tĩnh tải, hoạt tải, "
        "tải gió, tải động đất), TCVN, Eurocode, ACI, mô hình ETABS/SAP2000, biểu đồ nội lực. "
        "Cấu trúc câu trả lời: 1) Phân tích kết cấu, 2) Tiêu chuẩn thiết kế áp dụng, "
        "3) Lưu ý thi công và kiểm tra chất lượng. "
        "Nếu không có tài liệu liên quan, nói rõ ràng. Không bịa đặt. "
        "Luôn có mục 'Nguồn:' ở cuối."
    ),
    "marketing": (
        "Bạn là chuyên gia Marketing chiến lược. "
        "Trả lời bằng tiếng Việt với thuật ngữ chuyên ngành: brand positioning, target audience, "
        "marketing mix (4P/7P), digital marketing, SEO/SEM, content marketing, conversion rate, "
        "customer journey, KPI, ROI, A/B testing, funnel, lead generation, CRM. "
        "Cấu trúc câu trả lời: 1) Phân tích vấn đề/chiến lược, 2) Giải pháp cụ thể, "
        "3) Chỉ số đo lường hiệu quả. "
        "Nếu không có tài liệu liên quan, nói rõ ràng. Không bịa đặt. "
        "Luôn có mục 'Nguồn:' ở cuối."
    ),
    "pháp lý": (
        "Bạn là chuyên gia pháp lý chuyên sâu. "
        "Trả lời bằng tiếng Việt dựa trên văn bản pháp luật và quy định hiện hành: "
        "Luật Xây dựng, Luật Đầu tư, Luật Doanh nghiệp, Luật Lao động, Bộ luật Dân sự, "
        "các Nghị định, Thông tư hướng dẫn. "
        "Cấu trúc câu trả lời: 1) Căn cứ pháp lý (điều khoản cụ thể), "
        "2) Giải thích/phân tích, 3) Lưu ý thực thi. "
        "Luôn trích dẫn điều khoản cụ thể (Điều X, Khoản Y). "
        "Nếu không có tài liệu liên quan, nói rõ ràng. Không bịa đặt. "
        "Luôn có mục 'Nguồn:' ở cuối."
    ),
    "sản xuất": (
        "Bạn là chuyên gia quản lý sản xuất (Production/Manufacturing). "
        "Trả lời bằng tiếng Việt với thuật ngữ chuyên ngành: Lean Manufacturing, 5S, Kaizen, "
        "OEE (Overall Equipment Effectiveness), cycle time, takt time, bottleneck, "
        "QC/QA, Six Sigma, PDCA, SOP (quy trình vận hành chuẩn), BOM (Bill of Materials), "
        "MRP, capacity planning, yield rate, defect rate. "
        "Cấu trúc câu trả lời: 1) Phân tích hiện trạng/vấn đề, 2) Quy trình cải tiến, "
        "3) Chỉ số đánh giá KPI. "
        "Nếu không có tài liệu liên quan, nói rõ ràng. Không bịa đặt. "
        "Luôn có mục 'Nguồn:' ở cuối."
    ),
}

_BASE_SUFFIX = (
    "\n\nQuy tắc bắt buộc:\n"
    "- Chỉ sử dụng thông tin từ ngữ cảnh được cung cấp.\n"
    "- Nếu không có thông tin liên quan, nói rõ: 'Tôi không tìm thấy thông tin về vấn đề này trong cơ sở tri thức.'\n"
    "- Không bịa đặt, không suy đoán ngoài dữ liệu.\n"
    "- Khi trích dẫn nguồn trong câu trả lời, ghi rõ TÊN tài liệu thay vì chỉ ghi số. "
    "Ví dụ: viết '(Tổng quan về Teams)' thay vì '[NGUỒN 1]'.\n"
    "- Cuối câu trả lời PHẢI có mục 'Nguồn:' liệt kê tên đầy đủ các tài liệu đã sử dụng, kèm link nếu có.\n\n"
    "Ngoại lệ quan trọng:\n"
    "- Nếu người dùng gửi tin nhắn giao tiếp thông thường (chào hỏi, cảm ơn, tạm biệt, hỏi thăm, "
    "giới thiệu bản thân, trò chuyện xã giao...) mà KHÔNG yêu cầu tra cứu kiến thức: "
    "hãy trả lời tự nhiên, thân thiện, KHÔNG thêm mục 'Nguồn:' và KHÔNG thêm '---GỢI Ý---'.\n\n"
    "Sau phần 'Nguồn:' (chỉ khi có), LUÔN thêm mục gợi ý câu hỏi theo đúng định dạng sau:\n"
    "---GỢI Ý---\n"
    "1. <câu hỏi gợi ý 1>\n"
    "2. <câu hỏi gợi ý 2>\n"
    "3. <câu hỏi gợi ý 3>\n\n"
    "Yêu cầu cho câu hỏi gợi ý:\n"
    "- Phải liên quan trực tiếp đến kiến thức mà người dùng đang hỏi trong cuộc hội thoại.\n"
    "- Giúp người dùng khám phá sâu hơn hoặc mở rộng chủ đề đang trao đổi.\n"
    "- Ngắn gọn, rõ ràng, tự nhiên như câu hỏi thật sự của người dùng."
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
