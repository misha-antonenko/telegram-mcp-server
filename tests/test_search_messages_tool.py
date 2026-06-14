"""Tests for the search_messages tool."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml
from telethon.helpers import TotalList

from telegram_mcp_server.ids import encode_chat, encode_message


def _make_tl_msg(msg_id, text="hi", msg_date: datetime | None = None):
    msg = MagicMock()
    msg.id = msg_id
    msg.message = text
    msg.date = msg_date or datetime(2024, 1, 1, tzinfo=UTC)
    msg.media = None
    msg.from_id = None
    msg.peer_id = None
    msg.fwd_from = None
    msg.reply_to = None
    return msg


def _make_client(tl_msgs):
    """Build a mock client for search_messages (newest-first, no reverse)."""
    client = MagicMock()

    async def _get_messages_side_effect(*args, **kwargs):
        limit = kwargs.get("limit", len(tl_msgs))
        add_offset = kwargs.get("add_offset", 0)
        offset_date = kwargs.get("offset_date")
        filtered = tl_msgs
        # No reverse: offset_date means messages *before* this date (exclusive).
        if offset_date is not None:
            filtered = [m for m in filtered if m.date < offset_date]
        page = filtered[add_offset : add_offset + limit]
        result = TotalList(page)
        result.total = len(filtered)
        return result

    client.get_messages = AsyncMock(side_effect=_get_messages_side_effect)
    client.get_entity = AsyncMock(side_effect=Exception("no entity"))

    dialog = MagicMock()
    dialog.read_inbox_max_id = 0
    dialogs_result = MagicMock()
    dialogs_result.dialogs = [dialog]

    async def _call_side_effect(*_args, **_kwargs):
        return dialogs_result

    client.side_effect = _call_side_effect

    return client


def _parse_messages(result: str) -> list[dict]:
    return yaml.safe_load(result)["messages"]


class TestSearchMessages:
    async def test_passes_search_to_get_messages(self):
        from telegram_mcp_server.tools.messages import search_messages

        client = _make_client([])
        await search_messages(client, query="hello", chat_id=encode_chat(1))
        client.get_messages.assert_called_once_with(
            1, search="hello", limit=16, add_offset=0
        )

    async def test_global_search_when_no_chat_id(self):
        from telegram_mcp_server.tools.messages import search_messages

        client = _make_client([])
        await search_messages(client, query="hello")
        client.get_messages.assert_called_once_with(
            None, search="hello", limit=16, add_offset=0
        )

    async def test_returns_yaml_envelope(self):
        from telegram_mcp_server.tools.messages import search_messages

        client = _make_client([_make_tl_msg(1, "match")])
        result = await search_messages(client, query="match", chat_id=encode_chat(5))
        parsed = _parse_messages(result)
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
        assert len(_parse_messages(result0)) == 16

        client = _make_client(msgs)
        result1 = await search_messages(
            client, query="x", chat_id=encode_chat(1), page_idx=1
        )
        assert len(_parse_messages(result1)) == 4

    async def test_results_ascending_within_page(self):
        """Within a page, messages are reversed to oldest-first."""
        from telegram_mcp_server.tools.messages import search_messages

        # Newest-first from API.
        msgs = [_make_tl_msg(i) for i in [5, 4, 3, 2, 1]]
        client = _make_client(msgs)
        result = await search_messages(client, query="x", chat_id=encode_chat(1))
        ids = [int(r["id"].split(":")[2]) for r in _parse_messages(result)]
        assert ids == sorted(ids)

    async def test_until_passes_offset_date(self):
        from telegram_mcp_server.tools.messages import search_messages

        client = _make_client([])
        await search_messages(
            client, query="x", chat_id=encode_chat(1), until=date(2024, 6, 15)
        )
        call_kwargs = client.get_messages.call_args.kwargs
        assert call_kwargs["offset_date"] == datetime(2024, 6, 15, tzinfo=UTC)

    async def test_since_filters_messages(self):
        from telegram_mcp_server.tools.messages import search_messages

        # Newest-first.
        msgs = [
            _make_tl_msg(3, "new", datetime(2024, 6, 20, tzinfo=UTC)),
            _make_tl_msg(2, "mid", datetime(2024, 6, 10, tzinfo=UTC)),
            _make_tl_msg(1, "old", datetime(2024, 6, 1, tzinfo=UTC)),
        ]
        client = _make_client(msgs)
        result = await search_messages(
            client, query="x", chat_id=encode_chat(1), since=date(2024, 6, 10)
        )
        texts = [m["text"] for m in _parse_messages(result)]
        assert "old" not in texts
        assert "mid" in texts
        assert "new" in texts

    async def test_since_and_until_combined(self):
        from telegram_mcp_server.tools.messages import search_messages

        # Newest-first.
        msgs = [
            _make_tl_msg(3, "new", datetime(2024, 6, 20, tzinfo=UTC)),
            _make_tl_msg(2, "mid", datetime(2024, 6, 10, tzinfo=UTC)),
            _make_tl_msg(1, "old", datetime(2024, 6, 1, tzinfo=UTC)),
        ]
        client = _make_client(msgs)
        result = await search_messages(
            client,
            query="x",
            chat_id=encode_chat(1),
            since=date(2024, 6, 5),
            until=date(2024, 6, 15),
        )
        call_kwargs = client.get_messages.call_args.kwargs
        assert call_kwargs["offset_date"] == datetime(2024, 6, 15, tzinfo=UTC)
        texts = [m["text"] for m in _parse_messages(result)]
        assert texts == ["mid"]
