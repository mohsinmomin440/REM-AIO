"""Second-pass migration for variable-path aiosqlite.connect calls."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"tools", "games", "__pycache__", "utils", "db"}

IMPORT = "from utils.database import connect, open_connection\n"
ASYNC_WITH_RE = re.compile(r"async with aiosqlite\.connect\(([^)]+)\) as (\w+):")
AWAIT_RE = re.compile(r"(\s*)(\w+) = await aiosqlite\.connect\(([^)]+)\)")


def ensure_import(text: str) -> str:
    if "from utils.database import" in text:
        return text
    if text.startswith("from __future__ import"):
        lines = text.splitlines(keepends=True)
        idx = 1
        while idx < len(lines) and (
            lines[idx].strip() == ""
            or lines[idx].startswith("import ")
            or lines[idx].startswith("from ")
        ):
            idx += 1
        lines.insert(idx, IMPORT)
        return "".join(lines)
    return IMPORT + text


def migrate(path: Path) -> bool:
    if any(part in SKIP for part in path.parts):
        return False
    original = path.read_text(encoding="utf-8")
    if "aiosqlite.connect" not in original:
        return False

    updated = ASYNC_WITH_RE.sub(r"async with connect(\1) as \2:", original)
    updated = AWAIT_RE.sub(r"\1\2 = await open_connection(\3)", updated)

    if "aiosqlite" not in updated.replace("import aiosqlite", ""):
        updated = re.sub(r"^import aiosqlite\n", "", updated, flags=re.M)

    if updated == original:
        return False

    updated = ensure_import(updated)
    path.write_text(updated, encoding="utf-8")
    print(f"migrated: {path.relative_to(ROOT)}")
    return True


def main() -> None:
    count = 0
    for path in ROOT.rglob("*.py"):
        if migrate(path):
            count += 1
    print(f"done — migrated {count} files")


if __name__ == "__main__":
    main()