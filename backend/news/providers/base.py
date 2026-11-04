"""Common article shape returned by every provider."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class NormalizedArticle:
    title: str
    source_url: str
    source_name: str = ""
    description: str = ""
    content: str = ""
    image_url: str = ""
    author: str = ""
    published_at: datetime | None = None
    provider: str = ""
    feed_key: str = ""
    category_slug: str = ""
    is_breaking: bool = False
    search_query: str = ""
    external_id: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        if data["published_at"]:
            data["published_at"] = data["published_at"].isoformat()
        return data


@dataclass
class ProviderResult:
    articles: list[NormalizedArticle] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    providers_attempted: int = 0
    providers_succeeded: int = 0
