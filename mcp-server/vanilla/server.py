"""
Vanilla MCP Server — Team Knowledge Base (NO authentication).

Demonstrates the security problem: every tool is accessible to everyone,
including delete_note and list_users. No identity, no audit trail, no RBAC.

Run:
    pip install -r requirements.txt
    python server.py
"""

import os
import json
from mcp.server.fastmcp import FastMCP

from tools import init_database, do_search_notes, do_create_note, do_delete_note, do_list_users, log_audit

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
mcp = FastMCP("Team Knowledge Base (Vanilla)")

PORT = int(os.environ.get("MCP_PORT", "3000"))


# ---------------------------------------------------------------------------
# Tools — every single one is PUBLIC, no auth whatsoever
# ---------------------------------------------------------------------------

@mcp.tool()
def search_notes(query: str) -> str:
    """Search notes by keyword. Anyone can read everything — including confidential finance notes."""
    results = do_search_notes(query)
    log_audit("search_notes", detail=f"query={query}")
    if not results:
        return json.dumps({"results": [], "message": "No notes found."})
    return json.dumps({"results": results, "count": len(results)}, default=str)


@mcp.tool()
def create_note(title: str, content: str, tags: str = "") -> str:
    """Create a note. No identity attached — created_by is always 'anonymous'."""
    note = do_create_note(title, content, tags, created_by="anonymous")
    log_audit("create_note", detail=f"title={title}")
    return json.dumps({"created": note}, default=str)


@mcp.tool()
def delete_note(note_id: int) -> str:
    """Delete any note by ID. WARNING: Anyone can delete anything — no admin check!"""
    result = do_delete_note(note_id)
    log_audit("delete_note", detail=f"note_id={note_id}")
    return json.dumps(result, default=str)


@mcp.tool()
def list_users() -> str:
    """View access audit log. In production this should be admin-only, but here it's wide open."""
    entries = do_list_users()
    log_audit("list_users")
    return json.dumps({"audit_log": entries, "count": len(entries)}, default=str)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  VANILLA MCP SERVER — NO AUTHENTICATION")
    print("=" * 60)
    print()
    print("  WARNING: All 4 tools are exposed to EVERYONE.")
    print("  - search_notes  : reads confidential data")
    print("  - create_note   : no identity on created notes")
    print("  - delete_note   : anyone can delete anything")
    print("  - list_users    : audit log visible to all")
    print()
    print(f"  Listening on http://0.0.0.0:{PORT}")
    print(f"  MCP Inspector: npx @modelcontextprotocol/inspector http://0.0.0.0:{PORT}")
    print("=" * 60)

    init_database()
    mcp.run(transport="sse")
