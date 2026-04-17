# Trung Tam Tri Thuc - Tong Quan Du An

## Gioi thieu

**Trung Tam Tri Thuc** (Knowledge Center) la he thong **RAG (Retrieval-Augmented Generation)** xay dung tren FastAPI, cho phep:

1. **Nap tai lieu** (PDF, DOCX, XLSX, TXT, MD, Video) vao co so tri thuc
2. **Hoi dap** bang ngon ngu tu nhien — tim kiem thong tin va tra loi bang tieng Viet, kem trich dan nguon

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
    |  - Retriever      |           |  - Doc Parser         |
    |  - Reranker       |           |    (Docling/Vision/   |
    |  - Prompt Builder |           |     pdfplumber)       |
    |  - Claude Client  |           |  - Table Processor    |
    +--------+----------+           |  - Chunker            |
             |                      |  - Voyage Embedder    |
    +--------v----------------------------------v--------+
    |              Qdrant Vector Database                 |
    |  +----------------+  +----------------+            |
    |  | ttt_documents  |  | ttt_videos     |            |
    |  +----------------+  +----------------+            |
    |                                                    |
    |  +------------------------------------------------+|
    |  | vmedia_* (READ ONLY - cluster rieng)           ||
    |  +------------------------------------------------+|
    +----------------------------------------------------+
```

---

## Pipeline Xu Ly Tai Lieu

### Tong quan flow

```
FILE UPLOAD
    │
    ▼
[PARSE] doc_parser.py — 3 tier:
    │
    ├─ Tier 1: Docling (mien phi, local)
    │   OCR + layout + table → Markdown
    │   Quality check: phat hien bang vo, header lap, duplicate
    │   ├─ OK → Markdown
    │   └─ FAIL → Tier 2
    │
    ├─ Tier 2: Claude Haiku Vision (~$0.002/trang)
    │   PDF → hinh anh → Vision doc truc tiep
    │   Hieu: bang phuc tap, mau sac, merged cells
    │   ├─ OK → Structured text
    │   └─ FAIL → Tier 3
    │
    └─ Tier 3: pdfplumber (mien phi)
        Text thuan, khong co cau truc
    │
    ▼
[PROCESS] doc_pipeline.py — xu ly tung bang rieng:
    │
    ├─ Khong co bang → strip ## ** → giu nguyen text
    │
    ├─ Bang co data (<50% cot trong)
    │   → LLM tom tat 2-3 cau (cho search)
    │   → Giu bang goc Markdown (cho LLM tra loi)
    │   → Qdrant: text = tom tat, table_data = bang goc
    │
    └─ Bang co mau sac (>50% cot trong)
        → Vision doc hinh voi context tu cac trang khac
        → Output: structured text (khong phai paragraph)
        → Qdrant: text = structured text
    │
    ▼
