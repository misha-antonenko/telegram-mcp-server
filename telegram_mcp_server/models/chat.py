from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from telegram_mcp_server.ids import encode_chat, encode_topic

if TYPE_CHECKING:
    from telethon.tl.types import Dialog, ForumTopic


@dataclass
class Chat:
    id: str  # opaque ChatRef encoded string
    name: str
    preview: str  # ≤32 characters of the last message
    has_unread: bool

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "preview": self.preview,
            "has_unread": self.has_unread,
        }

    @classmethod
    def from_dialog(cls, dialog: Dialog) -> Chat:
        """Build a Chat from a regular Telethon Dialog."""
        entity = dialog.entity
        peer_id = _peer_id(entity)
        name = getattr(entity, "title", None) or _full_name(entity)
        preview = _preview(dialog.message)
        has_unread = dialog.unread_count > 0
        return cls(
            id=encode_chat(peer_id),
            name=name,
            preview=preview,
            has_unread=has_unread,
        )

    @classmethod
    def from_topic(
        cls,
        supergroup_id: int,
        topic: ForumTopic,
        last_message_text: str,
        has_unread: bool,
    ) -> Chat:
        """Build a Chat from a Telethon ForumTopic."""
        return cls(
            id=encode_topic(supergroup_id, topic.id),
            name=topic.title,
            preview=_truncate(last_message_text),
            has_unread=has_unread,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
