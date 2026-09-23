"""[OXIO] Boîte mail personnelle : découverte des serveurs, IMAP lecture seule, SMTP explicite."""

import argparse
import email
import imaplib
import json
import os
import re
import smtplib
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from email.policy import default as policy_default
from email.utils import formatdate, make_msgid, parseaddr
from pathlib import Path
from xml.etree import ElementTree

STATE = Path(
    os.environ.get("SEARCHMYJOB_STATE", str(Path.home() / ".local/state/searchmyjob-community"))
)
CONFIG = STATE / "mailbox.json"
JOURNAL = STATE / "mailbox-sent.jsonl"
TIMEOUT = 30
MAX_BODY = 200_000
# [OXIO] Réglages hors ligne des fournisseurs courants ; sinon autoconfig Thunderbird puis heuristique.
PROVIDERS = {
    ("gmail.com", "googlemail.com"): (
        "imap.gmail.com",
        993,
        "ssl",
        "smtp.gmail.com",
        465,
        "ssl",
        "Google exige un mot de passe d'application (validation en deux étapes activée).",
    ),
    ("outlook.com", "outlook.fr", "hotmail.com", "hotmail.fr", "live.com", "live.fr", "msn.com"): (
        "outlook.office365.com",
        993,
        "ssl",
        "smtp.office365.com",
        587,
        "starttls",
        "Microsoft a fermé l'authentification par mot de passe sur les comptes personnels : seul OAuth2 (Thunderbird) fonctionne encore.",
    ),
    ("yahoo.com", "yahoo.fr"): (
        "imap.mail.yahoo.com",
        993,
        "ssl",
        "smtp.mail.yahoo.com",
        465,
        "ssl",
        "Yahoo exige un mot de passe d'application.",
    ),
    ("protonmail.com", "protonmail.ch", "proton.me", "pm.me"): (
        "127.0.0.1",
        1143,
        "starttls",
        "127.0.0.1",
        1025,
        "starttls",
        "Proton passe par Proton Bridge, qui doit tourner ; le mot de passe est celui affiché par Bridge, pas celui du compte.",
    ),
    ("icloud.com", "me.com", "mac.com"): (
        "imap.mail.me.com",
        993,
        "ssl",
        "smtp.mail.me.com",
        587,
        "starttls",
        "Apple exige un mot de passe d'application.",
    ),
    ("free.fr",): ("imap.free.fr", 993, "ssl", "smtp.free.fr", 465, "ssl", ""),
    ("orange.fr", "wanadoo.fr"): ("imap.orange.fr", 993, "ssl", "smtp.orange.fr", 465, "ssl", ""),
    ("sfr.fr", "neuf.fr"): ("imap.sfr.fr", 993, "ssl", "smtp.sfr.fr", 465, "ssl", ""),
    ("laposte.net",): ("imap.laposte.net", 993, "ssl", "smtp.laposte.net", 465, "ssl", ""),
    ("gmx.com", "gmx.fr", "gmx.net"): ("imap.gmx.com", 993, "ssl", "mail.gmx.com", 465, "ssl", ""),
    ("zoho.com", "zoho.eu"): ("imap.zoho.eu", 993, "ssl", "smtp.zoho.eu", 465, "ssl", ""),
    ("infomaniak.com", "ik.me", "etik.com"): (
        "mail.infomaniak.com",
        993,
        "ssl",
        "mail.infomaniak.com",
        465,
        "ssl",
        "",
    ),
    ("ovh.net", "ovh.com"): ("ssl0.ovh.net", 993, "ssl", "ssl0.ovh.net", 465, "ssl", ""),
}


def now():
    return datetime.now(timezone.utc).isoformat()


def loopback(host):
    return host in ("127.0.0.1", "::1", "localhost")


def context(host):
    # [OXIO] Proton Bridge présente un certificat auto-signé sur la boucle locale ; ailleurs, vérification stricte.
    if loopback(host):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return ssl.create_default_context()


def preset(key, note=""):
    settings = dict(
        zip(
            (
                "imap_host",
                "imap_port",
                "imap_security",
                "smtp_host",
                "smtp_port",
                "smtp_security",
                "note",
            ),
            PROVIDERS[key],
        )
    )
    return settings | ({"note": note} if note else {})


