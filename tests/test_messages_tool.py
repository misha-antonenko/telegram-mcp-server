"""Tests for the get_messages and get_message tools."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from telegram_mcp_server.ids import encode_chat, encode_message, encode_topic


def _make_tl_msg(msg_id, text="hi"):
    msg = MagicMock()
    msg.id = msg_id
    msg.message = text
    msg.date = datetime(2024, 1, msg_id if msg_id <= 28 else 1, tzinfo=UTC)
    msg.media = None
    msg.from_id = None
    msg.peer_id = None
    msg.fwd_from = None
    msg.reply_to = None
    return msg


async def _async_gen(items):
    for item in items:
        yield item


def _make_client(tl_msgs):
    client = MagicMock()
    client.iter_messages = MagicMock(return_value=_async_gen(tl_msgs))
    client.get_entity = AsyncMock(side_effect=Exception("no entity"))
    return client


class TestGetMessages:
    async def test_returns_yaml_list(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([_make_tl_msg(1, "hello")])
        result = await get_messages(client, chat_id=encode_chat(99))
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, list)
        assert parsed[0]["text"] == "hello"
        assert parsed[0]["id"] == encode_message(99, 1)

    async def test_pagination(self):
        from telegram_mcp_server.tools.messages import get_messages

        msgs = [_make_tl_msg(i, f"msg{i}") for i in range(1, 21)]
        client = _make_client(msgs)
        result = await get_messages(client, chat_id=encode_chat(1), page_idx=0)
        assert len(yaml.safe_load(result)) == 16

        client = _make_client(msgs)
        result2 = await get_messages(client, chat_id=encode_chat(1), page_idx=1)
        assert len(yaml.safe_load(result2)) == 4

    async def test_topic_passes_reply_to(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([])
        await get_messages(client, chat_id=encode_topic(200, 5))
        client.iter_messages.assert_called_once_with(200, reply_to=5)

    async def test_regular_chat_no_reply_to(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([])
        await get_messages(client, chat_id=encode_chat(300))
        client.iter_messages.assert_called_once_with(300)

    async def test_search_query_passed_to_iter_messages(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([])
        await get_messages(client, chat_id=encode_chat(300), search_query="hello")
        client.iter_messages.assert_called_once_with(300, search="hello")

    async def test_empty_search_query_not_passed(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([])
        await get_messages(client, chat_id=encode_chat(300), search_query="")
        client.iter_messages.assert_called_once_with(300)

    async def test_none_chat_id_passes_none_peer(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([])
        await get_messages(client, chat_id=None, search_query="global")
        client.iter_messages.assert_called_once_with(None, search="global")

    async def test_page_ascending_order(self):
        from telegram_mcp_server.tools.messages import get_messages

        # iter_messages returns newest-first (ids 5,4,3,2,1)
        msgs = [_make_tl_msg(i) for i in [5, 4, 3, 2, 1]]
        client = _make_client(msgs)
        result = await get_messages(client, chat_id=encode_chat(1), page_idx=0)
        parsed = yaml.safe_load(result)
        ids = [p["id"] for p in parsed]
        # Within the page, oldest (id=1) should come first
        assert ids == [encode_message(1, i) for i in [1, 2, 3, 4, 5]]

    async def test_sender_name_populated(self):
        from telethon.tl.types import PeerUser

        from telegram_mcp_server.tools.messages import get_messages

        peer = MagicMock(spec=PeerUser)
        peer.user_id = 42

        tl_msg = _make_tl_msg(1, "hi")
        tl_msg.from_id = peer

        entity = MagicMock()
        entity.first_name = "Alice"
        entity.last_name = None
        entity.username = "alice"

        client = MagicMock()
        client.iter_messages = MagicMock(return_value=_async_gen([tl_msg]))
        client.get_entity = AsyncMock(return_value=entity)

        result = await get_messages(client, chat_id=encode_chat(1))
        parsed = yaml.safe_load(result)
        assert "sender_name" in parsed[0]
        assert "@alice" in parsed[0]["sender_name"]

    async def test_none_fields_omitted(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([_make_tl_msg(1, "hello")])
        result = await get_messages(client, chat_id=encode_chat(1))
        parsed = yaml.safe_load(result)
        row = parsed[0]
        assert "sender_id" not in row
        assert "sender_name" not in row
        assert "forwarded_from_id" not in row
        assert "reply_to_message_id" not in row

    async def test_sender_name_no_username(self):
        from telethon.tl.types import PeerUser

        from telegram_mcp_server.tools.messages import get_messages

        peer = MagicMock(spec=PeerUser)
        peer.user_id = 55

        tl_msg = _make_tl_msg(1, "hi")
        tl_msg.from_id = peer

        entity = MagicMock()
        entity.first_name = "Bob"
        entity.last_name = "Smith"
        entity.username = None
        entity.title = None

        client = MagicMock()
        client.iter_messages = MagicMock(return_value=_async_gen([tl_msg]))
        client.get_entity = AsyncMock(return_value=entity)

        result = await get_messages(client, chat_id=encode_chat(1))
        parsed = yaml.safe_load(result)
        sender_name = parsed[0]["sender_name"]
        assert "@" not in sender_name
        assert "Bob" in sender_name

    async def test_pages_descending_across_page_boundary(self):
        from telegram_mcp_server.tools.messages import get_messages

        # iter_messages returns 20 msgs newest-first: ids 20..1
        msgs = [_make_tl_msg(i) for i in range(20, 0, -1)]
        client = _make_client(msgs)
        result0 = await get_messages(client, chat_id=encode_chat(1), page_idx=0)

        client = _make_client(msgs)
        result1 = await get_messages(client, chat_id=encode_chat(1), page_idx=1)

        page0_ids = [p["id"] for p in yaml.safe_load(result0)]
        page1_ids = [p["id"] for p in yaml.safe_load(result1)]

        # Page 0 contains ids 5..20, page 1 ids 1..4 — oldest in page 0 > newest in page 1
        page0_nums = {int(pid.split(":")[2]) for pid in page0_ids}
        page1_nums = {int(pid.split(":")[2]) for pid in page1_ids}
        assert min(page0_nums) > max(page1_nums)

        # Within page 0: ascending (first element is oldest of that page)
        page0_nums_ordered = [int(pid.split(":")[2]) for pid in page0_ids]
        assert page0_nums_ordered == sorted(page0_nums_ordered)


class TestGetMessage:
    async def test_returns_single_message(self):
        from telegram_mcp_server.tools.messages import get_message

        tl_msg = _make_tl_msg(7, "single")
        client = MagicMock()
        client.get_messages = AsyncMock(return_value=tl_msg)
        client.get_entity = AsyncMock(side_effect=Exception("no entity"))

        result = await get_message(client, message_id=encode_message(99, 7))
        parsed = yaml.safe_load(result)
        assert parsed["id"] == encode_message(99, 7)
        assert parsed["text"] == "single"

    async def test_fetches_correct_peer_and_msg_id(self):
        from telegram_mcp_server.tools.messages import get_message

        tl_msg = _make_tl_msg(42, "x")
        client = MagicMock()
        client.get_messages = AsyncMock(return_value=tl_msg)
        client.get_entity = AsyncMock(side_effect=Exception("no entity"))

        await get_message(client, message_id=encode_message(1234, 42))
        client.get_messages.assert_called_once_with(1234, ids=42)

    async def test_sender_name_populated(self):
        from telethon.tl.types import PeerUser

        from telegram_mcp_server.tools.messages import get_message

        peer = MagicMock(spec=PeerUser)
        peer.user_id = 7

        tl_msg = _make_tl_msg(1, "hello")
        tl_msg.from_id = peer

        entity = MagicMock()
        entity.first_name = "Carol"
        entity.last_name = None
        entity.username = "carol"
        entity.title = None

        client = MagicMock()
        client.get_messages = AsyncMock(return_value=tl_msg)
        client.get_entity = AsyncMock(return_value=entity)

        result = await get_message(client, message_id=encode_message(1, 1))
        parsed = yaml.safe_load(result)
        assert "sender_name" in parsed
        assert "Carol" in parsed["sender_name"]
        assert "@carol" in parsed["sender_name"]

    async def test_not_found_raises(self):
        from telegram_mcp_server.tools.messages import get_message

        client = MagicMock()
        client.get_messages = AsyncMock(return_value=None)
        client.get_entity = AsyncMock(side_effect=Exception("no entity"))

        with pytest.raises(AssertionError):
            await get_message(client, message_id=encode_message(1, 999))
