from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

import discord
from discord.ext import commands, menus
from discord.ext.commands import Context
from discord import ButtonStyle, Interaction

from utils import emojis
from utils.cv2_compat import panel_with_actions, sync_panel_message

if TYPE_CHECKING:
    pass


class _PaginatorControls(discord.ui.View):
    def __init__(self, paginator: "Paginator"):
        super().__init__(timeout=180)
        self.paginator = paginator
        self.panel_embed: Optional[discord.Embed] = None
        self.message: Optional[discord.Message] = None
        self._fill_items()

    def _fill_items(self) -> None:
        self.clear_items()
        source = self.paginator.source
        if not source.is_paginating():
            return

        max_pages = source.get_max_pages()
        use_last_and_first = max_pages is not None and max_pages >= 2
        page = self.paginator.current_page

        if use_last_and_first:
            self.add_item(self._button("first", str(emojis.REWIND1), page == 0))
        self.add_item(self._button("prev", str(emojis.NEXT), page == 0))
        self.add_item(self._button("stop", str(emojis.DELETE), style=ButtonStyle.danger))
        self.add_item(
            self._button(
                "next",
                str(emojis.ICONS_NEXT),
                max_pages is not None and (page + 1) >= max_pages,
            )
        )
        if use_last_and_first:
            self.add_item(
                self._button(
                    "last",
                    str(emojis.FORWARD),
                    max_pages is not None and (page + 1) >= max_pages,
                )
            )

    def _button(
        self,
        action: str,
        emoji: str,
        disabled: bool = False,
        *,
        style: ButtonStyle = ButtonStyle.secondary,
    ) -> discord.ui.Button:
        button = discord.ui.Button(
            emoji=emoji,
            style=style,
            disabled=disabled,
            custom_id=f"paginator:{action}",
        )

        async def callback(interaction: Interaction) -> None:
            if not await self.paginator.interaction_check(interaction):
                return

            if action == "first":
                await self.paginator.show_page(interaction, 0)
            elif action == "prev":
                await self.paginator.show_checked_page(interaction, self.paginator.current_page - 1)
            elif action == "stop":
                await interaction.response.defer()
                await interaction.delete_original_response()
                self.stop()
            elif action == "next":
                await self.paginator.show_checked_page(interaction, self.paginator.current_page + 1)
            elif action == "last":
                max_pages = self.paginator.source.get_max_pages()
                if max_pages:
                    await self.paginator.show_page(interaction, max_pages - 1)

        button.callback = callback
        return button

    async def on_timeout(self) -> None:
        await sync_panel_message(self, disable=True)


class Paginator:
    """CV2 paginator that renders embed pages as Component v2 panels."""

    def __init__(
        self,
        source: menus.PageSource,
        *,
        ctx: Context | Interaction,
        check_embeds: bool = True,
    ):
        self.source: menus.PageSource = source
        self.check_embeds: bool = check_embeds
        self.ctx = ctx
        self.message: Optional[discord.Message] = None
        self.current_page: int = 0
        self.controls = _PaginatorControls(self)

    async def _get_page_embed(self, page_number: int) -> discord.Embed:
        page = await self.source.get_page(page_number)
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if isinstance(value, discord.Embed):
            return value
        if isinstance(value, str):
            return discord.Embed(description=value, color=0x000000)
        if isinstance(value, dict) and value.get("embed"):
            return value["embed"]
        return discord.Embed(description="\u200b", color=0x000000)

    def _panel_view(self, page_number: int, embed: discord.Embed) -> discord.ui.LayoutView:
        self.controls.panel_embed = embed
        self.controls._fill_items()
        return panel_with_actions(embed, self.controls, timeout=self.controls.timeout)

    async def show_page(self, interaction: Interaction, page_number: int) -> None:
        self.current_page = page_number
        embed = await self._get_page_embed(page_number)
        view = self._panel_view(page_number, embed)
        if interaction.response.is_done():
            if self.message:
                await self.message.edit(view=view)
        else:
            await interaction.response.edit_message(view=view)

    async def show_checked_page(self, interaction: Interaction, page_number: int) -> None:
        max_pages = self.source.get_max_pages()
        try:
            if max_pages is None:
                await self.show_page(interaction, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(interaction, page_number)
        except IndexError:
            pass

    async def interaction_check(self, interaction: Interaction) -> bool:
        if isinstance(self.ctx, Interaction):
            if interaction.user and interaction.user.id in (
                self.ctx.client.owner_id,
                self.ctx.user.id,
            ):
                return True
            await interaction.response.send_message(
                "Uh oh! That message doesn't belong to you. You must run this command to interact with it.",
                ephemeral=True,
            )
            return False

        if interaction.user and interaction.user.id in (
            self.ctx.bot.owner_id,
            self.ctx.author.id,
        ):
            return True

        await interaction.response.send_message(
            "Uh oh! That message doesn't belong to you. You must run this command to interact with it.",
            ephemeral=True,
        )
        return False

    async def paginate(
        self,
        *,
        content: Optional[str] = None,
        ephemeral: bool = False,
        **kwargs,
    ) -> None:
        await self.source._prepare_once()
        embed = await self._get_page_embed(0)
        view = self._panel_view(0, embed)

        if isinstance(self.ctx, Interaction):
            self.message = await self.ctx.response.send_message(
                content=content,
                view=view,
                ephemeral=ephemeral,
            )
            self.controls.message = self.message
            return

        self.message = await self.ctx.send(content=content, view=view, ephemeral=ephemeral)
        self.controls.message = self.message