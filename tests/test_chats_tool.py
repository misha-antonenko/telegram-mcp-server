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

        result = await get_chats(client, folder="all unarchived")
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, list)
        assert parsed[0]["id"] == encode_chat(1)

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

        await get_chats(client, folder="archive")
        client.iter_dialogs.assert_called_once_with(folder=1)

    async def test_folder_custom_filters_by_include_peers(self):
        from telethon.tl.types import User

        from telegram_mcp_server.tools.chats import get_chats

        peer_in = MagicMock()
        peer_in.user_id = 10
        peer_in.channel_id = None
        peer_in.chat_id = None

        custom = _make_filter(5, "Work")
        custom.pinned_peers = []
        custom.include_peers = [peer_in]
        custom.exclude_peers = []
        custom.contacts = False
        custom.non_contacts = False
        custom.groups = False
        custom.broadcasts = False
        custom.bots = False

        filters_result = MagicMock()
        filters_result.filters = [custom]

        # dialog_in: entity id=10 matches include_peers.
        dialog_in = _make_dialog(10, "Included", unread_count=0, message_text="hi")
        dialog_in.entity = MagicMock(spec=User)
        dialog_in.entity.id = 10
        dialog_in.entity.bot = False
        dialog_in.entity.contact = False
        dialog_in.entity.forum = False

        # dialog_out: not in any explicit or category list.
        dialog_out = _make_dialog(20, "Excluded", unread_count=0, message_text="bye")
        dialog_out.entity = MagicMock(spec=User)
        dialog_out.entity.id = 20
        dialog_out.entity.bot = False
        dialog_out.entity.contact = False
        dialog_out.entity.forum = False

        client = AsyncMock()
        client.iter_dialogs = MagicMock(
            return_value=_async_gen([dialog_in, dialog_out])
        )
        client.return_value = filters_result

        result = await get_chats(client, folder="Work")
        chats = yaml.safe_load(result)
        assert len(chats) == 1
        assert chats[0]["id"] == encode_chat(10)

    async def test_folder_custom_filters_by_category_flags(self):
        from telethon.tl.types import Channel, User

        from telegram_mcp_server.tools.chats import get_chats

        custom = _make_filter(5, "Channels")
        custom.pinned_peers = []
        custom.include_peers = []
        custom.exclude_peers = []
        custom.contacts = False
        custom.non_contacts = False
        custom.groups = False
        custom.broadcasts = True  # include broadcast channels
        custom.bots = False

        filters_result = MagicMock()
        filters_result.filters = [custom]

        # A broadcast channel — should be included.
        dialog_channel = _make_dialog(1, "Chan", unread_count=0, message_text="x")
        dialog_channel.entity = MagicMock(spec=Channel)
        dialog_channel.entity.id = 1
        dialog_channel.entity.megagroup = False
        dialog_channel.entity.gigagroup = False
        dialog_channel.entity.forum = False

        # A plain user — should not be included.
        dialog_user = _make_dialog(2, "User", unread_count=0, message_text="y")
        dialog_user.entity = MagicMock(spec=User)
        dialog_user.entity.id = 2
        dialog_user.entity.bot = False
        dialog_user.entity.contact = False
        dialog_user.entity.forum = False

        client = AsyncMock()
        client.iter_dialogs = MagicMock(
            return_value=_async_gen([dialog_channel, dialog_user])
        )
        client.return_value = filters_result

        result = await get_chats(client, folder="Channels")
        chats = yaml.safe_load(result)
        assert len(chats) == 1
        assert chats[0]["id"] == encode_chat(1)

    async def test_folder_custom_exclude_peers_override(self):
        from telethon.tl.types import User

        from telegram_mcp_server.tools.chats import get_chats

        exclude_peer = MagicMock()
        exclude_peer.user_id = 10
        exclude_peer.channel_id = None
        exclude_peer.chat_id = None

        custom = _make_filter(5, "Work")
        custom.pinned_peers = []
        custom.include_peers = []
        custom.exclude_peers = [exclude_peer]
        custom.contacts = True  # would include all contacts ...
        custom.non_contacts = False
        custom.groups = False
        custom.broadcasts = False
        custom.bots = False

        filters_result = MagicMock()
        filters_result.filters = [custom]

        # A contact that is also excluded — exclude wins.
        dialog = _make_dialog(10, "Bob", unread_count=0, message_text="hi")
        dialog.entity = MagicMock(spec=User)
        dialog.entity.id = 10
        dialog.entity.bot = False
        dialog.entity.contact = True
        dialog.entity.forum = False

        client = AsyncMock()
        client.iter_dialogs = MagicMock(return_value=_async_gen([dialog]))
        client.return_value = filters_result

        result = await get_chats(client, folder="Work")
        chats = yaml.safe_load(result)
        assert len(chats) == 0

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
        result = await get_chats(client, folder="all unarchived", page_idx=0)
        assert len(yaml.safe_load(result)) == 16

        client.iter_dialogs = MagicMock(return_value=_async_gen(dialogs))
        result2 = await get_chats(client, folder="all unarchived", page_idx=1)
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

        result = await get_chats(client, folder="all unarchived")
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

        result = await get_chats(client, folder="all unarchived")
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

        result = await get_chats(client, folder="all unarchived")
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

        result = await get_chats(client, folder="all unarchived")
        chats = yaml.safe_load(result)
        assert "last_sender_name" not in chats[0]
