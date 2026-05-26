#!/usr/bin/env python3
"""atlas-mcp server — Lark Doc writing tools for Claude Code.

Stdio MCP server, no external SDK dependency.
Implements: initialize / tools/list / tools/call (JSON-RPC 2.0).

Tools:
  - lark_doc_create(title, folder_token)
  - lark_doc_transfer_ownership(doc_id, email|open_id)
  - lark_doc_list_blocks(doc_id)
  - lark_doc_create_blocks(doc_id, parent_block_id, blocks, index)
  - lark_doc_patch_text(doc_id, block_id, new_text)
  - lark_doc_upload_image(doc_id, block_id, image_path)
  - lark_doc_delete_children(doc_id, parent_block_id, start, end)
  - lookup_open_id_by_email(email)
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# ---------- credentials ----------
#
# 凭据加载顺序:
#   1. 环境变量 PG_LARK_APP_ID / PG_LARK_APP_SECRET
#   2. 本目录下 .env 文件 (KEY=VALUE 格式, 注释 # 开头)
#   3. 本目录下 config.json ({"lark":{"app_id":..., "app_secret":...}})
# 找不到任何来源时, server 启动会报错并打印提示。

def _load_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        if "=" not in line: continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip("'\"")
    return out


def _load_credentials() -> Dict[str, str]:
    here = Path(__file__).parent
    env_file = _load_env_file(here / ".env")

    cfg_file = {}
    cfg_path = here / "config.json"
    if cfg_path.exists():
        try:
            cfg_file = json.loads(cfg_path.read_text())
        except Exception:
            pass

    def get(env_key: str, cfg_path_keys: List[str], default: str = "") -> str:
        # 1. shell env
        v = os.environ.get(env_key)
        if v: return v
        # 2. .env file
        v = env_file.get(env_key)
        if v: return v
        # 3. config.json
        v = cfg_file
        for k in cfg_path_keys:
            if not isinstance(v, dict): break
            v = v.get(k)
        if isinstance(v, str) and v: return v
        return default

    creds = {
        "lark_app_id": get("PG_LARK_APP_ID", ["lark", "app_id"]),
        "lark_app_secret": get("PG_LARK_APP_SECRET", ["lark", "app_secret"]),
        "kb_root": get("PG_KB_ROOT", ["paths", "kb_root"]),
        "sop_path": get("PG_SOP_PATH", ["paths", "sop_path"]),
    }
    if not creds["lark_app_id"] or not creds["lark_app_secret"]:
        sys.stderr.write(
            "[atlas-mcp] FATAL: missing Lark credentials. "
            "Set PG_LARK_APP_ID / PG_LARK_APP_SECRET via env, "
            f".env file, or config.json in {here}\n"
        )
        sys.exit(1)
    return creds


_creds = _load_credentials()
LARK_APP_ID = _creds["lark_app_id"]
LARK_APP_SECRET = _creds["lark_app_secret"]
LARK_BASE = "https://open.larksuite.com/open-apis"

KB_ROOT = Path(_creds["kb_root"]) if _creds["kb_root"] else Path()
SOP_PATH = Path(_creds["sop_path"]) if _creds["sop_path"] else Path()


# ---------- logging (to stderr; stdout is reserved for protocol) ----------

def log(msg: str) -> None:
    sys.stderr.write(f"[atlas-mcp] {msg}\n")
    sys.stderr.flush()


# ---------- Lark token cache ----------

_token_cache: Dict[str, Any] = {"token": None, "exp": 0}


def lark_token() -> str:
    if _token_cache["token"] and _token_cache["exp"] > time.time():
        return _token_cache["token"]
    r = requests.post(
        f"{LARK_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET},
        timeout=10,
    ).json()
    if r.get("code") != 0:
        raise RuntimeError(f"lark auth fail: {r.get('msg')}")
    _token_cache["token"] = r["tenant_access_token"]
    _token_cache["exp"] = time.time() + 6600
    return _token_cache["token"]


def lark_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {lark_token()}",
        "Content-Type": "application/json; charset=utf-8",
    }


# ---------- tool implementations ----------

def tool_lark_doc_list_blocks(doc_id: str) -> Dict:
    """列出 Doc 所有 block, 返回 block_id + type + 文字摘要"""
    r = requests.get(
        f"{LARK_BASE}/docx/v1/documents/{doc_id}/blocks?page_size=500",
        headers={"Authorization": f"Bearer {lark_token()}"},
        timeout=15,
    ).json()
    if r.get("code") != 0:
        return {"error": r.get("msg"), "raw": r}
    items = r.get("data", {}).get("items", [])
    out = []
    type_to_key = {
        2: "text", 3: "heading1", 4: "heading2", 5: "heading3",
        6: "heading4", 7: "heading5", 12: "bullet", 13: "ordered",
        22: "divider", 27: "image",
    }
    for it in items:
        bt = it.get("block_type")
        text = ""
        key = type_to_key.get(bt)
        if key and key in it:
            elements = it[key].get("elements", []) if isinstance(it[key], dict) else []
            text = "".join(e.get("text_run", {}).get("content", "") for e in elements)
        out.append({
            "block_id": it.get("block_id"),
            "block_type": bt,
            "type_name": key or f"type_{bt}",
            "text": text[:200],
        })
    return {"blocks": out, "count": len(out)}


def _build_block(block_spec: Dict) -> Dict:
    """从用户传入的简化规格构造 Lark block dict.
    支持: {type: "heading1"|"heading2"|"heading3"|"text"|"bullet"|"divider"|"image",
           text: "...", bold: false}
    """
    bt_map = {"text": 2, "heading1": 3, "heading2": 4, "heading3": 5,
              "heading4": 6, "heading5": 7, "bullet": 12, "divider": 22,
              "image": 27}
    t = block_spec.get("type", "text")
    bt = bt_map.get(t, 2)
    if bt == 22:
        return {"block_type": 22, "divider": {}}
    if bt == 27:
        return {"block_type": 27, "image": {"token": ""}}
    style = {}
    if block_spec.get("bold"):
        style["bold"] = True
    if block_spec.get("color"):
        style["text_color"] = block_spec["color"]
    text_run = {
        "content": block_spec.get("text", ""),
        "text_element_style": style,
    }
    key = {2: "text", 3: "heading1", 4: "heading2", 5: "heading3",
           6: "heading4", 7: "heading5", 12: "bullet"}[bt]
    return {
        "block_type": bt,
        key: {"elements": [{"text_run": text_run}], "style": {}},
    }


def tool_lark_doc_create_blocks(
    doc_id: str,
    parent_block_id: Optional[str],
    blocks: List[Dict],
    index: int = 0,
) -> Dict:
    """在 parent block 下创建一批 block. parent_block_id 为空时插到 page 根节点."""
    if not parent_block_id:
        # 找 page 根
        list_r = tool_lark_doc_list_blocks(doc_id)
        for b in list_r.get("blocks", []):
            if b["block_type"] == 1:
                parent_block_id = b["block_id"]
                break
        if not parent_block_id:
            # 大多 doc 第一个 block 就是 page; 直接退而求其次取第一个
            blocks_data = list_r.get("blocks", [])
            if blocks_data:
                parent_block_id = blocks_data[0]["block_id"]
    children = [_build_block(b) for b in blocks]
    url = (f"{LARK_BASE}/docx/v1/documents/{doc_id}/blocks/"
           f"{parent_block_id}/children?document_revision_id=-1")
    payload = {"index": index, "children": children}
    r = requests.post(
        url, headers=lark_headers(),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=20,
    ).json()
    if r.get("code") != 0:
        return {"error": r.get("msg"), "raw": r}
    created = r.get("data", {}).get("children", [])
    return {
        "created_count": len(created),
        "block_ids": [c.get("block_id") for c in created],
        "image_block_ids": [c.get("block_id") for c in created if c.get("block_type") == 27],
    }


def tool_lark_doc_patch_text(doc_id: str, block_id: str, new_text: str,
                              bold: bool = False) -> Dict:
    """改某个 text/heading/bullet block 的文字内容"""
    style = {}
    if bold: style["bold"] = True
    body = {
        "update_text_elements": {
            "elements": [
                {"text_run": {"content": new_text, "text_element_style": style}}
            ]
        }
    }
    url = (f"{LARK_BASE}/docx/v1/documents/{doc_id}/blocks/{block_id}"
           f"?document_revision_id=-1")
    r = requests.patch(
        url, headers=lark_headers(),
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        timeout=15,
    ).json()
    if r.get("code") != 0:
        return {"error": r.get("msg"), "raw": r}
    return {"ok": True, "block_id": block_id}


def tool_lark_doc_upload_image(doc_id: str, block_id: str, image_path: str) -> Dict:
    """上传图片到指定的 image block (block 必须先创建好且 block_type=27)"""
    p = Path(image_path)
    if not p.exists():
        return {"error": f"image not found: {image_path}"}
    files = {"file": (p.name, open(p, "rb"), "image/png" if p.suffix.lower() == ".png" else "image/jpeg")}
    data = {
        "file_name": p.name,
        "parent_type": "docx_image",
        "parent_node": block_id,
        "size": str(p.stat().st_size),
    }
    up = requests.post(
        f"{LARK_BASE}/drive/v1/medias/upload_all",
        headers={"Authorization": f"Bearer {lark_token()}"},
        files=files, data=data, timeout=60,
    ).json()
    if up.get("code") != 0:
        return {"error": "upload fail: " + up.get("msg", ""), "raw": up}
    file_token = up["data"]["file_token"]
    url = (f"{LARK_BASE}/docx/v1/documents/{doc_id}/blocks/{block_id}"
           f"?document_revision_id=-1")
    pr = requests.patch(
        url, headers=lark_headers(),
        data=json.dumps({"replace_image": {"token": file_token}}),
        timeout=15,
    ).json()
    if pr.get("code") != 0:
        return {"error": "patch fail: " + pr.get("msg", ""), "raw": pr}
    return {"ok": True, "file_token": file_token, "block_id": block_id}


def tool_lark_doc_delete_children(doc_id: str, parent_block_id: str,
                                    start: int, end: int) -> Dict:
    """批量删除 parent 下 [start, end) 范围的 children"""
    url = (f"{LARK_BASE}/docx/v1/documents/{doc_id}/blocks/"
           f"{parent_block_id}/children/batch_delete?document_revision_id=-1")
    r = requests.delete(
        url, headers=lark_headers(),
        json={"start_index": start, "end_index": end},
        timeout=15,
    ).json()
    if r.get("code") != 0:
        return {"error": r.get("msg"), "raw": r}
    return {"ok": True, "deleted": end - start}


def tool_lark_doc_create(title: str, folder_token: Optional[str] = None) -> Dict:
    """新建一个空 Lark Doc, 返回 doc_id 和访问 URL.

    创建出的 doc 默认 owner 是 app (机器人), 业务方需调用
    lark_doc_transfer_ownership 转给真人才能在 Lark UI 里看到/编辑。
    """
    body = {"title": title}
    if folder_token:
        body["folder_token"] = folder_token
    r = requests.post(
        f"{LARK_BASE}/docx/v1/documents",
        headers=lark_headers(),
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        timeout=15,
    ).json()
    if r.get("code") != 0:
        return {"error": r.get("msg"), "raw": r}
    doc = r.get("data", {}).get("document", {}) or {}
    doc_id = doc.get("document_id")
    return {
        "doc_id": doc_id,
        "title": doc.get("title"),
        "url": f"https://open.larksuite.com/docx/{doc_id}" if doc_id else None,
        "note": "owner 是 app, 真人看不到。若要在 Lark UI 里访问, 调 lark_doc_transfer_ownership 转给真人。",
    }


def tool_lark_doc_transfer_ownership(
    doc_id: str,
    email: Optional[str] = None,
    open_id: Optional[str] = None,
    remove_old_owner: bool = True,
) -> Dict:
    """把 Lark Doc 所有权转让给指定真人 (email 或 open_id 二选一).

    底层调 drive permission member transfer_owner endpoint.
    若只给 email, 内部会先反查 open_id.
    """
    if not open_id and not email:
        return {"error": "必须提供 email 或 open_id"}
    if not open_id:
        lookup = tool_lookup_open_id_by_email(email)
        if "error" in lookup:
            return {"error": f"email 反查失败: {lookup['error']}", "lookup_raw": lookup}
        open_id = lookup["open_id"]

    url = (f"{LARK_BASE}/drive/v1/permissions/{doc_id}/members/transfer_owner"
           f"?type=docx&need_notification=true&remove_old_owner="
           f"{'true' if remove_old_owner else 'false'}")
    body = {"member_type": "openid", "member_id": open_id}
    r = requests.post(
        url, headers=lark_headers(),
        data=json.dumps(body).encode("utf-8"),
        timeout=15,
    ).json()
    if r.get("code") != 0:
        return {"error": r.get("msg"), "raw": r,
                "hint": "若是 1061045 / 没权限, 检查 app 是否有 drive:drive scope"}
    return {"ok": True, "doc_id": doc_id, "new_owner_open_id": open_id,
            "url": f"https://open.larksuite.com/docx/{doc_id}"}


def tool_lookup_open_id_by_email(email: str) -> Dict:
    """email → open_id (用 v1.4.3 bot 的 contact 权限)"""
    r = requests.post(
        f"{LARK_BASE}/contact/v3/users/batch_get_id?user_id_type=open_id",
        headers=lark_headers(), json={"emails": [email]}, timeout=10,
    ).json()
    if r.get("code") != 0:
        return {"error": r.get("msg"), "raw": r}
    users = r.get("data", {}).get("user_list", [])
    if not users or not users[0].get("user_id"):
        return {"error": "user not found", "email": email}
    return {"open_id": users[0]["user_id"], "email": email,
            "active": users[0].get("status", {}).get("is_activated", False)}


# ---------- tool registry ----------

TOOLS: List[Dict] = [
    {
        "name": "lark_doc_list_blocks",
        "description": "List all blocks in a Lark Doc. Returns block_id, block_type, type_name (text/heading1/bullet/image/divider/...), and text snippet (first 200 chars). Use this to find the block_id you want to patch or replace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string", "description": "Lark Doc ID (the path segment in URL after /docx/)"},
            },
            "required": ["doc_id"],
        },
    },
    {
        "name": "lark_doc_create_blocks",
        "description": "Create blocks in a Lark Doc under a parent. Each block spec is {type, text, bold?, color?}. Supported types: text, heading1, heading2, heading3, heading4, heading5, bullet, divider, image. Returns block_ids of created blocks. For images, returned block_id is a placeholder; use lark_doc_upload_image to fill it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string"},
                "parent_block_id": {"type": "string", "description": "Parent block id. If empty, will use page root."},
                "blocks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "text": {"type": "string"},
                            "bold": {"type": "boolean"},
                            "color": {"type": "integer"},
                        },
                    },
                },
                "index": {"type": "integer", "description": "Insert position (0 = top)", "default": 0},
            },
            "required": ["doc_id", "blocks"],
        },
    },
    {
        "name": "lark_doc_patch_text",
        "description": "Replace the text content of a single block (text/heading/bullet). Pass full block_id from list_blocks (not truncated).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string"},
                "block_id": {"type": "string"},
                "new_text": {"type": "string"},
                "bold": {"type": "boolean", "default": False},
            },
            "required": ["doc_id", "block_id", "new_text"],
        },
    },
    {
        "name": "lark_doc_upload_image",
        "description": "Upload a local PNG/JPG to fill an image placeholder block. The block must already exist with block_type=27 (created via create_blocks with type=image).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string"},
                "block_id": {"type": "string", "description": "Image block id"},
                "image_path": {"type": "string", "description": "Absolute local path to PNG/JPG"},
            },
            "required": ["doc_id", "block_id", "image_path"],
        },
    },
    {
        "name": "lark_doc_delete_children",
        "description": "Delete a range of children blocks under a parent. Use to clear part of a doc before rebuilding.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string"},
                "parent_block_id": {"type": "string"},
                "start": {"type": "integer", "description": "start index (inclusive)"},
                "end": {"type": "integer", "description": "end index (exclusive)"},
            },
            "required": ["doc_id", "parent_block_id", "start", "end"],
        },
    },
    {
        "name": "lark_doc_create",
        "description": "Create a new empty Lark Doc. Returns doc_id and URL. WARNING: the new doc's owner is the bot/app, so the human user can't see it in Lark UI until you call lark_doc_transfer_ownership. Two workflows: (A) create via this tool then transfer to user; (B) skip this tool, ask user to manually create the doc and paste the URL — then use lark_doc_list_blocks etc on the existing doc_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Document title"},
                "folder_token": {"type": "string", "description": "Optional folder token (the doc will be created under this folder). Omit for root."},
            },
            "required": ["title"],
        },
    },
    {
        "name": "lark_doc_transfer_ownership",
        "description": "Transfer ownership of a Lark Doc to a real user (by email or open_id). Required after lark_doc_create so the user can access the doc in Lark UI. Provide either email (will auto-resolve to open_id) or open_id directly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string"},
                "email": {"type": "string", "description": "User email — preferred, auto-resolves to open_id"},
                "open_id": {"type": "string", "description": "Or pass open_id directly if already known"},
                "remove_old_owner": {"type": "boolean", "description": "Remove the bot from the doc's permission list after transfer (default: true)", "default": True},
            },
            "required": ["doc_id"],
        },
    },
    {
        "name": "lookup_open_id_by_email",
        "description": "Look up Lark open_id by email. Mostly used internally by lark_doc_transfer_ownership; expose as a standalone tool in case you need to confirm a user exists before transferring.",
        "inputSchema": {
            "type": "object",
            "properties": {"email": {"type": "string"}},
            "required": ["email"],
        },
    },
]


TOOL_FUNCS = {
    "lark_doc_list_blocks": tool_lark_doc_list_blocks,
    "lark_doc_create_blocks": tool_lark_doc_create_blocks,
    "lark_doc_patch_text": tool_lark_doc_patch_text,
    "lark_doc_upload_image": tool_lark_doc_upload_image,
    "lark_doc_delete_children": tool_lark_doc_delete_children,
    "lark_doc_create": tool_lark_doc_create,
    "lark_doc_transfer_ownership": tool_lark_doc_transfer_ownership,
    "lookup_open_id_by_email": tool_lookup_open_id_by_email,
}


# ---------- JSON-RPC stdio loop ----------

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "atlas-mcp", "version": "0.1.0"}


def send(payload: Dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle_request(req: Dict) -> Optional[Dict]:
    rid = req.get("id")
    method = req.get("method")
    params = req.get("params", {}) or {}

    try:
        if method == "initialize":
            return {
                "jsonrpc": "2.0", "id": rid,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": SERVER_INFO,
                },
            }
        if method == "notifications/initialized":
            return None  # notification, no response
        if method == "tools/list":
            return {
                "jsonrpc": "2.0", "id": rid,
                "result": {"tools": TOOLS},
            }
        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {}) or {}
            fn = TOOL_FUNCS.get(name)
            if not fn:
                return {
                    "jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32601, "message": f"unknown tool: {name}"},
                }
            log(f"call tool {name} args={list(args.keys())}")
            result = fn(**args)
            return {
                "jsonrpc": "2.0", "id": rid,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2),
                    }],
                },
            }
        # other methods: ping, etc.
        if method == "ping":
            return {"jsonrpc": "2.0", "id": rid, "result": {}}
        return {
            "jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"method not found: {method}"},
        }
    except Exception as e:
        log(f"error in {method}: {e}\n{traceback.format_exc()}")
        return {
            "jsonrpc": "2.0", "id": rid,
            "error": {"code": -32603, "message": f"internal error: {e}"},
        }


def main() -> None:
    log(f"atlas-mcp server starting (pid={os.getpid()})")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            log(f"bad json: {e} line={line[:200]}")
            continue
        resp = handle_request(req)
        if resp is not None:
            send(resp)


if __name__ == "__main__":
    main()
