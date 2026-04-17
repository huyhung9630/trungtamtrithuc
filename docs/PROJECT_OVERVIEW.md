# Trung Tam Tri Thuc - Tong Quan Du An

## Gioi thieu

**Trung Tam Tri Thuc** (Knowledge Center) la mot he thong **RAG (Retrieval-Augmented Generation)** xay dung tren FastAPI, cho phep nguoi dung:

1. **Nap tai lieu** (PDF, DOCX, TXT, MD) vao co so tri thuc
2. **Hoi dap** bang ngon ngu tu nhien — he thong tu dong tim kiem thong tin lien quan va tra loi bang tieng Viet, kem trich dan nguon

He thong su dung **Claude (Anthropic)** lam LLM, **Voyage AI** de tao embedding, va **Qdrant** (vector database) de luu tru va truy xuat tri thuc.

---

## Kien truc tong the

```
                    +---------------------+
                    |   Web Frontend      |
                    |  (HTML/CSS/JS)      |
                    |  chat.html          |
                    |  ingest.html        |
                    |  knowledge.html     |
                    +----------+----------+
                               |
                          HTTP REST
                               |
                    +----------v----------+
                    |   FastAPI Server     |
                    |   (app/main.py)      |
                    +----------+----------+
                               |
              +----------------+----------------+
              |                                 |
    +---------v---------+           +-----------v-----------+
    |  /api/chat        |           |  /api/ingest          |
    |  (Chat API)       |           |  (Ingest API)         |
    +---------+---------+           +-----------+-----------+
              |                                 |
    +---------v---------+           +-----------v-----------+
    |   RAG Chain       |           |  Ingestion Pipeline   |
    |  - Retriever      |           |  - Doc Parser (hybrid)|
    |  - Reranker       |           |    pdfplumber + Docling|
    |  - Prompt Builder |           |  - Chunker            |
    |  - Claude Client  |           |  - Voyage Embedder    |
    +--------+----------+           |  - Qdrant Store       |
             |                      +-----------+-----------+
    +--------v----------------------------------v--------+
    |              Qdrant Vector Database                 |
    |  +----------------+  +----------------+            |
    |  | ttt_documents  |  | ttt_videos     |            |
    |  +----------------+  +----------------+            |
    |                                                    |
    |  +------------------------------------------------+|
    |  | vmedia_* (READ ONLY - cluster rieng)           ||
    |  | vmedia_content, vmedia_design, vmedia_digital  ||
    |  | vmedia_documents, vmedia_fonts, vmedia_image   ||
    |  | vmedia_media, vmedia_qa, vmedia_ttnb           ||
    |  +------------------------------------------------+|
    +----------------------------------------------------+
```

---

## Cau truc thu muc

