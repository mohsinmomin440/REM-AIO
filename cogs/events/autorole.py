from utils.database import connect
import discord
import aiohttp
import asyncio
import logging
from discord.ext import commands
from core import Rem, Cog

DATABASE_PATH = 'autorole.db'
logger = logging.getLogger(__name__)

class Autorole2(Cog):
    def __init__(self, bot: Rem):
        self.bot = bot
        self.headers = {"Authorization": f"Bot {self.bot.http.token}"}

    async def get_autorole(self, guild_id: int):
        async with connect(DATABASE_PATH) as db:
            async with db.execute("SELECT bots, humans FROM autorole WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    bots, humans = row
                    bots = [int(role_id) for role_id in bots.replace('[', '').replace(']', '').replace(' ', '').split(',') if role_id]
                    humans = [int(role_id) for role_id in humans.replace('[', '').replace(']', '').split(',') if role_id]
                    return {"bots": bots, "humans": humans}
                else:
                    return {"bots": [], "humans": []}

    @commands.Cog.listener()
    async def on_member_join(self, member):
        data = await self.get_autorole(member.guild.id)
        bot_roles = data["bots"]
        human_roles = data["humans"]

        if member.bot:
            roles_to_add = bot_roles
        else:
            roles_to_add = human_roles

        for role_id in roles_to_add:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="REM ALL IN ONE BOT Autoroles")
                except discord.Forbidden:
                    logger.warning("Bot lacks permissions to add autorole in guild %s", member.guild.id)
                except discord.HTTPException as exc:
                    if exc.status == 429:
                        retry_after = exc.response.headers.get('Retry-After') if exc.response else None
                        if retry_after:
                            await asyncio.sleep(float(retry_after))
                            await member.add_roles(role, reason="REM ALL IN ONE BOT  Autoroles")
                except discord.errors.RateLimited as exc:
                    logger.warning("Autorole rate limited in guild %s; retrying in %ss", member.guild.id, exc.retry_after)
                    await asyncio.sleep(exc.retry_after)
                    await member.add_roles(role, reason="REM ALL IN ONE BOT  Autoroles")
                except Exception as e:
                    logger.error(f"Unexpected error in Autorole: {e}")

