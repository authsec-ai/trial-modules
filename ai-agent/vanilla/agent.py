"""
Vanilla AI Agent — raw HTTP calls, NO delegation.

Demonstrates the security problem with unprotected agents:
  - No identity: the agent shares a single set of credentials (or none)
  - No scoping: it can call any endpoint the network allows
  - No audit trail: nobody knows which agent did what

Uses JSONPlaceholder as a safe, public REST API for demo purposes.

Run:
    pip install -r requirements.txt
    python agent.py
"""

import asyncio
import os
import json
import aiohttp

TARGET_API = os.environ.get("TARGET_API_URL", "https://jsonplaceholder.typicode.com")


async def fetch_posts() -> dict:
    """Fetch posts — no auth header, no identity."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{TARGET_API}/posts?_limit=5") as resp:
            posts = await resp.json()
            return {"posts": posts, "count": len(posts)}


async def create_post(title: str, body: str) -> dict:
    """Create a post — anyone can do this, no permission check."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{TARGET_API}/posts",
            json={"title": title, "body": body, "userId": 1},
        ) as resp:
            return await resp.json()


async def delete_post(post_id: int) -> dict:
    """Delete a post — no admin check, no confirmation."""
    async with aiohttp.ClientSession() as session:
        async with session.delete(f"{TARGET_API}/posts/{post_id}") as resp:
            return {"deleted": True, "post_id": post_id, "status": resp.status}


async def main():
    print("=" * 60)
    print("  VANILLA AI AGENT — NO DELEGATION")
    print("=" * 60)
    print()
    print("  WARNING: This agent has NO identity and NO permission checks.")
    print("  It uses shared/anonymous credentials for every request.")
    print()

    # 1. Fetch
    print("[1] Fetching posts (no auth)...")
    result = await fetch_posts()
    print(f"    Got {result['count']} posts")
    for p in result["posts"][:3]:
        print(f"    - #{p['id']}: {p['title'][:50]}")

    # 2. Create
    print()
    print("[2] Creating a post (no identity attached)...")
    created = await create_post("Agent Post", "Created by an anonymous agent with no audit trail.")
    print(f"    Created post #{created.get('id')}: {created.get('title')}")

    # 3. Delete
    print()
    print("[3] Deleting post #1 (no admin check)...")
    deleted = await delete_post(1)
    print(f"    Deleted: status={deleted['status']}")

    # Summary
    print()
    print("=" * 60)
    print("  SECURITY GAPS:")
    print("  - No identity: who made these requests? Unknown.")
    print("  - No scoping: agent can call ANY endpoint.")
    print("  - No audit trail: no record of agent actions.")
    print("  - Shared credentials: every agent instance is identical.")
    print()
    print("  Compare with: ai-agent/protected/agent.py")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
