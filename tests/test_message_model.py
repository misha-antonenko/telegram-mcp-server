"""Tests for the Message model."""

from datetime import datetime, timezone
from unittest.mock import MagicMock


from telegram_mcp_server.ids import encode_message, encode_message_media
from telegram_mcp_server.models.message import Message


def _make_msg(**kwargs):
    """Build a minimal mock Telethon Message."""
    msg = MagicMock()
    msg.id = kwargs.get("id", 1)
    msg.date = kwargs.get("date", datetime(2024, 1, 1, tzinfo=timezone.utc))
    msg.message = kwargs.get("message", "")
    msg.media = kwargs.get("media", None)
    msg.from_id = kwargs.get("from_id", None)
    msg.peer_id = kwargs.get("peer_id", None)
    msg.fwd_from = kwargs.get("fwd_from", None)
    msg.reply_to = kwargs.get("reply_to", None)
    return msg


class TestMessageFromTelethon:
    def test_plain_text(self):
        msg = _make_msg(id=5, message="Hello world")
        result = Message.from_telethon(msg, peer_id=100)
        assert result.id == encode_message(100, 5)
        assert result.text == "Hello world"
        assert result.reply_to_message_id is None
        assert result.forwarded_from_id is None

    def test_timestamp_format(self):
        dt = datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
        msg = _make_msg(date=dt)
        result = Message.from_telethon(msg, peer_id=1)
        assert "2024-06-15" in result.timestamp

    def test_media_replaced_by_id(self):
        from telethon.tl.types import MessageMediaPhoto

        photo = MagicMock(spec=MessageMediaPhoto)
        msg = _make_msg(id=7, media=photo, message="")
        result = Message.from_telethon(msg, peer_id=200)
        assert result.text == encode_message_media(200, 7)

    def test_sticker_replaced_by_xml(self):
        from telethon.tl.types import (
            DocumentAttributeSticker,
            MessageMediaDocument,
        )

        attr = MagicMock(spec=DocumentAttributeSticker)
        attr.alt = "😂"
        doc = MagicMock()
        doc.id = 99999
        doc.attributes = [attr]
        media = MagicMock(spec=MessageMediaDocument)
        media.document = doc
        msg = _make_msg(id=3, media=media)
        result = Message.from_telethon(msg, peer_id=1)
        assert '<sticker id="99999" alt="😂"/>' == result.text

    def test_reply_to_parsed(self):
        reply = MagicMock()
        reply.reply_to_msg_id = 42
        msg = _make_msg(id=99, reply_to=reply)
        result = Message.from_telethon(msg, peer_id=5)
        assert result.reply_to_message_id == encode_message(5, 42)

    def test_sender_id_from_user(self):
        from telethon.tl.types import PeerUser

        peer = MagicMock(spec=PeerUser)
        peer.user_id = 777
        msg = _make_msg(from_id=peer)
        result = Message.from_telethon(msg, peer_id=1)
        assert result.sender_id == 777

    def test_forwarded_from_user(self):
        from telethon.tl.types import PeerUser

        fwd_peer = MagicMock(spec=PeerUser)
        fwd_peer.user_id = 123
        fwd = MagicMock()
        fwd.from_id = fwd_peer
        msg = _make_msg(fwd_from=fwd)
        result = Message.from_telethon(msg, peer_id=1)
        assert result.forwarded_from_id == 123

    def test_webpage_media_shows_text(self):
        from telethon.tl.types import MessageMediaWebPage

        webpage = MagicMock(spec=MessageMediaWebPage)
        msg = _make_msg(id=10, media=webpage, message="Check this link")
        result = Message.from_telethon(msg, peer_id=1)
        # Webpage media should NOT replace text with a media ID
        assert result.text == "Check this link"

    def test_to_dict_keys(self):
        msg = _make_msg(message="hi")
        result = Message.from_telethon(msg, peer_id=1)
        d = result.to_dict()
        # sender_id/sender_name/forwarded_from_id/reply_to_message_id are None → omitted
        assert set(d.keys()) == {"id", "timestamp", "text"}

    def test_to_dict_omits_none_fields(self):
        msg = _make_msg(message="hi")
        result = Message.from_telethon(msg, peer_id=1)
        d = result.to_dict()
        assert "sender_id" not in d
        assert "sender_name" not in d
        assert "forwarded_from_id" not in d
        assert "reply_to_message_id" not in d

    def test_to_dict_includes_sender_name_when_set(self):
        msg = _make_msg(message="hi")
        result = Message.from_telethon(msg, peer_id=1)
        result.sender_name = "Alice (@alice)"
        d = result.to_dict()
        assert d["sender_name"] == "Alice (@alice)"
