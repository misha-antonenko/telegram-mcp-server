from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, NamedTuple

from pydantic import Field
from telethon.tl.types import DocumentAttributeSticker

from telegram_mcp_server.ids import encode_message, encode_message_media
from telegram_mcp_server.models.base import ToolModel
from telegram_mcp_server.models.media import MediaCategory, classify_media, get_document_file_name

if TYPE_CHECKING:
    from telethon.tl.types import Document
    from telethon.tl.types import Message as TLMessage


class _MessageContent(NamedTuple):
    text: str
    image: str | None = None
    audio: str | None = None
    video: str | None = None
    file: str | None = None
    file_name: str | None = None


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
    file: str | None = None
    file_name: str | None = None

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
            file=content.file,
            file_name=content.file_name,
        )


def _format_utc_minute(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M")


def _extract_content(msg: TLMessage, peer_id: int) -> _MessageContent:
    media = getattr(msg, "media", None)
    category = classify_media(media)
    caption: str = getattr(msg, "message", "") or ""
    if category is None:
        return _MessageContent(text=caption)

    handle = encode_message_media(peer_id, msg.id)
    match category:
        case MediaCategory.STICKER:
            return _MessageContent(text=_format_sticker(media.document))
        case MediaCategory.IMAGE:
            return _MessageContent(text=caption, image=handle)
        case MediaCategory.AUDIO | MediaCategory.VOICE:
            return _MessageContent(text=caption, audio=handle)
        case MediaCategory.VIDEO:
            return _MessageContent(text=caption, video=handle)
        case MediaCategory.FILE:
            return _MessageContent(
                text=caption, file=handle, file_name=get_document_file_name(media.document)
            )
        case MediaCategory.OTHER:
            return _MessageContent(text=handle)


def _format_sticker(document: Document) -> str:
    [alt] = [a.alt for a in document.attributes if isinstance(a, DocumentAttributeSticker)]
    return f'<sticker id="{document.id}" alt="{alt or ""}"/>'


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
