# Trung Tâm Tri Thức — RAG Chatbot

Dịch vụ hỏi đáp thông minh sử dụng Voyage AI embeddings, Qdrant vector store và Claude (Anthropic).

## Kiến trúc

```
  Upload tài liệu / video / YouTube URL
            │
            ▼
  ┌─────────────────┐    parse / chunk    ┌──────────────────┐
  │   Ingestion     │ ──────────────────► │  Voyage AI Embed │
  │ PDF/DOCX/Video  │                     │  voyage-4-lite   │
  └─────────────────┘                     │  512-dim vectors │
                                          └────────┬─────────┘
                                                   │ upsert
                                                   ▼
                                     ┌─────────────────────────┐
                                     │       Qdrant Cloud      │
                                     │  ttt_documents  (R/W)   │
                                     │  ttt_videos     (R/W)   │
                                     │  vmedia         (R only)│
                                     └────────────┬────────────┘
                                                  │ search
  Câu hỏi người dùng                              │
            │                                     ▼
            └───────────────────────► ┌─────────────────────────┐
                                      │   RAG Retriever         │
                                      │   Top-K + Rerank        │
                                      └────────────┬────────────┘
                                                   │ context
                                                   ▼
                                      ┌─────────────────────────┐
                                      │   Claude (Anthropic)    │
                                      │   claude-sonnet-4-*     │
                                      └────────────┬────────────┘
                                                   │
                                                   ▼
                                        Answer + Sources (JSON)
```

## Yêu cầu

- Python 3.11+
- ffmpeg (cho Whisper phiên âm video): `brew install ffmpeg` / `apt install ffmpeg`
- Tài khoản: Anthropic API, Voyage AI, Qdrant Cloud

## Cài đặt

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # điền API keys
```

## Cấu hình (.env)

| Biến | Mô tả |
|------|-------|
| `ANTHROPIC_API_KEY` | Key Claude API |
| `VOYAGE_API_KEY` | Key Voyage AI |
| `QDRANT_URL` | URL Qdrant cluster |
| `QDRANT_API_KEY` | Key R/W cho `ttt_documents` + `ttt_videos` |
| `QDRANT_VMEDIA_API_KEY` | Key **CHỈ READ** cho collection `vmedia` |
| `CLAUDE_MODEL` | Mặc định: `claude-sonnet-4-20250514` |
| `API_PORT` | Mặc định: `8000` |

> **QUAN TRỌNG:** `QDRANT_VMEDIA_API_KEY` chỉ được phép search/read. Tuyệt đối không dùng key này để upsert, tạo hoặc xóa collection.

## Chạy

```bash
# Dev (auto-reload)
./run.sh

# Hoặc trực tiếp
uvicorn app.main:app --reload --port 8000

# Docker
docker build -t ttt-chatbot .
docker run --env-file .env -p 8000:8000 ttt-chatbot
```

Giao diện web: **http://localhost:8000/**
API docs (Swagger): **http://localhost:8000/docs**

## Cấu trúc thư mục

```
trungtamtrithuc/
├── app/
│   ├── config.py          # biến môi trường
│   ├── schemas.py         # Pydantic models
│   ├── main.py            # FastAPI app
│   ├── api/               # routes: chat, ingest, knowledge
│   ├── core/              # voyage_embed, qdrant_store, claude_client
│   ├── ingestion/         # doc_parser, video pipeline, chunker
│   └── rag/               # retriever, reranker, prompt_builder, chain
├── web/                   # UI tĩnh: index.html, chat.html, ingest.html
├── data/uploads/          # file tạm (tự tạo khi chạy)
├── docs/INTEGRATION.md    # hướng dẫn tích hợp FE/BE
├── requirements.txt
├── run.sh
└── Dockerfile
```

## API Reference

Base URL: `http://localhost:8000`

### GET /health
```json
{"status": "ok"}
```

### POST /api/ingest/file — Nạp tài liệu hoặc video
`Content-Type: multipart/form-data`

| Field | Mô tả |
|-------|-------|
| `file` | PDF, DOCX, TXT, MD, MP4, MKV, MOV, AVI |
| `collection` | `ttt_documents` (mặc định) hoặc `ttt_videos` |

```bash
curl -X POST http://localhost:8000/api/ingest/file \
  -F "file=@report.pdf" -F "collection=ttt_documents"
```

Response:
```json
{"status": "ok", "chunks_added": 42, "message": "Đã nạp thành công 42 đoạn."}
```

### POST /api/ingest/youtube — Nạp YouTube URL
```bash
curl -X POST "http://localhost:8000/api/ingest/youtube?url=https://www.youtube.com/watch?v=ID"
```

### POST /api/chat/ — Hỏi đáp
```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Tóm tắt nội dung tài liệu", "session_id": "uuid-v4", "domain": "general", "history": []}'
```

Response:
```json
{
  "answer": "Câu trả lời...",
  "sources": [{"title": "...", "score": 0.91, "youtube_url": "...&t=123s", "timestamp": 123}],
  "session_id": "uuid-v4"
}
```

**Ví dụ JS:**
```js
const sessionId = localStorage.getItem('sid') ?? crypto.randomUUID();
localStorage.setItem('sid', sessionId);

const res = await fetch('/api/chat/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({message: 'câu hỏi', session_id: sessionId, domain: 'general', history: []})
});
const {answer, sources} = await res.json();
```

**Ví dụ Python (httpx):**
```python
import httpx, uuid
sid = str(uuid.uuid4())
r = httpx.post('http://localhost:8000/api/chat/',
    json={'message': 'câu hỏi', 'session_id': sid, 'domain': 'general', 'history': []},
    timeout=60)
print(r.json()['answer'])
```

## Troubleshooting

| Lỗi | Giải pháp |
|-----|-----------|
| `401` từ Qdrant | Kiểm tra `QDRANT_API_KEY` trong `.env` |
| `ffmpeg not found` | `brew install ffmpeg` hoặc `apt install ffmpeg` |
| Server chậm lần đầu | Whisper đang tải model — bình thường, chờ 1-2 phút |
| `collection not found` | Nạp ít nhất 1 tài liệu để tạo collection |
