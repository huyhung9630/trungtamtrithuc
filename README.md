# Trung Tâm Tri Thức — RAG Chatbot

Hệ thống hỏi đáp doanh nghiệp dựa trên RAG (Retrieval-Augmented Generation): nạp tài liệu (PDF/DOCX/XLSX/TXT/MD), video (MP4/YouTube/Playlist), trả lời tiếng Việt kèm trích dẫn nguồn và gợi ý câu hỏi tiếp theo.

## Kiến trúc tổng thể

```
  Upload (file / video / YouTube URL / Playlist)
            │
            ▼
  ┌──────────────────────────────┐
  │ Ingestion pipeline           │
  │  PDF: 3-tier                 │
  │   ├ Docling (local)          │
  │   ├ Claude Vision (fallback) │
  │   └ pdfplumber (last resort) │
  │  DOCX: Docling / python-docx │
  │  XLSX: openpyxl              │
  │  Video: yt-dlp + Whisper     │
  │  YouTube: transcript-api     │
  └──────────────┬───────────────┘
                 │ table detect + LLM describe + Vision+context
                 ▼
  ┌──────────────────────────────┐
  │ Chunker (heading-aware)      │
  │   max 700 tok, overlap 80    │
  └──────────────┬───────────────┘
                 ▼
  ┌──────────────────────────────┐    upsert    ┌──────────────────────────────────┐
  │ Voyage AI embed (voyage-3)   │ ───────────► │ Qdrant Cloud                     │
  │   1024-dim vectors           │              │  ttt_documents    (R/W)          │
  └──────────────────────────────┘              │  ttt_videos       (R/W)          │
                                                │  vmedia_*         (READ ONLY)    │
                                                └──────────────┬───────────────────┘
                                                               │ search
  Câu hỏi người dùng                                           │
            │                                                  ▼
            ├──────────────► ┌──────────────────────────────────────────┐
            │                │  Retriever (parallel, 3 nguồn)           │
            │                └──────────────────────┬───────────────────┘
            │                                       ▼
            │                ┌──────────────────────────────────────────┐
            │                │  Reranker (cross-encoder)                │
            │                └──────────────────────┬───────────────────┘
            │                                       ▼
            │                ┌──────────────────────────────────────────┐
            │                │  Prompt builder                          │
            │                │   system + domain preset + context       │
            │                │   + table_data + history                 │
            │                └──────────────────────┬───────────────────┘
            │                                       ▼
            │                ┌──────────────────────────────────────────┐
            │                │  Claude Sonnet 4 (Anthropic)             │
            │                └──────────────────────┬───────────────────┘
            │                                       ▼
            └──► Answer + Sources + Suggested Questions (JSON)
```

## Yêu cầu hệ thống

- Python 3.12+ (macOS Apple Silicon M1-M4 hoặc Linux)
- RAM ≥ 16GB (Docling + Vision)
- `poppler` cho pdf2image: `brew install poppler` / `apt install poppler-utils`
- `ffmpeg` cho Whisper (tuỳ chọn, cho video local): `brew install ffmpeg`
- Tài khoản: **Anthropic API**, **Voyage AI**, **Qdrant Cloud**

## Cài đặt

```bash
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
brew install poppler            # macOS
# apt install poppler-utils     # Linux

cp .env.example .env            # điền API keys (xem bảng bên dưới)
```

## Cấu hình `.env`

### Bắt buộc

| Biến | Mô tả |
|------|-------|
| `ANTHROPIC_API_KEY` | Key Claude API |
| `VOYAGE_API_KEY` | Key Voyage AI |
| `VOYAGE_MODEL` | Mặc định `voyage-3` |
| `VOYAGE_DIM` | Mặc định `1024` |
| `QDRANT_URL` | URL Qdrant cluster chính |
| `QDRANT_API_KEY` | Key R/W cho `ttt_documents` + `ttt_videos` |

### Tuỳ chọn

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Model trả lời chính |
| `CLAUDE_HAIKU_MODEL` | `claude-haiku-4-5-20251001` | Vision + describe table |
| `COLLECTION_DOCS` | `ttt_documents` | Collection tài liệu |
| `COLLECTION_VIDEOS` | `ttt_videos` | Collection video |
| `CHUNK_MAX_TOKENS` | `700` | Kích thước chunk tối đa |
| `CHUNK_OVERLAP_TOKENS` | `80` | Overlap giữa các chunk |
| `TOP_K` | `7` | Số hit trước rerank |
| `RERANK_TOP_K` | `5` | Số hit sau rerank |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | |

