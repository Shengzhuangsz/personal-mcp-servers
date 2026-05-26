# atlas-mcp — Lark Doc writing tools for Claude Code

A stdio MCP server that turns Claude Code into a Lark Doc co-author. Eight tools cover the full doc lifecycle: create, write blocks, patch text, upload images, and transfer ownership.

No more writing `/tmp/lark_xxx.py` every time you want Claude to update a doc.

## Two ways to write a doc

**A · Create new and transfer to you**

```
Claude: lark_doc_create(title="季度汇报")
        → returns doc_id (owner = bot, you can't see it yet)
Claude: lark_doc_create_blocks(doc_id, blocks=[...heading, text, image...])
Claude: lark_doc_upload_image(doc_id, block_id, "/path/to/diagram.png")
Claude: lark_doc_transfer_ownership(doc_id, email="you@company.com")
        → you're now owner, doc shows up in Lark
```

**B · Edit an existing doc you already created**

```
You:    Manually create the doc in Lark UI, paste the URL into chat
Claude: lark_doc_list_blocks(doc_id)         # find what to change
Claude: lark_doc_patch_text(doc_id, block_id, "new wording")
Claude: lark_doc_upload_image(doc_id, image_block_id, "/path/to/new.png")
```

Path B is usually friendlier — you keep ownership from the start, no transfer step.

## Tools

| Tool | What it does |
|---|---|
| `lark_doc_create` | Create a new empty Doc (owner = bot until transferred) |
| `lark_doc_transfer_ownership` | Transfer ownership to a real user by email or open_id |
| `lark_doc_list_blocks` | List all blocks (block_id, type, text snippet) |
| `lark_doc_create_blocks` | Batch-create heading / text / bullet / divider / image blocks |
| `lark_doc_patch_text` | Replace the text of a single block |
| `lark_doc_upload_image` | Upload a local PNG / JPG into an image placeholder block |
| `lark_doc_delete_children` | Batch-delete a range of children under a parent block |
| `lookup_open_id_by_email` | Resolve a Lark open_id from an email |

## Install

### Quick install (recommended)

```bash
git clone https://github.com/Shengzhuangsz/personal-mcp-servers ~/code/personal-mcp-servers
cd ~/code/personal-mcp-servers/atlas-mcp
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
cd ~/code/personal-mcp-servers/atlas-mcp
cp .env.example .env                 # then edit .env and fill in credentials
claude mcp add atlas-mcp -s user -- python3 $(pwd)/server.py
claude mcp list                       # should show: atlas-mcp ... ✓ Connected
```

### Required Lark scopes

The Lark app you point this MCP at needs:

- `docx:document` — all `lark_doc_*` block operations (list / create / patch / delete)
- `drive:file` — `lark_doc_create`, `lark_doc_upload_image`
- `drive:drive` — `lark_doc_transfer_ownership`
- `contact:user.base:readonly` — `lookup_open_id_by_email` (also used internally by transfer_ownership when you pass `email`)

The server reads credentials in this order: shell env vars → `.env` file → `config.json`. Pick whichever matches your security model.

### Use it

Open a fresh Claude Code session and ask things like:

**Path A — create + populate + transfer**

> "新建一个 Lark Doc, 标题叫 '季度汇报 2026 Q1', 里面写 3 段大纲, 然后把所有权转给 me@company.com"

Claude will chain `lark_doc_create` → `lark_doc_create_blocks` (×N) → `lark_doc_transfer_ownership`.

**Path B — edit existing doc**

> "https://your.larksuite.com/docx/abcXXX 里把第二段标题改成 '现状分析', 在末尾加一张图 ~/Pictures/q1.png"

Claude will call `lark_doc_list_blocks` to locate the target block, then `lark_doc_patch_text` and `lark_doc_create_blocks` + `lark_doc_upload_image`.

No more shell scripts.

## Notes

- **No external dependencies.** Pure Python 3.9+ with `requests` (already on most systems).
- **Stdio transport.** No network port opens, no inbound connections. Only your local Claude Code can talk to it.
- **Per-user credentials.** Each install uses its own `.env`. Don't commit `.env`.
- **Lark domain.** Hardcoded to `open.larksuite.com` (海外). For `feishu.cn` change `LARK_BASE` in `server.py`.

## License

MIT — do whatever, no warranty.
