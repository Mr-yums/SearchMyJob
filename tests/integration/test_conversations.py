import asyncio
import json
import sqlite3

from searchmyjob.infrastructure.repositories.conversations import ConversationRepository
from searchmyjob.integrations.ai import runner as ai_runner
from support.polling import wait


def test_existing_history_migrates_without_changes(tmp_path):
    db = sqlite3.connect(tmp_path / "old.sqlite3", isolation_level=None)
    db.row_factory = sqlite3.Row
    db.executescript(
        "CREATE TABLE messages(id TEXT PRIMARY KEY,role TEXT,provider TEXT,text TEXT,created REAL); CREATE TABLE runs(id TEXT PRIMARY KEY,status TEXT);"
    )
    db.execute(
        "INSERT INTO messages VALUES (?,?,?,?,?)", ("old", "user", "toi", "Historique conservé", 1)
    )
    before = tuple(db.execute("SELECT * FROM messages").fetchone())
    repo = ConversationRepository(db)
    assert tuple(db.execute("SELECT * FROM messages").fetchone()) == before
    assert repo.messages("main")[0]["text"] == "Historique conservé"
    ConversationRepository(db)
    assert db.execute("SELECT count(*) FROM conversation_messages").fetchone()[0] == 1
    db.close()


def test_threads_have_isolated_agent_context_and_persist(client, monkeypatch):
    seen = []

    async def agent(provider, prompt):
        seen.append(prompt)
        return json.dumps({"reply": "Réponse propre au fil", "action": "none"}), "fixture"

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    a = client.post("/api/conversations", json={}).json()["id"]
    b = client.post("/api/conversations", json={"title": "Autre sujet"}).json()["id"]
    client.post(
        "/api/chat", json={"text": "Secret du fil A", "conversation_id": a, "provider": "openai"}
    )
    wait(client)
    client.post(
        "/api/chat", json={"text": "Sujet du fil B", "conversation_id": b, "provider": "openai"}
    )
    wait(client)
    assert "Secret du fil A" not in seen[-1]
    assert len(client.get("/api/state", params={"conversation_id": a}).json()["messages"]) == 2
    assert len(client.get("/api/state", params={"conversation_id": b}).json()["messages"]) == 2
    assert client.get("/api/state").json()["messages"] == []
    assert (
        client.post("/api/conversations/" + a + "/rename", json={"title": "Candidature A"}).json()[
            "title"
        ]
        == "Candidature A"
    )
    repo = ConversationRepository(client.app.state.engine.db)
    assert repo.get(a)["title"] == "Candidature A" and len(repo.messages(a)) == 2


def test_running_reply_stays_in_original_thread(client, monkeypatch):
    async def agent(*args):
        await asyncio.sleep(0.15)
        return json.dumps({"reply": "Réponse A", "action": "none"}), "fixture"

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    a = client.post("/api/conversations", json={}).json()["id"]
    client.post("/api/chat", json={"text": "A", "conversation_id": a, "provider": "openai"})
    b = client.post("/api/conversations", json={}).json()["id"]
    assert client.get("/api/state", params={"conversation_id": b}).json()["messages"] == []
    assert client.post("/api/conversations/" + a + "/reset", json={}).status_code == 409
    assert wait(client)["conversation_id"] == a
    assert (
        client.get("/api/state", params={"conversation_id": a}).json()["messages"][-1]["text"]
        == "Réponse A"
    )
    assert client.get("/api/state", params={"conversation_id": b}).json()["messages"] == []


def test_reset_archives_history_and_preserves_workspace(client, monkeypatch):
    async def agent(*args):
        return json.dumps({"reply": "Texte conservé", "action": "none"}), "fixture"

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post("/api/profile", json={"text": "Profil partagé"})
    client.post("/api/chat", json={"text": "Ancien échange", "provider": "openai"})
    wait(client)
    count = client.app.state.engine.db.execute("SELECT count(*) FROM messages").fetchone()[0]
    reset = client.post("/api/conversations/main/reset", json={})
    assert reset.status_code == 200
    new = reset.json()["id"]
    state = client.get("/api/state", params={"conversation_id": new}).json()
    assert state["messages"] == [] and state["profile"] == "Profil partagé"
    assert len(client.get("/api/state?conversation_id=main").json()["messages"]) == count
    assert (
        client.app.state.engine.db.execute("SELECT count(*) FROM messages").fetchone()[0] == count
    )
    assert (
        client.post("/api/chat", json={"text": "Interdit", "conversation_id": "main"}).status_code
        == 409
    )
    assert client.get("/api/state").json()["conversation_id"] == new
    assert (
        client.post("/api/chat", json={"text": "Inconnu", "conversation_id": "missing"}).status_code
        == 404
    )
    assert client.post("/api/conversations", json={"title": " "}).status_code == 422
