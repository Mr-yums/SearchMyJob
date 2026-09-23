"""Process configuration and paths, independent of the working directory."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE = Path(
    os.environ.get("SEARCHMYJOB_STATE", str(Path.home() / ".local/state/searchmyjob-community"))
)
PORT = int(os.environ.get("SEARCHMYJOB_PORT", "8935"))
FRONTEND_PORT = os.environ.get("SEARCHMYJOB_FRONTEND_PORT", "")
TZ = ZoneInfo("Europe/Paris")
