# Protected AI Agent — AuthSec Delegation SDK

The exact same AI agent as the [vanilla version](../vanilla/), now secured with the **AuthSec Delegation SDK**. The agent pulls a scoped delegation token before acting, checks permissions before every API call, and provides a full audit trail via JWT claims.

---

## What Changes vs. Vanilla

| Vanilla | Protected |
|---------|-----------|
| `import aiohttp` | `from authsec_sdk import DelegationClient` |
| Raw `session.get(url)` | `client.request_json("GET", url)` — JWT attached automatically |
| No permission checks | `client.has_permission("posts:read")` before every action |
| Anonymous — no identity | `client.decode_token_claims()` — full audit: sub, tenant_id, permissions |
| Credentials shared / hardcoded | Scoped token pulled from AuthSec, auto-refreshed before expiry |

---

## Prerequisites

### 1. Get your AuthSec Client ID

The agent needs a `client_id` to pull delegation tokens:

1. **Sign up** at [app.authsec.ai](https://app.authsec.ai) (free)
2. **Register an AI Agent client** — go to Delegation > AI Agents in the dashboard
3. **Copy the Client ID** — it's a UUID like `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
4. **Delegate a token** — an admin must delegate a token to this `client_id` with the desired permissions (e.g. `posts:read`, `posts:write`, `posts:delete`)

### 2. Install the AuthSec SDK

You have two options — the import `from authsec_sdk import DelegationClient` works identically either way.

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

There are two ways to configure. Both work identically at runtime.

**Path 1: `authsec init` (recommended — interactive setup)**

```bash
cd ai-agent/protected
authsec init
```

```
AuthSec SDK — interactive setup

Use default AuthSec URLs or custom? (default/custom) [default]: default
client_id (required): a1b2c3d4-e5f6-7890-abcd-ef1234567890

Config saved to /path/to/ai-agent/protected/.authsec.json
```

This creates `.authsec.json` in the current directory. The SDK reads it automatically — you get the default AuthSec URLs without hardcoding anything. Choose "custom" if you're pointing at a self-hosted or staging instance.

Verify your config at any time:
```bash
authsec config show
```

**Path 2: Manual `.env` file**

```bash
cp .env.example .env
# Edit .env:
#   AUTHSEC_CLIENT_ID=your-agent-client-id-here
#   AUTHSEC_USERFLOW_URL=https://dev.api.authsec.dev/authsec/uflow
```

The `agent.py` reads these values from the environment. The `AUTHSEC_USERFLOW_URL` defaults to the hosted AuthSec user-flow service if not set.

**Configuration Priority Chain**

| Priority | Source | Example |
|----------|--------|---------|
| 1 | Explicit code parameters | `DelegationClient(client_id="...", userflow_url="...")` |
| 2 | Environment variables | `AUTHSEC_CLIENT_ID`, `AUTHSEC_USERFLOW_URL` |
| 3 | `.authsec.json` in cwd | Created by `authsec init` |
| 4 | Hardcoded defaults | `https://dev.api.authsec.dev/...` |

---

## Quick Start

```bash
# 1. Install the SDK (choose one)
pip install authsec-sdk
# pip install -e ../../../../sdk-authsec/packages/python-sdk

# 2. Configure (choose one)
authsec init                         # Path 1: interactive setup (creates .authsec.json)
# cp .env.example .env               # Path 2: manual .env (edit AUTHSEC_CLIENT_ID)

# 3. Run the agent
python agent.py
```

---

## What Happens When You Run It

### Step 1: Initialize the DelegationClient

```python
from authsec_sdk import DelegationClient

client = DelegationClient(
    client_id="your-agent-client-id",                        # from app.authsec.ai
    userflow_url="https://dev.api.authsec.dev/authsec/uflow", # AuthSec user-flow service
)
```

The client is created but **no token is fetched yet** — it's lazy.

### Step 2: Pull the delegation token

```python
token_info = await client.pull_token()
# Returns: {token, spiffe_id, permissions, audience, expires_at, ttl_seconds, ...}
```

This calls the AuthSec user-flow service. An **admin must have delegated a token** to this `client_id` beforehand (via the dashboard). If no token exists, you get a `DelegationTokenNotFound` error with setup instructions.

### Step 3: Check permissions before acting

```python
if client.has_permission("posts:read"):
    data = await client.request_json("GET", f"{TARGET_API}/posts")
else:
    print("SKIPPED — posts:read not granted")

if client.has_permission("posts:delete"):
    await client.request_json("DELETE", f"{TARGET_API}/posts/1")
else:
    print("SKIPPED — posts:delete not granted (admin only)")
```

The agent only does what the token allows. No `has_permission()` match = no action.

### Step 4: Audit trail via JWT claims

```python
claims = client.decode_token_claims()
# {
#   "sub": "agent-abc123",
#   "tenant_id": "acme-corp",
#   "permissions": ["posts:read", "posts:write"],
#   "aud": "https://api.example.com",
#   "exp": 1700000000
# }
```

Every action is traceable: who (sub), which tenant (tenant_id), what permissions, when (exp).

---

## How `DelegationClient` Works

| Method | What It Does |
|--------|-------------|
| `pull_token()` | Fetches the delegation JWT from AuthSec. Caches it locally. |
| `ensure_token()` | Like `pull_token()`, but only refreshes if the token is near expiry. |
| `has_permission("scope:action")` | Returns `True` if the token includes this permission string. |
| `has_any_permission("a:read", "a:write")` | Returns `True` if any of the permissions match. |
| `has_all_permissions("a:read", "a:write")` | Returns `True` only if all permissions match. |
| `request_json(method, url)` | Makes an HTTP request with `Authorization: Bearer <token>`. Auto-refreshes on 401. |
| `request(method, url)` | Same as above but returns the raw `aiohttp.ClientResponse`. |
| `decode_token_claims()` | Decodes the JWT payload (without verification) for audit/inspection. |
| `get_auth_header()` | Returns `{"Authorization": "Bearer <token>"}` for manual use. |

### Auto-refresh

When `auto_refresh=True` (the default), the client:
- Re-pulls the token when it's within `refresh_buffer_seconds` (default: 300s) of expiry
- Retries once on HTTP 401 responses with a fresh token

### Error Handling

```python
from authsec_sdk import DelegationTokenNotFound, DelegationError

try:
    await client.pull_token()
except DelegationTokenNotFound:
    print("No token found — ask an admin to delegate one to this client_id")
except DelegationError as e:
    print(f"Something went wrong: {e}")
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AUTHSEC_CLIENT_ID` | Yes | — | Your agent's client UUID from [app.authsec.ai](https://app.authsec.ai) |
| `AUTHSEC_USERFLOW_URL` | No | `https://dev.api.authsec.dev/authsec/uflow` | AuthSec user-flow service URL |
| `TARGET_API_URL` | No | `https://jsonplaceholder.typicode.com` | The API the agent calls |

---

## File Structure

```
protected/
├── agent.py           # DelegationClient — pull_token, has_permission, request_json
├── requirements.txt   # authsec-sdk>=4.0.0
├── .env.example       # AUTHSEC_CLIENT_ID, AUTHSEC_USERFLOW_URL, TARGET_API_URL
└── README.md          # This file
```

---

## Compare With

See [`../vanilla/`](../vanilla/) for the same agent with **zero security** — raw HTTP calls, no identity, no permission checks, no audit trail.
