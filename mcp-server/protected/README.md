# Protected MCP Server — Team Knowledge Base (AuthSec OAuth + RBAC)

The exact same Team Knowledge Base as the [vanilla version](../vanilla/), now secured with **AuthSec SDK**. Tools are hidden until the user authenticates via OAuth, and RBAC rules control who can see and call each tool.

---

## What Changes vs. Vanilla

The business logic (`tools.py`) is **identical** — not a single line changed. The only differences are in `server.py`:

| Vanilla | Protected |
|---------|-----------|
| `from mcp.server.fastmcp import FastMCP` | `from authsec_sdk import protected_by_AuthSec, run_mcp_server_with_oauth` |
| `@mcp.tool()` | `@protected_by_AuthSec("tool_name", roles=[...], scopes=[...])` |
| `mcp.run(transport="sse")` | `run_mcp_server_with_oauth(sys.modules[__name__], client_id, app_name)` |
| All tools visible immediately | Tools hidden until OAuth login |
| No identity on actions | `arguments["_user_info"]` auto-injected with user email, roles, tenant |
| Anyone can delete notes | Only `admin` role can call `delete_note` |

---

## RBAC Rules

| Tool | Decorator | Who Can Access |
|------|-----------|---------------|
| `search_notes` | `@protected_by_AuthSec("search_notes", scopes=["read"])` | Any authenticated user with `read` scope |
| `create_note` | `@protected_by_AuthSec("create_note", scopes=["write"])` | Users with `write` scope |
| `delete_note` | `@protected_by_AuthSec("delete_note", roles=["admin"])` | Admins only |
| `list_users` | `@protected_by_AuthSec("list_users", roles=["admin"], scopes=["audit"], require_all=True)` | Admins who also have `audit` scope |

---

## Prerequisites

### 1. Get your AuthSec Client ID

You need a `client_id` to connect to the AuthSec auth service:

