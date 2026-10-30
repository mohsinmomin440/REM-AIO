from __future__ import annotations

import discord

from utils.automod_cache import AutomodGate, automod_gate, get_automod_state
from utils.cv2_compat import embed_to_view

__all__ = ("automod_gate", "log_automod_action")


async def log_automod_action(
    guild: discord.Guild,
    user: discord.Member,
    channel: discord.abc.GuildChannel,
    action: str,
    reason: str,
    *,
    title: str,
    log_channel_id: int | None,
) -> None:
    if not log_channel_id:
        return

    log_channel = guild.get_channel(log_channel_id)
    if log_channel is None:
        return

    embed = discord.Embed(title=title, color=0xFF0000)
    embed.add_field(name="User", value=user.mention, inline=False)
    embed.add_field(name="Action", value=action, inline=False)
    embed.add_field(name="Channel", value=channel.mention, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"User ID: {user.id}")
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.timestamp = discord.utils.utcnow()
    await log_channel.send(view=embed_to_view(embed))