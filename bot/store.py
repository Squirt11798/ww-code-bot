"""Persistence of codes we've already seen, so each code is posted only once.

A tiny SQLite file is plenty here — codes appear a handful of times per patch.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

from .models import Code


class CodeStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_codes (
                code       TEXT PRIMARY KEY,
                reward     TEXT,
                source     TEXT,
                first_seen TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def is_seen(self, code: Code) -> bool:
        cur = self.conn.execute("SELECT 1 FROM seen_codes WHERE code = ?", (code.key(),))
        return cur.fetchone() is not None

    def add(self, code: Code) -> None:
        """Record a code as seen. No-op if already present (keeps the original row)."""
        self.conn.execute(
            "INSERT OR IGNORE INTO seen_codes (code, reward, source, first_seen) VALUES (?, ?, ?, ?)",
            (code.key(), code.reward, code.source, datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def new_codes(self, codes: list[Code]) -> list[Code]:
        """Return only the codes not already in the store, preserving order."""
        return [c for c in codes if not self.is_seen(c)]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM seen_codes").fetchone()[0]

    def close(self) -> None:
        self.conn.close()
