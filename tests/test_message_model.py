"""Tests for the Message model."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from telegram_mcp_server.ids import encode_message, encode_message_media
from telegram_mcp_server.models.message import Message


def _make_msg(**kwargs):
    """Build a minimal mock Telethon Message."""
    msg = MagicMock()
    msg.id = kwargs.get("id", 1)
    msg.date = kwargs.get("date", datetime(2024, 1, 1, tzinfo=UTC))
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
        dt = datetime(2024, 6, 15, 12, 30, 0, tzinfo=UTC)
        msg = _make_msg(date=dt)
        result = Message.from_telethon(msg, peer_id=1)
        assert result.timestamp == "2024-06-15 16:30"  # UTC+4

    def test_photo_caption_and_image_field(self):
        from telethon.tl.types import MessageMediaPhoto

        photo = MagicMock(spec=MessageMediaPhoto)
        msg = _make_msg(id=7, media=photo, message="my caption")
        result = Message.from_telethon(msg, peer_id=200)
        assert result.text == "my caption"
        assert result.image == encode_message_media(200, 7)
        assert result.audio is None
        assert result.video is None

    def test_photo_no_caption(self):
        from telethon.tl.types import MessageMediaPhoto

        photo = MagicMock(spec=MessageMediaPhoto)
        msg = _make_msg(id=7, media=photo, message="")
        result = Message.from_telethon(msg, peer_id=200)
        assert result.text == ""
        assert result.image == encode_message_media(200, 7)

    def test_audio_caption_and_audio_field(self):
        from telethon.tl.types import DocumentAttributeAudio, MessageMediaDocument

        attr = MagicMock(spec=DocumentAttributeAudio)
        doc = MagicMock()
        doc.id = 111
        doc.attributes = [attr]
        media = MagicMock(spec=MessageMediaDocument)
        media.document = doc
        msg = _make_msg(id=8, media=media, message="song caption")
        result = Message.from_telethon(msg, peer_id=10)
        assert result.text == "song caption"
        assert result.audio == encode_message_media(10, 8)
        assert result.image is None
        assert result.video is None

    def test_video_caption_and_video_field(self):
        from telethon.tl.types import DocumentAttributeVideo, MessageMediaDocument

        attr = MagicMock(spec=DocumentAttributeVideo)
        doc = MagicMock()
        doc.id = 222
        doc.attributes = [attr]
        media = MagicMock(spec=MessageMediaDocument)
        media.document = doc
        msg = _make_msg(id=9, media=media, message="clip caption")
        result = Message.from_telethon(msg, peer_id=10)
        assert result.text == "clip caption"
        assert result.video == encode_message_media(10, 9)
        assert result.image is None
        assert result.audio is None

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

    def test_model_dump_omits_none_fields(self):
        msg = _make_msg(message="hi")
        result = Message.from_telethon(msg, peer_id=1)
        d = result.model_dump()
        assert set(d.keys()) == {"id", "timestamp", "text"}
        assert "sender" not in d
        assert "sender_id" not in d
        assert "forwarded_from_id" not in d
        assert "reply_to_message_id" not in d

    def test_model_dump_includes_sender_when_set(self):
        msg = _make_msg(message="hi")
        result = Message.from_telethon(msg, peer_id=1)
        result.sender = "Alice (@alice)"
        d = result.model_dump()
        assert d["sender"] == "Alice (@alice)"
