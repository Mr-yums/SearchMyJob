"""Build a clean source distribution from an explicit list; never package state."""

import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "dist"
OUTPUT.mkdir(exist_ok=True)
files = {ROOT / ".github/workflows/quality.yml"}
for name in (
    "README.md",
    "Dockerfile",
    "compose.yaml",
    "requirements.lock.txt",
    "pyproject.toml",
    "requirements-dev.txt",
    ".prettierrc.json",
    ".prettierignore",
    ".dockerignore",
    ".gitignore",
    ".env.example",
):
    files.add(ROOT / name)
for folder, patterns in {
    "backend": ["*.py"],
    "tests": ["*.py", "*.mjs"],
    "docs": ["*.md", "*.png"],
    "scripts": ["*.py", "*.mjs"],
    "mcp": ["*.mjs", "package.json", "package-lock.json"],
    "ui": ["package.json", "package-lock.json", "vite.config.js", "index.html"],
}.items():
    for pattern in patterns:
        files.update(
            (ROOT / folder).rglob(pattern)
            if folder not in ("mcp", "ui")
            else (ROOT / folder).glob(pattern)
        )
for folder in ("ui/src", "ui/public"):
    files.update(p for p in (ROOT / folder).rglob("*") if p.is_file())
files = {p for p in files if not p.is_relative_to(ROOT / "tests/manual")}
for p in files:
    if p.is_symlink() or p.suffix in (".sqlite", ".sqlite3", ".db", ".env"):
        raise SystemExit("Fichier interdit dans la distribution : " + str(p.relative_to(ROOT)))
archive = OUTPUT / "searchmyjob-docker-0.3.8.zip"
temporary = archive.with_suffix(".zip.tmp")
with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(files):
        z.write(p, "searchmyjob-docker/" + str(p.relative_to(ROOT)))
with zipfile.ZipFile(temporary) as z:
    if z.testzip():
        raise SystemExit("Archive endommagée")
temporary.replace(archive)
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
(OUTPUT / "SHA256SUMS").write_text(checksum + "  " + archive.name + "\n")
print(
    f"{archive.name} : {len(files)} fichiers, {archive.stat().st_size} octets · SHA256 {checksum}"
)
