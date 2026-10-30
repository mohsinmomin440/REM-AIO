from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from cogs.antinuke._helpers import (
    AuditRateLimiter,
    fetch_recent_audit_entry,
    is_antinuke_enabled,
    is_guild_blacklisted,
    should_skip_antinuke_actor,
)

log = logging.getLogger(__name__)


class AntiKick(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._audit = AuditRateLimiter(max_requests=6)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        guild = member.guild
        if await is_guild_blacklisted(guild.id):
            return
        if not await is_antinuke_enabled(guild.id):
            return
        if not self._audit.can_fetch(guild.id, "kick"):
            return

        entry = await fetch_recent_audit_entry(
            guild,
            discord.AuditLogAction.kick,
            target_id=member.id,
        )
        if not entry or not entry.user:
            return

        executor = entry.user
        if await should_skip_antinuke_actor(guild, executor.id, self.bot.user.id, "kick"):
            return

        await self._ban_executor(guild, executor)
        await asyncio.sleep(2)

    async def _ban_executor(self, guild: discord.Guild, executor: discord.User, retries: int = 3) -> None:
        while retries > 0:
            try:
                await guild.ban(executor, reason="Antinuke | Unauthorized kick")
                return
            except discord.Forbidden:
                return
            except discord.HTTPException as exc:
                if exc.status == 429:
                    retry_after = exc.response.headers.get("Retry-After") if exc.response else None
                    if retry_after:
                        await asyncio.sleep(float(retry_after))
                        retries -= 1
                        continue
                log.warning("Antinuke kick ban failed for guild %s: %s", guild.id, exc)
                return
            except discord.errors.RateLimited as exc:
                await asyncio.sleep(exc.retry_after)
                retries -= 1
            except Exception:
                log.exception("Antinuke kick executor failed for guild %s", guild.id)
                return