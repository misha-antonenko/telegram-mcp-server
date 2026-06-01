"""get_chats and get_folders tool implementations."""

from __future__ import annotations

from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.tl.functions.messages import (
    GetDialogFiltersRequest,
    GetForumTopicsRequest,
)
from telethon.tl.types import Channel, Chat, DialogFilter, User

from telegram_mcp_server.models.chat import Chat as ChatModel
from telegram_mcp_server.models.chat import _msg_sender_id
from telegram_mcp_server.tools.messages import _format_sender_name
from telegram_mcp_server.yaml_utils import to_yaml

PAGE_SIZE = 16

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_FOLDER_ALL_UNARCHIVED = "all unarchived"
_FOLDER_ARCHIVE = "archive"


def _filter_title(f: object) -> str | None:
    """Extract a plain-string title from a dialog filter object.

    Telegram returns titles as TextWithEntities; fall back to str() for
    any type that doesn't have a .text attribute.
    """
    raw = getattr(f, "title", None)
    if raw is None:
        return None
    return getattr(raw, "text", None) or str(raw) or None


def _peer_id(peer: object) -> int | None:
    """Return the bare entity ID from an InputPeer."""
    return (
        getattr(peer, "user_id", None)
        or getattr(peer, "channel_id", None)
        or getattr(peer, "chat_id", None)
    )


def _peer_ids(peers: list) -> set[int]:
    return {pid for p in peers if (pid := _peer_id(p)) is not None}


def _dialog_matches_filter(dialog: object, flt: DialogFilter) -> bool:
    """Return True if *dialog* belongs to *flt* per Telegram's filter semantics.

    Order of precedence (mirrors official client behaviour):
    1. Explicitly excluded peers → reject.
    2. Explicitly included peers (pinned + include_peers) → accept.
    3. Category flags (contacts, non_contacts, groups, broadcasts, bots) → accept
       if the dialog's entity type matches an enabled flag.
    4. No match → reject.

    exclude_muted / exclude_read / exclude_archived are intentionally not
    applied here because we want to show all folder members, not a filtered
    view (the caller can add those filters later if needed).
    """
    entity = dialog.entity
    eid = entity.id

    exclude_ids = _peer_ids(getattr(flt, "exclude_peers", []))
    if eid in exclude_ids:
        return False

    include_ids = _peer_ids(
        list(getattr(flt, "pinned_peers", [])) + list(getattr(flt, "include_peers", []))
    )
    if eid in include_ids:
        return True

    # Category-flag matching.
    if isinstance(entity, User):
        if getattr(entity, "bot", False):
            return bool(getattr(flt, "bots", False))
        if getattr(entity, "contact", False):
            return bool(getattr(flt, "contacts", False))
        return bool(getattr(flt, "non_contacts", False))

    if isinstance(entity, Chat):
        # Basic group (not a supergroup/channel).
        return bool(getattr(flt, "groups", False))

    if isinstance(entity, Channel):
        is_group = getattr(entity, "megagroup", False) or getattr(
            entity, "gigagroup", False
        )
        if is_group:
            return bool(getattr(flt, "groups", False))
        return bool(getattr(flt, "broadcasts", False))

    return False


async def _fetch_filters(client: TelegramClient) -> list:
    result = await client(GetDialogFiltersRequest())
    return result.filters


async def _find_custom_filter(
    client: TelegramClient, folder: str
) -> DialogFilter | None:
    for f in await _fetch_filters(client):
        title = _filter_title(f)
        if title and title.lower() == folder.lower():
            return f
    return None


async def get_folders(client: TelegramClient) -> str:
    """Return a YAML list of available folder names."""
    names: list[str] = [_FOLDER_ALL_UNARCHIVED, _FOLDER_ARCHIVE]
    for f in await _fetch_filters(client):
        title = _filter_title(f)
        if title:
            names.append(title)
    return to_yaml(names)


