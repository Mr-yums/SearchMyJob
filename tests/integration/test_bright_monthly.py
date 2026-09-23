import asyncio
from datetime import datetime, timezone

import httpx
import pytest
from searchmyjob.integrations.search.monthly import MonthlyUsage, month_bounds, parse_zone_usage


def stamp(date):
    return datetime.fromisoformat(date).replace(tzinfo=timezone.utc).timestamp()


def test_month_range_includes_last_day_and_year_boundary():
    assert month_bounds(stamp("2026-12-31")) == ("2026-12-01", "2027-01-01")
    assert month_bounds(stamp("2028-02-29")) == ("2028-02-01", "2028-03-01")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        {"account": {}},
        {"account": {"custom": {}}},
        {"account": {"custom": {"reqs_serp": -1}}},
        {"account": {"custom": {"reqs_serp": True}}},
    ],
)
def test_unknown_usage_never_becomes_zero(payload):
    with pytest.raises(ValueError):
        parse_zone_usage(payload)


def test_read_only_remote_usage_cached_without_inventing_balance():
    calls = []
    now = [stamp("2026-09-15")]

    def request(req):
        calls.append(req)
        assert (
            req.method == "GET"
            and req.url.host == "api.brightdata.com"
            and req.url.path == "/zone/cost"
        )
        assert req.url.params["zone"] == "mcp_unlocker" and req.url.params["to"] == "2026-10-01"
        assert req.headers["Authorization"] == "Bearer test-secret"
        return httpx.Response(
            200, json={"private-account": {"custom": {"reqs_serp": 7, "cost": 0.0105}}}
        )

    service = MonthlyUsage(
        lambda: {"bright_key": "test-secret"},
        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(request), **kw),
        lambda: now[0],
    )

    async def check():
        first, second = await asyncio.gather(service.get(), service.get())
        assert first == second and first["used"] == 7 and first["remaining"] is None
        assert "test-secret" not in str(first) and "private-account" not in str(first)
        assert len(calls) == 1
        service.invalidate()
        await service.get()
        assert len(calls) == 2

    asyncio.run(check())


def test_new_month_does_not_keep_previous_count():
    now = [stamp("2026-09-30T23:59:59")]
    calls = []

    def request(req):
        calls.append(req)
        if len(calls) == 1:
            return httpx.Response(200, json={"account": {"custom": {"reqs_serp": 7}}})
        return httpx.Response(403, text="private-secret-error")

    service = MonthlyUsage(
        lambda: {"bright_key": "test-secret"},
        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(request), **kw),
        lambda: now[0],
    )

    async def check():
        assert (await service.get())["used"] == 7
        now[0] = stamp("2026-10-01")
        result = await service.get()
        assert result["used"] is None and result["status"] == "forbidden"
        assert result["period_start"] == "2026-10-01" and "private-secret-error" not in str(result)
        await service.get()
        assert len(calls) == 2

    asyncio.run(check())


def test_missing_key_does_not_call_network():
    def blocked(**kw):
        raise AssertionError("Network must not run")

    result = asyncio.run(MonthlyUsage(lambda: {}, blocked).get())
    assert result["status"] == "not_connected" and result["used"] is None