def discover(address, online=True):
    """Réglages IMAP/SMTP : table locale, autoconfig Thunderbird, hébergeur déduit du MX, puis convention."""
    domain = address.rsplit("@", 1)[-1].lower()
    for domains in PROVIDERS:
        if domain in domains:
            return preset(domains) | {"source": "table locale"}
    if online:
        for found in (ispdb(domain), by_mx(domain)):
            if found:
                return found
    return {
        "imap_host": f"imap.{domain}",
        "imap_port": 993,
        "imap_security": "ssl",
        "smtp_host": f"smtp.{domain}",
        "smtp_port": 465,
        "smtp_security": "ssl",
        "note": "Réglages devinés par convention : à vérifier avec `test`.",
        "source": "convention",
    }


# [OXIO] Un domaine personnel est souvent hébergé ailleurs ; le MX désigne l'hébergeur réel.
HOSTS = (
    (
        "google",
        "gmail.com",
        "Domaine hébergé par Google Workspace : mot de passe d'application requis, ou OAuth2 via Thunderbird.",
    ),
    (
        "outlook",
        "outlook.com",
        "Domaine hébergé par Microsoft 365 : l'authentification par mot de passe est souvent désactivée par l'administrateur.",
    ),
    ("protonmail", "proton.me", "Domaine hébergé par Proton : passer par Proton Bridge."),
    ("proton.me", "proton.me", "Domaine hébergé par Proton : passer par Proton Bridge."),
    ("ovh", "ovh.net", "Domaine hébergé par OVH."),
    ("infomaniak", "infomaniak.com", "Domaine hébergé par Infomaniak."),
    ("zoho", "zoho.com", "Domaine hébergé par Zoho."),
    ("yandex", "yahoo.com", ""),
)


def mx(domain):
    """Enregistrements MX par DNS-over-HTTPS, sans dépendance système."""
    if not re.fullmatch(r"[a-z0-9.-]{1,253}", domain):
        return []
    try:
        with urllib.request.urlopen(
            f"https://dns.google/resolve?name={domain}&type=MX", timeout=15
        ) as response:
            answers = json.loads(response.read(100_000)).get("Answer", [])
    except Exception:
        return []
    return [str(a.get("data", "")).lower() for a in answers if a.get("type") == 15]


def by_mx(domain):
    records = " ".join(mx(domain))
    if not records:
        return None
    for needle, key, note in HOSTS:
        if needle in records:
            for domains in PROVIDERS:
                if key in domains:
                    return preset(domains, note) | {"source": f"MX ({needle})"}
    return None


def ispdb(domain):
    """Base publique de configuration Thunderbird (Mozilla ISPDB)."""
    if not re.fullmatch(r"[a-z0-9.-]{1,253}", domain):
        return None
    try:
        with urllib.request.urlopen(
            f"https://autoconfig.thunderbird.net/v1.1/{domain}", timeout=15
        ) as response:
            root = ElementTree.fromstring(response.read(200_000))
    except Exception:
        return None
    found = {"note": "", "source": "autoconfig Thunderbird"}
    for server in root.iter("incomingServer"):
        if server.get("type") == "imap" and "imap_host" not in found:
            found |= {
                "imap_host": server.findtext("hostname", ""),
                "imap_port": int(server.findtext("port", "993")),
                "imap_security": "starttls"
                if server.findtext("socketType", "") == "STARTTLS"
                else "ssl",
            }
    for server in root.iter("outgoingServer"):
        if server.get("type") == "smtp" and "smtp_host" not in found:
            found |= {
                "smtp_host": server.findtext("hostname", ""),
                "smtp_port": int(server.findtext("port", "587")),
                "smtp_security": "starttls"
                if server.findtext("socketType", "") == "STARTTLS"
                else "ssl",
            }
    return found if found.get("imap_host") and found.get("smtp_host") else None


def config():
    data = json.loads(CONFIG.read_text()) if CONFIG.exists() else {"accounts": {}, "default": ""}
    return data


def write_config(data):
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    CONFIG.chmod(0o600)


def store_password(name, password):
    from searchmyjob.infrastructure import vault

    vault.save({"mailbox_" + name: password})


def password(name):
    from searchmyjob.infrastructure import vault

    value = vault.read().get("mailbox_" + name)
    if not value:
        raise RuntimeError("Aucun mot de passe enregistré pour cette boîte.")
    return value


def forget_password(name):
    from searchmyjob.infrastructure import vault

    vault.save({"mailbox_" + name: None})


