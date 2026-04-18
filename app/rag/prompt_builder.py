"""Prompt builder theo best practice của Anthropic (Claude Sonnet 4+):
  - XML tags (<retrieved_documents>, <user_context>, <session_summary>)
    thay cho markdown headers → Claude parse boundary chắc chắn hơn.
  - Positive framing: mô tả "làm gì" thay vì "không làm gì".
  - Quote-first grounding: yêu cầu xác định đoạn liên quan trước khi tổng hợp.
  - Follow-up suggestions bám sát tài liệu vừa truy xuất (không generic).
  - Tone tiếng Việt rõ ràng: lịch sự thân thiện, xưng "tôi" - gọi "bạn",
    giữ nguyên thuật ngữ chuyên ngành EN, format số kiểu VN.

Ref: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags
Ref: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices
"""
from __future__ import annotations

from app.rag.retriever import Hit

# ---------------------------------------------------------------- personas
# Mỗi persona là 1-2 câu mô tả vai trò + domain vocabulary. Giữ ngắn:
# rule chi tiết đã chuẩn hoá ở _BASE_SUFFIX cho mọi domain.
DOMAIN_PERSONAS: dict[str, str] = {
    "mặc định": (
        "Bạn là trợ lý tri thức chuyên nghiệp, trả lời câu hỏi dựa trên "
        "tài liệu được truy xuất và dữ kiện người dùng đã cung cấp."
    ),
    "bim": (
        "Bạn là chuyên gia BIM (Building Information Modeling) cao cấp. "
        "Thuật ngữ thường dùng: LOD, clash detection, model coordination, "
        "Revit, Navisworks, IFC, CDE, BEP, federated model, point cloud. "
        "Cấu trúc câu trả lời theo 3 phần: (1) khái niệm, (2) quy trình/bước, "
        "(3) lưu ý thực tế."
    ),
    "mep": (
        "Bạn là kỹ sư MEP (Mechanical, Electrical, Plumbing) cao cấp. "
        "Thuật ngữ: HVAC, chiller, AHU, FCU, hệ PCCC, sprinkler, riser diagram, "
        "load calculation, busduct, cable tray, ELV, BMS, bơm tăng áp. "
        "Cấu trúc câu trả lời: (1) nguyên lý, (2) tiêu chuẩn áp dụng "
        "(TCVN, ASHRAE, NFPA…), (3) lưu ý thi công/vận hành."
    ),
    "kết cấu": (
        "Bạn là kỹ sư kết cấu cao cấp. Thuật ngữ: BTCT, móng cọc, móng băng, "
        "dầm, cột, sàn, vách, tải trọng (tĩnh/hoạt/gió/động đất), TCVN, Eurocode, "
        "ACI, ETABS, SAP2000, biểu đồ nội lực. "
        "Cấu trúc: (1) phân tích kết cấu, (2) tiêu chuẩn thiết kế, "
        "(3) lưu ý thi công và kiểm tra chất lượng."
    ),
    "marketing": (
        "Bạn là chuyên gia Marketing chiến lược. Thuật ngữ: brand positioning, "
        "target audience, marketing mix (4P/7P), digital marketing, SEO/SEM, "
        "content marketing, conversion rate, customer journey, KPI, ROI, "
        "A/B testing, funnel, lead generation, CRM. "
        "Cấu trúc: (1) phân tích vấn đề, (2) giải pháp cụ thể, "
        "(3) chỉ số đo lường hiệu quả."
    ),
    "pháp lý": (
        "Bạn là chuyên gia pháp lý. Dẫn chiếu văn bản pháp luật Việt Nam: "
        "Luật Xây dựng, Luật Đầu tư, Luật Doanh nghiệp, Luật Lao động, "
        "Bộ luật Dân sự, các Nghị định / Thông tư. "
        "Cấu trúc: (1) căn cứ pháp lý (Điều X, Khoản Y), (2) giải thích, "
        "(3) lưu ý thực thi. Luôn trích dẫn điều khoản cụ thể."
    ),
    "sản xuất": (
        "Bạn là chuyên gia quản lý sản xuất. Thuật ngữ: Lean Manufacturing, "
        "5S, Kaizen, OEE, cycle time, takt time, bottleneck, QC/QA, Six Sigma, "
        "PDCA, SOP, BOM, MRP, capacity planning, yield rate, defect rate. "
        "Cấu trúc: (1) phân tích hiện trạng, (2) quy trình cải tiến, "
        "(3) KPI đánh giá."
    ),
}

