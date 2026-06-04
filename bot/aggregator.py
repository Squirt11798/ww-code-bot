"""Run all enabled sources concurrently and merge their results.

A code is kept if *any* source reports it. We attribute it to the sources that
saw it (handy for the embed footer and for spotting a flaky scraper in logs).
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from .models import Code
from .sources import Source

log = logging.getLogger(__name__)


class Aggregator:
    def __init__(self, sources: list[Source]) -> None:
        self.sources = sources

    async def gather(self) -> list[Code]:
        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                *(src.fetch(session) for src in self.sources),
                return_exceptions=True,
            )

        merged: dict[str, Code] = {}
        sources_for: dict[str, set[str]] = {}

        for src, result in zip(self.sources, results):
            if isinstance(result, Exception):
                log.warning("[%s] raised during gather: %s", src.name, result)
                continue
            for code in result:
                key = code.key()
                sources_for.setdefault(key, set()).add(src.name)
                # Prefer the first non-empty reward we see across sources.
                if key not in merged:
                    merged[key] = code
                elif not merged[key].reward and code.reward:
                    merged[key] = code

        # Re-stamp each merged code with the full set of sources that reported it.
        out: list[Code] = []
        for key, code in merged.items():
            srcs = ", ".join(sorted(sources_for.get(key, set())))
            out.append(Code(code=code.code, reward=code.reward, source=srcs))

        log.info("Aggregated %d unique codes from %d sources", len(out), len(self.sources))
        return out
