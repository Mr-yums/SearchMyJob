"""Offline contracts: geography, structured listings, budget and resumable polling."""

import asyncio
import json

import httpx
import pytest
from searchmyjob.domain.models import Criteria
from searchmyjob.domain.search_quality import checks, search_plan
from searchmyjob.infrastructure import bright_budget
from searchmyjob.integrations.search import job_platforms as jobs
from searchmyjob.integrations.search.providers import ProviderError


@pytest.mark.parametrize("country", ["it", "de", "be", "fr", "gb", "us", "ca", "jp"])
def test_country_reaches_both_platforms(country):
    criteria = Criteria(country=country.upper(), keywords="infirmier", freelance=False).model_dump()
    for platform in ("linkedin", "indeed"):
        payload = jobs.discovery_input(platform, criteria)
        assert payload["country"] == country.upper()
        assert payload["location"]
        assert "infirmier" in payload.values()
    assert jobs.discovery_input("indeed", criteria)["domain"] == (
        "www.indeed.com"
        if country == "us"
        else ("uk" if country == "gb" else country) + ".indeed.com"
    )


def test_profession_and_constraints_are_not_personal_defaults():
    c = Criteria(country="de", keywords="Koch", platforms=["linkedin", "indeed"]).model_dump()
    assert not c["freelance"] and not c["remote"]
    plans = search_plan(c)
    assert [p["_platform"] for p in plans] == ["linkedin", "indeed"]
    assert all(p["country"] == "de" and p["keywords"] == "Koch" for p in plans)
    q = checks(
        {"title": "Cook", "description": "CDI. On-site. Fluent English. Travel required."}, c
    )
    assert all(v["state"] != "conflict" for v in q["conditions"].values())
    assert (
        checks({"description": "Closed."}, c)["conditions"]["availability"]["state"] == "conflict"
    )
    assert Criteria(axes=["infirmier", "comptable", "cuisinier"]).axes[-1] == "cuisinier"
    with pytest.raises(ValueError):
        Criteria(country="zz")


@pytest.fixture
def collection(monkeypatch):
    bright_budget.initialize()
    monkeypatch.setattr(jobs, "read", lambda: {"bright_key": "fixture-secret"})
    real_client = httpx.AsyncClient

    def install(handler):
        monkeypatch.setattr(
            jobs.httpx,
            "AsyncClient",
            lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(handler)),
        )

    return install


def test_trigger_poll_normalize_and_budget(collection):
    requests = []
    c = Criteria(country="be", keywords="comptable", platforms=["indeed"]).model_dump()

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/trigger"):
            assert request.url.params["dataset_id"] == jobs.DATASETS["indeed"]
            assert request.url.params["limit_per_input"] == "20"
            assert request.url.params["discover_by"] == "keyword"
            assert json.loads(request.content) == [
                {
                    "keyword_search": "comptable",
                    "location": "Belgium",
                    "country": "BE",
                    "domain": "be.indeed.com",
                }
            ]
            return httpx.Response(200, json={"snapshot_id": "sd_fixture"})
        if "/progress/" in request.url.path:
            return httpx.Response(200, json={"status": "ready"})
        return httpx.Response(
            200,
            json=[
                {
                    "url": "https://be.indeed.com/viewjob?jk=abc",
                    "job_title": "Comptable",
                    "company_name": "Fixture",
                    "description_text": "CDI. Fluent English.",
                    "job_type": ["Full-time"],
                    "location": "Bruxelles",
                }
            ],
        )

    collection(handler)
    rows = asyncio.run(jobs.discover("indeed", c))
    assert len(rows) == 1 and rows[0]["location"] == "Bruxelles"
    assert rows[0]["company"] == "Fixture"
    assert rows[0]["collection_method"] == "brightdata_scraper"
    assert checks(rows[0], c)["verification"] == "platform_data"
    assert bright_budget.status()["used"] == 1
    assert len(requests) == 3


def test_failed_poll_resumes_without_new_paid_trigger(collection):
    triggered = []
    fail = True

    def handler(request):
        if request.url.path.endswith("/trigger"):
            triggered.append(1)
            return httpx.Response(200, json={"snapshot_id": "sd_resume"})
        if "/progress/" in request.url.path:
            return httpx.Response(503 if fail else 200, json={"status": "ready"})
        return httpx.Response(200, json=[])

    collection(handler)
    criteria = Criteria(country="it", keywords="cuoco").model_dump()
    with pytest.raises(ProviderError, match="503"):
        asyncio.run(jobs.discover("linkedin", criteria))
    fail = False
    bright_budget.set_limit(1)  # Download remains possible even at the call limit.
    assert asyncio.run(jobs.discover("linkedin", criteria)) == []
    assert len(triggered) == 1 and bright_budget.status()["used"] == 1


def test_denied_collection_and_budget_never_retry(collection):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"error": "fixture-secret"})

    collection(handler)
    bright_budget.set_limit(1)
    c = Criteria(country="fr", keywords="infirmier").model_dump()
    with pytest.raises(ProviderError, match="401") as exc:
        asyncio.run(jobs.discover("indeed", c))
    assert "fixture-secret" not in str(exc.value)
    with pytest.raises(ProviderError, match="Stop-loss"):
        asyncio.run(jobs.discover("indeed", c))
    assert len(calls) == 1


def test_invalid_and_error_results_are_not_empty_success():
    for data in (
        {"error": "no"},
        [{"error": "no"}],
        [{"url": "https://indeed.com.attacker.test/viewjob?jk=1", "job_title": "Fake"}],
    ):
        with pytest.raises(ProviderError):
            jobs.normalize("indeed", data, {"country": "fr"})


def test_activation_requires_country_and_selected_source_key(client, monkeypatch):
    from searchmyjob.infrastructure import vault
    from searchmyjob.integrations.ai import provider

    monkeypatch.setattr(provider, "saved", lambda _: {"tested_at": 1})
    body = {"country": "it", "source": "bright", "keywords": "cuoco", "platforms": ["indeed"]}
    assert client.post("/api/activation", json={"provider": "openai"}).status_code == 422
    assert client.post("/api/activation", json=body).status_code == 422
    monkeypatch.setattr(vault, "read", lambda: {"bright_key": "fixture"})
    assert client.post("/api/activation", json={**body, "source": "france"}).status_code == 422
    assert not client.get("/api/activation").json()["completed"]
    assert client.post("/api/activation", json=body).status_code == 200
    saved = client.get("/api/state").json()["criteria"]
    assert all(saved[k] == v for k, v in body.items())
    assert {"de", "be", "it", "fr"}.issubset(client.get("/api/search/options").json()["countries"])


def test_cache_separates_countries_and_platforms(client, monkeypatch):
    from searchmyjob.integrations.search import providers

    seen = []

    async def source(criteria):
        seen.append((criteria["country"], criteria["_platform"]))
        return []

    monkeypatch.setattr(providers, "bright", source)
    engine = client.app.state.engine

    async def run():
        for country in ("fr", "de", "fr"):
            await engine.search(
                Criteria(
                    country=country, keywords="comptable", platforms=["linkedin", "indeed"]
                ).model_dump()
            )

    asyncio.run(run())
    assert seen == [("fr", "linkedin"), ("fr", "indeed"), ("de", "linkedin"), ("de", "indeed")]
