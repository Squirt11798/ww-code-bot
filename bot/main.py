"""Discord bot entry point.

Polls the code sources on a fixed interval, posts any genuinely-new codes to the
configured channel, and exposes a few slash commands for manual control.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands, tasks

from .aggregator import Aggregator
from .config import REDEEM_URL, Config
from .models import Code
from .sources import build_sources
from .store import CodeStore

log = logging.getLogger(__name__)


class CodeBot(commands.Bot):
    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.store = CodeStore(config.db_path)
        self.aggregator = Aggregator(build_sources(config.enabled_sources))

    async def setup_hook(self) -> None:
        # Register the slash commands globally and start the polling loop.
        await self.tree.sync()
        self.poll_loop.change_interval(minutes=self.config.poll_interval_minutes)
        self.poll_loop.start()

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id=%s)", self.user, self.user.id if self.user else "?")
        log.info(
            "Watching %d sources, posting to channel %s every %d min",
            len(self.config.enabled_sources),
            self.config.channel_id,
            self.config.poll_interval_minutes,
        )

    # ── polling ─────────────────────────────────────────────────────────────
    @tasks.loop(minutes=30)  # interval overridden in setup_hook from config
    async def poll_loop(self) -> None:
        await self.check_and_post()

    @poll_loop.before_loop
    async def _before_poll(self) -> None:
        await self.wait_until_ready()

    async def check_and_post(self, *, force: bool = False) -> list[Code]:
        """Fetch, diff against the store, and post new codes. Returns what was posted.

        On the first ever run, if ``SEED_SILENTLY`` is set, we record everything as
        seen without posting so the channel doesn't get a backlog dump. ``force``
        (used by /checknow) bypasses neither — it just runs a normal cycle now.
        """
        codes = await self.aggregator.gather()
        if not codes:
            log.info("No codes returned this cycle.")
            return []

        first_run = self.store.count() == 0
        new = self.store.new_codes(codes)

        if first_run and self.config.seed_silently and not force:
            for code in codes:
                self.store.add(code)
            log.info("First run: seeded %d existing codes silently (none posted).", len(codes))
            return []

        if not new:
            log.info("No new codes (all %d already seen).", len(codes))
            return []

        channel = self.get_channel(self.config.channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(self.config.channel_id)
            except Exception as exc:
                log.error("Cannot resolve channel %s: %s", self.config.channel_id, exc)
                return []

        posted: list[Code] = []
        for code in new:
            try:
                await channel.send(  # type: ignore[union-attr]
                    content=self._ping_prefix(),
                    embed=self._embed(code),
                )
                self.store.add(code)
                posted.append(code)
                log.info("Posted new code: %s", code.code)
            except Exception as exc:
                # Don't mark as seen if the post failed — retry next cycle.
                log.error("Failed to post %s: %s", code.code, exc)

        return posted

    # ── presentation ────────────────────────────────────────────────────────
    def _ping_prefix(self) -> str | None:
        if self.config.ping_role_id:
            return f"<@&{self.config.ping_role_id}>"
        return None

    def _embed(self, code: Code) -> discord.Embed:
        embed = discord.Embed(
            title="🌊 New Wuthering Waves Code!",
            description=f"**`{code.code}`**",
            color=0x4AA3DF,
            url=REDEEM_URL,
        )
        if code.reward:
            embed.add_field(name="Reward", value=code.reward, inline=False)
        if code.expires:
            embed.add_field(name="⏳ Expires", value=code.expires, inline=False)
        embed.add_field(name="Redeem", value=f"[Official redemption page]({REDEEM_URL})", inline=False)
        if code.source_links:
            links = " · ".join(f"[{name}]({url})" for name, url in code.source_links)
            embed.add_field(name="Source", value=links, inline=False)
        elif code.source:
            embed.set_footer(text=f"Found via: {code.source}")
        return embed


def _register_commands(bot: CodeBot) -> None:
    @bot.tree.command(name="checknow", description="Check the sources for new codes right now.")
    async def checknow(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        posted = await bot.check_and_post(force=True)
        if posted:
            await interaction.followup.send(f"Posted {len(posted)} new code(s).", ephemeral=True)
        else:
            await interaction.followup.send("No new codes found.", ephemeral=True)

    @bot.tree.command(name="codes", description="List the codes currently known to the bot.")
    async def codes(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        current = await bot.aggregator.gather()
        if not current:
            await interaction.followup.send("Couldn't fetch any codes right now — try again later.", ephemeral=True)
            return
        listing = "\n".join(
            f"• `{c.code}`"
            + (f" — {c.reward}" if c.reward else "")
            + (f" _({c.expires})_" if c.expires else "")
            for c in current
        )
        embed = discord.Embed(
            title="🌊 Current Wuthering Waves Codes",
            description=listing[:4000],
            color=0x4AA3DF,
            url=REDEEM_URL,
        )
        embed.set_footer(text="Redeem at the official page (link in title).")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="redeem", description="Get the official Wuthering Waves redemption link.")
    async def redeem(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"Redeem your codes here: {REDEEM_URL}\n"
            "(You must be Union Level 2+ to redeem.)",
            ephemeral=True,
        )


def main() -> None:
    config = Config.from_env()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    bot = CodeBot(config)
    _register_commands(bot)
    bot.run(config.token, log_handler=None)


if __name__ == "__main__":
    main()
