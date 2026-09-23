import time

from searchmyjob.domain.mail import MailTransport, Receipt


class FakeTransport(MailTransport):
    """Transport en mémoire : connexion simulée, envois enregistrés, pannes pilotables."""

    def __init__(self, connected=False, address="moi@example.com"):
        self.connected, self.address = connected, address
        self.sent, self.flow, self.fail_with = (
            [],
            {"state": "idle", "error": "", "auth_url": ""},
            "",
        )

    def status(self):
        return {"connected": self.connected, "address": self.address if self.connected else ""}

    def begin_connection(self, client_json):
        node = client_json.get("installed") or {}
        if not node.get("client_id"):
            raise ValueError("JSON Google invalide (fixture)")
        self.flow = {
            "state": "pending",
            "error": "",
            "auth_url": "https://accounts.google.test/auth?fixture=1",
        }
        return self.flow["auth_url"]

    def complete(self):
        self.connected, self.flow = True, {"state": "connected", "error": "", "auth_url": ""}

    def connection_state(self):
        return self.flow

    def send(self, envelope):
        if self.fail_with:
            from searchmyjob.domain.mail import MailError

            raise MailError(self.fail_with)
        self.sent.append(envelope)
        return Receipt("msg-" + str(len(self.sent)), self.address, envelope.to, time.time())

    def disconnect(self):
        self.connected, self.flow = False, {"state": "idle", "error": "", "auth_url": ""}
