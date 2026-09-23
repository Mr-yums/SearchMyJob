"""[OXIO] Tests hors ligne de la boîte mail : aucune connexion réelle, aucun accès au coffre."""

import json

import pytest
from searchmyjob.integrations.mail import mailbox as mb


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(mb, "STATE", tmp_path)
    monkeypatch.setattr(mb, "CONFIG", tmp_path / "mailbox.json")
    monkeypatch.setattr(mb, "JOURNAL", tmp_path / "mailbox-sent.jsonl")
    monkeypatch.setattr(mb, "store_password", lambda name, value: None)
    monkeypatch.setattr(mb, "password", lambda name: "secret")
    return tmp_path


class FakeSMTP:
    sent = []

    def __init__(self, settings):
        self.settings = settings

    def send_message(self, message):
        FakeSMTP.sent.append(message)

    def quit(self):
        pass


def compte(**overrides):
    return mb.add("perso", "yum@gmail.com", "motdepasse", online=False, **overrides)


def test_discover_table_locale():
    found = mb.discover("yum@gmail.com", online=False)
    assert found["imap_host"] == "imap.gmail.com" and found["smtp_port"] == 465
    assert "mot de passe d" in found["note"]


def test_discover_proton_passe_par_le_bridge():
    found = mb.discover("yum@proton.me", online=False)
    assert found["imap_host"] == "127.0.0.1" and found["imap_security"] == "starttls"


def test_discover_convention_si_domaine_inconnu():
    found = mb.discover("yum@searchmyjob.invalid", online=False)
    assert found["imap_host"] == "imap.searchmyjob.invalid" and found["source"] == "convention"


def test_contexte_tls_strict_hors_boucle_locale():
    assert mb.context("imap.gmail.com").verify_mode is not mb.ssl.CERT_NONE
    assert mb.context("127.0.0.1").verify_mode is mb.ssl.CERT_NONE


def test_add_enregistre_sans_secret_sur_disque(isolate):
    compte()
    data = json.loads((isolate / "mailbox.json").read_text())
    assert data["default"] == "perso" and data["accounts"]["perso"]["imap_host"] == "imap.gmail.com"
    assert "motdepasse" not in (isolate / "mailbox.json").read_text()
    assert oct((isolate / "mailbox.json").stat().st_mode)[-3:] == "600"


def test_overrides_prioritaires():
    result = compte(imap_host="mail.perso.net", imap_port=143, imap_security="starttls")
    assert (
        result["settings"]["imap_host"] == "mail.perso.net"
        and result["settings"]["imap_port"] == 143
    )


def test_envoi_construit_un_message_complet(isolate):
    compte(from_name="Yums")
    piece = isolate / "cv.pdf"
    piece.write_bytes(b"%PDF-1.4 test")
    FakeSMTP.sent.clear()
    result = mb.send(
        "rh@example.com",
        "Candidature",
        "Bonjour,\n\nVoici mon dossier.",
        attach=[str(piece)],
        reply_to="yum@gmail.com",
        identifier="candidature-1",
        smtp_factory=FakeSMTP,
    )
    assert result["status"] == "accepted"
    message = FakeSMTP.sent[-1]
    assert message["From"] == "Yums <yum@gmail.com>" and message["Reply-To"] == "yum@gmail.com"
    assert [p.get_filename() for p in message.iter_attachments()] == ["cv.pdf"]
    assert (
        json.loads((isolate / "mailbox-sent.jsonl").read_text().splitlines()[0])["to"]
        == "rh@example.com"
    )


def test_identifiant_stable_refuse_le_doublon(isolate):
    compte()
    FakeSMTP.sent.clear()
    mb.send(
        "rh@example.com",
        "Candidature",
        "Bonjour",
        identifier="candidature-1",
        smtp_factory=FakeSMTP,
    )
    with pytest.raises(RuntimeError, match="Déjà envoyé"):
        mb.send(
            "rh@example.com",
            "Candidature",
            "Bonjour",
            identifier="candidature-1",
            smtp_factory=FakeSMTP,
        )
    assert len(FakeSMTP.sent) == 1


