"""Rebrand Axon/Olympus identifiers to REM across the codebase."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"__pycache__", ".git", "games", "terminals"}
TEXT_EXTENSIONS = {".py", ".md", ".sh", ".yml", ".json", ".txt"}

REPLACEMENTS = [
    ("from core.axon import axon", "from core.rem import Rem"),
    ("from core import axon", "from core import Rem"),
    ("from core import Cog, axon, Context", "from core import Cog, Rem, Context"),
    ("Cog, axon, Context", "Cog, Rem, Context"),
    ("import axon, Cog", "import Rem, Cog"),
    ("axon, Cog", "Rem, Cog"),
    (": axon)", ": Rem)"),
    (": axon:", ": Rem:"),
    ("(bot: axon)", "(bot: Rem)"),
    ("(client: axon)", "(client: Rem)"),
    ("client = axon()", "client = Rem()"),
    ("bot = axon()", "bot = Rem()"),
    ("async def setup(bot: axon)", "async def setup(bot: Rem)"),
    ("from .axon.", "from .rem."),
    ("cogs/axon", "cogs/rem"),
    ("core.axon", "core.rem"),
    ("class axon(", "class Rem("),

    ("_axon_neutral_policy", "_rem_neutral_policy"),
    ("Axon X", "REM"),
    ("Olympus", "REM"),
    ("olympus", "rem"),
    ("modified version of REM. Original project lineage includes REM and REM bot components", "REM ALL IN ONE BOT"),
]


def rebrand_file(path: Path) -> bool:
    if path.name == "rebrand_to_rem.py":
        return False
    if "words.txt" in str(path):
        return False

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False

    original = text
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)

    if text == original:
        return False

    path.write_text(text, encoding="utf-8")
    print(f"rebranded: {path.relative_to(ROOT)}")
    return True


def main() -> None:
    count = 0
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in TEXT_EXTENSIONS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if rebrand_file(path):
            count += 1
    print(f"done — rebranded {count} files")


if __name__ == "__main__":
    main()