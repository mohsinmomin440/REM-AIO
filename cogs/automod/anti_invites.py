from utils.database import connect
from utils import emojis

import discord
from discord.ext import commands
import asyncio
from datetime import timedelta
import re
from utils.cv2_compat import embed_to_view, embeds_to_view
from utils.automod_helpers import automod_gate, log_automod_action

class AntiInvite(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invite_pattern = re.compile(r'(https?://)?(www\.)?(discord\.gg|discordapp\.com/invite|discord\.com/invite)/\S+')

    async def is_automod_enabled(self, guild_id):
        async with connect('automod.db') as db:
            cursor = await db.execute("SELECT enabled FROM automod WHERE guild_id = ?", (guild_id,))
            result = await cursor.fetchone()
            return result is not None and result[0] == 1

    async def is_anti_invites_enabled(self, guild_id):
        async with connect('automod.db') as db:
            cursor = await db.execute("SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = 'Anti invites'", (guild_id,))
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
            cursor = await db.execute("SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = 'Anti invites'", (guild_id,))
            result = await cursor.fetchone()
            return result[0] if result else None

    async def log_action(self, guild, user, channel, action, reason):
        async with connect('automod.db') as db:
            cursor = await db.execute("SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild.id,))
            log_channel_id = await cursor.fetchone()

        if log_channel_id and log_channel_id[0]:
            log_channel = guild.get_channel(log_channel_id[0])
            if log_channel:
                embed = discord.Embed(title="Automod Log: Anti-Invite", color=0xff0000)
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

        gate = await automod_gate(message, 'Anti invites')
        if gate is None:
            return

        guild = message.guild
        user = message.author
        channel = message.channel


        if self.invite_pattern.search(message.content):
            invite_link = self.invite_pattern.search(message.content).group(0)
            invite_code = invite_link.split('/')[-1]

            try:
                invite = await guild.invites()
                if any(invite.code == invite_code for invite in invite):
                    return  

                punishment = gate.punishment
                action_taken = None
                reason = "Posted an invite link"

                try:
                    if punishment == "Mute":
                        timeout_duration = discord.utils.utcnow() + timedelta(minutes=12)
                        await user.edit(timed_out_until=timeout_duration, reason="Posted an invite link")
                        action_taken = "Muted for 12 minutes"
                    elif punishment == "Kick":
                        await user.kick(reason="Posted an invite link")
                        action_taken = "Kicked"
                    elif punishment == "Ban":
                        await user.ban(reason="Posted an invite link")
                        action_taken = "Banned"
                        
                    await message.delete()

                    simple_embed = discord.Embed(title="Automod Anti-Invite", color=0xff0000)
                    simple_embed.description = f"{emojis.TICK} | {user.mention} has been successfully **{action_taken}** for **posting an invite link.**"
                    
                    simple_embed.set_footer(text="Use the “automod logging” command to get automod logs if it is not enabled.", icon_url=self.bot.user.display_avatar.url)
                    await channel.send(view = embed_to_view(simple_embed), delete_after=30)

                    await log_automod_action(
                    guild, user, channel, action_taken, reason,
                    title='Automod Log: Anti invites',
                    log_channel_id=gate.log_channel_id,
                )

                except discord.Forbidden:
                    pass
                except discord.HTTPException:
                    pass
                except Exception:
                    pass

            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_rate_limit(self, message):
        await asyncio.sleep(10)

