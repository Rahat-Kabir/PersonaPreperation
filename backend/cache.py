"""
SQLite-backed cache for tool results and final briefs.

One table, key-value with TTL. Keys are sha256 hex digests built from
caller-supplied namespace + canonical JSON payload. Values are JSON strings.

Designed for single-process FastAPI use. A new connection is opened per
operation to remain safe under asyncio.to_thread without sharing connections
across threads. SQLite is in WAL mode, so this is fast enough at our scale.
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from typing import Any, Optional

logger = logging.getLogger("persona_preparation")

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "cache.db")

# TTL presets (seconds)
TOOL_SEARCH_TTL = 7 * 24 * 60 * 60       # Tavily / Brave: 7 days
TOOL_SCRAPE_TTL = 15 * 24 * 60 * 60      # Firecrawl scrape: 15 days
BRIEF_TTL = 15 * 24 * 60 * 60            # Final agent brief: 15 days

# Manual escape hatch: bump to invalidate every existing brief without
# touching the system prompt or model name.
BRIEF_CACHE_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS cache_expires_idx ON cache(expires_at);
"""


def _db_path() -> str:
    """Resolve the cache DB path; CACHE_DB_PATH env var wins for tests."""
    return os.getenv("CACHE_DB_PATH", DEFAULT_DB_PATH)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    """Idempotently create the cache table. Call once at startup."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def _canonical_json(payload: Any) -> str:
    """Stable JSON for hashing: sorted keys, no whitespace."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def build_key(namespace: str, payload: Any) -> str:
    """Build a sha256 cache key from a namespace + arbitrary JSON-able payload."""
    raw = f"{namespace}|{_canonical_json(payload)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(key: str) -> Optional[Any]:
    """Return the cached JSON value for `key`, or None if missing/expired."""
    now = int(time.time())
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (key,),
            ).fetchone()
    except sqlite3.Error as e:
        logger.warning("cache.get failed (%s); treating as miss", e)
        return None

    if not row:
        return None
    value, expires_at = row
    if expires_at <= now:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        logger.warning("cache.get found malformed JSON for key %s; treating as miss", key[:12])
        return None


def set(key: str, value: Any, ttl_seconds: int) -> None:
    """Store `value` under `key` for `ttl_seconds`. Overwrites existing entries."""
    now = int(time.time())
    expires_at = now + max(ttl_seconds, 1)
    try:
        encoded = json.dumps(value, default=str)
    except (TypeError, ValueError) as e:
        logger.warning("cache.set skipped — value not JSON-serializable: %s", e)
        return
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (key, encoded, now, expires_at),
            )
    except sqlite3.Error as e:
        logger.warning("cache.set failed (%s); continuing without persisting", e)


def delete(key: str) -> None:
    """Remove a single key. No-op if absent."""
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
    except sqlite3.Error as e:
        logger.warning("cache.delete failed (%s)", e)


def purge_expired() -> int:
    """Delete all expired rows. Returns the number of rows deleted."""
    now = int(time.time())
    try:
        with _connect() as conn:
            cur = conn.execute("DELETE FROM cache WHERE expires_at <= ?", (now,))
            return cur.rowcount or 0
    except sqlite3.Error as e:
        logger.warning("cache.purge_expired failed (%s)", e)
        return 0


def clear_all() -> None:
    """Remove every row. Test-only helper."""
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM cache")
    except sqlite3.Error as e:
        logger.warning("cache.clear_all failed (%s)", e)
