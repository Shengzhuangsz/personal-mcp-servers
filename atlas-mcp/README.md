# atlas-mcp — Lark Doc writing tools for Claude Code

A stdio MCP server that turns Claude Code into a Lark Doc co-author. Eight tools cover the full document lifecycle: create, populate, patch, upload images, and transfer ownership.

No more writing `/tmp/lark_xxx.py` every time you want Claude to update a doc.

---

## Two ways to write a doc

**A · Bot creates new doc, then transfers to you**

```
Claude: lark_doc_create(title="季度汇报")
        → returns doc_id (owner = bot, you can't see it yet)
Claude: lark_doc_create_blocks(doc_id, blocks=[heading, text, image, ...])
Claude: lark_doc_upload_image(doc_id, image_block_id, "/path/to/diagram.png")
Claude: lark_doc_transfer_ownership(doc_id, email="you@company.com")
        → ownership moved, doc shows up in your Lark
```

**B · You create the doc in Lark, give Claude the URL**

```
You:    [create doc in Lark UI, copy URL]
        > "https://your.larksuite.com/docx/abcXXX 把第二段改成 '现状分析'"
Claude: lark_doc_list_blocks(doc_id)            # locate target block
Claude: lark_doc_patch_text(doc_id, block_id, "现状分析")
```

Path B keeps ownership clean from the start — usually friendlier.

---

## Tools

| Tool | Purpose |
|---|---|
| `lark_doc_create` | Create a new empty Doc (owner = bot until transferred) |
| `lark_doc_transfer_ownership` | Transfer ownership to a user by email or open_id |
| `lark_doc_list_blocks` | List all blocks: block_id, type, text snippet |
| `lark_doc_create_blocks` | Batch-create heading / text / bullet / divider / image blocks |
| `lark_doc_patch_text` | Replace the text of a single block |
| `lark_doc_upload_image` | Upload a local PNG / JPG into an image placeholder |
| `lark_doc_delete_children` | Batch-delete a range of children under a parent |
| `lookup_open_id_by_email` | Resolve a Lark open_id from an email |

### Block-type reference (for `lark_doc_create_blocks`)

Each block in the `blocks` array uses this shape:

```json
{"type": "heading1", "text": "一、总览", "bold": false, "color": null}
```

Supported `type`:

| `type` | Renders as |
|---|---|
| `heading1` … `heading5` | H1–H5 |
| `text` | Plain paragraph |
| `bullet` | Unordered list item |
| `divider` | Horizontal line (no `text` needed) |
| `image` | Image placeholder — fill via `lark_doc_upload_image` after |

---

## Install

### Quick install

```bash
git clone https://github.com/Shengzhuangsz/personal-mcp-servers ~/code/personal-mcp-servers
cd ~/code/personal-mcp-servers/atlas-mcp
./install.sh
```

`install.sh` will:

1. `cp .env.example .env` (if missing)
2. Open `.env` in `$EDITOR` for you to paste credentials
3. Register the server with Claude Code via `claude mcp add`
4. Verify the registration

### Manual install

```bash
git clone https://github.com/Shengzhuangsz/personal-mcp-servers ~/code/personal-mcp-servers
cd ~/code/personal-mcp-servers/atlas-mcp
cp .env.example .env                  # edit and fill in credentials
claude mcp add atlas-mcp -s user -- python3 $(pwd)/server.py
claude mcp list                       # expect: atlas-mcp ... ✓ Connected
```

### Required Lark scopes

| Scope | Used by |
|---|---|
| `docx:document` | All `lark_doc_*` block operations |
| `drive:file` | `lark_doc_create`, `lark_doc_upload_image` |
| `drive:drive` | `lark_doc_transfer_ownership` |
| `contact:user.base:readonly` | `lookup_open_id_by_email` (and `transfer_ownership` when given an email) |

After adding scopes in the Lark Open Platform, **publish a new app version** — scope changes don't take effect until you publish.

### Credential resolution order

Server reads in this order, first match wins:

1. Shell environment variables (`PG_LARK_APP_ID`, `PG_LARK_APP_SECRET`)
2. `.env` file in the same directory as `server.py`
3. `config.json` in the same directory: `{"lark": {"app_id": "...", "app_secret": "..."}}`

Pick whichever matches your security model.

---

## Two-minute demo

After install, open a fresh Claude Code session and try:

> 新建一个 Lark Doc, 标题 "atlas-mcp 测试", 里面加两段:
> 第一段是 H2 "总览", 第二段是 bullet "这是一条测试", 然后转给 me@example.com

Claude will chain four tool calls and report the URL when done.

If that works, you're set. Try the real workflows from the **Two ways to write a doc** section above.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `claude mcp list` shows ✗ Failed | server.py crashed at startup, usually missing credentials | Check stderr; fill in `.env` |
| `1061002 params error` on upload_image | wrong file field name | Already handled by this server. If it recurs, check the file path exists |
| `1024005 invalid param` on patch_text | block_id was truncated | Always pass the full block_id from `lark_doc_list_blocks`, not the first 20 chars |
| `1061045 access denied` on transfer | app missing `drive:drive` scope, or doc isn't owned by the app | Add scope, republish; or check the current owner with `lark_doc_list_blocks` |
| `99991672 access denied` on lookup_open_id | app missing `contact:user.base:readonly` | Add scope, republish |
| Tools don't show up in Claude Code | server registered but session didn't reload | Restart Claude Code (existing sessions don't pick up new MCP) |
| `feishu.cn` errors | Server hardcoded to larksuite.com | Edit `LARK_BASE` in `server.py` |

---

## Design notes

- **No external SDK.** Hand-rolled JSON-RPC over stdio so it works on any Python 3.9+ box without `pip install`.
- **Stdio transport.** No port opens, no inbound network. Only your local Claude Code talks to it.
- **Per-user credentials.** Each install uses its own `.env`. Never commit `.env` (`.gitignore` already handles it).
- **Lark domain.** Hardcoded to `open.larksuite.com` (海外). Change `LARK_BASE` in `server.py` for `feishu.cn`.
- **Token caching.** `tenant_access_token` cached for 110 minutes per process to avoid hammering auth.

---

## Versions

- `0.1.0` — Initial release: 8 tools covering create / populate / patch / image / transfer.

---

## License

MIT.
