"""send_message, forward_message, and upload_attachment tool implementations."""

from __future__ import annotations

import base64
from pathlib import Path

import telegramify_markdown
from telegramify_markdown.entity import MessageEntity as TmEntity
from telethon import TelegramClient
from telethon.tl import types as tl

from telegram_mcp_server.ids import decode_chat, decode_message

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
    """Convert telegramify_markdown entities to Telethon TL entity objects."""
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
    """Parse Markdown text into (plain_text, telethon_entities).

    Uses telegramify_markdown.convert() so that the plain text is sent
    verbatim with formatting applied via entity objects, avoiding any
    MarkdownV2 escape sequences leaking into the message body.
    """
    plain, tm_entities = telegramify_markdown.convert(text)
    return plain, _to_telethon_entities(tm_entities)


def upload_attachment(filename: str, data_base64: str, attachments_dir: Path) -> str:
    """Write base64-encoded data to *attachments_dir*/*filename*.

    Args:
        filename: Basename only — must not contain path separators.
        data_base64: Base64-encoded file content.
        attachments_dir: Directory to write into (created if absent).

    Returns:
        The filename on success.
    """
    if "/" in filename or "\\" in filename or filename in (".", ".."):
        raise ValueError(f"Invalid filename: {filename!r}")
    attachments_dir.mkdir(parents=True, exist_ok=True)
    data = base64.b64decode(data_base64)
    (attachments_dir / filename).write_bytes(data)
    return filename


def _resolve_attachment(filename: str, attachments_dir: Path) -> Path:
    """Resolve *filename* to a path inside *attachments_dir*, rejecting traversal."""
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
    """Send a Markdown-formatted message to *chat_id*.

    Args:
        chat_id: Opaque chat ID (from get_chats).
        text: Message body in Markdown format.
        attachments: Optional list of local file paths to attach.
        reply_to_message_id: Opaque message ID to reply to.
    """
    ref = decode_chat(chat_id)
    peer = ref.peer_id
    reply_to: int | None = None
    if reply_to_message_id:
        reply_to = decode_message(reply_to_message_id).msg_id

    plain, formatting_entities = _parse_markdown(text)

    if attachments:
        files = [_resolve_attachment(name, attachments_dir) for name in attachments]
        if len(files) == 1:
            msg = await client.send_file(
                peer,
                file=files[0],
                caption=plain,
                formatting_entities=formatting_entities,
                reply_to=reply_to,
            )
        else:
            # Send first file with caption, rest without
            msg = await client.send_file(
                peer,
                file=files,
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
    """Forward a message identified by *message_id* to *to_chat_id*.

    Args:
        message_id: Opaque message ID (from get_messages).
        to_chat_id: Opaque destination chat ID (from get_chats).
    """
    msg_ref = decode_message(message_id)
    to_ref = decode_chat(to_chat_id)

    await client.forward_messages(
        entity=to_ref.peer_id,
        messages=msg_ref.msg_id,
        from_peer=msg_ref.peer_id,
    )
    return f"Forwarded message {message_id} to {to_chat_id}"
