import asyncio
import json
import socket

import pytest
from searchmyjob.application import agent_tools as agent_tools
from searchmyjob.domain.context import native_session
from searchmyjob.integrations.ai import runner as ai_runner
from searchmyjob.integrations.search import public_pages as public_pages
from searchmyjob.integrations.search.providers import offer
from support.polling import wait


def test_chat_native_tool_chain_saves_sources_and_draft_without_nested_agents(client, monkeypatch):
    seen = []

    async def web(query, geo):
        seen.append((query, geo))
        return [
            offer(
                "Bright Data",
                "recruiter",
                "Cabinet recrutement IT",
                url="https://cabinet.example/contact",
            )
        ]

    client.app.state.engine.agent_tools.web_search = web
    monkeypatch.setattr(
        agent_tools,
        "read_public_page",
        lambda url: {
            "url": url,
            "text": "Contact professionnel : recrutement@cabinet.example",
            "links": [],
        },
    )

    async def agent(provider, prompt):
        descriptor = native_session.get()
        assert descriptor
        token = descriptor["token"]
        service = client.app.state.engine.agent_tools
        assert "send_email" not in service.tools
        result = await service.call(
            token, "search_web", {"query": "cabinet recrutement freelance Python"}
        )
        assert result["results"][0]["lead_type"] == "contact_or_website"
        page = await service.call(
            token, "read_public_page", {"url": "https://cabinet.example/contact"}
        )
        assert page["contacts"][0]["email"] == "recrutement@cabinet.example"
        assert page["contacts"][0]["source_url"] == "https://cabinet.example/contact"
        draft = await service.call(
            token,
            "draft_email",
            {
                "offer_id": page["offer_id"],
                "to": page["contacts"][0]["email"],
                "subject": "Présentation",
                "body": "Brouillon à relire",
            },
        )
        assert draft["status"] == "draft"
        return json.dumps(
            {
                "reply": "Source conservée et brouillon préparé.",
                "action": "search",
                "criteria": {"keywords": "ne pas relancer"},
            }
        ), "fixture"

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    response = client.post(
        "/api/chat", json={"text": "Trouve un cabinet et prépare un e-mail", "provider": "openai"}
    )
    assert response.status_code == 200 and wait(client)["status"] == "completed"
    assert len(seen) == 1
    state = client.get("/api/state").json()
    assert state["emails"][0]["status"] == "draft" and not state["emails"][0]["sent_at"]
    assert client.app.state.engine.agent_tools.sessions == {}
    assert len(client.app.state.engine.rows("SELECT * FROM agent_tool_calls")) == 3
    assert (
        client.app.state.engine.rows("SELECT source FROM offer_sources WHERE kind='page'")[0][
            "source"
        ]
        == "Lecture HTTPS directe"
    )
    assert state["messages"][-1]["text"] == "Source conservée et brouillon préparé."


def test_runtime_requires_active_capability_and_bounds_operations(client, monkeypatch):
    captured = []

    async def agent(provider, prompt):
        token = native_session.get()["token"]
        captured.append(token)
        service = client.app.state.engine.agent_tools
        assert len(service.catalog(token)["tools"]) == 16
        service.sessions[token].calls = service.MAX_CALLS
        with pytest.raises(ValueError):
            await service.call(token, "get_profile", {})
        return json.dumps({"reply": "Test terminé", "action": "none"}), "fixture"

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    assert client.get("/api/agent/runtime").status_code == 403
    client.post("/api/chat", json={"text": "test", "provider": "kimi"})
    assert wait(client)["status"] == "completed"
    assert (
        client.get("/api/agent/runtime", headers={"X-Agent-Session": captured[0]}).status_code
        == 403
    )


@pytest.mark.parametrize(
    "ip", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "fc00::1", "192.168.1.1"]
)
def test_public_reader_rejects_private_dns(monkeypatch, ip):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))],
    )
    with pytest.raises(ValueError):
        public_pages.public_target("https://cabinet.example/contact")


@pytest.mark.parametrize(
    "url", ["http://example.com", "https://user:password@example.com", "https://example.com:8443"]
)
def test_public_reader_rejects_other_transports(url):
    with pytest.raises(ValueError):
        public_pages.public_target(url)


def test_public_reader_pins_target_and_extracts_contact_links(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    host, ip, _, _ = public_pages.public_target("https://example.com/contact")
    assert (host, ip) == ("example.com", "93.184.216.34")
    parser = public_pages.PageText("https://example.com")
    parser.feed(
        '<script>evil@invalid.example</script><a href="mailto:jobs@example.com">Contact</a><a href="/contact">Contact complet</a>'
    )
    assert "jobs@example.com" in parser.parts
    assert all("evil" not in text for text in parser.parts)
    assert parser.links == ["https://example.com/contact"]


def test_agent_cancellation_revokes_session(client, monkeypatch):
    async def agent(provider, prompt):
        assert native_session.get()
        await asyncio.sleep(20)

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post("/api/chat", json={"text": "test annulation", "provider": "openai"})
    client.post("/api/cancel", json={})
    assert wait(client)["status"] == "cancelled"
    assert client.app.state.engine.agent_tools.sessions == {}


def test_gzip_pages_are_bounded_after_decompression():
    import gzip

    assert public_pages.decode_gzip(gzip.compress(b"Public contact page")) == b"Public contact page"
    with pytest.raises(ValueError):
        public_pages.decode_gzip(gzip.compress(b"x" * 1_000_001))
    with pytest.raises(ValueError):
        public_pages.decode_gzip(b"invalid")
