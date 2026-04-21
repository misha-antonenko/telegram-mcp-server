# Implementation plan

## ID scheme

All IDs exposed by the API are opaque strings with a structured internal format.

### Chat IDs
- Regular chat/group/channel: `c:{peer_id}` (peer_id is a Telegram integer, may be negative)
- Forum topic: `t:{supergroup_id}:{topic_id}`

### Message IDs
- `m:{peer_id}:{msg_id}` for regular chats (peer_id is the supergroup_id for topics — message IDs are supergroup-scoped)

### Media IDs
- Message photo/video/file: `mp:{peer_id}:{msg_id}` (download by re-fetching the message)
- User profile photo: `up:{user_id}` (download the current profile photo)

## Module structure

```
telegram_mcp_server/
  __init__.py
  settings.py         # pydantic-settings: API_ID, API_HASH, SESSION_STRING, IMAGE_CACHE_DIR
  ids.py              # Opaque ID encode/decode helpers
  yaml_utils.py       # YAML serialization: only | for multiline strings
  client.py           # Telethon singleton client with async lock
  models/
    __init__.py
    chat.py           # Chat(id, name, preview, has_unread)
    user.py           # User(id, name, nickname, bio, profile_image_id)
    message.py        # Message(id, timestamp, text, sender_id, forwarded_from_id, reply_to_message)
  tools/
    __init__.py
    chats.py          # get_chats
    messages.py       # get_messages
    media.py          # get_image (returns MCP image, NOT YAML)
    users.py          # get_user
    send.py           # send_message, forward_message
  server.py           # FastMCP wiring + lifespan
tests/
  conftest.py
  test_ids.py
  test_yaml_utils.py
  test_chats.py
  test_messages.py
  test_media.py
  test_users.py
  test_send.py
```

## Key implementation notes

### Topics (forum supergroups)
1. `iter_dialogs()` returns the "forum" dialog for the supergroup.
2. Detect forum supergroups via `dialog.entity.forum == True`.
3. Fetch topics via `client(GetForumTopicsRequest(channel=entity, offset_date=0, offset_id=0, offset_topic=0, limit=100))`.
4. Each topic has `id` (topic_id), `title`, `unread_count`, `top_message` (ID of most recent message).
5. For `get_chats`, expand each forum supergroup into one entry per topic.

### Media in messages
In `from_telethon`, if a message has media:
- sticker (document with `DocumentAttributeSticker`): replace with `<sticker id="…" alt="…"/>`
- photo/document/video/etc: replace text portion with a media ID string `mp:{peer_id}:{msg_id}`

### YAML serialization
Use `yaml.dump` with a custom representer: strings containing `\n` get `|` block style; all others use default (quoted when needed by the YAML library). Use `allow_unicode=True, sort_keys=False, default_flow_style=False`.

### Client lifecycle
Module-level `_client: TelegramClient | None = None` and `_lock: asyncio.Lock`. `get_client()` async function acquires lock, creates and connects client if needed. FastMCP server uses lifespan to connect on startup and disconnect on shutdown.

### `get_image`
Returns `mcp.types.ImageContent` (not YAML). Caches file at `{IMAGE_CACHE_DIR}/{media_id_safe}.jpg`. Handles both `mp:` (re-fetch message media) and `up:` (fetch user profile photo).

## Status
- [x] deps
- [x] settings + ids + yaml_utils
- [x] models
- [x] client
- [x] tools
- [x] server
- [x] tests
- [x] docs
