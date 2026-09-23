"""Persistence operations for runs."""


class RunsRepository:
    def __init__(self, db):
        self.db = db

    def find(self, run_id):
        return [dict(row) for row in self.db.execute("SELECT * FROM runs WHERE id=?", (run_id,))]

    def recent(self):
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT id,kind,provider,status,phase,created,finished,error FROM runs ORDER BY created DESC LIMIT 20"
            )
        ]

    def status(self, run_id):
        return [
            dict(row) for row in self.db.execute("SELECT status FROM runs WHERE id=?", (run_id,))
        ]

    def add(self, run_id, kind, provider, status, created, conversation_id):
        return self.db.execute(
            "INSERT INTO runs(id,kind,provider,status,created,conversation_id) VALUES (?,?,?,?,?,?)",
            (
                run_id,
                kind,
                provider,
                status,
                created,
                conversation_id,
            ),
        )

    def set_phase(self, phase, run_id):
        return self.db.execute(
            "UPDATE runs SET phase=? WHERE id=?",
            (
                phase,
                run_id,
            ),
        )

    def complete(self, output, finished, run_id):
        return self.db.execute(
            "UPDATE runs SET status='completed',output=?,finished=? WHERE id=?",
            (
                output,
                finished,
                run_id,
            ),
        )

    def cancel(self, finished, run_id):
        return self.db.execute(
            "UPDATE runs SET status='cancelled',error='Tâche arrêtée.',finished=? WHERE id=?",
            (
                finished,
                run_id,
            ),
        )

    def fail(self, error, finished, run_id):
        return self.db.execute(
            "UPDATE runs SET status='failed',error=?,finished=? WHERE id=?",
            (
                error,
                finished,
                run_id,
            ),
        )

    def heartbeat_count(self, since):
        return self.db.execute(
            "SELECT count(*) FROM runs WHERE kind='heartbeat' AND created>=?", (since,)
        ).fetchone()[0]
