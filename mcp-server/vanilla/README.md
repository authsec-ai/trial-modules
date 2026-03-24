# Vanilla MCP Server — Team Knowledge Base (No Auth)

A fully functional MCP server where **every tool is exposed to every user with zero authentication**. This is the "before" demo — run it to see how easy it is to read confidential data, delete notes, and leave no audit trail.

---

## The Security Problem

When you build an MCP server without AuthSec, this is what happens:

| Tool | What Goes Wrong |
|------|----------------|
| `search_notes` | Anyone can search and read **confidential finance notes** — no login required |
| `create_note` | Notes are created as "anonymous" — **no identity** is attached to the author |
| `delete_note` | Anyone can delete any note — **no admin check**, no confirmation |
| `list_users` | The access audit log is visible to the **entire public** |

There's no way to know who did what, no way to restrict access, and no way to hide sensitive tools.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> `requirements.txt` only needs `mcp>=1.0.0` — no AuthSec SDK required for the vanilla demo.

### 2. Run the server

```bash
python server.py
```

The server starts on `http://0.0.0.0:3000` (change the port with `MCP_PORT` env var).

### 3. Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector http://localhost:3000
```

All 4 tools appear **immediately** — no login, no OAuth, no nothing. Try:
- Call `search_notes` with query `"confidential"` — you'll get the finance note
- Call `delete_note` with `note_id=3` — the confidential note is gone
- Call `list_users` — full audit log visible to anyone

---

## How This Server Works

The server uses the standard `FastMCP` library with plain `@mcp.tool()` decorators:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Team Knowledge Base (Vanilla)")

@mcp.tool()
def search_notes(query: str) -> str:
    """Anyone can search everything — including confidential notes."""
    results = do_search_notes(query)
    return json.dumps({"results": results})

@mcp.tool()
def delete_note(note_id: int) -> str:
    """Anyone can delete anything — no admin check!"""
    result = do_delete_note(note_id)
    return json.dumps(result)
```

Notice: no `@protected_by_AuthSec`, no `run_mcp_server_with_oauth`. Just raw, unprotected tools.

### File Structure

```
vanilla/
├── server.py          # MCP server with @mcp.tool() decorators (no auth)
├── tools.py           # Pure business logic (SQLite database, shared with protected/)
├── requirements.txt   # mcp>=1.0.0
├── .env.example       # MCP_PORT, KB_DB_PATH
└── README.md          # This file
```

`tools.py` contains the shared business logic — the same file is used identically in the [protected version](../protected/). This proves that AuthSec doesn't require you to rewrite your business logic.

---

## The Fix

To see the same server with proper authentication and RBAC, check out [`../protected/`](../protected/).

The transition is three steps:

### 1. Install the SDK

```bash
# From PyPI
pip install authsec-sdk

# Or from source (clone the repo first)
git clone https://github.com/authsec-ai/sdk-authsec.git
pip install -e /path/to/sdk-authsec/packages/python-sdk
```

### 2. Configure your client_id

Get a `client_id` by signing up at [app.authsec.ai](https://app.authsec.ai), creating an MCP Server application, and copying the UUID. Then configure:

```bash
# Option A: interactive setup (creates .authsec.json — SDK reads it automatically)
authsec init

# Option B: manual .env file
cp .env.example .env   # edit AUTHSEC_CLIENT_ID
```

`authsec init` prompts you for "default or custom URLs" and your `client_id`, then writes a `.authsec.json` config file that the SDK picks up at startup — no code changes needed.

### 3. Change the code (minimal diff)

```python
# BEFORE (vanilla):
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("Team Knowledge Base")

@mcp.tool()
def delete_note(note_id: int) -> str: ...

mcp.run(transport="sse")

# AFTER (protected):
from authsec_sdk import protected_by_AuthSec, run_mcp_server_with_oauth

@protected_by_AuthSec("delete_note", roles=["admin"])
async def delete_note(arguments: dict) -> list: ...

run_mcp_server_with_oauth(sys.modules[__name__], client_id, app_name)
```

Same `tools.py`, same business logic — just wrapped with auth.
