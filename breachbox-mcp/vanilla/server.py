"""
Vanilla BreachBox MCP server.

Every tool is exposed immediately and can impact the remote demo VM state.
"""

import os

from mcp.server.fastmcp import FastMCP

from shared.breachbox_client import (
    BreachBoxClient,
    default_export_name,
    default_secret_name,
    make_actor,
    record_action,
)


mcp = FastMCP("BreachBox Remote Operations (Vanilla)", json_response=True)


def _client() -> BreachBoxClient:
    return BreachBoxClient()


@mcp.tool()
def show_demo_state() -> dict:
    """Show the current remote demo state, including exports, secrets, worker health, and latest audit events."""
    client = _client()
    actor = make_actor(auth_mode="vanilla")
    result = client.show_demo_state()
    record_action(client, actor, "show_demo_state", {"exports": len(result.get("exports", []))})
    return result


@mcp.tool()
def read_fake_secret(secret_name: str = default_secret_name()) -> dict:
    """Read a fake but realistic secret from the remote VM demo volume."""
    client = _client()
    actor = make_actor(auth_mode="vanilla")
    result = client.read_fake_secret(secret_name)
    record_action(client, actor, "read_fake_secret", {"secret_name": secret_name})
    return result


@mcp.tool()
def delete_customer_export(export_name: str = default_export_name()) -> dict:
    """Delete a customer export file from the remote VM demo volume."""
    client = _client()
    actor = make_actor(auth_mode="vanilla")
    result = client.delete_customer_export(export_name)
    record_action(client, actor, "delete_customer_export", {"export_name": export_name, "deleted": result.get("deleted")})
    return result


@mcp.tool()
def stop_demo_worker() -> dict:
    """Stop the demo worker container by flipping its control flag."""
    client = _client()
    actor = make_actor(auth_mode="vanilla")
    result = client.stop_demo_worker()
    record_action(client, actor, "stop_demo_worker", {"stopped": result.get("stopped")})
    return result


@mcp.tool()
def view_audit_events(limit: int = 20) -> dict:
    """View the latest audit events for the remote demo environment."""
    client = _client()
    actor = make_actor(auth_mode="vanilla")
    result = client.view_audit_events(limit=limit)
    record_action(client, actor, "view_audit_events", {"limit": limit})
    return result


if __name__ == "__main__":
    port = int(os.environ.get("MCP_PORT", "8000"))
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port
    print("=" * 60)
    print("  BREACHBOX VANILLA MCP")
    print("=" * 60)
    print(f"  Streamable HTTP endpoint: http://0.0.0.0:{port}/mcp")
    print("  Every VM-impacting tool is public.")
    print("=" * 60)
    mcp.run(transport="streamable-http")

