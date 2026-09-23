import json
import sqlite3

import pytest
from searchmyjob.infrastructure.repositories.usage import UsageLedger
from searchmyjob.integrations.ai.usage import codex_usage


def event(input=100, output=20, cache=80):
    return json.dumps(
        {
            "type": "turn.completed",
            "usage": {"input_tokens": input, "output_tokens": output, "cached_input_tokens": cache},
        }
    )


def test_usage_sums_turns_without_double_counting_cache():
    usage = codex_usage("\n".join(["noise", "{}", event(), event(200, 30, 150)]))
    assert usage == dict(input_tokens=300, output_tokens=50, cached_input_tokens=230)


@pytest.mark.parametrize(
    "output",
    [
        "",
        "{}",
        "[]",
        event(-1),
        event(cache=101),
        event(input=True),
        '{"type":"turn.completed","usage":{}}',
    ],
)
def test_missing_or_invalid_usage_is_unknown(output):
    assert codex_usage(output) is None


def test_ledger_persists_and_reports_partial_coverage(tmp_path):
    path = tmp_path / "usage.sqlite3"
    db = sqlite3.connect(path, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE config(key TEXT PRIMARY KEY,value TEXT)")
    ledger = UsageLedger(db)
    assert ledger.summary()["total_tokens"] is None
    ledger.record("openai", codex_usage(event()))
    ledger.record("kimi", None)
    ledger.record("openai", codex_usage(event(20, 5, 0)), completed=False)
    before = ledger.summary()
    db.close()
    db = sqlite3.connect(path, isolation_level=None)
    db.row_factory = sqlite3.Row
    assert UsageLedger(db).summary() == before
    assert before["total_tokens"] == 145
    assert before["partial"] and before["missing_calls"] == 1
    assert before["providers"]["openai"]["incomplete_calls"] == 1
    assert before["providers"]["kimi"]["total_tokens"] is None
    db.close()
