from utils import emojis

import logging

import discord
from discord.ext import commands
import asyncio

log = logging.getLogger(__name__)


class React(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        for owner in self.bot.owner_ids:
            if f"<@{owner}>" in message.content:
                try:
                    if owner in self.bot.owner_ids:  # Special reactions for all owners
                        await message.add_reaction(f"{emojis.REM_OWNER}")
                    else:
                        await message.add_reaction(f"{emojis.REM_OWNER}")
                except discord.errors.RateLimited as e:
                    await asyncio.sleep(e.retry_after)
                    await message.add_reaction(f"{emojis.REM_OWNER}")
                except Exception:
                    log.exception("Auto react owner mention failed")
