import discord
from discord.ext import commands
from datetime import datetime, timezone

from utils.components_v2 import info_panel, success_panel, warning_panel
from utils.cv2_compat import embed_to_view
from utils.database import connect

DB_FILE = "invite_tracker.db"


class InviteTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.guild_invites = {}

    async def cog_load(self) -> None:
        async with connect(DB_FILE) as db:
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS invites (
                guild_id TEXT,
                inviter_id TEXT,
                invite_code TEXT,
                uses INTEGER DEFAULT 0,
                PRIMARY KEY(guild_id, invite_code)
            );

            CREATE TABLE IF NOT EXISTS invite_stats (
                guild_id TEXT,
                user_id TEXT,
                invites INTEGER DEFAULT 0,
                fake INTEGER DEFAULT 0,
                leaves INTEGER DEFAULT 0,
                rejoins INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS invite_settings (
                guild_id TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 0
            );
            """)
            await db.commit()

        if self.bot.is_ready():
            await self._cache_guild_invites()

    async def _cache_guild_invites(self) -> None:
        for guild in self.bot.guilds:
            try:
                self.guild_invites[guild.id] = await guild.invites()
            except discord.Forbidden:
                self.guild_invites[guild.id] = []

    @commands.Cog.listener()
    async def on_ready(self):
        await self._cache_guild_invites()

    async def is_enabled(self, guild_id) -> bool:
        async with connect(DB_FILE) as db:
            async with db.execute(
                "SELECT enabled FROM invite_settings WHERE guild_id = ?",
                (str(guild_id),),
            ) as cursor:
                row = await cursor.fetchone()
        return bool(row[0]) if row else False

    async def set_enabled(self, guild_id, enabled: bool) -> None:
        async with connect(DB_FILE) as db:
            await db.execute(
                """
                INSERT INTO invite_settings (guild_id, enabled) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET enabled=excluded.enabled
                """,
                (str(guild_id), int(enabled)),
            )
            await db.commit()

    @commands.command(name="Invite enable")
    @commands.has_permissions(administrator=True)
    async def inviteenable(self, ctx):
        await self.set_enabled(ctx.guild.id, True)
        await ctx.reply(view=success_panel("Invite tracking **enabled** for this server.", title="Invite Tracker"))

    @commands.command(name="Invite disable")
    @commands.has_permissions(administrator=True)
    async def invitedisable(self, ctx):
        await self.set_enabled(ctx.guild.id, False)
        await ctx.reply(view=success_panel("Invite tracking **disabled** for this server.", title="Invite Tracker"))

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        try:
            self.guild_invites[guild.id] = await guild.invites()
        except discord.Forbidden:
            self.guild_invites[guild.id] = []

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        invites = self.guild_invites.get(invite.guild.id, [])
        invites.append(invite)
        self.guild_invites[invite.guild.id] = invites

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        invites = self.guild_invites.get(invite.guild.id, [])
        self.guild_invites[invite.guild.id] = [i for i in invites if i.code != invite.code]

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not await self.is_enabled(member.guild.id):
            return

        guild = member.guild
        before_invites = self.guild_invites.get(guild.id, [])
        try:
            after_invites = await guild.invites()
        except discord.Forbidden:
            return

        self.guild_invites[guild.id] = after_invites
        used_invite = None

        for before in before_invites:
            after = discord.utils.get(after_invites, code=before.code)
            if after and after.uses > before.uses:
                used_invite = after
                break

        if not used_invite or not used_invite.inviter:
            return

        inviter = used_invite.inviter
        acc_age = datetime.now(timezone.utc) - member.created_at

        async with connect(DB_FILE) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO invites (guild_id, inviter_id, invite_code, uses)
                VALUES (?, ?, ?, 0)
                """,
                (str(guild.id), str(inviter.id), used_invite.code),
            )
            await db.execute(
                "UPDATE invites SET uses = uses + 1 WHERE guild_id = ? AND invite_code = ?",
                (str(guild.id), used_invite.code),
            )
            await db.execute(
                "INSERT OR IGNORE INTO invite_stats (guild_id, user_id) VALUES (?, ?)",
                (str(guild.id), str(inviter.id)),
            )

            if acc_age.total_seconds() < 86400:
                await db.execute(
                    "UPDATE invite_stats SET fake = fake + 1 WHERE guild_id = ? AND user_id = ?",
                    (str(guild.id), str(inviter.id)),
                )
            else:
                await db.execute(
                    "UPDATE invite_stats SET invites = invites + 1 WHERE guild_id = ? AND user_id = ?",
                    (str(guild.id), str(inviter.id)),
                )
            await db.commit()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if not await self.is_enabled(member.guild.id):
            return
        async with connect(DB_FILE) as db:
            await db.execute(
                "UPDATE invite_stats SET leaves = leaves + 1 WHERE guild_id = ? AND user_id = ?",
                (str(member.guild.id), str(member.id)),
            )
            await db.commit()

    async def get_stats(self, guild_id, user_id):
        async with connect(DB_FILE) as db:
            async with db.execute(
                """
                SELECT invites, fake, leaves, rejoins FROM invite_stats
                WHERE guild_id = ? AND user_id = ?
                """,
                (str(guild_id), str(user_id)),
            ) as cursor:
                row = await cursor.fetchone()
        return row or (0, 0, 0, 0)

    @commands.command(name="invites")
    async def invites(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        if not await self.is_enabled(ctx.guild.id):
            return await ctx.reply(view=warning_panel("Invite tracking is disabled.", title="Invites"))

        invites, fake, leaves, rejoins = await self.get_stats(ctx.guild.id, member.id)
        await ctx.reply(
            view=info_panel(
                "",
                title=f"Invite Stats — {member.display_name}",
                fields=[
                    ("Total Invites", str(invites)),
                    ("Fake", str(fake)),
                    ("Leaves", str(leaves)),
                    ("Rejoins", str(rejoins)),
                ],
            )
        )

    @commands.command(name="inviteleaderboard")
    async def inviteleaderboard(self, ctx):
        async with connect(DB_FILE) as db:
            async with db.execute(
                """
                SELECT user_id, invites FROM invite_stats
                WHERE guild_id = ? ORDER BY invites DESC LIMIT 10
                """,
                (str(ctx.guild.id),),
            ) as cursor:
                rows = await cursor.fetchall()

        fields = []
        for index, (user_id, count) in enumerate(rows, start=1):
            user = ctx.guild.get_member(int(user_id))
            name = user.display_name if user else f"<@{user_id}>"
            fields.append((f"#{index} {name}", f"{count} invites"))

        if not fields:
            return await ctx.reply(view=info_panel("No invite data yet.", title="Invite Leaderboard"))

        await ctx.reply(view=info_panel("", title="Invite Leaderboard", fields=fields))

    @commands.command(name="resetinvites")
    @commands.has_permissions(administrator=True)
    async def resetinvites(self, ctx, member: discord.Member):
        async with connect(DB_FILE) as db:
            await db.execute(
                "DELETE FROM invite_stats WHERE guild_id = ? AND user_id = ?",
                (str(ctx.guild.id), str(member.id)),
            )
            await db.commit()
        await ctx.reply(view=success_panel(f"Reset invites for {member.mention}.", title="Invites"))

    @commands.command(name="addinvites")
    @commands.has_permissions(administrator=True)
    async def addinvites(self, ctx, member: discord.Member, amount: int):
        async with connect(DB_FILE) as db:
            await db.execute(
                "INSERT OR IGNORE INTO invite_stats (guild_id, user_id, invites) VALUES (?, ?, 0)",
                (str(ctx.guild.id), str(member.id)),
            )
            await db.execute(
                "UPDATE invite_stats SET invites = invites + ? WHERE guild_id = ? AND user_id = ?",
                (amount, str(ctx.guild.id), str(member.id)),
            )
            await db.commit()
        await ctx.reply(view=success_panel(f"Added {amount} invites to {member.mention}.", title="Invites"))

    @commands.command(name="removeinvites")
    @commands.has_permissions(administrator=True)
    async def removeinvites(self, ctx, member: discord.Member, amount: int):
        async with connect(DB_FILE) as db:
            await db.execute(
                "INSERT OR IGNORE INTO invite_stats (guild_id, user_id, invites) VALUES (?, ?, 0)",
                (str(ctx.guild.id), str(member.id)),
            )
            await db.execute(
                "UPDATE invite_stats SET invites = MAX(invites - ?, 0) WHERE guild_id = ? AND user_id = ?",
                (amount, str(ctx.guild.id), str(member.id)),
            )
            await db.commit()
        await ctx.reply(view=success_panel(f"Removed {amount} invites from {member.mention}.", title="Invites"))

    @commands.command(name="resetserverinvites")
    @commands.has_permissions(administrator=True)
    async def resetserverinvites(self, ctx):
        async with connect(DB_FILE) as db:
            await db.execute("DELETE FROM invite_stats WHERE guild_id = ?", (str(ctx.guild.id),))
            await db.execute("DELETE FROM invites WHERE guild_id = ?", (str(ctx.guild.id),))
            await db.commit()
        await ctx.reply(view=success_panel("Reset all invite stats for this server.", title="Invites"))