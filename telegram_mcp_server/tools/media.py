from __future__ import annotations

import asyncio
import hashlib
import uuid
from typing import TYPE_CHECKING

from telegram_mcp_server.ids import MediaKind, MediaRef, decode_media
from telegram_mcp_server.models.media import MediaCategory, classify_media
from telegram_mcp_server.settings import get_settings
from telegram_mcp_server.tools.images import EncodedImage, normalize_image

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from telethon import TelegramClient
    from telethon.tl.types import Message as TLMessage


async def get_image(client: TelegramClient, media_id: str) -> EncodedImage:
    ref = decode_media(media_id)
    if ref.kind == MediaKind.PROFILE_PHOTO:
        data = await _download_profile_photo(client, media_id, ref)
    else:
        data = await _download_message_media(client, media_id, MediaCategory.IMAGE)
    return await asyncio.to_thread(normalize_image, data, get_settings().image_max_side_px)


def _cache_path(media_id: str, category: MediaCategory) -> Path:
    digest = hashlib.sha256(f"{category}:{media_id}".encode()).hexdigest()
    return get_settings().image_cache_dir / f"{digest}.bin"


async def _read_cached(cache_path: Path) -> bytes | None:
    if await asyncio.to_thread(cache_path.exists):
        return await asyncio.to_thread(cache_path.read_bytes)
    return None


def _write_cache_atomically(cache_path: Path, data: bytes) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = cache_path.with_name(f"{cache_path.name}.{uuid.uuid4().hex}.tmp")
    temporary_path.write_bytes(data)
    temporary_path.replace(cache_path)


async def _download_cached(cache_path: Path, download: Callable[[], Awaitable[bytes]]) -> bytes:
    if (cached := await _read_cached(cache_path)) is not None:
        return cached
    data = await download()
    assert isinstance(data, bytes) and data, f"empty or non-bytes download for {cache_path}"
    await asyncio.to_thread(_write_cache_atomically, cache_path, data)
    return data


async def _download_message_media(
    client: TelegramClient, media_id: str, expected_category: MediaCategory
) -> bytes:
    ref = decode_media(media_id)
    if ref.kind != MediaKind.MESSAGE_ATTACHMENT:
        raise ValueError(f"{media_id!r} is not a message attachment")

    async def download() -> bytes:
        tl_message: TLMessage | None = await client.get_messages(ref.peer_id, ids=ref.msg_id)
        if tl_message is None:
            raise ValueError(f"Message for {media_id!r} not found")
        category = classify_media(tl_message.media)
        if category != expected_category:
            raise ValueError(f"{media_id!r} is {category or 'no media'}, not {expected_category}")
        return await client.download_media(tl_message, file=bytes)

    return await _download_cached(_cache_path(media_id, expected_category), download)


async def _download_profile_photo(client: TelegramClient, media_id: str, ref: MediaRef) -> bytes:
    async def download() -> bytes:
        data = await client.download_profile_photo(ref.peer_id, file=bytes)
        if data is None:
            raise ValueError(f"No profile photo for entity {ref.peer_id}")
        return data

    return await _download_cached(_cache_path(media_id, MediaCategory.IMAGE), download)
