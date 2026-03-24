# Vanilla AI Agent — No Delegation (No Auth)

An AI agent that makes raw HTTP calls to a REST API with **no identity, no permission checks, and no audit trail**. This is the "before" demo — run it to see the security gaps that arise when agents operate without AuthSec.

---

## The Security Problem

| Gap | What Happens |
|-----|-------------|
| **No identity** | Who made the request? Unknown. The API sees an anonymous caller. |
| **No scoping** | The agent can call ANY endpoint — read, write, delete — with no restrictions. |
| **No audit trail** | There's no record of which agent did what, or when. |
| **Shared credentials** | Every agent instance uses the same (or no) credentials. If one is compromised, all are. |

This demo uses [JSONPlaceholder](https://jsonplaceholder.typicode.com) as a safe, public API. In a real scenario, these gaps would mean agents can access production databases, delete resources, and leak sensitive data — all without accountability.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> `requirements.txt` only needs `aiohttp>=3.9.0` — no AuthSec SDK required for the vanilla demo.

### 2. Run the agent

```bash
python agent.py
```

The agent will:
1. **Fetch posts** — no auth header, no identity
2. **Create a post** — anonymous, no permission check
3. **Delete a post** — no admin role required, no confirmation

---

## What the Code Looks Like

```python
import aiohttp

async def fetch_posts():
    """No auth header, no identity — just a raw GET."""
    async with aiohttp.ClientSession() as session:
        async with session.get("https://jsonplaceholder.typicode.com/posts") as resp:
            return await resp.json()

async def delete_post(post_id: int):
    """No admin check — anyone (or anything) can delete."""
    async with aiohttp.ClientSession() as session:
        async with session.delete(f"https://jsonplaceholder.typicode.com/posts/{post_id}") as resp:
            return {"deleted": True, "status": resp.status}
```

There's no `DelegationClient`, no `has_permission()`, no `pull_token()`. The agent just fires HTTP calls into the void.

---

## File Structure

```
vanilla/
├── agent.py           # Raw aiohttp calls — no auth, no delegation
├── requirements.txt   # aiohttp>=3.9.0
├── .env.example       # TARGET_API_URL
└── README.md          # This file
```

---

## The Fix

To see the same agent with proper delegation and permission checks, see [`../protected/`](../protected/).

The transition is three steps:

### 1. Install the SDK

```bash
# From PyPI
pip install authsec-sdk

# Or from source (clone the repo first)
git clone https://github.com/authsec-ai/sdk-authsec.git
pip install -e /path/to/sdk-authsec/packages/python-sdk
```

### 2. Configure your agent's client_id

Register an AI Agent client at [app.authsec.ai](https://app.authsec.ai) (Delegation > AI Agents), then delegate a token with the permissions you want. Then configure:

```bash
# Option A: interactive setup (creates .authsec.json — SDK reads it automatically)
authsec init

# Option B: manual .env file
cp .env.example .env   # edit AUTHSEC_CLIENT_ID, AUTHSEC_USERFLOW_URL
```

`authsec init` prompts for "default or custom URLs" and your `client_id`, then writes `.authsec.json`. The SDK reads this file automatically at startup.

### 3. Change the code

```python
# BEFORE (vanilla):
async with aiohttp.ClientSession() as session:
    async with session.get(url) as resp:
        data = await resp.json()

# AFTER (protected):
from authsec_sdk import DelegationClient

client = DelegationClient(client_id="...", userflow_url="...")
await client.pull_token()

if client.has_permission("posts:read"):
    data = await client.request_json("GET", url)
```

Key differences:
- Replace raw `aiohttp` calls with `DelegationClient.request_json()` — JWT attached automatically
- Gate every action with `client.has_permission("scope:action")` before executing
- Get a full audit trail from `client.decode_token_claims()` — sub, tenant_id, permissions, exp
- Auto-refresh keeps tokens valid without manual intervention
