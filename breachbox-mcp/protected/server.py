"""
Protected BreachBox MCP server.

Uses AuthSec OAuth and RBAC to hide or block high-risk VM operations.
"""

import json
import os
import sys

from authsec_sdk import mcp_tool, protected_by_AuthSec, run_mcp_server_with_oauth

from shared.breachbox_client import (
    BreachBoxClient,
    default_export_name,
    default_secret_name,
    make_actor,
    record_action,
)


CLIENT_ID = os.environ.get("AUTHSEC_CLIENT_ID", "your-client-id-here")
APP_NAME = os.environ.get("AUTHSEC_APP_NAME", "BreachBox Remote Operations (Protected)")
PORT = int(os.environ.get("AUTHSEC_PORT", "8001"))


def _client() -> BreachBoxClient:
    return BreachBoxClient()


def _payload(data: dict) -> list:
    return [{"type": "text", "text": json.dumps(data, indent=2)}]


@mcp_tool(
    name="authsec_demo_guide",
    description="Read this first. Explains how to log in, which personas exist, and what each permission can do in the protected BreachBox demo.",
    inputSchema={"type": "object", "properties": {}, "required": []},
)
async def authsec_demo_guide(arguments: dict) -> list:
    return _payload(
        {
            "app_name": APP_NAME,
            "client_id": CLIENT_ID,
            "login_flow": [
                "Call oauth_start.",
                "Complete browser login with the AuthSec user you want to demo.",
                "Call oauth_status to confirm the session is authenticated.",
                "Call oauth_user_info to verify the session contains the expected breachbox.* permissions.",
                "Use actual protected tool calls as the proof of authorization; do not rely only on tools/list.",
                "Before switching accounts, call oauth_logout.",
            ],
            "personas": {
                "viewer": ["breachbox.state:read", "breachbox.secret:read"],
                "operator": [
                    "breachbox.state:read",
                    "breachbox.secret:read",
                    "breachbox.export:delete",
                ],
                "admin": [
                    "breachbox.state:read",
                    "breachbox.secret:read",
                    "breachbox.export:delete",
                    "breachbox.worker:execute",
                    "breachbox.audit:read",
                ],
            },
            "tool_access": {
                "show_demo_state": ["breachbox.state:read"],
                "read_fake_secret": ["breachbox.secret:read"],
                "delete_customer_export": ["breachbox.export:delete"],
                "stop_demo_worker": ["breachbox.worker:execute"],
                "view_audit_events": ["breachbox.audit:read"],
            },
            "notes": [
                "If oauth_user_info shows scopes as null, login succeeded but RBAC will deny protected tools.",
                "This server currently exposes OAuth as MCP tools; some clients may not detect it as native auth automatically.",
                "Map your real AuthSec test accounts to the generic viewer/operator/admin personas outside this public guide.",
            ],
        }
    )


@protected_by_AuthSec(
    "show_demo_state",
    permissions=["breachbox.state:read"],
    description="Show the current remote demo state, including exports, secrets, worker health, and latest audit events.",
    inputSchema={"type": "object", "properties": {}, "required": []},
)
async def show_demo_state(arguments: dict) -> list:
    client = _client()
    actor = make_actor(arguments.get("_user_info"), auth_mode="protected")
    result = client.show_demo_state()
    record_action(client, actor, "show_demo_state", {"exports": len(result.get("exports", []))})
    return _payload(result)


@protected_by_AuthSec(
    "read_fake_secret",
    permissions=["breachbox.secret:read"],
    description="Read a fake but realistic secret from the remote VM demo volume.",
    inputSchema={
        "type": "object",
        "properties": {"secret_name": {"type": "string", "description": "Secret file name"}},
        "required": [],
    },
)
async def read_fake_secret(arguments: dict) -> list:
    secret_name = arguments.get("secret_name") or default_secret_name()
    client = _client()
    actor = make_actor(arguments.get("_user_info"), auth_mode="protected")
    result = client.read_fake_secret(secret_name)
    record_action(client, actor, "read_fake_secret", {"secret_name": secret_name})
    return _payload(result)


@protected_by_AuthSec(
    "delete_customer_export",
    permissions=["breachbox.export:delete"],
    description="Delete a customer export file from the remote VM demo volume.",
    inputSchema={
        "type": "object",
        "properties": {"export_name": {"type": "string", "description": "Export file name"}},
        "required": [],
    },
)
async def delete_customer_export(arguments: dict) -> list:
    export_name = arguments.get("export_name") or default_export_name()
    client = _client()
    actor = make_actor(arguments.get("_user_info"), auth_mode="protected")
    result = client.delete_customer_export(export_name)
    record_action(client, actor, "delete_customer_export", {"export_name": export_name, "deleted": result.get("deleted")})
    return _payload(result)


@protected_by_AuthSec(
    "stop_demo_worker",
    permissions=["breachbox.worker:execute"],
    description="Stop the demo worker container by flipping its control flag.",
    inputSchema={"type": "object", "properties": {}, "required": []},
)
async def stop_demo_worker(arguments: dict) -> list:
    client = _client()
    actor = make_actor(arguments.get("_user_info"), auth_mode="protected")
    result = client.stop_demo_worker()
    record_action(client, actor, "stop_demo_worker", {"stopped": result.get("stopped")})
    return _payload(result)


@protected_by_AuthSec(
    "view_audit_events",
    permissions=["breachbox.audit:read"],
    description="View the latest audit events for the remote demo environment.",
    inputSchema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "description": "Number of audit events to fetch"}},
        "required": [],
    },
)
async def view_audit_events(arguments: dict) -> list:
    limit = int(arguments.get("limit") or 20)
    client = _client()
    actor = make_actor(arguments.get("_user_info"), auth_mode="protected")
    result = client.view_audit_events(limit=limit)
    record_action(client, actor, "view_audit_events", {"limit": limit})
    return _payload(result)


if __name__ == "__main__":
    print("=" * 60)
    print("  BREACHBOX PROTECTED MCP")
    print("=" * 60)
    print("  Public endpoint is expected at https://protected.<PUBLIC_HOST>/mcp")
    print("  This demo relies on authsec-sdk>=4.1.2 for client-side hidden-tool behavior.")
    print("=" * 60)
    run_mcp_server_with_oauth(
        user_module=sys.modules[__name__],
        client_id=CLIENT_ID,
        app_name=APP_NAME,
        host="0.0.0.0",
        port=PORT,
    )
