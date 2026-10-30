"""Remove unused aiosqlite imports after database migration."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"tools", "games", "__pycache__"}


def cleanup(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "import aiosqlite" not in text and "from aiosqlite" not in text:
        return False
    if re.search(r"\baiosqlite\b", re.sub(r"^import aiosqlite\n", "", text, flags=re.M)):
        return False
    new_text = re.sub(r"^import aiosqlite\n", "", text, flags=re.M)
    new_text = re.sub(r"^from aiosqlite import .+\n", "", new_text, flags=re.M)
    if new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    print(f"cleaned: {path.relative_to(ROOT)}")
    return True


def main() -> None:
    count = 0
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP for part in path.parts):
            continue
        if cleanup(path):
            count += 1
    print(f"done — cleaned {count} files")


if __name__ == "__main__":
    main()