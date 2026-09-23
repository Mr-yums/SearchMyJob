"""[OXIO] Connexion Gmail par OAuth pour l'envoi seul.

Objectif : la manip la moins pénible possible pour l'utilisateur final.
Il dépose le fichier JSON téléchargé chez Google tel quel, autorise une fois dans son
navigateur, et l'app obtient un refresh token permanent. Ensuite l'agent prépare des
brouillons, l'utilisateur valide, et le serveur envoie depuis la vraie boîte de l'utilisateur.

Permission demandée : gmail.send uniquement (envoyer). Pas de lecture de la boîte, donc
aucun audit de sécurité Google (scope « sensible », pas « restreint »). Le refresh token
n'est permanent que si le projet Google est publié « En production » : sinon Google
l'expire à 7 jours et `send` le signalera clairement.

Autonome : utilisable en ligne de commande ou importé par le serveur (`OAuthFlow` en deux
temps, car un service ne peut pas ouvrir de navigateur). Ne touche ni aux agents ni à la
base. Aucun agent ne reçoit d'outil d'envoi ; le serveur seul envoie, après validation.
"""

import argparse
import base64
import json
import os
import secrets
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

try:  # Le coffre (Secret Service) sert de dépôt aux secrets ; repli fichier si indisponible.
    from searchmyjob.infrastructure.vault import read as vault_read
    from searchmyjob.infrastructure.vault import save as vault_save
except Exception:  # pragma: no cover - le repli n'est utilisé qu'en dehors de la session graphique.
    vault_read = vault_save = None

STATE = Path(
    os.environ.get("SEARCHMYJOB_STATE", str(Path.home() / ".local/state/searchmyjob-community"))
)
TOKEN_CACHE = STATE / "gmail-token.json"  # access token court-vécu (0600), régénérable.
FALLBACK = STATE / "gmail-secret.json"  # repli hors coffre (0600), refresh token compris.
JOURNAL = STATE / "gmail-sent.jsonl"
SCOPE = "https://www.googleapis.com/auth/gmail.send"
AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SEND_URI = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
USERINFO_URI = "https://openidconnect.googleapis.com/v1/userinfo"
TIMEOUT = 30
MAX_ATTACH = 20 * 1024 * 1024
PORTS = (
    int(os.environ.get("SEARCHMYJOB_OAUTH_PORT", "8975")),
)  # loopback fixe d'abord, éphémère en dernier recours.


def now():
    return time.time()


# ---------------------------------------------------------------- dépôt des secrets
def _vault_ok():
    return vault_read is not None and vault_save is not None


def load_secret():
    """Identifiants OAuth et refresh token : coffre en priorité, sinon fichier 0600."""
    if _vault_ok():
        data = vault_read()
        keep = {k[6:]: v for k, v in data.items() if k.startswith("gmail_")}
        if keep:
            return keep
    if FALLBACK.exists():
        return json.loads(FALLBACK.read_text())
    return {}


def save_secret(values):
    values = {k: v for k, v in values.items() if v is not None}
    if _vault_ok():
        vault_save({"gmail_" + k: v for k, v in values.items()})
        return
    data = load_secret()
    data.update(values)
    FALLBACK.parent.mkdir(parents=True, exist_ok=True)
    FALLBACK.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    FALLBACK.chmod(0o600)


def parse_client_data(raw):
    """Accepte le contenu du fichier client_secret_*.json de Google (type installed ou web)."""
    if not isinstance(raw, dict):
        raise ValueError("Fichier Google invalide : un objet JSON est attendu.")
    node = raw.get("installed") or raw.get("web") or raw
    client_id = node.get("client_id") if isinstance(node, dict) else None
    client_secret = node.get("client_secret") if isinstance(node, dict) else None
    if not client_id or not client_secret:
        raise ValueError(
            "Fichier Google invalide : client_id ou client_secret absent. "
            "Télécharge le JSON d'un identifiant OAuth de type « Application de bureau »."
        )
    if "installed" not in raw and "web" in raw:
        raise ValueError(
            "Cet identifiant est de type « Application Web » : Google refuse alors la "
            "redirection locale. Crée un identifiant de type « Application de bureau »."
        )
    return client_id, client_secret