```
trungtamtrithuc/
├── app/                        # Ma nguon chinh
│   ├── main.py                 # FastAPI app, mount router + static files
│   ├── config.py               # Doc bien moi truong (.env)
│   ├── schemas.py              # Pydantic models (request/response)
│   ├── api/                    # API endpoints
│   │   ├── chat.py             # POST /api/chat/ — hoi dap RAG
│   │   ├── ingest.py           # POST /api/ingest/file — nap tai lieu
│   │   ├── schemas.py          # Schema phu cho API
│   │   └── server.py           # (Du phong/legacy)
│   ├── core/                   # Cac thanh phan loi
│   │   ├── chunker.py          # Chia van ban thanh chunks (token-based)
│   │   ├── claude_client.py    # Giao tiep voi Claude API (Anthropic)
│   │   ├── embedder.py         # (Legacy embedder)
│   │   ├── voyage_embed.py     # Tao embedding bang Voyage AI
│   │   ├── qdrant_client.py    # (Legacy qdrant client)
│   │   ├── qdrant_store.py     # Read/Write + ReadOnly store cho Qdrant
│   │   ├── session_memory.py   # Luu lich su hoi thoai theo session
│   │   └── config.py           # Config bo sung cho core
│   ├── ingestion/              # Pipeline nap du lieu
│   │   ├── doc_parser.py       # Hybrid: pdfplumber + Docling (OCR, table, layout)
│   │   ├── doc_pipeline.py     # Orchestrate: parse → chunk → embed → upsert
│   │   ├── video_pipeline.py   # Pipeline nap video (YouTube)
│   │   ├── video_transcriber.py# Phien am video (Whisper)
│   │   └── youtube_fetcher.py  # Lay transcript tu YouTube
│   └── rag/                    # RAG pipeline
│       ├── chain.py            # RAGChain: retriever → reranker → LLM
│       ├── retriever.py        # Tim kiem song song tren nhieu collection
│       ├── reranker.py         # Xep hang lai bang keyword overlap
│       └── prompt_builder.py   # Tao system prompt theo domain chuyen gia
├── web/                        # Frontend (static HTML)
│   ├── index.html              # Trang chu
│   ├── chat.html               # Giao dien hoi dap
│   ├── ingest.html             # Giao dien nap tai lieu
│   └── knowledge.html          # Giao dien duyet co so tri thuc
├── data/                       # Du lieu runtime
│   ├── uploads/                # File upload tam
│   ├── sessions/               # Lich su hoi thoai (JSON)
│   └── logs/                   # Log nap du lieu
├── scripts/                    # Cong cu phu tro
│   ├── seed_sample_data.py     # Nap du lieu mau
│   └── test_questions.py       # Test cau hoi
├── docs/                       # Tai lieu
├── .env                        # Bien moi truong (API keys, config)
├── Dockerfile                  # Container hoa
├── requirements.txt            # Python dependencies
└── run.sh                      # Script khoi dong
```

---

## Luong du lieu chinh

### 1. Nap tai lieu (Ingest)

```
Upload file (PDF/DOCX/TXT/MD)
    │
    ▼
Doc Parser (hybrid 2 tang)
    │
    ├─ [Tang 1] pdfplumber
    │   Text >= 50 ky tu? → XONG (mien phi, <0.1s/trang)
    │   Xu ly ~70-80% trang binh thuong
    │
    └─ [Tang 2] Docling standard pipeline
        OCR + layout analysis + table extraction
        Output: Markdown co cau truc
        Xu ly trang scan, hinh anh, bang bieu phuc tap
    │
    ▼
Chunker ────── Chia van ban thanh doan nho (~700 tokens)
    │           Co overlap (~80 tokens) giua cac doan
    │           Giu heading path (tieu de phan cap)
    │           Hieu Markdown (heading, table, list)
    ▼
Voyage AI ──── Tao vector embedding (1024 chieu)
    │           Model: voyage-3
    ▼
Qdrant ─────── Luu vector + metadata vao collection
               (ttt_documents hoac ttt_videos)
```

### 2. Hoi dap (Chat)

```
Nguoi dung gui cau hoi
    │
    ▼
Voyage AI ──── Tao embedding cho cau hoi
    │
    ▼
Retriever ──── Tim kiem song song tren 3 nguon:
    │           - ttt_documents (tai lieu nap vao)
    │           - ttt_videos (video YouTube)
    │           - vmedia_* (du lieu san co, chi doc)
    │           Loai bo trung lap, sap xep theo diem
    ▼
Reranker ───── Xep hang lai: cosine score + keyword overlap bonus
    │           Lay top-5 ket qua tot nhat
    ▼
Prompt ─────── Xay dung system prompt theo domain
Builder         (mac dinh / ky thuat / phap ly / nhan su / y te)
    │           Tao context block tu cac hit
    ▼
Claude API ─── Gui system prompt + context + lich su hoi thoai
    │           Model: claude-sonnet-4
    │           Prompt caching duoc bat (ephemeral)
    ▼
Tra ve ─────── Cau tra loi tieng Viet + danh sach nguon
               Luu vao session memory
```

---

## Cac thanh phan ky thuat

### LLM — Claude (Anthropic)

- **Model**: `claude-sonnet-4-20250514` (co the cau hinh)
- **Prompt caching**: bat voi `cache_control: ephemeral` cho system prompt va context
- **Temperature**: 0.3 (uu tien do chinh xac)
- **Max tokens**: 2048
- Ho tro **streaming** (SSE)

