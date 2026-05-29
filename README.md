# telegram-mcp-server

An MCP server that lets an LLM use Telegram as a normal human user, built with [FastMCP](https://github.com/jlowin/fastmcp) and [Telethon](https://github.com/LonamiWebs/Telethon).

## Tools

| Tool | Description |
|------|-------------|
| `get_chats` | Paginated list of chats sorted by recency, with unread/archived filters and forum topic support |
| `search_chats` | Search for chats by name substring (case-insensitive) across all local dialogs |
| `get_messages` | Paginated messages from a chat (or global search), with optional keyword filter |
| `search_messages` | Search for messages by keyword, optionally restricted to a specific chat |
| `get_message` | Fetch a single message by opaque ID |
| `get_image` | Fetch and cache a photo by its opaque media ID |
| `get_user` | Name, username, bio, and profile photo ID for a user |
| `send_message` | Send a Markdown-formatted message with optional attachments and reply-to |
| `forward_message` | Forward a message to another chat |

All `get_*` and `search_*` tools (except `get_image`) return valid YAML.

## Deployment

The server is deployed with Docker Compose behind [Caddy](https://caddyserver.com/) (automatic HTTPS). Authentication uses GitHub OAuth via FastMCP's built-in `GitHubProvider`.

### Prerequisites

- A Linux host with a public domain name pointing to it
- Docker and Docker Compose
- A Telegram account with API credentials from [my.telegram.org](https://my.telegram.org)
- A [GitHub OAuth App](https://github.com/settings/developers) with:
  - Homepage URL: `https://<your-domain>`
  - Callback URL: `https://<your-domain>/auth/callback`

### 1. Get a Telegram session string

The server authenticates with Telegram using a session string (portable, no session file needed).

```bash
uv run python session_string_generator.py
```

Follow the prompts. Copy the printed session string.

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in `.env`:

```dotenv
# Telegram API credentials — from https://my.telegram.org/apps
API_ID=12345678
API_HASH=0123456789abcdef0123456789abcdef
SESSION_STRING=<output from session_string_generator.py>

# Public domain name (Caddy uses this for Let's Encrypt)
MCP_DOMAIN=your-domain.example

# GitHub OAuth App credentials — from https://github.com/settings/developers
GITHUB_CLIENT_ID=Ov23li...
GITHUB_CLIENT_SECRET=...
```

### 3. Deploy

```bash
docker compose up -d --build
```

Caddy will obtain a TLS certificate automatically via Let's Encrypt (HTTP-01 challenge on port 80).

### 4. Configure auth (optional: static token)

By default the server only accepts GitHub OAuth tokens. To also accept a static token (useful for automated testing or clients that don't support OAuth), set `MCP_AUTH_TOKEN` in `.env`:

```dotenv
MCP_AUTH_TOKEN=<a long random string>
```

Generate one with `openssl rand -base64 32`.

### 5. Connect

Add `https://<your-domain>/mcp` as a custom MCP server in your Claude client. The client will redirect you to GitHub to authorize on first use.

**Re-authentication after restarts:** FastMCP generates a fresh JWT signing key on each startup, so existing GitHub OAuth tokens are invalidated. If tools stop working after a server restart, disconnect and reconnect (or clear cached tokens) in your Claude client to trigger a new OAuth flow.

## Local development

### Install dependencies

```bash
uv sync
```

### Run locally (stdio transport)

```bash
MCP_TRANSPORT=stdio uv run telegram-mcp-server
```

### Run tests

```bash
uv run pytest
```

### Manually test tools against the live server

`scripts/call_tool.py` sends a single tool call to the running server and prints the result. It reads `MCP_AUTH_TOKEN` and `MCP_DOMAIN` from `.env` automatically, so `MCP_AUTH_TOKEN` must be set (see "Configure auth" above).

```bash
# List all chats (unread only, non-archived — the default)
uv run python scripts/call_tool.py get_chats

# All chats, no filters
uv run python scripts/call_tool.py get_chats unread=null archived=null

# Search for chats by name
uv run python scripts/call_tool.py search_chats query=Python limit=5

# Search messages globally
uv run python scripts/call_tool.py search_messages query=hello

# Search messages within a specific chat
uv run python scripts/call_tool.py search_messages query=hello chat_id=c:123456

# Fetch a page of messages from a chat
uv run python scripts/call_tool.py get_messages chat_id=c:123456 page_idx=0

# Fetch a single message
uv run python scripts/call_tool.py get_message message_id=m:123456:42

# Send a message
uv run python scripts/call_tool.py send_message chat_id=c:123456 text=Hello
```

Value types: bare strings, integers, `null` (→ `None`), `true`/`false` (→ `bool`).

Pass `--url <url>` to override the server URL (e.g. `--url http://localhost:8000/mcp` when port-forwarding).

## ID scheme

All IDs passed between tools are opaque strings:

| Kind | Format | Example |
|------|--------|---------|
| Regular chat | `c:{peer_id}` | `c:-1001234567` |
| Forum topic | `t:{supergroup_id}:{topic_id}` | `t:-1001234567:5` |
| Message | `m:{peer_id}:{msg_id}` | `m:-1001234567:42` |
| Message media | `mp:{peer_id}:{msg_id}` | `mp:-1001234567:42` |
| User photo | `up:{user_id}` | `up:777000` |

## Project structure

```
telegram_mcp_server/
  settings.py        # pydantic-settings configuration
  ids.py             # opaque ID encoding/decoding
  yaml_utils.py      # YAML serialization helpers
  client.py          # Telethon singleton client
  models/            # Chat, User, Message dataclasses
  tools/             # one module per MCP tool
  server.py          # FastMCP wiring and tool registration
tests/               # pytest unit tests (all mocked, no live API calls)
session_string_generator.py  # interactive script to obtain a Telegram session string
```
