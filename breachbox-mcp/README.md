# BreachBox MCP Demo

BreachBox is the Docker-first remote VM demo for AuthSec.

It is built to answer one specific question in a live demo:

What happens when an MCP client can reach a remote operations server that has dangerous tools?

The demo ships in two variants with identical business logic:

- `vanilla/`: every dangerous tool is immediately available
- `protected/`: the same tools are fronted by AuthSec OAuth and RBAC

The deployable artifact is the stack bundle in [`stack/`](/Users/pc/Desktop/authnull/trial-modules/breachbox-mcp/stack/README.md).

## Tool Story

- `show_demo_state`: inspect exports, secrets, worker health, and recent activity
- `read_fake_secret`: read a fake but realistic secret
- `delete_customer_export`: delete a customer export from the VM-backed demo volume
- `stop_demo_worker`: disable the demo worker
- `view_audit_events`: inspect recent audit history

## Runtime Layout

- `control-api/`: reads and mutates the bind-mounted demo state under `/srv/breachbox-demo`
- `status-ui/`: visible proof that the VM was impacted
- `worker/`: a disposable worker container that can be stopped during the demo
- `shared/`: common client and audit helpers
- `stack/`: Compose bundle, proxy config, bootstrap scripts, and operator docs

## AuthSec RBAC Model

Use one AuthSec MCP application for the protected server and create these permissions:

- Scopes: `read`, `write`, `ops`, `audit`
- Role: `admin`

Use these demo users:

- `viewer`: scope `read`
- `operator`: scopes `read`, `write`
- `admin`: role `admin`, scopes `read`, `write`, `ops`, `audit`

Tool mapping:

- `show_demo_state`, `read_fake_secret`: `read`
- `delete_customer_export`: `write`
- `stop_demo_worker`: role `admin` and scope `ops`
- `view_audit_events`: role `admin` and scope `audit`

## Local Codex Client Flow

Once the remote stack is live:

1. Generate the Codex snippet with [`render_codex_config_snippet.sh`](/Users/pc/Desktop/authnull/trial-modules/breachbox-mcp/stack/render_codex_config_snippet.sh).
2. Append it to [config.toml](/Users/pc/.codex/config.toml).
3. Restart Codex.
4. Connect to `breachbox_vanilla` and show that the dangerous tools are immediately available.
5. Connect to `breachbox_protected`, run `oauth_start`, and complete login in a dedicated browser profile for `viewer`, `operator`, or `admin`.
6. Use `oauth_status` and `tools/list` to confirm RBAC changes the visible and callable tools.
7. Use `oauth_logout` before switching personas.

If the VM's cloud firewall does not expose public `80/443` yet, use SSH tunnels to the VM-local ports:

- vanilla MCP: `ssh -L 9000:127.0.0.1:8000 authsec@<vm-ip>`
- protected MCP: `ssh -L 9001:127.0.0.1:8001 authsec@<vm-ip>`
- status UI: `ssh -L 9002:127.0.0.1:8081 authsec@<vm-ip>`

## Disposable VM Goal

The intended operator path is:

1. publish the Docker images
2. package the stack bundle
3. render `cloud-init`
4. create a fresh VM
5. wait for Docker Compose to pull and start
6. connect from local Codex and Inspector
