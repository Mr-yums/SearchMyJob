from searchmyjob.integrations.search import providers as source_providers

"""Shared web/MCP contracts, task ownership and persistence without external calls."""
import asyncio

from searchmyjob.integrations.search.providers import offer
from support.polling import wait


def test_agent_reads_are_bounded_and_do_not_expose_session(client):
    session = client.get("/api/agent/session").json()
    assert "criteria" in session["search_schema"]["properties"]
    for endpoint in ("profile", "offers", "watch", "usage"):
        response = client.get("/api/agent/" + endpoint)
        assert response.status_code == 200
        assert session["token"] not in response.text
    assert client.get("/api/agent/offers?limit=51").status_code == 422
    assert client.get("/api/agent/offers?offset=-1").status_code == 422
    assert client.get("/api/agent/offers?status=bad").status_code == 422
    assert client.get("/api/agent/runs/missing").status_code == 404
    assert client.get("/api/agent/documents/missing").status_code == 404
    assert client.get("/api/agent/emails/missing").status_code == 404


def test_mcp_search_shares_queue_and_keeps_saved_preferences(client, monkeypatch):
    calls = []

    async def source(criteria):
        calls.append(criteria)
        await asyncio.sleep(0.1)
        return [offer("France Travail", "one", "Python API")]

    monkeypatch.setattr(source_providers, "france_travail", source)
    client.post(
        "/api/criteria",
        json={
            "source": "france",
            "keywords": "préférence durable",
            "exclude": "Upwork",
            "remote": True,
        },
    )
    response = client.post(
        "/api/agent/search", json={"criteria": {"source": "france", "keywords": "Python"}}
    )
    assert response.status_code == 200
    rid = response.json()["run_id"]
    assert (
        client.post("/api/search", json={"source": "france", "keywords": "autre"}).status_code
        == 409
    )
    assert wait(client)["status"] == "completed"
    assert client.get("/api/agent/runs/" + rid).json()["status"] == "completed"
    assert client.get("/api/agent/profile").json()["criteria"]["keywords"] == "préférence durable"
    assert len(calls) == 1
    assert calls[0]["exclude"] == "Upwork" and calls[0]["remote"] is True
    listed = client.get("/api/agent/offers?query=python&limit=1").json()
    assert listed["total"] == 1 and len(listed["items"]) == 1
    oid = listed["items"][0]["id"]
    assert client.get("/api/offers/" + oid + "/dossier").json()["offer"]["title"] == "Python API"


def test_draft_lifecycle_is_visible_without_send(client, monkeypatch):
    async def source(criteria):
        return [offer("France Travail", "one", "Python API")]

    monkeypatch.setattr(source_providers, "france_travail", source)
    client.post("/api/search", json={"source": "france", "keywords": "Python"})
    wait(client)
    oid = client.get("/api/agent/offers").json()["items"][0]["id"]
    client.post("/api/profile", json={"text": "Python et API"})
    assert (
        client.post(
            "/api/generate", json={"offer_id": oid, "kind": "letter", "provider": "openai"}
        ).status_code
        == 200
    )
    assert wait(client)["status"] == "completed"
    dossier = client.get("/api/offers/" + oid + "/dossier").json()
    document = client.get("/api/agent/documents/" + dossier["documents"][0]["id"]).json()
    assert document["approved"] == 0 and document["text"]
    client.post("/api/generate", json={"offer_id": oid, "kind": "email", "provider": "openai"})
    assert wait(client)["status"] == "completed"
    dossier = client.get("/api/offers/" + oid + "/dossier").json()
    email = client.get("/api/agent/emails/" + dossier["emails"][0]["id"]).json()
    assert email["status"] == "draft" and email["sent_at"] is None
    assert client.post("/api/generate", json={"offer_id": "missing"}).status_code == 404


def test_agent_mutations_keep_existing_boundary(client):
    assert (
        client.post("/api/agent/search", json={}, headers={"X-Workspace-Token": "bad"}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/agent/search", json={}, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/agent/search",
            json={"criteria": {"source": "france", "keywords": "test", "platforms": ["unknown"]}},
        ).status_code
        == 422
    )


def test_downloadable_client_config_has_no_credentials(client):
    response = client.get("/api/integrations/mcp-config")
    assert response.status_code == 200
    config = response.json()["mcpServers"]["searchmyjob"]
    assert config["args"][0].endswith("/mcp/workspace-server.mjs")
    assert config["env"] == {"SEARCHMYJOB_API": "http://127.0.0.1:8935"}
    assert client.get("/api/agent/session").json()["token"] not in response.text
