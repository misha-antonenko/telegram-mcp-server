"""get_user tool implementation."""

from __future__ import annotations

from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest

from telegram_mcp_server.models.user import User
from telegram_mcp_server.yaml_utils import to_yaml


async def get_user(client: TelegramClient, user_id: int) -> str:
    """Return a YAML-serialised User for the given *user_id*."""
    full = await client(GetFullUserRequest(id=user_id))
    user = User.from_full(full)
    return to_yaml(user.model_dump())
