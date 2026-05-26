# pg-atlas — Lark Doc / Bitable / KB tools for Claude Code

A stdio MCP server that exposes Lark Doc editing, Bitable querying, and PG knowledge-base search as tools, so Claude Code can write / patch Lark Docs directly without you writing `/tmp/lark_xxx.py` scripts every time.

Built for the GBIS Data Products workflow but the Lark Doc / Bitable tools are generic — anyone with a Lark Open Platform app can use them.

## Tools

| Tool | What it does |
|---|---|
| `lark_doc_list_blocks` | List all blocks in a Lark Doc (block_id, type, text snippet) |
| `lark_doc_create_blocks` | Batch-create heading / text / bullet / divider / image blocks |
| `lark_doc_patch_text` | Replace the text of a single block |
| `lark_doc_upload_image` | Upload a local PNG / JPG into an image placeholder block |
| `lark_doc_delete_children` | Batch-delete a range of children under a parent block |
| `bitable_query_records` | Query records from a Lark Bitable table |
| `kb_search` | Keyword-search the local PG knowledge base |
| `lookup_open_id_by_email` | Resolve a Lark `open_id` from an email address |

## Install

### 1. Clone

```bash
git clone https://github.com/Shengzhuangsz/personal-mcp-servers ~/code/personal-mcp-servers
```

(Or any path you like; we'll reference it below as `$MCP_DIR`.)

### 2. Configure credentials

```bash
cd ~/code/personal-mcp-servers/pg-atlas
cp .env.example .env
# edit .env and fill in your Lark App ID / Secret
```

The server reads credentials in this order: shell env vars → `.env` file → `config.json`. Pick whichever matches your security model.

Required Lark scopes on the app:

- `im:message:send_as_bot` — send replies (only needed if you use the bot, not strictly the MCP)
- `contact:user.base:readonly` — `lookup_open_id_by_email`
- `bitable:app:readonly` — `bitable_query_records`
- `drive:file` — `lark_doc_upload_image`
- `docx:document` — all `lark_doc_*` tools

### 3. Register with Claude Code

```bash
claude mcp add pg-atlas -s user -- python3 ~/code/personal-mcp-servers/pg-atlas/server.py
```

Verify:

```bash
claude mcp list
# pg-atlas: python3 .../pg-atlas/server.py - ✓ Connected
```

### 4. Use it

Open a fresh Claude Code session and ask things like:

- "List all blocks in this Lark Doc: `<doc_id>`"
- "Replace block `doxlgxxx...` with the text 'New title'"
- "Upload `~/Pictures/diagram.png` into image block `doxlgyyy...`"
- "Search the knowledge base for `FTD`"

Claude will pick the right tool and call it. No more shell scripts.

## Notes

- **No external dependencies.** Pure Python 3.9+ with `requests` (already on most systems).
- **Stdio transport.** No network port opens, no inbound connections. Only your local Claude Code can talk to it.
- **Per-user credentials.** Each install uses its own `.env`. Don't commit `.env`.
- **Lark domain.** Hardcoded to `open.larksuite.com` (海外). For `feishu.cn` change `LARK_BASE` in `server.py`.

## License

MIT — do whatever, no warranty.
