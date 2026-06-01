from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import Field

from telegram_mcp_server.ids import encode_chat, encode_topic
from telegram_mcp_server.models.base import ToolModel

if TYPE_CHECKING:
    from telethon.tl.types import Dialog, ForumTopic


class Chat(ToolModel):
    id: str  # opaque ChatRef encoded string
    name: str
    preview: str  # ≤32 characters of the last message
    has_unread: bool
    last_sender_name: str | None = None
    # Not serialised; used for sorting and entity lookup inside get_chats.
    last_sender_id: int | None = Field(default=None, exclude=True)
    last_message_date: datetime | None = Field(default=None, exclude=True)

    @classmethod
    def from_dialog(cls, dialog: Dialog) -> Chat:
        """Build a Chat from a regular Telethon Dialog."""
        entity = dialog.entity
        peer_id = _peer_id(entity)
        name = getattr(entity, "title", None) or _full_name(entity)
        preview = _preview(dialog.message)
        has_unread = dialog.unread_count > 0
        sender_id = _msg_sender_id(dialog.message)
        date = getattr(dialog.message, "date", None) if dialog.message else None
        return cls(
            id=encode_chat(peer_id),
            name=name,
            preview=preview,
            has_unread=has_unread,
            last_sender_id=sender_id,
            last_message_date=date,
        )

    @classmethod
    def from_topic(
        cls,
        supergroup_id: int,
        forum_name: str,
        topic: ForumTopic,
        last_message_text: str,
        has_unread: bool,
        last_sender_id: int | None = None,
        last_message_date: datetime | None = None,
    ) -> Chat:
        """Build a Chat from a Telethon ForumTopic."""
        return cls(
            id=encode_topic(supergroup_id, topic.id),
            name=f"{forum_name} / {topic.title}",
            preview=_truncate(last_message_text),
            has_unread=has_unread,
            last_sender_id=last_sender_id,
            last_message_date=last_message_date,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _msg_sender_id(msg: object | None) -> int | None:
    """Extract the numeric sender ID from a Telethon message object."""
    if msg is None:
        return None
    peer = getattr(msg, "from_id", None) or getattr(msg, "peer_id", None)
    if peer is None:
        return None
    return (
        getattr(peer, "user_id", None)
        or getattr(peer, "channel_id", None)
        or getattr(peer, "chat_id", None)
    )


def _peer_id(entity: object) -> int:
    """Return the numeric peer ID for any Telethon entity."""
    return getattr(entity, "id", 0)


def _full_name(entity: object) -> str:
    first = getattr(entity, "first_name", "") or ""
    last = getattr(entity, "last_name", "") or ""
    return (first + " " + last).strip() or str(_peer_id(entity))


def _truncate(text: str, limit: int = 32) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _preview(message: object | None) -> str:
    if message is None:
        return ""
    text: str = getattr(message, "message", "") or getattr(message, "text", "") or ""
    if not text:
        # Summarise media type
        media = getattr(message, "media", None)
        if media is not None:
            text = f"[{type(media).__name__}]"
    return _truncate(text)
