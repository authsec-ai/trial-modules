import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


DATA_ROOT = Path(os.environ.get("BREACHBOX_DATA_ROOT", "/srv/breachbox-demo"))
EXPORT_DIR = DATA_ROOT / "customer-exports"
SECRETS_DIR = DATA_ROOT / "fake-secrets"
AUDIT_DIR = DATA_ROOT / "audit"
RUNTIME_DIR = DATA_ROOT / "runtime"
CONTROL_TOKEN = os.environ.get("BREACHBOX_CONTROL_TOKEN", "")
HEARTBEAT_STALE_SECONDS = int(os.environ.get("BREACHBOX_HEARTBEAT_STALE_SECONDS", "8"))


class AuditEvent(BaseModel):
    timestamp: str
    action: str
    actor_identity: str
    auth_mode: str
    roles: List[str] = Field(default_factory=list)
    tenant_id: Optional[str] = None
    status: str = "success"
    details: Dict[str, Any] = Field(default_factory=dict)


app = FastAPI(title="BreachBox Control API", version="1.0.0")


def _ensure_layout() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def _require_token(header_token: Optional[str]) -> None:
    if CONTROL_TOKEN and header_token != CONTROL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid control token")


def _worker_enabled_file() -> Path:
    return RUNTIME_DIR / "worker-enabled"


def _worker_heartbeat_file() -> Path:
    return RUNTIME_DIR / "worker-heartbeat.json"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _worker_enabled() -> bool:
    file_path = _worker_enabled_file()
    if not file_path.exists():
        return False
    return file_path.read_text().strip() == "1"


def _worker_running() -> bool:
    heartbeat = _load_json(_worker_heartbeat_file())
    if not heartbeat:
        return False
    timestamp = float(heartbeat.get("timestamp_epoch", 0))
    if not timestamp:
        return False
    return (time.time() - timestamp) <= HEARTBEAT_STALE_SECONDS


def _secret_preview(secret_name: str) -> str:
    secret_path = SECRETS_DIR / secret_name
    if not secret_path.exists():
        return "missing"
    value = secret_path.read_text().strip()
    if len(value) <= 8:
        return value
    return f"{value[:6]}..."


def _list_exports() -> List[Dict[str, Any]]:
    return [
        {
            "name": path.name,
            "exists": path.exists(),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(EXPORT_DIR.glob("*"))
        if path.is_file()
    ]


def _list_secrets() -> List[Dict[str, Any]]:
    return [
        {
            "name": path.name,
            "exists": path.exists(),
            "preview": _secret_preview(path.name),
        }
        for path in sorted(SECRETS_DIR.glob("*"))
        if path.is_file()
    ]


def _read_audit(limit: int = 20) -> List[Dict[str, Any]]:
    audit_file = AUDIT_DIR / "events.jsonl"
    if not audit_file.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in audit_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows[-limit:][::-1]


def _append_audit(event: Dict[str, Any]) -> None:
    audit_file = AUDIT_DIR / "events.jsonl"
    with audit_file.open("a") as handle:
        handle.write(json.dumps(event, sort_keys=True))
        handle.write("\n")


def _state_payload() -> Dict[str, Any]:
    heartbeat = _load_json(_worker_heartbeat_file())
    audit_tail = _read_audit(limit=15)
    latest = audit_tail[0] if audit_tail else {}
    return {
        "status": "ok",
        "exports": _list_exports(),
        "secrets": _list_secrets(),
        "worker": {
            "enabled": _worker_enabled(),
            "running": _worker_running(),
            "heartbeat": heartbeat,
        },
        "latest_actor_identity": latest.get("actor_identity", "none"),
        "latest_action": latest.get("action", "none"),
        "audit_tail": audit_tail,
    }


@app.on_event("startup")
def on_startup() -> None:
    _ensure_layout()


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "data_root": str(DATA_ROOT),
        "worker_running": _worker_running(),
    }


@app.get("/state")
def state(x_breachbox_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _require_token(x_breachbox_token)
    return _state_payload()


@app.get("/audit")
def audit(limit: int = 20, x_breachbox_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _require_token(x_breachbox_token)
    return {"events": _read_audit(limit=limit)}


@app.get("/secrets/{secret_name}")
def read_secret(secret_name: str, x_breachbox_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _require_token(x_breachbox_token)
    secret_path = SECRETS_DIR / secret_name
    if not secret_path.exists():
        raise HTTPException(status_code=404, detail=f"secret {secret_name} not found")
    return {
        "secret_name": secret_name,
        "content": secret_path.read_text().strip(),
    }


@app.post("/exports/{export_name}/delete")
def delete_export(export_name: str, x_breachbox_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _require_token(x_breachbox_token)
    export_path = EXPORT_DIR / export_name
    if not export_path.exists():
        return {"deleted": False, "export_name": export_name, "message": "already missing"}
    export_path.unlink()
    return {"deleted": True, "export_name": export_name}


@app.post("/worker/stop")
def stop_worker(x_breachbox_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _require_token(x_breachbox_token)
    _worker_enabled_file().write_text("0")
    return {"stopped": True, "message": "worker disable flag set"}


@app.post("/audit")
def append_audit(event: AuditEvent, x_breachbox_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _require_token(x_breachbox_token)
    _append_audit(event.model_dump())
    return {"stored": True}

