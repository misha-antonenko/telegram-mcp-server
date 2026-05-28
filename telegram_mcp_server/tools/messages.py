"""get_messages and get_message tool implementations."""

from __future__ import annotations

from telethon import TelegramClient
from telethon import utils as tl_utils

from telegram_mcp_server.ids import ChatRef, decode_chat, decode_message
from telegram_mcp_server.models.message import Message
from telegram_mcp_server.yaml_utils import to_yaml

PAGE_SIZE = 16


def _format_sender_name(entity: object) -> str:
    name = tl_utils.get_display_name(entity)
    if not name:
        # Fallback: entity may not be a standard Telethon type (e.g. a stub)
        name = (
            getattr(entity, "title", None)
            or getattr(entity, "first_name", None)
            or getattr(entity, "username", None)
            or ""
        )
    username = getattr(entity, "username", None)
    if name and username:
        return f"{name} (@{username})"
    return name


async def _populate_sender_names(
    client: TelegramClient, messages: list[Message]
) -> None:
    """Fetch sender entities in batch and set sender_name on each message."""
    ids = {m.sender_id for m in messages if m.sender_id is not None}
    if not ids:
        return
    name_map: dict[int, str] = {}
    for entity_id in ids:
        try:
            entity = await client.get_entity(entity_id)
            name_map[entity_id] = _format_sender_name(entity)
        except Exception:
            pass
    for msg in messages:
        if msg.sender_id is not None:
            msg.sender_name = name_map.get(msg.sender_id)


async def get_messages(
    client: TelegramClient,
    chat_id: str | None,
    page_idx: int = 0,
    search_query: str = "",
) -> str:
    """Return a YAML-serialised paginated list of messages from *chat_id*.

    Pages are ordered newest-first across pages; within each page messages
    are ordered oldest-first (ascending by time).

    When *chat_id* is None and *search_query* is provided, Telegram performs
    a global search across all chats.
    """
    kwargs: dict = {}

    if chat_id is not None:
        ref: ChatRef = decode_chat(chat_id)
        peer_id: int | None = ref.peer_id
        if ref.is_topic:
            # For forum topics, filter by reply_to_msg_id == topic_id.
            kwargs["reply_to"] = ref.topic_id
    else:
        peer_id = None

    if search_query:
        kwargs["search"] = search_query

    messages = [
        Message.from_telethon(msg, peer_id or 0)
        async for msg in client.iter_messages(peer_id, **kwargs)
    ]

    page = list(reversed(messages[page_idx * PAGE_SIZE : (page_idx + 1) * PAGE_SIZE]))
    await _populate_sender_names(client, page)
    return to_yaml([m.to_dict() for m in page])


async def get_message(client: TelegramClient, message_id: str) -> str:
    """Return a YAML-serialised single message by its opaque message ID."""
    ref = decode_message(message_id)
    tl_msg = await client.get_messages(ref.peer_id, ids=ref.msg_id)
    assert tl_msg is not None, f"Message not found: {message_id!r}"
    msg = Message.from_telethon(tl_msg, ref.peer_id)
    await _populate_sender_names(client, [msg])
    return to_yaml(msg.to_dict())
