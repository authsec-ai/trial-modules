"""
Protected MCP Server — Team Knowledge Base (AuthSec OAuth + RBAC).

Same business logic as the vanilla server, but every tool is wrapped with
@protected_by_AuthSec. Tools are hidden until the user authenticates,
and RBAC rules control who can do what.

Run:
    pip install -r requirements.txt   # or: pip install -e ../../sdk-authsec/packages/python-sdk
    python server.py
"""

import os
import sys
import json
from authsec_sdk import protected_by_AuthSec, run_mcp_server_with_oauth

from tools import init_database, do_search_notes, do_create_note, do_delete_note, do_list_users, log_audit

# ---------------------------------------------------------------------------
# Configuration (env vars or defaults)
# ---------------------------------------------------------------------------
CLIENT_ID = os.environ.get("AUTHSEC_CLIENT_ID", "your-client-id-here")
APP_NAME = os.environ.get("AUTHSEC_APP_NAME", "Team Knowledge Base (Protected)")
PORT = int(os.environ.get("AUTHSEC_PORT", "3005"))


# ---------------------------------------------------------------------------
# Protected tools — hidden until authenticated, gated by RBAC
# ---------------------------------------------------------------------------

@protected_by_AuthSec(
    "search_notes",
    scopes=["read"],
    description="Search notes by keyword (requires 'read' scope).",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword"}
        },
        "required": ["query"],
    },
)
async def search_notes(arguments: dict) -> list:
    query = arguments.get("query", "")
    user_email = arguments.get("_user_info", {}).get("email", "unknown")
    results = do_search_notes(query)
    log_audit("search_notes", user_email=user_email, detail=f"query={query}")
    payload = {"results": results, "count": len(results)} if results else {"results": [], "message": "No notes found."}
    return [{"type": "text", "text": json.dumps(payload, default=str)}]


@protected_by_AuthSec(
    "create_note",
    scopes=["write"],
    description="Create a new note (requires 'write' scope).",
    inputSchema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Note title"},
            "content": {"type": "string", "description": "Note body"},
            "tags": {"type": "string", "description": "Comma-separated tags"},
        },
        "required": ["title", "content"],
    },
)
async def create_note(arguments: dict) -> list:
    user_email = arguments.get("_user_info", {}).get("email", "unknown")
    note = do_create_note(
        title=arguments.get("title", "Untitled"),
        content=arguments.get("content", ""),
        tags=arguments.get("tags", ""),
        created_by=user_email,
    )
    log_audit("create_note", user_email=user_email, detail=f"title={note['title']}")
    return [{"type": "text", "text": json.dumps({"created": note}, default=str)}]


@protected_by_AuthSec(
    "delete_note",
    roles=["admin"],
    description="Delete a note by ID (admin only).",
    inputSchema={
        "type": "object",
        "properties": {
            "note_id": {"type": "integer", "description": "ID of the note to delete"}
        },
        "required": ["note_id"],
    },
)
async def delete_note(arguments: dict) -> list:
    user_email = arguments.get("_user_info", {}).get("email", "unknown")
    note_id = arguments.get("note_id", 0)
    result = do_delete_note(int(note_id))
    log_audit("delete_note", user_email=user_email, detail=f"note_id={note_id}")
    return [{"type": "text", "text": json.dumps(result, default=str)}]


@protected_by_AuthSec(
    "list_users",
    roles=["admin"],
    scopes=["audit"],
    require_all=True,
    description="View access audit log (admin + audit scope required).",
    inputSchema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def list_users(arguments: dict) -> list:
    user_email = arguments.get("_user_info", {}).get("email", "unknown")
    entries = do_list_users()
    log_audit("list_users", user_email=user_email)
    return [{"type": "text", "text": json.dumps({"audit_log": entries, "count": len(entries)}, default=str)}]


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  PROTECTED MCP SERVER — AuthSec OAuth + RBAC")
    print("=" * 60)
    print()
    print("  Tools are HIDDEN until the user authenticates via OAuth.")
    print("  After login, only permitted tools are revealed:")
    print("  - search_notes  : scopes=[read]")
    print("  - create_note   : scopes=[write]")
    print("  - delete_note   : roles=[admin]")
    print("  - list_users    : roles=[admin], scopes=[audit], require_all")
    print()
    print(f"  Client ID: {CLIENT_ID[:12]}...")
    print(f"  Port: {PORT}")
    print("=" * 60)

    init_database()

    run_mcp_server_with_oauth(
        user_module=sys.modules[__name__],
        client_id=CLIENT_ID,
        app_name=APP_NAME,
        host="0.0.0.0",
        port=PORT,
    )