### Embedding — Voyage AI

- **Model**: `voyage-3`
- **Kich thuoc vector**: 1024 chieu
- **Batch size**: 32 texts/request
- **Retry**: 5 lan voi exponential backoff (25s cho rate limit)

### Vector Database — Qdrant (Cloud)

- **2 cluster rieng biet**:
  - **Cluster chinh** (`QDRANT_URL`): doc/ghi — luu `ttt_documents` va `ttt_videos`
  - **Cluster vmedia** (`QDRANT_VMEDIA_URL`): chi doc — 9 collection `vmedia_*`
- **HNSW config**: m=24, ef_construct=256
- **Distance metric**: Cosine similarity
- **Upsert batch**: 64 points/batch

### Chunking

- **Max tokens/chunk**: 700
- **Overlap**: 80 tokens (dam bao lien tuc ngu canh)
- **Tokenizer**: tiktoken (`cl100k_base`)
- **Chien luoc**: Markdown heading-aware → paragraph → sentence

### Session Memory

- Luu lich su hoi thoai tai `data/sessions/{session_id}.json`
- **Toi da 10 luot** (20 messages) moi session
- Cache trong bo nho, persist ra file JSON

### Document Parser (3 tang — Docling → Claude Vision → pdfplumber)

Pipeline xu ly tai lieu su dung chien luoc **3 tang** de dam bao moi dang PDF deu duoc xu ly tot:

```
PDF → [Tang 1] Docling (mien phi, local)
        │
        ├─ Quality OK → Markdown (heading, table, list)
        │
        └─ Quality FAIL (bang vo, merged cells, duplicate)
              │
              ▼
      [Tang 2] Claude Haiku Vision (~$0.002/trang)
        Gui hinh trang → nhan Markdown
        Hieu bang, mau sac, layout, infographic
              │
              ├─ OK → Markdown
              │
              └─ Fail
                    │
                    ▼
              [Tang 3] pdfplumber (mien phi, text only)
```

**Tang 1 — Docling standard pipeline (mien phi, local):**
- Su dung cac model AI cua Docling (IBM Research)
- Layout analysis, table structure, OCR
- Output: Markdown co cau truc
- **Quality check tu dong**: phat hien bang vo, header lap lai, du lieu trung lap
- Xu ly **~80-90%** tai lieu binh thuong
- Toc do: **~8-40 giay** tuy do phuc tap

**Tang 2 — Claude Haiku Vision (chi khi Docling fail):**
- Chuyen tung trang PDF thanh hinh anh (pdf2image + poppler)
- Gui hinh cho Claude Haiku Vision voi prompt chuyen thanh Markdown
- **Hieu duoc**: bang phuc tap, merged cells, mau sac, bieu do, infographic
- Chi phi: **~$0.002/trang** (~5 dong VND/trang)
- Chi chay cho file Docling that bai (~10-20% tai lieu)

**Tang 3 — pdfplumber (last resort):**
- Trich xuat text thuan, khong co cau truc
- Chi dung khi ca Docling va Vision deu fail
- Mien phi, nhanh

**DOCX**: Docling xu ly chinh (giu heading, table, list), fallback python-docx

**TXT/MD**: Doc truc tiep

### Table Embedding (Haiku mo ta bang)

Khi chunk co chua Markdown table, he thong **khong embed bang truc tiep** ma:

1. **text** (luu trong Qdrant payload): giu nguyen Markdown table → LLM doc de tra loi
2. **embed_text** (tao vector): Haiku mo ta bang thanh **van ban tu nhien** → search match tot

```
Vi du:
  text:       | Nhóm | Tỷ trọng | Nhân sự |
              | VP   | ~30%     | ~200    |

  embed_text: Nhóm Khối Văn phòng chiếm tỷ trọng khoảng 30%
              với khoảng 200 nhân sự, làm việc tại Hà Nội.
```

