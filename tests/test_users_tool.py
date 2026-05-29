"""Tests for the get_user tool."""

from unittest.mock import AsyncMock, MagicMock

import yaml

from telegram_mcp_server.ids import encode_user_photo


class TestGetUser:
    async def test_returns_yaml(self):
        from telegram_mcp_server.tools.users import get_user

        user = MagicMock()
        user.id = 42
        user.first_name = "Alice"
        user.last_name = ""
        user.username = "alice"
        user.photo = MagicMock()

        full_user = MagicMock()
        full_user.about = "I am Alice"

        full = MagicMock()
        full.users = [user]
        full.full_user = full_user

        client = AsyncMock()
        client.return_value = full

        result = await get_user(client, user_id=42)
        parsed = yaml.safe_load(result)
        assert parsed["id"] == 42
        assert parsed["name"] == "Alice"
        assert parsed["nickname"] == "alice"
        assert parsed["bio"] == "I am Alice"
        assert parsed["profile_image_id"] == encode_user_photo(42)

    async def test_no_photo_no_bio(self):
        from telegram_mcp_server.tools.users import get_user

        user = MagicMock()
        user.id = 1
        user.first_name = "Bob"
        user.last_name = ""
        user.username = None
        user.photo = None

        full_user = MagicMock()
        full_user.about = None

        full = MagicMock()
        full.users = [user]
        full.full_user = full_user

        client = AsyncMock()
        client.return_value = full

        result = await get_user(client, user_id=1)
        parsed = yaml.safe_load(result)
        assert "profile_image_id" not in parsed
        assert "bio" not in parsed
