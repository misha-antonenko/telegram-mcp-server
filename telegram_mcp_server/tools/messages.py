from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from enum import Enum, auto

import telethon.hints
from telethon import TelegramClient
from telethon import utils as tl_utils
from telethon.errors import RPCError
from telethon.tl.functions.messages import GetPeerDialogsRequest
from telethon.tl.types import Channel, User

from telegram_mcp_server.client import get_owner_id
from telegram_mcp_server.ids import ChatRef, decode_chat, decode_message
from telegram_mcp_server.models.message import Message
from telegram_mcp_server.tools.transcription import attach_voice_transcripts
from telegram_mcp_server.yaml_utils import to_yaml

PAGE_SIZE = 16


class _ChatType(Enum):
    DIRECT = auto()
    BROADCAST_CHANNEL = auto()
    GROUP = auto()
    UNKNOWN = auto()


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
    if peer_id is None:
        return _ChatType.UNKNOWN
    try:
        entity = await client.get_entity(peer_id)
    except (ValueError, RPCError):
        return _ChatType.UNKNOWN

    if isinstance(entity, User):
        return _ChatType.DIRECT
    if isinstance(entity, Channel):
        is_group = getattr(entity, "megagroup", False) or getattr(entity, "gigagroup", False)
        return _ChatType.GROUP if is_group else _ChatType.BROADCAST_CHANNEL
    return _ChatType.GROUP


async def _populate_senders(
    client: TelegramClient,
    messages: list[Message],
    tl_messages: list,
    chat_type: _ChatType,
) -> None:
    if chat_type == _ChatType.BROADCAST_CHANNEL:
        _populate_post_authors(messages, tl_messages)
    elif chat_type == _ChatType.DIRECT:
        _populate_direct_senders(messages)
    else:
        await _populate_group_senders(client, messages)


def _populate_post_authors(messages: list[Message], tl_messages: list) -> None:
    for msg, tl_msg in zip(messages, tl_messages, strict=True):
        author = getattr(tl_msg, "post_author", None)
        if author:
            msg.sender = author


def _populate_direct_senders(messages: list[Message]) -> None:
    my_id = get_owner_id()
    for msg in messages:
        if msg.sender_id is not None:
            msg.sender = "me" if msg.sender_id == my_id else "them"


async def _populate_group_senders(client: TelegramClient, messages: list[Message]) -> None:
    ids = {m.sender_id for m in messages if m.sender_id is not None}
    if not ids:
        return

    async def _fetch(entity_id: int) -> tuple[int, str] | None:
        try:
            entity = await client.get_entity(entity_id)
            return entity_id, _format_sender_name(entity)
        except (ValueError, RPCError):
            return None

    results = await asyncio.gather(*(_fetch(eid) for eid in ids))
    name_map = {eid: name for r in results if r is not None for eid, name in [r]}
    for msg in messages:
        if msg.sender_id is not None:
            msg.sender = name_map.get(msg.sender_id)


def _utc_midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


async def _build_chat_kwargs(client: TelegramClient, chat_id: str) -> tuple[int, dict]:
    ref: ChatRef = decode_chat(chat_id)
    await _cache_access_hash(client, ref.peer_id)
    kwargs: dict = {}
    if ref.is_topic:
        kwargs["reply_to"] = ref.topic_id
    return ref.peer_id, kwargs


async def _cache_access_hash(client: TelegramClient, peer_id: int) -> None:
    await client.get_input_entity(peer_id)


async def _find_last_message_id_before(
    client: TelegramClient, peer_id: int, moment: datetime, filter_kwargs: dict
) -> int:
    newest_first = await client.get_messages(peer_id, limit=1, offset_date=moment, **filter_kwargs)
    return newest_first[0].id if newest_first else 0


def _forward_page_offset(page_idx: int, *, is_anchored_at_min_id: bool) -> int:
    offset = page_idx * PAGE_SIZE
    # With reverse=True, Telethon sets offset_id from min_id and
    # adjusts add_offset relative to that anchor.  When anchored at
    # offset_id=1 (no min_id), positive add_offset pages forward.
    # When anchored at min_id+1, the direction flips — negate to
    # keep pages going forward in time.
    return -offset if is_anchored_at_min_id else offset


