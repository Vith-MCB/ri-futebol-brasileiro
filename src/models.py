from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class FrontierItem:
    url: str
    depth: int
    priority: int
    source_url: str | None = None


@dataclass(slots=True)
class Document:
    url: str
    canonical_url: str
    domain: str
    title: str
    author: str | None
    description: str | None
    published_at: datetime | None
    collected_at: datetime
    text: str
    content_hash: str
    status_code: int
