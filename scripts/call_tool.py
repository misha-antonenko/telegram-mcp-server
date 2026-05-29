#!/usr/bin/env python3
"""Manually call any MCP tool against the running server.

Reads MCP_AUTH_TOKEN and MCP_DOMAIN from .env automatically.
The server URL defaults to https://<MCP_DOMAIN>/mcp; override with --url.

Usage:
    uv run python scripts/call_tool.py <tool> [key=value ...] [--url URL]

Value types: bare strings, integers, null (→ None), true/false (→ bool).

Examples:
    uv run python scripts/call_tool.py get_chats
    uv run python scripts/call_tool.py get_chats unread=null archived=null
    uv run python scripts/call_tool.py search_chats query=Python limit=5
    uv run python scripts/call_tool.py search_messages query=hello
    uv run python scripts/call_tool.py search_messages query=hello chat_id=c:123
    uv run python scripts/call_tool.py get_messages chat_id=c:123 page_idx=0
    uv run python scripts/call_tool.py get_message message_id=m:123:456
"""

from __future__ import annotations

import json
import ssl
import sys
import urllib.request
from pathlib import Path


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path = Path(__file__).parent.parent / ".env"
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def _parse_value(v: str) -> object:
    """Parse a string CLI value into the most appropriate Python type."""
    if v == "null":
        return None
    if v == "true":
        return True
    if v == "false":
        return False
    try:
        return int(v)
    except ValueError:
        pass
    return v


def _call(tool: str, args: dict, token: str, url: str) -> dict:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        }
    ).encode()
    # Allow self-signed certs for local/dev use.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
        },
    )
    resp = urllib.request.urlopen(req, context=ctx)
    for line in resp.read().decode().splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:])
    raise RuntimeError("No data line in server response")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    tool = sys.argv[1]
    args: dict[str, object] = {}
    url_override: str | None = None

    rest = sys.argv[2:]
    i = 0
    while i < len(rest):
        token_str = rest[i]
        if token_str == "--url":
            url_override = rest[i + 1]
            i += 2
            continue
        assert "=" in token_str, f"Expected key=value, got: {token_str!r}"
        k, v = token_str.split("=", 1)
        args[k] = _parse_value(v)
        i += 1

    env = _load_env()
    mcp_token = env.get("MCP_AUTH_TOKEN") or ""
    assert mcp_token, "MCP_AUTH_TOKEN not set in .env"

    if url_override:
        url = url_override
    else:
        domain = env.get("MCP_DOMAIN") or ""
        assert domain, "MCP_DOMAIN not set in .env (or pass --url)"
        url = f"https://{domain}/mcp"

    print(f"→ {url}  tool={tool}  args={args}\n")
    result = _call(tool, args, mcp_token, url)
    content = result.get("result", {})
    is_error = content.get("isError", False)
    text = content.get("content", [{}])[0].get("text", json.dumps(content))

    if is_error:
        print(f"ERROR: {text}", file=sys.stderr)
        sys.exit(1)
    print(text)


if __name__ == "__main__":
    main()