# ---------------------------------------------------------------- base rules
# Quy tắc chung cho mọi domain. Đặt ở SYSTEM prompt cùng persona để Claude
# cache được (persona + rules là stable cross-turn).
_BASE_RULES = """
<language_style>
- Trả lời bằng tiếng Việt, lịch sự nhưng thân thiện. Xưng "tôi", gọi người dùng là "bạn".
- Giữ nguyên thuật ngữ chuyên ngành tiếng Anh khi không có bản dịch thông dụng (BIM, LOD, HVAC, KPI…).
- Định dạng số theo kiểu Việt Nam: dấu chấm phân cách hàng nghìn, dấu phẩy cho thập phân (vd: 1.000.000 đồng, 13,3 triệu).
</language_style>

<reasoning_process>
Trước khi viết câu trả lời, hãy thầm (không cần in ra):
1. Xác định các đoạn trong <retrieved_documents> liên quan trực tiếp tới câu hỏi.
2. Xác định dữ kiện trong <user_context> có thể dùng kết hợp.
3. Nếu câu hỏi cần tính toán hoặc tổng hợp nhiều nguồn: dùng cả tài liệu và dữ kiện user để suy luận. Đây là suy luận hợp lệ.
</reasoning_process>

<grounding_rules>
Nguồn thông tin hợp lệ để trả lời gồm:
(a) các đoạn trong <retrieved_documents> — tài liệu được truy xuất cho câu hỏi này.
(b) dữ kiện trong <user_context> — thông tin user đã xác nhận rõ ràng trong hội thoại (tên, team, ngân sách, sở thích, mục tiêu…).

Bạn được phép:
- Trả lời dựa trên (a), (b), hoặc kết hợp cả hai.
- Suy luận, tính toán, ước lượng dựa trên dữ kiện user đã khai báo kể cả khi tài liệu không có (vd: user nói "ngân sách 80 triệu cho 6 video" → trả lời "80 / 6 ≈ 13,3 triệu/video"). Đây KHÔNG phải bịa đặt.
- Tự tin khẳng định dữ kiện user đã nói — coi đây là sự thật đã xác lập, không phải suy đoán.

Bạn chỉ nói "Tôi không tìm thấy thông tin này" khi CẢ <retrieved_documents> LẪN <user_context> đều không chứa dữ liệu cần thiết cho câu hỏi.

Chỉ trả lời dựa trên thông tin trong hai nguồn trên. Không thêm số liệu tài liệu không có; không bịa fact user chưa từng nói.
</grounding_rules>

<citation_rules>
- Trong phần nội dung: trích nguồn bằng TÊN tài liệu (vd: "(CHÂN DUNG ĐỐI TƯỢNG...)", không dùng "[NGUỒN 1]").
- Nếu câu trả lời có dùng tài liệu: kết thúc bằng đúng 1 dòng "Nguồn:" liệt kê tên tài liệu, kèm link nếu có.
- Nếu câu trả lời chỉ dùng dữ kiện user (không dùng tài liệu): ghi "Nguồn: Thông tin bạn đã cung cấp trong cuộc trò chuyện."
- Với câu xã giao (chào hỏi, cảm ơn, giới thiệu bản thân, trò chuyện thường): trả lời tự nhiên, BỎ mục "Nguồn:" và BỎ phần "---GỢI Ý---".
</citation_rules>

<followup_suggestions>
Khi câu trả lời có nội dung kiến thức, sau "Nguồn:" thêm đúng khối sau:
---GỢI Ý---
1. <câu hỏi 1>
2. <câu hỏi 2>
3. <câu hỏi 3>

Yêu cầu câu hỏi gợi ý:
- Rút ra trực tiếp từ nội dung trong <retrieved_documents> vừa dùng, hoặc từ chủ đề user đang trao đổi — không phải câu hỏi generic trong ngành.
- Gợi ra hướng đào sâu hoặc mở rộng tự nhiên từ câu trả lời vừa viết.
- Ngắn gọn, đúng như một câu hỏi thật của user (xưng "tôi", không phải bot nói về bot).
</followup_suggestions>
"""


def build_system_prompt(expert_domain: str | None = None) -> str:
    """System prompt ổn định cross-turn (Claude cache được)."""
    domain = (expert_domain or "mặc định").lower().strip()
    persona = DOMAIN_PERSONAS.get(
        domain,
        f"Bạn là chuyên gia về '{expert_domain}'. Trả lời tiếng Việt chính xác, có nguồn rõ ràng.",
    )
    return persona.strip() + "\n" + _BASE_RULES.strip()


# ---------------------------------------------------------------- user_context
def _fmt_relative_time(created_at: int) -> str:
    import time as _t
    if not created_at:
        return ""
    delta = int(_t.time()) - int(created_at)
    if delta < 3600:
        return f"{max(1, delta // 60)} phút trước"
    if delta < 86400:
        return f"{delta // 3600} giờ trước"
    return f"{delta // 86400} ngày trước"


