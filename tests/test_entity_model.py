"""Tests for the Entity models."""

from unittest.mock import MagicMock

from telegram_mcp_server.ids import encode_user_photo
from telegram_mcp_server.models.entity import ChannelEntity, GroupEntity, UserEntity


def _make_full_user(
    user_id=1,
    first="Alice",
    last="Smith",
    username="alice",
    about="Bio text",
    has_photo=True,
):
    user = MagicMock()
    user.id = user_id
    user.first_name = first
    user.last_name = last
    user.username = username
    user.photo = MagicMock() if has_photo else None

    full_user = MagicMock()
    full_user.about = about

    full = MagicMock()
    full.users = [user]
    full.full_user = full_user
    return full


def _make_channel(
    channel_id=100,
    title="Test Channel",
    username="testchannel",
    has_photo=True,
):
    channel = MagicMock()
    channel.id = channel_id
    channel.title = title
    channel.username = username
    channel.photo = MagicMock() if has_photo else None
    return channel


def _make_full_channel(about="Channel description"):
    full_chat = MagicMock()
    full_chat.about = about
    full = MagicMock()
    full.full_chat = full_chat
    return full


def _make_chat(chat_id=200, title="Test Group", has_photo=True):
    chat = MagicMock()
    chat.id = chat_id
    chat.title = title
    chat.photo = MagicMock() if has_photo else None
    return chat


def _make_full_chat(about="Group description"):
    full_chat = MagicMock()
    full_chat.about = about
    full = MagicMock()
    full.full_chat = full_chat
    return full


class TestUserEntity:
    def test_basic_fields(self):
        full = _make_full_user(
            user_id=5, first="Alice", last="Smith", username="alice", about="Hello"
        )
        entity = UserEntity.from_full(full)
        assert entity.id == 5
        assert entity.type == "user"
        assert entity.name == "Alice Smith"
        assert entity.username == "alice"
        assert entity.bio == "Hello"

    def test_profile_image_id_set(self):
        full = _make_full_user(user_id=5, has_photo=True)
        entity = UserEntity.from_full(full)
        assert entity.profile_image_id == encode_user_photo(5)

    def test_no_profile_photo(self):
        full = _make_full_user(has_photo=False)
        entity = UserEntity.from_full(full)
        assert entity.profile_image_id is None

    def test_no_bio(self):
        full = _make_full_user(about=None)
        entity = UserEntity.from_full(full)
        assert entity.bio is None

    def test_name_no_last(self):
        full = _make_full_user(first="Bob", last="")
        entity = UserEntity.from_full(full)
        assert entity.name == "Bob"

    def test_model_dump_keys(self):
        full = _make_full_user()
        d = UserEntity.from_full(full).model_dump()
        assert set(d.keys()) == {
            "type",
            "id",
            "name",
            "username",
            "bio",
            "profile_image_id",
        }

    def test_omits_none(self):
        full = _make_full_user(username=None, about=None, has_photo=False)
        d = UserEntity.from_full(full).model_dump()
        assert "username" not in d
        assert "bio" not in d
        assert "profile_image_id" not in d


class TestChannelEntity:
    def test_basic_fields(self):
        channel = _make_channel(channel_id=100, title="News", username="news")
        full = _make_full_channel(about="Daily news")
        entity = ChannelEntity.from_full(full, channel)
        assert entity.id == 100
        assert entity.type == "channel"
        assert entity.name == "News"
        assert entity.username == "news"
        assert entity.about == "Daily news"

    def test_no_username(self):
        channel = _make_channel(username=None)
        full = _make_full_channel()
        entity = ChannelEntity.from_full(full, channel)
        assert entity.username is None

    def test_no_photo(self):
        channel = _make_channel(has_photo=False)
        full = _make_full_channel()
        entity = ChannelEntity.from_full(full, channel)
        assert entity.profile_image_id is None

    def test_no_about(self):
        channel = _make_channel()
        full = _make_full_channel(about=None)
        entity = ChannelEntity.from_full(full, channel)
        assert entity.about is None


class TestGroupEntity:
    def test_from_supergroup(self):
        channel = _make_channel(channel_id=101, title="Dev Chat", username="devchat")
        full = _make_full_channel(about="Developers only")
        entity = GroupEntity.from_full_channel(full, channel)
        assert entity.id == 101
        assert entity.type == "group"
        assert entity.name == "Dev Chat"
        assert entity.username == "devchat"
        assert entity.about == "Developers only"

    def test_from_basic_chat(self):
        chat = _make_chat(chat_id=200, title="Friends")
        full = _make_full_chat(about="Just friends chatting")
        entity = GroupEntity.from_full_chat(full, chat)
        assert entity.id == 200
        assert entity.type == "group"
        assert entity.name == "Friends"
        assert entity.username is None
        assert entity.about == "Just friends chatting"

    def test_no_about(self):
        chat = _make_chat()
        full = _make_full_chat(about=None)
        entity = GroupEntity.from_full_chat(full, chat)
        assert entity.about is None

    def test_no_photo(self):
        chat = _make_chat(has_photo=False)
        full = _make_full_chat()
        entity = GroupEntity.from_full_chat(full, chat)
        assert entity.profile_image_id is None
