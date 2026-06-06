"""Tests for the Chat model."""

from unittest.mock import MagicMock

from telegram_mcp_server.ids import encode_chat, encode_topic
from telegram_mcp_server.models.chat import Chat


def _make_dialog(peer_id=1, title="Chat", unread_count=0, message_text=""):
    entity = MagicMock()
    entity.id = peer_id
    entity.title = title
    entity.username = None
    entity.forum = False

    last_msg = MagicMock()
    last_msg.message = message_text
    last_msg.text = message_text
    last_msg.media = None

    dialog = MagicMock()
    dialog.entity = entity
    dialog.unread_count = unread_count
    dialog.message = last_msg
    return dialog


class TestChatFromDialog:
    def test_basic_fields(self):
        dialog = _make_dialog(peer_id=42, title="Test", unread_count=3)
        chat = Chat.from_dialog(dialog)
        assert chat.id == encode_chat(42)
        assert chat.name == "Test"
        assert chat.has_unread is True

    def test_no_unread(self):
        dialog = _make_dialog(unread_count=0)
        chat = Chat.from_dialog(dialog)
        assert chat.has_unread is False

    def test_model_dump_keys(self):
        dialog = _make_dialog()
        d = Chat.from_dialog(dialog).model_dump()
        assert set(d.keys()) == {"id", "name", "has_unread"}


class TestChatFromTopic:
    def test_basic_fields(self):
        topic = MagicMock()
        topic.id = 7
        topic.title = "My Topic"
        chat = Chat.from_topic(
            supergroup_id=111,
            forum_name="My Forum",
            topic=topic,
            has_unread=True,
        )
        assert chat.id == encode_topic(111, 7)
        assert chat.name == "My Forum / My Topic"
        assert chat.has_unread is True