def account(name=""):
    data = config()
    name = name or data.get("default", "")
    if not name or name not in data["accounts"]:
        raise RuntimeError(
            "Aucun compte configuré ; utiliser `add`."
            if not data["accounts"]
            else f"Compte inconnu : {name}"
        )
    return name, data["accounts"][name]


def imap_open(settings):
    host, port = settings["imap_host"], settings["imap_port"]
    if settings["imap_security"] == "starttls":
        box = imaplib.IMAP4(host, port, timeout=TIMEOUT)
        box.starttls(context(host))
    else:
        box = imaplib.IMAP4_SSL(host, port, ssl_context=context(host), timeout=TIMEOUT)
    box.login(settings.get("username") or settings["address"], password(settings["name"]))
    return box


def smtp_open(settings):
    host, port = settings["smtp_host"], settings["smtp_port"]
    if settings["smtp_security"] == "starttls":
        server = smtplib.SMTP(host, port, timeout=TIMEOUT)
        server.ehlo()
        server.starttls(context=context(host))
        server.ehlo()
    else:
        server = smtplib.SMTP_SSL(host, port, context=context(host), timeout=TIMEOUT)
    server.login(settings.get("username") or settings["address"], password(settings["name"]))
    return server


def test(name=""):
    """Vérifie les deux connexions sans lire ni envoyer quoi que ce soit."""
    name, settings = account(name)
    settings = settings | {"name": name}
    report = {"account": name, "address": settings["address"]}
    try:
        box = imap_open(settings)
        try:
            report["imap"] = "ok"
            report["folders"] = len(box.list()[1] or [])
        finally:
            box.logout()
    except Exception as error:
        report["imap"] = f"échec : {error}"
    try:
        server = smtp_open(settings)
        try:
            report["smtp"] = "ok"
        finally:
            server.quit()
    except Exception as error:
        report["smtp"] = f"échec : {error}"
    return report


def folders(name=""):
    name, settings = account(name)
    box = imap_open(settings | {"name": name})
    try:
        return [
            re.sub(r'^.*"/" ', "", line.decode(errors="replace")).strip('"')
            for line in (box.list()[1] or [])
        ]
    finally:
        box.logout()


def summary(raw, uid):
    message = email.message_from_bytes(raw, policy=policy_default)
    return {
        "uid": uid,
        "from": str(message.get("From", "")),
        "to": str(message.get("To", "")),
        "subject": str(message.get("Subject", "")),
        "date": str(message.get("Date", "")),
        "message_id": str(message.get("Message-ID", "")),
        "attachments": [part.get_filename() or "sans-nom" for part in message.iter_attachments()],
    }


def inbox(name="", folder="INBOX", limit=20, unread=False):
    """Derniers messages, sans marquer lu (EXAMINE + BODY.PEEK)."""
    name, settings = account(name)
    box = imap_open(settings | {"name": name})
    try:
        box.select(f'"{folder}"', readonly=True)
        status, data = box.uid("SEARCH", None, "UNSEEN" if unread else "ALL")
        if status != "OK":
            raise RuntimeError("Recherche IMAP refusée")
        uids = (data[0] or b"").split()[-max(1, min(limit, 200)) :]
        messages = []
        for uid in reversed(uids):
            status, parts = box.uid("FETCH", uid.decode(), "(BODY.PEEK[HEADER])")
            if status == "OK" and parts and isinstance(parts[0], tuple):
                messages.append(summary(parts[0][1], uid.decode()))
        return messages
    finally:
        box.logout()


def read(uid, name="", folder="INBOX", attachments_to=None):
    """Message complet ; les pièces jointes ne sont écrites que si un dossier est demandé."""
    if not re.fullmatch(r"[0-9]{1,20}", str(uid)):
        raise ValueError("UID IMAP invalide")
    name, settings = account(name)
    box = imap_open(settings | {"name": name})
    try:
        box.select(f'"{folder}"', readonly=True)
        status, parts = box.uid("FETCH", str(uid), "(BODY.PEEK[])")
        if status != "OK" or not parts or not isinstance(parts[0], tuple):
            raise RuntimeError("Message introuvable")
        raw = parts[0][1]
    finally:
        box.logout()
    message = email.message_from_bytes(raw, policy=policy_default)
    body = message.get_body(preferencelist=("plain", "html"))
    result = summary(raw, str(uid)) | {
        "body": (body.get_content()[:MAX_BODY] if body else ""),
        "html": bool(body and body.get_content_type() == "text/html"),
    }
    if attachments_to:
        target = Path(attachments_to)
        target.mkdir(mode=0o700, parents=True, exist_ok=True)
        saved = []
        for part in message.iter_attachments():
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", part.get_filename() or "piece-jointe")[:120]
            path = target / safe
            path.write_bytes(part.get_payload(decode=True) or b"")
            path.chmod(0o600)
            saved.append(str(path))
        result["saved"] = saved
    return result


