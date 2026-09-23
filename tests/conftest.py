from searchmyjob.api.app import create_app
from searchmyjob.integrations.ai import runner as ai_runner
from searchmyjob.integrations.search import providers as source_providers

"""[OXIO] Doubles de test partagés : aucun test ne touche au coffre, à Google ni au réseau."""
import pytest


@pytest.fixture(autouse=True)
def sealed_vault(monkeypatch):
    """[OXIO · Opus 5 · 16/09/2026] Coffre vide par défaut.

    `agents.bright_mcp` consulte le coffre pour décider de brancher le MCP Bright Data :
    sans ce double, la configuration des agents dépendrait du trousseau de la machine."""
    from searchmyjob.infrastructure import vault

    monkeypatch.setattr(vault, "read", lambda: {})


from support.mail import FakeTransport


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCHMYJOB_STATE", str(tmp_path / "state"))


from fastapi.testclient import TestClient
from searchmyjob import runtime as server
from searchmyjob.integrations.mail import gmail


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(gmail, "PORTS", (0,))
    monkeypatch.setenv("SEARCHMYJOB_STATE", str(tmp_path))

    # [Sol] No real agent or source may run in regression tests.
    async def agent(*args, **kwargs):
        return "Bilan simulé : pistes à vérifier.", "fixture"

    async def blocked(*args, **kwargs):
        raise AssertionError("Unmocked source in offline test")

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    monkeypatch.setattr(source_providers, "bright", blocked)
    monkeypatch.setattr(source_providers, "france_travail", blocked)
    # [OXIO] Aucun coffre ni Gmail réel : transport factice.
    monkeypatch.setattr(server, "GmailTransport", FakeTransport)
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1:8935") as c:
        token = c.get("/api/state").json()["token"]
        c.headers.update({"Origin": "http://127.0.0.1:8935", "X-Workspace-Token": token})
        yield c


@pytest.fixture(autouse=True)
def isolated_oauth_port(monkeypatch):
    monkeypatch.setattr(gmail, "PORTS", (0,))
