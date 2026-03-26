import json
import os
import socket
import time
from pathlib import Path


DATA_ROOT = Path(os.environ.get("BREACHBOX_DATA_ROOT", "/srv/breachbox-demo"))
RUNTIME_DIR = DATA_ROOT / "runtime"
HEARTBEAT_FILE = RUNTIME_DIR / "worker-heartbeat.json"
ENABLED_FILE = RUNTIME_DIR / "worker-enabled"
LOOP_SECONDS = float(os.environ.get("BREACHBOX_WORKER_LOOP_SECONDS", "2"))


def worker_enabled() -> bool:
    if not ENABLED_FILE.exists():
        return False
    return ENABLED_FILE.read_text().strip() == "1"


def write_heartbeat() -> None:
    payload = {
        "status": "running",
        "hostname": socket.gethostname(),
        "timestamp_epoch": time.time(),
    }
    HEARTBEAT_FILE.write_text(json.dumps(payload, sort_keys=True))


def main() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        if not worker_enabled():
            print("breachbox-worker: disable flag detected, exiting.")
            break
        write_heartbeat()
        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    main()

