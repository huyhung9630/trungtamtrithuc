from __future__ import annotations

import hashlib
import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)

_OCR_AVAILABLE: bool | None = None


def _check_ocr_available() -> bool:
    global _OCR_AVAILABLE
    if _OCR_AVAILABLE is not None:
        return _OCR_AVAILABLE
    try:
        import pytesseract
        from pdf2image import convert_from_path  # noqa: F401
        pytesseract.get_tesseract_version()
        _OCR_AVAILABLE = True
    except ImportError:
        _OCR_AVAILABLE = False
        logger.warning(
            "OCR không khả dụng: cần cài pytesseract và pdf2image. "
            "PDF scan sẽ trả về text rỗng."
        )
    except Exception:
        _OCR_AVAILABLE = False
        logger.warning(
            "OCR không khả dụng: tesseract binary không tìm thấy. "
            "Cài đặt: brew install tesseract tesseract-lang"
        )
    return _OCR_AVAILABLE


def _ocr_page_image(image) -> str:
    import pytesseract
    try:
        text = pytesseract.image_to_string(image, lang="vie+eng")
        return text.strip()
    except Exception:
        logger.exception("OCR thất bại cho trang")
        return ""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _is_scanned_page(text: str) -> bool:
    return len(text.strip()) < 50


def parse_pdf(path: Path) -> list[dict]:
    import pdfplumber  # type: ignore

    pages = []
    ocr_pages: list[int] = []

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if _is_scanned_page(text):
                ocr_pages.append(i)
                pages.append({"page": i, "text": ""})
            else:
                pages.append({"page": i, "text": text.strip()})

    if ocr_pages and _check_ocr_available():
        from pdf2image import convert_from_path

        logger.info(
            "Phát hiện %d trang scan, đang OCR: %s", len(ocr_pages), path.name
        )
        for page_num in ocr_pages:
            try:
                images = convert_from_path(
                    str(path), dpi=300,
                    first_page=page_num, last_page=page_num,
                )
                if images:
                    ocr_text = _ocr_page_image(images[0])
                    pages[page_num - 1]["text"] = ocr_text
                    logger.info(
                        "OCR trang %d: %d ký tự", page_num, len(ocr_text)
                    )
                del images
            except Exception:
                logger.exception("OCR thất bại cho trang %d của %s", page_num, path.name)
    elif ocr_pages:
        logger.warning(
            "%d trang scan nhưng OCR không khả dụng, bỏ qua.", len(ocr_pages)
        )

    return pages


def parse_xlsx(path: Path) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(str(path), data_only=True)
    parts: list[str] = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue

        # Find header row (first row with 2+ non-empty cells)
        header_idx = 0
        headers: list[str] = []
        for i, row in enumerate(rows):
            non_empty = [c for c in row if c is not None and str(c).strip()]
            if len(non_empty) >= 2:
                headers = [str(c).strip() if c else f"Col{j+1}" for j, c in enumerate(row)]
                header_idx = i
                break

        if len(wb.sheetnames) > 1:
            parts.append(f"# Sheet: {sheet_name}")

        if not headers:
            # No header found, dump all non-empty rows as text
            for row in rows:
                line = " | ".join(str(c).strip() for c in row if c is not None and str(c).strip())
                if line:
                    parts.append(line)
            continue

        # Convert data rows to structured text
        for row in rows[header_idx + 1:]:
            cells = [str(c).strip() if c is not None else "" for c in row]
            if not any(cells):
                continue
            row_parts: list[str] = []
            for header, cell in zip(headers, cells):
                if cell:
                    row_parts.append(f"{header}: {cell}")
            if row_parts:
                parts.append("\n".join(row_parts))

    return "\n\n".join(parts)


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
    elif suffix == ".xlsx":
        content = parse_xlsx(path)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
