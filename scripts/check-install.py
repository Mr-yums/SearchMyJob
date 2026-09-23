"""Check a fresh, isolated Docker installation without contacting providers."""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

base = sys.argv[1].rstrip("/")
version = json.loads((Path(__file__).resolve().parents[1] / "ui/package.json").read_text())[
    "version"
]


def get(path):
    with urllib.request.urlopen(base + path, timeout=5) as response:
        return json.load(response)


for attempt in range(60):
    try:
        health = get("/api/health")
        break
    except OSError, ValueError:
        time.sleep(1)
else:
    raise SystemExit("Application did not start")

assert health == {"status": "ok", "service": "SearchMyJob", "version": version}
state = get("/api/state")
for field in ("messages", "offers", "documents", "emails", "imports", "runs"):
    assert not state[field], field
assert not state["profile"]
assert not state["settings"]["enabled"]
assert state["bright_budget"]["used"] == 0
assert not get("/api/activation")["completed"]
with urllib.request.urlopen(base, timeout=5) as response:
    assert response.status == 200
    assert b"/assets/" in response.read()
request = urllib.request.Request(base + "/api/health", headers={"Host": "attacker.invalid"})
try:
    urllib.request.urlopen(request, timeout=5)
except urllib.error.HTTPError as exc:
    assert exc.code == 403
else:
    raise AssertionError("Untrusted host was accepted")
print("PASS: fresh installation, expected version, empty data, monitoring off, host boundary")