Chi phi: ~$0.001/bang (Haiku). Chi chay cho chunk co bang.

**So sanh voi phien ban cu:**

| Tieu chi | v1.0 (pdfplumber + tesseract) | v1.2 (Docling + Vision + Haiku) |
|----------|-------------------------------|----------------------------------|
| PDF text binh thuong | OK | **Tot hon** (co heading, list) |
| PDF scan (tieng Viet) | Kem, sai dau | **Chinh xac** (Docling OCR) |
| Bang bieu don gian | Mat cau truc | **Markdown table** (Docling) |
| Bang phuc tap (Excel merged) | Mat hoan toan | **Markdown table** (Claude Vision) |
| Mau sac co y nghia | Khong hieu | **Hieu** (Claude Vision) |
| Infographic / bieu do | Khong hieu | **Mo ta duoc** (Claude Vision) |
| Bang → embedding | Embed bang tho | **Van ban tu nhien** (Haiku mo ta) |
| Dependencies | tesseract binary | Docling + poppler |

---

## API Endpoints

| Method | Path               | Mo ta                              |
|--------|--------------------|------------------------------------|
| POST   | `/api/chat/`       | Hoi dap RAG — nhan cau hoi, tra loi kem nguon |
| POST   | `/api/ingest/file` | Upload va nap tai lieu vao vector DB |
| POST   | `/api/ingest/youtube` | Nap video YouTube (dang phat trien) |
| GET    | `/health`          | Health check                        |

### Chat Request

```json
{
  "message": "Cau hoi cua nguoi dung",
  "session_id": "uuid-hoac-ten-bat-ky",
  "domain": "general | ky thuat | phap ly | nhan su | y te"
}
```

### Chat Response

```json
{
  "answer": "Cau tra loi tieng Viet voi trich dan nguon...",
  "sources": [
    {
      "title": "Ten tai lieu",
      "url": "link (neu co)",
      "score": 0.85,
      "source_type": "document"
    }
  ],
  "session_id": "..."
}
```

---

## Domain chuyen gia

He thong ho tro cac che do chuyen gia, moi che do co system prompt rieng:

| Domain      | Mo ta                                      |
|-------------|---------------------------------------------|
| `mac dinh`  | Tro ly tri thuc chung                       |
| `ky thuat`  | Ky su ky thuat — co code va so do           |
| `phap ly`   | Chuyen gia phap luat — trich dan dieu khoan |
| `nhan su`   | Chuyen gia HR — chinh sach, tuyen dung      |
| `y te`      | Chuyen gia y te — thong tin y hoc           |

Moi domain deu buoc phai:
- Chi su dung thong tin tu context
- Khong bia dat, khong suy doan
- Luon co muc "Nguon:" o cuoi cau tra loi

---

## Cach chay

### Yeu cau he thong

- **Python >= 3.12** (bat buoc — Docling yeu cau >= 3.10)
- **macOS Apple Silicon** (M1/M2/M3/M4) hoac Linux voi GPU
- **RAM >= 16GB** (Docling models chay local)

### Chay truc tiep

```bash
# Tao virtual environment voi Python 3.12
python3.12 -m venv venv
source venv/bin/activate

# Cai dat dependencies
pip install -r requirements.txt

# Cau hinh .env
# Can co: ANTHROPIC_API_KEY, VOYAGE_API_KEY, QDRANT_URL, QDRANT_API_KEY

# Khoi dong
./run.sh
# Hoac: uvicorn app.main:app --host 0.0.0.0 --port 8088 --reload
```

### Chay bang Docker

```bash
docker build -t trungtamtrithuc .
docker run -p 8000:8000 --env-file .env trungtamtrithuc
```

### Truy cap

- Trang chu: `http://localhost:8088/`
- Chat: `http://localhost:8088/chat.html`
- Nap tai lieu: `http://localhost:8088/ingest.html`
- API docs: `http://localhost:8088/docs` (Swagger UI tu dong cua FastAPI)

---

## Bien moi truong (.env)

