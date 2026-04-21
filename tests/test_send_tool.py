"""Tests for the send_message and forward_message tools."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from telegram_mcp_server.ids import encode_chat, encode_message, encode_topic


class TestSendMessage:
    async def test_plain_message(self):
        from telegram_mcp_server.tools.send import send_message

        sent = MagicMock()
        sent.id = 100
        client = MagicMock()
        client.send_message = AsyncMock(return_value=sent)

        result = await send_message(client, chat_id=encode_chat(1), text="Hello")
        assert "100" in result
        client.send_message.assert_called_once()
        call_kwargs = client.send_message.call_args
        assert call_kwargs.args[0] == 1

    async def test_reply_to(self):
        from telegram_mcp_server.tools.send import send_message

        sent = MagicMock()
        sent.id = 200
        client = MagicMock()
        client.send_message = AsyncMock(return_value=sent)

        await send_message(
            client,
            chat_id=encode_chat(5),
            text="Reply",
            reply_to_message_id=encode_message(5, 42),
        )
        call_kwargs = client.send_message.call_args
        assert call_kwargs.kwargs.get("reply_to") == 42

    async def test_with_single_attachment(self):
        from telegram_mcp_server.tools.send import send_message

        sent = MagicMock()
        sent.id = 300
        client = MagicMock()
        client.send_file = AsyncMock(return_value=sent)

        await send_message(client, chat_id=encode_chat(1), text="pic", attachments=["/tmp/photo.jpg"])
        client.send_file.assert_called_once()


class TestForwardMessage:
    async def test_forward(self):
        from telegram_mcp_server.tools.send import forward_message

        client = MagicMock()
        client.forward_messages = AsyncMock(return_value=None)

        result = await forward_message(
            client,
            message_id=encode_message(10, 99),
            to_chat_id=encode_chat(20),
        )
        assert "Forwarded" in result
        client.forward_messages.assert_called_once_with(
            entity=20,
            messages=99,
            from_peer=10,
        )

    async def test_forward_invalid_message_id_raises(self):
        from telegram_mcp_server.tools.send import forward_message

        client = MagicMock()
        with pytest.raises(ValueError):
            await forward_message(client, message_id="bad", to_chat_id=encode_chat(1))
