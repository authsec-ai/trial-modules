import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests


class BreachBoxAPIError(RuntimeError):
    """Raised when the control API returns an unexpected response."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BreachBoxClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        control_token: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("BREACHBOX_CONTROL_API_URL", "http://localhost:8080")).rstrip("/")
        self.control_token = control_token or os.environ.get("BREACHBOX_CONTROL_TOKEN", "")
        self.timeout_seconds = int(timeout_seconds or os.environ.get("BREACHBOX_CONTROL_TIMEOUT_SECONDS", "10"))

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.control_token:
            headers["X-BreachBox-Token"] = self.control_token
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        merged_headers = self._headers()
        merged_headers.update(headers)
        response = requests.request(method=method, url=url, headers=merged_headers, timeout=self.timeout_seconds, **kwargs)
        try:
            payload = response.json()
        except Exception as exc:  # pragma: no cover - defensive path for demo reliability
            raise BreachBoxAPIError(f"Invalid JSON from control API {url}: {response.text[:200]}") from exc

        if response.status_code >= 400:
            raise BreachBoxAPIError(payload.get("detail") or payload.get("error") or f"HTTP {response.status_code}")
        return payload

    def show_demo_state(self) -> Dict[str, Any]:
        return self._request("GET", "/state")

    def read_fake_secret(self, secret_name: str) -> Dict[str, Any]:
        return self._request("GET", f"/secrets/{secret_name}")

    def delete_customer_export(self, export_name: str) -> Dict[str, Any]:
        return self._request("POST", f"/exports/{export_name}/delete")

    def stop_demo_worker(self) -> Dict[str, Any]:
        return self._request("POST", "/worker/stop")

    def view_audit_events(self, limit: int = 20) -> Dict[str, Any]:
        return self._request("GET", "/audit", params={"limit": limit})

    def log_audit(self, event: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/audit", json=event)


def default_export_name() -> str:
    return os.environ.get("BREACHBOX_PRIMARY_EXPORT", "acme-enterprise-export.csv")


def default_secret_name() -> str:
    return os.environ.get("BREACHBOX_PRIMARY_SECRET", "prod-db-root-token.txt")


def make_actor(user_info: Optional[Dict[str, Any]] = None, auth_mode: str = "vanilla") -> Dict[str, Any]:
    info = user_info or {}
    identity = (
        info.get("email")
        or info.get("email_id")
        or info.get("user_email")
        or info.get("user_id")
        or "anonymous"
    )
    return {
        "identity": str(identity),
        "auth_mode": auth_mode,
        "roles": list(info.get("roles") or []),
        "tenant_id": info.get("tenant_id"),
    }


def record_action(
    client: BreachBoxClient,
    actor: Dict[str, Any],
    action: str,
    details: Dict[str, Any],
    status: str = "success",
) -> None:
    try:
        client.log_audit(
            {
                "timestamp": utc_now_iso(),
                "action": action,
                "actor_identity": actor.get("identity", "anonymous"),
                "auth_mode": actor.get("auth_mode", "unknown"),
                "roles": actor.get("roles", []),
                "tenant_id": actor.get("tenant_id"),
                "status": status,
                "details": details,
            }
        )
    except Exception:
        # Audit failure should not block the live demo flow.
        return

