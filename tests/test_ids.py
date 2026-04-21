"""Tests for the opaque ID scheme."""

import pytest

from telegram_mcp_server.ids import (
    ChatRef,
    MediaRef,
    MessageRef,
    decode_chat,
    decode_media,
    decode_message,
    encode_chat,
    encode_message,
    encode_message_media,
    encode_topic,
    encode_user_photo,
)


class TestChatIds:
    def test_regular_chat_roundtrip(self):
        encoded = encode_chat(12345)
        ref = decode_chat(encoded)
        assert ref == ChatRef(peer_id=12345)
        assert not ref.is_topic

    def test_negative_peer_id(self):
        encoded = encode_chat(-100123456789)
        ref = decode_chat(encoded)
        assert ref.peer_id == -100123456789

    def test_topic_roundtrip(self):
        encoded = encode_topic(111, 5)
        ref = decode_chat(encoded)
        assert ref == ChatRef(peer_id=111, topic_id=5)
        assert ref.is_topic

    def test_encode_via_chatref(self):
        ref = ChatRef(peer_id=42, topic_id=7)
        assert ref.encode() == encode_topic(42, 7)

    def test_invalid_prefix_raises(self):
        with pytest.raises(ValueError, match="Invalid chat ID"):
            decode_chat("x:123")


class TestMessageIds:
    def test_roundtrip(self):
        encoded = encode_message(999, 42)
        ref = decode_message(encoded)
        assert ref == MessageRef(peer_id=999, msg_id=42)

    def test_negative_peer(self):
        encoded = encode_message(-100987, 1)
        ref = decode_message(encoded)
        assert ref.peer_id == -100987
        assert ref.msg_id == 1

    def test_invalid_prefix_raises(self):
        with pytest.raises(ValueError):
            decode_message("c:1:2")


class TestMediaIds:
    def test_message_photo_roundtrip(self):
        encoded = encode_message_media(555, 10)
        ref = decode_media(encoded)
        assert ref == MediaRef(kind="mp", peer_id=555, msg_id=10)

    def test_user_photo_roundtrip(self):
        encoded = encode_user_photo(777)
        ref = decode_media(encoded)
        assert ref == MediaRef(kind="up", peer_id=777)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            decode_media("bad:1")
