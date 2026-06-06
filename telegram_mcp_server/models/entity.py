from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Union

from telegram_mcp_server.ids import encode_user_photo
from telegram_mcp_server.models.base import ToolModel

if TYPE_CHECKING:
    from telethon.tl.types import (
        Channel as TLChannel,
        Chat as TLChat,
        messages,
        users,
    )


class UserEntity(ToolModel):
    type: Literal["user"] = "user"
    id: int
    name: str
    username: str | None = None
    bio: str | None = None
    profile_image_id: str | None = None

    @classmethod
    def from_full(cls, full: users.UserFull) -> UserEntity:
        """Build from a Telethon UserFull response."""
        user = full.users[0]
        first = getattr(user, "first_name", "") or ""
        last = getattr(user, "last_name", "") or ""
        name = (first + " " + last).strip() or str(user.id)
        username = getattr(user, "username", None)
        bio = getattr(full.full_user, "about", None) or None

        photo_id: str | None = None
        if getattr(user, "photo", None) is not None:
            photo_id = encode_user_photo(user.id)

        return cls(
            id=user.id,
            name=name,
            username=username,
            bio=bio,
            profile_image_id=photo_id,
        )


class ChannelEntity(ToolModel):
    type: Literal["channel"] = "channel"
    id: int
    name: str
    username: str | None = None
    about: str | None = None
    profile_image_id: str | None = None

    @classmethod
    def from_full(cls, full: messages.ChatFull, channel: TLChannel) -> ChannelEntity:
        """Build from a Telethon ChatFull response for a broadcast channel."""
        name = getattr(channel, "title", "") or str(channel.id)
        username = getattr(channel, "username", None)
        about = getattr(full.full_chat, "about", None) or None

        photo_id: str | None = None
        if getattr(channel, "photo", None) is not None:
            photo_id = encode_user_photo(channel.id)

        return cls(
            id=channel.id,
            name=name,
            username=username,
            about=about,
            profile_image_id=photo_id,
        )


class GroupEntity(ToolModel):
    type: Literal["group"] = "group"
    id: int
    name: str
    username: str | None = None
    about: str | None = None
    profile_image_id: str | None = None

    @classmethod
    def from_full_channel(
        cls, full: messages.ChatFull, channel: TLChannel
    ) -> GroupEntity:
        """Build from a Telethon ChatFull response for a supergroup/megagroup."""
        name = getattr(channel, "title", "") or str(channel.id)
        username = getattr(channel, "username", None)
        about = getattr(full.full_chat, "about", None) or None

        photo_id: str | None = None
        if getattr(channel, "photo", None) is not None:
            photo_id = encode_user_photo(channel.id)

        return cls(
            id=channel.id,
            name=name,
            username=username,
            about=about,
            profile_image_id=photo_id,
        )

    @classmethod
    def from_full_chat(cls, full: messages.ChatFull, chat: TLChat) -> GroupEntity:
        """Build from a Telethon ChatFull response for a basic group."""
        name = getattr(chat, "title", "") or str(chat.id)
        about = getattr(full.full_chat, "about", None) or None

        photo_id: str | None = None
        if getattr(chat, "photo", None) is not None:
            photo_id = encode_user_photo(chat.id)

        return cls(
            id=chat.id,
            name=name,
            username=None,
            about=about,
            profile_image_id=photo_id,
        )


Entity = Union[UserEntity, ChannelEntity, GroupEntity]
