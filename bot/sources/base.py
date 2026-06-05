"""Source base class and the generic HTML code extractor.

Wuthering Waves codes have no official API, so we scrape community "active codes"
pages. Codes are short, ALL-CAPS, alphanumeric tokens (e.g. ``WUTHERINGGIFT``,
``STRANGEVISITORS``, ``M5KJ5HV32T``). The extractor below pulls every token that
*looks* like a code out of the candidate-bearing tags, then filters aggressively
against a blocklist of common English/UI words to kill false positives.

This is deliberately layout-tolerant: rather than depending on a fragile CSS
selector that breaks on every site redesign, we read the visible text of the
likely-bearing elements (table cells, list items, code/strong tags). The cost is
the occasional false positive, which the blocklist handles.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod

import aiohttp
from bs4 import BeautifulSoup

from ..models import Code

log = logging.getLogger(__name__)

# A code token: 6–16 chars, upper-case letters and digits, and must contain at
# least one letter (pure numbers like "20000" are rewards/credits, not codes).
CODE_RE = re.compile(r"\b(?=[A-Z0-9]*[A-Z])[A-Z0-9]{6,16}\b")

# Common ALL-CAPS tokens that match the shape of a code but never are one.
# Extend this freely as you spot false positives in the logs.
BLOCKLIST: frozenset[str] = frozenset(
    {
        # site / web furniture
        "HTTPS", "HTML", "HTTP", "JSON", "EMAIL", "LOGIN", "SUBMIT", "SEARCH",
        "ACCEPT", "COOKIE", "COOKIES", "PRIVACY", "POLICY", "GOOGLE", "TWITTER",
        "FACEBOOK", "YOUTUBE", "DISCORD", "REDDIT", "GITHUB", "ANDROID",
        # game / article vocabulary that is all-caps or gets upper-cased
        "ASTRITE", "ASTRITES", "SHELL", "CREDIT", "CREDITS", "RESONANCE",
        "POTION", "POTIONS", "REVIVAL", "INHALER", "INHALERS", "ENERGY",
        "REWARD", "REWARDS", "REDEEM", "REDEEMED", "EXPIRED", "ACTIVE",
        "UNION", "LEVEL", "VERSION", "LIVESTREAM", "PIONEER", "PODCAST",
        "WUTHERING", "WAVES", "WUWA", "KURO", "GAMES", "PATCH", "UPDATE",
        "CHAPTER", "QUEST", "STORY", "CODE", "CODES", "GIFT", "GIFTS",
        "PREMIUM", "ADVANCED", "MEDIUM", "SMALL", "LARGE", "ENCLOSURE",
        "TANK", "BAG", "BAGS", "CORE", "CORES",
        # calendar / units
        "JANUARY", "FEBRUARY", "MARCH", "APRIL", "AUGUST", "SEPTEMBER",
        "OCTOBER", "NOVEMBER", "DECEMBER", "MONDAY", "TUESDAY", "WEDNESDAY",
        "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY",
    }
)

# Tags whose text is worth scanning for codes. Keeps us off nav/script noise.
BEARING_TAGS = ("code", "strong", "b", "td", "li", "span", "p", "h2", "h3", "mark")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class Source(ABC):
    name: str

    @abstractmethod
    async def fetch(self, session: aiohttp.ClientSession) -> list[Code]:
        """Return the codes currently advertised by this source."""


class HtmlSource(Source):
    """Generic scraper: fetch a page, extract code-shaped tokens, filter noise."""

    def __init__(self, name: str, url: str, timeout: float = 20.0) -> None:
        self.name = name
        self.url = url
        self.timeout = timeout

    async def fetch(self, session: aiohttp.ClientSession) -> list[Code]:
        try:
            async with session.get(
                self.url,
                headers=DEFAULT_HEADERS,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as resp:
                if resp.status != 200:
                    log.warning("[%s] HTTP %s for %s", self.name, resp.status, self.url)
                    return []
                html = await resp.text()
        except Exception as exc:  # network error, timeout, etc. — never crash the loop
            log.warning("[%s] fetch failed: %s", self.name, exc)
            return []

        return self.extract(html)

    def extract(self, html: str) -> list[Code]:
        """Parse codes out of raw HTML. Exposed separately so tests can feed fixtures."""
        soup = BeautifulSoup(html, "html.parser")

        # Drop script/style so we never scrape JS identifiers or CSS class names.
        for bad in soup(["script", "style", "noscript"]):
            bad.decompose()

        found: dict[str, Code] = {}
        for tag in soup.find_all(BEARING_TAGS):
            text = tag.get_text(" ", strip=True)
            if not text:
                continue
            for match in CODE_RE.findall(text):
                if match in BLOCKLIST:
                    continue
                key = match.upper()
                if key not in found:
                    found[key] = Code(
                        code=match,
                        source=self.name,
                        source_links=((self.name, self.url),),
                    )

        log.debug("[%s] extracted %d candidate codes", self.name, len(found))
        return list(found.values())
