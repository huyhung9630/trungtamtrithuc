"""Unit tests cho Entity Memory System."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.core.entity_schema import Entity
from app.core.entity_memory import EntityMemory, _combined_score
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


# --- Upsert ---

@pytest.mark.asyncio
async def test_upsert_new_entity(memory, entity):
    memory._req = MagicMock(side_effect=[
        {"result": []},  # search returns empty
        {},  # upsert
    ])
    await memory.upsert(entity)
    assert memory._req.call_count == 2


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


@pytest.mark.asyncio
async def test_upsert_conflict_supersedes(memory, entity):
    memory._req = MagicMock(side_effect=[
        {"result": [{"id": "old-id", "score": 0.80, "payload": {}}]},  # search (conflict range)
        {},  # supersede old
        {},  # insert new
    ])
    await memory.upsert(entity)
    assert memory._req.call_count == 3


# --- Retrieve ---

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


@pytest.mark.asyncio
async def test_retrieve_excludes_superseded(memory):
    memory._req = MagicMock(return_value={"result": []})
    await memory.retrieve("u1", "query", "s1", ["s1"])
    call_body = memory._req.call_args_list[0][0][2]
    filters = call_body["filter"]["must"]
    status_filter = [f for f in filters if f.get("key") == "status"]
    assert len(status_filter) == 1
    assert status_filter[0]["match"]["value"] == "active"


@pytest.mark.asyncio
async def test_retrieve_graceful_on_error(memory):
    memory._embed = MagicMock(side_effect=Exception("connection error"))
    result = await memory.retrieve("u1", "query", "s1", ["s1"])
    assert result == []


# --- Memory block ---

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


# --- Combined score ---

def test_combined_score_same_session_boost():
    import time
    e = Entity(text="t", category="persistent", user_id="u1", session_id="s1", access_count=5)
    now = int(time.time())
    score_same = _combined_score(e, 0.8, now, "s1")
    score_diff = _combined_score(e, 0.8, now, "s_other")
    assert score_same > score_diff
