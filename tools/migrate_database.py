"""One-shot migration: replace direct aiosqlite.connect calls with utils.database.connect."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"__pycache__", ".git", "tools", "games"}
SKIP_FILES = {
    ROOT / "utils" / "database.py",
    ROOT / "db" / "_db.py",
}

IMPORT_LINE = "from utils.database import connect\n"
CONNECT_RE = re.compile(
    r"aiosqlite\.connect\(\s*(['\"])(?:db/)?([^'\"]+)\1\s*(?:,\s*[^)]+)?\)"
)


def uses_aiosqlite_otherwise(content: str) -> bool:
    stripped = CONNECT_RE.sub("", content)
    return "aiosqlite" in stripped


def migrate_file(path: Path) -> bool:
    if path in SKIP_FILES:
        return False

    original = path.read_text(encoding="utf-8")
    if "aiosqlite.connect" not in original:
        return False

    updated = CONNECT_RE.sub(lambda m: f"connect('{m.group(2)}')", original)

    if "from utils.database import connect" not in updated:
        if updated.startswith("from __future__ import"):
            lines = updated.splitlines(keepends=True)
            idx = 1
            while idx < len(lines) and (lines[idx].strip() == "" or lines[idx].startswith("import ") or lines[idx].startswith("from ")):
                idx += 1
            lines.insert(idx, IMPORT_LINE)
            updated = "".join(lines)
        else:
            updated = IMPORT_LINE + updated

    if not uses_aiosqlite_otherwise(updated):
        updated = re.sub(r"^import aiosqlite\n", "", updated, flags=re.M)
        updated = re.sub(r"^from aiosqlite import .+\n", "", updated, flags=re.M)

    if updated == original:
        return False

    path.write_text(updated, encoding="utf-8")
    print(f"migrated: {path.relative_to(ROOT)}")
    return True


def main() -> None:
    count = 0
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if migrate_file(path):
            count += 1
    print(f"done — migrated {count} files")


if __name__ == "__main__":
    main()