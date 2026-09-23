"""Watch operations for the workspace."""

import asyncio
import time
from datetime import datetime

from searchmyjob.config import TZ


class WatchService:
    """Watch use cases sharing the workspace unit of work."""

    def __init__(self, engine):
        self.engine = engine

    async def heartbeat(self, provider=None):
        settings = self.engine.get("settings")
        return await self.engine.search_and_report(
            provider or settings["provider"],
            self.engine.get("criteria"),
            request="Faire un bilan des opportunités",
            instructions=settings["instructions"],
        )

    def tick(self, now):
        s = self.engine.get("settings")
        local = datetime.fromtimestamp(now, TZ)
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        count = self.engine.runs.heartbeat_count(midnight)
        if (
            s["enabled"]
            and s["start_hour"] <= local.hour < s["end_hour"]
            and count < s["max_daily"]
            and now >= self.engine.get("next_heartbeat")
            and not (self.engine.task and not self.engine.task.done())
        ):
            self.engine.set("next_heartbeat", now + s["interval_hours"] * 3600)
            return self.engine.start("heartbeat", s["provider"], self.engine.heartbeat)
        return None

    async def scheduler(self):
        while True:
            await asyncio.sleep(15)
            self.engine.tick(time.time())
