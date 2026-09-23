"""Persistence operations for tool calls."""


class ToolCallsRepository:
    def __init__(self, db):
        self.db = db
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS agent_tool_calls(\n          id TEXT PRIMARY KEY,run_id TEXT,conversation_id TEXT,provider TEXT,tool TEXT,status TEXT,created REAL)"
        )

    def add(self, call_id, run_id, conversation_id, provider, tool, status, created):
        return self.db.execute(
            "INSERT INTO agent_tool_calls VALUES (?,?,?,?,?,?,?)",
            (
                call_id,
                run_id,
                conversation_id,
                provider,
                tool,
                status,
                created,
            ),
        )

    def set_status(self, status, call_id):
        return self.db.execute(
            "UPDATE agent_tool_calls SET status=? WHERE id=?",
            (
                status,
                call_id,
            ),
        )

    def completed(self, run_id):
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT tool FROM agent_tool_calls WHERE run_id=? AND status='completed'", (run_id,)
            )
        ]
