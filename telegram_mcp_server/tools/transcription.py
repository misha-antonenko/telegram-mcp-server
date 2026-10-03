from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from telethon.tl.functions.messages import TranscribeAudioRequest

from telegram_mcp_server.models.media import MediaCategory, classify_media
from telegram_mcp_server.settings import get_settings

if TYPE_CHECKING:
    from telethon import TelegramClient
    from telethon.tl.types import Message as TLMessage

    from telegram_mcp_server.models.message import Message


async def transcribe_voice(client: TelegramClient, tl_message: TLMessage) -> str:
    settings = get_settings()
    request = TranscribeAudioRequest(peer=tl_message.peer_id, msg_id=tl_message.id)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + settings.transcription_timeout_seconds
    while (result := await client(request)).pending:
        if loop.time() >= deadline:
            raise TimeoutError(
                f"Transcription of message {tl_message.id} in {tl_message.peer_id} is still"
                f" pending after {settings.transcription_timeout_seconds}s; retry later or raise"
                " TRANSCRIPTION_TIMEOUT_SECONDS"
            )
        await asyncio.sleep(settings.transcription_poll_interval_seconds)
    return result.text


async def attach_voice_transcripts(
    client: TelegramClient, messages: list[Message], tl_messages: list[TLMessage]
) -> None:
    voice_messages = [
        (message, tl_message)
        for message, tl_message in zip(messages, tl_messages, strict=True)
        if classify_media(tl_message.media) == MediaCategory.VOICE
    ]
    transcripts = await asyncio.gather(
        *(transcribe_voice(client, tl_message) for _, tl_message in voice_messages)
    )
    for (message, _), transcript in zip(voice_messages, transcripts, strict=True):
        message.voice = transcript
