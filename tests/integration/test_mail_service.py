from searchmyjob.integrations.ai import runner as ai_runner

"""[OXIO] Courrier : cycle de vie des brouillons, garde-fous d'envoi et routes serveur, hors ligne."""
import json
import sqlite3
import time

import pytest
from searchmyjob.application.mail import MailService
from searchmyjob.domain.mail import Envelope, MailError, split_subject
from searchmyjob.infrastructure.repositories.outbox import Outbox
from support.mail import FakeTransport


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def service():
    return MailService(FakeTransport(connected=True))


def test_envelope_validation():
    with pytest.raises(MailError, match="Destinataire"):
        Envelope("pas-une-adresse", "Objet", "corps").validate()
    with pytest.raises(MailError, match="objet"):
        Envelope("rh@ex.com", "  ", "corps").validate()
    with pytest.raises(MailError, match="vide"):
        Envelope("rh@ex.com", "Objet", "  ").validate()
    assert Envelope("Nom <rh@ex.com>", "Objet", "corps").validate()


def test_split_subject_from_agent_answer():
    assert split_subject("Objet : Candidature dev\n\nBonjour,\nCorps") == (
        "Candidature dev",
        "Bonjour,\nCorps",
    )
    assert split_subject("Sujet: X\nCorps") == ("X", "Corps")
    assert split_subject("Bonjour sans objet") == ("", "Bonjour sans objet")


def test_outbox_lifecycle_and_idempotent_send(db, service):
    box = Outbox(db)
    draft = box.propose("Objet", "Corps", offer_id="o1", origin="openai")
    assert draft["status"] == "draft" and draft["to"] == ""
    with pytest.raises(MailError, match="Coche"):
        box.send(draft["id"], service, confirm=False)
    with pytest.raises(MailError, match="Destinataire"):
        box.send(draft["id"], service, confirm=True)
    assert box.get(draft["id"])["error"].startswith("Destinataire")
    box.update(draft["id"], "rh@ex.com", "Objet final", "Corps final")
    sent = box.send(draft["id"], service, confirm=True, name="Jean")
    assert sent["status"] == "sent" and sent["message_id"] == "msg-1" and sent["error"] == ""
    envelope = service.transport.sent[0]
    assert envelope.name == "Jean" and envelope.identifier == "email-" + draft["id"]
    with pytest.raises(MailError, match="déjà parti"):
        box.send(draft["id"], service, confirm=True)
    with pytest.raises(MailError, match="ne se modifie plus"):
        box.update(draft["id"], "x@y.z", "a", "b")
    with pytest.raises(MailError, match="envoyé ne peut pas"):
        box.discard(draft["id"])
    assert len(service.transport.sent) == 1


def test_outbox_discard_blocks_send(db, service):
    box = Outbox(db)
    d = box.propose("O", "C")
    box.update(d["id"], "rh@ex.com", "O", "C")
    assert box.discard(d["id"])["status"] == "discarded"
    with pytest.raises(MailError, match="écarté"):
        box.send(d["id"], service, confirm=True)


def test_send_requires_connection(db):
    service = MailService(FakeTransport(connected=False))
    box = Outbox(db)
    d = box.propose("O", "C")
    box.update(d["id"], "rh@ex.com", "O", "C")
    with pytest.raises(MailError, match="Aucune boîte"):
        box.send(d["id"], service, confirm=True)


def test_transport_failure_is_recorded_and_retryable(db, service):
    box = Outbox(db)
    d = box.propose("O", "C")
    box.update(d["id"], "rh@ex.com", "O", "C")
    service.transport.fail_with = "Gmail indisponible"
    with pytest.raises(MailError, match="indisponible"):
        box.send(d["id"], service, confirm=True)
    assert box.get(d["id"])["status"] == "draft" and "indisponible" in box.get(d["id"])["error"]
    service.transport.fail_with = ""
    assert box.send(d["id"], service, confirm=True)["status"] == "sent"


def test_service_connect_flow_and_status_cache():
    transport = FakeTransport()
    service = MailService(transport)
    assert service.status()["connected"] is False
    with pytest.raises(MailError, match="JSON"):
        service.connect(b"pas du json")
    with pytest.raises(MailError, match="volumineux"):
        service.connect(b"{" + b" " * MailService.MAX_CLIENT_JSON + b"}")
    url = service.connect(
        json.dumps({"installed": {"client_id": "c", "client_secret": "s"}}).encode()
    )
    assert url.startswith("https://") and service.status()["pending"] is True
    transport.complete()
    status = service.status()
    assert (
        status["connected"] is True
        and status["address"] == "moi@example.com"
        and status["pending"] is False
    )
    service.disconnect()
    assert service.status()["connected"] is False


def test_send_test_goes_to_self(service):
    receipt = service.send_test(name="Jean")
    assert receipt.to == "moi@example.com" and service.transport.sent[0].name == "Jean"


# ---------------------------------------------------------------- routes serveur
from support.polling import wait


def _offer(client):
    from searchmyjob.integrations.search.providers import offer

    row = offer("fixture", "mail-1", "Développeur Python")
    client.app.state.engine.db.execute(
        "INSERT INTO offers(id,data,found,updated) VALUES (?,?,?,?)",
        (row["id"], json.dumps(row), time.time(), time.time()),
    )
    return row


def test_state_exposes_mail_and_emails(client):
    s = client.get("/api/state").json()
    assert s["mail"] == {
        "connected": False,
        "address": "",
        "pending": False,
        "auth_url": "",
        "error": "",
        "sender_name": "",
    }
    assert s["emails"] == []


