import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import re

from utils.components_v2 import info_panel, success_panel, warning_panel
from utils.cv2_compat import embed_to_view
from utils.database import open_connection

DB_FILE = "jail.db"

_SETTING_FIELDS = frozenset({"jail_role", "jail_channel", "mod_role", "log_channel"})


class Jail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = None

    async def cog_load(self) -> None:
        self.db = await open_connection(DB_FILE)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS jailed (
                guild_id TEXT,
                user_id TEXT,
                mod_id TEXT,
                reason TEXT,
                jailed_at TEXT,
                duration INTEGER,
                roles TEXT,
                PRIMARY KEY (guild_id, user_id)
            );
        """)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS jail_settings (
                guild_id TEXT PRIMARY KEY,
                jail_role TEXT,
                jail_channel TEXT,
                mod_role TEXT,
                log_channel TEXT
            );
        """)
        try:
            await self.db.execute("SELECT roles FROM jailed LIMIT 1;")
        except Exception:
            await self.db.execute("ALTER TABLE jailed ADD COLUMN roles TEXT;")
        await self.db.commit()

    async def cog_unload(self) -> None:
        self.jail_check_loop.cancel()
        if self.db is not None:
            await self.db.close()
            self.db = None

    async def get_setting(self, guild_id, field: str):
        if field not in _SETTING_FIELDS:
            raise ValueError(f"Invalid jail setting field: {field}")
        async with self.db.execute(
            f"SELECT {field} FROM jail_settings WHERE guild_id = ?",
            (str(guild_id),),
        ) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else None

    async def set_setting(self, guild_id, field: str, value):
        if field not in _SETTING_FIELDS:
            raise ValueError(f"Invalid jail setting field: {field}")
        await self.db.execute(
            f"""
            INSERT INTO jail_settings (guild_id, {field})
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET {field} = excluded.{field}
            """,
            (str(guild_id), str(value)),
        )
        await self.db.commit()

    def parse_duration(self, duration_str: str):
        pattern = re.compile(r"((?P<hours>\d+)h)?((?P<minutes>\d+)m)?")
        match = pattern.fullmatch(duration_str.lower())
        if not match:
            return None
        hours = int(match.group("hours") or 0)
        minutes = int(match.group("minutes") or 0)
        return (hours * 60 + minutes) * 60 if (hours or minutes) else None

    @tasks.loop(minutes=1)
    async def jail_check_loop(self):
        now = datetime.utcnow()
        async with self.db.execute(
            "SELECT guild_id, user_id, duration, jailed_at, roles FROM jailed"
        ) as cursor:
            rows = await cursor.fetchall()

        for guild_id, user_id, duration, jailed_at, roles in rows:
            if not duration:
                continue
            jailed_time = datetime.fromisoformat(jailed_at)
            if (now - jailed_time).total_seconds() >= duration:
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    member = guild.get_member(int(user_id))
                    if member:
                        await self.unjail_member(guild, member)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.jail_check_loop.is_running():
            self.jail_check_loop.start()

    async def unjail_member(self, guild, member):
        jail_role_id = await self.get_setting(guild.id, "jail_role")
        if jail_role_id:
            jail_role = guild.get_role(int(jail_role_id))
            if jail_role in member.roles:
                await member.remove_roles(jail_role, reason="Unjailed")

        async with self.db.execute(
            "SELECT roles FROM jailed WHERE guild_id = ? AND user_id = ?",
            (str(guild.id), str(member.id)),
        ) as cursor:
            row = await cursor.fetchone()

        if row and row[0]:
            role_ids = map(int, row[0].split(","))
            roles = [guild.get_role(rid) for rid in role_ids if guild.get_role(rid)]
            if roles:
                await member.add_roles(*roles, reason="Restored previous roles after jail")

        await self.db.execute(
            "DELETE FROM jailed WHERE guild_id = ? AND user_id = ?",
            (str(guild.id), str(member.id)),
        )
        await self.db.commit()

        try:
            await member.send(f"🔓 You have been unjailed in **{guild.name}**.")
        except Exception:
            pass

        log_channel_id = await self.get_setting(guild.id, "log_channel")
        if log_channel_id:
            log_channel = guild.get_channel(int(log_channel_id))
            if log_channel:
                embed = discord.Embed(title="🔓 Member Unjailed", color=discord.Color.green())
                embed.add_field(name="User", value=member.mention)
                embed.timestamp = datetime.utcnow()
                embed.set_footer(text=f"{guild.name}")
                await log_channel.send(view=embed_to_view(embed))

    @commands.command(name="jail")
    @commands.has_permissions(manage_roles=True)
    async def jail(self, ctx, member: discord.Member, duration: str = None, *, reason="No reason provided"):
        jail_role_id = await self.get_setting(ctx.guild.id, "jail_role")
        jail_channel_id = await self.get_setting(ctx.guild.id, "jail_channel")
        log_channel_id = await self.get_setting(ctx.guild.id, "log_channel")

        if not jail_role_id or not jail_channel_id:
            return await ctx.send(view=warning_panel("Jail system not fully configured.", title="Jail"))

        jail_role = ctx.guild.get_role(int(jail_role_id))
        if not jail_role:
            return await ctx.send(view=warning_panel("Jail role does not exist.", title="Jail"))

        duration_secs = self.parse_duration(duration) if duration else None
        jailed_at = datetime.utcnow().isoformat()
        roles_str = ",".join(str(r.id) for r in member.roles if r != ctx.guild.default_role)

        await self.db.execute(
            "DELETE FROM jailed WHERE guild_id = ? AND user_id = ?",
            (str(ctx.guild.id), str(member.id)),
        )
        await self.db.execute(
            """
            INSERT INTO jailed (guild_id, user_id, mod_id, reason, jailed_at, duration, roles)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (str(ctx.guild.id), str(member.id), str(ctx.author.id), reason, jailed_at, duration_secs, roles_str),
        )
        await self.db.commit()

        try:
            await member.edit(roles=[jail_role], reason="Jailed")
        except discord.Forbidden:
            return await ctx.send(view=warning_panel("I don't have permission to change roles.", title="Jail"))

        jail_channel = ctx.guild.get_channel(int(jail_channel_id))
        if jail_channel:
            await jail_channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )

        try:
            await member.send(
                f"🔒 You were jailed in **{ctx.guild.name}**.\n"
                f"📝 Reason: {reason}\n⏰ Duration: {duration or 'Permanent'}"
            )
        except Exception:
            pass

        await ctx.send(
            view=success_panel(
                f"{member.mention} has been jailed {'for ' + duration if duration else 'permanently'}.",
                title="Jail",
            )
        )

        if log_channel_id:
            log_channel = ctx.guild.get_channel(int(log_channel_id))
            if log_channel:
                embed = discord.Embed(title="🔒 Member Jailed", color=discord.Color.red())
                embed.add_field(name="User", value=member.mention, inline=False)
                embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Duration", value=duration or "Permanent", inline=False)
                embed.timestamp = datetime.utcnow()
                await log_channel.send(view=embed_to_view(embed))

    @commands.command(name="unjail")
    @commands.has_permissions(manage_roles=True)
    async def unjail(self, ctx, member: discord.Member):
        await self.unjail_member(ctx.guild, member)
        await ctx.send(view=success_panel(f"{member.mention} has been unjailed.", title="Unjail"))

    @commands.command(name="jailhistory")
    async def jailhistory(self, ctx, member: discord.Member):
        async with self.db.execute(
            """
            SELECT reason, jailed_at, duration, mod_id FROM jailed
            WHERE guild_id = ? AND user_id = ?
            """,
            (str(ctx.guild.id), str(member.id)),
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            reason, jailed_at, duration, mod_id = row
            mod = ctx.guild.get_member(int(mod_id))
            jailed_time = datetime.fromisoformat(jailed_at)
            await ctx.send(
                view=info_panel(
                    "",
                    title="Jail Record",
                    fields=[
                        ("User", member.mention),
                        ("Reason", reason),
                        ("Jailed At", jailed_time.strftime("%Y-%m-%d %H:%M:%S UTC")),
                        ("Duration", f"{duration // 60} minutes" if duration else "Permanent"),
                        ("Jailed By", mod.mention if mod else "Unknown"),
                    ],
                )
            )
        else:
            await ctx.send(view=warning_panel(f"No jail record found for {member.mention}.", title="Jail Record"))