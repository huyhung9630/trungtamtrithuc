"""Pydantic models cho Memory System.

2 loai memory:
  - Memory record: thong tin ca nhan, preference (entity)
  - Session summary: tom tat conversation (summary)
"""
from __future__ import annotations

import time
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field

MemoryCategory = Literal["persistent", "contextual", "preference", "summary"]
MemoryStatus = Literal["active", "superseded", "archived"]


class MemoryRecord(BaseModel):
    """Memory record luu trong Qdrant ttt_memory.

    Categories:
      - persistent: thong tin ca nhan ben vung (ten, phong ban, chuyen mon)
      - preference: cach user muon duoc tra loi
      - contextual: context user dang quan tam (chu de, cau hoi)
      - summary: tom tat session (cap nhat moi 4 turn)
    """
    memory_id: str = Field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}")
    text: str
    category: MemoryCategory
    user_id: str
    session_id: str
    created_at: int = Field(default_factory=lambda: int(time.time()))
    last_accessed: int = Field(default_factory=lambda: int(time.time()))
    access_count: int = 0
    confidence: float = 0.8
    status: MemoryStatus = "active"
    tags: list[str] = Field(default_factory=list)
    domain: str = "mặc định"
    superseded_by: Optional[str] = None
    supersedes: list[str] = Field(default_factory=list)
    turn_count: int = 0  # so turn da tom tat (cho summary)


# Backward compat alias
Entity = MemoryRecord
