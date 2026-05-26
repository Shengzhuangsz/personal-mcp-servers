# personal-mcp-servers

A small collection of stdio MCP servers I use with Claude Code.

Each subdirectory is a standalone server with its own `README.md` and install instructions. They share two principles:

- **No external SDK.** Hand-rolled JSON-RPC over stdio so they work on any Python 3.9+ box without `pip install`.
- **Credentials stay local.** Each server reads from `.env` / env vars / `config.json` — nothing committed to the repo.

## Servers

| Folder | Purpose |
|---|---|
| [`pg-atlas`](./pg-atlas) | Lark Doc / Bitable / KB tools — for writing and patching Lark documents from Claude Code |

## Install pattern (any server)

```bash
git clone https://github.com/Shengzhuangsz/personal-mcp-servers ~/code/personal-mcp-servers
cd ~/code/personal-mcp-servers/<server>
cp .env.example .env  # fill in credentials
claude mcp add <server> -s user -- python3 $(pwd)/server.py
```

Each server's README has the specific scopes / endpoints it needs.

## License

MIT.
