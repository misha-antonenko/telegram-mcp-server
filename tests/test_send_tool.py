"""Tests for the send_message and forward_message tools."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegramify_markdown.entity import MessageEntity as TmEntity
from telethon.tl import types as tl

from telegram_mcp_server.ids import encode_chat, encode_message, encode_topic


class TestToTelethonEntities:
    """Unit tests for _to_telethon_entities() covering every supported entity type."""

    def _convert(self, entities):
        from telegram_mcp_server.tools.send import _to_telethon_entities
        return _to_telethon_entities(entities)

    def _entity(self, **kwargs):
        defaults = dict(type="bold", offset=0, length=5, url=None, language=None, custom_emoji_id=None)
        defaults.update(kwargs)
        return TmEntity(**defaults)

    def test_bold(self):
        result = self._convert([self._entity(type="bold", offset=3, length=7)])
        assert len(result) == 1
        assert isinstance(result[0], tl.MessageEntityBold)
        assert result[0].offset == 3
        assert result[0].length == 7

    def test_italic(self):
        result = self._convert([self._entity(type="italic", offset=1, length=4)])
        assert len(result) == 1
        assert isinstance(result[0], tl.MessageEntityItalic)
        assert result[0].offset == 1
        assert result[0].length == 4

    def test_code(self):
        result = self._convert([self._entity(type="code", offset=0, length=8)])
        assert len(result) == 1
        assert isinstance(result[0], tl.MessageEntityCode)

    def test_pre_with_language(self):
        result = self._convert([self._entity(type="pre", offset=0, length=9, language="python")])
        assert len(result) == 1
        assert isinstance(result[0], tl.MessageEntityPre)
        assert result[0].language == "python"

    def test_pre_without_language_defaults_to_empty_string(self):
        result = self._convert([self._entity(type="pre", offset=0, length=9, language=None)])
        assert isinstance(result[0], tl.MessageEntityPre)
        assert result[0].language == ""

    def test_strikethrough(self):
        result = self._convert([self._entity(type="strikethrough", offset=0, length=6)])
        assert len(result) == 1
        assert isinstance(result[0], tl.MessageEntityStrike)

    def test_underline(self):
        result = self._convert([self._entity(type="underline", offset=0, length=10)])
        assert len(result) == 1
        assert isinstance(result[0], tl.MessageEntityUnderline)

    def test_spoiler(self):
        result = self._convert([self._entity(type="spoiler", offset=0, length=7)])
        assert len(result) == 1
        assert isinstance(result[0], tl.MessageEntitySpoiler)

    def test_text_link(self):
        result = self._convert([self._entity(type="text_link", offset=0, length=10, url="https://example.com")])
        assert len(result) == 1
        assert isinstance(result[0], tl.MessageEntityTextUrl)
        assert result[0].url == "https://example.com"

    def test_text_link_without_url_defaults_to_empty_string(self):
        result = self._convert([self._entity(type="text_link", offset=0, length=5, url=None)])
        assert isinstance(result[0], tl.MessageEntityTextUrl)
        assert result[0].url == ""

    def test_custom_emoji(self):
        result = self._convert([self._entity(type="custom_emoji", offset=0, length=2, custom_emoji_id="99887766")])
        assert len(result) == 1
        assert isinstance(result[0], tl.MessageEntityCustomEmoji)
        assert result[0].document_id == 99887766

    def test_unknown_type_is_skipped(self):
        result = self._convert([self._entity(type="mention"), self._entity(type="bold")])
        assert len(result) == 1
        assert isinstance(result[0], tl.MessageEntityBold)

    def test_multiple_entities_preserve_order(self):
        entities = [
            self._entity(type="bold", offset=0, length=4),
            self._entity(type="italic", offset=5, length=6),
            self._entity(type="code", offset=12, length=3),
        ]
        result = self._convert(entities)
        assert len(result) == 3
        assert isinstance(result[0], tl.MessageEntityBold)
        assert isinstance(result[1], tl.MessageEntityItalic)
        assert isinstance(result[2], tl.MessageEntityCode)

    def test_empty_list(self):
        assert self._convert([]) == []


class TestParseMarkdown:
    """Integration tests for _parse_markdown() using real telegramify_markdown.convert() output."""

    def _parse(self, text):
        from telegram_mcp_server.tools.send import _parse_markdown
        return _parse_markdown(text)

    def test_plain_text_no_entities(self):
        plain, entities = self._parse("Hello, world!")
        assert plain == "Hello, world!"
        assert entities == []

    def test_plain_text_no_backslash_escaping(self):
        plain, entities = self._parse("bugs. end!")
        assert "\\" not in plain
        assert entities == []

    def test_bold(self):
        plain, entities = self._parse("**bold**")
        assert plain == "bold"
        assert len(entities) == 1
        assert isinstance(entities[0], tl.MessageEntityBold)
        assert entities[0].offset == 0
        assert entities[0].length == 4

    def test_italic(self):
        plain, entities = self._parse("_italic_")
        assert plain == "italic"
        assert isinstance(entities[0], tl.MessageEntityItalic)

    def test_inline_code(self):
        plain, entities = self._parse("`code`")
        assert plain == "code"
        assert isinstance(entities[0], tl.MessageEntityCode)

    def test_code_block_with_language(self):
        plain, entities = self._parse("```python\nprint('hi')\n```")
        assert "print" in plain
        assert isinstance(entities[0], tl.MessageEntityPre)
        assert entities[0].language == "python"

    def test_strikethrough(self):
        plain, entities = self._parse("~~struck~~")
        assert plain == "struck"
        assert isinstance(entities[0], tl.MessageEntityStrike)

    def test_spoiler(self):
        plain, entities = self._parse("||spoiler||")
        assert plain == "spoiler"
        assert isinstance(entities[0], tl.MessageEntitySpoiler)

    def test_hyperlink(self):
        plain, entities = self._parse("[click here](https://example.com)")
        assert plain == "click here"
        assert isinstance(entities[0], tl.MessageEntityTextUrl)
        assert entities[0].url == "https://example.com"

    def test_mixed_formatting(self):
        plain, entities = self._parse("Hello **world** and `code`")
        assert "world" in plain
        assert "code" in plain
        assert any(isinstance(e, tl.MessageEntityBold) for e in entities)
        assert any(isinstance(e, tl.MessageEntityCode) for e in entities)



    async def test_no_backslash_escaping_in_plain_text(self):
        """Regression: plain text with periods/punctuation must not gain backslash escapes."""
        from telegram_mcp_server.tools.send import send_message

        sent = MagicMock()
        sent.id = 1
        client = MagicMock()
        client.send_message = AsyncMock(return_value=sent)

        text = "Why do programmers prefer dark mode? 🌑\n\nBecause light attracts bugs. 🐛"
        await send_message(client, chat_id=encode_chat(1), text=text)

        call_kwargs = client.send_message.call_args
        sent_message = call_kwargs.kwargs.get("message") or call_kwargs.args[1]
        assert "\\" not in sent_message, f"Unexpected backslash escapes in: {sent_message!r}"
        assert "bugs. 🐛" in sent_message

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
