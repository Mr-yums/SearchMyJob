"""Workspace services consume this port; runtime owns the concrete wiring."""

from typing import Any, Protocol


class WorkspaceContext(Protocol):
    token: str
    task: Any

    def get(self, key: str) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    def start(self, kind, provider, fn, conversation_id=None) -> dict: ...
