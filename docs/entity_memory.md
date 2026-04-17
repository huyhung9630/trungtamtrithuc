# Entity Memory System

## Architecture

```
User chat → RAG Chain (4 sources parallel)
               │
               ├── ttt_documents (Docling pipeline)
               ├── ttt_videos (YouTube/local)
               ├── vmedia_* (read-only)
               └── ttt_memory (entity memory) ← NEW
               │
               ▼
         Claude Sonnet → response
               │
               ▼
         BackgroundTask: extract entities every 4 turns
               │
               ▼
         Claude Haiku → JSON entities
               │
               ▼
         Dedup + conflict resolution → upsert to ttt_memory
```

### Flow chi tiet

1. User gui message → chat API
2. RAG chain retrieve 4 sources song song (documents + videos + vmedia + memory)
3. Memory entities duoc inject vao prompt TRUOC document context
4. Claude tra loi, response tra ve user
5. Moi 4 turn, background task extract entities tu conversation
6. Entities duoc embed (Voyage) → dedup check → upsert vao Qdrant

## Setup

```bash
# 1. Cai dependencies
pip install -r requirements.txt

# 2. Tao Qdrant collection + indexes
python scripts/init_memory_collection.py

# 3. Verify
# Collection ttt_memory voi 7 payload indexes
```

## Configuration

Tat ca config trong `app/config.py`, co the override qua .env:

| Variable | Default | Mo ta |
|----------|---------|-------|
| MEMORY_COLLECTION | ttt_memory | Ten Qdrant collection |
| MEMORY_EXTRACTION_MODEL | claude-haiku-4-5-20251001 | Model dung de extract entities |
| MEMORY_EXTRACTION_EVERY_N_TURNS | 4 | Trigger extraction moi N turn |
| MEMORY_DUP_THRESHOLD | 0.88 | Score >= nay = duplicate (chi touch) |
| MEMORY_CONFLICT_THRESHOLD | 0.75 | Score >= nay = conflict (supersede) |
| MEMORY_RETRIEVE_TOP_K | 5 | So entity retrieve toi da |
| MEMORY_MIN_CONFIDENCE | 0.6 | Entity confidence < nay bi loc |
| MEMORY_NEAR_SEARCH_LIMIT | 15 | Limit cho near-session search |
| MEMORY_LONGTERM_SEARCH_LIMIT | 5 | Limit cho long-term search |
| MEMORY_RECENT_SESSIONS_COUNT | 2 | So session gan nhat de search |

## Entity Schema

3 category:
- persistent: ten, phong ban, chuyen mon (ben vung)
- contextual: du an, task, deadline (thay doi theo thoi gian)
- preference: cach tra loi (ngan gon, kem code, formal)

Entity co lifecycle:
- active → superseded (khi thong tin moi thay the)
- active → archived (khi het han expires_at)

## Dedup + Conflict Resolution

Khi upsert entity moi:

| Cosine score voi entity cu | Action |
|----------------------------|--------|
| >= 0.88 | Duplicate: chi update last_accessed, access_count++ |
| 0.75 - 0.88 | Conflict: supersede entity cu, insert entity moi |
| < 0.75 | New: insert binh thuong |

## Retrieve (Hybrid)

2 query song song:
1. Near context: recent sessions, moi category
2. Long-term: persistent + preference, xuyen thoi gian

Combined score = 50% semantic + 25% recency + 15% same_session + 10% frequency

## Monitoring

### Log patterns

```bash
# Extraction
grep "Extracted.*entities" data/logs/*.log

# Retrieval
grep "Memory retrieve" data/logs/*.log

# Errors
grep "Entity.*failed" data/logs/*.log

# Filter by session
grep "session=SESSION_ID" data/logs/*.log
```

### Metrics nen theo doi

- So entity/user (tang deu, khong bung no)
- Extract latency (< 2s voi Haiku)
- Retrieve latency (< 200ms)
- Duplicate ratio (nen > 30% — cho thay dedup hoat dong)

## Debugging

### Entity khong duoc retrieve

1. Check entity co status=active khong
2. Check user_id khop
3. Check domain khop (hoac "mac dinh")
4. Test cosine similarity giua query va entity text
5. Check combined score (recency co the thap neu entity cu)

### Entity bi duplicate

1. Giam MEMORY_DUP_THRESHOLD (VD: 0.85 → 0.80)
2. Check embedding quality (Voyage co embed dung khong)

### Extraction khong tao entity

1. Check log: "Extracted 0 entities" → conversation khong co info
2. Check confidence: entity bi filter (< 0.6)
3. Check API key: Anthropic credit con khong

## Graceful Degradation

Entity Memory **KHONG BAO GIO** lam crash chat:
- Extraction fail → log + skip (chat van hoat dong)
- Retrieve fail → return [] (chat van co RAG docs)
- Upsert fail → log + skip entity do
- Qdrant connection fail → log + graceful fallback

## Files

| File | Muc dich |
|------|----------|
| app/config.py | Config variables |
| app/core/entity_schema.py | Pydantic Entity + ExtractedEntity |
| app/core/entity_memory.py | CRUD + retrieve + dedup logic |
| app/ingestion/entity_extractor.py | Claude Haiku extraction |
| app/rag/retriever.py | Them memory source thu 4 |
| app/rag/prompt_builder.py | Inject memory block vao prompt |
| app/api/chat.py | Background extraction trigger |
| scripts/init_memory_collection.py | Setup Qdrant collection |
| tests/test_entity_memory.py | 14 unit tests |
