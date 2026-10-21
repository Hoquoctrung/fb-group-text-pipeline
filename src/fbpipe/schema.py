"""Pydantic schemas shared by collection stages."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Attachment(BaseModel):
    """Minimal attachment metadata."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["photo", "video", "link", "file", "other"]
    url_domain: str | None = None


class Comment(BaseModel):
    """Comment associated with a post. Collection is disabled in the 48-hour scope."""

    model_config = ConfigDict(extra="forbid")

    comment_id: str
    parent_id: str | None = None
    author_hash: str
    created_at: datetime | None = None
    text: str
    reactions_total: int | None = None


class RawPost(BaseModel):
    """Validated Bronze representation of one post."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    post_id: str
    group_id: str
    permalink_path: str | None = None
    author_hash: str
    created_at: datetime | None = None
    collected_at: datetime
    text: str
    reactions_total: int | None = None
    reactions_by_type: dict[str, int] = Field(default_factory=dict)
    comments_count: int | None = None
    shares_count: int | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    comments: list[Comment] = Field(default_factory=list)
    source: Literal["playwright_graphql", "playwright_dom", "import", "synthetic"]
    content_hash: str
