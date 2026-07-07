from __future__ import annotations

from ..rss import RssFeedAdapter, RssFeedConfig


class JobsColliderAdapter(RssFeedAdapter):
    def __init__(self) -> None:
        super().__init__(
            RssFeedConfig(
                source_name="JobsCollider",
                url="https://jobscollider.com/remote-jobs.rss",
            )
        )
