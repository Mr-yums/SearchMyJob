import json
import time

from searchmyjob.domain.mail import Envelope, MailError, MailTransport


class MailService:
    """Point d'entrée unique du serveur ; le statut du coffre est lu une fois puis mis en cache."""

    MAX_CLIENT_JSON = 64 * 1024

    def __init__(self, transport: MailTransport):
        self.transport = transport
        self._status = None

    def status(self):
        if self._status is None:
            try:
                self._status = self.transport.status()
            except Exception:
                self._status = {"connected": False, "address": ""}
        flow = self.transport.connection_state()
        if flow["state"] == "connected" and not self._status.get("connected"):
            self._status = None
            return self.status()
        return {
            **self._status,
            "pending": flow["state"] == "pending",
            "auth_url": flow["auth_url"],
            "error": flow["error"] if flow["state"] == "failed" else "",
        }

    def connect(self, raw: bytes):
        if len(raw) > self.MAX_CLIENT_JSON:
            raise MailError("Fichier trop volumineux pour un identifiant Google.")
        try:
            data = json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError, ValueError:
            raise MailError("Ce fichier n’est pas un JSON Google valide.") from None
        try:
            url = self.transport.begin_connection(data)
        except ValueError as exc:
            raise MailError(str(exc)) from None
        self._status = None
        return url

    def disconnect(self):
        self.transport.disconnect()
        self._status = None

    def send(self, envelope: Envelope):
        if not self.status().get("connected"):
            raise MailError("Aucune boîte connectée : connecte ta boîte Gmail dans Courrier.")
        return self.transport.send(envelope.validate())

    def send_test(self, name=""):
        address = self.status().get("address", "")
        body = (
            "Ceci est un test d’envoi depuis SearchMyJob.\n\nSi tu lis ce message, ta boîte est bien "
            "connectée : l’agent prépare, tu valides, et ça part de ta vraie adresse."
        )
        return self.send(
            Envelope(
                address,
                "Test SearchMyJob — connexion Gmail",
                body,
                name=name,
                identifier=f"test-{int(time.time())}",
            )
        )
