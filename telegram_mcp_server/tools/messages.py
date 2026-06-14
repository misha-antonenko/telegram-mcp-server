"""get_messages and get_message tool implementations."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from enum import Enum, auto

from telethon import TelegramClient
from telethon import utils as tl_utils
import telethon.hints
from telethon.tl.functions.messages import GetPeerDialogsRequest
from telethon.tl.types import Channel, User

from telegram_mcp_server.client import get_owner_id
from telegram_mcp_server.ids import ChatRef, decode_chat, decode_message
from telegram_mcp_server.models.message import Message
from telegram_mcp_server.yaml_utils import to_yaml

PAGE_SIZE = 16


class _ChatType(Enum):
    DM = auto()  # 1:1 chat with a user
    CHANNEL = auto()  # broadcast channel (not a group)
    GROUP = auto()  # group chat (basic group, supergroup, megagroup)
    UNKNOWN = auto()  # global search or unknown entity


def _format_sender_name(entity: object) -> str:
    name = tl_utils.get_display_name(entity)
    if not name:
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


async def _get_chat_type(client: TelegramClient, peer_id: int | None) -> _ChatType:
    """Determine the chat type for sender simplification."""
    if peer_id is None:
        return _ChatType.UNKNOWN
    try:
        entity = await client.get_entity(peer_id)
    except Exception:
        return _ChatType.UNKNOWN

    if isinstance(entity, User):
        return _ChatType.DM
    if isinstance(entity, Channel):
        is_group = getattr(entity, "megagroup", False) or getattr(
            entity, "gigagroup", False
        )
        return _ChatType.GROUP if is_group else _ChatType.CHANNEL
    # Basic Chat type is always a group.
    return _ChatType.GROUP


async def _populate_senders(
    client: TelegramClient,
    messages: list[Message],
    tl_messages: list,
    chat_type: _ChatType,
) -> None:
    """Set `sender` on each message based on chat type.

    - DM: "me" or "them"
    - Channel: post_author if signed, else None (omitted)
    - Group/Unknown: "Full Name (@username)"

    *tl_messages* must be in the same order as *messages* (oldest-first after reversal).
    """
    if chat_type == _ChatType.CHANNEL:
        # Channel posts may have a signature (post_author).
        for msg, tl_msg in zip(messages, tl_messages):
            author = getattr(tl_msg, "post_author", None)
            if author:
                msg.sender = author
        return

    if chat_type == _ChatType.DM:
        my_id = get_owner_id()
        for msg in messages:
            if msg.sender_id is not None:
                msg.sender = "me" if msg.sender_id == my_id else "them"
        return

    # Group or unknown: fetch sender names.
    ids = {m.sender_id for m in messages if m.sender_id is not None}
    if not ids:
        return

    async def _fetch(entity_id: int) -> tuple[int, str] | None:
        try:
            entity = await client.get_entity(entity_id)
            return entity_id, _format_sender_name(entity)
        except Exception:
            return None

    results = await asyncio.gather(*(_fetch(eid) for eid in ids))
    name_map = {eid: name for r in results if r is not None for eid, name in [r]}
    for msg in messages:
        if msg.sender_id is not None:
            msg.sender = name_map.get(msg.sender_id)


def _date_to_datetime(d: date) -> datetime:
    """Convert a date to a timezone-aware datetime at midnight UTC."""
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


async def get_messages(
    client: TelegramClient,
    chat_id: str | None,
    page_idx: int = 0,
    search_query: str = "",
    since: date | None = None,
    until: date | None = None,
) -> str:
    """Return a YAML-serialised paginated list of messages from *chat_id*.

    Pages are ordered newest-first across pages; within each page messages
    are ordered oldest-first (ascending by time).

    When *chat_id* is None and *search_query* is provided, Telegram performs
    a global search across all chats.

    Args:
        since: If provided, only return messages from this date onwards (inclusive).
        until: If provided, only return messages up to this date (exclusive).
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

    if until is not None:
        kwargs["offset_date"] = _date_to_datetime(until)

    since_dt = _date_to_datetime(since) if since is not None else None

    # Fetch read_inbox_max_id to mark unread messages (only meaningful for specific chats).
    read_inbox_max_id: int = 0
    if chat_id is not None and peer_id is not None:
        try:
            dialogs_result = await client(GetPeerDialogsRequest(peers=[peer_id]))
            if dialogs_result.dialogs:
                read_inbox_max_id = dialogs_result.dialogs[0].read_inbox_max_id
        except Exception:
            pass  # leave read_inbox_max_id = 0; no unread marking

    # Fetch the needed page (newest-first, then reverse for display).
    kwargs["limit"] = PAGE_SIZE
    kwargs["add_offset"] = page_idx * PAGE_SIZE
    tl_messages = await client.get_messages(peer_id, reverse=True, **kwargs)
    assert isinstance(tl_messages, telethon.hints.TotalList), type(tl_messages)
    total: int = tl_messages.total

    # Filter by since date if provided (Telethon has no native min_date).
    if since_dt is not None:
        tl_messages = [m for m in tl_messages if m.date >= since_dt]

    page = [Message.from_telethon(msg, peer_id or 0) for msg in tl_messages]
    for msg, tl_msg in zip(page, tl_messages):
        if tl_msg.id > read_inbox_max_id:
            msg.unread = True

    chat_type = await _get_chat_type(client, peer_id)
    await _populate_senders(client, page, tl_messages, chat_type)

    fetched_through = (page_idx + 1) * PAGE_SIZE
    remaining_pages = max(0, max(0, total - fetched_through) // PAGE_SIZE)

    return to_yaml(
        {
            "remaining_pages": remaining_pages,
            "messages": [m.model_dump() for m in page],
        }
    )


async def search_messages(
    client: TelegramClient,
    query: str,
    chat_id: str | None = None,
    page_idx: int = 0,
    since: date | None = None,
    until: date | None = None,
) -> str:
    """Return a YAML-serialised paginated list of messages matching *query*.

    Args:
        query: Non-empty search string.
        chat_id: Opaque chat ID to restrict the search to; when None, searches globally.
        page_idx: Zero-based page index (16 messages per page).
        since: If provided, only return messages from this date onwards (inclusive).
        until: If provided, only return messages up to this date (exclusive).
    """
    assert query, "query must be non-empty"
    return await get_messages(
        client,
        chat_id=chat_id,
        page_idx=page_idx,
        search_query=query,
        since=since,
        until=until,
    )


async def get_message(client: TelegramClient, message_id: str) -> str:
    """Return a YAML-serialised single message by its opaque message ID."""
    ref = decode_message(message_id)
    tl_msg = await client.get_messages(ref.peer_id, ids=ref.msg_id)
    assert tl_msg is not None, f"Message not found: {message_id!r}"
    msg = Message.from_telethon(tl_msg, ref.peer_id)
    chat_type = await _get_chat_type(client, ref.peer_id)
    await _populate_senders(client, [msg], [tl_msg], chat_type)
    return to_yaml(msg.model_dump())