def parse_client(path):
    return parse_client_data(json.loads(Path(path).expanduser().read_text()))


# ---------------------------------------------------------------- HTTP OAuth + Gmail
def _post_token(params):
    body = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(TOKEN_URI, data=body, method="POST")
    try:
        with urllib.request.urlopen(
            req, timeout=TIMEOUT, context=ssl.create_default_context()
        ) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            reason = (
                json.loads(detail).get("error_description")
                or json.loads(detail).get("error")
                or detail
            )
        except Exception:
            reason = detail
        if "invalid_grant" in detail:
            raise RuntimeError(
                "Autorisation Google expirée ou révoquée. Si ton projet Google est "
                "encore en mode « Test », publie-le « En production » pour que la "
                "connexion soit permanente, puis reconnecte-toi."
            ) from None
        raise RuntimeError(f"Google a refusé la demande de jeton : {reason}") from None


class _LoopbackServer(HTTPServer):
    """Serveur local d'un seul retour Google ; le flux propriétaire est attaché à l'instance."""

    allow_reuse_address = True
    flow = None


class _Catch(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        flow = self.server.flow
        ok = params.get("state") == flow.state_token and "code" in params
        flow.callback = params if ok else {"error": params.get("error", "state invalide")}
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        message = (
            "Connexion réussie. Tu peux fermer cet onglet et revenir dans SearchMyJob."
            if ok
            else "Échec de la connexion. Reviens dans SearchMyJob et réessaie."
        )
        self.wfile.write(
            f"<!doctype html><meta charset=utf-8><title>SearchMyJob</title>"
            f'<body style="font-family:system-ui;padding:3rem;color:#2a2338">'
            f"<h2>{message}</h2></body>".encode()
        )

    def log_message(self, *a):
        pass


class OAuthFlow:
    """Flux « application de bureau » en deux temps.

    `start()` réserve un port local, construit l'URL d'autorisation et attend le retour de
    Google dans un thread ; `state` vaut pending, connected ou failed. Le serveur web renvoie
    l'URL au navigateur de l'utilisateur ; la CLI l'ouvre elle-même.
    """

    def __init__(self, client_id, client_secret, timeout=300):
        self.client_id, self.client_secret, self.timeout = client_id, client_secret, timeout
        self.state, self.error, self.address, self.auth_url = "idle", "", "", ""
        self.state_token = secrets.token_urlsafe(24)
        self.callback = {}
        self._thread = None

    def start(self):
        server = None
        for port in PORTS:
            try:
                server = _LoopbackServer(
                    (os.environ.get("SEARCHMYJOB_OAUTH_BIND", "127.0.0.1"), port), _Catch
                )
                break
            except OSError:
                continue
        if server is None:
            raise RuntimeError("Aucun port local disponible pour recevoir la réponse de Google.")
        server.flow = self
        server.timeout = self.timeout
        redirect_uri = f"http://127.0.0.1:{server.server_address[1]}/"
        self.auth_url = (
            AUTH_URI
            + "?"
            + urllib.parse.urlencode(
                {
                    "client_id": self.client_id,
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "scope": f"{SCOPE} openid email",
                    "access_type": "offline",
                    "prompt": "consent",
                    "state": self.state_token,
                }
            )
        )
        self.state = "pending"
        self._thread = threading.Thread(target=self._run, args=(server, redirect_uri), daemon=True)
        self._thread.start()
        return self.auth_url

    def _run(self, server, redirect_uri):
        try:
            server.handle_request()  # une seule requête, ou expiration après `timeout`.
        finally:
            server.server_close()
        try:
            params = self.callback
            if "code" not in params:
                raise RuntimeError(
                    "Autorisation non reçue (annulée ou expirée). " + params.get("error", "")
                )
            token = _post_token(
                {
                    "code": params["code"],
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                }
            )
            refresh = token.get("refresh_token")
            if not refresh:
                raise RuntimeError(
                    "Google n'a pas renvoyé de refresh token. Révoque l'accès de l'app "
                    "dans ton compte Google puis reconnecte-toi pour forcer un nouveau consentement."
                )
            self.address = _whoami(token.get("access_token", ""))
            save_secret(
                {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh,
                    "address": self.address,
                }
            )
            _cache_access(token)
            self.state = "connected"
        except Exception as exc:
            self.error, self.state = str(exc), "failed"

    def wait(self, timeout=None):
        if self._thread:
            self._thread.join(timeout=timeout or self.timeout + 5)
        if self.state == "connected":
            return {"connected": True, "address": self.address}
        raise RuntimeError(self.error or "Autorisation non reçue.")


def connect(client_json, open_browser=True, on_url=None):
    """Version bloquante pour la ligne de commande : ouvre le navigateur et attend."""
    client_id, client_secret = parse_client(client_json)
    flow = OAuthFlow(client_id, client_secret)
    url = flow.start()
    if on_url:
        on_url(url)
    if open_browser:
        webbrowser.open(url)
    return flow.wait()


def _whoami(access_token):
    if not access_token:
        return ""
    req = urllib.request.Request(USERINFO_URI, headers={"Authorization": "Bearer " + access_token})
    try:
        with urllib.request.urlopen(
            req, timeout=TIMEOUT, context=ssl.create_default_context()
        ) as r:
            return json.loads(r.read()).get("email", "")
    except Exception:
        return ""


def _cache_access(token):
    STATE.mkdir(parents=True, exist_ok=True)
    TOKEN_CACHE.write_text(
        json.dumps(
            {
                "access_token": token.get("access_token", ""),
                "expiry": now() + int(token.get("expires_in", 3600)) - 60,
            }
        )
    )
    TOKEN_CACHE.chmod(0o600)


def access_token():
    """Renvoie un access token valide, rafraîchi si besoin depuis le refresh token permanent."""
    if TOKEN_CACHE.exists():
        try:
            cache = json.loads(TOKEN_CACHE.read_text())
            if cache.get("access_token") and cache.get("expiry", 0) > now():
                return cache["access_token"]
        except Exception:
            pass
    secret = load_secret()
    if not secret.get("refresh_token"):
        raise RuntimeError("Aucune boîte Gmail connectée. Lance la connexion une première fois.")
    token = _post_token(
        {
            "client_id": secret["client_id"],
            "client_secret": secret["client_secret"],
            "refresh_token": secret["refresh_token"],
            "grant_type": "refresh_token",
        }
    )
    _cache_access(token)
    return token["access_token"]


def status():
    secret = load_secret()
    return {"connected": bool(secret.get("refresh_token")), "address": secret.get("address", "")}


def logout():
    """Oublie la boîte : retire les clés gmail_* du coffre (vault.save ne sait pas supprimer)."""
    if _vault_ok():
        data = {k: v for k, v in vault_read().items() if not k.startswith("gmail_")}
        _vault_rewrite(data)
    for path in (TOKEN_CACHE, FALLBACK):
        path.unlink(missing_ok=True)
    return {"connected": False}


def _vault_rewrite(data):
    """Réécrit le coffre sans les clés gmail_* (vault.save ne sait pas supprimer)."""
    from searchmyjob.infrastructure import vault

    vault.save({key: None for key in vault.read() if key.startswith("gmail_")})


# ---------------------------------------------------------------- envoi
def _build(to, subject, body, sender="", reply_to="", cc="", name="", attachments=()):
    if not parseaddr(to)[1] or "@" not in parseaddr(to)[1]:
        raise ValueError("Destinataire invalide.")
    if not subject.strip():
        raise ValueError("Objet vide.")
    msg = EmailMessage()
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg["From"] = f"{name} <{sender}>" if name and sender else (sender or "")
    if reply_to:
        msg["Reply-To"] = reply_to
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.set_content(body)
    total = 0
    for path in attachments:
        data = Path(path).read_bytes()
        total += len(data)
        if total > MAX_ATTACH:
            raise ValueError("Pièces jointes trop volumineuses (max 20 Mo au total).")
        msg.add_attachment(
            data, maintype="application", subtype="octet-stream", filename=Path(path).name
        )
    return msg


def send(to, subject, body, reply_to="", cc="", name="", attachments=(), identifier=""):
    """Envoie via l'API Gmail depuis la boîte connectée. `identifier` empêche un doublon."""
    secret = load_secret()
    sender = secret.get("address", "")
    if identifier and _already_sent(identifier):
        raise RuntimeError("Message déjà envoyé (identifiant réutilisé).")
    msg = _build(
        to,
        subject,
        body,
        sender=sender,
        reply_to=reply_to,
        cc=cc,
        name=name,
        attachments=attachments,
    )
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload = json.dumps({"raw": raw}).encode()
    req = urllib.request.Request(
        SEND_URI,
        data=payload,
        method="POST",
        headers={"Authorization": "Bearer " + access_token(), "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(
            req, timeout=TIMEOUT, context=ssl.create_default_context()
        ) as r:
            result = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"Envoi refusé par Gmail (HTTP {e.code}) : {e.read().decode(errors='replace')[:300]}"
        ) from None
    _record(identifier, to, subject, sender)
    return {"sent": True, "id": result.get("id", ""), "from": sender, "to": to}


def _already_sent(identifier):
    if not JOURNAL.exists():
        return False
    return any(
        json.loads(line).get("id") == identifier
        for line in JOURNAL.read_text().splitlines()
        if line.strip()
    )


def _record(identifier, to, subject, sender):
    STATE.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a") as handle:
        handle.write(
            json.dumps(
                {"id": identifier, "to": to, "subject": subject, "from": sender, "at": now()},
                ensure_ascii=False,
            )
            + "\n"
        )
    JOURNAL.chmod(0o600)


# ---------------------------------------------------------------- CLI
def main(argv=None):
    parser = argparse.ArgumentParser(description="Connexion Gmail (envoi seul) par OAuth.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("connect", help="Autoriser une boîte à partir du JSON Google téléchargé")
    c.add_argument("client_json", help="chemin du fichier client_secret_*.json")
    c.add_argument(
        "--no-browser", action="store_true", help="afficher l’URL au lieu d’ouvrir le navigateur"
    )
    sub.add_parser("status", help="Boîte connectée ?")
    sub.add_parser("logout", help="Oublier la boîte connectée")
    s = sub.add_parser("send", help="Envoyer un message")
    s.add_argument("--to", required=True)
    s.add_argument("--subject", required=True)
    s.add_argument("--body-file", required=True)
    s.add_argument("--reply-to", default="")
    s.add_argument("--cc", default="")
    s.add_argument("--name", default="")
    s.add_argument("--attach", action="append", default=[])
    s.add_argument("--id", default="")
    args = parser.parse_args(argv)
    if args.cmd == "connect":
        result = connect(
            args.client_json,
            open_browser=not args.no_browser,
            on_url=lambda u: print("Ouvre ce lien pour autoriser :\n" + u, file=sys.stderr),
        )
    elif args.cmd == "status":
        result = status()
    elif args.cmd == "logout":
        result = logout()
    else:
        body = Path(args.body_file).read_text()
        result = send(
            args.to,
            args.subject,
            body,
            reply_to=args.reply_to,
            cc=args.cc,
            name=args.name,
            attachments=args.attach,
            identifier=args.id,
        )
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