| Bien                  | Mo ta                                  | Mac dinh              |
|-----------------------|----------------------------------------|-----------------------|
| `ANTHROPIC_API_KEY`   | API key Anthropic (Claude)             | *bat buoc*            |
| `VOYAGE_API_KEY`      | API key Voyage AI                      | *bat buoc*            |
| `VOYAGE_MODEL`        | Model embedding                        | `voyage-3`            |
| `VOYAGE_DIM`          | Kich thuoc vector                      | `1024`                |
| `QDRANT_URL`          | URL Qdrant cluster chinh               | *bat buoc*            |
| `QDRANT_API_KEY`      | API key Qdrant cluster chinh           | *bat buoc*            |
| `QDRANT_VMEDIA_URL`   | URL Qdrant cluster vmedia (chi doc)    |                       |
| `QDRANT_VMEDIA_API_KEY`| API key Qdrant vmedia                 |                       |
| `COLLECTION_DOCS`     | Ten collection tai lieu                | `ttt_documents`       |
| `COLLECTION_VIDEOS`   | Ten collection video                   | `ttt_videos`          |
| `CLAUDE_MODEL`        | Model Claude su dung                   | `claude-sonnet-4-20250514` |
| `CHUNK_MAX_TOKENS`    | So token toi da moi chunk              | `700`                 |
| `CHUNK_OVERLAP_TOKENS`| So token overlap giua cac chunk        | `80`                  |
| `TOP_K`               | So ket qua retrieval                   | `7`                   |
| `RERANK_TOP_K`        | So ket qua sau rerank                  | `5`                   |
| `API_HOST`            | Host server                            | `0.0.0.0`             |
| `API_PORT`            | Port server                            | `8000`                |

---

## Cong nghe su dung

| Thanh phan       | Cong nghe                                    |
|------------------|----------------------------------------------|
| Backend          | Python 3.12, FastAPI, Uvicorn                |
| LLM              | Claude Sonnet 4 (Anthropic API)              |
| LLM (vision)     | Claude Haiku 4.5 (Vision fallback + mo ta bang) |
| Embedding        | Voyage AI (voyage-3, 1024 dim)               |
| Vector DB        | Qdrant Cloud (2 cluster)                     |
| Document parsing | Docling (IBM Research) + Claude Vision + pdfplumber |
| PDF → image      | pdf2image + poppler                          |
| DOCX parsing     | Docling (fallback: python-docx)              |
| Video transcript | yt-dlp, youtube-transcript-api               |
| Tokenizer        | tiktoken (cl100k_base)                       |
| Frontend         | HTML/CSS/JS (static, no framework)           |
| Container        | Docker                                       |

---

## Lich su cap nhat

### v1.2 — 3-tier parser + Table embedding (2026-04-16)

- **Them** Claude Haiku Vision lam tang 2 khi Docling fail (bang phuc tap, Excel merged cells)
- **Them** quality check tu dong cho Docling output (phat hien bang vo, header lap lai, duplicate)
- **Them** table embedding: Haiku mo ta bang thanh van ban tu nhien truoc khi embed
- **Them** `embed_text` field trong Chunk — tach biet text goc (LLM doc) va text embedding (search)
- **Chunker**: giu bang nguyen ven (khong cat giua), loc chunk rong/markup
- Chi phi them: ~$0.002/trang Vision + ~$0.001/bang Haiku (chi khi can)

### v1.1 — Tich hop Docling (2026-04-16)

- **Thay the** tesseract OCR bang **Docling standard pipeline**
- **Cai thien** xu ly PDF scan: tieng Viet chinh xac, giu cau truc bang bieu
- **Nang cap** Python 3.9 → 3.12
- **Don gian hoa** dependencies: bo `pytesseract`, them `docling[mlx]`
- **DOCX**: dung Docling thay vi python-docx (giu day du heading, table, list)

### v1.0 — Phien ban dau tien

- RAG pipeline: pdfplumber + tesseract + Voyage AI + Qdrant + Claude
- Web frontend: chat, ingest, knowledge
- 5 domain chuyen gia
- Session memory
- Video pipeline (YouTube transcript)