### Collection READ-ONLY (vmedia)

| Biến | Mô tả |
|------|-------|
| `QDRANT_VMEDIA_URL` | URL cluster vmedia (riêng) |
| `QDRANT_VMEDIA_API_KEY` | Key **CHỈ READ** — tuyệt đối không dùng để upsert/delete |
| `VMEDIA_COLLECTIONS` | CSV: `vmedia_content,vmedia_design,...` |

### YouTube proxy (vượt IP block)

Ưu tiên theo thứ tự:

| Biến | Mô tả |
|------|-------|
| `YOUTUBE_PROXY_LIST` | CSV hoặc xuống dòng: `http://user:pass@host:port` (xoay vòng) |
| `WEBSHARE_PROXY_USERNAME` + `WEBSHARE_PROXY_PASSWORD` | Webshare rotating endpoint |
| `YOUTUBE_PROXY_HTTP` / `YOUTUBE_PROXY_HTTPS` | Proxy cố định |
| `YOUTUBE_TRANSCRIPT_MAX_RETRIES` | Mặc định `10` |
| `YOUTUBE_TRANSCRIPT_RETRY_DELAY` | Mặc định `1.5` giây |

## Chạy

```bash
# Dev (auto-reload)
./run.sh

# Trực tiếp
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Docker
docker build -t ttt-chatbot .
docker run --env-file .env -p 8000:8000 ttt-chatbot
```

Truy cập:

- Trang chủ: `http://localhost:8000/`
- Chat: `http://localhost:8000/chat.html`
- Nạp tài liệu: `http://localhost:8000/ingest.html`
- Tri thức: `http://localhost:8000/knowledge.html`
- Swagger: `http://localhost:8000/docs`

## Cấu trúc thư mục

```
trungtamtrithuc/
├── app/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Biến môi trường
│   ├── schemas.py              # Pydantic I/O
│   ├── api/
│   │   ├── chat.py             # POST /api/chat/
│   │   └── ingest.py           # POST /api/ingest/{file,video/file,youtube,youtube-playlist}
│   ├── core/
│   │   ├── chunker.py          # Heading-aware chunking (tiktoken)
│   │   ├── claude_client.py    # Anthropic client wrapper
│   │   ├── voyage_embed.py     # Voyage AI embedder
│   │   ├── qdrant_store.py     # Qdrant R/W + VMediaReadOnlyStore
│   │   └── session_memory.py   # File-backed conversation history
│   ├── ingestion/
│   │   ├── doc_parser.py       # 3-tier PDF parsing + typo fix
│   │   ├── doc_pipeline.py     # Table detect/process + embed + store
│   │   ├── video_pipeline.py   # Video ingest (YouTube + local + playlist)
│   │   ├── video_transcriber.py# Whisper transcription
│   │   └── youtube_fetcher.py  # YouTube transcript (with proxy rotation)
│   └── rag/
│       ├── chain.py            # Retrieve → rerank → generate → parse suggestions
│       ├── retriever.py        # Multi-source parallel search
│       ├── reranker.py         # Cross-encoder reranker
│       └── prompt_builder.py   # System prompt + context + table_data
├── web/                        # Static frontend (HTML/CSS/JS)
├── data/{uploads,logs}/        # Runtime (auto-created)
├── docs/{PROJECT_OVERVIEW,INTEGRATION}.md
├── requirements.txt
├── run.sh
└── Dockerfile
```

## API Reference

Base URL: `http://localhost:8000`

### `GET /health`

```json
{"status": "ok"}
```

### `POST /api/ingest/file` — Nạp tài liệu

`Content-Type: multipart/form-data`

| Field | Bắt buộc | Mô tả |
|-------|----------|-------|
| `file` | ✓ | PDF / DOCX / DOC / TXT / MD / XLSX |
| `collection` | | Mặc định `ttt_documents` |
| `title`, `domain`, `description`, `tags`, `url` | | Metadata (tuỳ chọn) |

```bash
curl -X POST http://localhost:8000/api/ingest/file \
  -F "file=@report.pdf" \
  -F "title=Báo cáo Q1" \
  -F "domain=marketing" \
  -F "tags=2026,Q1"
```

