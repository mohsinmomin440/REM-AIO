from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from cogs.antinuke._helpers import (
    AuditRateLimiter,
    fetch_recent_audit_entry,
    is_antinuke_enabled,
    should_skip_antinuke_actor,
)

log = logging.getLogger(__name__)


class AntiBan(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._audit = AuditRateLimiter()

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member) -> None:
        if not await is_antinuke_enabled(guild.id):
            return
        if not self._audit.can_fetch(guild.id, "member_ban"):
            return

        entry = await fetch_recent_audit_entry(
            guild,
            discord.AuditLogAction.ban,
            target_id=user.id,
        )
        if not entry or not entry.user:
            return

        executor = entry.user
        if await should_skip_antinuke_actor(guild, executor.id, self.bot.user.id, "ban"):
            return

        await self._ban_executor(guild, executor, user)

    async def _ban_executor(
        self,
        guild: discord.Guild,
        executor: discord.User,
        user: discord.User | discord.Member,
        retries: int = 3,
    ) -> None:
        while retries > 0:
            try:
                await guild.ban(executor, reason="Antinuke | Unauthorized ban")
                await guild.unban(user, reason="Antinuke | Reverting unauthorized ban")
                return
            except discord.Forbidden:
                return
            except discord.HTTPException as exc:
                if exc.status == 429 and exc.response:
                    retry_after = exc.response.headers.get("Retry-After")
                    if retry_after:
                        await asyncio.sleep(float(retry_after))
                        retries -= 1
                        continue
                log.warning("Antinuke ban response failed for guild %s: %s", guild.id, exc)
                return
            except Exception:
                log.exception("Antinuke ban executor failed for guild %s", guild.id)
                return

        retries = 3
        while retries > 0:
            try:
                await guild.unban(user, reason="Antinuke | Reverting unauthorized ban")
                return
            except discord.Forbidden:
                return
            except discord.HTTPException as exc:
                if exc.status == 429 and exc.response:
                    retry_after = exc.response.headers.get("Retry-After")
                    if retry_after:
                        await asyncio.sleep(float(retry_after))
                        retries -= 1
                        continue
                return
            except Exception:
                log.exception("Antinuke unban fallback failed for guild %s", guild.id)
                return