def test_connect_route_returns_auth_url_then_status(client):
    r = client.post("/api/mail/connect", files={"file": ("bad.json", b"{}", "application/json")})
    assert r.status_code == 422
    good = json.dumps({"installed": {"client_id": "c", "client_secret": "s"}}).encode()
    r = client.post(
        "/api/mail/connect", files={"file": ("client_secret.json", good, "application/json")}
    )
    assert r.status_code == 200 and r.json()["auth_url"].startswith("https://")
    assert client.get("/api/state").json()["mail"]["pending"] is True
    client.app.state.engine.mail.transport.complete()
    assert client.get("/api/state").json()["mail"]["connected"] is True
    assert client.post("/api/mail/prefs", json={"sender_name": "Jean Dupont"}).status_code == 200
    assert client.post("/api/mail/test", json={}).json()["to"] == "moi@example.com"
    assert client.app.state.engine.mail.transport.sent[0].name == "Jean Dupont"
    assert client.post("/api/mail/disconnect", json={}).status_code == 200
    assert client.get("/api/state").json()["mail"]["connected"] is False


def test_agent_email_generation_creates_draft_not_send(client, monkeypatch):
    row = _offer(client)
    client.post("/api/profile", json={"text": "Profil de test"})

    async def agent(*a, **k):
        return (
            "Objet : Candidature — Développeur Python\n\nBonjour,\n\nCorps de test.\n\n[nom]",
            "fixture",
        )

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post(
        "/api/generate", json={"offer_id": row["id"], "kind": "email", "provider": "openai"}
    )
    assert wait(client)["status"] == "completed"
    s = client.get("/api/state").json()
    assert len(s["emails"]) == 1 and s["documents"] == []
    draft = s["emails"][0]
    assert draft["subject"] == "Candidature — Développeur Python" and draft["body"].startswith(
        "Bonjour"
    )
    assert (
        draft["status"] == "draft"
        and draft["origin"] == "openai"
        and draft["offer_id"] == row["id"]
    )
    assert client.app.state.engine.mail.transport.sent == []
    assert "Courrier" in s["messages"][-1]["text"]


def test_chat_can_propose_email_draft(client, monkeypatch):
    row = _offer(client)
    client.post("/api/profile", json={"text": "Profil"})
    calls = []

    async def agent(*a, **k):
        calls.append(1)
        return (
            json.dumps(
                {
                    "reply": "Je prépare l’e-mail.",
                    "action": "generate",
                    "offer_id": row["id"],
                    "kind": "email",
                }
            )
            if len(calls) == 1
            else "Objet : Test\n\nCorps"
        ), "fixture"

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post(
        "/api/chat", json={"text": "prépare un mail pour cette offre", "provider": "openai"}
    )
    assert wait(client)["status"] == "completed"
    assert client.get("/api/state").json()["emails"][0]["subject"] == "Test"


def test_email_routes_full_cycle(client):
    row = _offer(client)
    r = client.post("/api/emails", json={"offer_id": row["id"]})
    draft = r.json()
    assert (
        r.status_code == 200
        and draft["subject"] == "Candidature — Développeur Python"
        and draft["origin"] == "toi"
    )
    assert client.post("/api/emails", json={"offer_id": "inconnu"}).status_code == 404
    # Envoi refusé sans confirmation, sans destinataire, sans boîte connectée.
    assert (
        client.post("/api/emails/" + draft["id"] + "/send", json={"confirm": False}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/emails/" + draft["id"],
            json={"to": "rh@ex.com", "subject": "Objet", "body": "Corps"},
        ).status_code
        == 200
    )
    r = client.post("/api/emails/" + draft["id"] + "/send", json={"confirm": True})
    assert r.status_code == 422 and "Aucune boîte" in r.json()["detail"]
    client.app.state.engine.mail.transport.complete()
    r = client.post("/api/emails/" + draft["id"] + "/send", json={"confirm": True})
    assert r.status_code == 200 and r.json()["status"] == "sent"
    assert (
        client.post("/api/emails/" + draft["id"] + "/send", json={"confirm": True}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/emails/" + draft["id"], json={"to": "x@y.zz", "subject": "a", "body": "b"}
        ).status_code
        == 409
    )
    assert client.post("/api/emails/" + draft["id"] + "/discard", json={}).status_code == 409
    assert client.post("/api/emails/inconnu/send", json={"confirm": True}).status_code == 404
    assert len(client.app.state.engine.mail.transport.sent) == 1


def test_email_from_letter_document(client, monkeypatch):
    row = _offer(client)
    client.post("/api/profile", json={"text": "Profil"})

    async def agent(*a, **k):
        return "Madame, Monsieur,\nLettre de test.", "fixture"

    monkeypatch.setattr(ai_runner, "run_agent", agent)
    client.post(
        "/api/generate", json={"offer_id": row["id"], "kind": "letter", "provider": "openai"}
    )
    assert wait(client)["status"] == "completed"
    doc = client.get("/api/state").json()["documents"][0]
    draft = client.post("/api/emails", json={"document_id": doc["id"]}).json()
    assert (
        draft["body"].startswith("Madame")
        and draft["document_id"] == doc["id"]
        and draft["offer_id"] == row["id"]
    )
    assert draft["subject"] == "Candidature — Développeur Python"
    assert (
        client.post("/api/emails/" + draft["id"] + "/discard", json={}).json()["status"]
        == "discarded"
    )
