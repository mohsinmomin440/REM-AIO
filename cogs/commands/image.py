import random

import aiohttp
import discord
from discord.ext import commands

from utils.components_v2 import error_panel, info_panel
from utils.config import PEXELS_API_KEY
from utils.cv2_compat import embed_to_view


class ImageCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_pexels_image(self, query):
        if not PEXELS_API_KEY:
            return None
        headers = {
            "Authorization": PEXELS_API_KEY
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.pexels.com/v1/search?query={query}&per_page=50",
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if data.get("photos"):
                    image = random.choice(data["photos"])
                    return image["src"]["original"]
                return None

    async def fetch_waifu_image(self, category="waifu"):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.waifu.pics/sfw/{category}") as resp:
                data = await resp.json()
                return data["url"]

    @commands.command(name="boy")
    async def boy_image(self, ctx):
        if not PEXELS_API_KEY:
            return await ctx.send(view=error_panel("Set `PEXELS_API_KEY` in `.env` to use image search.", title="Not Configured"))
        url = await self.fetch_pexels_image("handsome boy")
        if url:
            await ctx.send(view=embed_to_view(discord.Embed(title="👦 Boy Pic").set_image(url=url)))
        else:
            await ctx.send(view=info_panel("No boy image found.", title="Image Search"))

    @commands.command(name="girlpic", aliases=["girlimg"])
    async def girl_image(self, ctx):
        if not PEXELS_API_KEY:
            return await ctx.send(view=error_panel("Set `PEXELS_API_KEY` in `.env` to use image search.", title="Not Configured"))
        url = await self.fetch_pexels_image("beautiful girl")
        if url:
            await ctx.send(view=embed_to_view(discord.Embed(title="👧 Girl Pic").set_image(url=url)))
        else:
            await ctx.send(view=info_panel("No girl image found.", title="Image Search"))

    @commands.command(name="couple")
    async def couple_image(self, ctx):
        if not PEXELS_API_KEY:
            return await ctx.send(view=error_panel("Set `PEXELS_API_KEY` in `.env` to use image search.", title="Not Configured"))
        url = await self.fetch_pexels_image("romantic couple")
        if url:
            await ctx.send(view=embed_to_view(discord.Embed(title="💑 Couple Pic").set_image(url=url)))
        else:
            await ctx.send(view=info_panel("No couple image found.", title="Image Search"))

    @commands.command(name="anime")
    async def anime_image(self, ctx):
        url = await self.fetch_waifu_image("waifu")
        await ctx.send(view=embed_to_view(discord.Embed(title="🧚 Anime Waifu").set_image(url=url)))