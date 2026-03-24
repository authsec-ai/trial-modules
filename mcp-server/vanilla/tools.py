"""
Shared business logic for the Team Knowledge Base MCP server.

Pure Python functions backed by SQLite -- zero SDK dependency.
Import this from either the vanilla or protected server.
"""

import sqlite3
import os
import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.environ.get("KB_DB_PATH", "knowledge_base.db")

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_database() -> None:
    """Create tables and seed sample data on first run."""
    conn = _get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            content     TEXT NOT NULL,
            tags        TEXT DEFAULT '',
            created_by  TEXT DEFAULT 'system',
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS access_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            action      TEXT NOT NULL,
            user_email  TEXT DEFAULT 'anonymous',
            detail      TEXT DEFAULT '',
            timestamp   TEXT DEFAULT (datetime('now'))
        )
    """)

    # Seed data (only on first run)
    row = cur.execute("SELECT COUNT(*) AS cnt FROM notes").fetchone()
    if row["cnt"] == 0:
        seed = [
            (
                "Onboarding Guide",
                "Welcome to Acme Corp! Start by reading the engineering handbook, "
                "then set up your dev environment with `make setup`.",
                "onboarding,engineering",
                "hr-bot",
            ),
            (
                "REST API Standards",
                "All endpoints must use JSON:API format. Pagination via cursor tokens. "
                "Rate limit: 100 req/min per API key.",
                "api,standards",
                "tech-lead",
            ),
            (
                "Q3 Financial Summary (Confidential)",
                "Revenue: $4.2M (+18% QoQ). Burn rate: $320K/mo. Runway: 14 months. "
                "Board deck due Oct 15.",
                "finance,confidential",
                "cfo",
            ),
            (
                "Incident Response Playbook",
                "Sev-1: page on-call -> open war room -> CEO notified within 30 min. "
                "Post-mortem required within 48 hours.",
                "security,ops",
                "security-team",
            ),
        ]
        cur.executemany(
            "INSERT INTO notes (title, content, tags, created_by) VALUES (?, ?, ?, ?)",
            seed,
        )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Business functions (called by MCP tool handlers)
# ---------------------------------------------------------------------------

def do_search_notes(query: str) -> List[Dict[str, Any]]:
    """Full-text search across note titles and content."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, title, content, tags, created_by, created_at FROM notes "
        "WHERE title LIKE ? OR content LIKE ? ORDER BY created_at DESC",
        (f"%{query}%", f"%{query}%"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def do_create_note(
    title: str,
    content: str,
    tags: str = "",
    created_by: str = "anonymous",
) -> Dict[str, Any]:
    """Create a new note and return it."""
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO notes (title, content, tags, created_by) VALUES (?, ?, ?, ?)",
        (title, content, tags, created_by),
    )
    note_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    conn.close()
    return dict(row)


def do_delete_note(note_id: int) -> Dict[str, Any]:
    """Delete a note by ID. Returns status message."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not row:
        conn.close()
        return {"deleted": False, "error": f"Note {note_id} not found"}
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()
    return {"deleted": True, "note_id": note_id, "title": row["title"]}


def do_list_users() -> List[Dict[str, Any]]:
    """Return the access audit log."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, action, user_email, detail, timestamp FROM access_log "
        "ORDER BY timestamp DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_audit(action: str, user_email: str = "anonymous", detail: str = "") -> None:
    """Append an entry to the audit log."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO access_log (action, user_email, detail) VALUES (?, ?, ?)",
        (action, user_email, detail),
    )
    conn.commit()
    conn.close()
