"""send_message and forward_message tool implementations."""

from __future__ import annotations

from pathlib import Path

import telegramify_markdown
from telethon import TelegramClient

from telegram_mcp_server.ids import decode_chat, decode_message


async def send_message(
    client: TelegramClient,
    chat_id: str,
    text: str,
    attachments: list[str] | None = None,
    reply_to_message_id: str | None = None,
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

    # Convert Markdown → Telegram HTML / MarkdownV2 via telegramify_markdown
    formatted = telegramify_markdown.markdownify(text)

    if attachments:
        files = [Path(p) for p in attachments]
        if len(files) == 1:
            msg = await client.send_file(
                peer,
                file=files[0],
                caption=formatted,
                parse_mode="md",
                reply_to=reply_to,
            )
        else:
            # Send first file with caption, rest without
            msg = await client.send_file(
                peer,
                file=files,
                caption=formatted,
                parse_mode="md",
                reply_to=reply_to,
            )
    else:
        msg = await client.send_message(
            peer,
            message=formatted,
            parse_mode="md",
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
