"""get_entity tool implementation."""

from __future__ import annotations

from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import Channel, Chat, User

from telegram_mcp_server.models.entity import (
    ChannelEntity,
    Entity,
    GroupEntity,
    UserEntity,
)
from telegram_mcp_server.yaml_utils import to_yaml


async def get_entity(client: TelegramClient, entity_id: int) -> str:
    """Return a YAML-serialised Entity for the given *entity_id*.

    Works for users, channels, and groups.
    """
    entity = await client.get_entity(entity_id)
    result: Entity

    if isinstance(entity, User):
        full = await client(GetFullUserRequest(id=entity_id))
        result = UserEntity.from_full(full)
    elif isinstance(entity, Channel):
        full = await client(GetFullChannelRequest(channel=entity))
        is_group = getattr(entity, "megagroup", False) or getattr(
            entity, "gigagroup", False
        )
        if is_group:
            result = GroupEntity.from_full_channel(full, entity)
        else:
            result = ChannelEntity.from_full(full, entity)
    elif isinstance(entity, Chat):
        full = await client(GetFullChatRequest(chat_id=entity_id))
        result = GroupEntity.from_full_chat(full, entity)
    else:
        raise ValueError(f"Unknown entity type: {type(entity).__name__}")

    return to_yaml(result.model_dump())
