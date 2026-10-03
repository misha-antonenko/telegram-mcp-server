from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path

from telethon import TelegramClient

from telegram_mcp_server.ids import MediaKind, MediaRef, decode_media
from telegram_mcp_server.settings import get_settings


@dataclass(frozen=True, slots=True)
class Image:
    mime_type: str
    data_base64: str


async def get_image(client: TelegramClient, media_id: str) -> Image:
    settings = get_settings()
    cache_dir: Path = settings.image_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    safe_name = hashlib.sha256(media_id.encode()).hexdigest()
    ref: MediaRef = decode_media(media_id)

    if ref.kind == MediaKind.MESSAGE_ATTACHMENT:
        assert ref.msg_id is not None
        cache_path = cache_dir / f"{safe_name}.bin"
        if not cache_path.exists():
            msgs = await client.get_messages(ref.peer_id, ids=ref.msg_id)
            msg = msgs if not isinstance(msgs, list) else (msgs[0] if msgs else None)
            if msg is None or msg.media is None:
                raise ValueError(f"No media found for {media_id!r}")
            await client.download_media(msg, file=str(cache_path))
        data = cache_path.read_bytes()
    elif ref.kind == MediaKind.PROFILE_PHOTO:
        cache_path = cache_dir / f"{safe_name}.bin"
        if not cache_path.exists():
            photos = await client.get_profile_photos(ref.peer_id, limit=1)
            if not photos:
                raise ValueError(f"No profile photo for user {ref.peer_id}")
            await client.download_profile_photo(ref.peer_id, file=str(cache_path))
        data = cache_path.read_bytes()
    else:
        raise ValueError(f"Unknown media kind in {media_id!r}")

    return Image(
        mime_type=_guess_mime_type_from_magic_bytes(data),
        data_base64=base64.b64encode(data).decode(),
    )


def _guess_mime_type_from_magic_bytes(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"GIF8":
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"
