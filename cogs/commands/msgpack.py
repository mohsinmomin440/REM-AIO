import discord
from discord.ext import commands
from datetime import datetime

from utils.database import open_connection

DB_PATH = "messages.db"


class Messagespack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = None

    async def cog_load(self) -> None:
        self.db = await open_connection(DB_PATH)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                guild_id INTEGER,
                user_id INTEGER,
                date TEXT,
                count INTEGER
            )
        """)
        await self.db.commit()

    async def cog_unload(self) -> None:
        if self.db is not None:
            await self.db.close()

    @commands.command(name="addmessages", aliases=["addmsg"])
    @commands.has_permissions(manage_messages=True)
    async def addmessages(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send("Amount must be greater than 0.")

        today = datetime.utcnow().strftime("%Y-%m-%d")
        async with self.db.execute(
            "SELECT count FROM messages WHERE guild_id = ? AND user_id = ? AND date = ?",
            (ctx.guild.id, member.id, today),
        ) as cursor:
            result = await cursor.fetchone()

        if result:
            await self.db.execute(
                "UPDATE messages SET count = count + ? WHERE guild_id = ? AND user_id = ? AND date = ?",
                (amount, ctx.guild.id, member.id, today),
            )
        else:
            await self.db.execute(
                "INSERT INTO messages (guild_id, user_id, date, count) VALUES (?, ?, ?, ?)",
                (ctx.guild.id, member.id, today, amount),
            )

        await self.db.commit()
        await ctx.send(f"Added {amount} messages to {member.mention} for today.")

    @commands.command(name="removemessages", aliases=["removemsg"])
    @commands.has_permissions(manage_messages=True)
    async def removemessages(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send("Amount must be greater than 0.")

        today = datetime.utcnow().strftime("%Y-%m-%d")
        async with self.db.execute(
            "SELECT count FROM messages WHERE guild_id = ? AND user_id = ? AND date = ?",
            (ctx.guild.id, member.id, today),
        ) as cursor:
            result = await cursor.fetchone()

        if result:
            new_count = max(0, result[0] - amount)
            await self.db.execute(
                "UPDATE messages SET count = ? WHERE guild_id = ? AND user_id = ? AND date = ?",
                (new_count, ctx.guild.id, member.id, today),
            )
            await self.db.commit()
            await ctx.send(f"Removed {amount} messages from {member.mention} for today.")
        else:
            await ctx.send(f"{member.mention} has no messages recorded for today.")

    @commands.command(name="clearmessage", aliases=["clearmsg"])
    @commands.has_permissions(manage_messages=True)
    async def clearmessage(self, ctx, member: discord.Member):
        await self.db.execute(
            "DELETE FROM messages WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id),
        )
        await self.db.commit()
        await ctx.send(f"All messages cleared for {member.mention}.")


async def setup(bot):
    await bot.add_cog(Messagespack(bot))