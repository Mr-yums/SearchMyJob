import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.utils import parseaddr


class MailError(RuntimeError):
    """Erreur attendue, affichable telle quelle à l'utilisateur."""


@dataclass(frozen=True)
class Envelope:
    to: str
    subject: str
    body: str
    name: str = ""
    reply_to: str = ""
    identifier: str = ""

    def validate(self):
        address = parseaddr(self.to)[1]
        if not address or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address):
            raise MailError("Destinataire invalide : indique une adresse e-mail complète.")
        if not self.subject.strip():
            raise MailError("L'objet est vide.")
        if not self.body.strip():
            raise MailError("Le message est vide.")
        return self


@dataclass(frozen=True)
class Receipt:
    message_id: str
    sender: str
    to: str
    at: float


class MailTransport(ABC):
    """Contrat minimal : connaître l'état de la boîte, s'y connecter, envoyer, oublier."""

    @abstractmethod
    def status(self) -> dict: ...

    @abstractmethod
    def begin_connection(self, client_json: dict) -> str:
        """Démarre l'autorisation et renvoie l'URL à ouvrir dans le navigateur."""

    @abstractmethod
    def connection_state(self) -> dict: ...

    @abstractmethod
    def send(self, envelope: Envelope) -> Receipt: ...

    @abstractmethod
    def disconnect(self) -> None: ...


def split_subject(text):
    """L'agent rend « Objet : … » en première ligne puis le corps ; sinon objet par défaut."""
    lines = text.strip().splitlines()
    if lines and re.match(r"^\s*(objet|sujet|subject)\s*:", lines[0], re.I):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).lstrip("\n")
        return subject, body
    return "", text.strip()


from typing import Protocol


class MailSender(Protocol):
    def send(self, envelope: Envelope) -> Receipt: ...
