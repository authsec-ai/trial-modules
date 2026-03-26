import html
import os
from typing import Any, Dict

import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse


CONTROL_API_URL = os.environ.get("BREACHBOX_CONTROL_API_URL", "http://breachbox-control-api:8080").rstrip("/")
CONTROL_TOKEN = os.environ.get("BREACHBOX_CONTROL_TOKEN", "")
REFRESH_SECONDS = int(os.environ.get("BREACHBOX_STATUS_REFRESH_SECONDS", "5"))
APP_NAME = os.environ.get("BREACHBOX_STATUS_APP_NAME", "BreachBox Status Board")

app = FastAPI(title=APP_NAME, version="1.0.0")


def _headers() -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if CONTROL_TOKEN:
        headers["X-BreachBox-Token"] = CONTROL_TOKEN
    return headers


def _load_state() -> Dict[str, Any]:
    response = requests.get(f"{CONTROL_API_URL}/state", headers=_headers(), timeout=10)
    response.raise_for_status()
    return response.json()


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}


@app.get("/api/state")
def api_state() -> JSONResponse:
    return JSONResponse(_load_state())


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    state = _load_state()
    exports_rows = "".join(
        f"<tr><td>{html.escape(item['name'])}</td><td>{'present' if item['exists'] else 'deleted'}</td><td>{item['size_bytes']}</td></tr>"
        for item in state.get("exports", [])
    )
    secret_rows = "".join(
        f"<tr><td>{html.escape(item['name'])}</td><td>{html.escape(item['preview'])}</td></tr>"
        for item in state.get("secrets", [])
    )
    audit_rows = "".join(
        "<tr>"
        f"<td>{html.escape(event.get('timestamp', ''))}</td>"
        f"<td>{html.escape(event.get('actor_identity', 'unknown'))}</td>"
        f"<td>{html.escape(event.get('auth_mode', 'unknown'))}</td>"
        f"<td>{html.escape(event.get('action', ''))}</td>"
        f"<td>{html.escape(event.get('status', ''))}</td>"
        "</tr>"
        for event in state.get("audit_tail", [])
    )
    worker = state.get("worker", {})
    worker_status = "RUNNING" if worker.get("running") else "STOPPED"
    worker_class = "good" if worker.get("running") else "bad"

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="{REFRESH_SECONDS}">
  <title>{html.escape(APP_NAME)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #0f172a;
      --muted: #475569;
      --bg: #f8fafc;
      --card: #ffffff;
      --line: #dbe4ee;
      --good: #14532d;
      --good-bg: #dcfce7;
      --bad: #7f1d1d;
      --bad-bg: #fee2e2;
      --accent: #0f766e;
    }}
    body {{
      margin: 0;
      font-family: Menlo, Monaco, monospace;
      background: radial-gradient(circle at top, #dff7f1, #f8fafc 38%);
      color: var(--ink);
    }}
    main {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 32px;
      letter-spacing: -0.03em;
    }}
    p {{
      color: var(--muted);
      margin: 0 0 20px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
    }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 700;
    }}
    .good {{
      background: var(--good-bg);
      color: var(--good);
    }}
    .bad {{
      background: var(--bad-bg);
      color: var(--bad);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
    }}
    th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}
    @media (max-width: 900px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(APP_NAME)}</h1>
    <p>Live state for the disposable VM demo. Refreshes every {REFRESH_SECONDS} seconds.</p>

    <section class="hero">
      <article class="card">
        <div class="badge {worker_class}">Worker {worker_status}</div>
        <h2>breachbox-worker</h2>
        <p>Enabled flag: <strong>{worker.get('enabled')}</strong></p>
      </article>
      <article class="card">
        <div class="badge {'good' if state.get('latest_actor_identity') != 'anonymous' else 'bad'}">
          Latest actor: {html.escape(state.get('latest_actor_identity', 'none'))}
        </div>
        <h2>Last action</h2>
        <p><strong>{html.escape(state.get('latest_action', 'none'))}</strong></p>
      </article>
      <article class="card">
        <div class="badge good">Status board</div>
        <h2>Exports</h2>
        <p>{len(state.get('exports', []))} tracked files</p>
      </article>
    </section>

    <section class="grid">
      <article class="card">
        <h2>Customer Exports</h2>
        <table>
          <thead><tr><th>Name</th><th>Status</th><th>Size</th></tr></thead>
          <tbody>{exports_rows}</tbody>
        </table>
      </article>
      <article class="card">
        <h2>Fake Secrets</h2>
        <table>
          <thead><tr><th>Name</th><th>Preview</th></tr></thead>
          <tbody>{secret_rows}</tbody>
        </table>
      </article>
    </section>

    <section class="card" style="margin-top: 16px;">
      <h2>Audit Tail</h2>
      <table>
        <thead><tr><th>Timestamp</th><th>Actor</th><th>Mode</th><th>Action</th><th>Status</th></tr></thead>
        <tbody>{audit_rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>"""
    return HTMLResponse(page)

