from __future__ import annotations

from ..rss import RssFeedAdapter, RssFeedConfig


class RealWorkFromAnywhereAdapter(RssFeedAdapter):
    def __init__(self) -> None:
        super().__init__(
            RssFeedConfig(
                source_name="Real Work From Anywhere",
                url="https://www.realworkfromanywhere.com/rss.xml",
            )
        )
