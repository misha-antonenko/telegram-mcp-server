"""Tests for the get_chats and get_folders tools."""

from unittest.mock import AsyncMock, MagicMock

import yaml

from telegram_mcp_server.ids import encode_chat, encode_topic


def _make_dialog(
    peer_id, title, unread_count, message_text, is_forum=False, sender_id=None
):
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


def _make_filter(filter_id, title):
    f = MagicMock()
    f.id = filter_id
    f.title = title
    return f


class TestGetFolders:
    async def test_returns_fixed_plus_custom(self):
        from telegram_mcp_server.tools.chats import get_folders

        custom = _make_filter(2, "Work")
        filters_result = MagicMock()
        filters_result.filters = [custom]

        client = AsyncMock()
        client.return_value = filters_result

        result = await get_folders(client)
        names = yaml.safe_load(result)
        assert "all unarchived" in names
        assert "archive" in names
        assert "Work" in names

    async def test_no_custom_folders(self):
        from telegram_mcp_server.tools.chats import get_folders

        filters_result = MagicMock()
        filters_result.filters = []

        client = AsyncMock()
        client.return_value = filters_result

        result = await get_folders(client)
        names = yaml.safe_load(result)
        assert names == ["all unarchived", "archive"]


class TestGetChats:
    async def test_returns_yaml(self):
        from telegram_mcp_server.tools.chats import get_chats

        client = MagicMock()
        dialog = _make_dialog(1, "Chat", unread_count=1, message_text="hi")
        client.iter_dialogs = MagicMock(return_value=_async_gen([dialog]))

        result = await get_chats(client)
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, list)
        assert parsed[0]["id"] == encode_chat(1)

    async def test_no_folder_passes_no_kwarg(self):
        from telegram_mcp_server.tools.chats import get_chats

        client = MagicMock()
        dialogs = [
            _make_dialog(1, "A", unread_count=1, message_text="x"),
            _make_dialog(2, "B", unread_count=0, message_text="y"),
        ]
        client.iter_dialogs = MagicMock(return_value=_async_gen(dialogs))

        result = await get_chats(client, folder=None)
        chats = yaml.safe_load(result)
        client.iter_dialogs.assert_called_once_with()
        assert len(chats) == 2

    async def test_folder_all_unarchived(self):
        from telegram_mcp_server.tools.chats import get_chats

        client = MagicMock()
        dialog = _make_dialog(1, "Chat", unread_count=0, message_text="hi")
        client.iter_dialogs = MagicMock(return_value=_async_gen([dialog]))

        await get_chats(client, folder="all unarchived")
        client.iter_dialogs.assert_called_once_with(folder=0)

    async def test_folder_archive(self):
        from telegram_mcp_server.tools.chats import get_chats

        client = MagicMock()
        dialog = _make_dialog(1, "Chat", unread_count=0, message_text="hi")
        client.iter_dialogs = MagicMock(return_value=_async_gen([dialog]))

        # _resolve_folder_id for "archive" does not call GetDialogFiltersRequest
        await get_chats(client, folder="archive")
        client.iter_dialogs.assert_called_once_with(folder=1)

    async def test_folder_custom(self):
        from telegram_mcp_server.tools.chats import get_chats

        custom = _make_filter(5, "Work")
        filters_result = MagicMock()
        filters_result.filters = [custom]

        client = AsyncMock()
        dialog = _make_dialog(1, "Chat", unread_count=0, message_text="hi")
        client.iter_dialogs = MagicMock(return_value=_async_gen([dialog]))
        client.return_value = filters_result

        await get_chats(client, folder="Work")
        client.iter_dialogs.assert_called_once_with(folder=5)

    async def test_unknown_folder_raises(self):
        import pytest

        from telegram_mcp_server.tools.chats import get_chats

        filters_result = MagicMock()
        filters_result.filters = []

        client = AsyncMock()
        client.return_value = filters_result

        with pytest.raises(ValueError, match="Unknown folder"):
            await get_chats(client, folder="Nonexistent")

    async def test_pagination(self):
        from telegram_mcp_server.tools.chats import get_chats

        client = MagicMock()
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

        result = await get_chats(client)
        chats = yaml.safe_load(result)
        # Both topics returned — no unread filter anymore.
        assert len(chats) == 2
        ids = {c["id"] for c in chats}
        assert encode_topic(500, 1) in ids
        assert encode_topic(500, 2) in ids

    async def test_last_sender_name_populated(self):
        from telegram_mcp_server.tools.chats import get_chats

        dialog = _make_dialog(
            1, "Chat", unread_count=1, message_text="hello", sender_id=42
        )

        entity = MagicMock()
        entity.first_name = "Alice"
        entity.last_name = None
        entity.username = "alice"
        entity.title = None

        client = MagicMock()
        client.iter_dialogs = MagicMock(return_value=_async_gen([dialog]))
        client.get_entity = AsyncMock(return_value=entity)

        result = await get_chats(client)
        chats = yaml.safe_load(result)
        assert "last_sender_name" in chats[0]
        assert "Alice" in chats[0]["last_sender_name"]
        assert "@alice" in chats[0]["last_sender_name"]

    async def test_last_sender_name_absent_when_no_sender(self):
        from telegram_mcp_server.tools.chats import get_chats

        dialog = _make_dialog(
            1, "Chat", unread_count=1, message_text="hello", sender_id=None
        )

        client = MagicMock()
        client.iter_dialogs = MagicMock(return_value=_async_gen([dialog]))
        client.get_entity = AsyncMock(side_effect=Exception("should not be called"))

        result = await get_chats(client)
        chats = yaml.safe_load(result)
        assert "last_sender_name" not in chats[0]

    async def test_last_sender_name_absent_when_entity_fetch_fails(self):
        from telegram_mcp_server.tools.chats import get_chats

        dialog = _make_dialog(
            1, "Chat", unread_count=1, message_text="hello", sender_id=99
        )

        client = MagicMock()
        client.iter_dialogs = MagicMock(return_value=_async_gen([dialog]))
        client.get_entity = AsyncMock(side_effect=Exception("network error"))

        result = await get_chats(client)
        chats = yaml.safe_load(result)
        assert "last_sender_name" not in chats[0]
