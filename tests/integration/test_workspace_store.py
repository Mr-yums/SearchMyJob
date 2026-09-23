import asyncio
import json
import time

import pytest
from searchmyjob import runtime as server
from searchmyjob.domain.models import Criteria
from searchmyjob.integrations.search import providers as source_providers
from searchmyjob.integrations.search.providers import ProviderError, offer
from support.polling import wait


def test_search_cache_survives_restart_and_can_refresh(tmp_path, monkeypatch):
    calls = []

    async def source(c):
        calls.append(c)
        return [offer("Bright Data", "1", "Mission Python", url="https://example.org/jobs/1")]

    monkeypatch.setattr(source_providers, "bright", source)
    c = Criteria(keywords="python", source="bright", platforms=["direct"]).model_dump()
    e = server.Engine(tmp_path)
    asyncio.run(e.search(c))
    e.db.close()
    e = server.Engine(tmp_path)
    result = asyncio.run(e.search(c))
    assert len(calls) == 1 and "Cache SQLite" in result
    assert len(e.offers()) == 1
    asyncio.run(e.search(c, force=True))
    assert len(calls) == 2
    e.db.execute("UPDATE search_cache SET created=?", (time.time() - 7 * 3600,))
    asyncio.run(e.search(c))
    assert len(calls) == 3
    assert len(e.store.dossier(e.offers()[0]["id"])["sources"]) >= 1
    e.db.close()


def test_failed_search_is_not_cached_and_empty_success_is(tmp_path, monkeypatch):
    calls = []

    async def source(c):
        calls.append(c)
        if len(calls) == 1:
            raise ProviderError("fixture")
        return []

    monkeypatch.setattr(source_providers, "bright", source)
    e = server.Engine(tmp_path)
    c = Criteria(keywords="python", source="bright", platforms=["direct"]).model_dump()
    with pytest.raises(ProviderError):
        asyncio.run(e.search(c))
    assert e.db.execute("SELECT count(*) FROM search_cache").fetchone()[0] == 0
    asyncio.run(e.search(c))
    asyncio.run(e.search(c))
    assert len(calls) == 2
    e.db.close()


def test_preferences_draft_and_history(client):
    prefs = {
        "theme": "sombre",
        "page_width": "full",
        "agent_width": "normal",
        "layout": 2,
        "panels": ["conversation", "offers", "documents", "heartbeat"],
        "tabs": ["conversation", "offers"],
        "provider": "openai",
        "collapsed": True,
    }
    assert client.post("/api/preferences", json=prefs).status_code == 200
    assert (
        client.post(
            "/api/heartbeat-draft",
            json={"values": {"enabled": True, "instructions": "Préférence brouillon"}},
        ).status_code
        == 200
    )
    data = client.get("/api/workspace-memory").json()
    assert data["preferences"] == prefs and data["heartbeat_draft"]["enabled"]
    assert not client.get("/api/state").json()["settings"]["enabled"]
    client.post("/api/settings", json={"instructions": "Nouvelle consigne"})
    assert client.get("/api/workspace-memory").json()["heartbeat_draft"] is None
    history = client.get("/api/config-history").json()
    assert any(r["key"] == "preferences" and json.loads(r["value"]) == prefs for r in history)
    assert sum(r["key"] == "settings" for r in history) >= 2
    assert client.post("/api/preferences", json={**prefs, "panels": ["invalid"]}).status_code == 422


def test_import_original_is_persistent_deduplicated_and_downloadable(client):
    data = b"CV professionnel\nPython"
    first = client.post("/api/import", files={"file": ("cv.txt", data, "text/plain")}).json()
    second = client.post("/api/import", files={"file": ("cv.txt", data, "text/plain")}).json()
    assert first["id"] == second["id"]
    imports = client.get("/api/state").json()["imports"]
    assert len(imports) == 1
    assert client.get("/api/imports/" + first["id"] + "/download").content == data
    assert client.get("/api/state").json()["profile"] == ""


def test_page_dossier_contacts_and_csv_keep_provenance(client, monkeypatch):
    row = offer(
        "Bright Data",
        "id",
        "=unsafe formula",
        url="https://www.upwork.com/freelance-jobs/apply/job",
    )
    client.app.state.engine.db.execute(
        "INSERT INTO offers(id,data,found,updated) VALUES (?,?,?,?)",
        (row["id"], json.dumps(row), time.time(), time.time()),
    )
    calls = []

    async def page(url):
        calls.append(url)
        return (
            "Mission publique. Contact professionnel : recrutement@example.org. Compétence Python."
        )

    monkeypatch.setattr(source_providers, "bright_page", page)
    assert client.post("/api/offers/" + row["id"] + "/collect").status_code == 200
    assert wait(client)["status"] == "completed"
    result = client.get("/api/offers/" + row["id"] + "/dossier").json()
    assert result["page"]["application_mode"] == "platform"
    assert result["page"]["contacts"][0]["email"] == "recrutement@example.org"
    assert result["page"]["contacts"][0]["source_url"] == row["url"]
    assert client.post("/api/offers/" + row["id"] + "/collect").json()["cached"]
    assert len(calls) == 1
    csv = client.get("/api/export/offers.csv").text
    assert "'=unsafe formula" in csv and "recrutement@example.org" in csv
    assert (
        client.get("/api/sources/" + result["sources"][0]["id"]).json()["content"]
        == result["page"]["content"]
    )
    assert (
        client.get("/api/state").json()["offers"][0]["contact_candidates"][0]["status"]
        == "à vérifier"
    )


def test_page_without_email_stays_unknown_and_research_preserves_page(tmp_path, monkeypatch):
    e = server.Engine(tmp_path)
    row = offer("Bright Data", "one", "Python", url="https://example.org/jobs/one")

    async def source(c):
        return [row.copy()]

    monkeypatch.setattr(source_providers, "bright", source)
    c = Criteria(keywords="python", source="bright", platforms=["direct"]).model_dump()
    asyncio.run(e.search(c))
    e.store.save_page(row["id"], row["url"], "Annonce sans adresse de contact.")
    asyncio.run(e.search(c, force=True))
    e.db.close()
    e = server.Engine(tmp_path)
    page = e.store.page(row["id"])
    assert page["contacts"] == [] and page["application_mode"] == "contact_not_found"
    assert page["content"] == "Annonce sans adresse de contact."
    assert e.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    e.db.close()
