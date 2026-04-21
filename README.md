# telegram-mcp-server

An MCP server that lets an LLM use Telegram as a normal human user, built with [FastMCP](https://github.com/jlowin/fastmcp) and [Telethon](https://github.com/LonamiWebs/Telethon).

## Features

| Tool | Description |
|------|-------------|
| `get_chats` | Paginated list of chats sorted by recency, with unread/archived filters and forum topic support |
| `get_messages` | Paginated messages from a chat (media replaced by opaque IDs, stickers as XML markers) |
| `get_image` | Fetch and cache a photo by its opaque media ID |
| `get_user` | Name, username, bio, and profile photo ID for a user |
| `send_message` | Send a Markdown-formatted message with optional attachments and reply-to |
| `forward_message` | Forward a message to another chat |

All `get_*` tools (except `get_image`) return valid YAML.

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- A Telegram account and API credentials from [my.telegram.org](https://my.telegram.org)

### 1. Get a session string

```bash
uv run python session_string_generator.py
```

Follow the prompts. The printed `StringSession` value is your `SESSION_STRING`.

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your credentials:

```dotenv
API_ID=12345678
API_HASH=your_api_hash_here
SESSION_STRING=your_session_string_here
IMAGE_CACHE_DIR=.image_cache   # optional, default shown
```

### 3. Install dependencies

```bash
uv sync
```

### 4. Run the server

```bash
uv run python main.py
```

Or via the installed entry-point:

```bash
uv run telegram-mcp-server
```

## ID scheme

All IDs are opaque strings:

| Kind | Format | Example |
|------|--------|---------|
| Regular chat | `c:{peer_id}` | `c:-1001234567` |
| Forum topic | `t:{supergroup_id}:{topic_id}` | `t:-1001234567:5` |
| Message | `m:{peer_id}:{msg_id}` | `m:-1001234567:42` |
| Message media | `mp:{peer_id}:{msg_id}` | `mp:-1001234567:42` |
| User photo | `up:{user_id}` | `up:777000` |

## Development

### Run tests

```bash
uv run pytest
```

### Project structure

```
telegram_mcp_server/
  settings.py        # pydantic-settings configuration
  ids.py             # opaque ID encoding/decoding
  yaml_utils.py      # YAML serialization
  client.py          # Telethon singleton client
  models/            # Chat, User, Message pydantic-like dataclasses
  tools/             # one module per tool
  server.py          # FastMCP wiring
tests/               # pytest tests (all mocked, no live API calls)
rfcs/                # design documents
```