1. **Sign up** at [app.authsec.ai](https://app.authsec.ai) (free)
2. **Create a new application** — select "MCP Server" as the type
3. **Copy the Client ID** — it's a UUID like `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
4. **Set up RBAC** in your tenant settings:
   - Create roles: `admin`, `user`
   - Create permissions: `read`, `write`, `audit`
   - Assign roles/permissions to your users

### 2. Install the AuthSec SDK

You have two options — the import `from authsec_sdk import ...` works identically either way.

**Option A: From PyPI (recommended for trying it out)**

```bash
pip install authsec-sdk
```

**Option B: From source (recommended for SDK development)**

```bash
# Clone the SDK repo (if you haven't already)
git clone https://github.com/authsec-ai/sdk-authsec.git

# Install in editable mode
pip install -e /path/to/sdk-authsec/packages/python-sdk

# Or using relative path from this folder:
pip install -e ../../../../sdk-authsec/packages/python-sdk
```

### 3. Configure the SDK

There are two ways to configure the SDK. Both result in the same behavior.

**Path 1: `authsec init` (recommended — interactive setup)**

```bash
cd mcp-server/protected
authsec init
```

```
AuthSec SDK — interactive setup

Use default AuthSec URLs or custom? (default/custom) [default]: default
client_id (required): a1b2c3d4-e5f6-7890-abcd-ef1234567890

Config saved to /path/to/mcp-server/protected/.authsec.json
```

> **Troubleshooting: `authsec: command not found`**
>
> If `authsec init` fails after installing the SDK, pip likely installed the binary to a directory not on your PATH. You'll see a warning like:
>
> ```
> WARNING: The script authsec is installed in '/Users/<you>/Library/Python/3.11/bin' which is not on PATH.
> ```
>
> **Quick fix** — run it with the full path:
> ```bash
> /Users/<you>/Library/Python/3.11/bin/authsec init
> ```
>
> **Permanent fix** — add the directory to your PATH. Add this line to your `~/.zshrc` (or `~/.bashrc`):
> ```bash
> export PATH="$PATH:$HOME/Library/Python/3.11/bin"
> ```
> Then reload your shell:
> ```bash
> source ~/.zshrc
> ```
> After that, `authsec init` will work directly.

This creates `.authsec.json` in the current directory. The SDK **automatically reads it** at startup — no code changes needed, no `.env` file required.

If you choose "custom" instead of "default", the CLI prompts you for each URL individually (auth service, services base, CIBA base), letting you point at a self-hosted or staging AuthSec instance.

Verify your config at any time:
```bash
authsec config show
```

**Path 2: Manual `.env` file**

```bash
cp .env.example .env
# Edit .env and paste your AUTHSEC_CLIENT_ID from the dashboard
```

The `server.py` reads `AUTHSEC_CLIENT_ID` from the environment and passes it to `run_mcp_server_with_oauth()`. The auth service URLs default to `https://dev.api.authsec.dev/...` unless you override them with `AUTHSEC_AUTH_SERVICE_URL` / `AUTHSEC_SERVICES_URL` env vars.

**Configuration Priority Chain**

The SDK resolves each setting in this order (highest priority first):

| Priority | Source | Example |
|----------|--------|---------|
| 1 | Explicit code parameters | `run_mcp_server_with_oauth(client_id="...")` |
| 2 | Environment variables | `AUTHSEC_AUTH_SERVICE_URL`, `AUTHSEC_SERVICES_URL` |
| 3 | `.authsec.json` in cwd | Created by `authsec init` |
| 4 | Hardcoded defaults | `https://dev.api.authsec.dev/...` |

This means you can use `authsec init` to set URLs once, then override individual settings with env vars for CI/CD or staging environments.

---

## Quick Start

```bash
# 1. Install the SDK (choose one)
pip install authsec-sdk
# pip install -e ../../../../sdk-authsec/packages/python-sdk

# 2. Configure (choose one)
authsec init                         # Path 1: interactive setup (creates .authsec.json)
# cp .env.example .env               # Path 2: manual .env (edit AUTHSEC_CLIENT_ID)

# 3. Run the server
python server.py
```

The server starts on `http://0.0.0.0:3005` (change the port with `AUTHSEC_PORT` env var).

---

## Authentication Flow (Step by Step)

### Step 1: Connect — tools are hidden

```bash
npx @modelcontextprotocol/inspector http://localhost:3005
```

You'll only see 5 OAuth tools:
- `oauth_start`, `oauth_authenticate`, `oauth_status`, `oauth_logout`, `oauth_user_info`

Your business tools (`search_notes`, `create_note`, etc.) are **completely invisible**.

### Step 2: Start OAuth

Call `oauth_start`. You'll get back a `session_id` and an `authorization_url`. Open the URL in your browser to authenticate.

### Step 3: Complete authentication

After logging in, call `oauth_authenticate` with the `session_id` and the JWT token from the OAuth flow.

### Step 4: Tools appear based on your permissions

Now call `tools/list` again. You'll see only the tools your roles/scopes permit:
- A user with `read` scope sees `search_notes`
- A user with `write` scope also sees `create_note`
- An `admin` also sees `delete_note`
- An `admin` with `audit` scope sees everything including `list_users`

### Step 5: User context is injected automatically

When you call a protected tool, the SDK injects `_user_info` into the arguments:

```python
@protected_by_AuthSec("create_note", scopes=["write"])
async def create_note(arguments: dict) -> list:
    user_email = arguments["_user_info"]["email"]      # "jane@acme.com"
    user_roles = arguments["_user_info"]["roles"]      # ["admin", "user"]
    tenant_id  = arguments["_user_info"]["tenant_id"]  # "acme-corp"
    ...
```

This means every action is tied to an identity — perfect for audit trails.

---

## How `@protected_by_AuthSec` Works

The decorator does several things:

1. **Registers RBAC metadata** — stores the `roles`, `scopes`, `description`, and `inputSchema` on the function as attributes
2. **Wraps the function** — on every call, the wrapper:
   - Sends the user's session to the AuthSec auth service for validation
   - Checks if the user's JWT claims satisfy the RBAC rules
   - If denied: returns a JSON error (`"RBAC denied: missing required roles"`)
   - If allowed: injects `_user_info` into `arguments` and calls your original function
3. **Discovery** — `run_mcp_server_with_oauth()` scans your module with `inspect.getmembers()` to find all decorated functions and sends their metadata to the SDK Manager

## How `run_mcp_server_with_oauth()` Works

```python
run_mcp_server_with_oauth(
    user_module=sys.modules[__name__],   # module to scan for @protected tools
    client_id=CLIENT_ID,                 # from app.authsec.ai dashboard
    app_name=APP_NAME,                   # display name for the server
    host="0.0.0.0",                      # bind address
    port=3005,                           # listen port
)
```

This function:
- Calls `configure_auth()` with your `client_id` (handles env var / `.authsec.json` / default fallback)
- Creates an `MCPServer` instance (FastAPI-based, speaks MCP JSON-RPC)
- Calls `server.set_user_module()` to discover your decorated tools
- Starts `uvicorn` to serve the MCP endpoint
- Adds `oauth_start`, `oauth_authenticate`, `oauth_status`, `oauth_logout`, `oauth_user_info` tools automatically

---

## File Structure

```
protected/
├── server.py          # @protected_by_AuthSec decorators + run_mcp_server_with_oauth
├── tools.py           # Identical to ../vanilla/tools.py — same business logic
├── requirements.txt   # authsec-sdk>=4.0.0
├── .env.example       # AUTHSEC_CLIENT_ID, AUTHSEC_APP_NAME, AUTHSEC_PORT, KB_DB_PATH
└── README.md          # This file
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AUTHSEC_CLIENT_ID` | Yes | — | Your client UUID from [app.authsec.ai](https://app.authsec.ai) |
| `AUTHSEC_APP_NAME` | No | `Team Knowledge Base (Protected)` | Display name for the MCP server |
| `AUTHSEC_PORT` | No | `3005` | Port to listen on |
| `KB_DB_PATH` | No | `knowledge_base.db` | SQLite database file path |
| `AUTHSEC_AUTH_SERVICE_URL` | No | `https://dev.api.authsec.dev/authsec/sdkmgr/mcp-auth` | Override auth service endpoint |
| `AUTHSEC_SERVICES_URL` | No | `https://dev.api.authsec.dev/authsec/sdkmgr/services` | Override services endpoint |

---

## Compare With

See [`../vanilla/`](../vanilla/) for the same server with **zero authentication** — all tools public, no identity, no RBAC.
