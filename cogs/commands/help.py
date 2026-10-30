import discord
from discord.ext import commands
from difflib import get_close_matches
from core import Context
from core.rem import Rem
from core.Cog import Cog
from utils.Tools import getConfig
import asyncio
from utils.config import serverLink
from utils.Tools import *
from utils import help as vhelp
from utils.components_v2 import error_panel, info_panel

color = 0x185fe5

class HelpCommand(commands.HelpCommand):

  async def send_ignore_message(self, ctx, ignore_type: str):

    if ignore_type == "channel":
      await ctx.reply(f"This channel is ignored.", mention_author=False)
    elif ignore_type == "command":
      await ctx.reply(f"{ctx.author.mention} This Command, Channel, or You have been ignored here.", delete_after=6)
    elif ignore_type == "user":
      await ctx.reply(f"You are ignored.", mention_author=False)

  async def on_help_command_error(self, ctx, error):
    errors = [
      commands.CommandOnCooldown, commands.CommandNotFound,
      discord.HTTPException, commands.CommandInvokeError
    ]
    if not type(error) in errors:
      await self.context.reply(f"Unknown Error Occurred\n{error.original}",
                               mention_author=False)
    else:
      if type(error) == commands.CommandOnCooldown:
        return

    return await super().on_help_command_error(ctx, error)

  async def command_not_found(self, string: str) -> None:
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
        return

    if not check_ignore:
        await self.send_ignore_message(ctx, "command")
        return

    cmds = (str(cmd) for cmd in self.context.bot.walk_commands())
    matches = get_close_matches(string, cmds)

    description = f"Command not found with the name `{string}`."
    fields = []
    if matches:
        match_list = "\n".join([f"{index}. `{match}`" for index, match in enumerate(matches, start=1)])
        fields.append(("Did you mean", match_list))

    await vhelp.reply_help(
        ctx,
        error_panel(
            description,
            title="Command Not Found",
            fields=fields,
            footer=f"Requested by {ctx.author}",
            timeout=vhelp.HELP_VIEW_TIMEOUT,
        ),
    )

  async def send_bot_help(self, mapping):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    data = await getConfig(self.context.guild.id)
    prefix = data["prefix"]
    filtered = await self.filter_commands(self.context.bot.walk_commands(), sort=True)

    view = vhelp.View(
      mapping=mapping,
      ctx=self.context,
      ui=2,
      prefix=prefix,
      total_commands=len(set(self.context.bot.walk_commands())),
    )
    await vhelp.reply_help(ctx, view, mention_author=False)

  async def send_command_help(self, command):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    sonu = command.help if command.help else "No help provided."
    alias = " | ".join(command.aliases) if command.aliases else "No aliases"

    await vhelp.reply_help(
        ctx,
        info_panel(
            f"```xml\n<[] = optional | ‹› = required\nDon't type these while using commands>\n```\n{sonu}",
            title=f"{command.qualified_name.title()} Command",
            fields=[
                ("Aliases", alias),
                ("Usage", f"`{self.context.prefix}{command.signature}`"),
            ],
            footer=f"Requested by {ctx.author}",
            timeout=vhelp.HELP_VIEW_TIMEOUT,
        ),
        mention_author=False,
    )

  def get_command_signature(self, command: commands.Command) -> str:
    parent = command.full_parent_name
    if len(command.aliases) > 0:
      aliases = ' | '.join(command.aliases)
      fmt = f'[{command.name} | {aliases}]'
      if parent:
        fmt = f'{parent}'
      alias = f'[{command.name} | {aliases}]'
    else:
      alias = command.name if not parent else f'{parent} {command.name}'
    return f'{alias} {command.signature}'

  def common_command_formatting(self, embed_like, command):
    embed_like.title = self.get_command_signature(command)
    if command.description:
      embed_like.description = f'{command.description}\n\n{command.help}'
    else:
      embed_like.description = command.help or 'No help found...'

  async def send_group_help(self, group):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    entries = [
        (
            f"➜ `{self.context.prefix}{cmd.qualified_name}`",
            f"{cmd.short_doc if cmd.short_doc else ''}\n\u200b",
        )
        for cmd in group.commands
    ]

    view = vhelp.HelpListView(
      ctx,
      title=f"{group.qualified_name.title()} [{len(group.commands)}]",
      description="< > Duty | [ ] Optional",
      entries=entries,
      per_page=4,
    )
    await vhelp.reply_help(ctx, view, mention_author=False)

  async def send_cog_help(self, cog):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    entries = [(
      f"➜ `{self.context.prefix}{cmd.qualified_name}`",
      f"{cmd.short_doc if cmd.short_doc else ''}\n\u200b",
    ) for cmd in cog.get_commands()]

    view = vhelp.HelpListView(
      ctx,
      title=f"{cog.qualified_name.title()} ({len(cog.get_commands())})",
      description="< > Duty | [ ] Optional",
      entries=entries,
      per_page=4,
    )
    await vhelp.reply_help(ctx, view, mention_author=False)


class Help(Cog, name="help"):

  def __init__(self, client: Rem):
    self.client = client
    self._original_help_command = client.help_command
    attributes = {
      'name': "help",
      'aliases': ['h'],
      'cooldown': commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.user),
      'help': 'Shows help about bot, a command, or a category'
    }
    client.help_command = HelpCommand(command_attrs=attributes)
    client.help_command.cog = self

  async def cog_unload(self):
    self.client.help_command = self._original_help_command