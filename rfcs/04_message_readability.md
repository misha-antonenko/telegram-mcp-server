# RFC 04: Message readability improvements

## Status: implemented

## Problem

The current `get_messages` output has several readability issues for an LLM consumer:

1. `None` fields are emitted verbatim, adding noise.
2. Only numeric `sender_id` is shown — the agent has no name to associate with the message
   without a separate `get_user` call.
3. Messages within a page are ordered newest-first (descending), which is counter-intuitive
   for reading a conversation.
4. There is no way to fetch a single message by its opaque ID, which is needed to resolve
   `reply_to_message_id` without listing the whole conversation.

## Proposed changes

### 1. Strip `None` fields from serialization

`Message.to_dict` currently emits every field unconditionally.
Change it to omit any key whose value is `None`.

Affected: `telegram_mcp_server/models/message.py`.

### 2. Add `sender_name` to messages

Add an optional `sender_name: str | None` field to the `Message` dataclass in the form
`"John Doe (@john_doe)"` (or just `"John Doe"` when there is no username).

Resolution happens in the tool layer (`get_messages`), not in the model, because entity
fetching requires the Telegram client.  After slicing the page, collect unique sender IDs,
batch-fetch entities with `client.get_entity`, then populate `sender_name` on each message.

`Message.from_telethon` signature stays unchanged.

**Implementation notes**

* `telethon.utils.get_display_name(entity)` returns the full name.
* `getattr(entity, "username", None)` gives the username without `@`.
* If the entity fetch fails (e.g. deleted account), fall back to `None` (omitted by rule 1).
* For channel posts where `from_id` is absent and `sender_id` resolves to the channel
  itself, the channel title is a valid name.

Affected: `telegram_mcp_server/models/message.py`,
`telegram_mcp_server/tools/messages.py`.

### 3. Ascending order within each page

`iter_messages` returns messages in descending order (newest first).  Pagination over pages
stays descending so page 0 is the most recent window.  Within each page, reverse the slice
so the oldest message in the window comes first.

Change: `page = messages[...]` → `page = list(reversed(messages[...]))` in
`telegram_mcp_server/tools/messages.py`.

### 4. New `get_message` tool

Add a `get_message(message_id: str) -> str` tool that fetches a single message by its
opaque `MessageRef` and returns it in the same YAML format as one element of `get_messages`.

Implementation:
1. `decode_message(message_id)` to extract `peer_id` and `msg_id`.
2. `await client.get_messages(peer_id, ids=msg_id)` — returns a single `TLMessage`.
3. Build a `Message`, populate `sender_name`, call `to_dict`, serialise to YAML.

Expose via `server.py`.

Affected: `telegram_mcp_server/tools/messages.py`, `telegram_mcp_server/server.py`.

## Files touched

| File | Change |
|---|---|
| `telegram_mcp_server/models/message.py` | Add `sender_name` field; strip `None` from `to_dict` |
| `telegram_mcp_server/tools/messages.py` | Populate `sender_name`; reverse page; add `get_message` |
| `telegram_mcp_server/server.py` | Register `get_message` tool |
| `tests/test_message_model.py` | Update `test_to_dict_keys`; add None-stripping test |
| `tests/test_messages_tool.py` | Add tests for ascending order, `sender_name`, `get_message` |

## Open questions

None.