Response:

```json
{"status": "ok", "chunks_added": 42, "message": "Nạp thành công 'report.pdf': 42 đoạn từ 12 trang."}
```

### `POST /api/ingest/video/file` — Nạp video local

File: MP4, MKV, AVI, MOV, WEBM, FLV, WMV. Yêu cầu `openai-whisper` (cài thủ công — xem `requirements.txt`).

### `POST /api/ingest/youtube` — Nạp URL YouTube (tự nhận playlist)

```bash
curl -X POST "http://localhost:8000/api/ingest/youtube?url=https://www.youtube.com/watch?v=XXX"
curl -X POST "http://localhost:8000/api/ingest/youtube?url=https://www.youtube.com/playlist?list=YYY"
```

### `POST /api/ingest/youtube-playlist` — Nạp playlist (chi tiết từng video)

```json
{
  "status": "ok",
  "message": "Hoàn tất: 8/10 video thành công, tổng 312 đoạn.",
  "total_videos": 10,
  "success_count": 8,
  "total_chunks": 312,
  "results": [{"video_id": "...", "status": "ok", "chunks_added": 45}]
}
```

### `POST /api/chat/` — Hỏi đáp

```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tóm tắt kế hoạch truyền thông nội bộ",
    "session_id": "uuid-v4",
    "domain": "marketing",
    "history": []
  }'
```

`domain` hỗ trợ: `mặc định`, `bim`, `mep`, `kết cấu`, `marketing`, `pháp lý`, `sản xuất` (hoặc tuỳ ý — sẽ dùng prompt tổng quát).

Response:

```json
{
  "answer": "Kế hoạch gồm 15 hoạt động...\n\nNguồn:\n- KH truyền thông nội bộ 2026 (trang 3)",
  "sources": [
    {"index": 1, "source_type": "document", "title": "KH truyền thông nội bộ 2026",
     "url": "...", "page": 3, "score": 0.89, "positions": [{"page": 3}]}
  ],
  "session_id": "uuid-v4",
  "suggested_questions": [
    "Timeline cụ thể từng tháng ra sao?",
    "Có bao nhiêu sự kiện nội bộ trong Q2?",
    "Ngân sách dự kiến cho từng hoạt động?"
  ]
}
```

**Ví dụ JS:**

```js
const sessionId = localStorage.getItem('sid') ?? crypto.randomUUID();
localStorage.setItem('sid', sessionId);

const res = await fetch('/api/chat/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    message: 'câu hỏi',
    session_id: sessionId,
    domain: 'mặc định',
    history: [],
  }),
});
const {answer, sources, suggested_questions} = await res.json();
```

## Chi phí tham khảo

| Thành phần | Khi nào | Chi phí |
|------------|---------|---------|
| Docling | Luôn chạy | $0 (local) |
| Claude Vision | Docling fail / bảng có màu | ~$0.002/trang |
| LLM mô tả bảng | Bảng có dữ liệu | ~$0.001/bảng |
| Voyage embed | Luôn chạy | ~$0.0001/chunk |
| Claude Sonnet 4 answer | Mỗi câu trả lời | ~$0.003-0.015/lần |
| **File text thuần** | Docling OK | **~$0.001/file** |
| **File phức tạp** | Vision + LLM | **~$0.005-0.01/file** |

## Troubleshooting

| Lỗi | Giải pháp |
|-----|-----------|
| `401` từ Qdrant | Kiểm tra `QDRANT_API_KEY` |
| `poppler not found` | `brew install poppler` / `apt install poppler-utils` |
| `ffmpeg not found` | `brew install ffmpeg` (chỉ cần khi ingest video local) |
| YouTube `IP blocked` | Cấu hình `YOUTUBE_PROXY_LIST` hoặc Webshare |
| `openai-whisper not installed` | Bật dòng `openai-whisper` trong `requirements.txt` và `pip install` lại |
| `collection not found` | Nạp ít nhất 1 tài liệu để tạo collection |
| Server khởi động chậm lần đầu | Docling tải model — chờ 1-2 phút |

## Tài liệu chi tiết

- `docs/PROJECT_OVERVIEW.md` — kiến trúc, pipeline, quy tắc xử lý bảng
- `docs/INTEGRATION.md` — hướng dẫn tích hợp FE/BE
