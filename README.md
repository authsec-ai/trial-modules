# AuthSec SDK — Testing & Demos

Side-by-side demonstrations showing the security problem (unprotected AI tools) and the solution ([AuthSec SDK](https://github.com/authsec-ai/sdk-authsec)).

Run the **vanilla** demos to see how easy it is to exploit unprotected MCP servers and AI agents. Then run the **protected** demos to see how AuthSec locks everything down with OAuth 2.0, RBAC, and delegation tokens — without rewriting your business logic.

---

## Prerequisites

- **Python 3.10+**
- **An AuthSec account** (for protected demos only) — sign up free at [app.authsec.ai](https://app.authsec.ai)

---

## Demos at a Glance

| Demo | Path | What It Shows |
|------|------|---------------|
| BreachBox MCP (Docker, VM) | [`breachbox-mcp/`](breachbox-mcp/) | The remote-infrastructure story: the same VM-impacting MCP tools running as vanilla vs AuthSec-protected |
| MCP Server (Vanilla) | [`mcp-server/vanilla/`](mcp-server/vanilla/) | The problem: every tool is public — anyone can delete notes, read confidential data |
| MCP Server (Protected) | [`mcp-server/protected/`](mcp-server/protected/) | The fix: tools are hidden until OAuth login, then gated by RBAC roles & scopes |
| AI Agent (Vanilla) | [`ai-agent/vanilla/`](ai-agent/vanilla/) | The problem: agent has no identity, shared credentials, zero audit trail |
| AI Agent (Protected) | [`ai-agent/protected/`](ai-agent/protected/) | The fix: scoped delegation tokens, permission checks before every action |

---

## Installing the AuthSec SDK

The protected demos need the `authsec-sdk` package. You have two options — the import (`from authsec_sdk import ...`) is **identical** either way.

### Option A: Install from PyPI (recommended for trying it out)

```bash
pip install authsec-sdk
```

### Option B: Install from source (recommended for contributors / local dev)

```bash
# Clone the SDK repo
git clone https://github.com/authsec-ai/sdk-authsec.git

# Install in editable mode (from any demo folder)
pip install -e /path/to/sdk-authsec/packages/python-sdk
```

If the testing folder and the SDK repo live side by side on disk (e.g. both under `~/projects/`), the relative path from a demo folder looks like:

```bash
# From mcp-server/protected/ or mcp-server/vanilla/
pip install -e ../../../../sdk-authsec/packages/python-sdk

# From ai-agent/protected/ or ai-agent/vanilla/
pip install -e ../../../../sdk-authsec/packages/python-sdk
```

---

## Getting Your AuthSec Client ID

Every protected demo needs a `client_id`. Here's how to get one:

1. **Sign up** at [app.authsec.ai](https://app.authsec.ai) (free)
2. **Create an application** — choose "MCP Server" as the app type
3. **Copy the Client ID** from the application settings page — it's a UUID like `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
4. **Configure roles & scopes** — go to RBAC settings in your tenant and add:
   - Roles: `admin`, `user` (or whatever your team needs)
   - Scopes: `read`, `write`, `audit`
5. **Assign roles to users** — in the Users section, map each user to their roles and scopes

---

## Configuring the SDK: Two Paths

Once you have a `client_id`, there are two ways to configure the SDK. Both result in the same behavior — choose whichever you prefer.

### Path 1: `authsec init` (recommended — interactive setup)

After installing the SDK, run the built-in CLI:

```bash
authsec init
```

This launches an interactive prompt:

```
AuthSec SDK — interactive setup

Use default AuthSec URLs or custom? (default/custom) [default]: default
client_id (required): a1b2c3d4-e5f6-7890-abcd-ef1234567890

Config saved to /path/to/your/project/.authsec.json
```

It creates a `.authsec.json` file in your current directory:

```json
{
  "client_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "auth_service_url": "https://dev.api.authsec.dev/authsec/sdkmgr/mcp-auth",
  "services_base_url": "https://dev.api.authsec.dev/authsec/sdkmgr/services",
  "ciba_base_url": "https://dev.api.authsec.dev"
}
```

The SDK **automatically reads `.authsec.json`** from the current working directory at startup. You don't need to pass URLs or client IDs in code — it just works.

If you choose "custom" instead of "default", the CLI prompts you for each URL individually, letting you point at a self-hosted or staging AuthSec instance.

To verify your saved config at any time:

```bash
authsec config show
```

### Path 2: Manual `.env` file + code parameters

If you prefer explicit control, skip `authsec init` and configure everything via environment variables and code:

```bash
cp .env.example .env
# Edit .env with your values:
#   AUTHSEC_CLIENT_ID=a1b2c3d4-e5f6-7890-abcd-ef1234567890
#   AUTHSEC_APP_NAME=My Server
#   AUTHSEC_PORT=3005
```

Then in your code, pass the `client_id` directly:

```python
run_mcp_server_with_oauth(
    user_module=sys.modules[__name__],
    client_id=os.environ["AUTHSEC_CLIENT_ID"],
    app_name="My Server",
)
```

### Configuration Priority Chain

The SDK resolves configuration in this order (highest priority first):

| Priority | Source | Example |
|----------|--------|---------|
| 1 | Explicit code parameters | `run_mcp_server_with_oauth(client_id="...", ...)` |
| 2 | Environment variables | `AUTHSEC_AUTH_SERVICE_URL`, `AUTHSEC_SERVICES_URL` |
| 3 | `.authsec.json` in cwd | Created by `authsec init` |
| 4 | Hardcoded defaults | `https://dev.api.authsec.dev/...` |

This means: if you run `authsec init` to set URLs, but also set `AUTHSEC_AUTH_SERVICE_URL` as an env var, the env var wins. And if you pass a URL directly in code, that wins over everything.

---

## Quick Start

### 1. Vanilla demos (no AuthSec account needed)

These run immediately — zero setup:

```bash
# MCP Server — all tools are public, anyone can do anything
cd mcp-server/vanilla
pip install -r requirements.txt
python server.py
# Test: npx @modelcontextprotocol/inspector http://localhost:3000

# AI Agent — raw HTTP calls, no identity
cd ai-agent/vanilla
pip install -r requirements.txt
python agent.py
```

### 2. Protected demos (requires AuthSec account + client_id)

```bash
# MCP Server — tools hidden until OAuth, gated by RBAC
cd mcp-server/protected
pip install authsec-sdk              # Option A: from PyPI
# pip install -e ../../../../sdk-authsec/packages/python-sdk  # Option B: from source

# Configure (choose one):
authsec init                         # Path 1: interactive setup (creates .authsec.json)
# cp .env.example .env               # Path 2: manual .env (edit AUTHSEC_CLIENT_ID)

python server.py

# AI Agent — delegation tokens, permission-gated actions
cd ai-agent/protected
pip install authsec-sdk              # Option A: from PyPI
# pip install -e ../../../../sdk-authsec/packages/python-sdk  # Option B: from source

# Configure (choose one):
authsec init                         # Path 1: interactive setup
# cp .env.example .env               # Path 2: manual .env

python agent.py
```

---

## How the SDK Works (The Education Part)

### Protecting MCP Server Tools

AuthSec uses two main pieces to secure an MCP server:

**1. The `@protected_by_AuthSec` decorator** — wraps each tool function with authentication + RBAC:

```python
from authsec_sdk import protected_by_AuthSec

@protected_by_AuthSec(
    "delete_note",           # tool name (shown to MCP clients)
    roles=["admin"],         # only users with the "admin" role can call this
    description="Delete a note by ID",
    inputSchema={...},       # MCP-compliant JSON Schema for the tool's inputs
)
async def delete_note(arguments: dict) -> list:
    # arguments["_user_info"] is auto-injected by the SDK after auth:
    #   {"email": "jane@acme.com", "roles": ["admin"], "tenant_id": "acme-corp", ...}
    user = arguments["_user_info"]["email"]
    ...
```

What this decorator does under the hood:
- **Before auth**: the tool is completely hidden from the MCP `tools/list` response
- **During auth**: the SDK checks the user's JWT claims against the RBAC rules you set
- **After auth**: only tools the user is permitted to use become visible and callable
- **On every call**: the SDK re-validates the session and injects `_user_info` into `arguments`

**2. `run_mcp_server_with_oauth()`** — the entry point that wires everything together:

```python
from authsec_sdk import run_mcp_server_with_oauth
import sys

run_mcp_server_with_oauth(
    user_module=sys.modules[__name__],   # the module containing your @protected tools
    client_id="your-client-id",          # from app.authsec.ai
    app_name="My Server",
    host="0.0.0.0",
    port=3005,
)
```

This function:
- Discovers all `@protected_by_AuthSec`-decorated functions in your module
- Registers them with the AuthSec SDK Manager (the hosted auth service)
- Starts a FastAPI server that speaks the MCP JSON-RPC protocol
- Automatically adds OAuth tools (`oauth_start`, `oauth_authenticate`, `oauth_status`, `oauth_logout`, `oauth_user_info`)
- Handles session management, token validation, and RBAC checks for you

### RBAC Rules — What You Can Control

| Parameter | Example | Meaning |
|-----------|---------|---------|
| `roles=["admin"]` | Only admins | User's JWT must include this role |
| `scopes=["read", "write"]` | Read or write access | User needs at least one of these scopes |
| `roles=["admin"], scopes=["audit"], require_all=True` | Admin AND audit | User must satisfy ALL conditions |
| *(no RBAC params)* | Any authenticated user | Just being logged in is enough |

### Protecting AI Agents with Delegation

For agents that call external APIs, AuthSec uses the `DelegationClient`:

```python
from authsec_sdk import DelegationClient

client = DelegationClient(
    client_id="your-agent-client-id",
    userflow_url="https://dev.api.authsec.dev/authsec/uflow",
)

# 1. Pull the delegation token (admin must have delegated it first)
token_info = await client.pull_token()

# 2. Check permissions before acting
if client.has_permission("posts:read"):
    data = await client.request_json("GET", "https://api.example.com/posts")

# 3. Inspect claims for audit trail
claims = client.decode_token_claims()
print(claims["sub"], claims["tenant_id"], claims["permissions"])
```

Key methods:
| Method | What It Does |
|--------|-------------|
| `pull_token()` | Fetches the delegation JWT from the AuthSec service |
| `has_permission("scope:action")` | Checks if the token includes a specific permission |
| `request_json(method, url)` | Makes an HTTP request with the JWT in the `Authorization` header |
| `decode_token_claims()` | Decodes the JWT payload for auditing (sub, tenant_id, permissions, exp) |
| `ensure_token()` | Like `pull_token()` but only refreshes if the current token is near expiry |

---

## Theme: Team Knowledge Base

All demos use a "Team Knowledge Base" — a simple scenario with natural access levels:

| Tool | What It Does | RBAC (Protected Only) |
|------|-------------|----------------------|
| `search_notes` | Full-text search across notes | `scopes=["read"]` |
| `create_note` | Create note with title, content, tags | `scopes=["write"]` |
| `delete_note` | Delete a note by ID | `roles=["admin"]` |
| `list_users` | View access audit log | `roles=["admin"], scopes=["audit"], require_all=True` |

The database is SQLite, seeded with 4 sample notes on first run (onboarding guide, API docs, confidential finance note, security playbook).

---

## Related

- [AuthSec SDK Repository](https://github.com/authsec-ai/sdk-authsec)
- [AuthSec Dashboard](https://app.authsec.ai)
- [Documentation & Blog](https://authsec.dev/blogs)
- [Support](mailto:support@authsec.dev)
