"""Tests for the get_image tool."""

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telegram_mcp_server.ids import encode_message_media, encode_user_photo


class TestGetImage:
    async def test_message_photo_cached(self, tmp_path):
        from telegram_mcp_server.tools.media import get_image

        media_id = encode_message_media(100, 5)
        fake_bytes = b"\xff\xd8\xff" + b"\x00" * 10  # JPEG magic

        mock_msg = MagicMock()
        mock_msg.media = MagicMock()

        client = MagicMock()
        client.get_messages = AsyncMock(return_value=mock_msg)

        async def fake_download(msg, file=None):
            Path(file).write_bytes(fake_bytes)

        client.download_media = fake_download

        with patch("telegram_mcp_server.tools.media.get_settings") as mock_settings:
            settings = MagicMock()
            settings.image_cache_dir = tmp_path
            mock_settings.return_value = settings

            result = await get_image(client, media_id)

        assert result["mime_type"] == "image/jpeg"
        assert base64.b64decode(result["data"]) == fake_bytes

    async def test_cached_file_not_re_downloaded(self, tmp_path):
        from telegram_mcp_server.tools.media import get_image

        media_id = encode_message_media(1, 1)
        # Pre-populate cache
        import hashlib

        safe = hashlib.sha256(media_id.encode()).hexdigest()
        cache_file = tmp_path / f"{safe}.bin"
        fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10
        cache_file.write_bytes(fake_bytes)

        client = MagicMock()
        client.get_messages = AsyncMock()  # should NOT be called

        with patch("telegram_mcp_server.tools.media.get_settings") as mock_settings:
            settings = MagicMock()
            settings.image_cache_dir = tmp_path
            mock_settings.return_value = settings

            result = await get_image(client, media_id)

        client.get_messages.assert_not_called()
        assert result["mime_type"] == "image/png"

    async def test_invalid_media_id_raises(self, tmp_path):
        from telegram_mcp_server.tools.media import get_image

        client = MagicMock()
        with patch("telegram_mcp_server.tools.media.get_settings") as mock_settings:
            settings = MagicMock()
            settings.image_cache_dir = tmp_path
            mock_settings.return_value = settings

            with pytest.raises(ValueError):
                await get_image(client, "bad:id")

    async def test_user_photo(self, tmp_path):
        from telegram_mcp_server.tools.media import get_image

        media_id = encode_user_photo(99)
        fake_bytes = b"RIFF" + b"\x00" * 4 + b"WEBP"

        async def fake_download_profile(entity, file=None):
            Path(file).write_bytes(fake_bytes)

        client = MagicMock()
        client.get_profile_photos = AsyncMock(return_value=[MagicMock()])
        client.download_profile_photo = fake_download_profile

        with patch("telegram_mcp_server.tools.media.get_settings") as mock_settings:
            settings = MagicMock()
            settings.image_cache_dir = tmp_path
            mock_settings.return_value = settings

            result = await get_image(client, media_id)

        assert result["mime_type"] == "image/webp"