def journal(entry):
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with JOURNAL.open("a") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    JOURNAL.chmod(0o600)


def already_sent(identifier):
    if not identifier or not JOURNAL.exists():
        return None
    for line in JOURNAL.read_text().splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("id") == identifier:
            return entry
    return None


def build(settings, to, subject, body, attach=(), cc="", reply_to="", html=False):
    if not re.fullmatch(r"[^@\s,]+@[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,63}", to):
        raise ValueError("Adresse destinataire invalide")
    if not subject.strip() or len(subject) > 250 or any(ord(c) < 32 for c in subject):
        raise ValueError("Objet absent, trop long ou avec caractère de contrôle")
    if not body.strip() or len(body) > MAX_BODY:
        raise ValueError("Corps vide ou trop long")
    message = EmailMessage()
    sender = settings["address"]
    message["From"] = f"{settings['from_name']} <{sender}>" if settings.get("from_name") else sender
    message["To"] = to
    if cc:
        message["Cc"] = cc
    if reply_to:
        message["Reply-To"] = reply_to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1])
    message.set_content(body, subtype="html" if html else "plain")
    for path in attach:
        source = Path(path)
        if not source.is_file():
            raise ValueError(f"Pièce jointe introuvable : {path}")
        if source.stat().st_size > 15_000_000:
            raise ValueError(f"Pièce jointe trop lourde : {path}")
        message.add_attachment(
            source.read_bytes(),
            maintype="application",
            subtype="octet-stream",
            filename=source.name,
        )
    return message


def send(
    to,
    subject,
    body,
    name="",
    attach=(),
    cc="",
    reply_to="",
    html=False,
    identifier="",
    smtp_factory=None,
):
    """Envoi explicite. `identifier` stable = refus de réenvoyer le même message deux fois."""
    duplicate = already_sent(identifier)
    if duplicate:
        raise RuntimeError(
            f"Déjà envoyé le {duplicate['at']} sous l'identifiant « {identifier} » ; changer d'identifiant pour un nouvel envoi."
        )
    name, settings = account(name)
    settings = settings | {"name": name}
    message = build(settings, to, subject, body, attach, cc, reply_to, html)
    server = (smtp_factory or smtp_open)(settings)
    try:
        server.send_message(message)
    finally:
        try:
            server.quit()
        except Exception:
            pass
    entry = {
        "id": identifier,
        "at": now(),
        "account": name,
        "to": to,
        "cc": cc,
        "subject": subject,
        "message_id": message["Message-ID"],
        "attachments": [Path(p).name for p in attach],
    }
    journal(entry)
    # [OXIO] « accepté » veut dire accepté par le serveur d'envoi, pas lu ni même reçu.
    return entry | {
        "status": "accepted",
        "meaning": "Accepté par le serveur SMTP ; réception finale non confirmée",
    }


def add(name, address, password_value, online=True, **overrides):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
        raise ValueError("Nom de compte invalide (lettres, chiffres, tirets)")
    if not parseaddr(address)[1] or "@" not in address:
        raise ValueError("Adresse invalide")
    settings = discover(address, online) | {"address": address, "username": "", "from_name": ""}
    settings |= {k: v for k, v in overrides.items() if v not in (None, "")}
    note = settings.pop("note", "")
    settings.pop("source", None)
    data = config()
    data["accounts"][name] = settings
    data["default"] = data.get("default") or name
    write_config(data)
    if password_value:
        store_password(name, password_value)
    return {"account": name, "settings": settings, "note": note}


