"""[Sol] Persistent, fail-closed Bright Data budget shared with the MCP HTTP guard.
[OXIO · Opus 5 · 16/09/2026] Plafond paramétrable et remise à zéro ; migration du schéma 50 en dur."""

import os
import sqlite3
from pathlib import Path

DEFAULT_LIMIT = 200
MAX_LIMIT = 5000


class BrightError(Exception):
    pass


def budget_path():
    return (
        Path(
            os.environ.get(
                "SEARCHMYJOB_STATE", str(Path.home() / ".local/state/searchmyjob-community")
            )
        )
        / "bright-budget.sqlite3"
    )


def default_limit():
    try:
        value = int(os.environ.get("SEARCHMYJOB_BRIGHT_LIMIT", DEFAULT_LIMIT))
    except ValueError:
        return DEFAULT_LIMIT
    return value if 1 <= value <= MAX_LIMIT else DEFAULT_LIMIT


SCHEMA = """CREATE TABLE IF NOT EXISTS budget (
  id INTEGER PRIMARY KEY CHECK(id=1),
  used INTEGER NOT NULL CHECK(used>=0),
  max_calls INTEGER NOT NULL CHECK(max_calls BETWEEN 1 AND 5000))"""


def initialize():
    path = budget_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS calls (id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP, operation TEXT NOT NULL)"
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(budget)")}
        if columns and "max_calls" not in columns:
            # [OXIO] L'ancien schéma porte CHECK(used BETWEEN 0 AND 50) : SQLite impose de recréer la table.
            db.execute("BEGIN IMMEDIATE")
            db.execute(SCHEMA.replace("IF NOT EXISTS budget", "budget_migrated"))
            db.execute(
                "INSERT INTO budget_migrated(id,used,max_calls) SELECT id,used,? FROM budget",
                (default_limit(),),
            )
            db.execute("DROP TABLE budget")
            db.execute("ALTER TABLE budget_migrated RENAME TO budget")
            db.execute("COMMIT")
        else:
            db.execute(SCHEMA)
            db.execute("INSERT OR IGNORE INTO budget VALUES (1,0,?)", (default_limit(),))
    path.chmod(0o600)


def status():
    try:
        with sqlite3.connect(f"file:{budget_path()}?mode=ro", uri=True) as db:
            used, limit = db.execute("SELECT used,max_calls FROM budget WHERE id=1").fetchone()
        if (
            not isinstance(used, int)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_LIMIT
            or not 0 <= used
        ):
            raise ValueError()
        return dict(used=used, limit=limit, remaining=max(0, limit - used), blocked=used >= limit)
    except Exception:
        return dict(
            used=None,
            limit=default_limit(),
            remaining=0,
            blocked=True,
            error="Compteur indisponible : appels bloqués",
        )


def set_limit(value):
    """Relever ou abaisser le plafond local. N'efface pas le compteur."""
    if not isinstance(value, int) or not 1 <= value <= MAX_LIMIT:
        raise BrightError(f"Plafond hors bornes (1 à {MAX_LIMIT})")
    initialize()
    with sqlite3.connect(budget_path()) as db:
        db.execute("UPDATE budget SET max_calls=? WHERE id=1", (value,))
    return status()


def reset():
    """Remettre le compteur local à zéro. Sans effet sur le quota mensuel réel du compte."""
    initialize()
    with sqlite3.connect(budget_path()) as db:
        db.execute("UPDATE budget SET used=0 WHERE id=1")
        db.execute("DELETE FROM calls")
    return status()


def reserve(operation):
    """Atomic reservation shared with the Node MCP guard; errors consume the call."""
    try:
        with sqlite3.connect(f"file:{budget_path()}?mode=rw", uri=True, timeout=10) as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute("UPDATE budget SET used=used+1 WHERE id=1 AND used<max_calls").rowcount
                != 1
            ):
                raise BrightError("Stop-loss Bright Data : plafond local atteint")
            db.execute("INSERT INTO calls(operation) VALUES (?)", (operation,))
    except sqlite3.Error:
        raise BrightError("Stop-loss Bright Data : compteur indisponible") from None


def pending(fingerprint):
    try:
        with sqlite3.connect(f"file:{budget_path()}?mode=rw", uri=True) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS pending_jobs (fingerprint TEXT PRIMARY KEY, snapshot TEXT NOT NULL)"
            )
            row = db.execute(
                "SELECT snapshot FROM pending_jobs WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        raise BrightError("Stop-loss Bright Data : compteur indisponible") from None


def save_pending(fingerprint, snapshot):
    with sqlite3.connect(f"file:{budget_path()}?mode=rw", uri=True) as db:
        if snapshot:
            db.execute("INSERT OR REPLACE INTO pending_jobs VALUES (?,?)", (fingerprint, snapshot))
        else:
            db.execute("DELETE FROM pending_jobs WHERE fingerprint=?", (fingerprint,))