[CHUNK] chunker.py — heading-aware:
    Chia theo heading (##) → paragraph → sentence
    Max 700 tokens, overlap 80 tokens
    Loc chunk < 10 tokens
    │
    ▼
[EMBED] Voyage AI → vector 1024 dim
    │
    ▼
[STORE] Qdrant payload:
    text: plain text (cho search + LLM doc)
    table_data: bang goc Markdown (chi khi co bang, cho LLM doc chinh xac)
    heading_path: ["Chuong", "Muc"]
    source_name, page, doc_id, uploaded_at
```

### 3 truong hop xu ly

| Dang tai lieu | Parse | Process | Qdrant text | Qdrant table_data |
|---------------|-------|---------|-------------|-------------------|
| **Text thuan** (van ban, bao cao) | Docling → Markdown | Strip ## ** | Plain text | (trong) |
| **Bang co data** (nhan su, kenh) | Docling → Markdown table | LLM tom tat 2-3 cau | Tom tat ngan | Bang goc Markdown |
| **Bang co mau** (timeline, Gantt) | Docling → bang trong | Vision + context | Structured text | (trong) |
| **Docling fail** (Excel merged) | Vision → structured text | Giu nguyen | Structured text | (trong) |
| **XLSX** | openpyxl → structured text | Giu nguyen | Structured text | (trong) |
| **DOCX** | Docling → Markdown | Nhu PDF | Nhu PDF | Nhu PDF |

### Tai sao 2 field trong Qdrant?

```
Khi user hoi: "Khoi Van phong co bao nhieu nguoi?"

1. SEARCH: embed(text) match "Khối Văn phòng 30%, 200 nhân sự"
   → Tim dung chunk (text la plain text, search tot)

2. LLM TRA LOI: doc text + table_data
   text:       "Bảng phân nhóm gồm 3 nhóm: VP 30%, BCHCT 40%, CN 30%"
   table_data: "| Nhóm | Tỷ trọng | Chi tiết |\n|---|---|---|\n| VP | ~30% | ~200 |"
   → Claude doc bang goc → tra loi chinh xac: "200 nhân sự"
```

### Docling Quality Check

Docling output duoc kiem tra 4 dieu kien truoc khi chap nhan:

| Check | Phat hien | Vi du |
|-------|-----------|-------|
| Broken table | > 20 pipes tren 1-2 dong | Excel merged cells |
| Repeated header | Cung text >= 5 lan | Merged header row |
| No line breaks | > 500 chars trong < 3 dong | Bang bi flatten |
| Duplicate blocks | > 40% paragraphs trung | Data lap lai |

Neu bat ky check nao fail → Docling REJECTED → chuyen Vision.

### Vision voi Context

Khi Vision doc trang co bang mau, no nhan **context tu cac trang khac** (tu Docling) de hieu trang do thuoc phan nao cua tai lieu:

```
Vision nhan:
  Context: "Kế hoạch truyền thông nội bộ 2026 của TDI...
            Mục tiêu: tăng tham gia nội bộ..."
  + Hinh: trang timeline co mau

Vision tra ve:
  "Timeline truyền thông nội bộ 2026 của TDI gồm 15 hoạt động:
   Tất niên, du xuân (T1-T2): đã hoàn thành.
   30/4-1/5 Hoạt động nội bộ (T4): sự kiện quan trọng.
   ..."
```

### Vietnamese Typo Auto-fix

Vision/LLM co the sai chinh ta tieng Viet. He thong tu dong sua:

| Sai | Dung |
|-----|------|
| Chông Cháy | Chống Cháy |
| Của chống | Cửa chống |
| Dã quay | Đã quay |
| Dạng edit | Đang edit |
| Tính trạng | Tình trạng |
| KỀ HOẠCH | KẾ HOẠCH |

Co the them loi moi vao `_TYPO_FIXES` trong `doc_parser.py`.

---

## RAG Pipeline (Hoi dap)

```
User hoi → Voyage embed → Qdrant search (3 nguon song song)
    → Reranker (cosine + keyword) → Top 5
    → Claude Sonnet 4 (system prompt + context + table_data + history)
    → Tra loi tieng Viet + nguon + goi y cau hoi
```

### Prompt Builder

Khi xay context cho LLM:
- Doc `text` tu payload (plain text)
- Neu co `table_data` → them vao context: "Du lieu bang chi tiet: [bang Markdown]"
- Claude doc ca 2 → tra loi chinh xac tu bang goc

### Domain chuyen gia

| Domain | Mo ta |
|--------|-------|
| mac dinh | Tro ly tri thuc chung |
| ky thuat | Ky su — code, so do |
| phap ly | Luat — trich dan dieu khoan |
| nhan su | HR — chinh sach, tuyen dung |
| y te | Y hoc — thong tin y te |

---

## Cau truc thu muc

```
trungtamtrithuc/
├── app/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Bien moi truong
│   ├── schemas.py              # Pydantic models
│   ├── api/
│   │   ├── chat.py             # POST /api/chat/
│   │   ├── ingest.py           # POST /api/ingest/file, /youtube, /video
│   │   └── schemas.py
│   ├── core/
│   │   ├── chunker.py          # Heading-aware text chunking
│   │   ├── claude_client.py    # Claude API client
│   │   ├── voyage_embed.py     # Voyage AI embedder
│   │   ├── qdrant_store.py     # Qdrant read/write + read-only
│   │   └── session_memory.py   # Session history (file-backed)
│   ├── ingestion/
│   │   ├── doc_parser.py       # 3-tier: Docling → Vision → pdfplumber
│   │   ├── doc_pipeline.py     # Table processing + embed + store
│   │   ├── video_pipeline.py   # Video ingest (YouTube + local)
│   │   ├── video_transcriber.py# Whisper transcription
│   │   └── youtube_fetcher.py  # YouTube transcript
│   └── rag/
│       ├── chain.py            # RAG chain (retrieve → rerank → generate)
│       ├── retriever.py        # Multi-source parallel search
│       ├── reranker.py         # Cosine + keyword reranker
│       └── prompt_builder.py   # System prompt + context + table_data
├── web/                        # Static frontend
├── data/                       # Runtime data (sessions, logs)
├── docs/                       # Documentation
├── requirements.txt            # Python dependencies
└── run.sh                      # Startup script
```

---

## Cai dat

### Yeu cau

- Python >= 3.12
- macOS Apple Silicon (M1-M4) hoac Linux
- RAM >= 16GB
- poppler (`brew install poppler`)

### Setup

```bash
# Python 3.12
brew install python@3.12
python3.12 -m venv venv
source venv/bin/activate

# Dependencies
pip install -r requirements.txt

# System dependency
brew install poppler

# Config
cp .env.example .env
# Dien: ANTHROPIC_API_KEY, VOYAGE_API_KEY, QDRANT_URL, QDRANT_API_KEY

# Run
./run.sh
```

### Truy cap

- Trang chu: `http://localhost:8088/`
- Chat: `http://localhost:8088/chat.html`
- Nap tai lieu: `http://localhost:8088/ingest.html`
- API docs: `http://localhost:8088/docs`

---

## Chi phi

| Thanh phan | Khi nao | Chi phi |
|------------|---------|--------|
| Docling | Luon chay | $0 (local) |
| Vision | Docling fail hoac bang mau | ~$0.002/trang |
| LLM tom tat bang | Bang co data | ~$0.001/bang |
| Voyage embed | Luon chay | ~$0.0001/chunk |
| **File binh thuong** | Docling OK, khong co bang | **~$0.001** |
| **File phuc tap** | Vision + LLM | **~$0.005-0.01** |

---

## Cong nghe

| Thanh phan | Cong nghe |
|------------|-----------|
| Backend | Python 3.12, FastAPI, Uvicorn |
| LLM | Claude Sonnet 4 (Anthropic API) |
| LLM Vision | Claude Haiku 4.5 (Vision + table description) |
| Embedding | Voyage AI (voyage-3, 1024 dim) |
| Vector DB | Qdrant Cloud |
| PDF parsing | Docling (IBM Research) + Claude Vision + pdfplumber |
| PDF → image | pdf2image + poppler |
| DOCX | Docling / python-docx |
| XLSX | openpyxl |
| Video | yt-dlp, youtube-transcript-api, Whisper |
| Tokenizer | tiktoken (cl100k_base) |
| Frontend | HTML/CSS/JS (static) |
