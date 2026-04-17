"""Unit tests cho Entity Memory System."""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.core.entity_schema import Entity, ExtractedMemory, MemoryRecord
from app.core.entity_memory import EntityMemory, _combined_score
from app.ingestion.entity_extractor import extract_entities, extract_memories, _parse_json_safe
from app.rag.prompt_builder import build_memory_block


# --- Fixtures ---

@pytest.fixture
def entity():
    return Entity(
        text="User ten Minh, phong Nhan su",
        category="persistent",
        user_id="u1",
        session_id="s1",
        confidence=0.95,
        tags=["ten:Minh", "phong Nhan su"],
    )


@pytest.fixture
def memory():
    mem = EntityMemory()
    mem._embed = MagicMock(return_value=[0.1] * 1024)
    return mem


# --- Test 1: Extract simple conversation ---

@pytest.mark.asyncio
async def test_extract_simple_conversation():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "memories": [
            {"text": "User ten Minh, phong Nhan su", "category": "persistent",
             "tags": ["ten:Minh"], "confidence": 0.95}
        ],
        "summary": "User gioi thieu ban than la Minh, phong Nhan su."
    }))]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("app.ingestion.entity_extractor.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value = mock_client
        records, summary = await extract_memories(
            turns=[{"role": "user", "content": "Minh la, phong Nhan su"}],
            user_id="u1", session_id="s1",
        )
        assert len(records) >= 1
        assert records[0].category == "persistent"
        assert records[0].user_id == "u1"
        assert summary is not None
        assert summary.category == "summary"


# --- Test 2: Extract greeting only ---

@pytest.mark.asyncio
async def test_extract_greeting_only():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "memories": [],
        "summary": "User chao hoi."
    }))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("app.ingestion.entity_extractor.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value = mock_client
        records, summary = await extract_memories(
            turns=[{"role": "user", "content": "Chao bot"}],
            user_id="u1", session_id="s1",
        )
        assert records == []
        assert summary is not None  # summary van co du chi la chao


# --- Test 3: Low confidence filtered ---

@pytest.mark.asyncio
async def test_extract_low_confidence_filtered():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "memories": [
            {"text": "Maybe something", "category": "contextual",
             "tags": [], "confidence": 0.3}
        ],
        "summary": "User noi gi do khong ro."
    }))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("app.ingestion.entity_extractor.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value = mock_client
        records, summary = await extract_memories(
            turns=[{"role": "user", "content": "hmm"}],
            user_id="u1", session_id="s1",
        )
        assert records == []  # filtered by confidence


# --- Test 4: Invalid JSON returns empty ---

def test_extract_invalid_json_returns_empty():
    assert _parse_json_safe("not json") == {}
    assert _parse_json_safe("{bad}") == {}
    assert _parse_json_safe("") == {}


# --- Test 5: Upsert new entity ---

@pytest.mark.asyncio
async def test_upsert_new_entity(memory, entity):
    memory._req = MagicMock(side_effect=[
        {"result": []},  # search returns empty
        {},  # upsert
    ])
    await memory.upsert(entity)
    assert memory._req.call_count == 2


# --- Test 6: Upsert duplicate touches only ---

@pytest.mark.asyncio
async def test_upsert_duplicate_touches_only(memory, entity):
    memory._req = MagicMock(side_effect=[
        {"result": [{"id": "old-id", "score": 0.95, "payload": {"access_count": 3}}]},  # search
        {},  # touch (update payload)
    ])
    await memory.upsert(entity)
    # Should call search + touch, NOT insert
    assert memory._req.call_count == 2
    # Second call should be payload update, not points upsert
    second_call = memory._req.call_args_list[1]
    assert "payload" in str(second_call)


# --- Test 7: Upsert conflict supersedes ---

@pytest.mark.asyncio
async def test_upsert_conflict_supersedes(memory, entity):
    memory._req = MagicMock(side_effect=[
        {"result": [{"id": "old-id", "score": 0.80, "payload": {}}]},  # search (conflict range)
        {},  # supersede old
        {},  # insert new
    ])
    await memory.upsert(entity)
    assert memory._req.call_count == 3


# --- Test 8: Retrieve top-k order ---

@pytest.mark.asyncio
async def test_retrieve_top_k_order(memory):
    import time
    now = int(time.time())
    memory._req = MagicMock(side_effect=[
        {"result": [
            {"score": 0.9, "payload": {"memory_id": "e1", "text": "a", "category": "persistent",
             "user_id": "u1", "session_id": "s1", "created_at": now, "last_accessed": now,
             "access_count": 5, "confidence": 0.9, "status": "active", "tags": [], "domain": "mặc định"}},
            {"score": 0.5, "payload": {"memory_id": "e2", "text": "b", "category": "contextual",
             "user_id": "u1", "session_id": "s1", "created_at": now - 86400*30, "last_accessed": now,
             "access_count": 0, "confidence": 0.7, "status": "active", "tags": [], "domain": "mặc định"}},
        ]},  # near
        {"result": []},  # longterm
        {},  # touch
    ])
    result = await memory.retrieve("u1", "test query", "s1", ["s1"])
    assert len(result) == 2
    assert result[0].memory_id == "e1"  # higher combined score


# --- Test 9: Retrieve filters by user ---

@pytest.mark.asyncio
async def test_retrieve_filters_by_user(memory):
    memory._req = MagicMock(return_value={"result": []})
    result = await memory.retrieve("u1", "query", "s1", ["s1"])
    assert result == []
    # Verify filter includes user_id
    call_body = memory._req.call_args_list[0][0][2]
    filters = call_body["filter"]["must"]
    user_filter = [f for f in filters if f.get("key") == "user_id"]
    assert len(user_filter) == 1
    assert user_filter[0]["match"]["value"] == "u1"


# --- Test 10: Retrieve excludes superseded ---

@pytest.mark.asyncio
async def test_retrieve_excludes_superseded(memory):
    memory._req = MagicMock(return_value={"result": []})
    await memory.retrieve("u1", "query", "s1", ["s1"])
    call_body = memory._req.call_args_list[0][0][2]
    filters = call_body["filter"]["must"]
    status_filter = [f for f in filters if f.get("key") == "status"]
    assert len(status_filter) == 1
    assert status_filter[0]["match"]["value"] == "active"


# --- Test 11: Retrieve graceful on error ---

@pytest.mark.asyncio
async def test_retrieve_graceful_on_error(memory):
    memory._embed = MagicMock(side_effect=Exception("connection error"))
    result = await memory.retrieve("u1", "query", "s1", ["s1"])
    assert result == []


# --- Test memory block ---

def test_memory_block_empty():
    assert build_memory_block([]) == ""


def test_memory_block_grouped():
    entities = [
        Entity(text="Ten Minh", category="persistent", user_id="u1", session_id="s1"),
        Entity(text="Thich tra loi ngan", category="preference", user_id="u1", session_id="s1"),
        Entity(text="Dang lam du an X", category="contextual", user_id="u1", session_id="s1"),
    ]
    block = build_memory_block(entities)
    assert "Hồ sơ" in block
    assert "Sở thích" in block
    assert "Đang quan tâm" in block
    assert "Ten Minh" in block


# --- Test combined score ---

def test_combined_score_same_session_boost():
    import time
    e = Entity(text="t", category="persistent", user_id="u1", session_id="s1", access_count=5)
    now = int(time.time())
    score_same = _combined_score(e, 0.8, now, "s1")
    score_diff = _combined_score(e, 0.8, now, "s_other")
    assert score_same > score_diff
