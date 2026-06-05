"""Code sources.

Each source knows how to fetch one website and return a list of :class:`Code`.
Add a new site by appending a :class:`HtmlSource` to ``ALL_SOURCES`` below — no
other file needs to change.
"""

from __future__ import annotations

from .base import HtmlSource, Source

# ---------------------------------------------------------------------------
# Source registry.
#
# These community sites keep an up-to-date "active codes" list. The generic
# extractor pulls candidate code tokens out of the page and filters them against
# a blocklist (see base.py). If a site redesigns and a scraper stops returning
# codes, tweaking `code_container_hint` or the extraction is a one-line change
# here — the rest of the bot is untouched.
# ---------------------------------------------------------------------------
ALL_SOURCES: dict[str, Source] = {
    "game8": HtmlSource(
        name="game8",
        url="https://game8.co/games/Wuthering-Waves/archives/453149",
    ),
    "pcgamesn": HtmlSource(
        name="pcgamesn",
        url="https://www.pcgamesn.com/wuthering-waves/codes",
    ),
    # NOTE: pockettactics lists every code it has ever seen under one "active"
    # heading with no expired section, so it floods expired codes. It is NOT in
    # DEFAULT_ENABLED. Only enable it if you add expired-handling for that site.
    "pockettactics": HtmlSource(
        name="pockettactics",
        url="https://www.pockettactics.com/wuthering-waves/codes",
    ),
}

# Sources trusted enough to run by default — they cleanly separate active vs
# expired codes, which our parser relies on.
DEFAULT_ENABLED: list[str] = ["game8", "pcgamesn"]


def build_sources(enabled: list[str]) -> list[Source]:
    """Return the Source objects for the names listed in config, skipping unknowns."""
    out: list[Source] = []
    for name in enabled:
        src = ALL_SOURCES.get(name)
        if src is not None:
            out.append(src)
    return out


__all__ = ["Source", "HtmlSource", "ALL_SOURCES", "DEFAULT_ENABLED", "build_sources"]
