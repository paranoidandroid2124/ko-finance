"""Schemas for the Research Notebook API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


def _normalize_strings(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    normalized: List[str] = []
    for raw in values:
        if not isinstance(raw, str):
            continue
        trimmed = raw.strip()
        if trimmed and trimmed not in normalized:
            normalized.append(trimmed)
    return normalized


class NotebookEntrySourceSchema(BaseModel):
    type: Optional[str] = Field(default=None, description="Source type (filing, news, manual 등).")
    label: Optional[str] = Field(default=None, description="User-facing label for the highlight source.")
    url: Optional[str] = Field(default=None, description="External URL or deeplink.")
    deeplink: Optional[str] = Field(default=None, description="Internal deeplink for RAG snippets.")
    snippet: Optional[str] = Field(default=None, description="Optional snippet preview.")
    documentId: Optional[str] = Field(default=None, description="RAG document identifier.")
    chunkId: Optional[str] = Field(default=None, description="Chunk identifier when applicable.")
    page: Optional[int] = Field(default=None, description="Page hint inside the source document.")
    paragraph: Optional[str] = Field(default=None, description="Paragraph identifier or URN.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata payload.")

    @field_validator("type", "label", "url", "deeplink", "snippet", "documentId", "chunkId", "paragraph", mode="before")
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class NotebookEntryBase(BaseModel):
    highlight: str = Field(..., description="Highlighted text snippet.")
    annotation: Optional[str] = Field(default=None, description="Markdown or mixed rich-text annotation body.")
    annotationFormat: Optional[str] = Field(default="markdown", description="Formatting hint for the annotation.")
    tags: List[str] = Field(default_factory=list, description="Optional labels for this entry.")
    source: NotebookEntrySourceSchema = Field(default_factory=NotebookEntrySourceSchema)
    isPinned: bool = Field(default=False, description="Whether the entry is pinned to the top.")
    position: Optional[int] = Field(default=None, description="Manual ordering hint (higher renders first).")

    @field_validator("tags", mode="before")
    def _normalize_tags(cls, value: Optional[List[str]]) -> List[str]:
        return _normalize_strings(value)


class NotebookEntryCreateRequest(NotebookEntryBase):
    pass


class NotebookEntryUpdateRequest(BaseModel):
    highlight: Optional[str] = None
    annotation: Optional[str] = None
    annotationFormat: Optional[str] = None
    tags: Optional[List[str]] = None
    source: Optional[NotebookEntrySourceSchema] = None
    isPinned: Optional[bool] = None
    position: Optional[int] = None

    @field_validator("tags", mode="before")
    def _normalize_update_tags(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        return _normalize_strings(value)


class NotebookEntryResponse(BaseModel):
    id: str
    notebookId: str
    authorId: str
    highlight: str
    annotation: Optional[str] = None
    annotationFormat: str
    tags: List[str]
    source: NotebookEntrySourceSchema
    isPinned: bool
    position: int
    createdAt: str
    updatedAt: str


class NotebookSummary(BaseModel):
    id: str
    orgId: str
    ownerId: str
    title: str
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    coverColor: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    entryCount: int = 0
    lastActivityAt: Optional[str] = None
    createdAt: str
    updatedAt: str


class NotebookCreateRequest(BaseModel):
    title: str = Field(..., description="Notebook title.")
    summary: Optional[str] = Field(default=None, description="Optional description or goal.")
    tags: List[str] = Field(default_factory=list, description="Tags for quick filtering.")
    coverColor: Optional[str] = Field(default=None, description="Optional hex color for UI chips.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata payload.")

    @field_validator("title")
    def _ensure_title(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("title cannot be empty.")
        return text

    @field_validator("tags", mode="before")
    def _normalize_tags(cls, value: Optional[List[str]]) -> List[str]:
        return _normalize_strings(value)


class NotebookUpdateRequest(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    coverColor: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("title")
    def _validate_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("title cannot be empty.")
        return text

    @field_validator("tags", mode="before")
    def _normalize_optional_tags(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        return _normalize_strings(value)


class NotebookDetailResponse(BaseModel):
    notebook: NotebookSummary
    entries: List[NotebookEntryResponse] = Field(default_factory=list)


class NotebookListFilters(BaseModel):
    tags: List[str] = Field(default_factory=list)
    query: Optional[str] = None
    limit: int = Field(default=25)


class NotebookListResponse(BaseModel):
    items: List[NotebookSummary]
    filters: NotebookListFilters


class NotebookShareResponse(BaseModel):
    id: str
    notebookId: str
    token: str
    createdBy: str
    accessScope: str
    expiresAt: Optional[str] = None
    passwordProtected: bool = False
    passwordHint: Optional[str] = None
    revokedAt: Optional[str] = None
    lastAccessedAt: Optional[str] = None
    createdAt: str


class NotebookShareListResponse(BaseModel):
    shares: List[NotebookShareResponse] = Field(default_factory=list)


class NotebookShareCreateRequest(BaseModel):
    expiresInMinutes: Optional[int] = Field(default=None, description="TTL in minutes (defaults to 7 days).")
    password: Optional[str] = Field(default=None, description="Optional password required to open the link.")
    passwordHint: Optional[str] = Field(default=None, description="Safe hint shown to recipients.")
    accessScope: Optional[str] = Field(default="view", description="Scope (`view` only for MVP).")


class NotebookShareAccessRequest(BaseModel):
    token: str = Field(..., description="Share token extracted from the link.")
    password: Optional[str] = Field(default=None, description="Password if the link is protected.")


class NotebookShareAccessResponse(BaseModel):
    notebook: NotebookSummary
    entries: List[NotebookEntryResponse]
    share: NotebookShareResponse