def test_sans_identifiant_l_envoi_reste_possible(isolate):
    compte()
    FakeSMTP.sent.clear()
    mb.send("rh@example.com", "A", "Bonjour", smtp_factory=FakeSMTP)
    mb.send("rh@example.com", "A", "Bonjour", smtp_factory=FakeSMTP)
    assert len(FakeSMTP.sent) == 2


@pytest.mark.parametrize(
    "to,subject,body",
    [
        ("pas-une-adresse", "Objet", "Corps"),
        ("rh@example.com", "", "Corps"),
        ("rh@example.com", "Objet", "   "),
        ("rh@example.com", "Objet\nInjection: oui", "Corps"),
    ],
)
def test_entrees_refusees(isolate, to, subject, body):
    compte()
    FakeSMTP.sent.clear()
    with pytest.raises(ValueError):
        mb.send(to, subject, body, smtp_factory=FakeSMTP)
    assert FakeSMTP.sent == []


def test_piece_jointe_absente_refusee(isolate):
    compte()
    with pytest.raises(ValueError, match="introuvable"):
        mb.send(
            "rh@example.com", "Objet", "Corps", attach=["/inexistant.pdf"], smtp_factory=FakeSMTP
        )


def test_sans_compte_configure():
    with pytest.raises(RuntimeError, match="Aucun compte"):
        mb.account()


class FakeIMAP:
    """Boîte factice : retient les commandes pour prouver l'absence de marquage lu."""

    commandes = []

    def __init__(self, *args, **kwargs):
        pass

    def login(self, user, secret):
        FakeIMAP.commandes.append(("login", user))

    def select(self, folder, readonly=False):
        FakeIMAP.commandes.append(("select", folder, readonly))
        return ("OK", [b"1"])

    def list(self):
        return ("OK", [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren) "/" "Envoyes"'])

    def uid(self, command, *args):
        FakeIMAP.commandes.append((command,) + args)
        if command == "SEARCH":
            return ("OK", [b"11 12"])
        brut = b"From: RH <rh@example.com>\r\nTo: yum@gmail.com\r\nSubject: =?utf-8?q?R=C3=A9ponse?=\r\nMessage-ID: <a@b>\r\n\r\nBonjour Yums.\r\n"
        return ("OK", [(b"12 (BODY[])", brut)])

    def logout(self):
        pass


@pytest.fixture
def imap(monkeypatch):
    FakeIMAP.commandes.clear()
    monkeypatch.setattr(mb, "imap_open", lambda settings: FakeIMAP())
    return FakeIMAP


def test_inbox_ne_marque_pas_lu(isolate, imap):
    compte()
    messages = mb.inbox()
    assert messages[0]["subject"] == "Réponse" and messages[0]["from"] == "RH <rh@example.com>"
    assert ("select", '"INBOX"', True) in imap.commandes
    assert all("BODY.PEEK" in a for cmd in imap.commandes if cmd[0] == "FETCH" for a in cmd[2:])


def test_read_decode_le_corps(isolate, imap):
    compte()
    message = mb.read("12")
    assert message["body"].strip() == "Bonjour Yums." and message["html"] is False


def test_read_refuse_un_uid_invalide(isolate, imap):
    compte()
    with pytest.raises(ValueError, match="UID"):
        mb.read("12 OR 1=1")


def test_folders(isolate, imap):
    compte()
    assert mb.folders() == ["INBOX", "Envoyes"]


def test_by_mx_reconnait_google_workspace(monkeypatch):
    monkeypatch.setattr(mb, "mx", lambda domain: ["1 smtp.google.com."])
    found = mb.by_mx("searchmyjob.io")
    assert found["imap_host"] == "imap.gmail.com" and found["source"] == "MX (google)"
    assert "Workspace" in found["note"]


def test_by_mx_sans_correspondance(monkeypatch):
    monkeypatch.setattr(mb, "mx", lambda domain: ["10 mx1.improvmx.com."])
    assert mb.by_mx("trackmystart.de") is None


def test_discover_prefere_la_table_locale_au_reseau(monkeypatch):
    monkeypatch.setattr(mb, "ispdb", lambda d: pytest.fail("réseau interrogé à tort"))
    monkeypatch.setattr(mb, "mx", lambda d: pytest.fail("réseau interrogé à tort"))
    assert mb.discover("yum@gmail.com")["source"] == "table locale"
