from __future__ import annotations

from ..rss import RssFeedAdapter, RssFeedConfig


class HimalayasAdapter(RssFeedAdapter):
    def __init__(self) -> None:
        super().__init__(
            RssFeedConfig(
                source_name="Himalayas",
                url="https://himalayas.app/jobs/rss",
            )
        )
