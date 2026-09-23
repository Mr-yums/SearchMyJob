"""Private, transactional credentials store belonging only to this installation."""

import json
import os
import sqlite3
from pathlib import Path


def _connect():
    root = Path(os.environ.get("SEARCHMYJOB_STATE", "/state"))
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = root / "credentials.sqlite3"
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    path.chmod(0o600)
    db = sqlite3.connect(path, timeout=10)
    db.execute("CREATE TABLE IF NOT EXISTS secrets (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    return db


def read():
    db = _connect()
    try:
        return {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM secrets")}
    finally:
        db.close()


def save(values):
    db = _connect()
    try:
        with db:
            for key, value in values.items():
                if value is None:
                    db.execute("DELETE FROM secrets WHERE key=?", (key,))
                elif value != "":
                    db.execute(
                        "INSERT OR REPLACE INTO secrets VALUES (?,?)", (key, json.dumps(value))
                    )
    finally:
        db.close()
