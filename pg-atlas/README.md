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

### Quick install (recommended)

```bash
git clone https://github.com/Shengzhuangsz/personal-mcp-servers ~/code/personal-mcp-servers
cd ~/code/personal-mcp-servers/pg-atlas
./install.sh
```

`install.sh` will:

1. Copy `.env.example` → `.env` (if missing)
2. Open `.env` in your `$EDITOR` for you to paste credentials
3. Register the server with Claude Code via `claude mcp add`
4. Verify the registration

### Manual install (if you'd rather not run the script)

```bash
git clone https://github.com/Shengzhuangsz/personal-mcp-servers ~/code/personal-mcp-servers
cd ~/code/personal-mcp-servers/pg-atlas
cp .env.example .env                 # then edit .env and fill in credentials
claude mcp add pg-atlas -s user -- python3 $(pwd)/server.py
claude mcp list                       # should show: pg-atlas ... ✓ Connected
```

### Required Lark scopes

The Lark app you point this MCP at needs:

- `contact:user.base:readonly` — `lookup_open_id_by_email`
- `bitable:app:readonly` — `bitable_query_records`
- `drive:file` — `lark_doc_upload_image`
- `docx:document` — all `lark_doc_*` tools

The server reads credentials in this order: shell env vars → `.env` file → `config.json`. Pick whichever matches your security model.

### Use it

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
