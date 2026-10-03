from __future__ import annotations

from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from telethon import TelegramClient


async def get_entity(client: TelegramClient, entity_id: int) -> str:
    entity = await client.get_entity(entity_id)
    result: Entity

    if isinstance(entity, User):
        full = await client(GetFullUserRequest(id=entity_id))
        result = UserEntity.from_full(full)
    elif isinstance(entity, Channel):
        full = await client(GetFullChannelRequest(channel=entity))
        is_group = getattr(entity, "megagroup", False) or getattr(entity, "gigagroup", False)
        if is_group:
            result = GroupEntity.from_full_channel(full, entity)
        else:
            result = ChannelEntity.from_full(full, entity)
    elif isinstance(entity, Chat):
        full = await client(GetFullChatRequest(chat_id=entity_id))
        result = GroupEntity.from_full_chat(full, entity)
    else:
        raise TypeError(f"Unknown entity type: {type(entity).__name__}")

    return to_yaml(result.model_dump())
