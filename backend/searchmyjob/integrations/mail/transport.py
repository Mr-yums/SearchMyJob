import time

from searchmyjob.domain.mail import MailError, MailTransport, Receipt
from searchmyjob.integrations.mail import gmail as gmail_send


class GmailTransport(MailTransport):
    """API Gmail, scope gmail.send, refresh token permanent via `gmail_send`."""

    def __init__(self):
        self._flow = None

    def status(self):
        return gmail_send.status()

    def begin_connection(self, client_json):
        client_id, client_secret = gmail_send.parse_client_data(client_json)
        self._flow = gmail_send.OAuthFlow(client_id, client_secret)
        return self._flow.start()

    def connection_state(self):
        flow = self._flow
        if flow is None:
            return {"state": "idle", "error": "", "auth_url": ""}
        return {
            "state": flow.state,
            "error": flow.error,
            "auth_url": flow.auth_url if flow.state == "pending" else "",
        }

    def send(self, envelope):
        try:
            result = gmail_send.send(
                envelope.to,
                envelope.subject,
                envelope.body,
                reply_to=envelope.reply_to,
                name=envelope.name,
                identifier=envelope.identifier,
            )
        except (RuntimeError, ValueError) as exc:
            raise MailError(str(exc)) from None
        return Receipt(result.get("id", ""), result.get("from", ""), envelope.to, time.time())

    def disconnect(self):
        gmail_send.logout()
        self._flow = None
