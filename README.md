# telegram-mcp-server

An MCP server that lets an LLM use Telegram as a normal human user, built with [FastMCP](https://github.com/jlowin/fastmcp) and [Telethon](https://github.com/LonamiWebs/Telethon).

## Tools

| Tool | Description |
|------|-------------|
| `get_chats` | Paginated list of chats sorted by recency, with unread/archived filters and forum topic support |
| `get_messages` | Paginated messages from a chat (or global search), with optional keyword filter |
| `get_message` | Fetch a single message by opaque ID |
| `get_image` | Fetch and cache a photo by its opaque media ID |
| `get_user` | Name, username, bio, and profile photo ID for a user |
| `send_message` | Send a Markdown-formatted message with optional attachments and reply-to |
| `forward_message` | Forward a message to another chat |

All `get_*` tools (except `get_image`) return valid YAML.

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

### 4. Connect

Add `https://<your-domain>/mcp` as a custom MCP server in your Claude client. The client will redirect you to GitHub to authorize on first use.

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
