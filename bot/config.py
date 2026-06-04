"""Environment-driven configuration.

Everything the bot needs to run comes from environment variables so the same
image runs unchanged in Docker, on a VPS, or on a Pi. See ``.env.example``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load a local .env if present (no-op in Docker where env is injected directly).
load_dotenv()

REDEEM_URL = "https://wutheringwaves.kurogames.com/en/main/news/redeem"


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass
class Config:
    token: str
    channel_id: int
    ping_role_id: int = 0
    poll_interval_minutes: int = 30
    db_path: str = "/data/codes.db"
    seed_silently: bool = True
    enabled_sources: list[str] = field(default_factory=lambda: ["game8", "pockettactics", "pcgamesn"])
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")

        channel_id = _get_int("CHANNEL_ID", 0)
        if not channel_id:
            raise SystemExit("CHANNEL_ID is not set or invalid.")

        sources_raw = os.getenv("ENABLED_SOURCES", "").strip()
        enabled = [s.strip().lower() for s in sources_raw.split(",") if s.strip()] or [
            "game8",
            "pockettactics",
            "pcgamesn",
        ]

        return cls(
            token=token,
            channel_id=channel_id,
            ping_role_id=_get_int("PING_ROLE_ID", 0),
            poll_interval_minutes=max(5, _get_int("POLL_INTERVAL_MINUTES", 30)),
            db_path=os.getenv("DB_PATH", "/data/codes.db").strip() or "/data/codes.db",
            seed_silently=_get_bool("SEED_SILENTLY", True),
            enabled_sources=enabled,
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )
