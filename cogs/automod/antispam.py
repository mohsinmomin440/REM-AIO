from utils.database import connect
from utils import emojis

import discord
from discord.ext import commands
import asyncio
from datetime import timedelta
from utils.cv2_compat import embed_to_view, embeds_to_view
from utils.automod_helpers import automod_gate, log_automod_action

class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_threshold = 5
        self.mute_duration = 12 * 60
        self.recent_messages = {}

    async def is_automod_enabled(self, guild_id):
        async with connect('automod.db') as db:
            cursor = await db.execute("SELECT enabled FROM automod WHERE guild_id = ?", (guild_id,))
            result = await cursor.fetchone()
            return result is not None and result[0] == 1

    async def is_anti_spam_enabled(self, guild_id):
        async with connect('automod.db') as db:
            cursor = await db.execute("SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = 'Anti spam'", (guild_id,))
            result = await cursor.fetchone()
            return result is not None
            

    async def get_ignored_channels(self, guild_id):
        async with connect('automod.db') as db:
            cursor = await db.execute("SELECT id FROM automod_ignored WHERE guild_id = ? AND type = 'channel'", (guild_id,))
            return [row[0] for row in await cursor.fetchall()]

    async def get_ignored_roles(self, guild_id):
        async with connect('automod.db') as db:
            cursor = await db.execute("SELECT id FROM automod_ignored WHERE guild_id = ? AND type = 'role'", (guild_id,))
            return [row[0] for row in await cursor.fetchall()]

    async def get_punishment(self, guild_id):
        async with connect('automod.db') as db:
            cursor = await db.execute("SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = 'Anti spam'", (guild_id,))
            result = await cursor.fetchone()
            return result[0] if result else None

    async def log_action(self, guild, user, channel, action, reason):
        async with connect('automod.db') as db:
            cursor = await db.execute("SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild.id,))
            log_channel_id = await cursor.fetchone()

        if log_channel_id and log_channel_id[0]:
            log_channel = guild.get_channel(log_channel_id[0])
            if log_channel:
                embed = discord.Embed(title="Automod Log: Anti-Spam", color=0xff0000)
                embed.add_field(name="User", value=user.mention, inline=False)
                embed.add_field(name="Action", value=action, inline=False)
                embed.add_field(name="Channel", value=channel.mention, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.set_footer(text=f"User ID: {user.id}")
                avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
                embed.set_thumbnail(url=avatar_url)
                embed.timestamp=discord.utils.utcnow()
                await log_channel.send(view = embed_to_view(embed))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        gate = await automod_gate(message, 'Anti spam')
        if gate is None:
            return

        guild = message.guild
        user = message.author
        channel = message.channel

        current_time = message.created_at.timestamp()
        user_messages = self.recent_messages.get(user.id, [])
        user_messages = [msg for msg in user_messages if current_time - msg < 10]
        user_messages.append(current_time)
        self.recent_messages[user.id] = user_messages

        if len(user_messages) > self.spam_threshold:
            punishment = gate.punishment
            action_taken = None
            reason = "Spamming"

            try:
                if punishment == "Mute":
                    timeout_duration = discord.utils.utcnow() + timedelta(minutes=12)
                    await user.edit(timed_out_until=timeout_duration, reason="Spamming")
                    action_taken = "Muted for 12 minutes"
                elif punishment == "Kick":
                    await user.kick(reason="Spamming")
                    action_taken = "Kicked"
                elif punishment == "Ban":
                    await user.ban(reason="Spamming")
                    action_taken = "Banned"

                simple_embed = discord.Embed(title="Automod Anti-Spam", color=0xff0000)
                simple_embed.description = f"{emojis.TICK} | {user.mention} has been successfully **{action_taken}** for **Spamming.**"
                
                simple_embed.set_footer(text="Use the “automod logging” command to get automod logs if it is not enabled.", icon_url=self.bot.user.display_avatar.url)
                await channel.send(view = embed_to_view(simple_embed), delete_after=30)

                await log_automod_action(
                    guild, user, channel, action_taken, reason,
                    title='Automod Log: Anti spam',
                    log_channel_id=gate.log_channel_id,
                )

            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_rate_limit(self, message):
        await asyncio.sleep(10)

