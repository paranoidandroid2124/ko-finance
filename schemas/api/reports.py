"""Schemas for PDF report management APIs."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FileArtifact(BaseModel):
    path: str = Field(..., description="Relative path to the artifact from repository root.")
    exists: bool = Field(default=False, description="Whether the artifact currently exists on disk.")
    sizeBytes: Optional[int] = Field(default=None, description="File size in bytes when available.")
    downloadUrl: Optional[str] = Field(
        default=None,
        description="Signed or absolute URL for downloading the artifact when available.",
    )
    provider: Optional[str] = Field(
        default=None,
        description="Underlying storage provider identifier when available (e.g., minio, gcs).",
    )

    model_config = ConfigDict(populate_by_name=True)


class DailyBriefRun(BaseModel):
    id: UUID = Field(..., description="Unique identifier for the digest log row.")
    referenceDate: date = Field(..., description="Date the brief summarises (KST).")
    channel: str = Field(..., description="Delivery channel identifier.")
    generatedAt: datetime = Field(..., description="Timestamp when the digest entry was recorded.")
    pdf: FileArtifact = Field(..., description="PDF artefact metadata.")
    tex: FileArtifact = Field(..., description="LaTeX artefact metadata.")

    model_config = ConfigDict(populate_by_name=True)


class DailyBriefListResponse(BaseModel):
    items: List[DailyBriefRun]


class DailyBriefGenerateRequest(BaseModel):
    referenceDate: Optional[date] = Field(
        default=None,
        description="Override the target date (ISO format). Defaults to the current KST date.",
    )
    compilePdf: bool = Field(
        default=True,
        description="Compile the rendered TeX into PDF using latexmk.",
    )
    asyncMode: bool = Field(
        default=True,
        description="Run generation asynchronously via Celery. Set to false to execute synchronously.",
    )
    force: bool = Field(
        default=False,
        description="Generate even if a brief already exists for the given date.",
    )


class DailyBriefGenerateResponse(BaseModel):
    status: str = Field(..., description="Outcome of the generation request (queued/completed/already_generated).")
    referenceDate: date = Field(..., description="Target date associated with the generation job.")
    taskId: Optional[str] = Field(
        default=None,
        description="Celery task identifier when the job is queued asynchronously.",
    )
    artifactPath: Optional[str] = Field(
        default=None,
        description="Filesystem path to the rendered artefact when run synchronously.",
    )
    artifactUrl: Optional[str] = Field(
        default=None,
        description="Download URL for the rendered artefact when run synchronously and remote storage is configured.",
    )
