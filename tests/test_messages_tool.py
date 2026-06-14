"""Tests for the get_messages, count_messages, and get_message tools."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml
from telethon.helpers import TotalList

from telegram_mcp_server.ids import encode_chat, encode_message, encode_topic


def _make_tl_msg(msg_id, text="hi", msg_date: datetime | None = None):
    msg = MagicMock()
    msg.id = msg_id
    msg.message = text
    if msg_date is not None:
        msg.date = msg_date
    else:
        msg.date = datetime(2024, 1, msg_id if msg_id <= 28 else 1, tzinfo=UTC)
    msg.media = None
    msg.from_id = None
    msg.peer_id = None
    msg.fwd_from = None
    msg.reply_to = None
    return msg


def _make_client(tl_msgs, read_inbox_max_id: int = 0):
    """Build a mock client for get_messages (reverse=True, oldest-first)."""
    client = MagicMock()

    async def _get_messages_side_effect(*args, **kwargs):
        limit = kwargs.get("limit", len(tl_msgs))
        add_offset = kwargs.get("add_offset", 0)
        offset_date = kwargs.get("offset_date")
        filtered = tl_msgs
        # With reverse=True, offset_date is the start point (messages >= offset_date).
        if offset_date is not None:
            filtered = [m for m in filtered if m.date >= offset_date]
        page = filtered[add_offset : add_offset + limit]
        result = TotalList(page)
        result.total = len(filtered)
        return result

    client.get_messages = AsyncMock(side_effect=_get_messages_side_effect)
    client.get_entity = AsyncMock(side_effect=Exception("no entity"))

    dialog = MagicMock()
    dialog.read_inbox_max_id = read_inbox_max_id
    dialogs_result = MagicMock()
    dialogs_result.dialogs = [dialog]

    async def _call_side_effect(*_args, **_kwargs):
        return dialogs_result

    client.side_effect = _call_side_effect

    return client


def _make_sender_client(tl_msgs):
    """Build a client mock for sender tests (custom get_entity)."""
    client = MagicMock()

    async def _get_messages_side_effect(*args, **kwargs):
        result = TotalList(tl_msgs)
        result.total = len(tl_msgs)
        return result

    client.get_messages = AsyncMock(side_effect=_get_messages_side_effect)
    return client


def _parse_messages(result: str) -> list[dict]:
    """Extract the messages list from the YAML envelope."""
    return yaml.safe_load(result)["messages"]


def _parse_envelope(result: str) -> dict:
    """Parse the full YAML envelope (remaining_pages + messages)."""
    return yaml.safe_load(result)


class TestGetMessages:
    async def test_returns_yaml_envelope(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([_make_tl_msg(1, "hello")])
        result = await get_messages(client, chat_id=encode_chat(99))
        envelope = _parse_envelope(result)
        assert "remaining_pages" in envelope
        assert "messages" in envelope
        assert isinstance(envelope["messages"], list)
        assert envelope["messages"][0]["text"] == "hello"
        assert envelope["messages"][0]["id"] == encode_message(99, 1)

    async def test_pagination(self):
        from telegram_mcp_server.tools.messages import get_messages

        # Oldest-first: ids 1..20
        msgs = [_make_tl_msg(i, f"msg{i}") for i in range(1, 21)]
        client = _make_client(msgs)
        result = await get_messages(client, chat_id=encode_chat(1), page_idx=0)
        assert len(_parse_messages(result)) == 16

        client = _make_client(msgs)
        result2 = await get_messages(client, chat_id=encode_chat(1), page_idx=1)
        assert len(_parse_messages(result2)) == 4

    async def test_topic_passes_reply_to(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([])
        await get_messages(client, chat_id=encode_topic(200, 5))
        client.get_messages.assert_called_once_with(
            200, reverse=True, reply_to=5, limit=16, add_offset=0
        )

    async def test_regular_chat_no_reply_to(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([])
        await get_messages(client, chat_id=encode_chat(300))
        client.get_messages.assert_called_once_with(
            300, reverse=True, limit=16, add_offset=0
        )

    async def test_oldest_first_order(self):
        from telegram_mcp_server.tools.messages import get_messages

        # Already oldest-first (as reverse=True would return).
        msgs = [_make_tl_msg(i) for i in [1, 2, 3, 4, 5]]
        client = _make_client(msgs)
        result = await get_messages(client, chat_id=encode_chat(1), page_idx=0)
        parsed = _parse_messages(result)
        ids = [int(p["id"].split(":")[2]) for p in parsed]
        assert ids == [1, 2, 3, 4, 5]

    async def test_sender_populated_in_group(self):
        """In groups, sender is the formatted name."""
        from telethon.tl.types import Chat, PeerUser

        from telegram_mcp_server.tools.messages import get_messages

        peer = MagicMock(spec=PeerUser)
        peer.user_id = 42

        tl_msg = _make_tl_msg(1, "hi")
        tl_msg.from_id = peer

        group_entity = MagicMock(spec=Chat)

        user_entity = MagicMock()
        user_entity.first_name = "Alice"
        user_entity.last_name = None
        user_entity.username = "alice"

        async def _get_entity(entity_id):
            if entity_id == 1:
                return group_entity
            return user_entity

        client = _make_sender_client([tl_msg])
        client.get_entity = AsyncMock(side_effect=_get_entity)

        result = await get_messages(client, chat_id=encode_chat(1))
        parsed = _parse_messages(result)
        assert "sender" in parsed[0]
        assert "@alice" in parsed[0]["sender"]

    async def test_none_fields_omitted(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([_make_tl_msg(1, "hello")])
        result = await get_messages(client, chat_id=encode_chat(1))
        row = _parse_messages(result)[0]
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

        client = _make_sender_client([tl_msg])
        client.get_entity = AsyncMock(side_effect=_get_entity)

        result = await get_messages(client, chat_id=encode_chat(1))
        parsed = _parse_messages(result)
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

        # Oldest-first: me first, then them.
        client = _make_sender_client([msg_from_me, msg_from_them])
        client.get_entity = AsyncMock(return_value=dm_entity)

        orig = client_module._owner_id
        client_module._owner_id = my_id
        try:
            result = await get_messages(client, chat_id=encode_chat(999))
            parsed = _parse_messages(result)
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

        client = _make_sender_client([tl_msg])
        client.get_entity = AsyncMock(return_value=channel_entity)

        result = await get_messages(client, chat_id=encode_chat(123))
        parsed = _parse_messages(result)
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

        client = _make_sender_client([tl_msg])
        client.get_entity = AsyncMock(return_value=channel_entity)

        result = await get_messages(client, chat_id=encode_chat(123))
        parsed = _parse_messages(result)
        assert parsed[0]["sender"] == "Admin Name"

    async def test_pages_ascending_across_page_boundary(self):
        from telegram_mcp_server.tools.messages import get_messages

        # Oldest-first: ids 1..20
        msgs = [_make_tl_msg(i) for i in range(1, 21)]
        client = _make_client(msgs)
        result0 = await get_messages(client, chat_id=encode_chat(1), page_idx=0)

        client = _make_client(msgs)
        result1 = await get_messages(client, chat_id=encode_chat(1), page_idx=1)

        page0_nums = [int(p["id"].split(":")[2]) for p in _parse_messages(result0)]
        page1_nums = [int(p["id"].split(":")[2]) for p in _parse_messages(result1)]

        # Page 0 = ids 1..16 (oldest), page 1 = ids 17..20.
        assert max(page0_nums) < min(page1_nums)
        assert page0_nums == sorted(page0_nums)
        assert page1_nums == sorted(page1_nums)

    async def test_unread_field_set_for_unread_messages(self):
        from telegram_mcp_server.tools.messages import get_messages

        # Oldest-first.
        msgs = [_make_tl_msg(i) for i in [1, 2, 3]]
        client = _make_client(msgs, read_inbox_max_id=2)
        result = await get_messages(client, chat_id=encode_chat(1))
        parsed = _parse_messages(result)
        by_id = {int(r["id"].split(":")[2]): r for r in parsed}
        assert "unread" not in by_id[1]
        assert "unread" not in by_id[2]
        assert by_id[3].get("unread") is True

    async def test_unread_field_absent_when_all_read(self):
        from telegram_mcp_server.tools.messages import get_messages

        msgs = [_make_tl_msg(i) for i in [1, 2, 3]]
        client = _make_client(msgs, read_inbox_max_id=100)
        result = await get_messages(client, chat_id=encode_chat(1))
        for row in _parse_messages(result):
            assert "unread" not in row

    async def test_since_passes_offset_date(self):
        from telegram_mcp_server.tools.messages import get_messages

        client = _make_client([])
        await get_messages(client, chat_id=encode_chat(1), since=date(2024, 6, 15))
        call_kwargs = client.get_messages.call_args.kwargs
        assert call_kwargs["offset_date"] == datetime(2024, 6, 15, tzinfo=UTC)

    async def test_since_filters_server_side(self):
        from telegram_mcp_server.tools.messages import get_messages

        # Oldest-first.
        msgs = [
            _make_tl_msg(1, "old", datetime(2024, 6, 1, tzinfo=UTC)),
            _make_tl_msg(2, "mid", datetime(2024, 6, 10, tzinfo=UTC)),
            _make_tl_msg(3, "new", datetime(2024, 6, 20, tzinfo=UTC)),
        ]
        client = _make_client(msgs)
        result = await get_messages(
            client, chat_id=encode_chat(1), since=date(2024, 6, 10)
        )
        texts = [m["text"] for m in _parse_messages(result)]
        assert "old" not in texts
        assert "mid" in texts
        assert "new" in texts

    async def test_remaining_pages_reported(self):
        from telegram_mcp_server.tools.messages import get_messages

        msgs = [_make_tl_msg(i) for i in range(1, 21)]
        client = _make_client(msgs)
        envelope = _parse_envelope(
            await get_messages(client, chat_id=encode_chat(1), page_idx=0)
        )
        assert envelope["remaining_pages"] == 1

    async def test_remaining_pages_zero_on_last_page(self):
        from telegram_mcp_server.tools.messages import get_messages

        msgs = [_make_tl_msg(i) for i in range(1, 21)]
        client = _make_client(msgs)
        envelope = _parse_envelope(
            await get_messages(client, chat_id=encode_chat(1), page_idx=1)
        )
        assert envelope["remaining_pages"] == 0

    async def test_remaining_pages_zero_when_fits_in_one_page(self):
        from telegram_mcp_server.tools.messages import get_messages

        msgs = [_make_tl_msg(i) for i in [1, 2, 3]]
        client = _make_client(msgs)
        envelope = _parse_envelope(
            await get_messages(client, chat_id=encode_chat(1), page_idx=0)
        )
        assert envelope["remaining_pages"] == 0


class TestCountMessages:
    async def test_returns_total(self):
        from telegram_mcp_server.tools.messages import count_messages

        msgs = [_make_tl_msg(i) for i in range(1, 21)]
        client = _make_client(msgs)
        total = await count_messages(client, chat_id=encode_chat(1))
        assert total == 20

    async def test_with_since(self):
        from telegram_mcp_server.tools.messages import count_messages

        msgs = [
            _make_tl_msg(1, "old", datetime(2024, 6, 1, tzinfo=UTC)),
            _make_tl_msg(2, "mid", datetime(2024, 6, 10, tzinfo=UTC)),
            _make_tl_msg(3, "new", datetime(2024, 6, 20, tzinfo=UTC)),
        ]
        client = _make_client(msgs)
        total = await count_messages(
            client, chat_id=encode_chat(1), since=date(2024, 6, 10)
        )
        assert total == 2

    async def test_passes_limit_zero(self):
        from telegram_mcp_server.tools.messages import count_messages

        client = _make_client([_make_tl_msg(1)])
        await count_messages(client, chat_id=encode_chat(1))
        call_kwargs = client.get_messages.call_args.kwargs
        assert call_kwargs["limit"] == 0


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
