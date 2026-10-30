from __future__ import annotations

import datetime
import os
import time

import discord
import psutil
import wavelink
from discord import Embed
from discord.ext import commands

from utils import emojis
from utils.Tools import blacklist_check, ignore_check
from utils.cv2_compat import embed_to_view


from utils.database import connect
class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
        self.total_songs_played = 0
        self._code_stats: tuple[int, int, int] | None = None

    async def cog_load(self) -> None:
        await self.setup_database()

    async def setup_database(self):
        os.makedirs("db", exist_ok=True)
        async with connect('stats.db') as db:
            await db.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)")
            await db.commit()
            async with db.execute("SELECT value FROM stats WHERE key = 'total_songs_played'") as cursor:
                row = await cursor.fetchone()
            self.total_songs_played = row[0] if row else 0
            if row is None:
                await db.execute("INSERT INTO stats (key, value) VALUES ('total_songs_played', 0)")
                await db.commit()

    async def update_total_songs_played(self):
        async with connect('stats.db') as db:
            await db.execute(
                "INSERT OR REPLACE INTO stats (key, value) VALUES ('total_songs_played', ?)",
                (self.total_songs_played,),
            )
            await db.commit()

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        self.total_songs_played += 1
        await self.update_total_songs_played()

    def count_code_stats(self, file_path: str) -> tuple[int, int]:
        total_lines = 0
        total_words = 0
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                for line in file:
                    stripped = line.strip()
                    if stripped:
                        total_lines += 1
                        total_words += len(stripped.split())
        except (UnicodeDecodeError, OSError):
            pass
        return total_lines, total_words

    def gather_file_stats(self, directory: str) -> tuple[int, int, int]:
        total_files = 0
        total_lines = 0
        total_words = 0
        skipped_dirs = {
            ".git",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".venv",
            "venv",
            "env",
            "data",
            "db",
            "node_modules",
        }

        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in skipped_dirs]
            if any(part in skipped_dirs for part in os.path.normpath(root).split(os.sep)):
                continue
            for file in files:
                if not file.endswith(".py") or ".bak" in file:
                    continue
                total_files += 1
                file_lines, file_words = self.count_code_stats(os.path.join(root, file))
                total_lines += file_lines
                total_words += file_words

        return total_files, total_lines, total_words

    @commands.hybrid_command(
        name="stats",
        aliases=["botinfo", "botstats", "bi", "statistics"],
        help="Shows the bot's information.",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def stats(self, ctx: commands.Context):
        processing_message = await ctx.send(f"{emojis.LOADING} Loading REM ALL IN ONE BOT information...")

        guild_count = len(self.bot.guilds)
        user_count = sum(g.member_count for g in self.bot.guilds if g.member_count is not None)
        cached_members = list(self.bot.get_all_members())
        bot_count = sum(1 for member in cached_members if member.bot)
        human_count = max(user_count - bot_count, 0)
        total_users = human_count + bot_count

        all_channels = list(self.bot.get_all_channels())
        text_channel_count = sum(isinstance(c, discord.TextChannel) for c in all_channels)
        voice_channel_count = sum(isinstance(c, discord.VoiceChannel) for c in all_channels)
        channel_count = len(all_channels)

        slash_commands = len(self.bot.tree.get_commands())
        commands_count = len(tuple(self.bot.walk_commands()))

        uptime_seconds = int(time.time() - self.start_time)
        uptime = str(datetime.timedelta(seconds=uptime_seconds))

        if self._code_stats is None:
            self._code_stats = self.gather_file_stats(".")
        total_files, total_lines, total_words = self._code_stats

        memory_info = psutil.virtual_memory()
        channels_connected = len(self.bot.voice_clients)
        playing_tracks = sum(1 for vc in self.bot.voice_clients if getattr(vc, "playing", False))

        shard_id = ctx.guild.shard_id if ctx.guild else 0
        websocket_latency = round(self.bot.latency * 1000, 2)

        db_latency = "N/A"
        try:
            async with connect('afk.db') as db:
                start = time.perf_counter()
                await db.execute("SELECT 1")
                db_latency = f"{round((time.perf_counter() - start) * 1000, 2)} ms"
        except Exception:
            pass

        embed = Embed(
            title="REM ALL IN ONE BOT",
            description=(
                f"**Servers:** `{guild_count}`\n"
                f"**Users:** `{total_users}` total, `{human_count}` humans, `{bot_count}` bots\n"
                f"**Channels:** `{channel_count}` total, `{text_channel_count}` text, `{voice_channel_count}` voice\n"
                f"**Commands:** `{commands_count}` prefix, `{slash_commands}` slash\n"
                f"**Music:** `{channels_connected}` connected, `{playing_tracks}` playing, `{self.total_songs_played}` songs\n"
                f"**Uptime:** `{uptime}`\n"
                f"**Latency:** `{websocket_latency} ms` ws, `{db_latency}` db"
            ),
        )
        embed.add_field(
            name="System",
            value=(
                f"CPU `{psutil.cpu_percent()}%`"
                f" | RAM `{memory_info.used / (1024 ** 2):,.0f} MB`"
                f" | Code `{total_files}` files / `{total_lines}` lines"
            ),
            inline=False,
        )
        if self.bot.user:
            embed.set_footer(text="Powered by REM ALL IN ONE BOT", icon_url=self.bot.user.display_avatar.url)

        await ctx.reply(view=embed_to_view(embed), mention_author=False)
        await processing_message.delete()
