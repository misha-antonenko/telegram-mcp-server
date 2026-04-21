"""get_chats tool implementation."""

from __future__ import annotations

from telethon import TelegramClient
from telethon.tl.functions.messages import GetForumTopicsRequest

from telegram_mcp_server.models.chat import Chat
from telegram_mcp_server.yaml_utils import to_yaml

PAGE_SIZE = 16


async def get_chats(
    client: TelegramClient,
    page_idx: int = 0,
    unread: bool | None = True,
    archived: bool | None = False,
) -> str:
    """Return a YAML-serialised paginated list of chats."""
    entries: list[Chat] = []

    iter_kwargs = {} if archived is None else {"archived": archived}
    async for dialog in client.iter_dialogs(**iter_kwargs):
        entity = dialog.entity
        is_forum = getattr(entity, "forum", False)

        if is_forum:
            # Expand forum supergroup into per-topic entries.
            topics_result = await client(
                GetForumTopicsRequest(
                    peer=entity,
                    offset_date=None,
                    offset_id=0,
                    offset_topic=0,
                    limit=100,
                )
            )
            msg_map: dict[int, str] = {
                m.id: (m.message or "") for m in topics_result.messages
            }
            for topic in topics_result.topics:
                topic_unread = topic.unread_count > 0
                if unread is not None and topic_unread != unread:
                    continue
                last_text = msg_map.get(topic.top_message, "")
                entries.append(
                    Chat.from_topic(
                        supergroup_id=entity.id,
                        topic=topic,
                        last_message_text=last_text,
                        has_unread=topic_unread,
                    )
                )
        else:
            has_unread = dialog.unread_count > 0
            if unread is not None and has_unread != unread:
                continue
            entries.append(Chat.from_dialog(dialog))

    page = entries[page_idx * PAGE_SIZE : (page_idx + 1) * PAGE_SIZE]
    return to_yaml([c.to_dict() for c in page])
