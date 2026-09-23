from dataclasses import dataclass


@dataclass
class AgentResult:
    answer: str
    model: str
    usage: dict | None = None

    def __iter__(self):
        return iter((self.answer, self.model))


class AgentExecutionError(RuntimeError):
    def __init__(self, message, usage=None):
        super().__init__(message)
        self.usage = usage
