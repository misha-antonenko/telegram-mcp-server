"""Tests for the search_messages tool."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from telegram_mcp_server.ids import encode_chat, encode_message


async def _async_gen(items):
    for item in items:
        yield item


def _make_client(tl_msgs):
    client = MagicMock()
    client.iter_messages = MagicMock(return_value=_async_gen(tl_msgs))
    client.get_entity = AsyncMock(side_effect=Exception("no entity"))
    return client


def _make_tl_msg(msg_id, text="hi"):
    from datetime import UTC, datetime

    msg = MagicMock()
    msg.id = msg_id
    msg.message = text
    msg.date = datetime(2024, 1, 1, tzinfo=UTC)
    msg.media = None
    msg.from_id = None
    msg.peer_id = None
    msg.fwd_from = None
    msg.reply_to = None
    return msg


class TestSearchMessages:
    async def test_passes_search_to_iter_messages(self):
        from telegram_mcp_server.tools.messages import search_messages

        client = _make_client([])
        await search_messages(client, query="hello", chat_id=encode_chat(1))
        client.iter_messages.assert_called_once_with(1, search="hello")

    async def test_global_search_when_no_chat_id(self):
        from telegram_mcp_server.tools.messages import search_messages

        client = _make_client([])
        await search_messages(client, query="hello")
        client.iter_messages.assert_called_once_with(None, search="hello")

    async def test_returns_yaml_list(self):
        from telegram_mcp_server.tools.messages import search_messages

        client = _make_client([_make_tl_msg(1, "match")])
        result = await search_messages(client, query="match", chat_id=encode_chat(5))
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, list)
        assert parsed[0]["text"] == "match"
        assert parsed[0]["id"] == encode_message(5, 1)

    async def test_empty_query_raises(self):
        from telegram_mcp_server.tools.messages import search_messages

        client = _make_client([])
        with pytest.raises((AssertionError, ValueError)):
            await search_messages(client, query="", chat_id=encode_chat(1))

    async def test_pagination(self):
        from telegram_mcp_server.tools.messages import search_messages

        msgs = [_make_tl_msg(i) for i in range(1, 21)]
        client = _make_client(msgs)
        result0 = await search_messages(
            client, query="x", chat_id=encode_chat(1), page_idx=0
        )
        assert len(yaml.safe_load(result0)) == 16

        client = _make_client(msgs)
        result1 = await search_messages(
            client, query="x", chat_id=encode_chat(1), page_idx=1
        )
        assert len(yaml.safe_load(result1)) == 4

    async def test_results_ascending_within_page(self):
        from telegram_mcp_server.tools.messages import search_messages

        # iter_messages returns newest-first
        msgs = [_make_tl_msg(i) for i in [5, 4, 3, 2, 1]]
        client = _make_client(msgs)
        result = await search_messages(client, query="x", chat_id=encode_chat(1))
        ids = [int(r["id"].split(":")[2]) for r in yaml.safe_load(result)]
        assert ids == sorted(ids)
