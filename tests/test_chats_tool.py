"""Tests for the get_chats tool."""

from unittest.mock import AsyncMock, MagicMock

import yaml

from telegram_mcp_server.ids import encode_chat, encode_topic


def _make_dialog(peer_id, title, unread_count, message_text, is_forum=False, sender_id=None):
    entity = MagicMock()
    entity.id = peer_id
    entity.title = title
    entity.forum = is_forum

    last_msg = MagicMock()
    last_msg.message = message_text
    last_msg.media = None
    if sender_id is not None:
        from_peer = MagicMock()
        from_peer.user_id = sender_id
        from_peer.channel_id = None
        from_peer.chat_id = None
        last_msg.from_id = from_peer
        last_msg.peer_id = None
    else:
        last_msg.from_id = None
        last_msg.peer_id = None

    dialog = MagicMock()
    dialog.entity = entity
    dialog.unread_count = unread_count
    dialog.message = last_msg
    return dialog


async def _async_gen(items):
    for item in items:
        yield item


class TestGetChats:
    async def test_returns_yaml(self):
        from telegram_mcp_server.tools.chats import get_chats

        client = MagicMock()
        dialog = _make_dialog(1, "Chat", unread_count=1, message_text="hi")
        client.iter_dialogs = MagicMock(return_value=_async_gen([dialog]))

        result = await get_chats(client, unread=True)
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, list)
        assert parsed[0]["id"] == encode_chat(1)

    async def test_unread_filter(self):
        from telegram_mcp_server.tools.chats import get_chats

        client = MagicMock()
        dialogs = [
            _make_dialog(1, "Unread", unread_count=2, message_text="new"),
            _make_dialog(2, "Read", unread_count=0, message_text="old"),
        ]
        client.iter_dialogs = MagicMock(return_value=_async_gen(dialogs))

        result = await get_chats(client, unread=True)
        chats = yaml.safe_load(result)
        assert all(c["has_unread"] for c in chats)

        client.iter_dialogs = MagicMock(return_value=_async_gen(dialogs))
        result2 = await get_chats(client, unread=False)
        chats2 = yaml.safe_load(result2)
        assert all(not c["has_unread"] for c in chats2)

        client.iter_dialogs = MagicMock(return_value=_async_gen(dialogs))
        result3 = await get_chats(client, unread=None)
        chats3 = yaml.safe_load(result3)
        assert len(chats3) == 2

    async def test_archived_none_does_not_filter(self):
        from telegram_mcp_server.tools.chats import get_chats

        client = MagicMock()
        dialogs = [
            _make_dialog(1, "A", unread_count=1, message_text="x"),
            _make_dialog(2, "B", unread_count=0, message_text="y"),
        ]
        client.iter_dialogs = MagicMock(return_value=_async_gen(dialogs))

        result = await get_chats(client, unread=None, archived=None)
        chats = yaml.safe_load(result)
        # archived=None means iter_dialogs called without archived kwarg
        client.iter_dialogs.assert_called_once_with()
        assert len(chats) == 2

    async def test_pagination(self):
        from telegram_mcp_server.tools.chats import get_chats

        client = MagicMock()
        # 20 unread dialogs
        dialogs = [
            _make_dialog(i, f"Chat{i}", unread_count=1, message_text="x")
            for i in range(20)
        ]
        client.iter_dialogs = MagicMock(return_value=_async_gen(dialogs))
        result = await get_chats(client, page_idx=0)
        assert len(yaml.safe_load(result)) == 16

        client.iter_dialogs = MagicMock(return_value=_async_gen(dialogs))
        result2 = await get_chats(client, page_idx=1)
        assert len(yaml.safe_load(result2)) == 4

    async def test_forum_topics_expanded(self):
        from telegram_mcp_server.tools.chats import get_chats

        client = MagicMock()
        forum_dialog = _make_dialog(
            500, "Forum", unread_count=0, message_text="", is_forum=True
        )

        topic1 = MagicMock()
        topic1.id = 1
        topic1.title = "General"
        topic1.unread_count = 1
        topic1.top_message = 10

        topic2 = MagicMock()
        topic2.id = 2
        topic2.title = "Off-topic"
        topic2.unread_count = 0
        topic2.top_message = 20

        msg10 = MagicMock()
        msg10.id = 10
        msg10.message = "latest in General"

        msg20 = MagicMock()
        msg20.id = 20
        msg20.message = "latest in Off-topic"

        topics_result = MagicMock()
        topics_result.topics = [topic1, topic2]
        topics_result.messages = [msg10, msg20]

        client = AsyncMock()
        client.iter_dialogs = MagicMock(return_value=_async_gen([forum_dialog]))
        client.return_value = topics_result

        result = await get_chats(client, unread=True)
        chats = yaml.safe_load(result)
        # Only topic1 has unread
        assert len(chats) == 1
        assert chats[0]["id"] == encode_topic(500, 1)
        assert chats[0]["name"] == "General"

    async def test_last_sender_name_populated(self):
        from telegram_mcp_server.tools.chats import get_chats

        dialog = _make_dialog(1, "Chat", unread_count=1, message_text="hello", sender_id=42)

        entity = MagicMock()
        entity.first_name = "Alice"
        entity.last_name = None
        entity.username = "alice"
        entity.title = None

        client = MagicMock()
        client.iter_dialogs = MagicMock(return_value=_async_gen([dialog]))
        client.get_entity = AsyncMock(return_value=entity)

        result = await get_chats(client, unread=True)
        chats = yaml.safe_load(result)
        assert "last_sender_name" in chats[0]
        assert "Alice" in chats[0]["last_sender_name"]
        assert "@alice" in chats[0]["last_sender_name"]

    async def test_last_sender_name_absent_when_no_sender(self):
        from telegram_mcp_server.tools.chats import get_chats

        dialog = _make_dialog(1, "Chat", unread_count=1, message_text="hello", sender_id=None)

        client = MagicMock()
        client.iter_dialogs = MagicMock(return_value=_async_gen([dialog]))
        client.get_entity = AsyncMock(side_effect=Exception("should not be called"))

        result = await get_chats(client, unread=True)
        chats = yaml.safe_load(result)
        assert "last_sender_name" not in chats[0]

    async def test_last_sender_name_absent_when_entity_fetch_fails(self):
        from telegram_mcp_server.tools.chats import get_chats

        dialog = _make_dialog(1, "Chat", unread_count=1, message_text="hello", sender_id=99)

        client = MagicMock()
        client.iter_dialogs = MagicMock(return_value=_async_gen([dialog]))
        client.get_entity = AsyncMock(side_effect=Exception("network error"))

        result = await get_chats(client, unread=True)
        chats = yaml.safe_load(result)
        # Entity fetch failed, so last_sender_name should be absent
        assert "last_sender_name" not in chats[0]

