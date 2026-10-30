import discord
from discord.ext import commands
import asyncio

from utils.database import open_connection

DB_PATH = "fastgreet.db"


class FastGreet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = None

    async def cog_load(self) -> None:
        self.db = await open_connection(DB_PATH)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS greet_channels (
                guild_id INTEGER,
                channel_id INTEGER,
                PRIMARY KEY (guild_id, channel_id)
            )
        """)
        await self.db.commit()

    async def cog_unload(self) -> None:
        if self.db is not None:
            await self.db.close()

    @commands.command(name="fastgreet_add")
    @commands.has_permissions(administrator=True)
    async def add_greet_channel(self, ctx, channel: discord.TextChannel):
        await self.db.execute(
            "INSERT OR IGNORE INTO greet_channels (guild_id, channel_id) VALUES (?, ?)",
            (ctx.guild.id, channel.id),
        )
        await self.db.commit()
        await ctx.send(f"✅ {channel.mention} added as a greet channel.")

    @commands.command(name="fastgreet_remove")
    @commands.has_permissions(administrator=True)
    async def remove_greet_channel(self, ctx, channel: discord.TextChannel):
        await self.db.execute(
            "DELETE FROM greet_channels WHERE guild_id = ? AND channel_id = ?",
            (ctx.guild.id, channel.id),
        )
        await self.db.commit()
        await ctx.send(f"❌ {channel.mention} removed from greet channels.")

    @commands.command(name="fastgreet_list")
    async def list_greet_channels(self, ctx):
        async with self.db.execute(
            "SELECT channel_id FROM greet_channels WHERE guild_id = ?",
            (ctx.guild.id,),
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await ctx.send("⚠️ No greet channels configured.")
            return

        channels = [f"<#{cid[0]}>" for cid in rows]
        await ctx.send("📋 Greet Channels: " + ", ".join(channels))

    @commands.Cog.listener()
    async def on_member_join(self, member):
        async with self.db.execute(
            "SELECT channel_id FROM greet_channels WHERE guild_id = ?",
            (member.guild.id,),
        ) as cursor:
            channels = [row[0] for row in await cursor.fetchall()]

        for channel_id in channels:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    msg = await channel.send(f"{member.mention} Welcome!")
                    await asyncio.sleep(2)
                    await msg.delete()
                except discord.Forbidden:
                    continue


async def setup(bot):
    await bot.add_cog(FastGreet(bot))