"""Data model for collected editorials."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional


def generate_id(url: str, title: str, publish_date: str) -> str:
    raw = f"{url}|{title}|{publish_date}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class EditorialArchive:
    id: str
    title: str
    publisher: str
    publisher_name: str
    url: str
    source_type: str = "media"
    status: str = "active"
    publish_date: str = ""
    collected_at: str = ""
    last_revisit_at: Optional[str] = None
    summary: Optional[str] = None
    content_hash: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    changed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "EditorialArchive":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})
