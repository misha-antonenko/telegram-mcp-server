"""Tests for the get_entity tool."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from telegram_mcp_server.ids import encode_user_photo


def _make_user(user_id=42, first="Alice", last="", username="alice", has_photo=True):
    from telethon.tl.types import User

    user = MagicMock(spec=User)
    user.id = user_id
    user.first_name = first
    user.last_name = last
    user.username = username
    user.photo = MagicMock() if has_photo else None
    return user


def _make_full_user(user, about="I am a user"):
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
    megagroup=False,
    gigagroup=False,
    has_photo=True,
):
    from telethon.tl.types import Channel

    channel = MagicMock(spec=Channel)
    channel.id = channel_id
    channel.title = title
    channel.username = username
    channel.megagroup = megagroup
    channel.gigagroup = gigagroup
    channel.photo = MagicMock() if has_photo else None
    return channel


def _make_full_channel(about="Channel description"):
    full_chat = MagicMock()
    full_chat.about = about
    full = MagicMock()
    full.full_chat = full_chat
    return full


def _make_chat(chat_id=200, title="Test Group", has_photo=True):
    from telethon.tl.types import Chat

    chat = MagicMock(spec=Chat)
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


class TestGetEntityUser:
    async def test_returns_user_yaml(self):
        from telegram_mcp_server.tools.entities import get_entity

        user = _make_user(user_id=42, first="Alice", username="alice")
        full = _make_full_user(user, about="I am Alice")

        client = AsyncMock()
        client.get_entity = AsyncMock(return_value=user)
        client.return_value = full

        result = await get_entity(client, entity_id=42)
        parsed = yaml.safe_load(result)

        assert parsed["type"] == "user"
        assert parsed["id"] == 42
        assert parsed["name"] == "Alice"
        assert parsed["username"] == "alice"
        assert parsed["bio"] == "I am Alice"
        assert parsed["profile_image_id"] == encode_user_photo(42)

    async def test_no_photo_no_bio(self):
        from telegram_mcp_server.tools.entities import get_entity

        user = _make_user(user_id=1, first="Bob", username=None, has_photo=False)
        full = _make_full_user(user, about=None)

        client = AsyncMock()
        client.get_entity = AsyncMock(return_value=user)
        client.return_value = full

        result = await get_entity(client, entity_id=1)
        parsed = yaml.safe_load(result)

        assert parsed["type"] == "user"
        assert "profile_image_id" not in parsed
        assert "bio" not in parsed
        assert "username" not in parsed


class TestGetEntityChannel:
    async def test_returns_channel_yaml(self):
        from telegram_mcp_server.tools.entities import get_entity

        channel = _make_channel(
            channel_id=100, title="News", username="news", megagroup=False
        )
        full = _make_full_channel(about="Daily news")

        client = AsyncMock()
        client.get_entity = AsyncMock(return_value=channel)
        client.return_value = full

        result = await get_entity(client, entity_id=100)
        parsed = yaml.safe_load(result)

        assert parsed["type"] == "channel"
        assert parsed["id"] == 100
        assert parsed["name"] == "News"
        assert parsed["username"] == "news"
        assert parsed["about"] == "Daily news"

    async def test_supergroup_returns_group(self):
        from telegram_mcp_server.tools.entities import get_entity

        channel = _make_channel(
            channel_id=101, title="Dev Chat", username="devchat", megagroup=True
        )
        full = _make_full_channel(about="Developers only")

        client = AsyncMock()
        client.get_entity = AsyncMock(return_value=channel)
        client.return_value = full

        result = await get_entity(client, entity_id=101)
        parsed = yaml.safe_load(result)

        assert parsed["type"] == "group"
        assert parsed["name"] == "Dev Chat"

    async def test_gigagroup_returns_group(self):
        from telegram_mcp_server.tools.entities import get_entity

        channel = _make_channel(channel_id=102, megagroup=False, gigagroup=True)
        full = _make_full_channel()

        client = AsyncMock()
        client.get_entity = AsyncMock(return_value=channel)
        client.return_value = full

        result = await get_entity(client, entity_id=102)
        parsed = yaml.safe_load(result)

        assert parsed["type"] == "group"


class TestGetEntityChat:
    async def test_returns_group_yaml(self):
        from telegram_mcp_server.tools.entities import get_entity

        chat = _make_chat(chat_id=200, title="Friends")
        full = _make_full_chat(about="Just friends")

        client = AsyncMock()
        client.get_entity = AsyncMock(return_value=chat)
        client.return_value = full

        result = await get_entity(client, entity_id=200)
        parsed = yaml.safe_load(result)

        assert parsed["type"] == "group"
        assert parsed["id"] == 200
        assert parsed["name"] == "Friends"
        assert parsed["about"] == "Just friends"
        assert "username" not in parsed


class TestGetEntityUnknown:
    async def test_raises_for_unknown_type(self):
        from telegram_mcp_server.tools.entities import get_entity

        unknown = MagicMock()

        client = AsyncMock()
        client.get_entity = AsyncMock(return_value=unknown)

        with pytest.raises(ValueError, match="Unknown entity type"):
            await get_entity(client, entity_id=999)
