from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: str = Field(default="default")
    history: list[ChatMessage] = Field(default_factory=list)
    domain: str = Field(default="general")


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    session_id: str


class IngestRequest(BaseModel):
    source_type: str = Field(description="pdf | docx | txt | md | youtube | video")
    url: str | None = None
    collection: str = Field(default="ttt_documents")


class IngestResponse(BaseModel):
    status: str
    chunks_added: int
    message: str


class KnowledgeSearchRequest(BaseModel):
    query: str
    collection: str = Field(default="ttt_documents")
    top_k: int = Field(default=5)


class KnowledgeSearchResponse(BaseModel):
    results: list[dict[str, Any]]
