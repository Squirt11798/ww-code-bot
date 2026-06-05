"""Dry run: fetch the live sources and print what the bot *would* post.

Nothing is sent to Discord and no token is required. Use this to validate live
parsing on the box the bot will actually run from (community sites sometimes
block other IPs). Run with LOG_LEVEL=DEBUG to also see per-source extraction
detail (how many active vs expired codes each site yielded).

  python -m bot.dryrun          # local
  bash dryrun.sh                # via Docker (uses the built image)
"""

from __future__ import annotations

import asyncio
import logging
import os

import aiohttp

from .sources import DEFAULT_ENABLED, build_sources


def _enabled() -> list[str]:
    raw = os.getenv("ENABLED_SOURCES", "").strip()
    names = [s.strip().lower() for s in raw.split(",") if s.strip()]
    return names or list(DEFAULT_ENABLED)


async def _run() -> int:
    sources = build_sources(_enabled())
    if not sources:
        print("No sources enabled (check ENABLED_SOURCES).")
        return 1

    print(f"Dry run — fetching {len(sources)} source(s). Nothing is posted to Discord.\n")

    union: dict[str, object] = {}
    async with aiohttp.ClientSession() as session:
        for src in sources:
            try:
                codes = await src.fetch(session)
            except Exception as exc:
                print(f"  {src.name:<14} ERROR: {exc}\n")
                continue

            print(f"  {src.name:<14} {len(codes):>2} active code(s)   {src.url}")
            for c in sorted(codes, key=lambda c: c.code):
                extras = []
                if c.reward:
                    extras.append(c.reward)
                if c.expires:
                    extras.append(c.expires)
                detail = ("  - " + " | ".join(extras)) if extras else ""
                print(f"        {c.code}{detail}")
                union.setdefault(c.key(), c)
            print()

    print("-" * 60)
    if not union:
        print("Would post NOTHING. If you expected codes, run again with")
        print("LOG_LEVEL=DEBUG to see why (blocked IP, layout change, etc.).")
        return 0

    print(f"Would post {len(union)} unique active code(s):")
    for c in sorted(union.values(), key=lambda c: c.code):  # type: ignore[attr-defined]
        line = f"  * {c.code}"
        if c.reward:
            line += f" - {c.reward}"
        if c.expires:
            line += f"  [{c.expires}]"
        print(line)
    return 0


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "WARNING").upper(), logging.WARNING),
        format="%(levelname)s %(name)s: %(message)s",
    )
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
