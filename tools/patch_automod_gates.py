#!/usr/bin/env python3
"""Inject cached automod_gate into automod listener hot paths."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "antispam.py": "Anti spam",
    "anticaps.py": "Anti caps",
    "antilink.py": "Anti link",
    "anti_invites.py": "Anti invites",
    "anti_emoji_spam.py": "Anti emoji spam",
    "anti_mass_mention.py": "Anti mass mention",
}

OLD_BLOCK = """        if not await self.is_automod_enabled(guild_id) or not await self.is_anti"""

IMPORT_LINE = "from utils.automod_helpers import automod_gate, log_automod_action\n"


def patch_file(path: Path, event_name: str) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    if "automod_gate" in text:
        return False

    if IMPORT_LINE.strip() not in text:
        text = text.replace(
            "from utils.cv2_compat import embed_to_view, embeds_to_view\n",
            "from utils.cv2_compat import embed_to_view, embeds_to_view\n"
            + IMPORT_LINE,
        )

    marker = f"        if not await self.is_automod_enabled(guild_id) or not await self.is_anti"
    if marker not in text:
        return False

    start = text.index(marker)
    end = text.index("        if user == guild.owner", start)
    replacement = (
        f"        gate = await automod_gate(message, '{event_name}')\n"
        f"        if gate is None:\n"
        f"            return\n\n"
    )
    text = text[:start] + replacement + text[end:]

    text = text.replace(
        "punishment = await self.get_punishment(guild_id)",
        "punishment = gate.punishment",
    )
    text = text.replace(
        "await self.log_action(guild, user, channel, action_taken, reason)",
        (
            "await log_automod_action(\n"
            "                    guild, user, channel, action_taken, reason,\n"
            f"                    title='Automod Log: {event_name}',\n"
            "                    log_channel_id=gate.log_channel_id,\n"
            "                )"
        ),
    )

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = 0
    for filename, event in FILES.items():
        path = ROOT / "cogs" / "automod" / filename
        if patch_file(path, event):
            print(f"patched {path.relative_to(ROOT)}")
            changed += 1
    print(f"Done. {changed} file(s) updated.")


if __name__ == "__main__":
    main()