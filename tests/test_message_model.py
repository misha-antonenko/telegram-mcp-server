from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from telethon.tl.types import (
    Document,
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    DocumentAttributeImageSize,
    DocumentAttributeSticker,
    DocumentAttributeVideo,
    GeoPointEmpty,
    InputStickerSetEmpty,
    MessageMediaDocument,
    MessageMediaGeo,
    MessageMediaPhoto,
    MessageMediaWebPage,
    WebPageEmpty,
)

from telegram_mcp_server.ids import encode_message, encode_message_media
from telegram_mcp_server.models.message import Message

PEER_ID = 200
MSG_ID = 7
HANDLE = encode_message_media(PEER_ID, MSG_ID)


def _make_document(mime_type: str, attributes: list) -> MessageMediaDocument:
    document = Document(
        id=99999,
        access_hash=0,
        file_reference=b"",
        date=None,
        mime_type=mime_type,
        size=1,
        dc_id=1,
        attributes=attributes,
    )
    return MessageMediaDocument(document=document)


_MEDIA_CASES = {
    "photo": (MessageMediaPhoto(), {"image": HANDLE}),
    "image_as_file": (
        _make_document(
            "image/png",
            [DocumentAttributeImageSize(w=1, h=1), DocumentAttributeFilename("a.png")],
        ),
        {"image": HANDLE},
    ),
    "music": (
        _make_document("audio/mpeg", [DocumentAttributeAudio(duration=1)]),
        {"audio": HANDLE},
    ),
    "video": (
        _make_document("video/mp4", [DocumentAttributeVideo(duration=1, w=1, h=1)]),
        {"video": HANDLE},
    ),
    "text_file": (
        _make_document("text/markdown", [DocumentAttributeFilename("notes.md")]),
        {"file": HANDLE, "file_name": "notes.md"},
    ),
    "unnamed_file": (_make_document("application/pdf", []), {"file": HANDLE}),
    "webpage": (MessageMediaWebPage(webpage=WebPageEmpty(id=1)), {}),
}


def _make_msg(**kwargs):
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
        assert result.timestamp == "2024-06-15 12:30"

    @pytest.mark.parametrize("media, expected_fields", _MEDIA_CASES.values(), ids=_MEDIA_CASES)
    def test_media_fields_keep_caption(self, media, expected_fields):
        msg = _make_msg(id=MSG_ID, media=media, message="caption")
        dumped = Message.from_telethon(msg, peer_id=PEER_ID).model_dump()
        assert dumped.pop("text") == "caption"
        media_fields = {k: v for k, v in dumped.items() if k not in ("id", "timestamp")}
        assert media_fields == expected_fields

    def test_unsupported_media_replaced_by_handle(self):
        msg = _make_msg(id=MSG_ID, media=MessageMediaGeo(geo=GeoPointEmpty()), message="")
        assert Message.from_telethon(msg, peer_id=PEER_ID).text == HANDLE

    def test_sticker_replaced_by_xml(self):
        sticker = DocumentAttributeSticker(alt="😂", stickerset=InputStickerSetEmpty())
        msg = _make_msg(id=MSG_ID, media=_make_document("image/webp", [sticker]))
        result = Message.from_telethon(msg, peer_id=PEER_ID)
        assert result.text == '<sticker id="99999" alt="😂"/>'

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
