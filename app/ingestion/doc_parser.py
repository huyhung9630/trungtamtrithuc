from __future__ import annotations

import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Union


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def parse_pdf(path: Path) -> list[dict]:
    import pdfplumber  # type: ignore

    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"page": i, "text": text.strip()})
    return pages


def parse_docx(path: Path) -> str:
    from docx import Document  # type: ignore

    doc = Document(str(path))
    parts: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = para.style.name if para.style else ""
        if style.startswith("Heading"):
            level = "".join(filter(str.isdigit, style)) or "1"
            parts.append("#" * int(level) + " " + text)
        else:
            parts.append(text)
    return "\n\n".join(parts)


def parse_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_md(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse(path: Union[str, Path]) -> dict:
    path = Path(path)
    suffix = path.suffix.lower()
    doc_id = _sha256(path)
    uploaded_at = datetime.now(timezone.utc).isoformat()

    if suffix == ".pdf":
        content = parse_pdf(path)
        mime = "application/pdf"
    elif suffix in (".docx", ".doc"):
        content = parse_docx(path)
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif suffix == ".md":
        content = parse_md(path)
        mime = "text/markdown"
    else:
        content = parse_txt(path)
        mime = mimetypes.guess_type(path.name)[0] or "text/plain"

    return {
        "doc_id": doc_id,
        "source": path.name,
        "content": content,
        "mime": mime,
        "uploaded_at": uploaded_at,
    }
