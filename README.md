# personal-mcp-servers

Stdio MCP servers I use with Claude Code. Each server is a single `server.py` plus an `install.sh`, no build step, no external SDK.

## Servers

| Folder | Purpose |
|---|---|
| [`atlas-mcp`](./atlas-mcp) | Lark Doc writing tools — create, populate, patch text, upload images, transfer ownership |

More to come as needs arise.

## Why this repo exists

When I write docs with Claude Code, the same task — patch a Lark Doc, upload a fresh PNG, query a Bitable — keeps coming back. Without an MCP, every iteration involves writing a new throwaway script under `/tmp/` and re-pasting credentials.

Each server here is the answer to "I've written this script three times; package it once."

## Shared principles

- **No external SDK.** Hand-rolled JSON-RPC over stdio. Works on any Python 3.9+ box without `pip install`.
- **Credentials stay local.** Each server reads from `.env` / env vars / `config.json`. Nothing committed to the repo (`.gitignore` enforces).
- **Stdio only.** No network ports. Only your local Claude Code can reach it.
- **One folder = one server.** Self-contained, with its own README, `.env.example`, and `install.sh`.

## Install pattern

```bash
git clone https://github.com/Shengzhuangsz/personal-mcp-servers ~/code/personal-mcp-servers
cd ~/code/personal-mcp-servers/<server>
./install.sh
```

`install.sh` copies `.env.example`, opens `.env` in your editor, registers the server with Claude Code, and verifies the registration.

Each server's README spells out the specific scopes / endpoints it needs.

## Adding a new server

1. Create a folder `<name>/` at repo root
2. Drop in `server.py` (stdio JSON-RPC, follow `atlas-mcp/server.py` shape)
3. Add `.env.example`, `README.md`, and `install.sh` (copy from atlas-mcp and adjust)
4. Add a row to the **Servers** table above

That's it — no central registry, no CI.

## License

MIT.
