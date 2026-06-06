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


def _make_client(tl_msgs, read_inbox_max_id: int = 0):
    client = MagicMock()

    def _iter_messages_side_effect(*args, **kwargs):
        limit = kwargs.get("limit", len(tl_msgs))
        add_offset = kwargs.get("add_offset", 0)
        return _async_gen(tl_msgs[add_offset : add_offset + limit])

    client.iter_messages = MagicMock(side_effect=_iter_messages_side_effect)
    client.get_entity = AsyncMock(side_effect=Exception("no entity"))

    dialog = MagicMock()
    dialog.read_inbox_max_id = read_inbox_max_id
    dialogs_result = MagicMock()
    dialogs_result.dialogs = [dialog]

    # `await client(GetPeerDialogsRequest(...))` requires client() to return a coroutine.
    async def _call_side_effect(*_args, **_kwargs):
        return dialogs_result

    client.side_effect = _call_side_effect

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
        client.iter_messages.assert_called_once_with(
            200, reply_to=5, limit=16, add_offset=0
        )

    async def test_regular_chat_no_reply_to(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([])
        await get_messages(client, chat_id=encode_chat(300))
        client.iter_messages.assert_called_once_with(300, limit=16, add_offset=0)

    async def test_search_query_passed_to_iter_messages(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([])
        await get_messages(client, chat_id=encode_chat(300), search_query="hello")
        client.iter_messages.assert_called_once_with(
            300, search="hello", limit=16, add_offset=0
        )

    async def test_empty_search_query_not_passed(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([])
        await get_messages(client, chat_id=encode_chat(300), search_query="")
        client.iter_messages.assert_called_once_with(300, limit=16, add_offset=0)

    async def test_none_chat_id_passes_none_peer(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([])
        await get_messages(client, chat_id=None, search_query="global")
        client.iter_messages.assert_called_once_with(
            None, search="global", limit=16, add_offset=0
        )

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

    async def test_sender_populated_in_group(self):
        """In groups, sender is the formatted name."""
        from telethon.tl.types import Chat, PeerUser

        from telegram_mcp_server.tools.messages import get_messages

        peer = MagicMock(spec=PeerUser)
        peer.user_id = 42

        tl_msg = _make_tl_msg(1, "hi")
        tl_msg.from_id = peer

        # Chat entity for the group (to determine chat type).
        group_entity = MagicMock(spec=Chat)

        # User entity for the sender.
        user_entity = MagicMock()
        user_entity.first_name = "Alice"
        user_entity.last_name = None
        user_entity.username = "alice"

        async def _get_entity(entity_id):
            if entity_id == 1:
                return group_entity
            return user_entity

        client = MagicMock()
        client.iter_messages = MagicMock(
            side_effect=lambda *a, **kw: _async_gen([tl_msg])
        )
        client.get_entity = AsyncMock(side_effect=_get_entity)

        result = await get_messages(client, chat_id=encode_chat(1))
        parsed = yaml.safe_load(result)
        assert "sender" in parsed[0]
        assert "@alice" in parsed[0]["sender"]

    async def test_none_fields_omitted(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([_make_tl_msg(1, "hello")])
        result = await get_messages(client, chat_id=encode_chat(1))
        parsed = yaml.safe_load(result)
        row = parsed[0]
        assert "sender" not in row
        assert "sender_id" not in row
        assert "forwarded_from_id" not in row
        assert "reply_to_message_id" not in row

    async def test_sender_no_username_in_group(self):
        """In groups, sender name works without username."""
        from telethon.tl.types import Chat, PeerUser

        from telegram_mcp_server.tools.messages import get_messages

        peer = MagicMock(spec=PeerUser)
        peer.user_id = 55

        tl_msg = _make_tl_msg(1, "hi")
        tl_msg.from_id = peer

        group_entity = MagicMock(spec=Chat)
        user_entity = MagicMock()
        user_entity.first_name = "Bob"
        user_entity.last_name = "Smith"
        user_entity.username = None
        user_entity.title = None

        async def _get_entity(entity_id):
            if entity_id == 1:
                return group_entity
            return user_entity

        client = MagicMock()
        client.iter_messages = MagicMock(
            side_effect=lambda *a, **kw: _async_gen([tl_msg])
        )
        client.get_entity = AsyncMock(side_effect=_get_entity)

        result = await get_messages(client, chat_id=encode_chat(1))
        parsed = yaml.safe_load(result)
        sender = parsed[0]["sender"]
        assert "@" not in sender
        assert "Bob" in sender

    async def test_sender_me_them_in_dm(self):
        """In DMs, sender is 'me' or 'them'."""
        import telegram_mcp_server.client as client_module
        from telethon.tl.types import PeerUser, User

        from telegram_mcp_server.tools.messages import get_messages

        my_id = 100

        peer_me = MagicMock(spec=PeerUser)
        peer_me.user_id = my_id
        peer_them = MagicMock(spec=PeerUser)
        peer_them.user_id = 999

        msg_from_me = _make_tl_msg(1, "from me")
        msg_from_me.from_id = peer_me
        msg_from_them = _make_tl_msg(2, "from them")
        msg_from_them.from_id = peer_them

        dm_entity = MagicMock(spec=User)

        client = MagicMock()
        client.iter_messages = MagicMock(
            side_effect=lambda *a, **kw: _async_gen([msg_from_them, msg_from_me])
        )
        client.get_entity = AsyncMock(return_value=dm_entity)

        orig = client_module._owner_id
        client_module._owner_id = my_id
        try:
            result = await get_messages(client, chat_id=encode_chat(999))
            parsed = yaml.safe_load(result)
        finally:
            client_module._owner_id = orig

        assert parsed[0]["sender"] == "me"
        assert parsed[1]["sender"] == "them"

    async def test_sender_omitted_in_channel(self):
        """In channels without post_author, sender is omitted."""
        from telethon.tl.types import Channel

        from telegram_mcp_server.tools.messages import get_messages

        tl_msg = _make_tl_msg(1, "channel post")
        tl_msg.post_author = None

        channel_entity = MagicMock(spec=Channel)
        channel_entity.megagroup = False
        channel_entity.gigagroup = False

        client = MagicMock()
        client.iter_messages = MagicMock(
            side_effect=lambda *a, **kw: _async_gen([tl_msg])
        )
        client.get_entity = AsyncMock(return_value=channel_entity)

        result = await get_messages(client, chat_id=encode_chat(123))
        parsed = yaml.safe_load(result)
        assert "sender" not in parsed[0]

    async def test_sender_post_author_in_channel(self):
        """In channels with signed posts, sender is the post_author."""
        from telethon.tl.types import Channel

        from telegram_mcp_server.tools.messages import get_messages

        tl_msg = _make_tl_msg(1, "signed post")
        tl_msg.post_author = "Admin Name"

        channel_entity = MagicMock(spec=Channel)
        channel_entity.megagroup = False
        channel_entity.gigagroup = False

        client = MagicMock()
        client.iter_messages = MagicMock(
            side_effect=lambda *a, **kw: _async_gen([tl_msg])
        )
        client.get_entity = AsyncMock(return_value=channel_entity)

        result = await get_messages(client, chat_id=encode_chat(123))
        parsed = yaml.safe_load(result)
        assert parsed[0]["sender"] == "Admin Name"

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

        # Page 0 contains ids 20..5 (newest 16), page 1 ids 4..1 — oldest in page 0 > newest in page 1
        page0_nums = {int(pid.split(":")[2]) for pid in page0_ids}
        page1_nums = {int(pid.split(":")[2]) for pid in page1_ids}
        assert min(page0_nums) > max(page1_nums)

        # Within page 0: ascending (first element is oldest of that page)
        page0_nums_ordered = [int(pid.split(":")[2]) for pid in page0_ids]
        assert page0_nums_ordered == sorted(page0_nums_ordered)

    async def test_unread_field_set_for_unread_messages(self):
        from telegram_mcp_server.tools.messages import get_messages

        # Messages 1–3; read up to id=2 → only id=3 is unread.
        msgs = [_make_tl_msg(i) for i in [3, 2, 1]]  # newest-first
        client = _make_client(msgs, read_inbox_max_id=2)
        result = await get_messages(client, chat_id=encode_chat(1))
        parsed = yaml.safe_load(result)
        # page is oldest-first: [id=1, id=2, id=3]
        by_id = {int(r["id"].split(":")[2]): r for r in parsed}
        assert "unread" not in by_id[1]
        assert "unread" not in by_id[2]
        assert by_id[3].get("unread") is True

    async def test_unread_field_absent_when_all_read(self):
        from telegram_mcp_server.tools.messages import get_messages

        msgs = [_make_tl_msg(i) for i in [3, 2, 1]]
        client = _make_client(msgs, read_inbox_max_id=100)
        result = await get_messages(client, chat_id=encode_chat(1))
        for row in yaml.safe_load(result):
            assert "unread" not in row


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

    async def test_sender_populated_in_group(self):
        """get_message in a group shows full sender name."""
        from telethon.tl.types import Chat, PeerUser

        from telegram_mcp_server.tools.messages import get_message

        peer = MagicMock(spec=PeerUser)
        peer.user_id = 7

        tl_msg = _make_tl_msg(1, "hello")
        tl_msg.from_id = peer

        group_entity = MagicMock(spec=Chat)
        user_entity = MagicMock()
        user_entity.first_name = "Carol"
        user_entity.last_name = None
        user_entity.username = "carol"
        user_entity.title = None

        async def _get_entity(entity_id):
            if entity_id == 1:
                return group_entity
            return user_entity

        client = MagicMock()
        client.get_messages = AsyncMock(return_value=tl_msg)
        client.get_entity = AsyncMock(side_effect=_get_entity)

        result = await get_message(client, message_id=encode_message(1, 1))
        parsed = yaml.safe_load(result)
        assert "sender" in parsed
        assert "Carol" in parsed["sender"]
        assert "@carol" in parsed["sender"]

    async def test_not_found_raises(self):
        from telegram_mcp_server.tools.messages import get_message

        client = MagicMock()
        client.get_messages = AsyncMock(return_value=None)
        client.get_entity = AsyncMock(side_effect=Exception("no entity"))

        with pytest.raises(AssertionError):
            await get_message(client, message_id=encode_message(1, 999))
