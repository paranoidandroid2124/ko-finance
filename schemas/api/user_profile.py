from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class InterestTagRequest(BaseModel):
    tag: str = Field(..., description="Interest tag to add or remove")


class InterestTagsRequest(BaseModel):
    tags: List[str] = Field(..., description="Full list of interest tags")


class InterestTagsResponse(BaseModel):
    tags: List[str]


__all__ = ["InterestTagRequest", "InterestTagsRequest", "InterestTagsResponse"]
