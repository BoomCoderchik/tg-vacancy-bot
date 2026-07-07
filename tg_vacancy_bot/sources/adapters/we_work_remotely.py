from __future__ import annotations

from ..rss import RssFeedAdapter, RssFeedConfig


class WeWorkRemotelyAdapter(RssFeedAdapter):
    def __init__(self) -> None:
        super().__init__(
            RssFeedConfig(
                source_name="We Work Remotely",
                url="https://weworkremotely.com/categories/remote-programming-jobs.rss",
            )
        )