async def _populate_last_sender_names(
    client: TelegramClient, chats: list[ChatModel]
) -> None:
    """Fetch sender entities in batch and set last_sender_name on each chat."""
    ids = {c.last_sender_id for c in chats if c.last_sender_id is not None}
    if not ids:
        return
    name_map: dict[int, str] = {}
    for entity_id in ids:
        try:
            entity = await client.get_entity(entity_id)
            name_map[entity_id] = _format_sender_name(entity)
        except Exception:
            pass
    for chat in chats:
        if chat.last_sender_id is not None:
            chat.last_sender_name = name_map.get(chat.last_sender_id)


async def search_chats(
    client: TelegramClient,
    query: str,
    limit: int = 16,
) -> str:
    """Return a YAML-serialised list of chats whose name contains *query* (case-insensitive).

    Searches all dialogs (archived and non-archived). Returns at most *limit* results.
    """
    assert query, "query must be non-empty"
    needle = query.lower()
    matches: list[ChatModel] = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        name = getattr(entity, "title", None) or _full_name_from_entity(entity)
        if needle in name.lower():
            matches.append(ChatModel.from_dialog(dialog))
            if len(matches) == limit:
                break
    await _populate_last_sender_names(client, matches)
    return to_yaml([c.model_dump() for c in matches])


def _full_name_from_entity(entity: object) -> str:
    first = getattr(entity, "first_name", "") or ""
    last = getattr(entity, "last_name", "") or ""
    return (first + " " + last).strip() or str(getattr(entity, "id", ""))


async def _iter_folder_dialogs(client: TelegramClient, folder: str):
    """Yield dialogs belonging to *folder*, handling custom filters client-side."""
    if folder == _FOLDER_ALL_UNARCHIVED:
        async for d in client.iter_dialogs(folder=0):
            yield d
        return
    if folder == _FOLDER_ARCHIVE:
        async for d in client.iter_dialogs(folder=1):
            yield d
        return

    flt = await _find_custom_filter(client, folder)
    if flt is None:
        known = [_FOLDER_ALL_UNARCHIVED, _FOLDER_ARCHIVE] + [
            _filter_title(f) for f in await _fetch_filters(client) if _filter_title(f)
        ]
        raise ValueError(f"Unknown folder {folder!r}. Known folders: {known}")

    async for d in client.iter_dialogs():
        if _dialog_matches_filter(d, flt):
            yield d


async def get_chats(
    client: TelegramClient,
    folder: str,
    page_idx: int = 0,
) -> str:
    """Return a YAML-serialised paginated list of chats."""
    entries: list[ChatModel] = []
    async for dialog in _iter_folder_dialogs(client, folder):
        entity = dialog.entity
        is_forum = getattr(entity, "forum", False)

        if is_forum:
            topics_result = await client(
                GetForumTopicsRequest(
                    peer=entity,
                    offset_date=None,
                    offset_id=0,
                    offset_topic=0,
                    limit=100,
                )
            )
            sender_id_map: dict[int, int | None] = {
                m.id: _msg_sender_id(m) for m in topics_result.messages
            }
            msg_map: dict[int, str] = {
                m.id: (m.message or "") for m in topics_result.messages
            }
            date_map: dict[int, object] = {
                m.id: getattr(m, "date", None) for m in topics_result.messages
            }
            forum_name = getattr(entity, "title", "") or ""
            for topic in topics_result.topics:
                last_text = msg_map.get(topic.top_message, "")
                entries.append(
                    ChatModel.from_topic(
                        supergroup_id=entity.id,
                        forum_name=forum_name,
                        topic=topic,
                        last_message_text=last_text,
                        has_unread=topic.unread_count > 0,
                        last_sender_id=sender_id_map.get(topic.top_message),
                        last_message_date=date_map.get(topic.top_message),
                    )
                )
        else:
            entries.append(ChatModel.from_dialog(dialog))

    entries.sort(key=lambda c: c.last_message_date or _EPOCH, reverse=True)
    page = entries[page_idx * PAGE_SIZE : (page_idx + 1) * PAGE_SIZE]
    await _populate_last_sender_names(client, page)
    return to_yaml([c.model_dump() for c in page])
