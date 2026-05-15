"""
SQLite-backed history of successful meeting briefs.

Shares the same database file as `cache.py` (one connection path, one
WAL-mode SQLite db) but lives in a separate table — `cache` is invisible
optimization that expires; `brief_history` is the user-visible record.

A new row is appended each time the agent completes a fresh brief
(`stop_reason == "end_turn"`). Cache hits do NOT create history rows;
the original entry is already there. Hard-delete only — sensitive
content should actually be gone when removed.
"""

import json
import logging
import sqlite3
import time
from typing import Any, Dict, Optional

import cache  # share _connect() so we use the same DB path + pragmas

logger = logging.getLogger("persona_preparation")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS brief_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_name TEXT NOT NULL,
    meeting_context TEXT,
    selected_identity TEXT,
    brief TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS brief_history_created_idx
    ON brief_history(created_at DESC);
"""


def init_db() -> None:
    """Idempotently create the brief_history table. Safe to call repeatedly."""
    with cache._connect() as conn:
        conn.executescript(_SCHEMA)


def insert(
    person_name: str,
    meeting_context: str,
    selected_identity: Optional[Dict[str, Any]],
    brief: str,
) -> Optional[int]:
    """Append a new brief to history. Returns the new row id, or None on failure."""
    if not brief or not brief.strip():
        return None
    now = int(time.time())
    identity_json = json.dumps(selected_identity) if selected_identity else None
    try:
        with cache._connect() as conn:
            cur = conn.execute(
                "INSERT INTO brief_history "
                "(person_name, meeting_context, selected_identity, brief, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (person_name, meeting_context or "", identity_json, brief, now),
            )
            return int(cur.lastrowid) if cur.lastrowid is not None else None
    except sqlite3.Error as e:
        logger.warning("history.insert failed (%s); brief not saved to history", e)
        return None


def _row_to_dict(row, *, include_brief: bool) -> Dict[str, Any]:
    identity_raw = row["selected_identity"]
    identity: Optional[Dict[str, Any]] = None
    if identity_raw:
        try:
            identity = json.loads(identity_raw)
        except json.JSONDecodeError:
            identity = None
    item: Dict[str, Any] = {
        "id": row["id"],
        "person_name": row["person_name"],
        "meeting_context": row["meeting_context"] or "",
        "selected_identity": identity,
        "created_at": row["created_at"],
    }
    if include_brief:
        item["brief"] = row["brief"]
    return item


def list_items(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """Return slim history rows (no brief body) plus the total count."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    try:
        with cache._connect() as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) FROM brief_history").fetchone()[0]
            rows = conn.execute(
                "SELECT id, person_name, meeting_context, selected_identity, created_at "
                "FROM brief_history ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    except sqlite3.Error as e:
        logger.warning("history.list_items failed (%s)", e)
        return {"items": [], "total": 0}
    items = [_row_to_dict(r, include_brief=False) for r in rows]
    return {"items": items, "total": int(total)}


def get(item_id: int) -> Optional[Dict[str, Any]]:
    """Return the full history row including the brief body, or None."""
    try:
        with cache._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, person_name, meeting_context, selected_identity, brief, created_at "
                "FROM brief_history WHERE id = ?",
                (item_id,),
            ).fetchone()
    except sqlite3.Error as e:
        logger.warning("history.get failed (%s)", e)
        return None
    if not row:
        return None
    return _row_to_dict(row, include_brief=True)


def delete(item_id: int) -> bool:
    """Hard-delete a row. Returns True if a row was removed."""
    try:
        with cache._connect() as conn:
            cur = conn.execute("DELETE FROM brief_history WHERE id = ?", (item_id,))
            return (cur.rowcount or 0) > 0
    except sqlite3.Error as e:
        logger.warning("history.delete failed (%s)", e)
        return False


def clear_all() -> None:
    """Remove every row. Test-only helper."""
    try:
        with cache._connect() as conn:
            conn.execute("DELETE FROM brief_history")
    except sqlite3.Error as e:
        logger.warning("history.clear_all failed (%s)", e)
