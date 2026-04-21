"""get_messages tool implementation."""

from __future__ import annotations

from telethon import TelegramClient

from telegram_mcp_server.ids import ChatRef, decode_chat
from telegram_mcp_server.models.message import Message
from telegram_mcp_server.yaml_utils import to_yaml

PAGE_SIZE = 16


async def get_messages(
    client: TelegramClient,
    chat_id: str,
    page_idx: int = 0,
) -> str:
    """Return a YAML-serialised paginated list of messages from *chat_id*."""
    ref: ChatRef = decode_chat(chat_id)

    kwargs: dict = {}
    if ref.is_topic:
        # For forum topics, filter by reply_to_msg_id == topic_id.
        kwargs["reply_to"] = ref.topic_id

    messages: list[Message] = []
    async for msg in client.iter_messages(ref.peer_id, **kwargs):
        messages.append(Message.from_telethon(msg, ref.peer_id))

    page = messages[page_idx * PAGE_SIZE : (page_idx + 1) * PAGE_SIZE]
    return to_yaml([m.to_dict() for m in page])
