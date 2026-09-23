from datetime import datetime

from searchmyjob.api import security
from searchmyjob.config import TZ
from searchmyjob.domain.models import Settings
from searchmyjob.integrations.ai import runner as ai_runner
from searchmyjob.integrations.search import providers as source_providers
from searchmyjob.integrations.search.providers import ProviderError

"""[Sol] Regression checks for persistence, boundaries and asynchronous job behavior."""
import asyncio
import time

import pytest
from searchmyjob import runtime as server
from searchmyjob.integrations.search.providers import offer


def test_http_surface(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/state", headers={"Host": "evil.test"}).status_code == 403
    assert (
        client.post(
            "/api/profile", json={"text": "bad"}, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/profile", json={"text": "bad"}, headers={"X-Workspace-Token": "wrong"}
        ).status_code
        == 403
    )
    assert client.get("/server.py").status_code == 404
    assert client.get("/../vault.py").status_code == 404


def test_profile_and_draft_import(client):
    assert client.post("/api/profile", json={"text": "Parcours existant"}).status_code == 200
    r = client.post("/api/import", files={"file": ("cv.txt", "Nouveau CV".encode(), "text/plain")})
    assert r.json()["text"] == "Nouveau CV"
    assert client.get("/api/state").json()["profile"] == "Parcours existant"


def test_validation(client):
    assert client.post("/api/search", json={"source": "france", "keywords": ""}).status_code == 422
    assert client.post("/api/criteria", json={"department": "invalid"}).status_code == 422
    assert client.post("/api/settings", json={"enabled": True}).status_code == 422
    assert client.post("/api/settings", json={"start_hour": 20, "end_hour": 8}).status_code == 422


def test_dedup_preserves_selection(client, monkeypatch):
    async def source(c):
        return [offer("France Travail", "1", "Python")]

    monkeypatch.setattr(source_providers, "france_travail", source)
    for i in range(2):
        client.post("/api/search", json={"source": "france", "keywords": "python"})
        assert wait(client)["status"] == "completed"
        items = client.get("/api/state").json()["offers"]
        assert len(items) == 1
        if i == 0:
            client.post("/api/offers/" + items[0]["id"], json={"status": "saved"})
        else:
            assert items[0]["status"] == "saved"


def test_partial_source_failure(client, monkeypatch):
    async def ft(c):
        return [offer("France Travail", "1", "Python")]

    async def bd(c):
        raise ProviderError("Bright Data : authentification HTTP 401")

    monkeypatch.setattr(source_providers, "france_travail", ft)
    monkeypatch.setattr(source_providers, "bright", bd)
    client.post("/api/search", json={"keywords": "python", "source": "both"})
    r = wait(client)
    assert r["status"] == "completed"
    assert "401" in r["output"]
    assert len(client.get("/api/state").json()["offers"]) == 1


def test_exclusion(client, monkeypatch):
    async def ft(c):
        return [
            offer("France Travail", "1", "Stage Python"),
            offer("France Travail", "2", "Dev Python"),
        ]

    monkeypatch.setattr(source_providers, "france_travail", ft)
    client.post("/api/search", json={"source": "france", "keywords": "python", "exclude": "stage"})
    wait(client)
    assert [o["title"] for o in client.get("/api/state").json()["offers"]] == ["Dev Python"]


def test_queue_cancel(client, monkeypatch):
    async def slow(c):
        await asyncio.sleep(20)

    monkeypatch.setattr(source_providers, "france_travail", slow)
    assert (
        client.post("/api/search", json={"source": "france", "keywords": "python"}).status_code
        == 200
    )
    assert (
        client.post("/api/search", json={"source": "france", "keywords": "java"}).status_code == 409
    )
    assert client.get("/api/state").json()["criteria"]["keywords"] == "python"
    client.post("/api/cancel")
    assert wait(client)["status"] == "cancelled"


def test_chat_invalid_json_no_action(client, monkeypatch):
    async def agent(*args, **kwargs):
        return "pas de json", "fixture"

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post("/api/chat", json={"text": "bonjour", "provider": "openai"})
    assert wait(client)["status"] == "failed"
    assert client.get("/api/state").json()["profile"] == ""


def test_chat_search_action(client, monkeypatch):
    calls = []

    async def agent(*args, **kwargs):
        calls.append(args[1])
        return (
            '{"reply":"Je lance la recherche.","action":"search","criteria":{"keywords":"python","source":"france"}}'
            if len(calls) == 1
            else "Voici le bilan final de la recherche."
        ), "fixture"

    async def ft(c):
        return [offer("France Travail", "1", "Python")]

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    monkeypatch.setattr(source_providers, "france_travail", ft)
    client.post("/api/chat", json={"text": "cherche python", "provider": "openai"})
    assert wait(client)["status"] == "completed"
    state = client.get("/api/state").json()
    assert len(state["offers"]) == 1
    assert state["messages"][-1]["role"] == "assistant"
    assert state["messages"][-1]["text"] == "Voici le bilan final de la recherche."
    assert len(calls) == 2


def test_documents_version_and_download(client, monkeypatch):
    async def agent(*args, **kwargs):
        return "CV de test uniquement", "fixture"

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    row = offer("fixture", "1", "Développeur")
    client.app.state.engine.db.execute(
        "INSERT INTO offers(id,data,found,updated) VALUES (?,?,?,?)",
        (row["id"], __import__("json").dumps(row), time.time(), time.time()),
    )
    client.post("/api/generate", json={"offer_id": row["id"], "kind": "cv", "provider": "openai"})
    assert wait(client)["status"] == "failed"
    client.post("/api/profile", json={"text": "Profil de test"})
    client.post("/api/generate", json={"offer_id": row["id"], "kind": "cv", "provider": "openai"})
    assert wait(client)["status"] == "completed"
    doc = client.get("/api/state").json()["documents"][0]
    client.post("/api/documents/" + doc["id"], json={"text": "Version relue", "approved": True})
    assert client.app.state.engine.db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 1
    r = client.get("/api/documents/" + doc["id"] + "/download")
    assert r.status_code == 200 and r.content.startswith(b"PK")


def test_restart_recovers_runs(tmp_path):
    e = server.Engine(tmp_path)
    e.set("profile", "Conservé")
    e.set("settings", {**Settings().model_dump(), "enabled": True})
    e.db.execute(
        "INSERT INTO runs(id,status,created) VALUES ('interrupted','running',?)", (time.time(),)
    )
    e.db.close()
    e2 = server.Engine(tmp_path)
    assert e2.get("profile") == "Conservé"
    assert e2.get("settings")["enabled"]
    assert e2.rows("SELECT status FROM runs")[0]["status"] == "interrupted"
    e2.db.close()


def test_source_urls():
    assert offer("x", "1", "title", url="javascript:alert(1)")["url"] == ""


def test_heartbeat_window_cap_and_restart_clock(tmp_path):
    e = server.Engine(tmp_path)
    stamp = datetime(2026, 9, 14, 10, tzinfo=TZ).timestamp()
    fired = []
    e.start = lambda *a: fired.append(a[0]) or {"run_id": "fixture"}
    assert e.tick(stamp) is None
    e.set("settings", {**Settings().model_dump(), "enabled": True, "max_daily": 1})
    assert e.tick(stamp - 4 * 3600) is None  # before 08:00
    assert e.tick(stamp) == {"run_id": "fixture"}
    assert e.tick(stamp + 1) is None
    due = e.get("next_heartbeat")
    e.db.close()
    e = server.Engine(tmp_path)
    assert e.get("next_heartbeat") == due
    e.start = lambda *a: pytest.fail("daily cap bypassed")
    e.db.execute(
        "INSERT INTO runs(id,kind,status,created) VALUES ('failed','heartbeat','failed',?)",
        (stamp,),
    )
    assert e.tick(stamp + 7 * 3600) is None
    e.db.close()


def test_chat_generate_action(client, monkeypatch):
    import json

    row = offer("fixture", "chat-cv", "Développeur")
    client.app.state.engine.db.execute(
        "INSERT INTO offers(id,data,found,updated) VALUES (?,?,?,?)",
        (row["id"], json.dumps(row), time.time(), time.time()),
    )
    client.post("/api/profile", json={"text": "Profil de test confirmé"})
    calls = []

    async def agent(*args, **kwargs):
        calls.append(1)
        return (
            json.dumps(
                {
                    "reply": "Je prépare le CV.",
                    "action": "generate",
                    "offer_id": row["id"],
                    "kind": "cv",
                }
            )
            if len(calls) == 1
            else "Document de test"
        ), "fixture"

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post("/api/chat", json={"text": "Prépare mon CV pour cette offre", "provider": "openai"})
    assert wait(client)["status"] == "completed"
    assert len(client.get("/api/state").json()["documents"]) == 1


# [Sol] Vite's public origin is explicit; the private API retains token validation.
def test_dedicated_frontend_boundary(client, monkeypatch):
    monkeypatch.setattr(security, "PORT", 8937)
    monkeypatch.setattr(security, "FRONTEND_PORT", "8935")
    headers = {"Host": "127.0.0.1:8937", "Origin": "http://127.0.0.1:8935"}
    assert (
        client.post("/api/profile", json={"text": "Frontend test"}, headers=headers).status_code
        == 200
    )
    assert (
        client.get("/api/state", headers={"Host": "127.0.0.1:8937"}).json()["profile"]
        == "Frontend test"
    )
    assert (
        client.post(
            "/api/profile",
            json={"text": "bad"},
            headers={**headers, "X-Workspace-Token": "invalid"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/profile",
            json={"text": "bad"},
            headers={**headers, "Origin": "http://127.0.0.1:9999"},
        ).status_code
        == 403
    )
    assert client.get("/api/state", headers={"Host": "outside.example"}).status_code == 403


# [Sol] The same durable task owns collection AND the final conversational answer.
def test_search_stays_running_until_final_answer(client, monkeypatch):
    from threading import Event

    entered = Event()
    release = Event()
    calls = []

    async def source(c):
        calls.append(c)
        return [
            offer("Bright Data", "fresh", "Mission fictive", url="https://example.test/mission")
        ]

    async def agent(*args):
        entered.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        return "Résultats analysés, voici la piste et ses limites.", "fixture"

    monkeypatch.setattr(source_providers, "bright", source)
    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post("/api/settings", json={"provider": "openai"})
    client.post(
        "/api/search",
        json={"platforms": ["direct"], "keywords": "automatisation", "source": "bright"},
    )
    assert entered.wait(2)
    state = client.get("/api/state").json()
    assert (
        state["runs"][0]["status"] == "running"
        and "Analyse des résultats" in state["runs"][0]["phase"]
    )
    assert len(state["offers"]) == 1
    assert (
        client.post("/api/search", json={"source": "france", "keywords": "another"}).status_code
        == 409
    )
    release.set()
    assert wait(client)["status"] == "completed"
    assert len(calls) == 1
    state = client.get("/api/state").json()
    assert state["messages"][-1]["role"] == "assistant"
    assert state["messages"][-1]["text"] == "Résultats analysés, voici la piste et ses limites."
    assert state["runs"][0]["phase"] == "Terminé"


def test_report_uses_current_pass_not_old_top15(client, monkeypatch):
    import json

    old = offer("Bright Data", "old", "Ancienne piste hors recherche")
    reused = offer("Bright Data", "reused", "Piste retrouvée")
    for row, status in [(old, "new"), (reused, "saved")]:
        client.app.state.engine.db.execute(
            "INSERT INTO offers(id,data,status,found,updated) VALUES (?,?,?,?,?)",
            (row["id"], json.dumps(row), status, time.time(), time.time()),
        )

    async def source(c):
        return [reused, offer("Bright Data", "excluded", "Stage exclu")]

    payloads = []

    async def agent(provider, prompt):
        payloads.append(json.loads(prompt.split("DONNÉES DU PASSAGE : ", 1)[1]))
        return "Bilan du passage seulement.", "fixture"

    monkeypatch.setattr(source_providers, "bright", source)
    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post("/api/settings", json={"provider": "openai"})
    client.post(
        "/api/search",
        json={"platforms": ["direct"], "keywords": "IA", "source": "bright", "exclude": "stage"},
    )
    assert wait(client)["status"] == "completed"
    assert [o["id"] for o in payloads[0]["current_results"]] == [reused["id"]]
    assert payloads[0]["current_results"][0]["status"] == "saved"
    assert len(payloads) == 1


@pytest.mark.parametrize("rows", [[], [offer("Bright Data", "excluded", "Stage exclu")]])
def test_zero_matches_still_gets_final_reply_once(client, monkeypatch, rows):
    calls = []

    async def source(c):
        calls.append(c)
        return rows

    monkeypatch.setattr(source_providers, "bright", source)
    client.post("/api/settings", json={"provider": "openai"})
    client.post(
        "/api/search",
        json={"platforms": ["direct"], "keywords": "IA", "source": "bright", "exclude": "stage"},
    )
    assert wait(client)["status"] == "completed"
    assert len(calls) == 1
    assert client.get("/api/state").json()["messages"][-1]["role"] == "assistant"


def test_summary_failure_keeps_results_and_explains_without_retry(client, monkeypatch):
    calls = []

    async def source(c):
        calls.append(c)
        return [offer("Bright Data", "f", "Piste conservée", url="https://example.test/f")]

    async def agent(*args):
        raise RuntimeError("agent unavailable")

    monkeypatch.setattr(source_providers, "bright", source)
    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post("/api/search", json={"platforms": ["direct"], "keywords": "IA", "source": "bright"})
    assert wait(client)["status"] == "failed"
    s = client.get("/api/state").json()
    assert len(s["offers"]) == 1 and len(calls) == 1
    answers = [m["text"] for m in s["messages"] if m["role"] == "assistant"]
    assert (
        "synthèse IA n’a pas pu terminer" in answers[-1] and "https://example.test/f" in answers[-1]
    )


def test_stoploss_failure_answers_without_agent_or_retry(client, monkeypatch):
    calls = []

    async def source(c):
        calls.append(c)
        raise ProviderError("Stop-loss Bright Data : appels bloqués")

    async def agent(*args):
        pytest.fail("Agent must not disguise a total source failure")

    monkeypatch.setattr(source_providers, "bright", source)
    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post("/api/search", json={"platforms": ["direct"], "keywords": "IA", "source": "bright"})
    assert wait(client)["status"] == "failed"
    answers = [
        m["text"] for m in client.get("/api/state").json()["messages"] if m["role"] == "assistant"
    ]
    assert "Stop-loss" in answers[-1] and len(calls) == 1


def test_cancel_during_analysis_never_posts_late_completion(client, monkeypatch):
    from threading import Event

    entered = Event()

    async def source(c):
        return [offer("Bright Data", "c", "Piste")]

    async def agent(*args):
        entered.set()
        await asyncio.sleep(20)
        return "must never appear", "fixture"

    monkeypatch.setattr(source_providers, "bright", source)
    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post("/api/search", json={"platforms": ["direct"], "keywords": "IA", "source": "bright"})
    assert entered.wait(2)
    client.post("/api/cancel")
    assert wait(client)["status"] == "cancelled"
    assert all(
        m["text"] != "must never appear" for m in client.get("/api/state").json()["messages"]
    )


def test_heartbeat_has_single_collection_and_single_api_summary(client, monkeypatch):
    calls = []
    agents = []

    async def source(c):
        calls.append(c)
        return []

    async def agent(provider, prompt):
        agents.append(provider)
        return "Bilan fictif.", "fixture"

    monkeypatch.setattr(source_providers, "bright", source)
    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post(
        "/api/criteria", json={"platforms": ["direct"], "keywords": "IA", "source": "bright"}
    )
    client.post("/api/checkup")
    assert wait(client)["status"] == "completed"
    assert len(calls) == 1 and agents == ["openai"]
    assert client.get("/api/state").json()["messages"][-1]["role"] == "assistant"


def test_final_agent_cannot_dispatch_another_search(client, monkeypatch):
    calls = []

    async def source(c):
        calls.append(c)
        return []

    async def agent(*args):
        return '{"reply":"Je relance","action":"search","criteria":{"keywords":"autre"}}', "fixture"

    monkeypatch.setattr(source_providers, "bright", source)
    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post("/api/settings", json={"provider": "openai"})
    client.post("/api/search", json={"platforms": ["direct"], "keywords": "IA", "source": "bright"})
    assert wait(client)["status"] == "failed"
    assert len(calls) == 1
    assert client.get("/api/state").json()["criteria"]["keywords"] == "IA"


def test_progress_migration_preserves_old_database(tmp_path):
    import sqlite3

    db = sqlite3.connect(tmp_path / "workspace.sqlite3")
    db.execute(
        "CREATE TABLE runs(id TEXT PRIMARY KEY,kind TEXT,provider TEXT,status TEXT,created REAL,finished REAL,output TEXT DEFAULT '',error TEXT DEFAULT '')"
    )
    db.execute(
        "INSERT INTO runs(id,status,output) VALUES ('old','completed','Ancien bilan conservé')"
    )
    db.commit()
    db.close()
    e = server.Engine(tmp_path)
    assert e.rows("SELECT * FROM runs")[0]["output"] == "Ancien bilan conservé"
    assert e.rows("SELECT * FROM runs")[0]["phase"] == ""
    e.db.close()


# [Sol] Planned axes may each collect once; duplicates merge, failures stop further calls.
def test_multi_axis_dedup_and_budget_stop(client, monkeypatch):
    calls = []

    async def source(c):
        calls.append(c["keywords"])
        if len(calls) == 3:
            raise ProviderError("Stop-loss Bright Data : appels bloqués")
        return [
            offer(
                "Bright Data",
                "same",
                "Freelance fully remote",
                url="https://example.test/mission/same",
            )
        ]

    monkeypatch.setattr(source_providers, "bright", source)
    client.post("/api/settings", json={"provider": "openai"})
    client.post(
        "/api/search",
        json={
            "platforms": ["direct"],
            "keywords": "IA",
            "source": "bright",
            "axes": ["automatisation IA", "applications web", "intégration API", "dashboards"],
        },
    )
    result = wait(client)
    assert result["status"] == "completed" and "Stop-loss" in result["output"]
    assert calls == ["automatisation IA", "applications web", "intégration API"]
    offers = client.get("/api/state").json()["offers"]
    assert len(offers) == 1 and offers[0]["search_axes"] == [
        "automatisation IA",
        "applications web",
    ]


def test_all_four_axes_collect_once(client, monkeypatch):
    calls = []

    async def source(c):
        calls.append(c["keywords"])
        return []

    monkeypatch.setattr(source_providers, "bright", source)
    client.post(
        "/api/search",
        json={
            "platforms": ["direct"],
            "keywords": "IA",
            "source": "bright",
            "axes": ["automatisation IA", "applications web", "intégration API", "dashboards"],
        },
    )
    assert wait(client)["status"] == "completed"
    assert len(calls) == 4 and len(set(calls)) == 4


# [OXIO · Opus 5 · 16/09/2026] Le plafond local se règle depuis Connexions, sans toucher au quota du compte.
def test_local_bright_budget_is_adjustable_and_resettable(client):
    import sqlite3

    from searchmyjob.infrastructure import bright_budget as bright_budget

    with sqlite3.connect(bright_budget.budget_path()) as db:
        db.execute("UPDATE budget SET used=45,max_calls=45")
    assert client.get("/api/state").json()["bright_budget"] == {
        "used": 45,
        "limit": 45,
        "remaining": 0,
        "blocked": True,
    }
    assert client.post("/api/bright/budget", json={"limit": 300}).json() == {
        "used": 45,
        "limit": 300,
        "remaining": 255,
        "blocked": False,
    }
    assert client.post("/api/bright/budget", json={"reset": True}).json() == {
        "used": 0,
        "limit": 300,
        "remaining": 300,
        "blocked": False,
    }
    assert client.post("/api/bright/budget", json={"limit": 0}).status_code == 422
    assert client.post("/api/bright/budget", json={"limit": 99999}).status_code == 422
    # Le plafond survit au redémarrage de l'application.
    assert client.get("/api/state").json()["bright_budget"]["limit"] == 300


# [OXIO · Opus 4.8 · 16/09/2026] Le mode enregistré oriente le cadrage réellement envoyé à l'agent.
def test_objectif_mode_switches_agent_framing(client, monkeypatch):
    tasks = []

    async def rec(name, task):
        tasks.append(task)
        return ('{"reply":"ok","action":"none"}', "fixture")

    monkeypatch.setattr(ai_runner, "run_agent", rec)
    # Défaut = emploi.
    client.post("/api/chat", json={"text": "bonjour", "provider": "openai"})
    wait(client)
    assert any("conseiller emploi" in t for t in tasks)
    assert not any("PROSPECTION COMMERCIALE" in t for t in tasks)
    # Bascule en prospection via les critères.
    tasks.clear()
    crit = client.get("/api/state").json()["criteria"]
    crit["objectif"] = "prospection"
    assert client.post("/api/criteria", json=crit).status_code == 200
    client.post("/api/chat", json={"text": "trouve des clients", "provider": "openai"})
    wait(client)
    assert any("PROSPECTION COMMERCIALE" in t for t in tasks)  # rôle du chat
    assert any("mode PROSPECTION" in t for t in tasks)  # consignes communes
    assert not any("conseiller emploi" in t for t in tasks)


from support.polling import wait
