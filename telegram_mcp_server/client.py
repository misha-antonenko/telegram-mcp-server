"""Singleton Telethon TelegramClient with async-safe initialization."""

from __future__ import annotations

import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession

_client: TelegramClient | None = None
_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def get_client() -> TelegramClient:
    """Return the connected singleton TelegramClient, creating it if needed."""
    global _client
    async with _get_lock():
        if _client is None or not _client.is_connected():
            from telegram_mcp_server.settings import get_settings

            s = get_settings()
            _client = TelegramClient(
                StringSession(s.session_string),
                s.api_id,
                s.api_hash,
            )
        if not _client.is_connected():
            await _client.connect()
    return _client


async def disconnect() -> None:
    """Disconnect the singleton client if connected."""
    global _client
    if _client is not None and _client.is_connected():
        await _client.disconnect()
