"""Memory extraction tu hoi thoai bang Claude Haiku.

Trich xuat 2 loai:
  1. Memory records: thong tin ca nhan, preference, chu de quan tam
  2. Session summary: tom tat conversation (200 tu)

1 lan goi Haiku → tra ve ca 2.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from app.core.entity_schema import MemoryRecord, ExtractedMemory
from app.config import (
    ANTHROPIC_API_KEY,
    MEMORY_EXTRACTION_MODEL,
    MEMORY_MIN_CONFIDENCE,
)

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = (
    "Bạn là module trích xuất memory từ hội thoại chatbot Trung Tâm Tri Thức.\n\n"
    "Phân tích đoạn hội thoại và trả về JSON với 2 phần:\n\n"
    "1. **memories**: thông tin cần nhớ về user\n"
    "   - persistent: thông tin cá nhân (tên, phòng ban, chuyên môn)\n"
    "   - preference: cách user muốn được trả lời\n"
    "   - contextual: chủ đề user đang tìm hiểu, câu hỏi user quan tâm\n\n"
    "2. **summary**: tóm tắt cuộc hội thoại (tối đa 200 từ)\n"
    "   - User hỏi gì, về chủ đề gì\n"
    "   - Thông tin chính đã được trả lời\n"
    "   - Kết luận user đã biết\n\n"
    "QUY TẮC:\n"
    "- Chỉ dựa trên những gì USER NÓI và BOT TRẢ LỜI, không suy đoán\n"
    "- Mỗi memory text ≤ 50 từ, ngắn gọn\n"
    "- Summary ≤ 200 từ, tóm tắt đầy đủ nội dung trao đổi\n"
    "- confidence 0-1 dựa trên độ rõ ràng\n"
    "- Câu chào, cảm ơn → memories rỗng, summary vẫn ghi\n\n"
    "Trả về JSON thuần (không markdown code fence):\n"
    "{\n"
    '  "memories": [\n'
    '    {"category": "persistent|contextual|preference", "text": "...", '
    '"tags": [...], "confidence": 0.9}\n'
    "  ],\n"
    '  "summary": "Tóm tắt cuộc hội thoại..."\n'
    "}\n\n"
    'Không có gì đáng nhớ → {"memories": [], "summary": "..."}\n'
    'Chỉ câu chào → {"memories": [], "summary": "User chào hỏi."}'
)


def _apply_typo_fix(text: str) -> str:
    try:
        from app.ingestion.doc_parser import _fix_common_typos
        return _fix_common_typos(text)
    except ImportError:
        return text


def _parse_json_safe(raw: str) -> dict[str, Any]:
    """Parse JSON output tu LLM."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        return {}
    except json.JSONDecodeError:
        logger.warning("Memory extraction: invalid JSON: %s", raw[:200])
        return {}


async def extract_memories(
    turns: list[dict],
    user_id: str,
    session_id: str,
    domain: str = "mặc định",
    previous_summary: str = "",
) -> tuple[list[MemoryRecord], MemoryRecord | None]:
    """Trich xuat memory records + session summary tu hoi thoai.

    Args:
        turns: Lich su turn [{role, content}]
        user_id: ID nguoi dung
        session_id: ID session
        domain: Domain chatbot
        previous_summary: Summary truoc do (de cap nhat, khong tao moi)

    Returns:
        (list[MemoryRecord], session_summary_record | None)
    """
    if not turns:
        return [], None

    if not ANTHROPIC_API_KEY:
        logger.warning("Memory extraction skipped: no ANTHROPIC_API_KEY")
        return [], None

    # Build conversation text
    conv_lines: list[str] = []
    if previous_summary:
        conv_lines.append(f"[TÓM TẮT TRƯỚC ĐÓ]: {previous_summary}")
        conv_lines.append("")
    for turn in turns:
        role = "USER" if turn.get("role") == "user" else "BOT"
        conv_lines.append(f"{role}: {turn.get('content', '')}")
    conversation = "\n".join(conv_lines)

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=MEMORY_EXTRACTION_MODEL,
            max_tokens=1500,
            system=EXTRACTION_PROMPT,
            messages=[{"role": "user", "content": conversation}],
            temperature=0.1,
        )
        raw_output = response.content[0].text.strip()
    except Exception:
        logger.error("Memory extraction API call failed", exc_info=True)
        return [], None

    parsed = _parse_json_safe(raw_output)
    if not parsed:
        return [], None

    # Extract memory records
    records: list[MemoryRecord] = []
    raw_memories = parsed.get("memories", [])
    if isinstance(raw_memories, list):
        for raw in raw_memories:
            try:
                extracted = ExtractedMemory(**raw)
            except Exception:
                logger.warning("Memory validation failed: %s", raw)
                continue

            if extracted.confidence < MEMORY_MIN_CONFIDENCE:
                continue

            record = MemoryRecord(
                text=_apply_typo_fix(extracted.text),
                category=extracted.category,
                user_id=user_id,
                session_id=session_id,
                confidence=extracted.confidence,
                tags=extracted.tags,
                domain=domain,
            )
            records.append(record)

    # Extract session summary
    summary_record: MemoryRecord | None = None
    summary_text = parsed.get("summary", "")
    if summary_text and len(summary_text) > 10:
        summary_record = MemoryRecord(
            text=_apply_typo_fix(summary_text),
            category="summary",
            user_id=user_id,
            session_id=session_id,
            confidence=1.0,
            tags=["session_summary"],
            domain=domain,
            turn_count=len([t for t in turns if t.get("role") == "user"]),
        )

    logger.info(
        "Extracted %d memories + %s summary from session=%s",
        len(records), "1" if summary_record else "0", session_id,
    )
    return records, summary_record


# Backward compat
async def extract_entities(
    turns: list[dict],
    user_id: str,
    session_id: str,
    domain: str = "mặc định",
) -> list[MemoryRecord]:
    """Backward compat wrapper."""
    records, summary = await extract_memories(turns, user_id, session_id, domain)
    if summary:
        records.append(summary)
    return records
