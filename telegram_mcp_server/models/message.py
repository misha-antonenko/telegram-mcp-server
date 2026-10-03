from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, NamedTuple

from pydantic import Field

from telegram_mcp_server.ids import encode_message, encode_message_media
from telegram_mcp_server.models.base import ToolModel

if TYPE_CHECKING:
    from telethon.tl.types import Message as TLMessage


class _MessageContent(NamedTuple):
    text: str
    image: str | None = None
    audio: str | None = None
    video: str | None = None


class Message(ToolModel):
    id: str
    timestamp: str
    text: str
    sender: str | None = None
    sender_id: int | None = Field(default=None, exclude=True)
    forwarded_from_id: int | None = None
    reply_to_message_id: str | None = None
    unread: bool | None = None
    image: str | None = None
    audio: str | None = None
    video: str | None = None

    @classmethod
    def from_telethon(cls, msg: TLMessage, peer_id: int) -> Message:
        msg_id_str = encode_message(peer_id, msg.id)
        timestamp = _format_utc_minute(msg.date)
        content = _extract_content(msg, peer_id)
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
            text=content.text,
            sender_id=sender_id,
            forwarded_from_id=fwd_id,
            reply_to_message_id=reply_to_id,
            image=content.image,
            audio=content.audio,
            video=content.video,
        )


def _format_utc_minute(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M")


def _extract_content(msg: TLMessage, peer_id: int) -> _MessageContent:
    sticker_xml = _try_sticker(msg)
    if sticker_xml:
        return _MessageContent(text=sticker_xml)

    media = getattr(msg, "media", None)
    if media is None or _is_webpage(msg):
        return _MessageContent(text=getattr(msg, "message", "") or "")

    handle = encode_message_media(peer_id, msg.id)
    caption: str = getattr(msg, "message", "") or ""

    from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto

    if isinstance(media, MessageMediaPhoto):
        return _MessageContent(text=caption, image=handle)

    if isinstance(media, MessageMediaDocument):
        kind = _document_kind(media)
        assert kind != "sticker", f"sticker in message {msg.id} escaped _try_sticker"
        if kind == "audio":
            return _MessageContent(text=caption, audio=handle)
        if kind == "video":
            return _MessageContent(text=caption, video=handle)

    return _MessageContent(text=handle)


def _document_kind(media: object) -> Literal["sticker", "audio", "video"] | None:
    from telethon.tl.types import (
        DocumentAttributeAudio,
        DocumentAttributeSticker,
        DocumentAttributeVideo,
    )

    doc = getattr(media, "document", None)
    if doc is None:
        return None
    for attr in getattr(doc, "attributes", []):
        if isinstance(attr, DocumentAttributeSticker):
            return "sticker"
        if isinstance(attr, DocumentAttributeAudio):
            return "audio"
        if isinstance(attr, DocumentAttributeVideo):
            return "video"
    return None


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
    peer = getattr(msg, "from_id", None) or getattr(msg, "peer_id", None)
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
