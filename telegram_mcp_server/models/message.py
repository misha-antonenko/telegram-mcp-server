from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from telegram_mcp_server.ids import encode_message, encode_message_media
from telegram_mcp_server.models.base import ToolModel

if TYPE_CHECKING:
    from telethon.tl.types import Message as TLMessage


class Message(ToolModel):
    id: str  # opaque MessageRef
    timestamp: str  # "YYYY-MM-DD HH:MM" in UTC+4
    text: str  # may contain <sticker .../> markers or media ID strings
    sender_id: int | None = None
    sender_name: str | None = (
        None  # "Full Name (@username)" or "Full Name"; None if unknown
    )
    forwarded_from_id: int | None = None  # user/channel ID if forwarded
    reply_to_message_id: str | None = None  # opaque MessageRef of parent, if reply
    unread: bool | None = None  # True only for unread messages; omitted otherwise

    @classmethod
    def from_telethon(cls, msg: TLMessage, peer_id: int) -> Message:
        """Build a Message from a Telethon Message object.

        *peer_id* is the numeric ID of the chat the message belongs to
        (for topics this is the supergroup ID).
        """
        msg_id_str = encode_message(peer_id, msg.id)
        timestamp = _format_ts(msg.date)
        text = _extract_text(msg, peer_id)
        sender_id = _sender_id(msg)
        fwd_id = _forwarded_from_id(msg)
        reply_to_id: str | None = None
        if getattr(msg, "reply_to", None) is not None:
            reply_msg_id = getattr(msg.reply_to, "reply_to_msg_id", None)
            if reply_msg_id is not None:
                reply_to_id = encode_message(peer_id, reply_msg_id)

        return cls(
            id=msg_id_str,
            timestamp=timestamp,
            text=text,
            sender_id=sender_id,
            sender_name=None,
            forwarded_from_id=fwd_id,
            reply_to_message_id=reply_to_id,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_UTC4 = timezone(timedelta(hours=4))


def _format_ts(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(_UTC4).strftime("%Y-%m-%d %H:%M")


def _extract_text(msg: TLMessage, peer_id: int) -> str:
    # Check for sticker first (Document with DocumentAttributeSticker)
    sticker_xml = _try_sticker(msg)
    if sticker_xml:
        return sticker_xml

    # Other media: replace with opaque media ID
    if getattr(msg, "media", None) is not None and not _is_webpage(msg):
        return encode_message_media(peer_id, msg.id)

    return getattr(msg, "message", "") or ""


def _try_sticker(msg: TLMessage) -> str | None:
    from telethon.tl.types import DocumentAttributeSticker, MessageMediaDocument

    media = getattr(msg, "media", None)
    if not isinstance(media, MessageMediaDocument):
        return None
    doc = getattr(media, "document", None)
    if doc is None:
        return None
    for attr in getattr(doc, "attributes", []):
        if isinstance(attr, DocumentAttributeSticker):
            alt = attr.alt or ""
            return f'<sticker id="{doc.id}" alt="{alt}"/>'
    return None


def _is_webpage(msg: TLMessage) -> bool:
    from telethon.tl.types import MessageMediaWebPage

    return isinstance(getattr(msg, "media", None), MessageMediaWebPage)


def _sender_id(msg: TLMessage) -> int | None:
    peer = getattr(msg, "from_id", None)
    if peer is None:
        # Channel posts: sender is the channel itself
        peer = getattr(msg, "peer_id", None)
    if peer is None:
        return None
    return (
        getattr(peer, "user_id", None)
        or getattr(peer, "channel_id", None)
        or getattr(peer, "chat_id", None)
    )


def _forwarded_from_id(msg: TLMessage) -> int | None:
    fwd = getattr(msg, "fwd_from", None)
    if fwd is None:
        return None
    from_id = getattr(fwd, "from_id", None)
    if from_id is None:
        return None
    return getattr(from_id, "user_id", None) or getattr(from_id, "channel_id", None)
