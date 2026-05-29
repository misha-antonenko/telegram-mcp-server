"""Tests for the search_chats tool."""

from unittest.mock import MagicMock

import pytest
import yaml

from telegram_mcp_server.ids import encode_chat


def _make_dialog(peer_id, title, unread_count=0):
    entity = MagicMock()
    entity.id = peer_id
    entity.title = title
    entity.forum = False

    last_msg = MagicMock()
    last_msg.message = ""
    last_msg.text = ""
    last_msg.media = None
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


class TestSearchChats:
    async def test_substring_match_case_insensitive(self):
        from telegram_mcp_server.tools.chats import search_chats

        client = MagicMock()
        dialogs = [
            _make_dialog(1, "Python Dev"),
            _make_dialog(2, "Random Chat"),
            _make_dialog(3, "python tips"),
        ]
        client.iter_dialogs = MagicMock(return_value=_async_gen(dialogs))

        result = await search_chats(client, query="python")
        chats = yaml.safe_load(result)
        assert len(chats) == 2
        names = {c["name"] for c in chats}
        assert names == {"Python Dev", "python tips"}

    async def test_no_match_returns_empty(self):
        from telegram_mcp_server.tools.chats import search_chats

        client = MagicMock()
        dialogs = [_make_dialog(1, "Alpha"), _make_dialog(2, "Beta")]
        client.iter_dialogs = MagicMock(return_value=_async_gen(dialogs))

        result = await search_chats(client, query="xyz")
        assert yaml.safe_load(result) == []

    async def test_limit_respected(self):
        from telegram_mcp_server.tools.chats import search_chats

        client = MagicMock()
        dialogs = [_make_dialog(i, f"Chat {i}") for i in range(20)]
        client.iter_dialogs = MagicMock(return_value=_async_gen(dialogs))

        result = await search_chats(client, query="Chat", limit=5)
        assert len(yaml.safe_load(result)) == 5

    async def test_default_limit_is_16(self):
        from telegram_mcp_server.tools.chats import search_chats

        client = MagicMock()
        dialogs = [_make_dialog(i, f"Chat {i}") for i in range(30)]
        client.iter_dialogs = MagicMock(return_value=_async_gen(dialogs))

        result = await search_chats(client, query="Chat")
        assert len(yaml.safe_load(result)) == 16

    async def test_returns_yaml_with_correct_ids(self):
        from telegram_mcp_server.tools.chats import search_chats

        client = MagicMock()
        dialogs = [_make_dialog(42, "My Group")]
        client.iter_dialogs = MagicMock(return_value=_async_gen(dialogs))

        result = await search_chats(client, query="My Group")
        chats = yaml.safe_load(result)
        assert chats[0]["id"] == encode_chat(42)
        assert chats[0]["name"] == "My Group"

    async def test_empty_query_raises(self):
        from telegram_mcp_server.tools.chats import search_chats

        client = MagicMock()
        client.iter_dialogs = MagicMock(return_value=_async_gen([]))
        with pytest.raises((AssertionError, ValueError)):
            await search_chats(client, query="")

    async def test_iter_dialogs_called_without_archived_filter(self):
        from telegram_mcp_server.tools.chats import search_chats

        client = MagicMock()
        client.iter_dialogs = MagicMock(return_value=_async_gen([]))
        await search_chats(client, query="x")
        # search across all dialogs, no archived filter
        client.iter_dialogs.assert_called_once_with()
