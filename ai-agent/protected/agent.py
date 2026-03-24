"""
Protected AI Agent — AuthSec Delegation SDK.

Demonstrates secure agent behavior:
  - Agent pulls a scoped delegation token before acting
  - Permission checks gate every action
  - Auto-refresh keeps the token valid
  - decode_token_claims() provides a full audit trail

Run:
    pip install -r requirements.txt   # or: pip install -e ../../../sdk-authsec/packages/python-sdk
    cp .env.example .env              # fill in real values
    python agent.py
"""

import asyncio
import os
import json
from authsec_sdk import DelegationClient, DelegationTokenNotFound, DelegationError

CLIENT_ID = os.environ.get("AUTHSEC_CLIENT_ID", "your-agent-client-id-here")
USERFLOW_URL = os.environ.get("AUTHSEC_USERFLOW_URL", "https://dev.api.authsec.dev/authsec/uflow")
TARGET_API = os.environ.get("TARGET_API_URL", "https://jsonplaceholder.typicode.com")


async def main():
    print("=" * 60)
    print("  PROTECTED AI AGENT — AuthSec Delegation")
    print("=" * 60)
    print()

    # -----------------------------------------------------------------------
    # 1. Initialize the delegation client
    # -----------------------------------------------------------------------
    client = DelegationClient(
        client_id=CLIENT_ID,
        userflow_url=USERFLOW_URL,
    )
    print(f"[init] DelegationClient created: {client}")

    # -----------------------------------------------------------------------
    # 2. Pull the delegation token
    # -----------------------------------------------------------------------
    print()
    print("[1] Pulling delegation token...")
    try:
        token_info = await client.pull_token()
        print(f"    Token pulled successfully!")
        print(f"    SPIFFE ID : {token_info.get('spiffe_id', 'N/A')}")
        print(f"    Permissions: {token_info.get('permissions', [])}")
        print(f"    Expires in : {client.expires_in_seconds}s")
    except DelegationTokenNotFound:
        print("    ERROR: No delegation token found for this client.")
        print()
        print("    To fix this:")
        print("    1. Log into the AuthSec Dashboard (https://app.authsec.ai)")
        print("    2. Navigate to Delegation > AI Agents")
        print(f"    3. Delegate a token to client_id: {CLIENT_ID}")
        print("    4. Re-run this agent")
        return
    except DelegationError as e:
        print(f"    ERROR: {e}")
        return

    # -----------------------------------------------------------------------
    # 3. Inspect token claims (audit trail)
    # -----------------------------------------------------------------------
    print()
    print("[2] Token claims (audit trail):")
    claims = client.decode_token_claims()
    for key in ("sub", "tenant_id", "permissions", "aud", "exp"):
        if key in claims:
            print(f"    {key}: {claims[key]}")

    # -----------------------------------------------------------------------
    # 4. Permission-gated actions
    # -----------------------------------------------------------------------
    print()
    print("[3] Permission-gated API calls:")

    # Read action
    if client.has_permission("posts:read"):
        print("    [posts:read] Fetching posts...")
        data = await client.request_json("GET", f"{TARGET_API}/posts?_limit=3")
        if isinstance(data, list):
            for p in data[:3]:
                print(f"      - #{p['id']}: {p['title'][:50]}")
        else:
            print(f"      Response: {json.dumps(data)[:100]}")
    else:
        print("    [posts:read] SKIPPED — permission not granted.")

    # Write action
    if client.has_permission("posts:write"):
        print("    [posts:write] Creating a post...")
        created = await client.request_json(
            "POST",
            f"{TARGET_API}/posts",
            json_body={"title": "Delegated Post", "body": "Created by a trusted agent.", "userId": 1},
        )
        print(f"      Created post #{created.get('id')}: {created.get('title')}")
    else:
        print("    [posts:write] SKIPPED — permission not granted.")

    # Admin action
    if client.has_permission("posts:delete"):
        print("    [posts:delete] Deleting post #1...")
        deleted = await client.request_json("DELETE", f"{TARGET_API}/posts/1")
        print(f"      Deleted: {deleted}")
    else:
        print("    [posts:delete] SKIPPED — permission not granted (admin only).")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print()
    print("=" * 60)
    print("  SECURITY BENEFITS:")
    print(f"  - Identity: agent authenticated as {claims.get('sub', CLIENT_ID[:12] + '...')}")
    print(f"  - Scoped: only {len(client.permissions)} permission(s) granted")
    print(f"  - Auto-refresh: token expires in {client.expires_in_seconds}s, auto-renews")
    print(f"  - Audit trail: every call carries JWT with tenant_id={claims.get('tenant_id', 'N/A')}")
    print()
    print("  Compare with: ai-agent/vanilla/agent.py")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