def build_conversation_block(summary: str, recall_pairs: list[dict]) -> str:
    """Block ngữ cảnh hội thoại — để inject vào system prompt.

    Dùng XML tags để Claude parse boundary chắc chắn. Nội dung gồm:
      - <session_summary>: rolling summary (các lượt rớt khỏi sliding window)
      - <user_context>: fact user đã khai từ các session khác (vector recall)

    Trả về "" nếu rỗng cả 2.
    """
    parts: list[str] = []

    if summary and summary.strip():
        parts.append(
            "<session_summary>\n"
            "Đây là tóm tắt các lượt hội thoại TRƯỚC trong phiên hiện tại "
            "(đã rớt khỏi sliding window). Coi đây là thông tin đã được xác lập.\n"
            f"{summary.strip()}\n"
            "</session_summary>"
        )

    if recall_pairs:
        lines = [
            "<user_context>",
            "Đây là các trao đổi trước giữa user này và bạn "
            "(truy xuất theo độ tương đồng ngữ nghĩa với câu hỏi hiện tại).",
            "Coi các dữ kiện user khai báo trong đây là sự thật đã xác lập — "
            "được phép dùng để trả lời và suy luận.",
            "",
        ]
        for i, p in enumerate(recall_pairs, 1):
            ts = _fmt_relative_time(p.get("created_at", 0))
            tag = f"[#{i}" + (f" — {ts}" if ts else "") + "]"
            lines.append(tag)
            lines.append(p.get("text", "").strip())
            lines.append("")
        lines.append("</user_context>")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


# ---------------------------------------------------------------- documents
def _parse_timestamp(ts) -> tuple[int | None, str | None]:
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
    if not base_url or seconds is None or seconds <= 0:
        return base_url or ""
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}t={seconds}s"


def build_context_block(hits: list[Hit]) -> tuple[str, list[dict]]:
    """Build <retrieved_documents> block (XML) + dedup source mapping cho FE.

    XML cho phép Claude parse boundary chính xác giữa các <document>.
    """
    if not hits:
        return "", []

    doc_parts: list[str] = ["<retrieved_documents>"]

    for n, hit in enumerate(hits, 1):
        payload = hit.payload
        title = (
            payload.get("title")
            or payload.get("source_name")
            or payload.get("filename")
            or payload.get("source", "Không rõ nguồn")
        )
        page = payload.get("page")
        raw_ts = payload.get("start") or payload.get("timestamp")
        base_url = (
            payload.get("url") or payload.get("source") or payload.get("youtube_url")
        )
        ts_secs, ts_display = _parse_timestamp(raw_ts)

        source_parts = [title]
        if base_url:
            source_parts.append(_build_youtube_url_with_timestamp(base_url, ts_secs))
        if page is not None:
            source_parts.append(f"trang {page}")
        if ts_display is not None:
            source_parts.append(ts_display)
        source_line = " — ".join(source_parts)

        doc_parts.append(f'  <document index="{n}">')
        doc_parts.append(f"    <source>{source_line}</source>")
        doc_parts.append("    <content>")
        doc_parts.append(hit.text.strip())

        table_data = payload.get("table_data", "")
        if table_data:
            doc_parts.append("")
            doc_parts.append("Dữ liệu bảng chi tiết:")
            doc_parts.append(table_data.strip())

        doc_parts.append("    </content>")
        doc_parts.append("  </document>")

    doc_parts.append("</retrieved_documents>")

    # --- dedup source mapping cho FE ---
    seen: dict[str, dict] = {}
    for hit in hits:
        payload = hit.payload
        title = (
            payload.get("title")
            or payload.get("source_name")
            or payload.get("filename")
            or payload.get("source", "Không rõ nguồn")
        )
        page = payload.get("page")
        raw_ts = payload.get("start") or payload.get("timestamp")
        base_url = (
            payload.get("url")
            or payload.get("source")
            or payload.get("youtube_url")
            or ""
        )
        ts_secs, ts_display = _parse_timestamp(raw_ts)

        key = f"{title}||{base_url}"
        if key not in seen:
            seen[key] = {
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
        entry = seen[key]
        if hit.score > entry["score"]:
            entry["score"] = hit.score
        if ts_display is not None:
            pos = {
                "timestamp": ts_display,
                "url": _build_youtube_url_with_timestamp(base_url, ts_secs),
            }
            if pos not in entry["positions"]:
                entry["positions"].append(pos)
        if page is not None:
            pos = {"page": page}
            if pos not in entry["positions"]:
                entry["positions"].append(pos)

    mapping: list[dict] = []
    for idx, entry in enumerate(seen.values(), 1):
        first_pos_url = (
            entry["positions"][0]["url"]
            if entry["positions"] and "url" in entry["positions"][0]
            else entry["base_url"]
        )
        mapping.append(
            {
                "index": idx,
                "source_type": entry["source_type"],
                "title": entry["title"],
                "url": first_pos_url or entry["base_url"],
                "page": entry.get("page"),
                "timestamp": entry.get("timestamp"),
                "score": entry["score"],
                "positions": entry["positions"],
            }
        )

    return "\n".join(doc_parts), mapping
