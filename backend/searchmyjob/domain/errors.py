"""Expected workspace failure. HTTP translation belongs to the API adapter."""


class WorkspaceError(Exception):
    def __init__(self, status_code: int, detail: str = "Introuvable"):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