async def get_messages(
    client: TelegramClient,
    chat_id: str,
    since: date | None = None,
    page_idx: int = 0,
    search_query: str = "",
) -> str:
    peer_id, kwargs = await _build_chat_kwargs(client, chat_id)

    if search_query:
        kwargs["search"] = search_query

    min_id: int = 0
    if since is not None:
        filter_kwargs = {k: v for k, v in kwargs.items() if k in ("reply_to", "search")}
        min_id = await _find_last_message_id_before(
            client, peer_id, _utc_midnight(since), filter_kwargs
        )

    read_inbox_max_id: int = 0
    try:
        dialogs_result = await client(GetPeerDialogsRequest(peers=[peer_id]))
        if dialogs_result.dialogs:
            read_inbox_max_id = dialogs_result.dialogs[0].read_inbox_max_id
    except RPCError:
        pass

    if min_id:
        kwargs["min_id"] = min_id

    kwargs["limit"] = PAGE_SIZE
    kwargs["add_offset"] = _forward_page_offset(page_idx, is_anchored_at_min_id=bool(min_id))
    tl_messages = await client.get_messages(peer_id, reverse=True, **kwargs)
    assert isinstance(tl_messages, telethon.hints.TotalList), type(tl_messages)

    page = [Message.from_telethon(msg, peer_id) for msg in tl_messages]
    for msg, tl_msg in zip(page, tl_messages, strict=True):
        if tl_msg.id > read_inbox_max_id:
            msg.unread = True

    chat_type = await _get_chat_type(client, peer_id)
    await asyncio.gather(
        _populate_senders(client, page, list(tl_messages), chat_type),
        attach_voice_transcripts(client, page, list(tl_messages)),
    )

    return to_yaml([m.model_dump() for m in page])


async def count_messages(
    client: TelegramClient,
    chat_id: str,
    search_query: str = "",
) -> int:
    peer_id, kwargs = await _build_chat_kwargs(client, chat_id)
    if search_query:
        kwargs["search"] = search_query
    tl = await client.get_messages(peer_id, limit=0, **kwargs)
    assert isinstance(tl, telethon.hints.TotalList), type(tl)
    return tl.total


async def search_messages(
    client: TelegramClient,
    query: str,
    page_idx: int = 0,
    until: date | None = None,
) -> str:
    assert query, "query must be non-empty"

    kwargs: dict = {"search": query}

    if until is not None:
        end_of_until_day = _utc_midnight(until) + timedelta(days=1)
        kwargs["offset_date"] = end_of_until_day

    kwargs["limit"] = PAGE_SIZE
    kwargs["add_offset"] = page_idx * PAGE_SIZE
    tl_messages_raw = await client.get_messages(None, **kwargs)
    assert isinstance(tl_messages_raw, telethon.hints.TotalList), type(tl_messages_raw)

    tl_messages = list(tl_messages_raw)
    page = [Message.from_telethon(msg, 0) for msg in tl_messages]

    chat_type = _ChatType.UNKNOWN
    await asyncio.gather(
        _populate_senders(client, page, tl_messages, chat_type),
        attach_voice_transcripts(client, page, tl_messages),
    )

    return to_yaml([m.model_dump() for m in page])


async def get_message(client: TelegramClient, message_id: str) -> str:
    ref = decode_message(message_id)
    tl_msg = await client.get_messages(ref.peer_id, ids=ref.msg_id)
    assert tl_msg is not None, f"Message not found: {message_id!r}"
    msg = Message.from_telethon(tl_msg, ref.peer_id)
    chat_type = await _get_chat_type(client, ref.peer_id)
    await asyncio.gather(
        _populate_senders(client, [msg], [tl_msg], chat_type),
        attach_voice_transcripts(client, [msg], [tl_msg]),
    )
    return to_yaml(msg.model_dump())
