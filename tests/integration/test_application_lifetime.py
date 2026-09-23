"""App instances and persisted revisions must stay independent."""

import asyncio
import sqlite3

import pytest
from fastapi.testclient import TestClient
from searchmyjob.api.app import create_app
from searchmyjob.domain.errors import WorkspaceError
from searchmyjob.runtime import Engine


def test_two_apps_do_not_share_tokens_data_or_lifetime(tmp_path):
    with TestClient(create_app(tmp_path / "first"), base_url="http://127.0.0.1:8935") as first:
        first.app.state.engine.set("profile", "First workspace")
        token = first.get("/api/state").json()["token"]
        with TestClient(
            create_app(tmp_path / "second"), base_url="http://127.0.0.1:8935"
        ) as second:
            state = second.get("/api/state").json()
            assert state["profile"] == ""
            assert state["token"] != token
            rejected = second.post(
                "/api/profile",
                json={"text": "wrong workspace"},
                headers={"Origin": "http://127.0.0.1:8935", "X-Workspace-Token": token},
            )
            assert rejected.status_code == 403
        assert first.get("/api/state").json()["profile"] == "First workspace"


def test_shutdown_cancels_and_persists_the_active_job(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:8935") as client:

        async def start():
            return app.state.engine.start("test", "fixture", lambda: asyncio.sleep(60))

        client.portal.call(start)
    db = sqlite3.connect(tmp_path / "workspace.sqlite3")
    try:
        assert db.execute("SELECT status FROM runs").fetchone()[0] == "cancelled"
    finally:
        db.close()


def test_missing_document_rolls_back_revision_transaction(tmp_path):
    engine = Engine(tmp_path)
    try:
        with pytest.raises(WorkspaceError):
            engine.records.revise_document("missing", "replacement", True)
        assert not engine.db.in_transaction
        assert engine.db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 0
        engine.set("profile", "still writable")
        assert engine.get("profile") == "still writable"
    finally:
        engine.db.close()
