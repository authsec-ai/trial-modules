# AuthSec SDK — Testing Folder: Progress & Plan

## Overview

This folder contains side-by-side demos comparing unprotected (vanilla) and protected (AuthSec) implementations for MCP servers and AI agents. The goal is to make the security problem visceral and the solution obvious.

## Folder Structure

```
testing/
├── README.md                        # Master README
├── progress_and_plan.md             # This file
├── .gitignore
│
├── mcp-server/
│   ├── vanilla/                     # MCP server with NO auth
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   ├── .env.example
│   │   ├── tools.py                 # Shared business logic
│   │   └── server.py               # FastMCP server
│   │
│   └── protected/                   # MCP server WITH AuthSec
│       ├── README.md
│       ├── requirements.txt
│       ├── .env.example
│       ├── tools.py                 # Same business logic (copied)
│       └── server.py               # AuthSec-protected server
│
├── ai-agent/
│   ├── vanilla/                     # Agent with NO delegation
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   ├── .env.example
│   │   └── agent.py
│   │
│   └── protected/                   # Agent WITH AuthSec delegation
│       ├── README.md
│       ├── requirements.txt
│       ├── .env.example
│       └── agent.py
```

## Implementation Checklist

- [x] Delete old files (`productivity_server.py`, `.claude/`)
- [x] Create `.gitignore`
- [x] Create `progress_and_plan.md` (this file)
- [x] Create `mcp-server/vanilla/tools.py` (shared business logic with SQLite)
- [x] Create `mcp-server/vanilla/server.py` (FastMCP, no auth)
- [x] Create `mcp-server/vanilla/requirements.txt`, `.env.example`, `README.md`
- [x] Copy `tools.py` to `mcp-server/protected/tools.py`
- [x] Create `mcp-server/protected/server.py` (AuthSec OAuth + RBAC)
- [x] Create `mcp-server/protected/requirements.txt`, `.env.example`, `README.md`
- [x] Create `ai-agent/vanilla/agent.py` (raw HTTP, no auth)
- [x] Create `ai-agent/vanilla/requirements.txt`, `.env.example`, `README.md`
- [x] Create `ai-agent/protected/agent.py` (DelegationClient)
- [x] Create `ai-agent/protected/requirements.txt`, `.env.example`, `README.md`
- [x] Create `testing/README.md` (master)
- [x] Update `sdk-authsec/README.md` (add "Live Demos" section)

## Verification Steps

1. **Vanilla MCP server**: `cd mcp-server/vanilla && pip install -r requirements.txt && python server.py` — starts on port 3000, all 4 tools visible
2. **Protected MCP server**: `cd mcp-server/protected && pip install authsec-sdk && python server.py` — starts on port 3005, tools hidden until OAuth
3. **Vanilla agent**: `cd ai-agent/vanilla && pip install -r requirements.txt && python agent.py` — fetches/creates/deletes with no auth
4. **Protected agent**: `cd ai-agent/protected && pip install authsec-sdk && python agent.py` — pulls delegation token, permission-gated actions
5. **Local SDK dev**: `pip install -e ../../../../sdk-authsec/packages/python-sdk` from any protected folder

## Key SDK APIs Used

- `core.py`: `protected_by_AuthSec`, `mcp_tool`, `run_mcp_server_with_oauth`
- `delegation_sdk.py`: `DelegationClient.pull_token()`, `.has_permission()`, `.request_json()`, `.decode_token_claims()`
- `__init__.py`: Public exports for all import names
