"""Read-only monthly MCP usage. Published allowance is not an account balance."""

import asyncio
import time
from datetime import datetime, timezone

import httpx


def month_bounds(now):
    start = datetime.fromtimestamp(now, timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    end = start.replace(year=start.year + (start.month == 12), month=start.month % 12 + 1)
    return start.date().isoformat(), end.date().isoformat()


def parse_zone_usage(payload):
    if not isinstance(payload, dict) or not payload:
        raise ValueError("Statistiques indisponibles")
    count = 0
    for account in payload.values():
        if not isinstance(account, dict) or not isinstance(account.get("custom"), dict):
            raise ValueError("Format des statistiques non reconnu")
        value = account["custom"].get("reqs_serp")
        if type(value) is not int or value < 0:
            raise ValueError("Nombre de recherches non communiqué")
        count += value
    return count


class MonthlyUsage:
    def __init__(self, read_credentials, client_factory=httpx.AsyncClient, clock=time.time):
        self.read_credentials = read_credentials
        self.client_factory = client_factory
        self.clock = clock
        self.cached = None
        self.lock = asyncio.Lock()

    def invalidate(self):
        self.cached = None

    async def get(self):
        async with self.lock:
            now = self.clock()
            start, end = month_bounds(now)
            ttl = 900 if self.cached and self.cached.get("status") == "ok" else 60
            if (
                self.cached
                and self.cached["period_start"] == start
                and now - self.cached["checked_at"] < ttl
            ):
                return self.cached.copy()
            result = dict(
                allowance=5000,
                allowance_source="published_free_tier",
                period_start=start,
                renews_at=end,
                checked_at=now,
                used=None,
                remaining=None,
                zone="mcp_unlocker",
                status="unavailable",
            )
            try:
                keys = await asyncio.to_thread(self.read_credentials)
                key = keys.get("bright_key")
                if not key:
                    result.update(
                        status="not_connected",
                        message="Connecte Bright Data pour consulter la consommation MCP.",
                    )
                else:
                    async with self.client_factory(timeout=15, follow_redirects=False) as client:
                        response = await client.get(
                            "https://api.brightdata.com/zone/cost",
                            params={"zone": "mcp_unlocker", "from": start, "to": end},
                            headers={"Authorization": "Bearer " + key},
                        )
                    if response.status_code in (401, 403):
                        result.update(
                            status="forbidden",
                            message="La clé ne permet pas de lire ces statistiques.",
                        )
                    else:
                        response.raise_for_status()
                        result.update(used=parse_zone_usage(response.json()), status="ok")
            except httpx.HTTPError, ValueError:
                result["message"] = "Consommation mensuelle indisponible pour le moment."
            except Exception:
                result["message"] = "Accès au compte Bright Data indisponible."
            self.cached = result
            return result.copy()
