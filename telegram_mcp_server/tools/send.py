from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING

import telegramify_markdown
from telethon.tl import types as tl

from telegram_mcp_server.ids import decode_chat, decode_message

if TYPE_CHECKING:
    from telegramify_markdown.entity import MessageEntity as TmEntity
    from telethon import TelegramClient

_ENTITY_TYPE_MAP = {
    "bold": tl.MessageEntityBold,
    "italic": tl.MessageEntityItalic,
    "code": tl.MessageEntityCode,
    "pre": tl.MessageEntityPre,
    "strikethrough": tl.MessageEntityStrike,
    "underline": tl.MessageEntityUnderline,
    "spoiler": tl.MessageEntitySpoiler,
    "text_link": tl.MessageEntityTextUrl,
    "custom_emoji": tl.MessageEntityCustomEmoji,
}


def _to_telethon_entities(entities: list[TmEntity]) -> list:
    result = []
    for e in entities:
        cls = _ENTITY_TYPE_MAP.get(e.type)
        if cls is None:
            continue
        kwargs: dict = {"offset": e.offset, "length": e.length}
        if e.type == "pre":
            kwargs["language"] = e.language or ""
        elif e.type == "text_link":
            kwargs["url"] = e.url or ""
        elif e.type == "custom_emoji":
            kwargs["document_id"] = int(e.custom_emoji_id or 0)
        result.append(cls(**kwargs))
    return result


def _parse_markdown(text: str) -> tuple[str, list]:
    plain, tm_entities = telegramify_markdown.convert(text)
    return plain, _to_telethon_entities(tm_entities)


def upload_attachment(filename: str, data_base64: str, attachments_dir: Path) -> str:
    if "/" in filename or "\\" in filename or filename in (".", ".."):
        raise ValueError(f"Invalid filename: {filename!r}")
    attachments_dir.mkdir(parents=True, exist_ok=True)
    data = base64.b64decode(data_base64)
    (attachments_dir / filename).write_bytes(data)
    return filename


def _resolve_attachment(filename: str, attachments_dir: Path) -> Path:
    if "/" in filename or "\\" in filename or filename in (".", ".."):
        raise ValueError(f"Invalid filename: {filename!r}")
    path = (attachments_dir / filename).resolve()
    resolved_dir = attachments_dir.resolve()
    if not path.is_relative_to(resolved_dir):
        raise ValueError(f"{filename!r} escapes the attachments directory")
    return path


async def send_message(
    client: TelegramClient,
    chat_id: str,
    text: str,
    attachments: list[str] | None = None,
    reply_to_message_id: str | None = None,
    attachments_dir: Path = Path(".attachments"),
) -> str:
    ref = decode_chat(chat_id)
    peer = ref.peer_id
    reply_to: int | None = None
    if reply_to_message_id:
        reply_to = decode_message(reply_to_message_id).msg_id

    plain, formatting_entities = _parse_markdown(text)

    if attachments:
        files = [_resolve_attachment(name, attachments_dir) for name in attachments]
        msg = await client.send_file(
            peer,
            file=files[0] if len(files) == 1 else files,
            caption=plain,
            formatting_entities=formatting_entities,
            reply_to=reply_to,
        )
    else:
        msg = await client.send_message(
            peer,
            message=plain,
            formatting_entities=formatting_entities,
            reply_to=reply_to,
        )

    sent_id = msg.id if not isinstance(msg, list) else msg[0].id
    return f"Sent message {sent_id}"


async def forward_message(
    client: TelegramClient,
    message_id: str,
    to_chat_id: str,
) -> str:
    msg_ref = decode_message(message_id)
    to_ref = decode_chat(to_chat_id)

    await client.forward_messages(
        entity=to_ref.peer_id,
        messages=msg_ref.msg_id,
        from_peer=msg_ref.peer_id,
    )
    return f"Forwarded message {message_id} to {to_chat_id}"
