"""Core data types shared across the bot."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Code:
    """A single redemption code discovered from a source.

    ``code`` is stored verbatim but compared case-insensitively via :meth:`key`,
    because the same code shows up as e.g. ``WutheringGift`` / ``WUTHERINGGIFT``
    on different sites.
    """

    code: str
    reward: str | None = None
    source: str | None = None

    def key(self) -> str:
        """Normalised identity used for de-duplication and storage."""
        return self.code.strip().upper()

    def __post_init__(self) -> None:
        # Always store the canonical upper-case form so the DB and Discord output
        # are consistent regardless of how a given site capitalised it.
        object.__setattr__(self, "code", self.code.strip().upper())
