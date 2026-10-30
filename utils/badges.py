from __future__ import annotations

from utils.database import connect

BADGE_COLUMNS = frozenset({
    "owner",
    "staff",
    "partner",
    "sponsor",
    "friend",
    "early",
    "vip",
    "bug",
})

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS badges (
    user_id INTEGER PRIMARY KEY,
    owner INTEGER DEFAULT 0,
    staff INTEGER DEFAULT 0,
    partner INTEGER DEFAULT 0,
    sponsor INTEGER DEFAULT 0,
    friend INTEGER DEFAULT 0,
    early INTEGER DEFAULT 0,
    vip INTEGER DEFAULT 0,
    bug INTEGER DEFAULT 0
)
"""


async def ensure_badges_table() -> None:
    async with connect("badges.db") as db:
        await db.execute(_CREATE_SQL)
        await db.commit()


def _validate_badge(badge: str) -> str:
    key = badge.lower()
    if key not in BADGE_COLUMNS:
        raise ValueError(f"Invalid badge column: {badge}")
    return key


async def add_badge(user_id: int, badge: str) -> bool:
    column = _validate_badge(badge)
    async with connect("badges.db") as db:
        async with db.execute(
            f"SELECT {column} FROM badges WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            await db.execute(
                f"INSERT INTO badges (user_id, {column}) VALUES (?, 1)",
                (user_id,),
            )
        elif row[0] == 0:
            await db.execute(
                f"UPDATE badges SET {column} = 1 WHERE user_id = ?",
                (user_id,),
            )
        else:
            return False

        await db.commit()
        return True


async def remove_badge(user_id: int, badge: str) -> bool:
    column = _validate_badge(badge)
    async with connect("badges.db") as db:
        async with db.execute(
            f"SELECT {column} FROM badges WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if not row or row[0] != 1:
            return False

        await db.execute(
            f"UPDATE badges SET {column} = 0 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
        return True


async def get_user_badges(user_id: int) -> dict[str, int]:
    async with connect("badges.db") as db:
        async with db.execute(
            "SELECT owner, staff, partner, sponsor, friend, early, vip, bug FROM badges WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()

    keys = ("owner", "staff", "partner", "sponsor", "friend", "early", "vip", "bug")
    if not row:
        return {key: 0 for key in keys}
    return dict(zip(keys, row))