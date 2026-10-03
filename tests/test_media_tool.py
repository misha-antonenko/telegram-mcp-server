import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image as PillowImage
from telethon.tl.types import Document, DocumentAttributeFilename, MessageMediaDocument

from telegram_mcp_server.ids import encode_message_media, encode_user_photo
from telegram_mcp_server.tools.images import normalize_image
from telegram_mcp_server.tools.media import get_image

MAX_SIDE_PX = 64


def _encode_image(image_format: str, size: tuple[int, int], mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    PillowImage.new(mode, size).save(buffer, format=image_format)
    return buffer.getvalue()


def _document_message(mime_type: str) -> MagicMock:
    document = Document(
        id=1,
        access_hash=0,
        file_reference=b"",
        date=None,
        mime_type=mime_type,
        size=10,
        dc_id=1,
        attributes=[DocumentAttributeFilename("x")],
    )
    tl_message = MagicMock()
    tl_message.media = MessageMediaDocument(document=document)
    return tl_message


@pytest.fixture(autouse=True)
def settings(tmp_path):
    settings = MagicMock(image_cache_dir=tmp_path, image_max_side_px=MAX_SIDE_PX)
    with patch("telegram_mcp_server.tools.media.get_settings", return_value=settings):
        yield settings


@pytest.mark.parametrize(
    "image_format, mode, size, expected_mime_type, expected_size, is_passthrough",
    [
        ("JPEG", "RGB", (32, 16), "image/jpeg", (32, 16), True),
        ("PNG", "RGBA", (16, 16), "image/png", (16, 16), True),
        ("JPEG", "RGB", (256, 128), "image/jpeg", (64, 32), False),
        ("WEBP", "RGB", (128, 128), "image/png", (64, 64), False),
        ("BMP", "RGB", (8, 8), "image/png", (8, 8), False),
        ("TIFF", "RGB", (8, 8), "image/png", (8, 8), False),
    ],
)
def test_normalize_image(
    image_format, mode, size, expected_mime_type, expected_size, is_passthrough
):
    data = _encode_image(image_format, size, mode)
    normalized = normalize_image(data, MAX_SIDE_PX)
    assert normalized.mime_type == expected_mime_type
    with PillowImage.open(io.BytesIO(normalized.data)) as decoded:
        assert decoded.size == expected_size
    assert (normalized.data == data) == is_passthrough


async def test_image_sent_as_file_is_downloaded_once():
    data = _encode_image("PNG", (8, 8))
    client = MagicMock()
    client.get_messages = AsyncMock(return_value=_document_message("image/png"))
    client.download_media = AsyncMock(return_value=data)
    media_id = encode_message_media(100, 5)

    first = await get_image(client, media_id)
    second = await get_image(client, media_id)

    assert first == second
    assert first.mime_type == "image/png"
    client.download_media.assert_awaited_once()


async def test_non_image_rejected_before_download():
    client = MagicMock()
    client.get_messages = AsyncMock(return_value=_document_message("application/pdf"))
    client.download_media = AsyncMock()

    with pytest.raises(ValueError, match="is file, not image"):
        await get_image(client, encode_message_media(100, 5))
    client.download_media.assert_not_awaited()


async def test_profile_photo():
    client = MagicMock()
    client.download_profile_photo = AsyncMock(return_value=_encode_image("JPEG", (8, 8)))

    result = await get_image(client, encode_user_photo(99))

    assert result.mime_type == "image/jpeg"
    client.download_profile_photo.assert_awaited_once_with(99, file=bytes)


async def test_missing_profile_photo_raises():
    client = MagicMock()
    client.download_profile_photo = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="No profile photo"):
        await get_image(client, encode_user_photo(99))


async def test_invalid_media_id_raises():
    with pytest.raises(ValueError, match="Invalid media ID"):
        await get_image(MagicMock(), "bad:id")
