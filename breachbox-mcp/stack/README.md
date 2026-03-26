# BreachBox Stack Bundle

This bundle is the disposable-VM operator artifact for the BreachBox MCP demo.

## What It Contains

- `docker-compose.yml`
- `.env.example`
- `Caddyfile`
- `build_images.sh`
- `install.sh`
- `cloud-init.yaml`
- `render_cloud_init.sh`
- `seed_demo_state.sh`
- `reset_demo_state.sh`
- `healthcheck.sh`
- `restart_protected_mcp.sh`
- `render_codex_config_snippet.sh`
- `get_tunnel_url.sh`
- `codex-mcp.example.toml`

## Fast Path

```bash
cp .env.example .env
# fill BREACHBOX_CONTROL_TOKEN
./install.sh
```

## Source-Build Fallback

If Docker Hub push is not available yet, use the full `breachbox-mcp` source tree on the VM:

```bash
cp stack/.env.example stack/.env
# fill AUTHSEC_CLIENT_ID, BREACHBOX_CONTROL_TOKEN, and set SKIP_PULL=1
./stack/build_images.sh
sudo ./stack/install.sh
```

## Disposable VM Path

1. Build and push the five runtime images with `./publish_images.sh`.
2. Create a stack tarball with `./generate_bundle.sh`.
3. Put that tarball somewhere the VM can fetch over HTTPS.
4. Render a real cloud-init file:

```bash
BUNDLE_URL="https://<your-host>/breachbox-stack.tar.gz" ./render_cloud_init.sh
```

5. Create a fresh Ubuntu VM with the rendered `cloud-init`.
6. Wait for cloud-init to install Docker, pull the images, and start the stack.

If you preload images onto a VM instead of pulling from Docker Hub, set `SKIP_PULL=1` in `.env` before running `install.sh`.

## Public URLs

- Vanilla MCP: `https://vanilla.<PUBLIC_HOST>/mcp`
- Protected MCP: `https://protected.<PUBLIC_HOST>/mcp`
- Status UI: `https://status.<PUBLIC_HOST>/`

## Quick Tunnel URLs

The stack also starts a Cloudflare Quick Tunnel automatically, so a fresh VM can expose a usable remote URL even when inbound `80/443` is blocked.

Get the base URL with:

```bash
./get_tunnel_url.sh
```

Then use:

- Vanilla MCP: `<BASE_URL>/vanilla/mcp`
- Protected MCP: `<BASE_URL>/protected/mcp`
- Status UI: `<BASE_URL>/status/`

## Local Codex Setup

Generate a config snippet:

```bash
./render_codex_config_snippet.sh
```

Append the output to [config.toml](/Users/pc/.codex/config.toml), then restart Codex.

Use this live flow:

1. Open `breachbox_vanilla` in Codex and ask for the available tools.
2. Prompt Codex to read the fake secret, delete the export, and stop the worker.
3. Open `breachbox_protected` in Codex.
4. Run `oauth_start` and finish login in a dedicated browser profile.
5. Run `oauth_status`, then list tools again.
6. Switch personas with `oauth_logout` before each new login.

The same public URLs also work in MCP Inspector.

If the VM's public `80/443` path is blocked, use SSH tunnels instead:

```bash
ssh -L 9000:127.0.0.1:8000 -L 9001:127.0.0.1:8001 -L 9002:127.0.0.1:8081 authsec@<vm-ip>
```

Then render the tunnel variant:

```bash
./render_codex_config_snippet.sh tunnel
```

Then point local tools at:

- vanilla MCP: `http://127.0.0.1:9000/mcp`
- protected MCP: `http://127.0.0.1:9001`
- status UI: `http://127.0.0.1:9002`

If you want a direct remote Codex config from the Quick Tunnel instead of SSH tunneling:

```bash
./render_codex_config_snippet.sh quick https://<random>.trycloudflare.com
```

## Auth Reset

- First choice: run `oauth_logout` from the protected MCP client.
- Fallback: `./restart_protected_mcp.sh`

## Demo Personas

- `viewer@gmail.com`: `breachbox.state:read`, `breachbox.secret:read`
- `operator@gmail.com`: `breachbox.state:read`, `breachbox.secret:read`, `breachbox.export:delete`
- `superadmin@gmail.com`: `breachbox.state:read`, `breachbox.secret:read`, `breachbox.export:delete`, `breachbox.worker:execute`, `breachbox.audit:read`

Use exact `resource:action` permission strings in AuthSec for this demo. The protected BreachBox server is intended to match those permissions directly.
