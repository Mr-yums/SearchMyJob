def test_activation_once_and_persisted(client, monkeypatch):
    from searchmyjob.integrations.ai import provider as ai_provider

    monkeypatch.setattr(ai_provider, "saved", lambda provider: {"tested_at": 1})
    from searchmyjob.infrastructure import vault

    monkeypatch.setattr(vault, "read", lambda: {"bright_key": "fixture"})
    assert client.get("/api/activation").json()["completed"] is False
    r = client.post(
        "/api/activation",
        json={
            "country": "be",
            "source": "bright",
            "platforms": ["indeed"],
            "provider": "kimi",
            "profile": "Python et API",
            "keywords": "Python",
        },
    )
    assert r.status_code == 200 and r.json()["completed"]
    state = client.get("/api/state").json()
    assert state["profile"] == "Python et API"
    assert state["criteria"]["keywords"] == "Python"
    assert state["criteria"]["country"] == "be"
    assert state["criteria"]["source"] == "bright"
    assert state["criteria"]["platforms"] == ["indeed"]
    assert "paiement pour candidater" in state["criteria"]["exclude"]
    assert state["settings"]["provider"] == "kimi"
    assert state["settings"]["enabled"] is False
    assert state["runs"] == []
    assert client.get("/api/workspace-memory").json()["preferences"]["provider"] == "kimi"
    assert (
        client.post(
            "/api/activation", json={"country": "fr", "provider": "openai", "profile": "Overwrite"}
        ).json()
        == r.json()
    )
    assert client.get("/api/state").json()["profile"] == "Python et API"
    client.app.state.engine.onboarding.initialize()
    assert client.get("/api/activation").json() == r.json()


def test_existing_workspace_is_not_reset(client):
    client.post("/api/profile", json={"text": "Profil existant"})
    client.app.state.engine.db.execute("DELETE FROM config WHERE key='activation'")
    previous = client.get("/api/state").json()
    client.app.state.engine.onboarding.initialize()
    activation = client.get("/api/activation").json()
    assert activation["completed"] and activation["existing_workspace"]
    client.post("/api/activation", json={"provider": "kimi", "profile": "Overwrite"})
    current = client.get("/api/state").json()
    assert current["profile"] == previous["profile"]
    assert current["settings"] == previous["settings"]


def test_invalid_activation_does_not_complete(client):
    assert client.post("/api/activation", json={"provider": "unknown"}).status_code == 422
    assert (
        client.post("/api/activation", json={}, headers={"X-Workspace-Token": "bad"}).status_code
        == 403
    )
    assert client.get("/api/activation").json()["completed"] is False
