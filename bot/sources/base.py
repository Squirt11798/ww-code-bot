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

# Structural elements walked in document order for the section-aware parse.
STRUCTURE_TAGS = ("h1", "h2", "h3", "h4", "h5", "tr", "li", "dt", "dd")

# Sanity cap: Wuthering Waves realistically never has more than a handful of
# active codes at once. If a source returns more than this, its layout has
# probably broken or it's dumping a stale "all codes ever" list — skip it this
# cycle rather than flood the channel with expired codes.
MAX_ACTIVE_CODES = 15

# A heading or row containing one of these words marks the code(s) as no longer
# valid. Note: matches the whole word "expired", NOT "expires" (which is an
# expiry *date* on a still-active code — handled separately below).
STATUS_EXPIRED_RE = re.compile(r"\bexpired\b|\binactive\b|no longer|\bdead\b", re.I)
STATUS_ACTIVE_RE = re.compile(r"\bactive\b|\bworking\b|\bvalid\b|\bcurrent\b|\bavailable\b", re.I)

# Confirms nearby text is actually a reward description (not random page text).
REWARD_HINT_RE = re.compile(
    r"astrite|shell|credit|potion|inhaler|energy|core|tank|polymer|crystal|waveplate|union|exp\b",
    re.I,
)

# Expiry like "Expires June 30", "valid until 06/30/2026", "ends in 5 days".
_DATE = r"[A-Za-z]+\.?\s+\d{1,2}(?:,?\s+\d{4})?|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d+\s*days?"
EXPIRES_LABEL_RE = re.compile(
    r"(?:expires?|expiry|valid\s+(?:until|through|till)|ends?|until)\s*[:\-–]?\s*(" + _DATE + r")",
    re.I,
)

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

        # Preferred: a section-aware parse that distinguishes active vs expired
        # codes and pulls reward + expiry text. If a site's layout doesn't match
        # (no tables/lists), fall back to a broad scan so we never regress to
        # posting nothing.
        codes = self._structured_extract(soup)
        if codes:
            active = [c for c in codes if c.active]
            log.debug(
                "[%s] structured: %d codes (%d active, %d expired skipped)",
                self.name, len(codes), len(active), len(codes) - len(active),
            )
            return self._sanity_check(active)

        broad = self._broad_extract(soup)
        log.debug("[%s] broad fallback: %d codes", self.name, len(broad))
        return self._sanity_check(broad)

    def _sanity_check(self, codes: list[Code]) -> list[Code]:
        if len(codes) > MAX_ACTIVE_CODES:
            log.warning(
                "[%s] returned %d active codes (> cap %d) — likely a layout break "
                "or stale dump; skipping this source this cycle.",
                self.name, len(codes), MAX_ACTIVE_CODES,
            )
            return []
        return codes

    def _structured_extract(self, soup: BeautifulSoup) -> list[Code]:
        """Walk headings + rows in order, tracking active/expired sections."""
        found: dict[str, Code] = {}
        section_active = True  # assume active until a heading says otherwise
        for el in soup.find_all(STRUCTURE_TAGS):
            if el.name in ("h1", "h2", "h3", "h4", "h5"):
                htext = el.get_text(" ", strip=True)
                if not htext:
                    continue
                if STATUS_EXPIRED_RE.search(htext):
                    section_active = False
                elif STATUS_ACTIVE_RE.search(htext):
                    section_active = True
                continue

            text = el.get_text(" ", strip=True)
            if not text:
                continue
            codes_here = [m for m in CODE_RE.findall(text) if m not in BLOCKLIST]
            if not codes_here:
                continue

            # A single row can also mark itself expired (e.g. a "Status" column).
            row_active = section_active and not STATUS_EXPIRED_RE.search(text)
            reward = self._reward_from(text, codes_here)
            expires = self._expires_from(text)
            for m in codes_here:
                key = m.upper()
                if key in found:
                    continue
                found[key] = Code(
                    code=m,
                    reward=reward,
                    source=self.name,
                    source_links=((self.name, self.url),),
                    active=row_active,
                    expires=expires,
                )
        return list(found.values())

    def _broad_extract(self, soup: BeautifulSoup) -> list[Code]:
        """Layout-agnostic fallback: scan every content-bearing tag for codes."""
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
        return list(found.values())

    @staticmethod
    def _reward_from(text: str, codes: list[str]) -> str | None:
        """Best-effort reward description from a code's row, or None."""
        t = text
        for c in codes:
            t = re.sub(rf"\b{re.escape(c)}\b", " ", t)
        t = EXPIRES_LABEL_RE.sub(" ", t)  # don't let expiry text leak into reward
        t = re.sub(r"\s+", " ", t).strip(" -–—:•|\t()")
        if not REWARD_HINT_RE.search(t):
            return None
        t = re.sub(r"\b(active|expired|new|working|code)\b", " ", t, flags=re.I)
        t = re.sub(r"\s+", " ", t).strip(" -–—:•|\t()")
        return t[:250] or None

    @staticmethod
    def _expires_from(text: str) -> str | None:
        """Best-effort expiry string, e.g. 'Expires June 30' or 'Expires in 5 days'."""
        m = EXPIRES_LABEL_RE.search(text)
        if not m:
            return None
        val = m.group(1).strip(" .,-–")
        if re.search(r"days?$", val, re.I):
            return f"Expires in {val}"
        return f"Expires {val}"
