from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERN = re.compile(
    r"        if message\.author\.bot:\n"
    r"            return\n\n"
    r"        guild = message\.guild\n"
    r"        user = message\.author\n"
    r"        channel = message\.channel\n"
    r"        guild_id = guild\.id\n\n"
    r"        gate = await automod_gate\(message, '([^']+)'\)\n"
    r"        if gate is None:\n"
    r"            return\n",
)


def main() -> None:
    for path in (ROOT / "cogs" / "automod").glob("*.py"):
        if path.name == "antispam.py":
            continue
        text = path.read_text(encoding="utf-8")
        match = PATTERN.search(text)
        if not match:
            continue
        event = match.group(1)
        replacement = (
            "        if message.author.bot:\n"
            "            return\n\n"
            f"        gate = await automod_gate(message, '{event}')\n"
            "        if gate is None:\n"
            "            return\n\n"
            "        guild = message.guild\n"
            "        user = message.author\n"
            "        channel = message.channel\n"
        )
        path.write_text(PATTERN.sub(replacement, text), encoding="utf-8")
        print(f"reordered {path.name}")


if __name__ == "__main__":
    main()