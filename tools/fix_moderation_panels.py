#!/usr/bin/env python3
"""Fix moderation views that drop CV2 panels on timeout/edit."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD_DIR = ROOT / "cogs" / "moderation"

TIMEOUT_BLOCK = re.compile(
    r"async def on_timeout\(self\):\n"
    r"(?:.*\n)*?"
    r"        if self\.message:\n"
    r"            try:\n"
    r"                await self\.message\.edit\(view=self\)\n"
    r"            except Exception:\n"
    r"                pass\n",
    re.MULTILINE,
)

TIMEOUT_SIMPLE = re.compile(
    r"        if self\.message:\n"
    r"            try:\n"
    r"                await self\.message\.edit\(view=self\)\n"
    r"            except Exception:\n"
    r"                pass\n",
    re.MULTILINE,
)

STANDALONE_EDIT = re.compile(
    r"        await self\.message\.edit\(view=self\)\n",
    re.MULTILINE,
)


def patch_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    if "sync_panel_message" not in text:
        text = text.replace(
            "from utils.cv2_compat import embed_to_view, embeds_to_view",
            "from utils.cv2_compat import embed_to_view, embeds_to_view, sync_panel_message",
        )

    text = TIMEOUT_SIMPLE.sub(
        "        await sync_panel_message(self)\n",
        text,
    )
    text = STANDALONE_EDIT.sub(
        "        await sync_panel_message(self)\n",
        text,
    )

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = 0
    for path in sorted(MOD_DIR.glob("*.py")):
        if patch_file(path):
            print(f"patched {path.relative_to(ROOT)}")
            changed += 1
    print(f"Done. {changed} file(s) updated.")


if __name__ == "__main__":
    main()