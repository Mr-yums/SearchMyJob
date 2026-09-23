"""Open and migrate the workspace without rebuilding existing tables."""

import sqlite3


def open_workspace(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(path / "workspace.sqlite3", isolation_level=None, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript("""PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
    CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY,value TEXT);
    CREATE TABLE IF NOT EXISTS offers(id TEXT PRIMARY KEY,data TEXT,status TEXT DEFAULT 'new',found REAL,updated REAL);
    CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,role TEXT,provider TEXT,text TEXT,created REAL);
    CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,kind TEXT,provider TEXT,status TEXT,created REAL,finished REAL,output TEXT DEFAULT '',error TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,offer_id TEXT,kind TEXT,text TEXT,approved INTEGER,created REAL);
    CREATE TABLE IF NOT EXISTS revisions(id TEXT,document_id TEXT,text TEXT,created REAL);
    """)
    # [Sol] Add progress without rebuilding the workspace or losing previous runs.
    if "phase" not in {r[1] for r in db.execute("PRAGMA table_info(runs)")}:
        db.execute("ALTER TABLE runs ADD COLUMN phase TEXT NOT NULL DEFAULT ''")
    return db