def main():
    parser = argparse.ArgumentParser(
        description="Boîte mail : connexion, lecture (sans marquer lu) et envoi explicite."
    )
    parser.add_argument("--account", default="", help="Nom du compte (défaut : compte par défaut)")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("discover", help="Afficher les réglages devinés pour une adresse")
    p.add_argument("address")
    p = sub.add_parser(
        "add", help="Enregistrer un compte ; le mot de passe est lu sur l'entrée standard"
    )
    p.add_argument("name")
    p.add_argument("address")
    for flag in ("imap-host", "smtp-host", "username", "from-name"):
        p.add_argument("--" + flag, default="")
    p.add_argument("--imap-port", type=int)
    p.add_argument("--smtp-port", type=int)
    p.add_argument("--imap-security", choices=["ssl", "starttls"])
    p.add_argument("--smtp-security", choices=["ssl", "starttls"])
    p.add_argument("--offline", action="store_true", help="Ne pas interroger la base Thunderbird")
    sub.add_parser("list", help="Comptes enregistrés")
    p = sub.add_parser("remove", help="Oublier un compte et son mot de passe")
    p.add_argument("name")
    p = sub.add_parser("default", help="Choisir le compte par défaut")
    p.add_argument("name")
    sub.add_parser("test", help="Vérifier les connexions IMAP et SMTP")
    sub.add_parser("folders", help="Lister les dossiers IMAP")
    p = sub.add_parser("inbox", help="Derniers messages")
    p.add_argument("--folder", default="INBOX")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--unread", action="store_true")
    p = sub.add_parser("read", help="Lire un message par UID")
    p.add_argument("uid")
    p.add_argument("--folder", default="INBOX")
    p.add_argument("--attachments-to", default="")
    p = sub.add_parser("send", help="Envoyer un message (action explicite)")
    p.add_argument("--to", required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--body", default="")
    p.add_argument("--body-file", default="")
    p.add_argument("--attach", action="append", default=[])
    p.add_argument("--cc", default="")
    p.add_argument("--reply-to", default="")
    p.add_argument("--html", action="store_true")
    p.add_argument("--id", default="", help="Identifiant stable : empêche un double envoi")
    sub.add_parser("sent", help="Journal des envois")
    args = parser.parse_args()
    try:
        if args.command == "discover":
            result = discover(args.address)
        elif args.command == "add":
            secret = (
                sys.stdin.read().strip()
                if not sys.stdin.isatty()
                else __import__("getpass").getpass("Mot de passe (application) : ")
            )
            result = add(
                args.name,
                args.address,
                secret,
                online=not args.offline,
                imap_host=args.imap_host,
                smtp_host=args.smtp_host,
                username=args.username,
                from_name=args.from_name,
                imap_port=args.imap_port,
                smtp_port=args.smtp_port,
                imap_security=args.imap_security,
                smtp_security=args.smtp_security,
            )
        elif args.command == "list":
            data = config()
            result = {"default": data.get("default", ""), "accounts": data["accounts"]}
        elif args.command == "remove":
            data = config()
            if args.name not in data["accounts"]:
                raise RuntimeError("Compte inconnu")
            del data["accounts"][args.name]
            if data.get("default") == args.name:
                data["default"] = next(iter(data["accounts"]), "")
            write_config(data)
            forget_password(args.name)
            result = {"removed": args.name}
        elif args.command == "default":
            data = config()
            if args.name not in data["accounts"]:
                raise RuntimeError("Compte inconnu")
            data["default"] = args.name
            write_config(data)
            result = {"default": args.name}
        elif args.command == "test":
            result = test(args.account)
        elif args.command == "folders":
            result = folders(args.account)
        elif args.command == "inbox":
            result = inbox(args.account, args.folder, args.limit, args.unread)
        elif args.command == "read":
            result = read(args.uid, args.account, args.folder, args.attachments_to or None)
        elif args.command == "send":
            body = Path(args.body_file).read_text() if args.body_file else args.body
            result = send(
                args.to,
                args.subject,
                body,
                args.account,
                args.attach,
                args.cc,
                args.reply_to,
                args.html,
                args.id,
            )
        else:
            result = (
                [json.loads(line) for line in JOURNAL.read_text().splitlines()]
                if JOURNAL.exists()
                else []
            )
        print(json.dumps(result, ensure_ascii=False, indent=1))
        # [OXIO] `test` sort en erreur si une des deux connexions échoue, pour être utilisable en script.
        if args.command == "test" and (result["imap"] != "ok" or result["smtp"] != "ok"):
            sys.exit(1)
    except Exception as error:
        print(f"{type(error).__name__} : {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
