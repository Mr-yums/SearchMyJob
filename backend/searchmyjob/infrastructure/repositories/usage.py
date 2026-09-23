import json
import time


class UsageLedger:
    def __init__(self, db):
        self.db = db
        db.execute("""CREATE TABLE IF NOT EXISTS agent_usage (
            id INTEGER PRIMARY KEY, provider TEXT NOT NULL, created REAL NOT NULL,
            input_tokens INTEGER, output_tokens INTEGER, cached_input_tokens INTEGER,
            completed INTEGER NOT NULL)""")
        db.execute(
            "INSERT OR IGNORE INTO config VALUES (?,?)", ("usage_since", json.dumps(time.time()))
        )

    def record(self, provider, usage, completed=True):
        self.db.execute(
            """INSERT INTO agent_usage
            (provider,created,input_tokens,output_tokens,cached_input_tokens,completed)
            VALUES (?,?,?,?,?,?)""",
            (
                provider,
                time.time(),
                (usage or {}).get("input_tokens"),
                (usage or {}).get("output_tokens"),
                (usage or {}).get("cached_input_tokens"),
                int(completed),
            ),
        )

    def summary(self):
        providers = {}
        for name in ("deepseek", "kimi", "claude", "openai"):
            row = self.db.execute(
                """SELECT count(*) calls, count(input_tokens) measured_calls,
                sum(input_tokens) input_tokens, sum(output_tokens) output_tokens,
                sum(cached_input_tokens) cached_input_tokens,
                coalesce(sum(completed=0),0) incomplete_calls
                FROM agent_usage WHERE provider=?""",
                (name,),
            ).fetchone()
            values = dict(row)
            values["total_tokens"] = (
                (values["input_tokens"] + values["output_tokens"])
                if values["measured_calls"]
                else None
            )
            providers[name] = values
        measured = sum(p["measured_calls"] for p in providers.values())
        calls = sum(p["calls"] for p in providers.values())
        incomplete = sum(p["incomplete_calls"] for p in providers.values())
        return dict(
            since=json.loads(
                self.db.execute("SELECT value FROM config WHERE key='usage_since'").fetchone()[0]
            ),
            total_tokens=sum(p["total_tokens"] or 0 for p in providers.values())
            if measured
            else None,
            calls=calls,
            measured_calls=measured,
            missing_calls=calls - measured,
            partial=calls > measured or incomplete > 0,
            providers=providers,
        )
