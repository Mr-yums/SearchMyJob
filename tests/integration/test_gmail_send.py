"""[OXIO] Tests hors ligne du connecteur Gmail : aucun appel réseau, aucun accès au coffre réel."""

import base64
import json
from email import message_from_bytes

import pytest


@pytest.fixture
def gmail(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCHMYJOB_STATE", str(tmp_path))
    import importlib

    from searchmyjob.integrations.mail import gmail as gmail_send

    importlib.reload(gmail_send)
    # Force le repli fichier 0600 : les tests ne doivent jamais écrire dans Secret Service.
    monkeypatch.setattr(gmail_send, "vault_read", None)
    monkeypatch.setattr(gmail_send, "vault_save", None)
    return gmail_send


def _client_file(tmp_path, node="installed"):
    p = tmp_path / "client_secret_x.json"
    p.write_text(
        json.dumps({node: {"client_id": "cid.apps.googleusercontent.com", "client_secret": "sek"}})
    )
    return p


def test_parse_client_installed_and_rejects_web(gmail, tmp_path):
    assert gmail.parse_client(_client_file(tmp_path, "installed"))[0].startswith("cid")
    # Vécu le 15/09/2026 : un identifiant « Application Web » refuse la redirection locale.
    with pytest.raises(ValueError, match="Application de bureau"):
        gmail.parse_client(_client_file(tmp_path, "web"))


def test_oauth_flow_start_is_non_blocking_and_times_out(gmail):
    flow = gmail.OAuthFlow("cid", "sek", timeout=1)
    url = flow.start()
    assert flow.state == "pending" and "access_type=offline" in url and "prompt=consent" in url
    assert "gmail.send" in url and "127.0.0.1" in url
    with pytest.raises(RuntimeError, match="non reçue"):
        flow.wait(timeout=5)
    assert flow.state == "failed"


def test_parse_client_rejects_incomplete(gmail, tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"installed": {"client_id": "only"}}))
    with pytest.raises(ValueError):
        gmail.parse_client(p)


def test_build_sets_from_replyto_and_encodes(gmail):
    msg = gmail._build(
        "rh@example.com",
        "Candidature",
        "Corps du message",
        sender="moi@gmail.com",
        reply_to="moi@gmail.com",
        name="Jean Dupont",
    )
    assert msg["From"] == "Jean Dupont <moi@gmail.com>"
    assert msg["Reply-To"] == "moi@gmail.com"
    # Le message repart bien en RFC822 encodable en base64url (ce qu'attend l'API Gmail).
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    back = message_from_bytes(base64.urlsafe_b64decode(raw))
    assert back["Subject"] == "Candidature"


@pytest.mark.parametrize("to,subject", [("", "o"), ("pasunemail", "o"), ("a@b.com", "   ")])
def test_build_rejects_invalid(gmail, to, subject):
    with pytest.raises(ValueError):
        gmail._build(to, subject, "corps")


def test_attachment_size_guard(gmail, tmp_path):
    big = tmp_path / "gros.bin"
    big.write_bytes(b"0" * (gmail.MAX_ATTACH + 1))
    with pytest.raises(ValueError):
        gmail._build("a@b.com", "o", "c", sender="m@g.com", attachments=[str(big)])


def test_status_logout_roundtrip(gmail):
    assert gmail.status() == {"connected": False, "address": ""}
    gmail.save_secret(
        {"client_id": "c", "client_secret": "s", "refresh_token": "r", "address": "moi@gmail.com"}
    )
    assert gmail.status() == {"connected": True, "address": "moi@gmail.com"}
    # Refuge fichier écrit en 0600.
    assert oct(gmail.FALLBACK.stat().st_mode)[-3:] == "600"
    gmail.logout()
    assert gmail.status()["connected"] is False
    assert not gmail.FALLBACK.exists()


def test_duplicate_send_guard(gmail):
    gmail._record("offre-42", "rh@x.com", "Candidature", "moi@gmail.com")
    assert gmail._already_sent("offre-42") is True
    assert gmail._already_sent("offre-99") is False
    assert oct(gmail.JOURNAL.stat().st_mode)[-3:] == "600"


def test_send_refuses_duplicate_without_network(gmail):
    gmail.save_secret(
        {"client_id": "c", "client_secret": "s", "refresh_token": "r", "address": "m@g.com"}
    )
    gmail._record("offre-1", "rh@x.com", "Sujet", "m@g.com")
    with pytest.raises(RuntimeError, match="déjà envoyé"):
        gmail.send("rh@x.com", "Sujet", "corps", identifier="offre-1")


def test_access_token_without_connection(gmail):
    with pytest.raises(RuntimeError, match="Aucune boîte"):
        gmail.access_token()
